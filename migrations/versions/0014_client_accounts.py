"""Client accounts: regular customers whose bills go on their name

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-05 15:00:00.000000

"""
import json
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('client',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['user.id'], name='fk_client_created_by'),
        sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_client_name', 'client', ['name'])
    with op.batch_alter_table('manual_debts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('client_id', sa.Integer(), nullable=True))
        batch_op.create_index('ix_manual_debts_client_id', ['client_id'])
        batch_op.create_foreign_key('fk_manual_debts_client', 'client', ['client_id'], ['id'])
    with op.batch_alter_table('pos_session', schema=None) as batch_op:
        batch_op.add_column(sa.Column('client_id', sa.Integer(), nullable=True))
        batch_op.create_index('ix_pos_session_client_id', ['client_id'])
        batch_op.create_foreign_key('fk_pos_session_client', 'client', ['client_id'], ['id'])
    # Staff who already run the till can work with client accounts too.
    bind = op.get_bind()
    for user_id, permissions in bind.execute(sa.text('SELECT id, permissions FROM "user"')).fetchall():
        current = json.loads(permissions) if isinstance(permissions, str) else (permissions or [])
        if 'pos' in current and 'clients' not in current:
            bind.execute(sa.text('UPDATE "user" SET permissions = :p WHERE id = :id'),
                         dict(p=json.dumps(current + ['clients']), id=user_id))


def downgrade():
    with op.batch_alter_table('pos_session', schema=None) as batch_op:
        batch_op.drop_constraint('fk_pos_session_client', type_='foreignkey')
        batch_op.drop_index('ix_pos_session_client_id')
        batch_op.drop_column('client_id')
    with op.batch_alter_table('manual_debts', schema=None) as batch_op:
        batch_op.drop_constraint('fk_manual_debts_client', type_='foreignkey')
        batch_op.drop_index('ix_manual_debts_client_id')
        batch_op.drop_column('client_id')
    op.drop_index('ix_client_name', table_name='client')
    op.drop_table('client')
