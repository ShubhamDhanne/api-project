"""
BMI service.
Calls the API Ninjas Body Mass Index endpoint to calculate BMI and
return a health category for a given weight and height.

API docs: https://api-ninjas.com/api/bodymassindex
Endpoint: GET https://api.api-ninjas.com/v1/bodymassindex
Params:   weight_kg, height_cm
Auth:     X-Api-Key header (shared CALORIE_NINJAS_API_KEY)
"""
import logging
import os

import requests

from config import Config

logger = logging.getLogger(__name__)

# Built at call-time so the URL always reflects the current config
_BMI_URL = f'{Config.CALORIE_NINJAS_BASE_URL}/bodymassindex'


def get_bmi(weight_kg: float, height_cm: float) -> dict | None:
    """
    Calculate BMI via the API Ninjas BMI endpoint.

    Args:
        weight_kg:  User's weight in kilograms.
        height_cm:  User's height in centimetres.
    Returns:
        dict with keys: bmi (float), category (str), healthy_bmi_range (str)
        or None if the API call fails or key is not configured.
    """
    # Read key at call-time so it picks up the value loaded from .env on startup
    api_key = os.getenv('CALORIE_NINJAS_API_KEY') or Config.CALORIE_NINJAS_API_KEY
    if not api_key:
        logger.warning('CALORIE_NINJAS_API_KEY not set — BMI lookup skipped.')
        return None

    try:
        response = requests.get(
            _BMI_URL,
            params={'weight_kg': weight_kg, 'height_cm': height_cm},
            headers={'X-Api-Key': api_key},
            timeout=10,
        )
        if response.ok:
            data = response.json()
            # API Ninjas returns a single dict for BMI
            if isinstance(data, list) and data:
                data = data[0]
            logger.info('BMI result for %.1f kg / %.1f cm: %s', weight_kg, height_cm, data)
            return data
        logger.warning('API Ninjas BMI returned %s', response.status_code)
        return None
    except requests.RequestException as exc:
        logger.error('BMI API request error: %s', exc)
        return None
