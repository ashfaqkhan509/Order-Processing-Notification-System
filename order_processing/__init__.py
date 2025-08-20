from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from order_processing.config import Config


# Initialize SQLAlchemy (ORM for database interactions)
db = SQLAlchemy()

# Initialize Flask-Migrate (handles database migrations with Alembic)
migrate = Migrate()


def create_app(config_class=Config):
    """
    Application factory function for creating a Flask app instance.

    Args:
        config_class (object): The configuration class to use for the app.
                              Defaults to `Config` from order_processing.config.

    Returns:
        Flask: A fully configured Flask application instance.

    This function:
        - Creates a Flask app.
        - Loads configuration from the given config class.
        - Initializes extensions (SQLAlchemy, Flask-Migrate).
        - Registers blueprints (e.g., order routes).
    """
    app = Flask(__name__)

    # Load configuration settings into the app
    app.config.from_object(config_class)

    # Initialize extensions with the app
    db.init_app(app)
    migrate.init_app(app, db)

    # Register application blueprints (modular routes)
    from order_processing.routes import order
    app.register_blueprint(order.bp)

    return app
