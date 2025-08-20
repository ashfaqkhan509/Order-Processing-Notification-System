import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'default_secret_key')
    SQLALCHEMY_DATABASE_URI = os.getenv('SQLALCHEMY_DATABASE_URI')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Redis Streams
    ORDERS_STREAM = os.getenv("ORDERS_STREAM", "orders_stream")
    ORDER_UPDATES_STREAM = os.getenv("ORDER_UPDATES_STREAM", "order_updates_stream")
    ORDERS_CONSUMER_GROUP = os.getenv("ORDERS_CONSUMER_GROUP", "orders_group")
    WORKER_NAME = os.getenv("WORKER_NAME", "worker-1")


class TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.getenv('SQLALCHEMY_TEST_DATABASE_URI', 'sqlite:///:memory:')
    TESTING = True
    SECRET_KEY = os.getenv('SECRET_KEY')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    WTF_CSRF_ENABLED = False
