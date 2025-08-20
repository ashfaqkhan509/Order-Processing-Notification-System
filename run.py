from order_processing import db, create_app
from order_processing.models import Customer, Order, Product, OrderItem
import os


app = create_app()


@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'Customer': Customer,
        'Order': Order,
        'Product': Product,
        'OrderItem': OrderItem
    }


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
