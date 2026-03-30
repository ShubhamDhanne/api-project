"""
Authentication service.
Handles user registration, login, and JWT token operations.
Passwords are hashed with bcrypt — plain-text passwords are never stored.
"""
import logging
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from aws.dynamodb import get_user, put_user
from config import Config

logger = logging.getLogger(__name__)


# ── Registration ──────────────────────────────────────────────────────────────

def register_user(email: str, password: str, name: str) -> dict:
    """
    Register a new user.

    Args:
        email: User's email (used as partition key / user_id).
        password: Plain-text password (will be hashed).
        name: User's display name.
    Returns:
        dict with keys: success (bool), error (str on failure).
    """
    email = email.strip().lower()

    # Reject if user already exists
    existing = get_user(email)
    if existing:
        return {'success': False, 'error': 'An account with this email already exists.'}

    # Hash password — bcrypt handles salt generation internally
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    user_item = {
        'email': email,
        'name': name.strip(),
        'password_hash': password_hash,
        'created_at': datetime.utcnow().isoformat(),
    }

    success = put_user(email, user_item)
    if not success:
        return {'success': False, 'error': 'Failed to create account. Please try again.'}

    logger.info('New user registered: %s', email)
    return {'success': True}


# ── Login ─────────────────────────────────────────────────────────────────────

def login_user(email: str, password: str) -> dict:
    """
    Authenticate a user and return a signed JWT token.

    Args:
        email: User's email.
        password: Plain-text password.
    Returns:
        dict with keys: success (bool), token (str on success), name (str on success),
                        error (str on failure).
    """
    email = email.strip().lower()
    user = get_user(email)

    if not user:
        # Use same message as wrong password to avoid user enumeration
        return {'success': False, 'error': 'Invalid email or password.'}

    stored_hash = user.get('password_hash', '')
    if not bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
        return {'success': False, 'error': 'Invalid email or password.'}

    token = _create_token(email)
    logger.info('User logged in: %s', email)
    return {'success': True, 'token': token, 'name': user.get('name', '')}


# ── Token helpers ─────────────────────────────────────────────────────────────

def _create_token(user_id: str) -> str:
    """
    Create a signed JWT token for the given user_id.

    Args:
        user_id: The user's email address.
    Returns:
        Encoded JWT string.
    """
    payload = {
        'sub': user_id,
        'iat': datetime.now(tz=timezone.utc),
        'exp': datetime.now(tz=timezone.utc) + timedelta(hours=Config.JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm='HS256')


def verify_token(token: str) -> str | None:
    """
    Verify a JWT token and return the user_id (subject) if valid.

    Args:
        token: Encoded JWT string from the Authorization header.
    Returns:
        user_id string or None if token is invalid/expired.
    """
    try:
        payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=['HS256'])
        return payload.get('sub')
    except jwt.ExpiredSignatureError:
        logger.warning('JWT token expired.')
        return None
    except jwt.InvalidTokenError as exc:
        logger.warning('JWT token invalid: %s', exc)
        return None
