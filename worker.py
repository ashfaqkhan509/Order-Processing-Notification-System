"""
Worker service for processing incoming orders using Redis Streams.

This script continuously listens to the Redis `orders_stream` via a consumer group,
simulates order processing, updates the database with new statuses, and pushes 
status updates (e.g., PROCESSING, COMPLETED, FAILED) back to the Redis stream.

Key Features:
- Reads new orders from Redis consumer group (`xreadgroup`).
- Simulates order processing with random failures.
- Updates order status in the database.
- Publishes order status updates to Redis for real-time notifications.
- Acknowledges successfully processed messages (`xack`) to prevent reprocessing.
"""

import time
import random
import json
from order_processing import create_app, db
from order_processing.models import OrderStatus, Order
from order_processing.services.redis_stream import RedisStreamService


# Create Flask app for DB and Redis integration
app = create_app()


def simulate_order_processing(order: Order):
    """
    Simulate the processing of a single order.

    Steps:
        1. If order is `PENDING`, update it to `PROCESSING`.
        2. Sleep for 2 seconds to mimic real-world delay.
        3. Randomly determine success/failure (10% chance to fail).
        4. On success, update order status to `COMPLETED`.
        5. On failure, update order status to `FAILED` with a note.
        6. Push the status update to Redis for notification.

    Args:
        order (Order): The order object from the database to process.

    Raises:
        Exception: If there is an error committing to the database.
    """
    redis_service = RedisStreamService()

    if order.status == OrderStatus.PENDING:
        order.status = OrderStatus.PROCESSING
        db.session.commit()
        redis_service.push_status_update(order.id, OrderStatus.PROCESSING.value)

    time.sleep(2)  # simulate processing delay

    try:
        if random.random() < 0.1:  # 10% chance to fail
            order.status = OrderStatus.FAILED
            note = "Payment failed"
            db.session.commit()
            redis_service.push_status_update(order.id, OrderStatus.FAILED.value, note=note)
        else:
            order.status = OrderStatus.COMPLETED
            note = "Order processed successfully"
            db.session.commit()
            redis_service.push_status_update(order.id, OrderStatus.COMPLETED.value, note=note)

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error updating order {order.id}: {e}")


def main():
    """
    Main worker loop that continuously listens for new orders from Redis.

    Behavior:
        - Joins a consumer group for the orders stream.
        - Reads new orders using `xreadgroup`.
        - For each order message:
            - Parses the JSON payload.
            - Fetches the corresponding order from the database.
            - Calls `simulate_order_processing` to update its status.
            - Acknowledges the message (`xack`) if processed successfully.
        - Retries on errors with logging.
        - Sleeps briefly to avoid CPU overuse.

    This function runs indefinitely until the process is stopped.
    """
    with app.app_context():
        redis_service = RedisStreamService()
        redis_service.ensure_consumer_group()

        print(f"Worker {redis_service.worker_name} started. Waiting for messages...")

        while True:
            try:
                orders = redis_service.redis.xreadgroup(
                    redis_service.consumer_group,
                    redis_service.worker_name,
                    {redis_service.orders_stream: '>'},  # read new messages
                    count=1,
                    block=5000  # wait up to 5 seconds for new messages
                )

                if orders:
                    for stream, messages in orders:
                        for message_id, message_data in messages:
                            try:
                                order_json = json.loads(message_data[b'order'].decode())
                                order = db.session.get(Order, order_json["id"])
                                if order:
                                    simulate_order_processing(order)

                                    # Acknowledge after successful processing
                                    redis_service.redis.xack(
                                        redis_service.orders_stream,
                                        redis_service.consumer_group,
                                        message_id
                                    )
                            except Exception as e:
                                db.session.rollback()
                                app.logger.error(f"Error processing message {message_id}: {e}")

            except Exception as e:
                app.logger.error(f"Worker loop error: {e}")

            time.sleep(1)


if __name__ == '__main__':
    """
    Entry point for running the worker service.

    Starts the infinite main loop that listens to Redis for incoming orders.
    """
    main()
