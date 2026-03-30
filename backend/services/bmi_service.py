"""
BMI service.
Calculates BMI locally using the standard WHO formula and enriches
the result with exercise calories burned data from the API Ninjas
caloriesburned public API.

API docs: https://api-ninjas.com/api/caloriesburned
Endpoint: GET https://api.api-ninjas.com/v1/caloriesburned
Params:   activity (str), weight (kg), duration (minutes)
Auth:     X-Api-Key header (shared CALORIE_NINJAS_API_KEY)
"""
import logging
import os

import requests

from config import Config

logger = logging.getLogger(__name__)

_CALORIES_URL = f'{Config.CALORIE_NINJAS_BASE_URL}/caloriesburned'

# WHO BMI category thresholds
_BMI_CATEGORIES = [
    (0,    18.5, 'Underweight'),
    (18.5, 25.0, 'Normal weight'),
    (25.0, 30.0, 'Overweight'),
    (30.0, 35.0, 'Obese (Class I)'),
    (35.0, 40.0, 'Obese (Class II)'),
    (40.0, 9999, 'Obese (Class III)'),
]


def get_bmi(weight_kg: float, height_cm: float) -> dict:
    """
    Calculate BMI using the WHO formula and return category.

    Args:
        weight_kg:  User's weight in kilograms.
        height_cm:  User's height in centimetres.
    Returns:
        dict with bmi (float), category (str), healthy_bmi_range (str).
    """
    height_m = height_cm / 100.0
    bmi = round(weight_kg / (height_m ** 2), 1)

    category = 'Unknown'
    for low, high, label in _BMI_CATEGORIES:
        if low <= bmi < high:
            category = label
            break

    return {
        'bmi': bmi,
        'category': category,
        'healthy_bmi_range': '18.5 - 24.9',
        'weight_kg': weight_kg,
        'height_cm': height_cm,
    }


def get_calories_burned(activity: str, weight_kg: float, duration_minutes: int) -> list | None:
    """
    Fetch calories burned for a given activity using API Ninjas caloriesburned API.

    Args:
        activity:         Activity name (e.g. 'running', 'cycling', 'swimming').
        weight_kg:        User's weight in kilograms.
        duration_minutes: Duration of the activity in minutes.
    Returns:
        List of matching activity dicts with calories_per_hour and total_calories,
        or None if the API call fails.
    """
    api_key = os.getenv('CALORIE_NINJAS_API_KEY') or Config.CALORIE_NINJAS_API_KEY
    if not api_key:
        logger.warning('CALORIE_NINJAS_API_KEY not set — calories burned lookup skipped.')
        return None

    if not activity or not activity.strip():
        return None

    try:
        response = requests.get(
            _CALORIES_URL,
            params={
                'activity': activity.strip(),
                'weight': weight_kg,
                'duration': duration_minutes,
            },
            headers={'X-Api-Key': api_key},
            timeout=10,
        )
        if response.ok:
            data = response.json()
            logger.info('Calories burned for "%s": %d results', activity, len(data))
            return data[:5]  # Return top 5 matches
        logger.warning(
            'API Ninjas caloriesburned returned %s for "%s"', response.status_code, activity
        )
        return None
    except requests.RequestException as exc:
        logger.error('Calories burned API request error: %s', exc)
        return None
