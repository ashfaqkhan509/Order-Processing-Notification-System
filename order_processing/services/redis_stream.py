import redis
import json
from flask import current_app


class RedisStreamService:
    """
    A service class to interact with Redis Streams for order processing.

    This class handles:
        - Pushing new orders into the main `orders_stream`.
        - Publishing order status updates into `order_updates_stream`.
        - Re-queuing failed orders into a retry stream.
        - Ensuring Redis consumer groups exist for stream processing.

    Attributes:
        url (str): Redis connection URL.
        redis (Redis): Redis client instance.
        orders_stream (str): Name of the stream for incoming orders.
        order_updates_stream (str): Name of the stream for order status updates.
        retry_stream (str): Name of the stream for failed orders.
        consumer_group (str): Consumer group name for processing orders.
        worker_name (str): Worker identifier for consumer group.
    """

    def __init__(self):
        """Initialize Redis connection and stream configurations from Flask app config."""
        self.url = current_app.config.get(
            'REDIS_STREAM_URL',
            'redis://localhost:6379/0'
        )
        self.redis = redis.Redis.from_url(self.url)
        self.orders_stream = current_app.config.get(
            'ORDERS_STREAM',
            'orders_stream'
        )
        self.order_updates_stream = current_app.config.get(
            'ORDER_UPDATES_STREAM',
            'order_updates_stream'
        )
        self.retry_stream = current_app.config.get(
            'ORDER_RETRY_STREAM',
            'order_retry_stream'
        )
        self.consumer_group = current_app.config.get(
            'ORDERS_CONSUMER_GROUP',
            'orders_group'
        )
        self.worker_name = current_app.config.get(
            'WORKER_NAME',
            'worker-1'
        )

    def ensure_consumer_group(self):
        """
        Ensure that the Redis consumer group for orders exists.

        If the consumer group already exists, ignore the error.
        Raises:
            redis.exceptions.ResponseError: If another Redis error occurs.
        """
        try:
            self.redis.xgroup_create(
                self.orders_stream,
                self.consumer_group,
                id='0',
                mkstream=True
            )
        except redis.exceptions.ResponseError as e:
            if 'BUSYGROUP Consumer Group name already exists' not in str(e):
                raise

    def add_order(self, order_data):
        """
        Push a new order into the orders stream.

        Args:
            order_data (dict): Order details (customer, items, etc.).

        Returns:
            str: Redis stream entry ID.
        """
        order_json = json.dumps(order_data)
        return self.redis.xadd(self.orders_stream, {'order': order_json})

    def push_status_update(self, order_id, status, note=None):
        """
        Push an order status update into the order_updates stream.

        Args:
            order_id (int): ID of the order being updated.
            status (str): New status (e.g., "PROCESSING", "COMPLETED").
            note (str, optional): Extra information about the update.

        Returns:
            str: Redis stream entry ID.
        """
        update_data = {
            'order_id': order_id,
            'status': status,
            "note": note,
            "event": "status_update"
        }
        update_json = json.dumps(update_data)
        return self.redis.xadd(self.order_updates_stream, {'update': update_json})

    def requeue_failed_order(self, order_id, reason="processing_failed"):
        """
        Requeue a failed order into the retry stream.

        Args:
            order_id (int): ID of the failed order.
            reason (str, optional): Reason for requeueing (default: "processing_failed").

        Returns:
            str: Redis stream entry ID.
        """
        failed_data = {
            'order_id': order_id,
            'status': 'failed',
            'reason': reason,
            'event': 'retry'
        }
        failed_json = json.dumps(failed_data)
        return self.redis.xadd(self.retry_stream, {'retry_order': failed_json})
