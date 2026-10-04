"""Weekly regular bookings

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-04 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('regular_booking',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_name', sa.String(length=100), nullable=False),
        sa.Column('customer_phone', sa.String(length=20), nullable=False),
        sa.Column('stadium_id', sa.Integer(), nullable=False),
        sa.Column('weekday', sa.Integer(), nullable=False),
        sa.Column('hour', sa.Integer(), nullable=False),
        sa.Column('duration_hours', sa.Integer(), nullable=False),
        sa.Column('starts_on', sa.Date(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('conflict_on', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('ended_by', sa.Integer(), nullable=True),
        sa.Column('end_reason', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['stadium_id'], ['stadium.id'], name='fk_regular_booking_stadium_id'),
        sa.ForeignKeyConstraint(['created_by'], ['user.id'], name='fk_regular_booking_created_by'),
        sa.ForeignKeyConstraint(['ended_by'], ['user.id'], name='fk_regular_booking_ended_by'),
        sa.PrimaryKeyConstraint('id'))
    with op.batch_alter_table('booking', schema=None) as batch_op:
        batch_op.add_column(sa.Column('regular_id', sa.Integer(), nullable=True))
        batch_op.create_index('ix_booking_regular_id', ['regular_id'], unique=False)
        batch_op.create_foreign_key('fk_booking_regular_id', 'regular_booking', ['regular_id'], ['id'])
        batch_op.create_unique_constraint('uq_booking_regular_day', ['regular_id', 'business_day'])


def downgrade():
    with op.batch_alter_table('booking', schema=None) as batch_op:
        batch_op.drop_constraint('uq_booking_regular_day', type_='unique')
        batch_op.drop_constraint('fk_booking_regular_id', type_='foreignkey')
        batch_op.drop_index('ix_booking_regular_id')
        batch_op.drop_column('regular_id')
    op.drop_table('regular_booking')
