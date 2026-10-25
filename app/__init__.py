"""Application factory for the AI Career Assistant."""

from __future__ import annotations

import os
from typing import Any

from flask import Flask, jsonify, render_template
from werkzeug.exceptions import RequestEntityTooLarge

from app.blueprints.auth import auth_bp
from app.blueprints.main import main_bp
from app.blueprints.resumes import resumes_bp
from app.blueprints.internships import internships_bp
from app.commands import register_commands
from app.config import CONFIGS, Config
from app.extensions import csrf, db, login_manager, migrate
from app.models import User


def create_app(config_object: type[Config] | str | None = None) -> Flask:
    """Create and configure a Flask application."""
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)

    if config_object is None:
        config_object = os.environ.get("APP_ENV", "development")
    if isinstance(config_object, str):
        try:
            config_object = CONFIGS[config_object.lower()]
        except KeyError as error:
            raise ValueError(f"Unknown application environment: {config_object}") from error

    if config_object is CONFIGS["production"]:
        config_object.validate()
    app.config.from_object(config_object)
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(resumes_bp)
    app.register_blueprint(internships_bp)
    register_commands(app)

    @login_manager.user_loader
    def load_user(user_id: str) -> User | None:
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    @app.after_request
    def add_security_headers(response: Any) -> Any:
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response

    @app.get("/healthz")
    def healthz():
        return jsonify(status="ok"), 200

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_error(_error):
        db.session.rollback()
        return render_template("errors/500.html"), 500

    @app.errorhandler(RequestEntityTooLarge)
    def upload_too_large(_error):
        return render_template("errors/413.html"), 413

    with app.app_context():
        db.create_all()

    return app
