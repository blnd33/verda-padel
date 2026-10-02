"""Staff email is optional; staff sign in with a username

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-30 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('email', existing_type=sa.String(length=120), nullable=True)


def downgrade():
    # Staff created without an email get a placeholder so the column can be required again.
    op.execute("UPDATE \"user\" SET email = username || '@staff.invalid' WHERE email IS NULL")
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('email', existing_type=sa.String(length=120), nullable=False)
