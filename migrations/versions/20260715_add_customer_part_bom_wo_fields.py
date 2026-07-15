"""add_customer_part_bom_wo_fields

Revision ID: 20260715_add_customer_part_bom_wo_fields
Revises: base_20260701
Create Date: 2026-07-15

Background
----------
Adds BOM-driven Work Order support with new master data models:
- customers: Customer master data
- part_numbers: Part number master data
- customer_part_numbers: Mapping between customers and their approved parts
- part_number_boms: Bill of Materials linking parts to die/billet types
- customer_order_lines: Line items within customer orders

Also patches WorkOrder table with BOM resolution fields:
- customer_order_line_id, part_number_id, die_type_id, billet_type_id, bom_version_id
"""
from alembic import op
import sqlalchemy as sa


revision = '20260715_add_customer_part_bom_wo_fields'
down_revision = 'base_20260701'
branch_labels = None
depends_on = None


def upgrade():
    # ─── customers table ──────────────────────────────────────────────────────
    op.create_table(
        'customers',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('customer_code', sa.String(64), unique=True, nullable=False),
        sa.Column('customer_name', sa.String(128), nullable=False),
        sa.Column('contact_email', sa.String(128), nullable=True),
        sa.Column('contact_phone', sa.String(32), nullable=True),
        sa.Column('address', sa.Text, nullable=True),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
    )

    # ─── part_numbers table ───────────────────────────────────────────────────
    op.create_table(
        'part_numbers',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('part_code', sa.String(64), unique=True, nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('profile_code', sa.String(64), nullable=True),
        sa.Column('alloy', sa.String(64), nullable=True),
        sa.Column('unit_weight_kg', sa.Float, nullable=True),
        sa.Column('uom', sa.String(16), default='KG'),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
    )

    # ─── customer_part_numbers table (junction) ──────────────────────────────
    op.create_table(
        'customer_part_numbers',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('customer_id', sa.String(36), sa.ForeignKey('customers.id'), nullable=False),
        sa.Column('part_number_id', sa.String(36), sa.ForeignKey('part_numbers.id'), nullable=False),
        sa.Column('customer_part_ref', sa.String(64), nullable=True),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.UniqueConstraint('customer_id', 'part_number_id', name='uq_customer_part'),
    )

    # ─── part_number_boms table ──────────────────────────────────────────────
    op.create_table(
        'part_number_boms',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('part_number_id', sa.String(36), sa.ForeignKey('part_numbers.id'), nullable=False),
        sa.Column('version', sa.Integer, nullable=False, default=1),
        sa.Column('die_type_id', sa.String(36), sa.ForeignKey('dies.id'), nullable=False),
        sa.Column('billet_type_id', sa.String(36), sa.ForeignKey('billets.id'), nullable=False),
        sa.Column('billet_weight_kg', sa.Float, nullable=True),
        sa.Column('extrusion_ratio', sa.Float, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_by', sa.String(128), nullable=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ─── customer_order_lines table ──────────────────────────────────────────
    op.create_table(
        'customer_order_lines',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('order_id', sa.String(36), sa.ForeignKey('customer_orders.id'), nullable=False),
        sa.Column('part_number_id', sa.String(36), sa.ForeignKey('part_numbers.id'), nullable=False),
        sa.Column('line_number', sa.Integer, nullable=False, default=1),
        sa.Column('ordered_qty', sa.Float, nullable=False),
        sa.Column('uom', sa.String(16), default='KG'),
        sa.Column('required_date', sa.Date, nullable=True),
        sa.Column('customer_po_reference', sa.String(64), nullable=True),
        sa.Column('status', sa.String(32), nullable=False, default='OPEN'),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
    )

    # ─── Patch work_orders table with BOM resolution fields ──────────────────
    op.add_column('work_orders', sa.Column('customer_order_line_id', sa.String(36), nullable=True))
    op.add_column('work_orders', sa.Column('part_number_id', sa.String(36), nullable=True))
    op.add_column('work_orders', sa.Column('die_type_id', sa.String(36), nullable=True))
    op.add_column('work_orders', sa.Column('billet_type_id', sa.String(36), nullable=True))
    op.add_column('work_orders', sa.Column('bom_version_id', sa.String(36), nullable=True))

    # Add foreign keys for the new columns
    op.create_foreign_key(
        'fk_work_order_customer_order_line',
        'work_orders', 'customer_order_lines',
        ['customer_order_line_id'], ['id']
    )
    op.create_foreign_key(
        'fk_work_order_part_number',
        'work_orders', 'part_numbers',
        ['part_number_id'], ['id']
    )
    op.create_foreign_key(
        'fk_work_order_die_type',
        'work_orders', 'dies',
        ['die_type_id'], ['id']
    )
    op.create_foreign_key(
        'fk_work_order_billet_type',
        'work_orders', 'billets',
        ['billet_type_id'], ['id']
    )
    op.create_foreign_key(
        'fk_work_order_bom_version',
        'work_orders', 'part_number_boms',
        ['bom_version_id'], ['id']
    )


def downgrade():
    # Drop foreign keys first
    op.drop_constraint('fk_work_order_customer_order_line', 'work_orders', type_='foreignkey')
    op.drop_constraint('fk_work_order_part_number', 'work_orders', type_='foreignkey')
    op.drop_constraint('fk_work_order_die_type', 'work_orders', type_='foreignkey')
    op.drop_constraint('fk_work_order_billet_type', 'work_orders', type_='foreignkey')
    op.drop_constraint('fk_work_order_bom_version', 'work_orders', type_='foreignkey')

    # Drop new columns from work_orders
    op.drop_column('work_orders', 'bom_version_id')
    op.drop_column('work_orders', 'billet_type_id')
    op.drop_column('work_orders', 'die_type_id')
    op.drop_column('work_orders', 'part_number_id')
    op.drop_column('work_orders', 'customer_order_line_id')

    # Drop new tables in reverse order (dependencies first)
    op.drop_table('customer_order_lines')
    op.drop_table('part_number_boms')
    op.drop_table('customer_part_numbers')
    op.drop_table('part_numbers')
    op.drop_table('customers')
