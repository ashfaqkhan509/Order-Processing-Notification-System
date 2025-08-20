from flask import Blueprint, jsonify, request
from sqlalchemy.exc import SQLAlchemyError
from order_processing.models import Order, Customer, Product, OrderItem
from order_processing import db
from order_processing.services.redis_stream import RedisStreamService
from flask import Response


bp = Blueprint('api', __name__, url_prefix='/api')


@bp.route('/customers', methods=['POST'])
def create_customer():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No input data provided'}), 400

    try:
        new_customer = Customer(
            username=data['username'],
            email=data['email'],
            address=data['address']
        )
        db.session.add(new_customer)
        db.session.commit()
        return jsonify(new_customer.to_dict()), 201
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@bp.route('/customers', methods=['GET'])
def get_customers():
    try:
        customers = Customer.query.all()
        return jsonify([c.to_dict() for c in customers]), 200
    except SQLAlchemyError as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/customers/<int:customer_id>', methods=['GET'])
def get_customer(customer_id):
    try:
        customer = Customer.query.get_or_404(customer_id)
        return jsonify(customer.to_dict()), 200
    except SQLAlchemyError as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/products', methods=['POST'])
def create_product():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No input data provided'}), 400

    try:
        new_product = Product(
            name=data['name'],
            description=data.get('description', ''),
            price=data['price'],
            stock=data.get('stock', 0)
        )
        db.session.add(new_product)
        db.session.commit()
        return jsonify(new_product.to_dict()), 201
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@bp.route('/products', methods=['GET'])
def get_products():
    try:
        products = Product.query.all()
        return jsonify([p.to_dict() for p in products]), 200
    except SQLAlchemyError as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    try:
        product = Product.query.get_or_404(product_id)
        return jsonify(product.to_dict()), 200
    except SQLAlchemyError as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/orders', methods=['POST'])
def create_order():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No input data provided'}), 400

    try:
        customer = Customer.query.get_or_404(data['customer_id'])
        order_items = []
        total_amount = 0.0

        for item in data['items']:
            product = Product.query.get_or_404(item['product_id'])
            if product.stock < item['quantity']:
                return jsonify({'error': f'Insufficient stock for product {product.name}'}), 400

            order_item = OrderItem(
                product_id=product.id,
                quantity=item['quantity'],
                price=product.price
            )
            order_items.append(order_item)
            total_amount += product.price * item['quantity']
            product.stock -= item['quantity']

        new_order = Order(
            customer=customer,
            total_amount=total_amount,
            order_items=order_items
        )
        db.session.add(new_order)
        db.session.commit()

        # Push order to Redis stream
        redis_service = RedisStreamService()
        redis_service.ensure_consumer_group()
        redis_service.add_order(new_order.to_dict())

        return jsonify(new_order.to_dict()), 201
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@bp.route('/orders', methods=['GET'])
def get_orders():
    try:
        orders = Order.query.all()
        return jsonify([o.to_dict() for o in orders]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/orders/<int:order_id>', methods=['GET'])
def get_order(order_id):
    try:
        order = Order.query.get_or_404(order_id)
        return jsonify(order.to_dict()), 200
    except SQLAlchemyError as e:
        return jsonify({'error': str(e)}), 500


@bp.route("/orders/stream")
def stream_sse():
    """Stream order updates from Redis as SSE."""
    redis_service = RedisStreamService()

    def event_stream():
        last_id = '0'
        while True:
            updates = redis_service.redis.xread(
                {redis_service.order_updates_stream: last_id}, block=0, count=1
            )

            # Stop safely if no new updates (important for tests)
            if not updates:
                break

            for stream, messages in updates:
                for message_id, message_data in messages:
                    last_id = message_id
                    if b'update' in message_data:
                        yield f"data: {message_data[b'update'].decode()}\n\n"

    return Response(event_stream(), mimetype="text/event-stream")
