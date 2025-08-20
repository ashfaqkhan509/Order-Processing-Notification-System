from unittest.mock import patch, MagicMock
from order_processing import db
from order_processing.models import Customer, Product


def test_create_customer(client):
    """Test creating a new customer."""
    data = {"username": "Alice", "email": "alice@example.com", "address": "123 Street"}
    response = client.post("/api/customers", json=data)
    assert response.status_code == 201
    res_data = response.get_json()
    assert res_data["username"] == "Alice"
    assert res_data["email"] == "alice@example.com"


def test_get_customers(client):
    """Test retrieving all customers."""
    response = client.get("/api/customers")
    assert response.status_code == 200
    res_data = response.get_json()
    assert isinstance(res_data, list)


def test_create_product(client):
    """Test creating a new product."""
    data = {"name": "Laptop", "description": "Gaming Laptop", "price": 1500, "stock": 10}
    response = client.post("/api/products", json=data)
    assert response.status_code == 201
    res_data = response.get_json()
    assert res_data["name"] == "Laptop"
    assert res_data["price"] == 1500


def test_get_products(client):
    """Test retrieving all products."""
    response = client.get("/api/products")
    assert response.status_code == 200
    res_data = response.get_json()
    assert isinstance(res_data, list)


@patch("order_processing.routes.order.RedisStreamService")
def test_create_order(mock_redis, client, app):
    """Test creating a new order and pushing to Redis."""
    customer = Customer(username="Bob", email="bob@gmail.com", address="456 Avenue")
    product = Product(name="Smartphone", price=800, stock=50)
    db.session.add_all([customer, product])
    db.session.commit()

    order_data = {
        "customer_id": customer.id,
        "items": [{"product_id": product.id, "quantity": 1}]
    }

    mock_instance = MagicMock()
    mock_redis.return_value = mock_instance

    response = client.post("/api/orders", json=order_data)
    assert response.status_code == 201
    res_data = response.get_json()
    assert res_data["total_amount"] == 800
    mock_instance.add_order.assert_called_once()


@patch("order_processing.routes.order.RedisStreamService")
def test_orders_stream_sse(mock_redis, client):
    """Test the SSE endpoint by mocking Redis updates with a finite stream."""
    mock_instance = MagicMock()
    mock_redis.return_value = mock_instance

    # First call returns messages, second call returns empty to stop the generator
    mock_instance.redis.xread.side_effect = [
        [
            (
                b'order_updates_stream',
                [
                    (
                        b'1-0',
                        {
                            b'update': b'{"order_id":1,"status":"PROCESSING","event":"status_update"}'
                        }
                    ),
                    (
                        b'2-0',
                        {
                            b'update': b'{"order_id":1,"status":"COMPLETED","event":"status_update"}'
                        }
                    )
                ]
            )
        ],
        []
    ]

    response = client.get("/api/orders/stream", buffered=True)
    assert response.status_code == 200
    content = b"".join(response.response).decode()
    assert "PROCESSING" in content
    assert "COMPLETED" in content


@patch("order_processing.routes.order.RedisStreamService")
def test_orders_stream_failure(mock_redis, client):
    """Test SSE stream for orders that fail or are cancelled."""
    mock_instance = MagicMock()
    mock_redis.return_value = mock_instance

    mock_instance.redis.xread.side_effect = [
    [
        (
            b'order_updates_stream',
            [
                (
                    b'3-0',
                    {b'update': b'{"order_id":2,"status":"CANCELLED","event":"status_update"}'}
                ),
                (
                    b'4-0',
                    {b'update': b'{"order_id":3,"status":"FAILED","event":"status_update"}'}
                )
            ]
        )
    ],
    []
    ]

    response = client.get("/api/orders/stream", buffered=True)
    content = b"".join(response.response).decode()
    assert "CANCELLED" in content
    assert "FAILED" in content
