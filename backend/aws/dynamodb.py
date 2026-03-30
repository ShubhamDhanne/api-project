"""
DynamoDB helper module.
Provides a centralised boto3 resource/client, table creation, and
all CRUD operations for HealthUsers and HealthRecords tables.
Credentials are loaded from environment variables — never hardcoded.
"""
import logging
from decimal import Decimal
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

from config import Config

logger = logging.getLogger(__name__)


# ── boto3 resource/client factories ──────────────────────────────────────────

def get_dynamodb_resource():
    """Return a boto3 DynamoDB resource using env-based credentials."""
    return boto3.resource(
        'dynamodb',
        region_name=Config.AWS_REGION,
        aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
    )


def get_dynamodb_client():
    """Return a boto3 DynamoDB client using env-based credentials."""
    return boto3.client(
        'dynamodb',
        region_name=Config.AWS_REGION,
        aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
    )


# ── Table creation ────────────────────────────────────────────────────────────

def create_tables():
    """
    Create HealthUsers and HealthRecords DynamoDB tables if they do not exist.
    Both tables use on-demand (PAY_PER_REQUEST) billing for auto-scaling.
    """
    dynamodb = get_dynamodb_resource()

    # HealthUsers — PK: user_id (email)
    _create_table_if_missing(
        dynamodb,
        table_name=Config.DYNAMODB_USERS_TABLE,
        key_schema=[{'AttributeName': 'user_id', 'KeyType': 'HASH'}],
        attribute_definitions=[{'AttributeName': 'user_id', 'AttributeType': 'S'}],
    )

    # HealthRecords — PK: user_id, SK: date (YYYY-MM-DD)
    _create_table_if_missing(
        dynamodb,
        table_name=Config.DYNAMODB_RECORDS_TABLE,
        key_schema=[
            {'AttributeName': 'user_id', 'KeyType': 'HASH'},
            {'AttributeName': 'date', 'KeyType': 'RANGE'},
        ],
        attribute_definitions=[
            {'AttributeName': 'user_id', 'AttributeType': 'S'},
            {'AttributeName': 'date', 'AttributeType': 'S'},
        ],
    )


def _create_table_if_missing(dynamodb, table_name, key_schema, attribute_definitions):
    """
    Create a DynamoDB table with on-demand billing if it does not already exist.

    Args:
        dynamodb: boto3 DynamoDB resource.
        table_name: Name of the DynamoDB table.
        key_schema: List of key schema definitions.
        attribute_definitions: List of attribute definitions.
    """
    try:
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=key_schema,
            AttributeDefinitions=attribute_definitions,
            BillingMode='PAY_PER_REQUEST',
        )
        table.wait_until_exists()
        logger.info('Created DynamoDB table: %s', table_name)
    except ClientError as exc:
        if exc.response['Error']['Code'] == 'ResourceInUseException':
            logger.info('DynamoDB table already exists: %s', table_name)
        else:
            logger.error('Error creating table %s: %s', table_name, exc)
            raise


# ── Utility: convert DynamoDB Decimals to int/float ──────────────────────────

