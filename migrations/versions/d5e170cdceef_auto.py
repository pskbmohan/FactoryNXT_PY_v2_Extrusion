"""Add extrusion domain fields and convert ARRAY to JSON

Revision ID: d5e170cdceef
Revises: 8b1c2d3e4f5g
Create Date: 2026-06-30 06:27:20.381173

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'd5e170cdceef'
down_revision = '8b1c2d3e4f5g'
branch_labels = None
depends_on = None


def upgrade():
    # ── genealogy_events: make board_id and wo_id nullable ────────────────────
    with op.batch_alter_table('genealogy_events', schema=None) as batch_op:
        batch_op.alter_column('board_id',
               existing_type=sa.VARCHAR(),
               nullable=True)
        batch_op.alter_column('wo_id',
               existing_type=sa.VARCHAR(),
               nullable=True)

    # ── inspection_plans: add extrusion domain columns ────────────────────────
    with op.batch_alter_table('inspection_plans', schema=None) as batch_op:
        batch_op.add_column(sa.Column('target_type', sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column('target_code', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('operation_step', sa.String(length=64), nullable=True))
        batch_op.alter_column('part_number',
               existing_type=sa.VARCHAR(),
               nullable=True)
        batch_op.alter_column('operation_name',
               existing_type=sa.VARCHAR(),
               nullable=True)

    # ── machines: add created_at timestamp ────────────────────────────────────
    with op.batch_alter_table('machines', schema=None) as batch_op:
        batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))

    # ── process_plans: add FK references to extrusion domain ──────────────────
    with op.batch_alter_table('process_plans', schema=None) as batch_op:
        batch_op.add_column(sa.Column('machine_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('die_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('billet_id', sa.String(length=36), nullable=True))

    # ── roles: convert permissions from ARRAY to JSON ─────────────────────────
    # PostgreSQL requires explicit cast when converting ARRAY to JSON.
    # Convert ARRAY -> TEXT -> JSON via to_jsonb() then cast to JSON.
    op.execute("""
        ALTER TABLE roles
        ALTER COLUMN permissions TYPE JSON
        USING to_jsonb(permissions)::json
    """)

    # ── test_results: convert failure_codes from ARRAY to JSON ────────────────
    # failure_codes is nullable, so handle NULL values explicitly
    op.execute("""
        ALTER TABLE test_results
        ALTER COLUMN failure_codes TYPE JSON
        USING CASE
            WHEN failure_codes IS NULL THEN NULL
            ELSE to_jsonb(failure_codes)::json
        END
    """)


def downgrade():
    # ── test_results: convert failure_codes back to ARRAY ─────────────────────
    # JSON -> ARRAY is more complex; convert JSON array to PostgreSQL ARRAY
    op.execute("""
        ALTER TABLE test_results
        ALTER COLUMN failure_codes TYPE VARCHAR[]
        USING ARRAY(
            SELECT jsonb_array_elements_text(failure_codes::jsonb)
        )
    """)

    # ── roles: convert permissions back to ARRAY ──────────────────────────────
    op.execute("""
        ALTER TABLE roles
        ALTER COLUMN permissions TYPE VARCHAR[]
        USING ARRAY(
            SELECT jsonb_array_elements_text(permissions::jsonb)
        )
    """)

    # ── process_plans: remove extrusion domain FKs ────────────────────────────
    with op.batch_alter_table('process_plans', schema=None) as batch_op:
        batch_op.drop_column('billet_id')
        batch_op.drop_column('die_id')
        batch_op.drop_column('machine_id')

    # ── machines: remove created_at ───────────────────────────────────────────
    with op.batch_alter_table('machines', schema=None) as batch_op:
        batch_op.drop_column('created_at')

    # ── inspection_plans: restore original schema ─────────────────────────────
    with op.batch_alter_table('inspection_plans', schema=None) as batch_op:
        batch_op.alter_column('operation_name',
               existing_type=sa.VARCHAR(),
               nullable=False)
        batch_op.alter_column('part_number',
               existing_type=sa.VARCHAR(),
               nullable=False)
        batch_op.drop_column('operation_step')
        batch_op.drop_column('target_code')
        batch_op.drop_column('target_type')

    # ── genealogy_events: restore NOT NULL constraints ────────────────────────
    with op.batch_alter_table('genealogy_events', schema=None) as batch_op:
        batch_op.alter_column('wo_id',
               existing_type=sa.VARCHAR(),
               nullable=False)
        batch_op.alter_column('board_id',
               existing_type=sa.VARCHAR(),
               nullable=False)
