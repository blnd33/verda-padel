"""Person tabs: line discounts and free units

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-25 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('pos_order_item', schema=None) as batch_op:
        batch_op.add_column(sa.Column('free_quantity', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('discount_kind', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('discount_value', sa.BigInteger(), server_default='0', nullable=False))


def downgrade():
    with op.batch_alter_table('pos_order_item', schema=None) as batch_op:
        batch_op.drop_column('discount_value')
        batch_op.drop_column('discount_kind')
        batch_op.drop_column('free_quantity')
