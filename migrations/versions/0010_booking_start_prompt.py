"""Booking start reminder: remember a declined prompt

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-30 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('booking', schema=None) as batch_op:
        batch_op.add_column(sa.Column('start_prompt_declined_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('start_prompt_declined_by', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_booking_start_prompt_declined_by', 'user', ['start_prompt_declined_by'], ['id'])


def downgrade():
    with op.batch_alter_table('booking', schema=None) as batch_op:
        batch_op.drop_constraint('fk_booking_start_prompt_declined_by', type_='foreignkey')
        batch_op.drop_column('start_prompt_declined_by')
        batch_op.drop_column('start_prompt_declined_at')
