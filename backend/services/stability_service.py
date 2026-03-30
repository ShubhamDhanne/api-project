"""
Routine Stability service.
Calls the classmate's Routine Stability Index API with the user's recent
health records to compute a behavioural consistency score.

API endpoint: POST https://2u736o5k8k.execute-api.us-east-1.amazonaws.com/prod/api/stability
No authentication required on the classmate's API.
"""
import logging
from datetime import datetime, timedelta

import requests

from aws.dynamodb import get_health_records
from config import Config

logger = logging.getLogger(__name__)


def get_stability_score(user_id: str, days: int = 7) -> dict:
    """
    Fetch the Routine Stability Index for a user based on their recent health records.

    Collects sleep times, meal times, and exercise data from the last `days` days
    and sends them to the classmate's API.  Returns the full stability response or
    an error dict if there is insufficient data.

    Args:
        user_id: User's email address.
        days: Number of recent days of data to include (default 7).
    Returns:
        dict — either the stability API response or {'success': False, 'error': '...'}.
    """
    end_date = datetime.utcnow().strftime('%Y-%m-%d')
    start_date = (datetime.utcnow() - timedelta(days=days - 1)).strftime('%Y-%m-%d')

    records = get_health_records(user_id, start_date=start_date, end_date=end_date)

    if len(records) < 2:
        return {
            'success': False,
            'error': 'Not enough data to calculate stability score. Add at least 2 days of data.',
        }

    # Sort oldest-first so timeline is coherent for the API
    records_sorted = sorted(records, key=lambda r: r.get('date', ''))

    # ── Build sleep payload ────────────────────────────────────────────────────
    sleep_times = []
    wake_times = []
    for r in records_sorted:
        st = r.get('sleep_time')
        wt = r.get('wake_time')
        if st and wt and _valid_hhmm(st) and _valid_hhmm(wt):
            sleep_times.append(_to_hhmm(st))
            wake_times.append(_to_hhmm(wt))

    if len(sleep_times) < 2:
        return {
            'success': False,
            'error': 'Not enough sleep time data. Please enter sleep and wake times for at least 2 days.',
        }

    # ── Build meals payload ────────────────────────────────────────────────────
    meals_payload = []
    for r in records_sorted:
        day_meals = {}
        for meal in (r.get('meals') or []):
            if not isinstance(meal, dict):
                continue
            meal_type = meal.get('type', '').lower()
            meal_time = meal.get('time', '')
            if meal_type in ('breakfast', 'lunch', 'dinner') and _valid_hhmm(meal_time):
                day_meals[meal_type] = _to_hhmm(meal_time)
        if day_meals:
            meals_payload.append(day_meals)

    # ── Build exercise payload ────────────────────────────────────────────────
    exercise_days = []
    exercise_types = set()
    for r in records_sorted:
        ex = r.get('exercise')
        if ex and isinstance(ex, dict) and ex.get('duration_minutes', 0):
            exercise_days.append(ex.get('duration_minutes', 0))
            if ex.get('type'):
                exercise_types.add(ex['type'])

    freq_per_week = min(len(exercise_days), 7)
    avg_duration = round(sum(exercise_days) / len(exercise_days)) if exercise_days else 0

    # ── Assemble and send request ────────────────────────────────────────────
    payload = {
        'user_id': user_id,
        'sleep': {
            'sleep_times': sleep_times,
            'wake_times': wake_times,
        },
        'exercise': {
            'frequency_per_week': freq_per_week,
            'duration_minutes': avg_duration,
        },
    }
    if exercise_types:
        payload['exercise']['types'] = list(exercise_types)
    if meals_payload:
        payload['meals'] = meals_payload

    logger.info(
        'Calling stability API for user=%s with %d sleep entries, %d meal days',
        user_id, len(sleep_times), len(meals_payload),
    )

    try:
        resp = requests.post(
            f'{Config.STABILITY_API_BASE}/api/stability',
            json=payload,
            timeout=15,
        )
        if resp.ok:
            data = resp.json()
            data['success'] = True
            return data
        logger.warning('Stability API returned %s: %s', resp.status_code, resp.text)
        return {
            'success': False,
            'error': f'Stability API error (HTTP {resp.status_code}).',
        }
    except requests.RequestException as exc:
        logger.error('Stability API request failed: %s', exc)
        return {'success': False, 'error': 'Could not reach the Routine Stability API.'}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _valid_hhmm(value: str) -> bool:
    """Return True if value is a non-empty string that can be formatted as HH:MM."""
    if not value or not isinstance(value, str):
        return False
    # Accept "HH:MM" or "HH:MM:SS" — we'll truncate to HH:MM
    parts = value.strip().split(':')
    return len(parts) >= 2


def _to_hhmm(value: str) -> str:
    """Normalise a time string to HH:MM (strips seconds if present)."""
    parts = value.strip().split(':')
    return f'{parts[0].zfill(2)}:{parts[1].zfill(2)}'
