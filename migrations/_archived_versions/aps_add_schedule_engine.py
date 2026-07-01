"""Add Advanced Planning System (APS) tables.

Revision ID: aps_add_schedule_engine
Revises: d5e170cdceef
Create Date: 2026-06-30

Tables added:
  * aps_schedule_versions   – versioned snapshot / branch of the plan
  * aps_schedule_entries    – one row per scheduled job on a machine
  * aps_constraint_logs     – reasons a job is at risk / blocked
  * aps_schedule_events     – audit trail for schedule mutations

Idempotent: this app calls `db.create_all()` at startup (in
`app/__init__.py`) which creates all SA-declared tables if they don't
exist. That means the APS tables may already be materialised in
production Postgres before this migration runs. The upgrade() function
therefore guards every CREATE TABLE with an "IF NOT EXISTS" check and
is a no-op when the tables are already present.
"""
from alembic import op
import sqlalchemy as sa


revision = "aps_add_schedule_engine"
down_revision = "d5e170cdceef"
branch_labels = None
depends_on = None


def _has_table(conn, name):
    """Check if a table exists in the current database."""
    from sqlalchemy import inspect
    insp = inspect(conn)
    return name in insp.get_table_names()


def upgrade():
    bind = op.get_bind()

    # ── aps_schedule_versions ─────────────────────────────────────────────
    if not _has_table(bind, "aps_schedule_versions"):
        op.create_table(
            "aps_schedule_versions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("version_type", sa.String(32), nullable=False,
                      server_default="DRAFT"),
            sa.Column("planning_horizon_days", sa.Integer, nullable=False,
                      server_default="14"),
            sa.Column("description", sa.Text, nullable=True),
            sa.Column("created_by", sa.String(128), nullable=True),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("published_at", sa.DateTime, nullable=True),
        )

    # ── aps_schedule_entries ──────────────────────────────────────────────
    if not _has_table(bind, "aps_schedule_entries"):
        op.create_table(
            "aps_schedule_entries",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("version_id", sa.String(36),
                      sa.ForeignKey("aps_schedule_versions.id"),
                      nullable=False, index=True),
            sa.Column("work_order_id", sa.String(36),
                      sa.ForeignKey("work_orders.id"),
                      nullable=True, index=True),
            sa.Column("process_plan_id", sa.String(36),
                      sa.ForeignKey("process_plans.id"),
                      nullable=True),
            sa.Column("customer_order_id", sa.String(36),
                      sa.ForeignKey("customer_orders.id"),
                      nullable=True),
            sa.Column("machine_id", sa.Integer,
                      sa.ForeignKey("machines.id"),
                      nullable=True, index=True),
            sa.Column("die_id", sa.String(36),
                      sa.ForeignKey("dies.id"), nullable=True),
            sa.Column("billet_id", sa.String(36),
                      sa.ForeignKey("billets.id"), nullable=True),
            sa.Column("scheduled_start", sa.DateTime, nullable=False,
                      index=True),
            sa.Column("scheduled_end", sa.DateTime, nullable=False,
                      index=True),
            sa.Column("sequence_order", sa.Integer, nullable=True),
            sa.Column("is_locked", sa.Boolean, nullable=False,
                      server_default=sa.text("0")),
            sa.Column("lock_reason", sa.String(256), nullable=True),
            sa.Column("locked_by", sa.String(128), nullable=True),
            sa.Column("locked_at", sa.DateTime, nullable=True),
            sa.Column("status", sa.String(32), nullable=False,
                      server_default="PLANNED"),
            sa.Column("constraint_status", sa.String(32), nullable=False,
                      server_default="FEASIBLE"),
            sa.Column("constraint_reasons", sa.JSON, server_default="[]"),
            sa.Column("setup_duration_min", sa.Float, nullable=True),
            sa.Column("changeover_duration_min", sa.Float, nullable=True),
            sa.Column("priority", sa.String(16), nullable=True),
            sa.Column("notes", sa.Text, nullable=True),
            sa.Column("created_at", sa.DateTime,
                      server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime,
                      server_default=sa.func.now()),
        )

    # ── aps_constraint_logs ───────────────────────────────────────────────
    if not _has_table(bind, "aps_constraint_logs"):
        op.create_table(
            "aps_constraint_logs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("version_id", sa.String(36),
                      sa.ForeignKey("aps_schedule_versions.id"),
                      nullable=True, index=True),
            sa.Column("work_order_id", sa.String(36),
                      sa.ForeignKey("work_orders.id"), nullable=True),
            sa.Column("customer_order_id", sa.String(36),
                      sa.ForeignKey("customer_orders.id"), nullable=True),
            sa.Column("entry_id", sa.String(36),
                      sa.ForeignKey("aps_schedule_entries.id"),
                      nullable=True),
            sa.Column("reason_code", sa.String(64), nullable=False),
            sa.Column("message", sa.Text, nullable=False),
            sa.Column("severity", sa.String(16), nullable=False,
                      server_default="WARNING"),
            sa.Column("acknowledged", sa.Boolean,
                      server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime,
                      server_default=sa.func.now()),
        )

    # ── aps_schedule_events ───────────────────────────────────────────────
    if not _has_table(bind, "aps_schedule_events"):
        op.create_table(
            "aps_schedule_events",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("version_id", sa.String(36),
                      sa.ForeignKey("aps_schedule_versions.id"),
                      nullable=False, index=True),
            sa.Column("entry_id", sa.String(36),
                      sa.ForeignKey("aps_schedule_entries.id"),
                      nullable=True, index=True),
            sa.Column("event_type", sa.String(64), nullable=False),
            sa.Column("old_values", sa.JSON, server_default="{}"),
            sa.Column("new_values", sa.JSON, server_default="{}"),
            sa.Column("triggered_by", sa.String(128), nullable=True),
            sa.Column("created_at", sa.DateTime,
                      server_default=sa.func.now()),
        )

    # Stamp alembic_version to this revision. Needed because
    # db.create_all() may have materialised the tables before Alembic
    # ran, leaving alembic_version pointing at d5e170cdceef.
    if not _has_table(bind, "alembic_version"):
        # This shouldn't happen — alembic_version is created by flask-migrate
        # on first run — but guard defensively.
        return

    from sqlalchemy import text
    conn = op.get_bind()
    rows = conn.execute(
        text("SELECT version_num FROM alembic_version LIMIT 1")
    ).fetchall()
    current = rows[0][0] if rows else None
    # Only stamp if not yet at this revision
    if current != revision:
        if not rows:
            conn.execute(
                text(
                    "INSERT INTO alembic_version (version_num) "
                    "VALUES (:v)"
                ),
                {"v": revision},
            )
        else:
            conn.execute(
                text(
                    "UPDATE alembic_version SET version_num = :v "
                    "WHERE version_num = :c"
                ),
                {"v": revision, "c": current},
            )
        conn.commit()


def downgrade():
    bind = op.get_bind()
    from sqlalchemy import text
    for table_name in [
        "aps_schedule_events",
        "aps_constraint_logs",
        "aps_schedule_entries",
        "aps_schedule_versions",
    ]:
        if _has_table(bind, table_name):
            # Drop with IF EXISTS for idempotent rollback
            conn = op.get_bind()
            conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}"'))
            conn.commit()
