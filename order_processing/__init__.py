from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from order_processing.config import Config


db = SQLAlchemy()
migrate = Migrate()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)

    from order_processing.routes import order
    app.register_blueprint(order.bp)

    return app
