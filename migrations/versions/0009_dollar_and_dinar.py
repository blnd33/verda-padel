"""Dollar and dinar: a currency on every amount

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-25 21:00:00.000000

Existing rows are dinar. Bills may now owe both currencies, so a bill can have
one debt and one refund adjustment per currency instead of one in total.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None

CURRENCY_TABLES = ['product', 'pos_order_item', 'order_item', 'payment', 'adjustment', 'manual_debts', 'expense']
# SQLite reflects unnamed unique constraints without a name; this convention
# names them so batch mode can drop them.
NAMING = {'uq': 'uq_%(table_name)s_%(column_0_name)s'}


def currency_column():
    return sa.Column('currency', sa.String(length=3), server_default='IQD', nullable=False)


def single_column_uniques(bind, table, columns):
    found = []
    for constraint in sa.inspect(bind).get_unique_constraints(table):
        if constraint['column_names'] in [[c] for c in columns]:
            found.append(constraint)
    return found


def upgrade():
    bind = op.get_bind()
    sqlite = bind.dialect.name == 'sqlite'
    for table in CURRENCY_TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(currency_column())
    with op.batch_alter_table('pos_session', schema=None) as batch_op:
        batch_op.add_column(sa.Column('discount_currency', sa.String(length=3), server_default='IQD', nullable=False))
        batch_op.add_column(sa.Column('total_usd', sa.BigInteger(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('manual_discount_usd', sa.BigInteger(), server_default='0', nullable=False))
    with op.batch_alter_table('order', schema=None) as batch_op:
        batch_op.add_column(sa.Column('total_usd', sa.BigInteger(), server_default='0', nullable=False))

    with op.batch_alter_table('manual_debts', schema=None) as batch_op:
        batch_op.drop_constraint('uq_manual_debts_session_id', type_='unique')
        batch_op.create_unique_constraint('uq_manual_debts_session_currency', ['session_id', 'currency'])

    old = single_column_uniques(bind, 'adjustment', ['session_id', 'order_id'])
    with op.batch_alter_table('adjustment', schema=None, naming_convention=NAMING if sqlite else None,
                              recreate='always' if sqlite else 'auto') as batch_op:
        for constraint in old:
            name = constraint['name'] or 'uq_adjustment_' + constraint['column_names'][0]
            batch_op.drop_constraint(name, type_='unique')
        batch_op.create_unique_constraint('uq_adjustment_session_currency', ['session_id', 'currency'])
        batch_op.create_unique_constraint('uq_adjustment_order_currency', ['order_id', 'currency'])


def downgrade():
    with op.batch_alter_table('adjustment', schema=None) as batch_op:
        batch_op.drop_constraint('uq_adjustment_order_currency', type_='unique')
        batch_op.drop_constraint('uq_adjustment_session_currency', type_='unique')
        batch_op.create_unique_constraint('uq_adjustment_session_id', ['session_id'])
        batch_op.create_unique_constraint('uq_adjustment_order_id', ['order_id'])
    with op.batch_alter_table('manual_debts', schema=None) as batch_op:
        batch_op.drop_constraint('uq_manual_debts_session_currency', type_='unique')
        batch_op.create_unique_constraint('uq_manual_debts_session_id', ['session_id'])
    with op.batch_alter_table('order', schema=None) as batch_op:
        batch_op.drop_column('total_usd')
    with op.batch_alter_table('pos_session', schema=None) as batch_op:
        batch_op.drop_column('manual_discount_usd')
        batch_op.drop_column('total_usd')
        batch_op.drop_column('discount_currency')
    for table in reversed(CURRENCY_TABLES):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column('currency')
