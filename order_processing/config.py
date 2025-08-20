import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """
    Base configuration class for the Flask application.

    Loads settings from environment variables (via .env file if available).
    Provides default values where necessary.

    Attributes:
        SECRET_KEY (str): Secret key used for Flask session security.
        SQLALCHEMY_DATABASE_URI (str): Database connection URI for SQLAlchemy.
        SQLALCHEMY_TRACK_MODIFICATIONS (bool): Disables Flask-SQLAlchemy
            modification tracking (saves resources).
        JWT_SECRET_KEY (str): Secret key for encoding/decoding JWT tokens.
        JWT_ACCESS_TOKEN_EXPIRES (timedelta): Expiration time for access tokens.
        JWT_REFRESH_TOKEN_EXPIRES (timedelta): Expiration time for refresh tokens.
        REDIS_URL (str): Connection URL for Redis instance.
        ORDERS_STREAM (str): Redis stream name for incoming orders.
        ORDER_UPDATES_STREAM (str): Redis stream name for order updates.
        ORDERS_CONSUMER_GROUP (str): Redis consumer group for order workers.
        WORKER_NAME (str): Name identifier for the worker processing the stream.
    """

    SECRET_KEY = os.getenv('SECRET_KEY', 'default_secret_key')
    SQLALCHEMY_DATABASE_URI = os.getenv('SQLALCHEMY_DATABASE_URI')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Redis Streams configuration
    ORDERS_STREAM = os.getenv("ORDERS_STREAM", "orders_stream")
    ORDER_UPDATES_STREAM = os.getenv("ORDER_UPDATES_STREAM", "order_updates_stream")
    ORDERS_CONSUMER_GROUP = os.getenv("ORDERS_CONSUMER_GROUP", "orders_group")
    WORKER_NAME = os.getenv("WORKER_NAME", "worker-1")


class TestConfig(Config):
    """
    Testing configuration class (inherits from Config).

    Overrides database and security settings for testing environment.

    Attributes:
        SQLALCHEMY_DATABASE_URI (str): Uses in-memory SQLite DB for tests
            (or custom URI if provided).
        TESTING (bool): Enables Flask testing mode.
        SECRET_KEY (str): Test secret key.
        JWT_SECRET_KEY (str): Test JWT secret key.
        WTF_CSRF_ENABLED (bool): Disables CSRF protection for testing forms.
    """

    SQLALCHEMY_DATABASE_URI = os.getenv(
        'SQLALCHEMY_TEST_DATABASE_URI', 'sqlite:///:memory:'
    )
    TESTING = True
    SECRET_KEY = os.getenv('SECRET_KEY')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    WTF_CSRF_ENABLED = False
