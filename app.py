from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from lms_models import db, create_app as models_create_app
from api import register_blueprints
from api.auth import bp as auth_bp

def create_app():
    app = models_create_app()
    app.config.from_object("config.Dev")

    Migrate(app, db)
    JWTManager(app)

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    register_blueprints(app)
    return app

app = create_app()

if __name__ == "__main__":
    app.run()
