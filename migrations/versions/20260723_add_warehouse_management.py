"""add warehouse management tables for tool room

Revision ID: 20260723
Revises: 20260720_add_quality_schema
Create Date: 2026-07-23

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260723'
down_revision = '20260720_add_quality_schema'
branch_labels = None
depends_on = None


def _idx_exists(inspector, table, name):
    return name in {i['name'] for i in inspector.get_indexes(table)}


def upgrade():
    """Create warehouse management tables for tool room.

    Idempotent: tables may already exist when db.create_all() ran at
    app startup before flask db upgrade.
    """
    from sqlalchemy import inspect as sa_inspect
    inspector = sa_inspect(op.get_bind())
    tables = inspector.get_table_names()

    # ── tool_room_racks ─────────────────────────────────────────────────
    if 'tool_room_racks' not in tables:
        op.create_table(
            'tool_room_racks',
            sa.Column('id', sa.String(length=36), primary_key=True,
                      default=lambda: str(__import__('uuid').uuid4())),
            sa.Column('rack_code', sa.String(64), nullable=False, unique=True),
            sa.Column('rack_name', sa.String(128), nullable=False),
            sa.Column('rack_type', sa.String(32), nullable=False),
            sa.Column('location_zone', sa.String(64), nullable=True),
            sa.Column('total_slots', sa.Integer, nullable=False, default=20),
            sa.Column('available_slots', sa.Integer, nullable=False, default=20),
            sa.Column('status', sa.String(32), nullable=False, default='AVAILABLE'),
            sa.Column('description', sa.Text, nullable=True),
            sa.Column('is_active', sa.Boolean, nullable=False, default=True),
            sa.Column('created_by', sa.String(128), nullable=True),
            sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime,
                      server_default=sa.func.now(), onupdate=sa.func.now()),
            sa.PrimaryKeyConstraint('id'),
        )
    else:
        inspector = sa_inspect(op.get_bind())  # refresh after table creation

    if not _idx_exists(inspector, 'tool_room_racks', 'ix_tool_room_racks_rack_code'):
        op.create_index('ix_tool_room_racks_rack_code', 'tool_room_racks', ['rack_code'])
    if not _idx_exists(inspector, 'tool_room_racks', 'ix_tool_room_racks_status'):
        op.create_index('ix_tool_room_racks_status', 'tool_room_racks', ['status'])
    if not _idx_exists(inspector, 'tool_room_racks', 'ix_tool_room_racks_location_zone'):
        op.create_index('ix_tool_room_racks_location_zone', 'tool_room_racks', ['location_zone'])

    # Ensure created_by column exists (may be missing on tables created by earlier runs)
    if not any(c['name'] == 'created_by' for c in inspector.get_columns('tool_room_racks')):
        op.add_column('tool_room_racks', sa.Column('created_by', sa.String(128), nullable=True))

    # ── die_rack_assignments ────────────────────────────────────────────
    if 'die_rack_assignments' not in tables:
        op.create_table(
            'die_rack_assignments',
            sa.Column('id', sa.String(length=36), primary_key=True,
                      default=lambda: str(__import__('uuid').uuid4())),
            sa.Column('rack_id', sa.String(36), nullable=False),
            sa.Column('slot_number', sa.Integer, nullable=False),
            sa.Column('die_code', sa.String(64), nullable=False),
            sa.Column('die_id', sa.String(36), nullable=True),
            sa.Column('profile_code', sa.String(64), nullable=True),
            sa.Column('alloy', sa.String(64), nullable=True),
            sa.Column('assignment_status', sa.String(32), nullable=False,
                      default='ASSIGNED'),
            sa.Column('assigned_at', sa.DateTime, server_default=sa.func.now()),
            sa.Column('assigned_by', sa.String(128), nullable=True),
            sa.Column('last_accessed_at', sa.DateTime, nullable=True),
            sa.Column('notes', sa.Text, nullable=True),
            sa.ForeignKeyConstraint(['rack_id'], ['tool_room_racks.id'],
                                    ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['die_id'], ['dies.id'],
                                    ondelete='SET NULL'),
            sa.UniqueConstraint('rack_id', 'slot_number', name='uq_rack_slot'),
        )

    if 'die_rack_assignments' in inspector.get_table_names():
        inspector = sa_inspect(op.get_bind())
        for idx_name, col in [
            ('ix_die_rack_assignments_die_code', 'die_code'),
            ('ix_die_rack_assignments_die_id', 'die_id'),
            ('ix_die_rack_assignments_status', 'assignment_status'),
        ]:
            if not _idx_exists(inspector, 'die_rack_assignments', idx_name):
                op.create_index(idx_name, 'die_rack_assignments', [col])

    # ── rack_transactions ───────────────────────────────────────────────
    if 'rack_transactions' not in tables:
        op.create_table(
            'rack_transactions',
            sa.Column('id', sa.String(length=36), primary_key=True,
                      default=lambda: str(__import__('uuid').uuid4())),
            sa.Column('transaction_type', sa.String(32), nullable=False),
            sa.Column('rack_id', sa.String(36), nullable=True),
            sa.Column('slot_number', sa.Integer, nullable=True),
            sa.Column('die_code', sa.String(64), nullable=False),
            sa.Column('die_id', sa.String(36), nullable=True),
            sa.Column('profile_code', sa.String(64), nullable=True),
            sa.Column('alloy', sa.String(64), nullable=True),
            sa.Column('from_rack_id', sa.String(36), nullable=True),
            sa.Column('to_rack_id', sa.String(36), nullable=True),
            sa.Column('operator_id', sa.String(128), nullable=False),
            sa.Column('transaction_time', sa.DateTime,
                      server_default=sa.func.now()),
            sa.Column('notes', sa.Text, nullable=True),
            sa.ForeignKeyConstraint(['rack_id'], ['tool_room_racks.id'],
                                    ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['from_rack_id'], ['tool_room_racks.id'],
                                    ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['to_rack_id'], ['tool_room_racks.id'],
                                    ondelete='SET NULL'),
        )

    if 'rack_transactions' in inspector.get_table_names():
        inspector = sa_inspect(op.get_bind())
        for idx_name, col in [
            ('ix_rack_transactions_transaction_type', 'transaction_type'),
            ('ix_rack_transactions_die_code', 'die_code'),
            ('ix_rack_transactions_operator_id', 'operator_id'),
            ('ix_rack_transactions_time', 'transaction_time'),
        ]:
            if not _idx_exists(inspector, 'rack_transactions', idx_name):
                op.create_index(idx_name, 'rack_transactions', [col])

    # ── die_location_index ──────────────────────────────────────────────
    if 'die_location_index' not in tables:
        op.create_table(
            'die_location_index',
            sa.Column('id', sa.String(length=36), primary_key=True,
                      default=lambda: str(__import__('uuid').uuid4())),
            sa.Column('die_code', sa.String(64), nullable=False),
            sa.Column('rack_id', sa.String(36), nullable=False),
            sa.Column('slot_number', sa.Integer, nullable=False),
            sa.Column('profile_code', sa.String(64), nullable=True),
            sa.Column('alloy', sa.String(64), nullable=True),
            sa.Column('status', sa.String(32), nullable=False,
                      default='IN_STOCK'),
            sa.Column('last_updated_at', sa.DateTime,
                      server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['rack_id'], ['tool_room_racks.id'],
                                    ondelete='CASCADE'),
            sa.UniqueConstraint('die_code',
                                name='uq_die_code_current_location'),
        )

    if 'die_location_index' in inspector.get_table_names():
        inspector = sa_inspect(op.get_bind())
        for idx_name, col in [
            ('ix_die_location_index_die_code', 'die_code'),
            ('ix_die_location_index_profile_code', 'profile_code'),
            ('ix_die_location_index_alloy', 'alloy'),
            ('ix_die_location_index_status', 'status'),
        ]:
            if not _idx_exists(inspector, 'die_location_index', idx_name):
                op.create_index(idx_name, 'die_location_index', [col])


def downgrade():
    """Drop warehouse management tables."""

    # Drop indexes first
    op.drop_index('ix_die_location_index_status', table_name='die_location_index')
    op.drop_index('ix_die_location_index_alloy', table_name='die_location_index')
    op.drop_index('ix_die_location_index_profile_code', table_name='die_location_index')
    op.drop_index('ix_die_location_index_die_code', table_name='die_location_index')
    op.drop_table('die_location_index')
    op.drop_table('rack_transactions')
    op.drop_table('die_rack_assignments')
    op.drop_index('ix_tool_room_racks_status', table_name='tool_room_racks')
    op.drop_index('ix_tool_room_racks_location_zone', table_name='tool_room_racks')
    op.drop_index('ix_tool_room_racks_rack_code', table_name='tool_room_racks')
    op.drop_table('tool_room_racks')
