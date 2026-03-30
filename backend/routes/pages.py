"""
Page routes.
These Flask routes serve the Jinja2 HTML templates.
Authentication is handled client-side via JS — all pages are served freely
but JavaScript redirects unauthenticated users to /login.
"""
from flask import Blueprint, render_template

pages_bp = Blueprint('pages', __name__)


@pages_bp.route('/login')
def login():
    return render_template('login.html')


@pages_bp.route('/register')
def register():
    return render_template('register.html')


@pages_bp.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')


@pages_bp.route('/health/add')
def add_health():
    return render_template('add_health.html')


@pages_bp.route('/health/edit/<string:date>')
def edit_health(date: str):
    return render_template('add_health.html', edit_date=date)


@pages_bp.route('/analytics')
def analytics():
    return render_template('analytics.html')


@pages_bp.route('/history')
def history():
    return render_template('history.html')


@pages_bp.route('/api-docs')
def api_docs():
    return render_template('api_docs.html')
