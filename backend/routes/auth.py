"""
Authentication routes.
POST /api/auth/register  — create a new user account
POST /api/auth/login     — authenticate and receive a JWT
"""
import logging

from flask import Blueprint, request, jsonify

from services.auth_service import register_user, login_user

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Register a new user.

    Body (JSON):
        email    — user's email address
        password — plain-text password (min 8 chars)
        name     — display name

    Returns:
        201 on success, 400 on validation/duplicate error.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Request body must be JSON.'}), 400

    email = data.get('email', '').strip()
    password = data.get('password', '')
    name = data.get('name', '').strip()

    # ── Input validation ──────────────────────────────────────────────────────
    if not email or '@' not in email:
        return jsonify({'success': False, 'error': 'A valid email address is required.'}), 400
    if not password or len(password) < 8:
        return jsonify({'success': False, 'error': 'Password must be at least 8 characters.'}), 400
    if not name:
        return jsonify({'success': False, 'error': 'Name is required.'}), 400

    result = register_user(email, password, name)
    if not result['success']:
        return jsonify(result), 400

    return jsonify({'success': True, 'data': {'message': 'Account created successfully.'}}), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Authenticate a user and return a JWT token.

    Body (JSON):
        email    — user's email
        password — plain-text password

    Returns:
        200 with token on success, 401 on invalid credentials.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Request body must be JSON.'}), 400

    email = data.get('email', '').strip()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'success': False, 'error': 'Email and password are required.'}), 400

    result = login_user(email, password)
    if not result['success']:
        return jsonify({'success': False, 'error': result['error']}), 401

    return jsonify({
        'success': True,
        'data': {
            'token': result['token'],
            'name': result['name'],
            'email': email,
        },
    }), 200
