"""
Main Flask application factory.
Initialises Flask, registers blueprints, sets up logging, and ensures
AWS resources (DynamoDB tables, SQS queue) exist at startup.
"""
import logging
import os
import sys
from decimal import Decimal

from flask import Flask, redirect, url_for
from flask_cors import CORS

# Allow imports from this directory regardless of cwd
sys.path.insert(0, os.path.dirname(__file__))

from config import Config

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)
logger = logging.getLogger(__name__)


def decimal_default(obj):
    """JSON serialiser that converts Decimal to int/float."""
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    raise TypeError(f'Object of type {type(obj)} is not JSON serialisable')


def create_app():
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), '..', 'frontend', 'templates'),
        static_folder=os.path.join(os.path.dirname(__file__), '..', 'frontend', 'static'),
    )

    app.secret_key = Config.FLASK_SECRET_KEY
    app.config['DEBUG'] = Config.DEBUG

    # Enable CORS for API endpoints
    CORS(app, resources={r'/api/*': {'origins': '*'}})

    # ── Custom JSON encoder to handle DynamoDB Decimal types ────────────────
    from flask.json.provider import DefaultJSONProvider

    class CustomJSONProvider(DefaultJSONProvider):
        def default(self, obj):
            if isinstance(obj, Decimal):
                return int(obj) if obj % 1 == 0 else float(obj)
            return super().default(obj)

    app.json_provider_class = CustomJSONProvider
    app.json = CustomJSONProvider(app)

    # ── Register Blueprints ──────────────────────────────────────────────────
    from routes.auth import auth_bp
    from routes.health import health_bp
    from routes.analytics import analytics_bp
    from routes.pages import pages_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(health_bp, url_prefix='/api/health')
    app.register_blueprint(analytics_bp, url_prefix='/api/analytics')
    app.register_blueprint(pages_bp)

    # ── Root redirect ────────────────────────────────────────────────────────
    @app.route('/')
    def index():
        return redirect(url_for('pages.dashboard'))

    # ── Ensure AWS resources exist ───────────────────────────────────────────
    try:
        from aws.dynamodb import create_tables
        create_tables()
        logger.info('DynamoDB tables verified/created.')
    except Exception as exc:
        logger.error('Failed to initialise DynamoDB tables: %s', exc)

    try:
        from aws.sqs import ensure_queue
        ensure_queue()
        logger.info('SQS queue verified/created.')
    except Exception as exc:
        logger.error('Failed to initialise SQS queue: %s', exc)

    return app


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    application = create_app()
    application.run(host='0.0.0.0', port=Config.PORT, debug=Config.DEBUG)
