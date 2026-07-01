"""foundry domain consolidation

Revision ID: 8b1c2d3e4f5g
Revises: 7a42c1b9e2d5
Create Date: 2026-06-30 00:00:00.000000

Adds all tables for the aluminum extrusion foundry domain while
preserving the existing SMT/PCB tables intact.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8b1c2d3e4f5g'
down_revision = '7a42c1b9e2d5'
branch_labels = None
depends_on = None


def upgrade():
    # ── CustomerOrder ─────────────────────────────────────────────────────
    op.create_table(
        'customer_orders',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('order_number', sa.String(length=64), nullable=False),
        sa.Column('customer_name', sa.String(length=128), nullable=False),
        sa.Column('product_profile', sa.String(length=128), nullable=True),
        sa.Column('alloy', sa.String(length=64), nullable=True),
        sa.Column('quantity_tons', sa.Float(), nullable=True),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('erp_reference', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('order_number'),
    )

    # ── ProcessPlan ───────────────────────────────────────────────────────
    op.create_table(
        'process_plans',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('order_id', sa.String(length=36), nullable=True),
        sa.Column('plan_number', sa.String(length=64), nullable=False),
        sa.Column('alloy', sa.String(length=64), nullable=True),
        sa.Column('profile_shape', sa.String(length=128), nullable=True),
        sa.Column('scheduled_start', sa.DateTime(), nullable=True),
        sa.Column('scheduled_end', sa.DateTime(), nullable=True),
        sa.Column('actual_start', sa.DateTime(), nullable=True),
        sa.Column('actual_end', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('priority', sa.String(length=16), nullable=True),
        sa.Column('created_by', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('plan_number'),
        sa.ForeignKeyConstraint(['order_id'], ['customer_orders.id']),
    )

    # ── Die ───────────────────────────────────────────────────────────────
    op.create_table(
        'dies',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('die_code', sa.String(length=64), nullable=False),
        sa.Column('profile_code', sa.String(length=64), nullable=True),
        sa.Column('alloy', sa.String(length=64), nullable=True),
        sa.Column('supplier', sa.String(length=128), nullable=True),
        sa.Column('location', sa.String(length=128), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('life_cycles_total', sa.Integer(), nullable=False),
        sa.Column('last_inspected_at', sa.DateTime(), nullable=True),
        sa.Column('last_tested_at', sa.DateTime(), nullable=True),
        sa.Column('last_nitrided_at', sa.DateTime(), nullable=True),
        sa.Column('erp_asset_id', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('die_code'),
    )

    # ── DieInspection ─────────────────────────────────────────────────────
    op.create_table(
        'die_inspections',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('die_id', sa.String(length=36), nullable=False),
        sa.Column('inspection_date', sa.Date(), nullable=False),
        sa.Column('inspector', sa.String(length=128), nullable=True),
        sa.Column('dimensions_ok', sa.Boolean(), nullable=True),
        sa.Column('surface_ok', sa.Boolean(), nullable=True),
        sa.Column('hardness', sa.Float(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('erp_posted', sa.Boolean(), nullable=False),
        sa.Column('erp_posted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['die_id'], ['dies.id']),
    )

    # ── DieTest ───────────────────────────────────────────────────────────
    op.create_table(
        'die_tests',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('die_id', sa.String(length=36), nullable=False),
        sa.Column('test_date', sa.Date(), nullable=False),
        sa.Column('tester', sa.String(length=128), nullable=True),
        sa.Column('press_force', sa.Float(), nullable=True),
        sa.Column('temperature', sa.Float(), nullable=True),
        sa.Column('profile_quality', sa.String(length=32), nullable=True),
        sa.Column('result', sa.String(length=16), nullable=True),
        sa.Column('erp_posted', sa.Boolean(), nullable=False),
        sa.Column('erp_posted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['die_id'], ['dies.id']),
    )

    # ── NitridingRecord ───────────────────────────────────────────────────
    op.create_table(
        'nitriding_records',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('die_id', sa.String(length=36), nullable=False),
        sa.Column('furnace_id', sa.String(length=64), nullable=True),
        sa.Column('start_temp', sa.Float(), nullable=True),
        sa.Column('end_temp', sa.Float(), nullable=True),
        sa.Column('duration_hours', sa.Float(), nullable=True),
        sa.Column('atmosphere', sa.String(length=64), nullable=True),
        sa.Column('hardness_before', sa.Float(), nullable=True),
        sa.Column('hardness_after', sa.Float(), nullable=True),
        sa.Column('operator', sa.String(length=128), nullable=True),
        sa.Column('erp_posted', sa.Boolean(), nullable=False),
        sa.Column('erp_posted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['die_id'], ['dies.id']),
    )

    # ── Billet ────────────────────────────────────────────────────────────
    op.create_table(
        'billets',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('billet_code', sa.String(length=64), nullable=False),
        sa.Column('alloy', sa.String(length=64), nullable=True),
        sa.Column('diameter_mm', sa.Float(), nullable=True),
        sa.Column('length_mm', sa.Float(), nullable=True),
        sa.Column('supplier', sa.String(length=128), nullable=True),
        sa.Column('lot_number', sa.String(length=64), nullable=True),
        sa.Column('quantity_kg', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('billet_code'),
    )

    # ── BilletInspection ──────────────────────────────────────────────────
    op.create_table(
        'billet_inspections',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('billet_id', sa.String(length=36), nullable=False),
        sa.Column('inspection_date', sa.Date(), nullable=False),
        sa.Column('inspector', sa.String(length=128), nullable=True),
        sa.Column('chemical_composition', sa.JSON(), nullable=True),
        sa.Column('temperature', sa.Float(), nullable=True),
        sa.Column('result', sa.String(length=16), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['billet_id'], ['billets.id']),
    )

    # ── MaterialGrade ─────────────────────────────────────────────────────
    op.create_table(
        'material_grades',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('code', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('alloy_family', sa.String(length=64), nullable=True),
        sa.Column('density', sa.Float(), nullable=True),
        sa.Column('melting_point', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )

    # ── SetpointProfile ───────────────────────────────────────────────────
    op.create_table(
        'setpoint_profiles',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('process_type', sa.String(length=32), nullable=False),
        sa.Column('alloy', sa.String(length=64), nullable=True),
        sa.Column('profile_code', sa.String(length=128), nullable=True),
        sa.Column('parameters', sa.JSON(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── ProcessRun ────────────────────────────────────────────────────────
    op.create_table(
        'process_runs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('process_type', sa.String(length=32), nullable=False),
        sa.Column('plan_id', sa.String(length=36), nullable=True),
        sa.Column('machine_id', sa.String(length=36), nullable=True),
        sa.Column('operator_id', sa.String(length=64), nullable=True),
        sa.Column('setpoint_profile_id', sa.String(length=36), nullable=True),
        sa.Column('billet_id', sa.String(length=36), nullable=True),
        sa.Column('die_id', sa.String(length=36), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['plan_id'], ['process_plans.id']),
        sa.ForeignKeyConstraint(['setpoint_profile_id'], ['setpoint_profiles.id']),
        sa.ForeignKeyConstraint(['billet_id'], ['billets.id']),
        sa.ForeignKeyConstraint(['die_id'], ['dies.id']),
    )

    # ── QuenchRecord ──────────────────────────────────────────────────────
    op.create_table(
        'quench_records',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('run_id', sa.String(length=36), nullable=False),
        sa.Column('quench_type', sa.String(length=32), nullable=True),
        sa.Column('sensor_temperatures', sa.JSON(), nullable=True),
        sa.Column('start_time', sa.DateTime(), nullable=True),
        sa.Column('end_time', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['run_id'], ['process_runs.id']),
    )

    # ── CutRecord ─────────────────────────────────────────────────────────
    op.create_table(
        'cut_records',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('run_id', sa.String(length=36), nullable=False),
        sa.Column('target_length_mm', sa.Float(), nullable=True),
        sa.Column('actual_length_mm', sa.Float(), nullable=True),
        sa.Column('cut_method', sa.String(length=16), nullable=True),
        sa.Column('sensor_data', sa.JSON(), nullable=True),
        sa.Column('segregation_status', sa.String(length=32), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['run_id'], ['process_runs.id']),
    )

    # ── StretchRecord ─────────────────────────────────────────────────────
    op.create_table(
        'stretch_records',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('run_id', sa.String(length=36), nullable=False),
        sa.Column('tension_actual', sa.Float(), nullable=True),
        sa.Column('tension_setpoint', sa.Float(), nullable=True),
        sa.Column('position_transducer_reading', sa.Float(), nullable=True),
        sa.Column('pressure_transducer_reading', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['run_id'], ['process_runs.id']),
    )

    # ── OvenRecord ────────────────────────────────────────────────────────
    op.create_table(
        'oven_records',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('run_id', sa.String(length=36), nullable=False),
        sa.Column('oven_id', sa.String(length=64), nullable=True),
        sa.Column('set_temperature', sa.Float(), nullable=True),
        sa.Column('actual_temperature', sa.Float(), nullable=True),
        sa.Column('soak_time_minutes', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['run_id'], ['process_runs.id']),
    )

    # ── AlertRule ─────────────────────────────────────────────────────────
    op.create_table(
        'alert_rules',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('metric', sa.String(length=64), nullable=False),
        sa.Column('operator', sa.String(length=16), nullable=False),
        sa.Column('threshold_value', sa.JSON(), nullable=True),
        sa.Column('severity', sa.String(length=16), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── Alert ─────────────────────────────────────────────────────────────
    op.create_table(
        'alerts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('rule_id', sa.String(length=36), nullable=True),
        sa.Column('severity', sa.String(length=16), nullable=False),
        sa.Column('title', sa.String(length=256), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('source', sa.String(length=32), nullable=False),
        sa.Column('source_id', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('acknowledged_by', sa.String(length=128), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['rule_id'], ['alert_rules.id']),
    )

    # ── KPIRecord ─────────────────────────────────────────────────────────
    op.create_table(
        'kpi_records',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('kpi_type', sa.String(length=32), nullable=False),
        sa.Column('machine_id', sa.String(length=36), nullable=True),
        sa.Column('shift_date', sa.Date(), nullable=True),
        sa.Column('value', sa.Float(), nullable=True),
        sa.Column('unit', sa.String(length=32), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('calculated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── IntegrationJob ────────────────────────────────────────────────────
    op.create_table(
        'integration_jobs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('job_type', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('retries', sa.Integer(), nullable=False),
        sa.Column('max_retries', sa.Integer(), nullable=False),
        sa.Column('next_retry_at', sa.DateTime(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── ERPTransactionLog ─────────────────────────────────────────────────
    op.create_table(
        'erp_transaction_logs',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('direction', sa.String(length=16), nullable=False),
        sa.Column('entity_type', sa.String(length=64), nullable=False),
        sa.Column('entity_id', sa.String(length=64), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('erp_response', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── PLCSignalMapping ──────────────────────────────────────────────────
    op.create_table(
        'plc_signal_mappings',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('machine_name', sa.String(length=128), nullable=False),
        sa.Column('signal_tag', sa.String(length=256), nullable=False),
        sa.Column('signal_type', sa.String(length=16), nullable=False),
        sa.Column('unit', sa.String(length=32), nullable=True),
        sa.Column('process_type', sa.String(length=32), nullable=True),
        sa.Column('scale_factor', sa.Float(), nullable=False),
        sa.Column('offset', sa.Float(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── TraceabilityRecord ────────────────────────────────────────────────
    op.create_table(
        'traceability_records',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('entity_type', sa.String(length=32), nullable=False),
        sa.Column('entity_id', sa.String(length=64), nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('operator_id', sa.String(length=64), nullable=True),
        sa.Column('machine_id', sa.String(length=64), nullable=True),
        sa.Column('data', sa.JSON(), nullable=True),
        sa.Column('occurred_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('traceability_records')
    op.drop_table('plc_signal_mappings')
    op.drop_table('erp_transaction_logs')
    op.drop_table('integration_jobs')
    op.drop_table('kpi_records')
    op.drop_table('alerts')
    op.drop_table('alert_rules')
    op.drop_table('oven_records')
    op.drop_table('stretch_records')
    op.drop_table('cut_records')
    op.drop_table('quench_records')
    op.drop_table('process_runs')
    op.drop_table('setpoint_profiles')
    op.drop_table('material_grades')
    op.drop_table('billet_inspections')
    op.drop_table('billets')
    op.drop_table('nitriding_records')
    op.drop_table('die_tests')
    op.drop_table('die_inspections')
    op.drop_table('dies')
    op.drop_table('process_plans')
    op.drop_table('customer_orders')
