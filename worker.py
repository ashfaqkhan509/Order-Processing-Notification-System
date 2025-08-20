import time
import random
import json
from order_processing import create_app, db
from order_processing.models import OrderStatus, Order
from order_processing.services.redis_stream import RedisStreamService


app = create_app()


def simulate_order_processing(order: Order):
    """Simulate order processing by updating the order status."""
    redis_service = RedisStreamService()

    if order.status == OrderStatus.PENDING:
        order.status = OrderStatus.PROCESSING
        db.session.commit()
        redis_service.push_status_update(order.id, OrderStatus.PROCESSING.value)

    time.sleep(2)  # simulate delay

    try:
        if random.random() < 0.1:  # 10% failure chance
            order.status = OrderStatus.FAILED   # 👈 now using FAILED
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
    with app.app_context():
        redis_service = RedisStreamService()
        redis_service.ensure_consumer_group()

        print(f"Worker {redis_service.worker_name} started. Waiting for messages...")

        while True:
            try:
                orders = redis_service.redis.xreadgroup(
                    redis_service.consumer_group,
                    redis_service.worker_name,
                    {redis_service.orders_stream: '>'},
                    count=1,
                    block=5000
                )

                if orders:
                    for stream, messages in orders:
                        for message_id, message_data in messages:
                            try:
                                order_json = json.loads(message_data[b'order'].decode())
                                order = db.session.get(Order, order_json["id"])
                                if order:
                                    simulate_order_processing(order)

                                    # ✅ Ack after successful processing
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
    main()
