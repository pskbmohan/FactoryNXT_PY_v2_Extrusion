"""add quality schema - Quality Reporting & Control System

Revision ID: 20260720_add_quality_schema
Revises: 20260715_add_customer_part_bom_wo_fields
Create Date: 2026-07-20

This migration adds all quality-related tables for the Quality Reporting & Control System:
- quality_parameters: Process parameter limits per profile/alloy
- parameter_readings: Real-time PLC parameter capture
- defect_codes: Master list of defect types with categories
- quality_inspections: Unified inspection records across stages
- test_events: Mechanical/NDT test results
- alarm_breakdown_log: Machine alarm and downtime tracking
- process_parameter_alerts: Auto-triggered parameter violations
- spc_records: SPC chart data points
- material_traceability: End-to-end traceability chain

Also extends existing models (Die, KPIRecord) with quality-related fields.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '20260720_add_quality_schema'
down_revision = '20260715_add_customer_part_bom_wo_fields'
branch_labels = None
depends_on = None


def upgrade():
    """Create all quality-related tables and extend existing models."""

    # -------------------------------------------------------------------------
    # 1. Create defect_codes master data table (needed early for FKs)
    # -------------------------------------------------------------------------
    op.create_table(
        'defect_codes',
        sa.Column('id', sa.String(length=36), primary_key=True, default=lambda: str(__import__('uuid').uuid4())),
        sa.Column('code', sa.String(32), nullable=False, unique=True),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('category', sa.Enum('surface', 'functional', 'aesthetic', 'dimensional', name='defect_categories'), nullable=False),
        sa.Column('severity', sa.Enum('minor', 'moderate', 'major', 'critical', name='defect_severity'), default='moderate'),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, default=sa.func.now(), onupdate=sa.func.now())
    )
    op.create_index(op.f('ix_defect_codes_code'), 'defect_codes', ['code'], unique=False)
    op.create_index(op.f('ix_defect_codes_category'), 'defect_codes', ['category'], unique=False)

    # -------------------------------------------------------------------------
    # 2. Create quality_parameters table (process parameter limits per profile/alloy)
    # -------------------------------------------------------------------------
    op.create_table(
        'quality_parameters',
        sa.Column('id', sa.String(length=36), primary_key=True, default=lambda: str(__import__('uuid').uuid4())),
        sa.Column('profile_code', sa.String(128), nullable=False),
        sa.Column('alloy', sa.String(64), nullable=False),
        # Process parameter limits - billet heating
        sa.Column('billet_temp_min', sa.Float, nullable=True),
        sa.Column('billet_temp_max', sa.Float, nullable=True),
        # Container temperature limits
        sa.Column('container_temp_min', sa.Float, nullable=True),
        sa.Column('container_temp_max', sa.Float, nullable=True),
        # Die temperature limits
        sa.Column('die_temp_min', sa.Float, nullable=True),
        sa.Column('die_temp_max', sa.Float, nullable=True),
        # Exit temperature limits
        sa.Column('exit_temp_min', sa.Float, nullable=True),
        sa.Column('exit_temp_max', sa.Float, nullable=True),
        # Ram speed limits (mm/s)
        sa.Column('ram_speed_min', sa.Float, nullable=True),
        sa.Column('ram_speed_max', sa.Float, nullable=True),
        # Main cylinder pressure limits (bar)
        sa.Column('pressure_min', sa.Float, nullable=True),
        sa.Column('pressure_max', sa.Float, nullable=True),
        # Extrusion force limits (kN)
        sa.Column('force_min', sa.Float, nullable=True),
        sa.Column('force_max', sa.Float, nullable=True),
        # Cycle time limits (seconds)
        sa.Column('cycle_time_min', sa.Float, nullable=True),
        sa.Column('cycle_time_max', sa.Float, nullable=True),
        # Metadata
        sa.Column('setpoint_profile_id', sa.String(36), sa.ForeignKey('setpoint_profiles.id'), nullable=True),
        sa.Column('version', sa.Integer, default=1),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, default=sa.func.now(), onupdate=sa.func.now())
    )
    op.create_index(op.f('ix_quality_parameters_profile_code'), 'quality_parameters', ['profile_code'], unique=False)
    op.create_index(op.f('ix_quality_parameters_alloy'), 'quality_parameters', ['alloy'], unique=False)
    op.create_index(op.f('ix_quality_parameters_is_active'), 'quality_parameters', ['is_active'], unique=False)

    # -------------------------------------------------------------------------
    # 3. Create parameter_readings table (real-time PLC capture during extrusion)
    # -------------------------------------------------------------------------
    op.create_table(
        'parameter_readings',
        sa.Column('id', sa.String(length=36), primary_key=True, default=lambda: str(__import__('uuid').uuid4())),
        sa.Column('run_id', sa.String(36), sa.ForeignKey('process_runs.id'), nullable=False),
        sa.Column('timestamp', sa.DateTime, default=sa.func.now(), nullable=False),
        # Process parameter readings from PLC
        sa.Column('billet_temp', sa.Float, nullable=True),
        sa.Column('container_temp', sa.Float, nullable=True),
        sa.Column('die_temp', sa.Float, nullable=True),
        sa.Column('exit_temp', sa.Float, nullable=True),
        sa.Column('ram_speed', sa.Float, nullable=True),
        sa.Column('main_cylinder_pressure', sa.Float, nullable=True),
        sa.Column('extrusion_force', sa.Float, nullable=True),
        sa.Column('cycle_time', sa.Float, nullable=True),
        # Additional sensor readings
        sa.Column('stem_position', sa.Float, nullable=True),
        sa.Column('puller_speed', sa.Float, nullable=True),
        sa.Column('cooling_params', postgresql.JSONB(astext_type=sa.Text()), default=dict),
        # Validation flags
        sa.Column('all_within_limits', sa.Boolean, nullable=True),
        sa.Column('violation_count', sa.Integer, default=0),
        sa.Column('created_at', sa.DateTime, default=sa.func.now())
    )
    op.create_index(op.f('ix_parameter_readings_run_id'), 'parameter_readings', ['run_id'], unique=False)
    op.create_index(op.f('ix_parameter_readings_timestamp'), 'parameter_readings', ['timestamp'], unique=False)
    op.create_index(op.f('ix_parameter_readings_all_within_limits'), 'parameter_readings', ['all_within_limits'], unique=False)

    # -------------------------------------------------------------------------
    # 4. Create quality_inspections table (unified inspection records)
    # -------------------------------------------------------------------------
    op.create_table(
        'quality_inspections',
        sa.Column('id', sa.String(length=36), primary_key=True, default=lambda: str(__import__('uuid').uuid4())),
        sa.Column('inspection_type', sa.Enum('dimensional', 'visual', 'process_parameter', 'first_piece', name='inspection_types'), nullable=False),
        sa.Column('stage', sa.Enum('pre_production', 'in_process', 'post_extrusion', name='inspection_stages'), nullable=False),
        # Link to production entities (nullable for flexibility)
        sa.Column('wo_id', sa.String(36), sa.ForeignKey('work_orders.id'), nullable=True),
        sa.Column('billet_id', sa.String(36), sa.ForeignKey('billets.id'), nullable=True),
        sa.Column('die_id', sa.String(36), sa.ForeignKey('dies.id'), nullable=True),
        sa.Column('run_id', sa.String(36), sa.ForeignKey('process_runs.id'), nullable=True),
        # Operator info
        sa.Column('operator_id', sa.String(64), nullable=True),
        sa.Column('inspector_name', sa.String(128), nullable=True),
        # Inspection results
        sa.Column('timestamp', sa.DateTime, default=sa.func.now(), nullable=False),
        sa.Column('results', postgresql.JSONB(astext_type=sa.Text()), default=dict),
        sa.Column('pass_fail', sa.Enum('PASS', 'FAIL', 'PENDING', name='inspection_pass_fail'), default='PENDING'),
        # Measured values as JSON for flexibility across inspection types
        sa.Column('measured_values', postgresql.JSONB(astext_type=sa.Text()), default=dict),
        # Notes and ERP integration
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('erp_posted', sa.Boolean, default=False),
        sa.Column('erp_posted_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now())
    )
    op.create_index(op.f('ix_quality_inspections_inspection_type'), 'quality_inspections', ['inspection_type'], unique=False)
    op.create_index(op.f('ix_quality_inspections_stage'), 'quality_inspections', ['stage'], unique=False)
    op.create_index(op.f('ix_quality_inspections_wo_id'), 'quality_inspections', ['wo_id'], unique=False)
    op.create_index(op.f('ix_quality_inspections_die_id'), 'quality_inspections', ['die_id'], unique=False)
    op.create_index(op.f('ix_quality_inspections_pass_fail'), 'quality_inspections', ['pass_fail'], unique=False)

    # -------------------------------------------------------------------------
    # 5. Create test_events table (mechanical/NDT testing results)
    # -------------------------------------------------------------------------
    op.create_table(
        'test_events',
        sa.Column('id', sa.String(length=36), primary_key=True, default=lambda: str(__import__('uuid').uuid4())),
        sa.Column('test_type', sa.Enum('webster', 'barcol', 'vickers', 'uts', 'ut', name='test_types'), nullable=False),
        # Link to production/order entities
        sa.Column('wo_id', sa.String(36), sa.ForeignKey('work_orders.id'), nullable=True),
        sa.Column('specimen_id', sa.String(128), nullable=True),  # Specimen identifier from test machine
        # Test results
        sa.Column('result_value', sa.Float, nullable=True),
        sa.Column('acceptance_limit', sa.Float, nullable=True),
        sa.Column('passed', sa.Boolean, nullable=True),
        sa.Column('test_data', postgresql.JSONB(astext_type=sa.Text()), default=dict),  # Full test data dump
        # Tester info and timing
        sa.Column('tested_at', sa.DateTime, default=sa.func.now(), nullable=False),
        sa.Column('tester_id', sa.String(64), nullable=True),
        sa.Column('tester_name', sa.String(128), nullable=True),
        sa.Column('equipment_id', sa.String(64), nullable=True),  # Test machine ID
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now())
    )
    op.create_index(op.f('ix_test_events_test_type'), 'test_events', ['test_type'], unique=False)
    op.create_index(op.f('ix_test_events_wo_id'), 'test_events', ['wo_id'], unique=False)
    op.create_index(op.f('ix_test_events_passed'), 'test_events', ['passed'], unique=False)

    # -------------------------------------------------------------------------
    # 6. Create alarm_breakdown_log table (machine alarm and downtime tracking)
    # -------------------------------------------------------------------------
    op.create_table(
        'alarm_breakdown_log',
        sa.Column('id', sa.String(length=36), primary_key=True, default=lambda: str(__import__('uuid').uuid4())),
        sa.Column('machine_id', sa.String(36), nullable=False),
        sa.Column('alarm_code', sa.String(32), nullable=False),
        sa.Column('alarm_name', sa.String(128), nullable=False),
        # Duration tracking (minutes)
        sa.Column('duration_min', sa.Float, nullable=True),
        # Timing
        sa.Column('started_at', sa.DateTime, default=sa.func.now(), nullable=False),
        sa.Column('ended_at', sa.DateTime, nullable=True),
        # Alarm classification
        sa.Column('is_recurring', sa.Boolean, default=False),
        sa.Column('category', sa.Enum('mechanical', 'electrical', 'hydraulic', 'thermal', 'safety', name='alarm_categories'), nullable=True),
        sa.Column('severity', sa.Enum('info', 'warning', 'critical', name='alarm_severity_levels'), default='warning'),
        # Resolution info (filled when alarm cleared)
        sa.Column('resolved_by', sa.String(64), nullable=True),
        sa.Column('resolution_notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.UniqueConstraint('machine_id', 'alarm_code', 'started_at', name='uq_machine_alarm_start')
    )
    op.create_index(op.f('ix_alarm_breakdown_log_machine_id'), 'alarm_breakdown_log', ['machine_id'], unique=False)
    op.create_index(op.f('ix_alarm_breakdown_log_started_at'), 'alarm_breakdown_log', ['started_at'], unique=False)
    op.create_index(op.f('ix_alarm_breakdown_log_is_recurring'), 'alarm_breakdown_log', ['is_recurring'], unique=False)

    # -------------------------------------------------------------------------
    # 7. Create process_parameter_alerts table (auto-triggered violations)
    # -------------------------------------------------------------------------
    op.create_table(
        'process_parameter_alerts',
        sa.Column('id', sa.String(length=36), primary_key=True, default=lambda: str(__import__('uuid').uuid4())),
        sa.Column('run_id', sa.String(36), sa.ForeignKey('process_runs.id'), nullable=False),
        sa.Column('parameter_name', sa.String(64), nullable=False),  # e.g., 'billet_temp', 'die_temp'
        sa.Column('actual_value', sa.Float, nullable=False),
        sa.Column('threshold_low', sa.Float, nullable=True),  # Lower limit
        sa.Column('threshold_high', sa.Float, nullable=True),  # Upper limit
        sa.Column('triggered_at', sa.DateTime, default=sa.func.now(), nullable=False),
        # Auto-stop behavior
        sa.Column('auto_stop_triggered', sa.Boolean, default=False),
        sa.Column('stop_confirmed_by', sa.String(64), nullable=True),  # Operator who confirmed stop
        sa.Column('violation_type', sa.Enum('low_limit', 'high_limit', name='violation_types'), nullable=False),
        sa.Column('severity', sa.Enum('warning', 'critical', name='alert_severity'), default='warning'),
        sa.Column('status', sa.Enum('active', 'acknowledged', 'resolved', name='alert_status'), default='active'),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now())
    )
    op.create_index(op.f('ix_process_parameter_alerts_run_id'), 'process_parameter_alerts', ['run_id'], unique=False)
    op.create_index(op.f('ix_process_parameter_alerts_status'), 'process_parameter_alerts', ['status'], unique=False)
    op.create_index(op.f('ix_process_parameter_alerts_auto_stop_triggered'), 'process_parameter_alerts', ['auto_stop_triggered'], unique=False)

    # -------------------------------------------------------------------------
    # 8. Create spc_records table (SPC chart data points with shift grouping)
    # -------------------------------------------------------------------------
    op.create_table(
        'spc_records',
        sa.Column('id', sa.String(length=36), primary_key=True, default=lambda: str(__import__('uuid').uuid4())),
        sa.Column('wo_id', sa.String(36), sa.ForeignKey('work_orders.id'), nullable=False),
        # Dimension type being tracked (e.g., 'OD', 'ID', 'thickness')
        sa.Column('dimension_type', sa.String(64), nullable=False),
        sa.Column('target_value', sa.Float, nullable=False),  # Nominal/target dimension
        sa.Column('measured_value', sa.Float, nullable=False),  # Actual measurement
        # Control limits (calculated or specified)
        sa.Column('upper_limit', sa.Float, nullable=True),  # UCL/UML
        sa.Column('lower_limit', sa.Float, nullable=True),  # LCL/LML
        # Shift grouping for X-bar charts
        sa.Column('sample_number', sa.Integer, nullable=False),
        sa.Column('shift_group', sa.String(32), nullable=False),  # e.g., 'morning', 'afternoon', 'night'
        # Timing and operator info
        sa.Column('sample_time', sa.DateTime, default=sa.func.now(), nullable=False),
        sa.Column('operator_id', sa.String(64), nullable=True),
        sa.Column('inspector_name', sa.String(128), nullable=True),
        # SPC status flags
        sa.Column('out_of_control', sa.Boolean, default=False),
        sa.Column('trend_direction', sa.Enum('up', 'down', 'stable', name='trend_directions'), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now())
    )
    op.create_index(op.f('ix_spc_records_wo_id'), 'spc_records', ['wo_id'], unique=False)
    op.create_index(op.f('ix_spc_records_dimension_type'), 'spc_records', ['dimension_type'], unique=False)
    op.create_index(op.f('ix_spc_records_shift_group'), 'spc_records', ['shift_group'], unique=False)
    op.create_index(op.f('ix_spc_records_out_of_control'), 'spc_records', ['out_of_control'], unique=False)

    # -------------------------------------------------------------------------
    # 9. Create material_traceability table (end-to-end traceability chain)
    # -------------------------------------------------------------------------
    op.create_table(
        'material_traceability',
        sa.Column('id', sa.String(length=36), primary_key=True, default=lambda: str(__import__('uuid').uuid4())),
        # Traceability identifiers
        sa.Column('batch_number', sa.String(64), nullable=False),  # Production batch ID
        sa.Column('heat_number', sa.String(64), nullable=True),    # Heat/lots number from foundry
        sa.Column('billet_code', sa.String(64), nullable=True),
        sa.Column('die_code', sa.String(64), nullable=True),
        sa.Column('work_order_id', sa.String(36), sa.ForeignKey('work_orders.id'), nullable=False),
        # Timestamps and operator info
        sa.Column('extrusion_timestamp', sa.DateTime, default=sa.func.now(), nullable=False),
        sa.Column('operator_id', sa.String(64), nullable=True),
        # Process parameters snapshot (JSON for flexibility)
        sa.Column('process_params', postgresql.JSONB(astext_type=sa.Text()), default=dict),
        # Customer order linkage for forward traceability
        sa.Column('customer_order_line_id', sa.String(36), nullable=True),
        sa.Column('shipment_batch_id', sa.String(64), nullable=True),  # For customer shipments
        # Status tracking
        sa.Column('status', sa.Enum('in_production', 'completed', 'shipped', 'returned', name='traceability_status'), default='in_production'),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now())
    )
    op.create_index(op.f('ix_material_traceability_batch_number'), 'material_traceability', ['batch_number'], unique=False)
    op.create_index(op.f('ix_material_traceability_work_order_id'), 'material_traceability', ['work_order_id'], unique=False)
    op.create_index(op.f('ix_material_traceability_heat_number'), 'material_traceability', ['heat_number'], unique=False)

    # -------------------------------------------------------------------------
    # 10. Extend Die model with quality-related columns via ALTER TABLE
    # -------------------------------------------------------------------------
    # Add computed/calculated fields for die lifecycle tracking
    op.add_column('dies', sa.Column('die_life_cycles_remaining', sa.Integer, nullable=True))
    op.add_column('dies', sa.Column('last_failure_reason', sa.Text, nullable=True))
    op.add_column('dies', sa.Column('total_setup_time_minutes', sa.Float, default=0.0))
    op.add_column('dies', sa.Column('average_setup_time_minutes', sa.Float, nullable=True))

    # -------------------------------------------------------------------------
    # 11. Extend KPIRecord model with new quality KPI types
    # -------------------------------------------------------------------------
    # Add new kpi_type values: FPY, PPM, COPQ, ENERGY_CONSUMPTION
    op.execute("ALTER TYPE kpi_types ADD VALUE IF NOT EXISTS 'FPY'")
    op.execute("ALTER TYPE kpi_types ADD VALUE IF NOT EXISTS 'PPM'")
    op.execute("ALTER TYPE kpi_types ADD VALUE IF NOT EXISTS 'COPQ'")
    op.execute("ALTER TYPE kpi_types ADD VALUE IF NOT EXISTS 'ENERGY_CONSUMPTION'")

    # -------------------------------------------------------------------------
    # 12. Create additional indexes for performance
    # -------------------------------------------------------------------------
    # Composite index for quality_inspections (common query pattern)
    op.create_index(
        'ix_quality_inspections_wo_die_timestamp',
        'quality_inspections',
        ['wo_id', 'die_id', 'timestamp']
    )

    # Composite index for parameter_readings (time-series queries)
    op.create_index(
        'ix_parameter_readings_run_timestamp',
        'parameter_readings',
        ['run_id', 'timestamp']
    )


def downgrade():
    """Drop all quality-related tables and revert extensions."""

    # Drop indexes first
    op.drop_index('ix_quality_inspections_wo_die_timestamp', table_name='quality_inspections')
    op.drop_index('ix_parameter_readings_run_timestamp', table_name='parameter_readings')

    # Drop tables in reverse order of creation (respecting FKs)
    op.drop_table('material_traceability')
    op.drop_table('spc_records')
    op.drop_table('process_parameter_alerts')
    op.drop_table('alarm_breakdown_log')
    op.drop_table('test_events')
    op.drop_table('quality_inspections')
    op.drop_table('parameter_readings')
    op.drop_table('quality_parameters')
    op.drop_table('defect_codes')

    # Revert Die model extensions
    op.drop_column('dies', 'average_setup_time_minutes')
    op.drop_column('dies', 'total_setup_time_minutes')
    op.drop_column('dies', 'last_failure_reason')
    op.drop_column('dies', 'die_life_cycles_remaining')

    # Note: Cannot easily revert KPIRecord enum additions in downgrade
    # These would need manual intervention or keeping the new values


# Seed data insertion function (run after migration via separate script or manually)
def insert_default_defect_codes():
    """Insert default defect codes for immediate use."""
    default_codes = [
        {'code': 'DS001', 'name': 'Surface Scratches', 'category': 'surface', 'severity': 'minor', 'description': 'Minor surface scratches from handling'},
        {'code': 'DS002', 'name': 'Die Lines', 'category': 'surface', 'severity': 'moderate', 'description': 'Longitudinal lines from die wear'},
        {'code': 'DW001', 'name': 'Dimensional Out of Tolerance', 'category': 'dimensional', 'severity': 'major', 'description': 'Dimensions outside specified tolerance'},
        {'code': 'FW001', 'name': 'Incomplete Fill', 'category': 'functional', 'severity': 'critical', 'description': 'Profile not fully formed'},
        {'code': 'AW001', 'name': 'Color Variation', 'category': 'aesthetic', 'severity': 'minor', 'description': 'Visible color difference from standard'},
    ]
    return default_codes
