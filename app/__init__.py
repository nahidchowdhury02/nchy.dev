from pathlib import Path
from datetime import datetime

from flask import Flask, session

from .auth import is_admin_authenticated
from .config import Config
from .db import init_db
from .extensions import csrf, limiter
from .routes.admin import admin_bp
from .routes.api import api_bp
from .routes.main import main_bp
from .services.auth_service import AuthService
from .services.media_storage_service import configure_media_storage


def create_app(config_class=Config):
    base_dir = Path(__file__).resolve().parents[1]
    template_dir = base_dir / "templates"
    static_dir = base_dir / "static"

    app = Flask(
        __name__,
        template_folder=str(template_dir),
        static_folder=str(static_dir),
    )
    app.config.from_object(config_class)

    csrf.init_app(app)
    limiter.init_app(app)
    init_db(app)
    configure_media_storage(app)
    bootstrap_admin_from_env(app)

    @app.template_filter("pretty_date")
    def pretty_date(value):
        return _pretty_date(value)

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)

    @app.context_processor
    def inject_admin_context():
        return {
            "admin_authenticated": is_admin_authenticated(),
            "admin_username": session.get("admin_username", ""),
            "special_greeting_name": app.config.get("SPECIAL_GREETING_NAME", ""),
        }

    return app


def _ordinal_day(day: int) -> str:
    if 11 <= day % 100 <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


def _pretty_date(value) -> str:
    if not value:
        return ""

    parsed = value
    if isinstance(value, str):
        candidate = value.strip()
        if candidate.endswith("Z"):
            candidate = candidate[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            return value

    if not hasattr(parsed, "strftime"):
        return str(value)

    month = parsed.strftime("%B")
    return f"{month} {_ordinal_day(parsed.day)}, {parsed.year}"


def bootstrap_admin_from_env(app):
    db = app.extensions.get("mongo_db")
    if db is None:
        return

    username = (app.config.get("ADMIN_USERNAME") or "").strip()
    password = app.config.get("ADMIN_PASSWORD") or ""
    if not username or not password:
        return

    try:
        AuthService(db).bootstrap_admin(username=username, password=password)
        app.logger.info("Admin credentials bootstrapped from environment for '%s'", username)
    except Exception as exc:
        app.logger.warning("Admin bootstrap from environment failed: %s", exc)
