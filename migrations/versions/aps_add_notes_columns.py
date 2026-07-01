"""Add missing 'notes' column to aps_schedule_versions.

Revision ID: aps_add_notes_columns
Revises: 20260707_mrm, aps_add_schedule_engine
Create Date: 2026-07-01

Background
----------
The original aps_add_schedule_engine migration created aps_schedule_versions
with a ``description`` column.  The SQLAlchemy model (models_aps.py) was
later updated to use ``notes`` instead, but no migration was written for
the ALTER.  When the table already existed in Postgres (created by
db.create_all() at startup before migrations ran), the ``notes`` column
was missing, producing:

    ProgrammingError: column aps_schedule_versions.notes does not exist

This is a MERGE migration — it comes after both:
  * 20260707_mrm            (machine resource mapping)
  * aps_add_schedule_engine (APS tables)

This collapses the two-head fork back to a single linear tip so that
``flask db upgrade heads`` (and plain ``flask db upgrade``) both work.

The upgrade() adds ``notes`` (TEXT, nullable) to aps_schedule_versions
and ``published_at`` (DATETIME, nullable) if either is absent, making
the migration fully idempotent.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "aps_add_notes_columns"
# Merge node: depends on BOTH prior heads to collapse the fork
down_revision = ("20260707_mrm", "aps_add_schedule_engine")
branch_labels = None
depends_on = None


def _has_column(conn, table, column):
    insp = inspect(conn)
    cols = [c["name"] for c in insp.get_columns(table)]
    return column in cols


def _has_table(conn, table):
    insp = inspect(conn)
    return table in insp.get_table_names()


def upgrade():
    bind = op.get_bind()

    # ── aps_schedule_versions: add notes ─────────────────────────────────
    if _has_table(bind, "aps_schedule_versions"):
        if not _has_column(bind, "aps_schedule_versions", "notes"):
            op.add_column(
                "aps_schedule_versions",
                sa.Column("notes", sa.Text, nullable=True),
            )

    # ── aps_schedule_versions: add published_at if missing ───────────────
    # Some DB instances created by the old migration omit published_at.
    if _has_table(bind, "aps_schedule_versions"):
        if not _has_column(bind, "aps_schedule_versions", "published_at"):
            op.add_column(
                "aps_schedule_versions",
                sa.Column("published_at", sa.DateTime, nullable=True),
            )


def downgrade():
    bind = op.get_bind()

    if _has_table(bind, "aps_schedule_versions"):
        if _has_column(bind, "aps_schedule_versions", "notes"):
            op.drop_column("aps_schedule_versions", "notes")
        if _has_column(bind, "aps_schedule_versions", "published_at"):
            op.drop_column("aps_schedule_versions", "published_at")
