"""WSGI entry point for production servers (gunicorn)."""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app

application = create_app()

if __name__ == '__main__':
    application.run()
