"""
Health data CRUD service.
Handles creation, retrieval, update, and deletion of health records stored in
DynamoDB.  After every write it enqueues an SQS message for async analytics
processing by the Lambda worker.
"""
import logging
from datetime import datetime

from aws.dynamodb import (
    put_health_record,
    get_health_record,
    get_health_records,
    delete_health_record,
    update_health_record,
)
from aws.sqs import send_analytics_job
from services.nutrition_service import get_nutrition_data, summarise_nutrition

logger = logging.getLogger(__name__)


# ── Create ────────────────────────────────────────────────────────────────────

def create_health_record(user_id: str, date: str, data: dict) -> dict:
    """
    Create a new health record for the given user and date.
    If meals contain food descriptions, nutrition data is fetched from CalorieNinjas.
    A background analytics job is queued via SQS afterwards.

    Args:
        user_id: User's email address.
        date: Record date in YYYY-MM-DD format.
        data: Dict containing any of: steps, heart_rate, sleep_hours, sleep_time,
              wake_time, meals (list), exercise (dict), weight_kg.
    Returns:
        dict with success bool and either 'record' or 'error'.
    """
    # Validate date
    try:
        datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        return {'success': False, 'error': 'Invalid date format. Use YYYY-MM-DD.'}

    # Check for duplicate
    existing = get_health_record(user_id, date)
    if existing:
        return {'success': False, 'error': f'A health record for {date} already exists. Use PUT to update it.'}

    # Enrich meals with nutrition data from CalorieNinjas
    meals = data.get('meals', [])
    enriched_meals = _enrich_meals_with_nutrition(meals)
    if enriched_meals:
        data['meals'] = enriched_meals

    data['created_at'] = datetime.utcnow().isoformat()

    success = put_health_record(user_id, date, data)
    if not success:
        return {'success': False, 'error': 'Failed to save health record.'}

    # Queue async analytics job — fire and forget
    send_analytics_job(user_id, date, event_type='record_upsert')

    record = get_health_record(user_id, date)
    logger.info('Health record created: user=%s date=%s', user_id, date)
    return {'success': True, 'record': record}


# ── Read ──────────────────────────────────────────────────────────────────────

def get_record(user_id: str, date: str) -> dict:
    """
    Retrieve a single health record.

    Args:
        user_id: User's email.
        date: Record date YYYY-MM-DD.
    Returns:
        dict with success bool and 'record' or 'error'.
    """
    record = get_health_record(user_id, date)
    if record is None:
        return {'success': False, 'error': f'No health record found for {date}.'}
    return {'success': True, 'record': record}


def get_records(user_id: str, start_date: str = None, end_date: str = None) -> dict:
    """
    Retrieve all health records for a user, optionally filtered by date range.

    Args:
        user_id: User's email.
        start_date: Optional start date YYYY-MM-DD.
        end_date: Optional end date YYYY-MM-DD.
    Returns:
        dict with success bool and 'records' list.
    """
    records = get_health_records(user_id, start_date, end_date)
    return {'success': True, 'records': records}


def get_recent_records(user_id: str, days: int = 7) -> list:
    """
    Retrieve the N most recent health records for a user.

    Args:
        user_id: User's email.
        days: Number of days to look back.
    Returns:
        List of record dicts sorted by date descending.
    """
    from datetime import timedelta
    end = datetime.utcnow().strftime('%Y-%m-%d')
    start = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d')
    records = get_health_records(user_id, start_date=start, end_date=end)
    return records


# ── Update ────────────────────────────────────────────────────────────────────

def update_record(user_id: str, date: str, data: dict) -> dict:
    """
    Update an existing health record.

    Args:
        user_id: User's email.
        date: Record date YYYY-MM-DD.
        data: Fields to update.
    Returns:
        dict with success bool and 'record' or 'error'.
    """
    existing = get_health_record(user_id, date)
    if existing is None:
        return {'success': False, 'error': f'No health record found for {date}.'}

    # Re-enrich meals if updated
    if 'meals' in data:
        data['meals'] = _enrich_meals_with_nutrition(data['meals'])

    updated = update_health_record(user_id, date, data)
    if updated is None:
        return {'success': False, 'error': 'Failed to update health record.'}

    send_analytics_job(user_id, date, event_type='record_upsert')
    logger.info('Health record updated: user=%s date=%s', user_id, date)
    return {'success': True, 'record': updated}


# ── Delete ────────────────────────────────────────────────────────────────────

def delete_record(user_id: str, date: str) -> dict:
    """
    Delete a health record.

    Args:
        user_id: User's email.
        date: Record date YYYY-MM-DD.
    Returns:
        dict with success bool.
    """
    existing = get_health_record(user_id, date)
    if existing is None:
        return {'success': False, 'error': f'No health record found for {date}.'}

    success = delete_health_record(user_id, date)
    if not success:
        return {'success': False, 'error': 'Failed to delete health record.'}

    send_analytics_job(user_id, date, event_type='record_delete')
    logger.info('Health record deleted: user=%s date=%s', user_id, date)
    return {'success': True}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _enrich_meals_with_nutrition(meals: list) -> list:
    """
    For each meal that has a 'food' description, fetch nutrition data and
    attach it to the meal dict.

    Args:
        meals: List of meal dicts, each may have 'food', 'type', 'time' keys.
    Returns:
        Enriched list of meal dicts.
    """
    enriched = []
    for meal in meals:
        if isinstance(meal, dict) and meal.get('food'):
            nutrition = get_nutrition_data(meal['food'])
            if nutrition:
                summary = summarise_nutrition(nutrition)
                meal['nutrition'] = summary
                meal['calories'] = summary.get('total_calories', 0)
        enriched.append(meal)
    return enriched
