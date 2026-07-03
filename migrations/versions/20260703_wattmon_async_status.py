"""Wattmon: add async-processing status columns

Revision ID: 20260703_wattmon
Revises: base_20260701
Create Date: 2026-07-03

Background
----------
The Wattmon integration POST endpoint was rewritten to return the HTTP
response immediately and parse the CSV body in a background thread, so the
integration device (which has a strict 30-second CGI timeout) doesn't time
out on large payloads. The upload record now tracks processing state and
persists the raw body to disk.

Adds two new columns to ``wattmon_uploads``:
  * ``status``        -- 'pending' / 'success' / 'failed'
  * ``error_detail``  -- free-text error message when status == 'failed'

(The ``wattmon_readings`` table itself is created automatically by the app's
``db.create_all()`` call at startup and does not need a migration entry.)

Statements use ``ADD COLUMN IF NOT EXISTS`` so they are idempotent.
"""
from alembic import op


revision = '20260703_wattmon'
down_revision = 'base_20260701'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE wattmon_uploads "
        "ADD COLUMN IF NOT EXISTS status VARCHAR(16) NOT NULL DEFAULT 'pending'"
    )
    op.execute(
        "ALTER TABLE wattmon_uploads "
        "ADD COLUMN IF NOT EXISTS error_detail TEXT"
    )


def downgrade():
    op.execute("ALTER TABLE wattmon_uploads DROP COLUMN IF EXISTS error_detail")
    op.execute("ALTER TABLE wattmon_uploads DROP COLUMN IF EXISTS status")
