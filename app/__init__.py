from pathlib import Path

from flask import Flask, session

from .auth import is_admin_authenticated
from .config import Config
from .db import init_db
from .extensions import csrf, limiter
from .routes.admin import admin_bp
from .routes.api import api_bp
from .routes.main import main_bp
from .services.cloudinary_service import configure_cloudinary


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
    configure_cloudinary(app)

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)

    @app.context_processor
    def inject_admin_context():
        return {
            "admin_authenticated": is_admin_authenticated(),
            "admin_username": session.get("admin_username", ""),
        }

    return app
