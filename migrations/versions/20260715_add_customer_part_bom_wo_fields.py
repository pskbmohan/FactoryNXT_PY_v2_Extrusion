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
from sqlalchemy import inspect


revision = '20260715_add_customer_part_bom_wo_fields'
down_revision = '20260704_eav'
branch_labels = None
depends_on = None


def _has_table(inspector, name):
    """Check whether a table already exists in the target schema."""
    return name in inspector.get_table_names()


def _has_column(inspector, table, column):
    """Check whether a column already exists on a table."""
    if not _has_table(inspector, table):
        return False
    return column in {c['name'] for c in inspector.get_columns(table)}


def _has_fk(inspector, table, constraint_name):
    """Check whether a named FK constraint already exists on a table."""
    if not _has_table(inspector, table):
        return False
    return constraint_name in {
        fk['name'] for fk in inspector.get_foreign_keys(table) if fk.get('name')
    }


def _create_table_if_missing(inspector, name, *args, **kwargs):
    """op.create_table(...) only if the table does not already exist.

    The application calls `db.create_all()` at startup which materialises every
    registered SQLAlchemy model BEFORE Alembic migrations run.  That means on
    a fresh container boot the tables this migration introduces may already be
    present when Alembic replays it.  Guarding with `has_table` keeps the
    migration idempotent without changing semantics for a DB that hasn't
    bootstrapped the models yet.
    """
    if _has_table(inspector, name):
        return
    op.create_table(name, *args, **kwargs)


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    # ─── customers table ──────────────────────────────────────────────────────
    _create_table_if_missing(
        inspector,
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
    # Refresh inspector after a possible create so later lookups see the new table.
    inspector = inspect(conn)

    # ─── part_numbers table ───────────────────────────────────────────────────
    _create_table_if_missing(
        inspector,
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
    inspector = inspect(conn)

    # ─── customer_part_numbers table (junction) ──────────────────────────────
    _create_table_if_missing(
        inspector,
        'customer_part_numbers',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('customer_id', sa.String(36), sa.ForeignKey('customers.id'), nullable=False),
        sa.Column('part_number_id', sa.String(36), sa.ForeignKey('part_numbers.id'), nullable=False),
        sa.Column('customer_part_ref', sa.String(64), nullable=True),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.UniqueConstraint('customer_id', 'part_number_id', name='uq_customer_part'),
    )
    inspector = inspect(conn)

    # ─── part_number_boms table ──────────────────────────────────────────────
    _create_table_if_missing(
        inspector,
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
    inspector = inspect(conn)

    # ─── customer_order_lines table ──────────────────────────────────────────
    _create_table_if_missing(
        inspector,
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
    inspector = inspect(conn)

    # ─── Patch work_orders table with BOM resolution fields ──────────────────
    bom_columns = [
        ('customer_order_line_id', sa.String(36)),
        ('part_number_id',         sa.String(36)),
        ('die_type_id',            sa.String(36)),
        ('billet_type_id',         sa.String(36)),
        ('bom_version_id',         sa.String(36)),
    ]
    for col_name, col_type in bom_columns:
        if not _has_column(inspector, 'work_orders', col_name):
            op.add_column('work_orders', sa.Column(col_name, col_type, nullable=True))

    # Refresh inspector after adding columns so FK lookups are consistent.
    inspector = inspect(conn)

    # Add foreign keys for the new columns (idempotent by constraint name)
    new_fks = [
        ('fk_work_order_customer_order_line', 'work_orders', 'customer_order_lines',
         ['customer_order_line_id'], ['id']),
        ('fk_work_order_part_number', 'work_orders', 'part_numbers',
         ['part_number_id'], ['id']),
        ('fk_work_order_die_type', 'work_orders', 'dies',
         ['die_type_id'], ['id']),
        ('fk_work_order_billet_type', 'work_orders', 'billets',
         ['billet_type_id'], ['id']),
        ('fk_work_order_bom_version', 'work_orders', 'part_number_boms',
         ['bom_version_id'], ['id']),
    ]
    for fk_name, src_table, ref_table, src_cols, ref_cols in new_fks:
        if not _has_fk(inspector, src_table, fk_name):
            op.create_foreign_key(fk_name, src_table, ref_table, src_cols, ref_cols)


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
