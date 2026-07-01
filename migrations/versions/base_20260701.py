"""Base migration — single source of truth for fresh and existing DBs

Revision ID: base_20260701
Revises:
Create Date: 2026-07-01

Background
----------
The migration graph had accumulated overlapping branches and self-referential
merge nodes that repeatedly tripped Alembic's overlap detection on deploy:

    ERROR: Requested revision 20260702_die_ext overlaps with other
           requested revisions aps_add_notes_columns

The application calls `db.create_all()` at startup (see app/__init__.py),
which materialises every registered SQLAlchemy model table into Postgres
WITHOUT recording any revision in `alembic_version`.  After that, migrations
aren't needed to apply schema — the schema already exists.  What we DO need
is a single, clean, unambiguous version marker so Alembic can record "this
DB is up-to-date" without ever replaying a tangled graph.

This file is that marker.  Its `upgrade()` and `downgrade()` are no-ops:
the schema already exists (via db.create_all()), and there is nothing to
run.  The only thing this migration does is establish a clean revision ID
that `entrypoint.sh` stamps into `alembic_version` on every startup.

Old migration files have been moved to `migrations/_archived_versions/`
by the one-shot helper `scripts/clean_migrations.py`.  They are kept for
reference / archaeology only; Alembic does not scan the `_archived_versions/`
directory.

If a future schema change is needed, write it as a NORMAL migration with
`down_revision = 'base_20260701'`.  That's the only link needed going forward.

"""
from alembic import op
import sqlalchemy as sa


revision = 'base_20260701'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Base marker — db.create_all() materialises the schema; this is a
    # no-op structural anchor only.
    pass


def downgrade():
    pass
