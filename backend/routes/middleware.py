"""
auth_required decorator — shared by all protected route blueprints.
Extracts the JWT Bearer token from the Authorization header, verifies it,
and populates flask.g.user_id for downstream handlers.
"""
import logging
from functools import wraps

from flask import request, jsonify, g

from services.auth_service import verify_token

logger = logging.getLogger(__name__)


def auth_required(f):
    """
    Decorator that enforces JWT authentication on API routes.
    Sets g.user_id to the authenticated user's email on success.
    Returns 401 JSON response on failure.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'success': False, 'error': 'Missing or malformed Authorization header.'}), 401

        token = auth_header[len('Bearer '):]
        user_id = verify_token(token)
        if not user_id:
            return jsonify({'success': False, 'error': 'Invalid or expired token.'}), 401

        g.user_id = user_id
        return f(*args, **kwargs)
    return decorated
