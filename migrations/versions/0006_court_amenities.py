"""Court amenities

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-23 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('stadium', schema=None) as batch_op:
        batch_op.add_column(sa.Column('has_led', sa.Boolean(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('has_ac', sa.Boolean(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('has_turf', sa.Boolean(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('has_panoramic', sa.Boolean(), server_default='0', nullable=False))


def downgrade():
    with op.batch_alter_table('stadium', schema=None) as batch_op:
        batch_op.drop_column('has_panoramic')
        batch_op.drop_column('has_turf')
        batch_op.drop_column('has_ac')
        batch_op.drop_column('has_led')
