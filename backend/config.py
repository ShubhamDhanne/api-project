"""
Application configuration module.
Loads all settings from environment variables using python-dotenv.
Never hardcode credentials here.
"""
import os
import logging
from dotenv import load_dotenv

# Load .env file from project root
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

logger = logging.getLogger(__name__)


class Config:
    """Central configuration class for the Health Analytics application."""

    # ── AWS ──────────────────────────────────────────────────────────────────
    AWS_REGION = os.getenv('AWS_REGION', 'eu-north-1')
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')

    # ── DynamoDB ──────────────────────────────────────────────────────────────
    DYNAMODB_USERS_TABLE = 'HealthUsers'
    DYNAMODB_RECORDS_TABLE = 'HealthRecords'

    # ── SQS ───────────────────────────────────────────────────────────────────
    SQS_QUEUE_NAME = os.getenv('SQS_QUEUE_NAME', 'health-analytics-queue')

    # ── JWT ───────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'health-jwt-secret-change-in-prod-2024')
    JWT_EXPIRY_HOURS = int(os.getenv('JWT_EXPIRY_HOURS', '24'))

    # ── External APIs ─────────────────────────────────────────────────────────
    CALORIE_NINJAS_API_KEY = os.getenv('CALORIE_NINJAS_API_KEY', '')
    CALORIE_NINJAS_BASE_URL = 'https://api.calorieninjas.com/v1'

    STABILITY_API_BASE = 'https://2u736o5k8k.execute-api.us-east-1.amazonaws.com/prod'

    # ── Flask ─────────────────────────────────────────────────────────────────
    FLASK_SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'flask-secret-change-in-prod')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    PORT = int(os.getenv('PORT', '5000'))