def _deserialise(obj):
    """Recursively convert Decimal values returned by DynamoDB to int/float."""
    if isinstance(obj, dict):
        return {k: _deserialise(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deserialise(v) for v in obj]
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj


def _serialise(obj):
    """Recursively convert float to Decimal for DynamoDB storage."""
    if isinstance(obj, dict):
        return {k: _serialise(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialise(v) for v in obj]
    if isinstance(obj, float):
        return Decimal(str(obj))
    return obj


# ── HealthUsers operations ────────────────────────────────────────────────────

def put_user(user_id: str, item: dict):
    """
    Create or overwrite a user record in HealthUsers.

    Args:
        user_id: The user's email address (partition key).
        item: Dict of attributes to store (must NOT include raw password).
    Returns:
        True on success, False on failure.
    """
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(Config.DYNAMODB_USERS_TABLE)
    item['user_id'] = user_id
    item = _serialise(item)
    try:
        table.put_item(Item=item)
        return True
    except ClientError as exc:
        logger.error('put_user error for %s: %s', user_id, exc)
        return False


def get_user(user_id: str) -> dict | None:
    """
    Retrieve a user record from HealthUsers.

    Args:
        user_id: The user's email address.
    Returns:
        User dict or None if not found.
    """
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(Config.DYNAMODB_USERS_TABLE)
    try:
        response = table.get_item(Key={'user_id': user_id})
        item = response.get('Item')
        return _deserialise(item) if item else None
    except ClientError as exc:
        logger.error('get_user error for %s: %s', user_id, exc)
        return None


# ── HealthRecords operations ──────────────────────────────────────────────────

def put_health_record(user_id: str, date: str, item: dict):
    """
    Create or overwrite a health record for a given user and date.

    Args:
        user_id: The user's email address (partition key).
        date: Record date in YYYY-MM-DD format (sort key).
        item: Health data attributes.
    Returns:
        True on success, False on failure.
    """
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(Config.DYNAMODB_RECORDS_TABLE)
    item['user_id'] = user_id
    item['date'] = date
    item['updated_at'] = datetime.utcnow().isoformat()
    item = _serialise(item)
    try:
        table.put_item(Item=item)
        return True
    except ClientError as exc:
        logger.error('put_health_record error for %s/%s: %s', user_id, date, exc)
        return False


def get_health_record(user_id: str, date: str) -> dict | None:
    """
    Retrieve a single health record.

    Args:
        user_id: The user's email address.
        date: Record date in YYYY-MM-DD format.
    Returns:
        Record dict or None if not found.
    """
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(Config.DYNAMODB_RECORDS_TABLE)
    try:
        response = table.get_item(Key={'user_id': user_id, 'date': date})
        item = response.get('Item')
        return _deserialise(item) if item else None
    except ClientError as exc:
        logger.error('get_health_record error for %s/%s: %s', user_id, date, exc)
        return None


def get_health_records(user_id: str, start_date: str = None, end_date: str = None) -> list:
    """
    Query all health records for a user, optionally within a date range.

    Args:
        user_id: The user's email address.
        start_date: Optional inclusive start date (YYYY-MM-DD).
        end_date: Optional inclusive end date (YYYY-MM-DD).
    Returns:
        List of record dicts sorted by date descending.
    """
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(Config.DYNAMODB_RECORDS_TABLE)

    from boto3.dynamodb.conditions import Key, Attr

    try:
        if start_date and end_date:
            response = table.query(
                KeyConditionExpression=Key('user_id').eq(user_id) &
                                       Key('date').between(start_date, end_date)
            )
        elif start_date:
            response = table.query(
                KeyConditionExpression=Key('user_id').eq(user_id) &
                                       Key('date').gte(start_date)
            )
        else:
            response = table.query(
                KeyConditionExpression=Key('user_id').eq(user_id)
            )
        items = response.get('Items', [])
        items.sort(key=lambda x: x.get('date', ''), reverse=True)
        return [_deserialise(item) for item in items]
    except ClientError as exc:
        logger.error('get_health_records error for %s: %s', user_id, exc)
        return []


def delete_health_record(user_id: str, date: str) -> bool:
    """
    Delete a health record.

    Args:
        user_id: The user's email address.
        date: Record date in YYYY-MM-DD format.
    Returns:
        True on success, False on failure.
    """
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(Config.DYNAMODB_RECORDS_TABLE)
    try:
        table.delete_item(Key={'user_id': user_id, 'date': date})
        return True
    except ClientError as exc:
        logger.error('delete_health_record error for %s/%s: %s', user_id, date, exc)
        return False


def update_health_record(user_id: str, date: str, updates: dict) -> dict | None:
    """
    Partially update a health record using UpdateExpression.

    Args:
        user_id: The user's email address.
        date: Record date in YYYY-MM-DD format.
        updates: Dict of fields to update (merged with existing record).
    Returns:
        Updated record dict or None on failure.
    """
    # Fetch existing record, merge, and overwrite — simpler than building
    # UpdateExpression strings dynamically and avoids reserved-word conflicts.
    existing = get_health_record(user_id, date)
    if existing is None:
        return None
    existing.update(updates)
    existing['updated_at'] = datetime.utcnow().isoformat()
    success = put_health_record(user_id, date, existing)
    return existing if success else None
