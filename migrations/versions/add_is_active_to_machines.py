"""add is_active column to machines table

Revision ID: add_is_active_machines
Revises: f60e6a92c60b
Create Date: 2026-07-01

Made idempotent: db.create_all() may have already added the column before
Alembic migrations ran (brownfield / DO App Platform first-deploy scenario).
Using ADD COLUMN IF NOT EXISTS avoids DuplicateColumn errors in that case.
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_is_active_machines'
down_revision = 'f60e6a92c60b'
branch_labels = None
depends_on = None


def upgrade():
    # IF NOT EXISTS prevents DuplicateColumn when db.create_all() already
    # created the column before migrations ran (DO App Platform / brownfield).
    op.execute(
        "ALTER TABLE machines ADD COLUMN IF NOT EXISTS "
        "is_active BOOLEAN NOT NULL DEFAULT true"
    )


def downgrade():
    op.drop_column('machines', 'is_active')
