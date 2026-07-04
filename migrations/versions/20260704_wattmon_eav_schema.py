"""Wattmon: replace 216-column reading table with Entity-Attribute-Value schema

Revision ID: 20260704_eav
Revises: 20260703_wattmon
Create Date: 2026-07-04

Background
----------
The old ``wattmon_readings`` table had one row per CSV data row, with 216+
TEXT columns for every Wattmon meter field. That schema:
• rejected rows that did not have exactly 216 columns
• required a migration for every header change from the device firmware
• had an unusable UI (horizontal scroll across 216 columns)

The new schema is Entity-Attribute-Value: one row per (device_key,
column_name, value, time-point). A 216-column CSV row expands into 216 rows
sharing the same ``row_index`` and ``epoch_ts``. The pivot is query-time,
not schema-time:

    SELECT column_name, value
      FROM wattmon_readings
     WHERE upload_id = :uid AND epoch_ts = :ts
     ORDER BY column_name

This migration:
  1. Drops ``wattmon_readings`` (destructive — old data lost; CSV backups in
     ``instance/wattmon_uploads/<id>.csv`` still exist on disk).
  2. Recreates it with seven columns plus two composite indexes.

Rollback is supported via ``downgrade()``, which drops the new table and
re-creates the old wide table so ``db.create_all()``-style setups still work.
"""
from alembic import op
import sqlalchemy as sa


revision = '20260704_eav'
down_revision = '20260703_wattmon'
branch_labels = None
depends_on = None


# Columns of the OLD wide table, so downgrade() can recreate it exactly.
# Keeping this inline (rather than importing from the app) means rollback
# works even after the Python WattmonReading model has been rewritten.
_OLD_COLUMNS = {
    "ts": sa.Text,
    "timestamp": sa.Text,
    "m_schneider_540420085805_AC_Active_Power": sa.Text,
    "m_schneider_540420085805_AC_Reactive_Power": sa.Text,
    "m_schneider_540420085805_AC_Apparent_Power": sa.Text,
    "m_schneider_540420085805_kWh_Total_Active": sa.Text,
    "m_schneider_540420085805_kVARh_Total_Active": sa.Text,
    "m_schneider_540420085805_kVAh_Total_Active": sa.Text,
    "m_schneider_540420085805_AC_Current_A": sa.Text,
    "m_schneider_540420085805_AC_Current_B": sa.Text,
    "m_schneider_540420085805_AC_Current_C": sa.Text,
    "m_schneider_540420085805_AC_Voltage_AB": sa.Text,
    "m_schneider_540420085805_AC_Voltage_BC": sa.Text,
    "m_schneider_540420085805_AC_Voltage_CA": sa.Text,
    "m_schneider_540420085805_AC_Voltage_AN": sa.Text,
    "m_schneider_540420085805_AC_Voltage_BN": sa.Text,
    "m_schneider_540420085805_AC_Voltage_CN": sa.Text,
    "m_schneider_540420085805_AC_Active_Power_A": sa.Text,
    "m_schneider_540420085805_AC_Active_Power_B": sa.Text,
    "m_schneider_540420085805_AC_Active_Power_C": sa.Text,
    "m_schneider_540420085805_AC_Reactive_Power_A": sa.Text,
    "m_schneider_540420085805_AC_Reactive_Power_B": sa.Text,
    "m_schneider_540420085805_AC_Reactive_Power_C": sa.Text,
    "m_schneider_540420085805_AC_Apparent_Power_A": sa.Text,
    "m_schneider_540420085805_AC_Apparent_Power_B": sa.Text,
    "m_schneider_540420085805_AC_Apparent_Power_C": sa.Text,
    "m_schneider_540420085805_AC_PF_A": sa.Text,
    "m_schneider_540420085805_AC_PF_B": sa.Text,
    "m_schneider_540420085805_AC_PF_C": sa.Text,
    "m_schneider_540420085805_AC_PF": sa.Text,
    "m_schneider_540420085805_AC_Frequency": sa.Text,
    "m_schneider_540420080451_AC_Active_Power": sa.Text,
    "m_schneider_540420080451_kWh_Total_Active": sa.Text,
}


def _eav_columns():
    """Column definitions for the new EAV reading table."""
    return [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "upload_id",
            sa.Integer(),
            sa.ForeignKey("wattmon_uploads.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("device_key", sa.String(length=128), nullable=True, index=True),
        sa.Column("column_name", sa.String(length=256), nullable=False, index=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("row_index", sa.Integer(), nullable=False, index=True),
        sa.Column("epoch_ts", sa.Integer(), nullable=True, index=True),
    ]


def upgrade():
    conn = op.get_bind()

    # Drop the wide table — destructive but the only sensible action:
    # old rows cannot be un-pivoted reliably without the original CSV header.
    if conn.dialect.has_table(conn, "wattmon_readings"):
        op.drop_table("wattmon_readings")

    op.create_table(
        "wattmon_readings",
        *_eav_columns(),
    )
    op.create_index(
        "ix_wattmon_readings_lookup",
        "wattmon_readings",
        ["device_key", "epoch_ts"],
    )
    op.create_index(
        "ix_wattmon_readings_upload_row",
        "wattmon_readings",
        ["upload_id", "row_index"],
    )


def downgrade():
    """Re-create the old wide table so that downgrading is non-destructive."""
    # We re-create the wide schema so the old Python codebase works again.
    # Any data inserted in the EAV table is lost — restore from
    # instance/wattmon_uploads/ CSV backups if necessary.
    conn = op.get_bind()
    if conn.dialect.has_table(conn, "wattmon_readings"):
        op.drop_table("wattmon_readings")

    columns = [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "upload_id",
            sa.Integer(),
            sa.ForeignKey("wattmon_uploads.id"),
            nullable=False,
            index=True,
        ),
    ]
    for col_name, col_type in _OLD_COLUMNS.items():
        columns.append(sa.Column(col_name, col_type, nullable=True))

    columns.append(
        sa.Column("ts", sa.Text(), nullable=True, index=True)
    )  # was also indexed as (upload_id, ts)
    op.create_table(
        "wattmon_readings",
        *columns,
    )
    op.create_index(
        "ix_wattmon_readings_upload_ts",
        "wattmon_readings",
        ["upload_id", "ts"],
    )
