"""Add machine resource mapping for work order constraints

Revision ID: 20260707_mrm
Revises: aps_add_schedule_engine
Create Date: 2026-07-07

This migration adds tables to map machines to dies and consumables required for each part number.
When a work order is released, the scheduler uses these mappings as constraints.

Idempotent: uses IF NOT EXISTS so re-runs after a partial failure are safe.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = '20260707_mrm'
down_revision = 'aps_add_schedule_engine'
branch_labels = None
depends_on = None


def _table_exists(table_name):
    """Return True if the table already exists in the DB (handles re-run after partial failure)."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    return table_name in inspector.get_table_names()


def upgrade():
    # 1. Create MachineResourceMapping table (master mapping)
    if not _table_exists('machine_resource_mapping'):
        op.create_table(
            'machine_resource_mapping',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('part_number', sa.String(100), nullable=False),
            sa.Column('machine_id', sa.Integer(), nullable=False),
            # dies.id is VARCHAR(36) — must use String here, not Integer
            sa.Column('die_id', sa.String(36), nullable=True),
            sa.Column('changeover_time_sec', sa.Integer(), nullable=False, server_default='1800'),
            sa.Column('setup_time_sec', sa.Integer(), nullable=False, server_default='900'),
            sa.Column('cycle_time_sec', sa.Integer(), nullable=False, server_default='60'),
            sa.Column('transport_time_sec', sa.Integer(), nullable=False, server_default='300'),
            sa.Column('consumable_ids', sa.JSON(), nullable=True),
            sa.Column('preferred', sa.Boolean(), server_default='false'),
            sa.Column('active', sa.Boolean(), server_default='true'),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['machine_id'], ['machines.id']),
            sa.ForeignKeyConstraint(['die_id'], ['dies.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('part_number', 'machine_id', name='uq_part_machine'),
        )
        op.create_index('idx_machine_resource_part', 'machine_resource_mapping', ['part_number'])
        op.create_index('idx_machine_resource_active', 'machine_resource_mapping', ['active', 'part_number'])

    # 2. Create WorkOrderResource table (consumed resources during execution)
    if not _table_exists('work_order_resources'):
        op.create_table(
            'work_order_resources',
            sa.Column('id', sa.Integer(), nullable=False),
            # work_orders.id is VARCHAR(36) — must use String here, not Integer
            sa.Column('work_order_id', sa.String(36), nullable=False),
            sa.Column('machine_id', sa.Integer(), nullable=False),
            # dies.id is VARCHAR(36)
            sa.Column('die_id', sa.String(36), nullable=True),
            sa.Column('consumable_ids', sa.JSON(), nullable=True),
            sa.Column('cycle_time_sec', sa.Integer(), nullable=False),
            sa.Column('changeover_time_sec', sa.Integer(), nullable=False),
            sa.Column('setup_time_sec', sa.Integer(), nullable=False),
            sa.Column('transport_time_sec', sa.Integer(), nullable=False),
            sa.Column('scheduled_start', sa.DateTime(), nullable=False),
            sa.Column('scheduled_end', sa.DateTime(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['work_order_id'], ['work_orders.id']),
            sa.ForeignKeyConstraint(['machine_id'], ['machines.id']),
            sa.ForeignKeyConstraint(['die_id'], ['dies.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('idx_wor_entry', 'work_order_resources', ['work_order_id'])


def downgrade():
    if _table_exists('work_order_resources'):
        op.drop_index('idx_wor_entry', table_name='work_order_resources')
        op.drop_table('work_order_resources')
    if _table_exists('machine_resource_mapping'):
        op.drop_index('idx_machine_resource_active', table_name='machine_resource_mapping')
        op.drop_index('idx_machine_resource_part', table_name='machine_resource_mapping')
        op.drop_table('machine_resource_mapping')
