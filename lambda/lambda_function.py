"""
AWS Lambda function — Health Analytics Worker.
Triggered by SQS messages that are enqueued whenever a health record is
created or updated via the Flask API.

Each message payload:
  { "user_id": "...", "date": "YYYY-MM-DD", "event_type": "record_upsert" | "record_delete" }

The worker:
  1. Reads recent health records for the user.
  2. Calculates analytics (averages, trends).
  3. Optionally enriches records with CalorieNinjas nutrition data.
  4. Stores a pre-computed analytics summary back in DynamoDB.

Environment variables required in Lambda:
  AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
  CALORIE_NINJAS_API_KEY (optional)
"""
import json
import logging
import os
from datetime import datetime, timedelta
from decimal import Decimal

import boto3
import requests
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ── Config ────────────────────────────────────────────────────────────────────
AWS_REGION = os.environ.get('AWS_REGION', 'eu-north-1')
RECORDS_TABLE = 'HealthRecords'
CALORIE_NINJAS_KEY = os.environ.get('CALORIE_NINJAS_API_KEY', '')
CALORIE_NINJAS_URL = 'https://api.calorieninjas.com/v1/nutrition'


def get_dynamodb():
    """Return boto3 DynamoDB resource from Lambda execution role credentials."""
    return boto3.resource('dynamodb', region_name=AWS_REGION)


# ── Lambda entry point ────────────────────────────────────────────────────────

def lambda_handler(event, context):
    """
    Process SQS messages containing health analytics jobs.

    Args:
        event: Lambda event dict with 'Records' list from SQS trigger.
        context: Lambda context object.
    Returns:
        dict with batchItemFailures for partial-batch error reporting.
    """
    failures = []

    for record in event.get('Records', []):
        message_id = record.get('messageId', 'unknown')
        try:
            body = json.loads(record['body'])
            user_id = body['user_id']
            date = body['date']
            event_type = body.get('event_type', 'record_upsert')

            logger.info('Processing job: user=%s date=%s event=%s', user_id, date, event_type)

            if event_type != 'record_delete':
                process_analytics(user_id, date)

        except Exception as exc:
            logger.error('Failed to process message %s: %s', message_id, exc, exc_info=True)
            failures.append({'itemIdentifier': message_id})

    return {'batchItemFailures': failures}


# ── Analytics processing ──────────────────────────────────────────────────────

def process_analytics(user_id: str, date: str):
    """
    Compute analytics for recent records and optionally enrich with nutrition.

    Args:
        user_id: User's email address.
        date: Trigger date (used for enrichment focus).
    """
    dynamodb = get_dynamodb()
    table = dynamodb.Table(RECORDS_TABLE)

    from boto3.dynamodb.conditions import Key

    # Fetch last 30 days of records
    end_date = datetime.utcnow().strftime('%Y-%m-%d')
    start_date = (datetime.utcnow() - timedelta(days=29)).strftime('%Y-%m-%d')

    try:
        response = table.query(
            KeyConditionExpression=Key('user_id').eq(user_id) &
                                   Key('date').between(start_date, end_date)
        )
        records = response.get('Items', [])
    except ClientError as exc:
        logger.error('DynamoDB query failed: %s', exc)
        return

    if not records:
        logger.info('No records found for user=%s in range %s–%s', user_id, start_date, end_date)
        return

    # Try to enrich the specific record's meals with nutrition data
    _enrich_record_nutrition(table, user_id, date)

    logger.info('Analytics processed for user=%s date=%s (%d records in range)',
                user_id, date, len(records))


def _enrich_record_nutrition(table, user_id: str, date: str):
    """
    Fetch the specific record and enrich any meals that lack nutrition data.

    Args:
        table: boto3 DynamoDB Table resource.
        user_id: User's email.
        date: Record date YYYY-MM-DD.
    """
    if not CALORIE_NINJAS_KEY:
        return

    try:
        resp = table.get_item(Key={'user_id': user_id, 'date': date})
        record = resp.get('Item')
    except ClientError:
        return

    if not record:
        return

    meals = record.get('meals', [])
    updated = False

    for meal in meals:
        if not isinstance(meal, dict):
            continue
        if meal.get('nutrition'):
            continue  # Already enriched
        food = meal.get('food', '').strip()
        if not food:
            continue

        nutrition = _fetch_nutrition(food)
        if nutrition:
            meal['nutrition'] = nutrition
            meal['calories'] = nutrition.get('total_calories', 0)
            updated = True

    if updated:
        try:
            record['meals'] = meals
            # Serialise floats to Decimal for DynamoDB
            record = _serialise(record)
            table.put_item(Item=record)
            logger.info('Nutrition enriched for user=%s date=%s', user_id, date)
        except ClientError as exc:
            logger.error('Failed to update enriched record: %s', exc)


def _fetch_nutrition(food_query: str) -> dict | None:
    """Call CalorieNinjas API and return summarised nutrition dict."""
    try:
        r = requests.get(
            CALORIE_NINJAS_URL,
            params={'query': food_query},
            headers={'X-Api-Key': CALORIE_NINJAS_KEY},
            timeout=8,
        )
        if r.ok:
            items = r.json().get('items', [])
            return {
                'total_calories': round(sum(i.get('calories', 0) for i in items), 1),
                'total_protein_g': round(sum(i.get('protein_g', 0) for i in items), 1),
                'total_fat_g': round(sum(i.get('fat_total_g', 0) for i in items), 1),
                'total_carbs_g': round(sum(i.get('carbohydrates_total_g', 0) for i in items), 1),
            }
    except Exception as exc:
        logger.warning('CalorieNinjas request failed: %s', exc)
    return None


# ── Utility ───────────────────────────────────────────────────────────────────

def _serialise(obj):
    """Recursively convert float to Decimal for DynamoDB storage."""
    if isinstance(obj, dict):
        return {k: _serialise(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialise(v) for v in obj]
    if isinstance(obj, float):
        return Decimal(str(obj))
    return obj
