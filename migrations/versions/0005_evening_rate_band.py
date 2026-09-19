"""Evening rate band

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-18 15:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('evening_rate', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('evening_start_hour', sa.Integer(), server_default='18', nullable=False))
        batch_op.add_column(sa.Column('evening_end_hour', sa.Integer(), server_default='0', nullable=False))


def downgrade():
    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.drop_column('evening_end_hour')
        batch_op.drop_column('evening_start_hour')
        batch_op.drop_column('evening_rate')
