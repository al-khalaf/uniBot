from pathlib import Path

from flask import send_from_directory
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate

from api import register_blueprints
from lms_models import create_app as models_create_app, db
from services import init_app as init_services

FRONTEND_DIR = Path(__file__).parent / "frontend"

def create_app():
    app = models_create_app()
    app.config.from_object("config.Dev")

    Migrate(app, db)
    JWTManager(app)

    init_services(app)
    register_blueprints(app)
    _register_frontend(app)
    return app

app = create_app()

if __name__ == "__main__":
    app.run()


def _register_frontend(app):
    """Serve the lightweight front-end bundle if present."""

    if not FRONTEND_DIR.exists():
        return

    @app.route("/")
    def frontend_index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.route("/frontend/<path:path>")
    def frontend_assets(path):
        return send_from_directory(FRONTEND_DIR, path)
