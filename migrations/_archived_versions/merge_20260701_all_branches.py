"""merge all branch conflicts

Revision ID: merge_all_branches_20260701
Revises: 20260702_die_ext, add_is_active_machines
Create Date: 2026-07-01

Merges the two parallel heads that both descend from the initial
f60e6a92c60b commit:

  Path A: f60e6a92c60b -> f4bc0852bb9a -> 322b85370ef9 -> 7a42c1b9e2d5
          -> 8b1c2d3e4f5g -> d5e170cdceef -> aps_add_schedule_engine
          -> 20260707_mrm -> aps_add_notes_columns -> 20260702_die_ext

  Path B: f60e6a92c60b -> add_is_active_machines

Both branches operate on disjoint tables (machines.is_active vs. the
APS/extrusion schema), so there are no duplicate schema operations to
guard. This merge is a structural-only, empty migration.

"""
from alembic import op
import sqlalchemy as sa

revision = 'merge_all_branches_20260701'
down_revision = ('20260702_die_ext', 'add_is_active_machines')
branch_labels = None
depends_on = None


def upgrade():
    pass  # merge-only migration — no schema changes


def downgrade():
    pass  # merge-only migration — no schema changes
