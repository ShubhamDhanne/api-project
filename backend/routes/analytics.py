"""
Analytics routes.
All endpoints require a valid JWT Bearer token.

GET /api/analytics/daily?date=YYYY-MM-DD
GET /api/analytics/weekly?start_date=YYYY-MM-DD
GET /api/analytics/monthly?year=YYYY&month=MM
GET /api/analytics/stability?days=7
"""
import logging
from datetime import datetime

from flask import Blueprint, request, jsonify, g

from routes.middleware import auth_required
from services import analytics_service, stability_service, bmi_service

logger = logging.getLogger(__name__)

analytics_bp = Blueprint('analytics', __name__)


@analytics_bp.route('/daily', methods=['GET'])
@auth_required
def daily():
    """
    Return analytics for a specific day.

    Query params:
        date — YYYY-MM-DD (defaults to today UTC).
    Returns:
        200 with analytics dict.
    """
    date = request.args.get('date', datetime.utcnow().strftime('%Y-%m-%d'))
    result = analytics_service.get_daily_analytics(g.user_id, date)
    if not result['success']:
        return jsonify({'success': False, 'error': result['error']}), 404
    return jsonify({'success': True, 'data': result['analytics']}), 200


@analytics_bp.route('/weekly', methods=['GET'])
@auth_required
def weekly():
    """
    Return a weekly analytics summary.

    Query params:
        start_date — first day of the week, YYYY-MM-DD (defaults to 7 days ago).
    Returns:
        200 with weekly summary dict.
    """
    default_start = (datetime.utcnow() - __import__('datetime').timedelta(days=6)).strftime('%Y-%m-%d')
    start_date = request.args.get('start_date', default_start)

    result = analytics_service.get_weekly_analytics(g.user_id, start_date)
    if not result['success']:
        return jsonify({'success': False, 'error': result['error']}), 404
    return jsonify({'success': True, 'data': result['analytics']}), 200


@analytics_bp.route('/monthly', methods=['GET'])
@auth_required
def monthly():
    """
    Return a monthly analytics summary.

    Query params:
        year  — four-digit year  (defaults to current year).
        month — month number 1-12 (defaults to current month).
    Returns:
        200 with monthly summary dict.
    """
    now = datetime.utcnow()
    try:
        year = int(request.args.get('year', now.year))
        month = int(request.args.get('month', now.month))
    except ValueError:
        return jsonify({'success': False, 'error': 'year and month must be integers.'}), 400

    result = analytics_service.get_monthly_analytics(g.user_id, year, month)
    if not result['success']:
        return jsonify({'success': False, 'error': result['error']}), 404
    return jsonify({'success': True, 'data': result['analytics']}), 200


@analytics_bp.route('/stability', methods=['GET'])
@auth_required
def stability():
    """
    Return the Routine Stability Index from the classmate's API.

    Query params:
        days — number of recent days to analyse (default 7, max 30).
    Returns:
        200 with stability score and recommendations.
    """
    try:
        days = min(int(request.args.get('days', 7)), 30)
    except ValueError:
        days = 7

    result = stability_service.get_stability_score(g.user_id, days)
    if not result.get('success'):
        return jsonify({'success': False, 'error': result.get('error', 'Unknown error.')}), 400
    return jsonify({'success': True, 'data': result}), 200


@analytics_bp.route('/bmi', methods=['POST'])
@auth_required
def bmi():
    """
    Calculate BMI using the API Ninjas BMI public API.

    Body (JSON): { "weight_kg": 72.5, "height_cm": 175 }
    Returns:
        200 with bmi value, category, and healthy_bmi_range.
        400 on bad input, 503 if API key is missing.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'JSON body required.'}), 400

    try:
        weight_kg = float(data['weight_kg'])
        height_cm = float(data['height_cm'])
    except (KeyError, ValueError, TypeError):
        return jsonify({'success': False, 'error': 'weight_kg and height_cm are required numbers.'}), 400

    if not (20 <= weight_kg <= 500):
        return jsonify({'success': False, 'error': 'weight_kg must be between 20 and 500.'}), 400
    if not (50 <= height_cm <= 300):
        return jsonify({'success': False, 'error': 'height_cm must be between 50 and 300.'}), 400

    result = bmi_service.get_bmi(weight_kg, height_cm)
    if result is None:
        return jsonify({'success': False, 'error': 'BMI service unavailable. Ensure CALORIE_NINJAS_API_KEY is configured.'}), 503

    return jsonify({'success': True, 'data': result}), 200
