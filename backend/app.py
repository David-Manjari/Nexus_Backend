"""Flask application factory for the backend API."""

import os

from flask import Flask, jsonify

from .routes.audit import audit_bp
from .routes.sessions import sessions_bp
from .routes.users import users_bp
from .routes.assets import assets_bp, assignments_bp
from .db import connect_database, register_db_error_handlers


def create_app(*, secret_key=None):
    """Create the API app; configure SECRET_KEY in the runtime environment."""
    secret_key = secret_key or os.environ.get("SECRET_KEY")
    if not secret_key:
        raise RuntimeError("SECRET_KEY must be set before starting the application.")

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=secret_key,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    app.register_blueprint(sessions_bp, url_prefix="/session")
    app.register_blueprint(audit_bp, url_prefix="/audit")
    app.register_blueprint(users_bp, url_prefix="/users")
    
    app.register_blueprint(assets_bp, url_prefix="/assets")
    app.register_blueprint(assignments_bp, url_prefix="/assignments")
    register_db_error_handlers(app)

    @app.get("/health")
    def health():
        with connect_database() as connection:
            connection.execute("SELECT 1")
        return jsonify(status="ok")
    
    return app