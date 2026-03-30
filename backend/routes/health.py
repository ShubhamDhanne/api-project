"""
Health data CRUD routes.
All endpoints require a valid JWT Bearer token.

POST   /api/health                    — create a health record
GET    /api/health                    — list all records (optional ?start_date=&end_date=)
GET    /api/health/<date>             — get a single record
PUT    /api/health/<date>             — update a record
DELETE /api/health/<date>             — delete a record
POST   /api/health/nutrition-lookup   — proxy CalorieNinjas lookup
"""
import logging

from flask import Blueprint, request, jsonify, g

from routes.middleware import auth_required
from services import health_service
from services.nutrition_service import get_nutrition_data, summarise_nutrition

logger = logging.getLogger(__name__)

health_bp = Blueprint('health', __name__)


@health_bp.route('', methods=['POST'])
@auth_required
def create_record():
    """
    Create a new health record for the authenticated user.

    Body (JSON): date (YYYY-MM-DD), steps, heart_rate, sleep_hours,
                 sleep_time (HH:MM), wake_time (HH:MM),
                 meals (list), exercise (dict), weight_kg, calories_burned.
    Returns:
        201 with created record, 400 on validation/duplicate.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Request body must be JSON.'}), 400

    date = data.pop('date', None)
    if not date:
        return jsonify({'success': False, 'error': 'Field "date" (YYYY-MM-DD) is required.'}), 400

    result = health_service.create_health_record(g.user_id, date, data)
    if not result['success']:
        return jsonify({'success': False, 'error': result['error']}), 400

    return jsonify({'success': True, 'data': result['record']}), 201


@health_bp.route('', methods=['GET'])
@auth_required
def list_records():
    """
    List health records for the authenticated user.

    Query params: start_date (YYYY-MM-DD), end_date (YYYY-MM-DD) — both optional.
    Returns:
        200 with list of records.
    """
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    result = health_service.get_records(g.user_id, start_date, end_date)
    return jsonify({'success': True, 'data': result['records']}), 200


@health_bp.route('/<string:date>', methods=['GET'])
@auth_required
def get_single_record(date: str):
    """
    Retrieve a single health record by date.

    Args:
        date: Record date in YYYY-MM-DD format (URL path parameter).
    Returns:
        200 with record or 404 if not found.
    """
    result = health_service.get_record(g.user_id, date)
    if not result['success']:
        return jsonify({'success': False, 'error': result['error']}), 404
    return jsonify({'success': True, 'data': result['record']}), 200


@health_bp.route('/<string:date>', methods=['PUT'])
@auth_required
def update_record(date: str):
    """
    Update an existing health record.

    Args:
        date: Record date in YYYY-MM-DD format (URL path parameter).
    Body (JSON): Any subset of health record fields to update.
    Returns:
        200 with updated record or 404 if not found.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Request body must be JSON.'}), 400

    # Prevent overwriting the primary key fields via the body
    data.pop('user_id', None)
    data.pop('date', None)

    result = health_service.update_record(g.user_id, date, data)
    if not result['success']:
        status = 404 if 'not found' in result.get('error', '').lower() else 400
        return jsonify({'success': False, 'error': result['error']}), status

    return jsonify({'success': True, 'data': result['record']}), 200


@health_bp.route('/<string:date>', methods=['DELETE'])
@auth_required
def delete_record(date: str):
    """
    Delete a health record by date.

    Args:
        date: Record date in YYYY-MM-DD format (URL path parameter).
    Returns:
        200 on success, 404 if not found.
    """
    result = health_service.delete_record(g.user_id, date)
    if not result['success']:
        return jsonify({'success': False, 'error': result['error']}), 404
    return jsonify({'success': True, 'data': {'message': f'Record for {date} deleted.'}}), 200


@health_bp.route('/nutrition-lookup', methods=['POST'])
@auth_required
def nutrition_lookup():
    """
    Look up nutrition data for a food description using CalorieNinjas.

    Body (JSON): { "query": "2 boiled eggs and toast" }
    Returns:
        200 with nutrition summary, 400 on bad input, 503 if API unavailable.
    """
    data = request.get_json(silent=True)
    if not data or not data.get('query'):
        return jsonify({'success': False, 'error': 'Field "query" is required.'}), 400

    nutrition = get_nutrition_data(data['query'])
    if nutrition is None:
        return jsonify({
            'success': False,
            'error': 'Nutrition data unavailable. Ensure CALORIE_NINJAS_API_KEY is configured.',
        }), 503

    summary = summarise_nutrition(nutrition)
    return jsonify({'success': True, 'data': summary}), 200
