"""
Analytics service.
Computes daily, weekly, and monthly health analytics from DynamoDB records.
All heavy computation is triggered asynchronously via SQS/Lambda; this module
provides the aggregation logic used both in the Flask API and the Lambda worker.
"""
import logging
from datetime import datetime, timedelta
from statistics import mean, stdev

from aws.dynamodb import get_health_record, get_health_records

logger = logging.getLogger(__name__)


# ── Daily analytics ───────────────────────────────────────────────────────────

def get_daily_analytics(user_id: str, date: str) -> dict:
    """
    Return analytics for a single day's health record.

    Args:
        user_id: User's email.
        date: Date in YYYY-MM-DD format.
    Returns:
        dict with success bool and 'analytics' or 'error'.
    """
    record = get_health_record(user_id, date)
    if not record:
        return {'success': False, 'error': f'No health record found for {date}.'}

    analytics = _compute_daily(record)
    return {'success': True, 'analytics': analytics, 'record': record}


def _compute_daily(record: dict) -> dict:
    """Derive analytics fields from a single record."""
    steps = record.get('steps', 0) or 0
    sleep_hours = record.get('sleep_hours', 0) or 0
    heart_rate = record.get('heart_rate', 0) or 0
    weight = record.get('weight_kg', 0) or 0

    # Calories burned estimate: 0.04 kcal per step (rough approximation)
    calories_from_steps = round(steps * 0.04, 1)

    # Meal calories
    meals = record.get('meals', []) or []
    meal_calories = sum(m.get('calories', 0) or 0 for m in meals if isinstance(m, dict))

    # Exercise calories
    exercise = record.get('exercise') or {}
    exercise_calories = exercise.get('calories_burned', 0) or 0

    total_calories = round(meal_calories + calories_from_steps + exercise_calories, 1)

    # Sleep quality
    sleep_quality = _rate_sleep(sleep_hours)

    # Step goal (10,000 steps)
    step_goal_pct = min(round((steps / 10000) * 100, 1), 100)

    return {
        'date': record.get('date'),
        'steps': steps,
        'step_goal_pct': step_goal_pct,
        'heart_rate': heart_rate,
        'sleep_hours': sleep_hours,
        'sleep_quality': sleep_quality,
        'calories_burned': record.get('calories_burned') or total_calories,
        'meal_calories': meal_calories,
        'weight_kg': weight,
        'exercise_duration_min': (exercise.get('duration_minutes') or 0),
        'exercise_type': exercise.get('type', ''),
    }


def _rate_sleep(hours: float) -> str:
    """Return a qualitative label for sleep duration."""
    if hours >= 7.5:
        return 'Excellent'
    if hours >= 6.5:
        return 'Good'
    if hours >= 5.5:
        return 'Fair'
    return 'Poor'


# ── Weekly analytics ──────────────────────────────────────────────────────────

def get_weekly_analytics(user_id: str, start_date: str) -> dict:
    """
    Return a weekly summary starting from start_date (covers 7 days).

    Args:
        user_id: User's email.
        start_date: First day of the week (YYYY-MM-DD).
    Returns:
        dict with success bool and 'analytics' or 'error'.
    """
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d')
    except ValueError:
        return {'success': False, 'error': 'Invalid date format. Use YYYY-MM-DD.'}

    end = start + timedelta(days=6)
    end_date = end.strftime('%Y-%m-%d')

    records = get_health_records(user_id, start_date=start_date, end_date=end_date)
    if not records:
        return {'success': False, 'error': 'No records found for this week.'}

    analytics = _compute_period_analytics(records, label='weekly', start=start_date, end=end_date)
    return {'success': True, 'analytics': analytics}


# ── Monthly analytics ─────────────────────────────────────────────────────────

def get_monthly_analytics(user_id: str, year: int, month: int) -> dict:
    """
    Return a monthly summary.

    Args:
        user_id: User's email.
        year: Four-digit year.
        month: Month number (1-12).
    Returns:
        dict with success bool and 'analytics' or 'error'.
    """
    try:
        start_date = f'{year:04d}-{month:02d}-01'
        # Last day of month
        if month == 12:
            next_month_start = datetime(year + 1, 1, 1)
        else:
            next_month_start = datetime(year, month + 1, 1)
        end_date = (next_month_start - timedelta(days=1)).strftime('%Y-%m-%d')
    except ValueError as exc:
        return {'success': False, 'error': f'Invalid year/month: {exc}'}

    records = get_health_records(user_id, start_date=start_date, end_date=end_date)
    if not records:
        return {'success': False, 'error': 'No records found for this month.'}

    analytics = _compute_period_analytics(records, label='monthly', start=start_date, end=end_date)
    return {'success': True, 'analytics': analytics}


# ── Shared aggregation helper ─────────────────────────────────────────────────

def _compute_period_analytics(records: list, label: str, start: str, end: str) -> dict:
    """
    Aggregate stats across a list of health records.

    Args:
        records: List of health record dicts.
        label: 'weekly' or 'monthly'.
        start: Period start date string.
        end: Period end date string.
    Returns:
        Summary analytics dict.
    """
    steps_list = [r.get('steps', 0) or 0 for r in records]
    sleep_list = [r.get('sleep_hours', 0) or 0 for r in records]
    hr_list = [r.get('heart_rate', 0) or 0 for r in records if r.get('heart_rate')]

    # Calories: prefer stored value, fall back to step estimate
    cal_list = []
    for r in records:
        steps = r.get('steps', 0) or 0
        meals_cal = sum(m.get('calories', 0) or 0 for m in (r.get('meals') or []) if isinstance(m, dict))
        exercise_cal = (r.get('exercise') or {}).get('calories_burned', 0) or 0
        cal = r.get('calories_burned') or (round(steps * 0.04, 1) + meals_cal + exercise_cal)
        cal_list.append(cal)

    weight_list = [r.get('weight_kg', 0) or 0 for r in records if r.get('weight_kg')]

    # Daily breakdown for charts
    daily = sorted(
        [{'date': r['date'], 'steps': r.get('steps', 0) or 0,
          'sleep_hours': r.get('sleep_hours', 0) or 0,
          'calories': cal_list[i]} for i, r in enumerate(records)],
        key=lambda x: x['date'],
    )

    def safe_mean(lst):
        valid = [x for x in lst if x]
        return round(mean(valid), 1) if valid else 0

    return {
        'period': label,
        'start_date': start,
        'end_date': end,
        'record_count': len(records),
        'avg_steps': safe_mean(steps_list),
        'total_steps': sum(steps_list),
        'avg_sleep_hours': safe_mean(sleep_list),
        'avg_heart_rate': safe_mean(hr_list),
        'total_calories': round(sum(cal_list), 1),
        'avg_calories': safe_mean(cal_list),
        'avg_weight_kg': safe_mean(weight_list),
        'best_sleep_day': max(records, key=lambda r: r.get('sleep_hours', 0) or 0, default={}).get('date', ''),
        'best_steps_day': max(records, key=lambda r: r.get('steps', 0) or 0, default={}).get('date', ''),
        'daily_breakdown': daily,
    }
