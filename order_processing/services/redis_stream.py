import redis
import json
from flask import current_app


class RedisStreamService:
    def __init__(self):
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
        """Push a new order to the main orders stream"""
        order_json = json.dumps(order_data)
        return self.redis.xadd(self.orders_stream, {'order': order_json})

    def push_status_update(self, order_id, status, note=None):
        """Push an order status update to the order_updates stream"""
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
        Requeue a failed order into retry stream so it can be processed later.
        Include reason for debugging/monitoring.
        """
        failed_data = {
            'order_id': order_id,
            'status': 'failed',
            'reason': reason,
            'event': 'retry'
        }
        failed_json = json.dumps(failed_data)
        return self.redis.xadd(self.retry_stream, {'retry_order': failed_json})
