"""Remove Badini Kurdish language

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-18 14:45:00.000000

"""
import json

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None

SNAPSHOT_TABLES = ['order_item', 'pos_order_item']


def rewrite_snapshots(drop_kurdish):
    """Sold-line snapshots are frozen JSON, so historical receipts need the same rename."""
    bind = op.get_bind()
    for table in SNAPSHOT_TABLES:
        rows = bind.execute(sa.text(f'SELECT id, snapshot FROM {table} WHERE snapshot IS NOT NULL')).fetchall()
        for row_id, raw in rows:
            snapshot = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
            if not isinstance(snapshot, dict):
                continue
            if drop_kurdish:
                if not snapshot.get('name_en'):
                    snapshot['name_en'] = snapshot.get('name_ku')
                snapshot.pop('name_ku', None)
            else:
                snapshot.setdefault('name_ku', snapshot.get('name_en'))
            bind.execute(sa.text(f'UPDATE {table} SET snapshot = :snapshot WHERE id = :id'),
                         {'snapshot': json.dumps(snapshot), 'id': row_id})


def upgrade():
    # Kurdish was the required source language; preserve any row that only had Kurdish text.
    for table in ['category', 'product']:
        op.execute(f'UPDATE {table} SET name_en = name_ku WHERE name_en IS NULL OR name_en = ""')
        op.execute(f'UPDATE {table} SET description_en = description_ku '
                   f'WHERE (description_en IS NULL OR description_en = "") AND description_ku IS NOT NULL')
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column('name_en', existing_type=sa.String(length=100), nullable=False)
            batch_op.drop_column('description_ku')
            batch_op.drop_column('name_ku')

    rewrite_snapshots(drop_kurdish=True)

    op.execute("UPDATE settings SET default_language = 'en' WHERE default_language = 'ku'")
    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.alter_column('default_language', existing_type=sa.String(length=4),
                              server_default='en', existing_nullable=False)


def downgrade():
    rewrite_snapshots(drop_kurdish=False)
    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.alter_column('default_language', existing_type=sa.String(length=4),
                              server_default='ku', existing_nullable=False)

    # The original Kurdish text is gone; English seeds the restored columns so they stay non-null.
    for table in ['product', 'category']:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column('name_ku', sa.String(length=100), nullable=True))
            batch_op.add_column(sa.Column('description_ku', sa.Text(), nullable=True))
        op.execute(f'UPDATE {table} SET name_ku = name_en')
        op.execute(f'UPDATE {table} SET description_ku = description_en')
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column('name_ku', existing_type=sa.String(length=100), nullable=False)
            batch_op.alter_column('name_en', existing_type=sa.String(length=100), nullable=True)
