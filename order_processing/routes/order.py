from flask import Blueprint, jsonify, request, Response
from sqlalchemy.exc import SQLAlchemyError
from order_processing.models import Order, Customer, Product, OrderItem
from order_processing import db
from order_processing.services.redis_stream import RedisStreamService


bp = Blueprint('api', __name__, url_prefix='/api')


@bp.route('/customers', methods=['POST'])
def create_customer():
    """Create a new customer.

    Expects:
        JSON body with 'username', 'email', and 'address'.

    Returns:
        201 Created with the new customer JSON.
        400 if request body is missing.
        500 if a database error occurs.
    """
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
    """Retrieve all customers.

    Returns:
        200 with a list of customers as JSON.
        500 if a database error occurs.
    """
    try:
        customers = Customer.query.all()
        return jsonify([c.to_dict() for c in customers]), 200
    except SQLAlchemyError as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/customers/<int:customer_id>', methods=['GET'])
def get_customer(customer_id):
    """Retrieve a specific customer by ID.

    Args:
        customer_id (int): The ID of the customer.

    Returns:
        200 with the customer JSON if found.
        404 if the customer does not exist.
        500 if a database error occurs.
    """
    try:
        customer = Customer.query.get_or_404(customer_id)
        return jsonify(customer.to_dict()), 200
    except SQLAlchemyError as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/products', methods=['POST'])
def create_product():
    """Create a new product.

    Expects:
        JSON body with 'name', 'price', optional 'description' and 'stock'.

    Returns:
        201 Created with the new product JSON.
        400 if request body is missing.
        500 if a database error occurs.
    """
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
    """Retrieve all products.

    Returns:
        200 with a list of products as JSON.
        500 if a database error occurs.
    """
    try:
        products = Product.query.all()
        return jsonify([p.to_dict() for p in products]), 200
    except SQLAlchemyError as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    """Retrieve a specific product by ID.

    Args:
        product_id (int): The ID of the product.

    Returns:
        200 with the product JSON if found.
        404 if the product does not exist.
        500 if a database error occurs.
    """
    try:
        product = Product.query.get_or_404(product_id)
        return jsonify(product.to_dict()), 200
    except SQLAlchemyError as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/orders', methods=['POST'])
def create_order():
    """Create a new order.

    Expects:
        JSON body with:
            - 'customer_id' (int)
            - 'items' (list of {product_id, quantity})

    Process:
        - Validates stock for each product.
        - Deducts stock.
        - Creates Order and OrderItems.
        - Pushes the order to Redis for async processing.

    Returns:
        201 Created with order JSON.
        400 if stock is insufficient or body is missing.
        404 if customer or product not found.
        500 if a database error occurs.
    """
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
    """Retrieve all orders.

    Returns:
        200 with a list of orders as JSON.
        500 if a database error occurs.
    """
    try:
        orders = Order.query.all()
        return jsonify([o.to_dict() for o in orders]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/orders/<int:order_id>', methods=['GET'])
def get_order(order_id):
    """Retrieve a specific order by ID.

    Args:
        order_id (int): The ID of the order.

    Returns:
        200 with the order JSON if found.
        404 if the order does not exist.
        500 if a database error occurs.
    """
    try:
        order = Order.query.get_or_404(order_id)
        return jsonify(order.to_dict()), 200
    except SQLAlchemyError as e:
        return jsonify({'error': str(e)}), 500


@bp.route("/orders/stream")
def stream_sse():
    """Stream live order updates via Server-Sent Events (SSE).

    Process:
        - Reads messages from Redis stream (`order_updates_stream`).
        - Yields updates in SSE format: "data: <json>\n\n".
        - Stops gracefully if no updates (important for tests).

    Returns:
        A streaming HTTP response with MIME type "text/event-stream".
    """
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
