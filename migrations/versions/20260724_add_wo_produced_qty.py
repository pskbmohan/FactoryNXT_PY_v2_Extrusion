"""add_wo_produced_qty

Revision ID: 20260724_add_wo_produced_qty
Revises: 20260723
Create Date: 2026-07-24

Background
----------
The Work Order On-Time Probability engine (app/services/wo_probability.py)
needs a running count of units completed against a WO's target quantity.
No existing table tracks this against work_orders.quantity, so this adds
a single `produced_qty` column, defaulting existing rows to 0.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = '20260724_add_wo_produced_qty'
down_revision = '20260723'
branch_labels = None
depends_on = None


def _has_column(inspector, table, column):
    return column in {c['name'] for c in inspector.get_columns(table)}


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if not _has_column(inspector, 'work_orders', 'produced_qty'):
        op.add_column(
            'work_orders',
            sa.Column('produced_qty', sa.Integer(), nullable=False, server_default='0'),
        )


def downgrade():
    op.drop_column('work_orders', 'produced_qty')
