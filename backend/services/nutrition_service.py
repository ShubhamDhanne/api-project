"""
Nutrition service.
Queries the CalorieNinjas public API to retrieve calorie and macro data
for food items entered by the user.
API key is read from the CALORIE_NINJAS_API_KEY environment variable.
"""
import logging
import os

import requests

from config import Config

logger = logging.getLogger(__name__)

_BASE_URL = Config.CALORIE_NINJAS_BASE_URL


def get_nutrition_data(food_query: str) -> dict | None:
    """
    Fetch nutrition information for a food description from CalorieNinjas.

    Args:
        food_query: Natural-language food description, e.g. "2 eggs and toast".
    Returns:
        dict with 'items' list (each item has name, calories, protein_g, fat_g,
        carbohydrates_total_g, etc.) or None if the call fails.
    """
    api_key = os.getenv('CALORIE_NINJAS_API_KEY') or Config.CALORIE_NINJAS_API_KEY
    if not api_key:
        logger.warning('CALORIE_NINJAS_API_KEY not set — nutrition lookup skipped.')
        return None

    if not food_query or not food_query.strip():
        return None

    try:
        response = requests.get(
            f'{_BASE_URL}/nutrition',
            params={'query': food_query.strip()},
            headers={'X-Api-Key': api_key},
            timeout=10,
        )
        if response.ok:
            data = response.json()
            # API Ninjas returns a list directly; normalise to {"items": [...]}
            if isinstance(data, list):
                return {'items': data}
            return data
        logger.warning('CalorieNinjas API returned %s for query "%s"', response.status_code, food_query)
        return None
    except requests.RequestException as exc:
        logger.error('CalorieNinjas request error: %s', exc)
        return None


def summarise_nutrition(nutrition_response: dict) -> dict:
    """
    Sum up calories and macros from a CalorieNinjas response.

    Args:
        nutrition_response: The dict returned by get_nutrition_data().
    Returns:
        dict with total_calories, total_protein_g, total_fat_g, total_carbs_g.
    """
    if not nutrition_response or 'items' not in nutrition_response:
        return {}

    items = nutrition_response['items']

    def _num(val):
        """Return float if val is numeric, else 0 (handles premium-only string values)."""
        try:
            return float(val)
        except (TypeError, ValueError):
            return 0.0

    totals = {
        'total_calories': round(sum(_num(i.get('calories', 0)) for i in items), 1),
        'total_protein_g': round(sum(_num(i.get('protein_g', 0)) for i in items), 1),
        'total_fat_g': round(sum(_num(i.get('fat_total_g', 0)) for i in items), 1),
        'total_carbs_g': round(sum(_num(i.get('carbohydrates_total_g', 0)) for i in items), 1),
        'items': [
            {k: v for k, v in i.items() if not isinstance(v, str) or not 'premium' in v.lower()}
            for i in items
        ],
    }
    return totals
