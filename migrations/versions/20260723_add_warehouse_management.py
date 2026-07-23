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


def upgrade():
    """Create warehouse management tables for tool room."""

    # ──────────────────────────────────────────────────────────────────────
    # Tool Room Rack Management Tables
    # ──────────────────────────────────────────────────────────────────────

    op.create_table(
        'tool_room_racks',
        sa.Column('id', sa.String(length=36), primary_key=True, default=lambda: str(__import__('uuid').uuid4())),
        sa.Column('rack_code', sa.String(64), nullable=False, unique=True),
        sa.Column('rack_name', sa.String(128), nullable=False),
        sa.Column('rack_type', sa.String(32), nullable=False),  # 'STORAGE_RACK' | 'QUICK_CHANGE_RACK' | 'INPRESS_RACK'
        sa.Column('location_zone', sa.String(64), nullable=True),  # e.g., 'ZONE_A', 'ZONE_B'
        sa.Column('total_slots', sa.Integer, nullable=False, default=20),
        sa.Column('available_slots', sa.Integer, nullable=False, default=20),
        sa.Column('status', sa.String(32), nullable=False, default='AVAILABLE'),  # AVAILABLE | IN_USE | MAINTENANCE
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, default=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index('ix_tool_room_racks_rack_code', 'tool_room_racks', ['rack_code'])
    op.create_index('ix_tool_room_racks_status', 'tool_room_racks', ['status'])
    op.create_index('ix_tool_room_racks_location_zone', 'tool_room_racks', ['location_zone'])

    # ──────────────────────────────────────────────────────────────────────
    # Die-Rack Assignment Table (Links Dies to Rack Slots)
    # ──────────────────────────────────────────────────────────────────────

    op.create_table(
        'die_rack_assignments',
        sa.Column('id', sa.String(length=36), primary_key=True, default=lambda: str(__import__('uuid').uuid4())),
        sa.Column('rack_id', sa.String(36), nullable=False),
        sa.Column('slot_number', sa.Integer, nullable=False),
        sa.Column('die_code', sa.String(64), nullable=False),  # The die code stored in this slot
        sa.Column('die_id', sa.String(36), nullable=True),     # FK to dies table if exists
        sa.Column('profile_code', sa.String(64), nullable=True),
        sa.Column('alloy', sa.String(64), nullable=True),
        sa.Column('assignment_status', sa.String(32), nullable=False, default='ASSIGNED'),  # ASSIGNED | RESERVED | REMOVED
        sa.Column('assigned_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('assigned_by', sa.String(128), nullable=True),
        sa.Column('last_accessed_at', sa.DateTime, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.ForeignKeyConstraint(['rack_id'], ['tool_room_racks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['die_id'], ['dies.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('rack_id', 'slot_number', name='uq_rack_slot'),
    )

    op.create_index('ix_die_rack_assignments_die_code', 'die_rack_assignments', ['die_code'])
    op.create_index('ix_die_rack_assignments_die_id', 'die_rack_assignments', ['die_id'])
    op.create_index('ix_die_rack_assignments_status', 'die_rack_assignments', ['assignment_status'])

    # ──────────────────────────────────────────────────────────────────────
    # Rack Transaction Log (In/Out Transactions)
    # ──────────────────────────────────────────────────────────────────────

    op.create_table(
        'rack_transactions',
        sa.Column('id', sa.String(length=36), primary_key=True, default=lambda: str(__import__('uuid').uuid4())),
        sa.Column('transaction_type', sa.String(32), nullable=False),  # IN | OUT | TRANSFER | ADJUSTMENT
        sa.Column('rack_id', sa.String(36), nullable=True),           # FK to tool_room_racks.id (nullable for unassigned transactions)
        sa.Column('slot_number', sa.Integer, nullable=True),          # Slot involved in transaction
        sa.Column('die_code', sa.String(64), nullable=False),         # Die code being tracked
        sa.Column('die_id', sa.String(36), nullable=True),            # FK to dies.id (nullable for unknown dies)
        sa.Column('profile_code', sa.String(64), nullable=True),      # Profile associated with die
        sa.Column('alloy', sa.String(64), nullable=True),             # Alloy of the die
        sa.Column('from_rack_id', sa.String(36), nullable=True),       # For TRANSFER transactions (source rack)
        sa.Column('to_rack_id', sa.String(36), nullable=True),         # For TRANSFER transactions (destination rack)
        sa.Column('operator_id', sa.String(128), nullable=False),     # User who performed transaction
        sa.Column('transaction_time', sa.DateTime, server_default=sa.func.now()),
        sa.Column('notes', sa.Text, nullable=True),
        sa.ForeignKeyConstraint(['rack_id'], ['tool_room_racks.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['from_rack_id'], ['tool_room_racks.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['to_rack_id'], ['tool_room_racks.id'], ondelete='SET NULL'),
    )

    op.create_index('ix_rack_transactions_transaction_type', 'rack_transactions', ['transaction_type'])
    op.create_index('ix_rack_transactions_die_code', 'rack_transactions', ['die_code'])
    op.create_index('ix_rack_transactions_operator_id', 'rack_transactions', ['operator_id'])
    op.create_index('ix_rack_transactions_time', 'rack_transactions', ['transaction_time'])

    # ──────────────────────────────────────────────────────────────────────
    # Rack Search Index (Optimized for barcode/die code lookups)
    # ──────────────────────────────────────────────────────────────────────

    op.create_table(
        'die_location_index',
        sa.Column('id', sa.String(length=36), primary_key=True, default=lambda: str(__import__('uuid').uuid4())),
        sa.Column('die_code', sa.String(64), nullable=False),         # Primary search key
        sa.Column('rack_id', sa.String(36), nullable=False),          # Current rack location
        sa.Column('slot_number', sa.Integer, nullable=False),         # Slot number in rack
        sa.Column('profile_code', sa.String(64), nullable=True),      # For profile-based search
        sa.Column('alloy', sa.String(64), nullable=True),             # For alloy-based search
        sa.Column('status', sa.String(32), nullable=False, default='IN_STOCK'),  # IN_STOCK | OUT | UNKNOWN
        sa.Column('last_updated_at', sa.DateTime, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['rack_id'], ['tool_room_racks.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('die_code', name='uq_die_code_current_location'),
    )

    op.create_index('ix_die_location_index_die_code', 'die_location_index', ['die_code'])
    op.create_index('ix_die_location_index_profile_code', 'die_location_index', ['profile_code'])
    op.create_index('ix_die_location_index_alloy', 'die_location_index', ['alloy'])
    op.create_index('ix_die_location_index_status', 'die_location_index', ['status'])


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
