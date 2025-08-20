"""rename users table to customers

Revision ID: f4e7b92e8bc5
Revises: 14ad8746e5bb
Create Date: 2025-08-19 15:50:53.846508

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'f4e7b92e8bc5'
down_revision = '14ad8746e5bb'
branch_labels = None
depends_on = None


def upgrade():
    # Rename users → customers
    op.rename_table('users', 'customers')

    # Drop and recreate the foreign key to point to customers
    op.drop_constraint('orders_customer_id_fkey', 'orders', type_='foreignkey')
    op.create_foreign_key(
        'orders_customer_id_fkey',
        'orders',
        'customers',
        ['customer_id'],
        ['id']
    )


def downgrade():
    # Rollback: rename customers → users
    op.rename_table('customers', 'users')

    # Drop and recreate the foreign key to point back to users
    op.drop_constraint('orders_customer_id_fkey', 'orders', type_='foreignkey')
    op.create_foreign_key(
        'orders_customer_id_fkey',
        'orders',
        'users',
        ['customer_id'],
        ['id']
    )
