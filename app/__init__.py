from pathlib import Path
from flask import Flask

from .routes.main import main_bp


def create_app():
    base_dir = Path(__file__).resolve().parents[1]
    template_dir = base_dir / "templates"
    static_dir = base_dir / "static"

    app = Flask(
        __name__,
        template_folder=str(template_dir),
        static_folder=str(static_dir),
    )
    app.register_blueprint(main_bp)
    return app
