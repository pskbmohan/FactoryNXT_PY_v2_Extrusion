from . import db
from datetime import datetime
from sqlalchemy.dialects.postgresql import ENUM


class Line(db.Model):
    __tablename__ = "lines"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    status = db.Column(db.String(32), nullable=False)


class Machine(db.Model):
    __tablename__ = "machines"
    id = db.Column(db.Integer, primary_key=True)
    line_id = db.Column(db.Integer, db.ForeignKey("lines.id"), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="Idle")
    # is_active: soft-delete / enable-disable flag used by templates and queries
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    line = db.relationship("Line", backref="machines")


class Alarm(db.Model):
    __tablename__ = "alarms"
    id = db.Column(db.Integer, primary_key=True)
    machine_id = db.Column(db.Integer, db.ForeignKey("machines.id"), nullable=False)
    severity = db.Column(db.String(16), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)

    machine = db.relationship("Machine", backref="alarms")


class Station(db.Model):
    """Workstation/Station used in routing and operation execution."""
    __tablename__ = "stations"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, unique=True)
    code = db.Column(db.String(64), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class WorkOrder(db.Model):
    __tablename__ = "work_orders"
    id = db.Column(db.String(36), primary_key=True)
    order_number = db.Column(db.String(64), nullable=False, unique=True)
    part_number = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text, nullable=True)
    quantity = db.Column(db.Integer, nullable=False)
    # Status lifecycle: DRAFT -> RELEASED -> RUNNING -> COMPLETED | CANCELLED
    status = db.Column(db.String(32), nullable=False, default="DRAFT")
    due_date = db.Column(db.DateTime, nullable=True)
    # Canonical schedule window used by the Gantt board.
    # Editing a WO from the Gantt (drag/resize) updates these columns and
    # forces status back to DRAFT so the planner can re-release.
    scheduled_start = db.Column(db.DateTime, nullable=True)
    scheduled_end = db.Column(db.DateTime, nullable=True)
    priority = db.Column(db.String(16), nullable=True)
    # Lifecycle timestamps
    released_at = db.Column(db.DateTime, nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    # ── BOM-driven Work Order fields (Session 1 addition) ───────────────────
    customer_order_line_id = db.Column(db.String(36), db.ForeignKey("customer_order_lines.id"), nullable=True)
    part_number_id = db.Column(db.String(36), db.ForeignKey("part_numbers.id"), nullable=True)
    die_type_id = db.Column(db.String(36), db.ForeignKey("dies.id"), nullable=True)
    billet_type_id = db.Column(db.String(36), db.ForeignKey("billets.id"), nullable=True)
    bom_version_id = db.Column(db.String(36), db.ForeignKey("part_number_boms.id"), nullable=True)
    customer_order_line = db.relationship("CustomerOrderLine", backref="work_orders", foreign_keys=[customer_order_line_id])
    part_number_ref = db.relationship("PartNumber", backref="work_orders", foreign_keys=[part_number_id])
    die_type_ref = db.relationship("Die", backref="work_orders", foreign_keys=[die_type_id])
    billet_type_ref = db.relationship("Billet", backref="work_orders", foreign_keys=[billet_type_id])
    bom_ref = db.relationship("PartNumberBOM", backref="work_orders", foreign_keys=[bom_version_id])


class BOMItem(db.Model):
    __tablename__ = "bom_items"
    id = db.Column(db.Integer, primary_key=True)
    part_number = db.Column(db.String(64), nullable=False, index=True)
    component_part_number = db.Column(db.String(64), nullable=False)
    quantity_per_unit = db.Column(db.Float, nullable=False)
    designator = db.Column(db.String(128), nullable=True)
    revision = db.Column(db.String(8), nullable=True)


class RoutingStep(db.Model):
    __tablename__ = "routing_steps"
    id = db.Column(db.Integer, primary_key=True)
    part_number = db.Column(db.String(64), nullable=False, index=True)
    operation_sequence = db.Column(db.Integer, nullable=False)
    operation_name = db.Column(db.String(128), nullable=False)
    workstation_type = db.Column(db.String(64), nullable=True)
    standard_cycle_time_sec = db.Column(db.Float, nullable=False)
    # Link to Station by name for routing enforcement
    station_name = db.Column(db.String(128), db.ForeignKey("stations.name"), nullable=True)

    station = db.relationship("Station", backref="routing_steps")


class SerialNumber(db.Model):
    """Serial numbers generated when a Work Order is released."""
    __tablename__ = "serial_numbers"
    id = db.Column(db.Integer, primary_key=True)
    work_order_id = db.Column(db.String(36), db.ForeignKey("work_orders.id"), nullable=False)
    serial_number = db.Column(db.String(128), nullable=False, unique=True)
    current_step = db.Column(db.Integer, nullable=True)  # current routing step sequence
    current_status = db.Column(db.String(32), nullable=False, default="PENDING")  # PENDING, IN_PROGRESS, COMPLETED, REJECTED
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    work_order = db.relationship("WorkOrder", backref="serial_numbers")


class OperationTransaction(db.Model):
    """Full audit trail of every operation performed against a serial number."""
    __tablename__ = "operation_transactions"
    id = db.Column(db.Integer, primary_key=True)
    work_order_id = db.Column(db.String(36), db.ForeignKey("work_orders.id"), nullable=False)
    serial_number = db.Column(db.String(128), nullable=False)
    routing_step = db.Column(db.Integer, nullable=False)  # operation_sequence of the step
    station_id = db.Column(db.Integer, db.ForeignKey("stations.id"), nullable=True)
    operator_id = db.Column(db.String(128), nullable=False)
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    result = db.Column(db.String(8), nullable=True)  # OK | NG
    remarks = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    work_order = db.relationship("WorkOrder", backref="operation_transactions")
    station = db.relationship("Station", backref="operation_transactions")


class NCR(db.Model):
    __tablename__ = "ncrs"
    id = db.Column(db.String(36), primary_key=True)
    defect_id = db.Column(db.String(36), nullable=True)
    work_order_id = db.Column(db.String(36), db.ForeignKey("work_orders.id"), nullable=True)
    description = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(16), nullable=False, default="Minor")
    status = db.Column(db.String(16), nullable=False, default="Open")
    created_at = db.Column(db.DateTime, nullable=False)
    resolved_at = db.Column(db.DateTime, nullable=True)
    quarantine_location = db.Column(db.String(128), nullable=True)
    disposition_details = db.Column(db.Text, nullable=True)
    dispositioned_by = db.Column(db.String(128), nullable=True)

    work_order = db.relationship("WorkOrder", backref="ncrs")


class InventoryLocation(db.Model):
    __tablename__ = "inventory_locations"
    id = db.Column(db.String, primary_key=True)  # uuid as text
    plant_id = db.Column(db.String, nullable=False)
    code = db.Column(db.String, unique=True, nullable=False)
    name = db.Column(db.String, nullable=False)
    type = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class InventoryItem(db.Model):
    __tablename__ = "inventory_items"
    id = db.Column(db.String, primary_key=True)  # uuid as text
    part_number = db.Column(db.String, nullable=False)
    description = db.Column(db.Text)
    uom = db.Column(db.String, default="EA")
    quantity_on_hand = db.Column(db.Float, default=0)
    quantity_reserved = db.Column(db.Float, default=0)
    location_id = db.Column(db.String, db.ForeignKey("inventory_locations.id"))
    lot_number = db.Column(db.String)
    is_rohs = db.Column(db.Boolean, default=True)
    is_reach = db.Column(db.Boolean, default=True)
    msd_level = db.Column(db.String)
    shelf_life_days = db.Column(db.Integer)
    expiry_date = db.Column(db.Date)
    floor_life_hours = db.Column(db.Float)
    floor_life_start = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    location = db.relationship("InventoryLocation", backref="items")


class Kit(db.Model):
    __tablename__ = "kits"
    id = db.Column(db.String, primary_key=True)  # uuid
    wo_id = db.Column(db.String, db.ForeignKey("work_orders.id"), unique=True, nullable=False)
    status = db.Column(db.String, default="pending")
    kit_lines = db.Column(db.JSON, default=list)
    picked_by = db.Column(db.String)
    verified_by = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    work_order = db.relationship("WorkOrder", backref="kit")


class FeederReel(db.Model):
    __tablename__ = "feeder_reels"
    id = db.Column(db.String, primary_key=True)  # uuid
    reel_id = db.Column(db.String, unique=True, nullable=False)
    part_number = db.Column(db.String, nullable=False)
    quantity_initial = db.Column(db.Integer, nullable=False)
    quantity_remaining = db.Column(db.Integer, nullable=False)
    feeder_slot = db.Column(db.String)
    machine_id = db.Column(db.String)
    wo_id = db.Column(db.String, db.ForeignKey("work_orders.id"))
    is_spliced = db.Column(db.Boolean, default=False)
    splice_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SolderPasteLot(db.Model):
    __tablename__ = "solder_paste_lots"
    id = db.Column(db.String, primary_key=True)  # uuid
    lot_number = db.Column(db.String, unique=True, nullable=False)
    manufacturer = db.Column(db.String, nullable=False)
    part_number = db.Column(db.String, nullable=False)
    quantity_g = db.Column(db.Float, nullable=False)
    expiry_date = db.Column(db.Date, nullable=False)
    opened_at = db.Column(db.DateTime)
    floor_life_hours = db.Column(db.Float, default=8)
    must_discard_by = db.Column(db.DateTime)
    status = db.Column(db.String, default="sealed")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SmtLine(db.Model):
    __tablename__ = "smt_lines"
    id = db.Column(db.String, primary_key=True)  # uuid
    plant_id = db.Column(db.String, nullable=False)
    name = db.Column(db.String, nullable=False)
    code = db.Column(db.String, unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ProductionSchedule(db.Model):
    __tablename__ = "production_schedule"
    id = db.Column(db.String, primary_key=True)  # uuid
    plant_id = db.Column(db.String, nullable=False)
    wo_id = db.Column(db.String, db.ForeignKey("work_orders.id"), nullable=False)
    smt_line_id = db.Column(db.String, db.ForeignKey("smt_lines.id"))
    scheduled_start = db.Column(db.DateTime, nullable=False)
    scheduled_end = db.Column(db.DateTime, nullable=False)
    actual_start = db.Column(db.DateTime)
    actual_end = db.Column(db.DateTime)
    sequence_order = db.Column(db.Integer)
    is_locked = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    work_order = db.relationship("WorkOrder", backref="schedule_entries")
    smt_line = db.relationship("SmtLine", backref="schedule_entries")


class ShiftCalendar(db.Model):
    __tablename__ = "shift_calendars"
    id = db.Column(db.String, primary_key=True)  # uuid
    plant_id = db.Column(db.String, nullable=False)
    shift_name = db.Column(db.String, nullable=False)
    day_of_week = db.Column(db.Integer)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    is_active = db.Column(db.Boolean, default=True)


class OeeSnapshot(db.Model):
    __tablename__ = "oee_snapshots"
    id = db.Column(db.BigInteger, primary_key=True)
    machine_id = db.Column(db.String)
    smt_line_id = db.Column(db.String, db.ForeignKey("smt_lines.id"))
    shift_date = db.Column(db.Date, nullable=False)
    shift_name = db.Column(db.String, nullable=False)
    planned_production_time_min = db.Column(db.Float, nullable=False)
    downtime_min = db.Column(db.Float, default=0)
    speed_loss_min = db.Column(db.Float, default=0)
    defect_loss_min = db.Column(db.Float, default=0)
    availability = db.Column(db.Float)
    performance = db.Column(db.Float)
    quality = db.Column(db.Float)
    oee = db.Column(db.Float)
    units_planned = db.Column(db.Integer)
    units_produced = db.Column(db.Integer)
    units_defective = db.Column(db.Integer)
    calculated_at = db.Column(db.DateTime, default=datetime.utcnow)

    smt_line = db.relationship("SmtLine", backref="oee_snapshots")


class DowntimeEvent(db.Model):
    __tablename__ = "downtime_events"
    id = db.Column(db.String, primary_key=True)  # uuid
    machine_id = db.Column(db.String, nullable=False)
    reason_code = db.Column(db.String, nullable=False)
    reason_category = db.Column(db.String)
    started_at = db.Column(db.DateTime, nullable=False)
    ended_at = db.Column(db.DateTime)
    duration_min = db.Column(db.Float)
    notes = db.Column(db.Text)
    reported_by = db.Column(db.String)


class PcbPanel(db.Model):
    __tablename__ = "pcb_panels"
    id = db.Column(db.String, primary_key=True)  # uuid
    wo_id = db.Column(db.String, db.ForeignKey("work_orders.id"), nullable=False)
    panel_serial = db.Column(db.String, unique=True, nullable=False)
    board_count = db.Column(db.Integer, nullable=False, default=4)
    status = db.Column(db.String, default="In-Assembly")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    work_order = db.relationship("WorkOrder", backref="panels")


class PcbBoard(db.Model):
    __tablename__ = "pcb_boards"
    id = db.Column(db.String, primary_key=True)  # uuid
    panel_id = db.Column(db.String, db.ForeignKey("pcb_panels.id"))
    wo_id = db.Column(db.String, db.ForeignKey("work_orders.id"), nullable=False)
    serial_number = db.Column(db.String, unique=True, nullable=False)
    status = db.Column(db.String, default="in_progress")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    panel = db.relationship("PcbPanel", backref="boards")
    work_order = db.relationship("WorkOrder", backref="boards")


class UnitHistory(db.Model):
    __tablename__ = "unit_history"
    id = db.Column(db.String, primary_key=True)  # uuid
    board_id = db.Column(db.String, db.ForeignKey("pcb_boards.id"))
    operation_name = db.Column(db.String, nullable=False)
    status = db.Column(db.String, nullable=False)
    machine_id = db.Column(db.String)
    process_parameters = db.Column(db.JSON, default={})
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    board = db.relationship("PcbBoard", backref="history")


class GenealogyEvent(db.Model):
    __tablename__ = "genealogy_events"
    id = db.Column(db.BigInteger, primary_key=True)
    # nullable: extrusion-chain events (billet/die/profile) may not link to a PCB/board or WO
    board_id = db.Column(db.String, db.ForeignKey("pcb_boards.id"), nullable=True)
    wo_id = db.Column(db.String, db.ForeignKey("work_orders.id"), nullable=True)
    event_type = db.Column(db.String, nullable=False)
    machine_id = db.Column(db.String)
    operator_id = db.Column(db.String)
    reel_id = db.Column(db.String)
    feeder_slot = db.Column(db.String)
    reference_designator = db.Column(db.String)
    part_number = db.Column(db.String)
    lot_number = db.Column(db.String)
    data = db.Column(db.JSON, default={})
    occurred_at = db.Column(db.DateTime, default=datetime.utcnow)

    board = db.relationship("PcbBoard", backref="genealogy_events")
    work_order = db.relationship("WorkOrder", backref="genealogy_events")


class RepairRecord(db.Model):
    __tablename__ = "repair_records"
    id = db.Column(db.String, primary_key=True)  # uuid
    board_id = db.Column(db.String, db.ForeignKey("pcb_boards.id"), nullable=False)
    wo_id = db.Column(db.String, db.ForeignKey("work_orders.id"), nullable=False)
    ncr_id = db.Column(db.String, db.ForeignKey("ncrs.id"))
    reference_designator = db.Column(db.String, nullable=False)
    removed_part_number = db.Column(db.String, nullable=False)
    removed_lot = db.Column(db.String)
    installed_part_number = db.Column(db.String, nullable=False)
    installed_lot = db.Column(db.String)
    reason_code = db.Column(db.String, nullable=False)
    operator_id = db.Column(db.String, nullable=False)
    repaired_at = db.Column(db.DateTime, default=datetime.utcnow)

    board = db.relationship("PcbBoard", backref="repairs")
    work_order = db.relationship("WorkOrder", backref="repairs")


class DefectRecord(db.Model):
    __tablename__ = "defect_records"
    id = db.Column(db.String, primary_key=True)  # uuid
    unit_id = db.Column(db.String, nullable=False)
    wo_id = db.Column(db.String, db.ForeignKey("work_orders.id"))
    defect_code = db.Column(db.String, nullable=False)
    defect_category = db.Column(db.String, nullable=False)
    description = db.Column(db.Text)
    disposition = db.Column(db.String)
    is_repaired = db.Column(db.Boolean, default=False)
    detected_at = db.Column(db.DateTime, default=datetime.utcnow)

    work_order = db.relationship("WorkOrder", backref="defects")


class Capa(db.Model):
    __tablename__ = "capas"
    id = db.Column(db.String, primary_key=True)  # uuid
    capa_number = db.Column(db.String, unique=True, nullable=False)
    ncr_id = db.Column(db.String, db.ForeignKey("ncrs.id"))
    type = db.Column(db.String)
    title = db.Column(db.String, nullable=False)
    problem_statement = db.Column(db.Text, nullable=False)
    root_cause_analysis = db.Column(db.JSON, default={})
    actions = db.Column(db.JSON, default=list)
    status = db.Column(db.String, default="open")
    due_date = db.Column(db.Date)
    owner_id = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class InspectionPlan(db.Model):
    __tablename__ = "inspection_plans"
    id = db.Column(db.String, primary_key=True)  # uuid
    # Legacy fields (kept for backward compat)
    part_number = db.Column(db.String, nullable=True)
    operation_name = db.Column(db.String, nullable=True)
    # Extrusion-domain inspection target
    # target_type: DIE / BILLET / PROFILE / BUNDLE / PROCESS_STAGE / MACHINE_SETUP
    target_type = db.Column(db.String(32), nullable=True)
    target_code = db.Column(db.String(64), nullable=True)
    operation_step = db.Column(db.String(64), nullable=True)
    aql_level = db.Column(db.String, default="2.5")
    sample_size = db.Column(db.Integer, default=80)
    accept_limit = db.Column(db.Integer, default=2)
    reject_limit = db.Column(db.Integer, default=3)
    critical_checklist = db.Column(db.JSON, default=list)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class GoldenBoard(db.Model):
    __tablename__ = "golden_boards"
    id = db.Column(db.String, primary_key=True)  # uuid
    part_number = db.Column(db.String, nullable=False)
    serial_number = db.Column(db.String, unique=True, nullable=False)
    machine_id = db.Column(db.String)
    limit_file_path = db.Column(db.String)
    reference_data = db.Column(db.JSON, default={})
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PpapRecord(db.Model):
    __tablename__ = "ppap_records"
    id = db.Column(db.String, primary_key=True)  # uuid
    part_number = db.Column(db.String, nullable=False)
    wo_id = db.Column(db.String, db.ForeignKey("work_orders.id"))
    level = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String, default="in_progress")
    documents = db.Column(db.JSON, default=list)
    submitted_at = db.Column(db.DateTime)
    approved_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PmSchedule(db.Model):
    __tablename__ = "pm_schedules"
    id = db.Column(db.String, primary_key=True)  # uuid
    machine_id = db.Column(db.String, nullable=False)
    task_name = db.Column(db.String, nullable=False)
    frequency_days = db.Column(db.Integer)
    last_completed_at = db.Column(db.Date)
    due_at = db.Column(db.Date)
    assigned_engineer = db.Column(db.String)
    status = db.Column(db.String, default="Pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class MaintenanceLog(db.Model):
    __tablename__ = "maintenance_logs"
    id = db.Column(db.String, primary_key=True)  # uuid
    machine_id = db.Column(db.String, nullable=False)
    log_type = db.Column(db.String, nullable=False)
    description = db.Column(db.Text, nullable=False)
    action_taken = db.Column(db.Text)
    parts_replaced = db.Column(db.JSON, default=list)
    downtime_minutes = db.Column(db.Integer)
    technician_id = db.Column(db.String)
    performed_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CalibrationRecord(db.Model):
    __tablename__ = "calibration_records"
    id = db.Column(db.String, primary_key=True)  # uuid
    machine_id = db.Column(db.String, nullable=False)
    result = db.Column(db.String)
    certificate_number = db.Column(db.String)
    certificate_path = db.Column(db.String)
    performed_by = db.Column(db.String)
    performed_at = db.Column(db.DateTime, nullable=False)
    next_due_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Stencil(db.Model):
    __tablename__ = "stencils"
    id = db.Column(db.String, primary_key=True)  # uuid
    stencil_code = db.Column(db.String, unique=True, nullable=False)
    part_number = db.Column(db.String, nullable=False)
    manufacturer = db.Column(db.String)
    print_count = db.Column(db.Integer, default=0)
    print_count_limit = db.Column(db.Integer)
    clean_cycle_interval = db.Column(db.Integer, default=10)
    prints_since_last_clean = db.Column(db.Integer, default=0)
    status = db.Column(db.String, default="active")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class TestResult(db.Model):
    __tablename__ = "test_results"
    id = db.Column(db.BigInteger, primary_key=True)
    board_id = db.Column(db.String)
    wo_id = db.Column(db.String)
    machine_id = db.Column(db.String)
    test_type = db.Column(db.String, nullable=False)
    overall_result = db.Column(db.String, nullable=False)
    test_data = db.Column(db.JSON, default={})
    failure_codes = db.Column(db.JSON, nullable=True)  # Array stored as JSON for DB compatibility
    tested_at = db.Column(db.DateTime, default=datetime.utcnow)


class BurnInSession(db.Model):
    __tablename__ = "burn_in_sessions"
    id = db.Column(db.String, primary_key=True)  # uuid
    wo_id = db.Column(db.String, nullable=False)
    chamber_id = db.Column(db.String)
    planned_hours = db.Column(db.Float, nullable=False)
    actual_hours = db.Column(db.Float)
    status = db.Column(db.String, default="queued")
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)


class Plant(db.Model):
    __tablename__ = "plants"
    id = db.Column(db.String, primary_key=True)  # uuid
    code = db.Column(db.String, unique=True, nullable=False)
    name = db.Column(db.String, nullable=False)
    timezone = db.Column(db.String, default="UTC", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Role(db.Model):
    __tablename__ = "roles"
    id = db.Column(db.String, primary_key=True)  # uuid
    name = db.Column(db.String, unique=True, nullable=False)
    display_name = db.Column(db.String, nullable=False)
    permissions = db.Column(db.JSON, default=list, nullable=False)  # Array stored as JSON for DB compatibility


class UserProfile(db.Model):
    __tablename__ = "user_profiles"
    id = db.Column(db.String, primary_key=True)  # auth.users id as text
    plant_id = db.Column(db.String, db.ForeignKey("plants.id"))
    role_id = db.Column(db.String, db.ForeignKey("roles.id"))
    full_name = db.Column(db.String, nullable=False)
    employee_id = db.Column(db.String, unique=True, nullable=False)
    role = db.Column(db.String, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    plant = db.relationship("Plant", backref="users")
    role_rel = db.relationship("Role", backref="users")


class AuditLog(db.Model):
    __tablename__ = "audit_log"
    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(db.String)
    plant_id = db.Column(db.String, db.ForeignKey("plants.id"))
    table_name = db.Column(db.String, nullable=False)
    record_id = db.Column(db.String, nullable=False)
    action = db.Column(db.String, nullable=False)
    old_values = db.Column(db.JSON)
    new_values = db.Column(db.JSON)
    esig_reason = db.Column(db.String)
    ip_address = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    plant = db.relationship("Plant", backref="audit_log_entries")


class OperatorCertification(db.Model):
    __tablename__ = "operator_certifications"
    id = db.Column(db.String, primary_key=True)  # uuid
    user_id = db.Column(db.String, nullable=False)
    operation_code = db.Column(db.String, nullable=False)
    certification_level = db.Column(db.String, nullable=False)
    certified_at = db.Column(db.DateTime, nullable=False)
    expiry_date = db.Column(db.Date)
    certified_by = db.Column(db.String)
    is_active = db.Column(db.Boolean, default=True)


class ElectronicSignature(db.Model):
    __tablename__ = "electronic_signatures"
    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(db.String, nullable=False)
    record_type = db.Column(db.String, nullable=False)
    record_id = db.Column(db.String, nullable=False)
    action = db.Column(db.String, nullable=False)
    signature_hash = db.Column(db.String, nullable=False)
    signed_at = db.Column(db.DateTime, default=datetime.utcnow)


class Integration(db.Model):
    __tablename__ = "integrations"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class ErpSyncLog(db.Model):
    __tablename__ = "erp_sync_logs"
    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(128), nullable=False, default="all")
    status = db.Column(db.String(32), nullable=False)
    triggered_by = db.Column(db.String(128), nullable=True)
    started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    details = db.Column(db.JSON, default=dict)


class Webhook(db.Model):
    __tablename__ = "webhooks"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    url = db.Column(db.String(1024), nullable=False)
    event_type = db.Column(db.String(128), nullable=False)
    secret = db.Column(db.String(256), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class ApiKey(db.Model):
    __tablename__ = "api_keys"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    key_value = db.Column(db.String(256), nullable=False, unique=True, index=True)
    scope = db.Column(db.String(64), nullable=False, default="read")
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used_at = db.Column(db.DateTime, nullable=True)
    revoked_at = db.Column(db.DateTime, nullable=True)


# ─── FOUNDARY DOMAIN: ALUMINUM EXTRUSION ─────────────────────────────────────────────────────
# New models added for the foundry refactoring (dies, billets, extrusion process).
# Do NOT remove existing models above; only append new ones here.

import uuid as _uuid


class CustomerOrder(db.Model):
    __tablename__ = "customer_orders"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    order_number = db.Column(db.String(64), nullable=False, unique=True)
    customer_name = db.Column(db.String(128), nullable=False)
    product_profile = db.Column(db.String(128), nullable=True)
    alloy = db.Column(db.String(64), nullable=True)
    quantity_tons = db.Column(db.Float, nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    erp_reference = db.Column(db.String(64), nullable=True)
    # lifecycle: DRAFT / CONFIRMED / IN_PROGRESS / COMPLETED / CANCELLED
    status = db.Column(db.String(32), nullable=False, default="DRAFT")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProcessPlan(db.Model):
    __tablename__ = "process_plans"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    order_id = db.Column(db.String(36), db.ForeignKey("customer_orders.id"), nullable=True)
    plan_number = db.Column(db.String(64), nullable=False, unique=True)
    alloy = db.Column(db.String(64), nullable=True)
    profile_shape = db.Column(db.String(128), nullable=True)
    scheduled_start = db.Column(db.DateTime, nullable=True)
    scheduled_end = db.Column(db.DateTime, nullable=True)
    actual_start = db.Column(db.DateTime, nullable=True)
    actual_end = db.Column(db.DateTime, nullable=True)
    # lifecycle: Draft / Optimized / Released / InProgress / Delayed / Completed
    status = db.Column(db.String(32), nullable=False, default="Draft")
    priority = db.Column(db.String(16), nullable=True)
    created_by = db.Column(db.String(128), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Extrusion-domain scheduling FKs (machine/die/billet assignments)
    machine_id = db.Column(db.Integer, nullable=True)
    die_id = db.Column(db.String(36), nullable=True)
    billet_id = db.Column(db.String(36), nullable=True)

    order = db.relationship("CustomerOrder", backref="process_plans")


class Die(db.Model):
    __tablename__ = "dies"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    die_code = db.Column(db.String(64), nullable=False, unique=True)
    profile_code = db.Column(db.String(64), nullable=True)
    alloy = db.Column(db.String(64), nullable=True)
    supplier = db.Column(db.String(128), nullable=True)
    location = db.Column(db.String(128), nullable=True)
    # lifecycle: New / Inspected / TestingPending / TestingPassed / TestingFailed
    #            / Rework / NitridingPending / Nitrided / Available / Rejected
    status = db.Column(db.String(32), nullable=False, default="New")
    life_cycles_total = db.Column(db.Integer, nullable=False, default=0)
    last_inspected_at = db.Column(db.DateTime, nullable=True)
    last_tested_at = db.Column(db.DateTime, nullable=True)
    last_nitrided_at = db.Column(db.DateTime, nullable=True)
    erp_asset_id = db.Column(db.String(64), nullable=True)
    # ── Extrusion dies management extensions ───────────────────────────
    description = db.Column(db.Text, nullable=True)
    die_type = db.Column(db.String(64), nullable=True)  # solid / hollow / semi-hollow
    manufacturer = db.Column(db.String(128), nullable=True)
    manufactured_date = db.Column(db.Date, nullable=True)
    press_count = db.Column(db.Integer, default=0)
    press_count_limit = db.Column(db.Integer, nullable=True)
    repair_count = db.Column(db.Integer, default=0)
    nitriding_count = db.Column(db.Integer, default=0)
    last_used_at = db.Column(db.DateTime, nullable=True)
    last_repaired_at = db.Column(db.DateTime, nullable=True)
    # Extended statuses: in_furnace, in_press, repair, retired
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # ── Quality Reporting & Control System extensions (Phase 1) ───────────
    die_life_cycles_remaining = db.Column(db.Integer, nullable=True)  # Calculated: press_count_limit - press_count
    last_failure_reason = db.Column(db.Text, nullable=True)  # Last recorded failure/reason code
    total_setup_time_minutes = db.Column(db.Float, default=0.0)  # Cumulative setup time across all uses
    average_setup_time_minutes = db.Column(db.Float, nullable=True)  # Computed from total / usage count

    inspections = db.relationship("DieInspection", backref="die", lazy="dynamic")
    tests = db.relationship("DieTest", backref="die", lazy="dynamic")
    nitriding_records = db.relationship("NitridingRecord", backref="die", lazy="dynamic")
    furnace_logs = db.relationship("DieFurnaceLog", backref="die", lazy="dynamic")
    repair_records = db.relationship("DieRepairRecord", backref="die", lazy="dynamic")


class DieInspection(db.Model):
    __tablename__ = "die_inspections"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    die_id = db.Column(db.String(36), db.ForeignKey("dies.id"), nullable=False)
    inspection_date = db.Column(db.Date, nullable=False)
    inspector = db.Column(db.String(128), nullable=True)
    dimensions_ok = db.Column(db.Boolean, nullable=True)
    surface_ok = db.Column(db.Boolean, nullable=True)
    hardness = db.Column(db.Float, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    erp_posted = db.Column(db.Boolean, nullable=False, default=False)
    erp_posted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class DieTest(db.Model):
    __tablename__ = "die_tests"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    die_id = db.Column(db.String(36), db.ForeignKey("dies.id"), nullable=False)
    test_date = db.Column(db.Date, nullable=False)
    tester = db.Column(db.String(128), nullable=True)
    press_force = db.Column(db.Float, nullable=True)
    temperature = db.Column(db.Float, nullable=True)
    profile_quality = db.Column(db.String(32), nullable=True)
    # result: PASS / FAIL
    result = db.Column(db.String(16), nullable=True)
    erp_posted = db.Column(db.Boolean, nullable=False, default=False)
    erp_posted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class NitridingRecord(db.Model):
    __tablename__ = "nitriding_records"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    die_id = db.Column(db.String(36), db.ForeignKey("dies.id"), nullable=False)
    furnace_id = db.Column(db.String(64), nullable=True)
    start_temp = db.Column(db.Float, nullable=True)
    end_temp = db.Column(db.Float, nullable=True)
    duration_hours = db.Column(db.Float, nullable=True)
    atmosphere = db.Column(db.String(64), nullable=True)
    hardness_before = db.Column(db.Float, nullable=True)
    hardness_after = db.Column(db.Float, nullable=True)
    operator = db.Column(db.String(128), nullable=True)
    erp_posted = db.Column(db.Boolean, nullable=False, default=False)
    erp_posted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Billet(db.Model):
    __tablename__ = "billets"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    billet_code = db.Column(db.String(64), nullable=False, unique=True)
    alloy = db.Column(db.String(64), nullable=True)
    diameter_mm = db.Column(db.Float, nullable=True)
    length_mm = db.Column(db.Float, nullable=True)
    supplier = db.Column(db.String(128), nullable=True)
    lot_number = db.Column(db.String(64), nullable=True)
    quantity_kg = db.Column(db.Float, nullable=True)
    # lifecycle: AVAILABLE / INSPECTED / CONSUMED / REJECTED
    status = db.Column(db.String(32), nullable=False, default="AVAILABLE")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    inspections = db.relationship("BilletInspection", backref="billet", lazy="dynamic")


class BilletInspection(db.Model):
    __tablename__ = "billet_inspections"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    billet_id = db.Column(db.String(36), db.ForeignKey("billets.id"), nullable=False)
    inspection_date = db.Column(db.Date, nullable=False)
    inspector = db.Column(db.String(128), nullable=True)
    chemical_composition = db.Column(db.JSON, default=dict)
    temperature = db.Column(db.Float, nullable=True)
    result = db.Column(db.String(16), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class MaterialGrade(db.Model):
    __tablename__ = "material_grades"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    code = db.Column(db.String(64), nullable=False, unique=True)
    name = db.Column(db.String(128), nullable=False)
    alloy_family = db.Column(db.String(64), nullable=True)
    density = db.Column(db.Float, nullable=True)
    melting_point = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SetpointProfile(db.Model):
    __tablename__ = "setpoint_profiles"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    # process_type: HLS / PRESSING / QUENCHING / STRETCHING / OVEN
    process_type = db.Column(db.String(32), nullable=False)
    alloy = db.Column(db.String(64), nullable=True)
    profile_code = db.Column(db.String(128), nullable=True)
    parameters = db.Column(db.JSON, default=dict)
    version = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ProcessRun(db.Model):
    __tablename__ = "process_runs"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    process_type = db.Column(db.String(32), nullable=False)
    plan_id = db.Column(db.String(36), db.ForeignKey("process_plans.id"), nullable=True)
    machine_id = db.Column(db.String(36), nullable=True)
    operator_id = db.Column(db.String(64), nullable=True)
    setpoint_profile_id = db.Column(
        db.String(36), db.ForeignKey("setpoint_profiles.id"), nullable=True
    )
    billet_id = db.Column(db.String(36), db.ForeignKey("billets.id"), nullable=True)
    die_id = db.Column(db.String(36), db.ForeignKey("dies.id"), nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    ended_at = db.Column(db.DateTime, nullable=True)
    # status: RUNNING / COMPLETED / FAILED
    status = db.Column(db.String(32), nullable=False, default="RUNNING")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    plan = db.relationship("ProcessPlan", backref="process_runs")
    setpoint_profile = db.relationship("SetpointProfile", backref="process_runs")
    billet = db.relationship("Billet", backref="process_runs")
    die = db.relationship("Die", backref="process_runs")


class QuenchRecord(db.Model):
    __tablename__ = "quench_records"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    run_id = db.Column(db.String(36), db.ForeignKey("process_runs.id"), nullable=False)
    quench_type = db.Column(db.String(32), nullable=True)
    sensor_temperatures = db.Column(db.JSON, default=list)
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    run = db.relationship("ProcessRun", backref="quench_records")


class CutRecord(db.Model):
    __tablename__ = "cut_records"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    run_id = db.Column(db.String(36), db.ForeignKey("process_runs.id"), nullable=False)
    target_length_mm = db.Column(db.Float, nullable=True)
    actual_length_mm = db.Column(db.Float, nullable=True)
    # cut_method: AUTO / MANUAL
    cut_method = db.Column(db.String(16), nullable=True)
    sensor_data = db.Column(db.JSON, default=dict)
    segregation_status = db.Column(db.String(32), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    run = db.relationship("ProcessRun", backref="cut_records")


class StretchRecord(db.Model):
    __tablename__ = "stretch_records"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    run_id = db.Column(db.String(36), db.ForeignKey("process_runs.id"), nullable=False)
    tension_actual = db.Column(db.Float, nullable=True)
    tension_setpoint = db.Column(db.Float, nullable=True)
    position_transducer_reading = db.Column(db.Float, nullable=True)
    pressure_transducer_reading = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    run = db.relationship("ProcessRun", backref="stretch_records")


class OvenRecord(db.Model):
    __tablename__ = "oven_records"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    run_id = db.Column(db.String(36), db.ForeignKey("process_runs.id"), nullable=False)
    oven_id = db.Column(db.String(64), nullable=True)
    set_temperature = db.Column(db.Float, nullable=True)
    actual_temperature = db.Column(db.Float, nullable=True)
    soak_time_minutes = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    run = db.relationship("ProcessRun", backref="oven_records")


class AlertRule(db.Model):
    __tablename__ = "alert_rules"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    name = db.Column(db.String(128), nullable=False)
    metric = db.Column(db.String(64), nullable=False)
    # operator: GT / LT / EQ / BETWEEN
    operator = db.Column(db.String(16), nullable=False)
    threshold_value = db.Column(db.JSON, default=dict)
    severity = db.Column(db.String(16), nullable=False, default="WARNING")
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Alert(db.Model):
    __tablename__ = "alerts"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    rule_id = db.Column(db.String(36), db.ForeignKey("alert_rules.id"), nullable=True)
    # severity: INFO / WARNING / CRITICAL
    severity = db.Column(db.String(16), nullable=False, default="INFO")
    title = db.Column(db.String(256), nullable=False)
    message = db.Column(db.Text, nullable=True)
    # source: DIE / PROCESS_LINE / PLANNING / INTEGRATION / MACHINE
    source = db.Column(db.String(32), nullable=False)
    source_id = db.Column(db.String(64), nullable=True)
    # status: Open / Acknowledged / Closed
    status = db.Column(db.String(32), nullable=False, default="Open")
    acknowledged_by = db.Column(db.String(128), nullable=True)
    acknowledged_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    rule = db.relationship("AlertRule", backref="alerts")


class KPIRecord(db.Model):
    __tablename__ = "kpi_records"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    # kpi_type: OEE / THROUGHPUT / REJECTION_RATE / DIE_LIFETIME
    #           / MACHINE_DOWNTIME / SHORTAGE
    # Quality Reporting & Control System - New KPI types (Phase 1)
    # FPY = First Pass Yield, PPM = Parts Per Million defect rate
    # COPQ = Cost of Poor Quality, ENERGY_CONSUMPTION
    kpi_type = db.Column(db.String(32), nullable=False)
    machine_id = db.Column(db.String(36), nullable=True)
    shift_date = db.Column(db.Date, nullable=True)
    value = db.Column(db.Float, nullable=True)
    unit = db.Column(db.String(32), nullable=True)
    details = db.Column(db.JSON, default=dict)
    calculated_at = db.Column(db.DateTime, default=datetime.utcnow)



class IntegrationJob(db.Model):
    __tablename__ = "integration_jobs"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    # job_type: ERP_POST_INSPECTION / ERP_POST_TEST / ERP_POST_NITRIDING
    #           / ERP_ORDER_IMPORT / PLC_SETPOINT_LOAD / PLC_CAPTURE
    job_type = db.Column(db.String(64), nullable=False)
    # status: Pending / Running / Success / Failed / RetryQueued
    status = db.Column(db.String(32), nullable=False, default="Pending")
    payload = db.Column(db.JSON, default=dict)
    result = db.Column(db.JSON, default=dict)
    retries = db.Column(db.Integer, nullable=False, default=0)
    max_retries = db.Column(db.Integer, nullable=False, default=3)
    next_retry_at = db.Column(db.DateTime, nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ERPTransactionLog(db.Model):
    __tablename__ = "erp_transaction_logs"
    # Use BigInteger PK to match the convention in the spec (big PK).
    id = db.Column(db.BigInteger, primary_key=True)
    # direction: OUTBOUND / INBOUND
    direction = db.Column(db.String(16), nullable=False)
    entity_type = db.Column(db.String(64), nullable=False)
    entity_id = db.Column(db.String(64), nullable=True)
    payload = db.Column(db.JSON, default=dict)
    erp_response = db.Column(db.JSON, default=dict)
    # status: SUCCESS / FAILED / PENDING
    status = db.Column(db.String(16), nullable=False, default="PENDING")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PLCSignalMapping(db.Model):
    __tablename__ = "plc_signal_mappings"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    machine_name = db.Column(db.String(128), nullable=False)
    signal_tag = db.Column(db.String(256), nullable=False)
    # signal_type: SETPOINT / ACTUAL / ALARM / STATUS
    signal_type = db.Column(db.String(16), nullable=False)
    unit = db.Column(db.String(32), nullable=True)
    process_type = db.Column(db.String(32), nullable=True)
    scale_factor = db.Column(db.Float, nullable=False, default=1.0)
    offset = db.Column(db.Float, nullable=False, default=0.0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class TraceabilityRecord(db.Model):
    __tablename__ = "traceability_records"
    # Use BigInteger PK to match the spec (big PK).
    id = db.Column(db.BigInteger, primary_key=True)
    # entity_type: DIE / BILLET / PROCESS_RUN / ORDER
    entity_type = db.Column(db.String(32), nullable=False)
    entity_id = db.Column(db.String(64), nullable=False)
    event_type = db.Column(db.String(64), nullable=False)
    operator_id = db.Column(db.String(64), nullable=True)
    machine_id = db.Column(db.String(64), nullable=True)
    data = db.Column(db.JSON, default=dict)
    occurred_at = db.Column(db.DateTime, default=datetime.utcnow)


# ─── EXTRUSION: COST PRICE CALCULATOR ────────────────────────────────────
class CostPriceConfig(db.Model):
    __tablename__ = "cost_price_configs"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    part_number = db.Column(db.String(64), nullable=False)
    revision = db.Column(db.String(8), default="A")
    raw_material_cost_per_kg = db.Column(db.Float, default=0.0)
    material_weight_kg = db.Column(db.Float, default=0.0)
    machine_rate_per_hour = db.Column(db.Float, default=0.0)
    cycle_time_hours = db.Column(db.Float, default=0.0)
    labor_rate_per_hour = db.Column(db.Float, default=0.0)
    labor_hours = db.Column(db.Float, default=0.0)
    energy_kwh = db.Column(db.Float, default=0.0)
    energy_rate_per_kwh = db.Column(db.Float, default=0.0)
    overhead_percent = db.Column(db.Float, default=10.0)
    margin_percent = db.Column(db.Float, default=15.0)
    calculated_cost = db.Column(db.Float, nullable=True)
    break_even_price = db.Column(db.Float, nullable=True)
    currency = db.Column(db.String(8), default="USD")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ─── EXTRUSION: RAW MATERIAL RECEIPT ────────────────────────────────────
class RawMaterialType(db.Model):
    __tablename__ = "raw_material_types"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    code = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(128), nullable=False)
    category = db.Column(db.String(64), nullable=True)  # alloy / billet / ingot
    uom = db.Column(db.String(16), default="KG")


class AlloyComposition(db.Model):
    __tablename__ = "alloy_compositions"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    alloy_code = db.Column(db.String(64), unique=True, nullable=False)
    alloy_name = db.Column(db.String(128), nullable=False)
    composition = db.Column(db.JSON, default=dict)  # {"Si": {"min": 0.2, "max": 0.6}}
    standard = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class MaterialReceipt(db.Model):
    __tablename__ = "material_receipts"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    receipt_number = db.Column(db.String(64), unique=True, nullable=False)
    supplier_name = db.Column(db.String(128), nullable=True)
    truck_reference = db.Column(db.String(64), nullable=True)
    material_type_id = db.Column(db.String(36), db.ForeignKey("raw_material_types.id"), nullable=True)
    alloy_code = db.Column(db.String(64), db.ForeignKey("alloy_compositions.alloy_code"), nullable=True)
    lot_number = db.Column(db.String(64), nullable=False)
    quantity_received = db.Column(db.Float, nullable=False)
    quantity_available = db.Column(db.Float, nullable=True)
    uom = db.Column(db.String(16), default="KG")
    actual_composition = db.Column(db.JSON, default=dict)
    composition_status = db.Column(db.String(16), default="PENDING")
    received_by = db.Column(db.String(128), nullable=True)
    received_at = db.Column(db.DateTime, default=datetime.utcnow)
    location_id = db.Column(db.String(36), db.ForeignKey("inventory_locations.id"), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    material_type = db.relationship("RawMaterialType", backref="receipts")
    alloy = db.relationship("AlloyComposition", backref="receipts")
    location = db.relationship("InventoryLocation", backref="material_receipts")


# ─── EXTRUSION: DIE FURNACE & REPAIR ───────────────────────────────────
class DieFurnaceLog(db.Model):
    __tablename__ = "die_furnace_logs"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    die_id = db.Column(db.String(36), db.ForeignKey("dies.id"), nullable=False)
    furnace_id = db.Column(db.String(64), nullable=True)
    target_temp_celsius = db.Column(db.Float, nullable=True)
    actual_temp_celsius = db.Column(db.Float, nullable=True)
    soak_time_minutes = db.Column(db.Integer, nullable=True)
    started_at = db.Column(db.DateTime, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(16), default="heating")  # heating / soaking / ready / aborted
    operator_id = db.Column(db.String(128), nullable=True)


class DieRepairRecord(db.Model):
    __tablename__ = "die_repair_records"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    die_id = db.Column(db.String(36), db.ForeignKey("dies.id"), nullable=False)
    repair_type = db.Column(db.String(64), nullable=True)
    description = db.Column(db.Text, nullable=True)
    performed_by = db.Column(db.String(128), nullable=True)
    performed_at = db.Column(db.DateTime, nullable=False)
    cost = db.Column(db.Float, nullable=True)
    returned_to_store_at = db.Column(db.DateTime, nullable=True)


# ─── EXTRUSION: COATING SCHEDULE ───────────────────────────────────────
class CoatingColor(db.Model):
    __tablename__ = "coating_colors"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    color_code = db.Column(db.String(64), unique=True, nullable=False)
    color_name = db.Column(db.String(128), nullable=False)
    hex_value = db.Column(db.String(7), nullable=True)
    clean_time_minutes = db.Column(db.Integer, default=30)
    ral_code = db.Column(db.String(32), nullable=True)


class CoatingScheduleEntry(db.Model):
    __tablename__ = "coating_schedule_entries"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    wo_id = db.Column(db.String(36), db.ForeignKey("work_orders.id"), nullable=False)
    coating_line_id = db.Column(db.String(64), nullable=True)
    color_id = db.Column(db.String(36), db.ForeignKey("coating_colors.id"), nullable=True)
    color_group_sequence = db.Column(db.Integer, nullable=True)
    scheduled_start = db.Column(db.DateTime, nullable=True)
    scheduled_end = db.Column(db.DateTime, nullable=True)
    actual_start = db.Column(db.DateTime, nullable=True)
    actual_end = db.Column(db.DateTime, nullable=True)
    powder_quantity_kg = db.Column(db.Float, nullable=True)
    actual_powder_used_kg = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(32), default="planned")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    work_order = db.relationship("WorkOrder", backref=db.backref("coating_entries", lazy="dynamic"))
    color = db.relationship("CoatingColor", backref=db.backref("schedule_entries", lazy="dynamic"))


# ─── EXTRUSION: CONTAINERS ─────────────────────────────────────────────
class Container(db.Model):
    __tablename__ = "containers"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    container_code = db.Column(db.String(64), unique=True, nullable=False)
    container_type = db.Column(db.String(64), nullable=True)
    tare_weight_kg = db.Column(db.Float, nullable=True)
    max_capacity_kg = db.Column(db.Float, nullable=True)
    max_capacity_units = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(32), default="available")
    current_location = db.Column(db.String(128), nullable=True)
    current_wo_id = db.Column(db.String(36), db.ForeignKey("work_orders.id"), nullable=True)
    material = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    current_work_order = db.relationship("WorkOrder", backref="containers")


class ContainerWeighEvent(db.Model):
    __tablename__ = "container_weigh_events"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    container_id = db.Column(db.String(36), db.ForeignKey("containers.id"), nullable=False)
    wo_id = db.Column(db.String(36), db.ForeignKey("work_orders.id"), nullable=True)
    gross_weight_kg = db.Column(db.Float, nullable=False)
    tare_weight_kg = db.Column(db.Float, nullable=False)
    net_weight_kg = db.Column(db.Float, nullable=True)
    expected_weight_kg = db.Column(db.Float, nullable=True)
    weight_variance_percent = db.Column(db.Float, nullable=True)
    weigh_station = db.Column(db.String(64), nullable=True)
    operator_id = db.Column(db.String(128), nullable=True)
    weighed_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(16), default="OK")

    work_order = db.relationship("WorkOrder", backref=db.backref("container_weigh_events", lazy="dynamic"))
    container = db.relationship("Container", backref=db.backref("weigh_events", lazy="dynamic"))


class ContainerMovement(db.Model):
    __tablename__ = "container_movements"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    container_id = db.Column(db.String(36), db.ForeignKey("containers.id"), nullable=False)
    from_location = db.Column(db.String(128), nullable=True)
    to_location = db.Column(db.String(128), nullable=False)
    moved_by = db.Column(db.String(128), nullable=True)
    moved_at = db.Column(db.DateTime, default=datetime.utcnow)
    wo_id = db.Column(db.String(36), db.ForeignKey("work_orders.id"), nullable=True)

    work_order = db.relationship("WorkOrder", backref=db.backref("container_movements", lazy="dynamic"))
    container = db.relationship("Container", backref=db.backref("movements", lazy="dynamic"))


# ─── EXTRUSION: FURNACE / HEAT TREATMENT ───────────────────────────────
class Furnace(db.Model):
    __tablename__ = "furnaces"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    furnace_code = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(128), nullable=False)
    furnace_type = db.Column(db.String(64), nullable=True)
    max_temp_celsius = db.Column(db.Float, nullable=True)
    capacity_kg = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(32), default="idle")
    current_program_id = db.Column(db.String(36), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class HeatTreatmentProgram(db.Model):
    __tablename__ = "heat_treatment_programs"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    program_code = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(128), nullable=False)
    alloy_code = db.Column(db.String(64), nullable=True)
    temper_designation = db.Column(db.String(16), nullable=True)
    stages = db.Column(db.JSON, default=list)
    total_duration_minutes = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class FurnaceSession(db.Model):
    __tablename__ = "furnace_sessions"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    furnace_id = db.Column(db.String(36), db.ForeignKey("furnaces.id"), nullable=False)
    program_id = db.Column(db.String(36), db.ForeignKey("heat_treatment_programs.id"), nullable=False)
    wo_id = db.Column(db.String(36), db.ForeignKey("work_orders.id"), nullable=True)
    batch_reference = db.Column(db.String(64), nullable=True)
    loaded_containers = db.Column(db.JSON, default=list)
    total_load_kg = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(32), default="queued")
    current_stage_index = db.Column(db.Integer, default=0)
    current_temp_celsius = db.Column(db.Float, nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    operator_id = db.Column(db.String(128), nullable=True)
    temperature_log = db.Column(db.JSON, default=list)
    result = db.Column(db.String(16), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    furnace = db.relationship("Furnace", backref=db.backref("sessions", lazy="dynamic"))
    program = db.relationship("HeatTreatmentProgram", backref=db.backref("sessions", lazy="dynamic"))
    work_order = db.relationship("WorkOrder", backref=db.backref("furnace_sessions", lazy="dynamic"))


# ─── EXTRUSION: FINISHING PROCESSES ────────────────────────────────────
class FinishingProcessType(db.Model):
    __tablename__ = "finishing_process_types"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    code = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=True)
    requires_plc_instruction = db.Column(db.Boolean, default=False)
    default_parameters = db.Column(db.JSON, default=dict)


class FinishingOrder(db.Model):
    __tablename__ = "finishing_orders"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    order_number = db.Column(db.String(64), unique=True, nullable=False)
    wo_id = db.Column(db.String(36), db.ForeignKey("work_orders.id"), nullable=False)
    process_type_id = db.Column(db.String(36), db.ForeignKey("finishing_process_types.id"), nullable=False)
    container_id = db.Column(db.String(36), db.ForeignKey("containers.id"), nullable=True)
    sequence = db.Column(db.Integer, default=1)
    status = db.Column(db.String(32), default="pending")
    parameters = db.Column(db.JSON, default=dict)
    plc_command = db.Column(db.JSON, nullable=True)
    plc_ack_status = db.Column(db.String(16), nullable=True)
    operator_id = db.Column(db.String(128), nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    remarks = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    work_order = db.relationship("WorkOrder", backref=db.backref("finishing_orders", lazy="dynamic"))
    process_type_ref = db.relationship("FinishingProcessType", backref=db.backref("orders", lazy="dynamic"))
    container_ref = db.relationship("Container", backref=db.backref("finishing_orders", lazy="dynamic"))


# ─── EXTRUSION: LOGISTICS & SHIPMENT ───────────────────────────────────
class PackagingSpec(db.Model):
    __tablename__ = "packaging_specs"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    part_number = db.Column(db.String(64), nullable=False)
    packing_method = db.Column(db.String(128), nullable=True)
    units_per_pack = db.Column(db.Integer, nullable=True)
    theoretical_weight_per_pack_kg = db.Column(db.Float, nullable=True)
    label_template = db.Column(db.String(256), nullable=True)
    special_instructions = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PackagingOrder(db.Model):
    __tablename__ = "packaging_orders"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    wo_id = db.Column(db.String(36), db.ForeignKey("work_orders.id"), nullable=False)
    packaging_spec_id = db.Column(db.String(36), db.ForeignKey("packaging_specs.id"), nullable=True)
    pack_number = db.Column(db.String(64), unique=True, nullable=False)
    barcode = db.Column(db.String(128), unique=True, nullable=True)
    quantity_packed = db.Column(db.Integer, nullable=True)
    actual_weight_kg = db.Column(db.Float, nullable=True)
    theoretical_weight_kg = db.Column(db.Float, nullable=True)
    weight_variance_percent = db.Column(db.Float, nullable=True)
    label_printed = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(32), default="pending")
    packed_by = db.Column(db.String(128), nullable=True)
    packed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    work_order = db.relationship("WorkOrder", backref=db.backref("packaging_orders", lazy="dynamic"))
    spec = db.relationship("PackagingSpec", backref=db.backref("orders", lazy="dynamic"))


class Shipment(db.Model):
    __tablename__ = "shipments"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    shipment_number = db.Column(db.String(64), unique=True, nullable=False)
    customer_name = db.Column(db.String(128), nullable=True)
    delivery_address = db.Column(db.Text, nullable=True)
    carrier = db.Column(db.String(128), nullable=True)
    truck_reference = db.Column(db.String(64), nullable=True)
    scheduled_ship_date = db.Column(db.Date, nullable=True)
    actual_ship_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(32), default="open")
    theoretical_total_weight_kg = db.Column(db.Float, nullable=True)
    actual_total_weight_kg = db.Column(db.Float, nullable=True)
    weight_check_status = db.Column(db.String(16), nullable=True)
    weight_check_variance_percent = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ShipmentLine(db.Model):
    __tablename__ = "shipment_lines"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    shipment_id = db.Column(db.String(36), db.ForeignKey("shipments.id"), nullable=False)
    packaging_order_id = db.Column(db.String(36), db.ForeignKey("packaging_orders.id"), nullable=False)
    wo_id = db.Column(db.String(36), db.ForeignKey("work_orders.id"), nullable=True)
    quantity = db.Column(db.Integer, nullable=True)
    scanned_at = db.Column(db.DateTime, nullable=True)
    scanned_by = db.Column(db.String(128), nullable=True)

    shipment = db.relationship("Shipment", backref=db.backref("lines", lazy="dynamic"))
    packaging_order = db.relationship("PackagingOrder", backref=db.backref("shipment_lines", lazy="dynamic"))
    work_order = db.relationship("WorkOrder", backref=db.backref("shipment_lines", lazy="dynamic"))


# ─── WATMON ENERGY METER INTEGRATION ───────────────────────────────────────
# Fixed-column readings table for the Wattmon CSV export. Columns mirror the
# canonical header list produced by the Wattmon integration device. Any rows
# uploaded via POST /integrations/csv-upload are persisted here row-by-row.
#
# 216 columns in total:
#   - 1 common timestamp (ts)
#   - 1 common timestamp string (timestamp)
#   - 71 columns × 3 Schneider power meter serials (540420085805,
#     540420080451, 540420075852, 540420085806, 540420085810, 540420085804,
#     540420082234, 540420085811, 540420080682)  -- 9 meters × 71 cols each
#     NOTE: the canonical list actually contains 9 Schneider serials, not 3.
#   - 19 columns × 1 Rishabh meter (2303051510)
#
# All values stored as TEXT because Wattmon CSV payload values are plain
# strings ("0", "0.000", "411.788", ...). Numeric parsing is left to the
# read-side when calculations are needed.
class WattmonUpload(db.Model):
    """Metadata for each POST to /integrations/csv-upload."""
    __tablename__ = "wattmon_uploads"
    id = db.Column(db.Integer, primary_key=True)
    source_key = db.Column(db.String(128), nullable=True, index=True)       # device MAC from `key=` field
    filename = db.Column(db.String(256), nullable=False, default="upload.csv")
    row_count = db.Column(db.Integer, nullable=False, default=0)
    uploaded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    # Async-processing state: raw POST body is saved to disk immediately,
    # then a background thread parses + inserts the CSV rows.
    status = db.Column(db.String(16), nullable=False, default="pending")    # pending / success / failed
    error_detail = db.Column(db.Text, nullable=True)

    readings = db.relationship(
        "WattmonReading",
        backref=db.backref("upload", lazy="joined"),
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="WattmonReading.id",
    )


# Canonical Wattmon CSV header list — kept as documentation. The EAV schema
# below accepts *any* column name, so this list is not enforced at insert time.
# It is still useful for the UI and for tests that want to assert "known"
# columns are present in a payload.
_WATMON_COLUMNS = [
    "ts",
    # Schneider 540420085805
    "m_schneider_540420085805_AC_Active_Power",
    "m_schneider_540420085805_AC_Reactive_Power",
    "m_schneider_540420085805_AC_Apparent_Power",
    "m_schneider_540420085805_kWh_Total_Active",
    "m_schneider_540420085805_kVARh_Total_Active",
    "m_schneider_540420085805_kVAh_Total_Active",
    "m_schneider_540420085805_AC_Current_A",
    "m_schneider_540420085805_AC_Current_B",
    "m_schneider_540420085805_AC_Current_C",
    "m_schneider_540420085805_AC_Voltage_AB",
    "m_schneider_540420085805_AC_Voltage_BC",
    "m_schneider_540420085805_AC_Voltage_CA",
    "m_schneider_540420085805_AC_Voltage_AN",
    "m_schneider_540420085805_AC_Voltage_BN",
    "m_schneider_540420085805_AC_Voltage_CN",
    "m_schneider_540420085805_AC_Active_Power_A",
    "m_schneider_540420085805_AC_Active_Power_B",
    "m_schneider_540420085805_AC_Active_Power_C",
    "m_schneider_540420085805_AC_Reactive_Power_A",
    "m_schneider_540420085805_AC_Reactive_Power_B",
    "m_schneider_540420085805_AC_Reactive_Power_C",
    "m_schneider_540420085805_AC_Apparent_Power_A",
    "m_schneider_540420085805_AC_Apparent_Power_B",
    "m_schneider_540420085805_AC_Apparent_Power_C",
    "m_schneider_540420085805_AC_PF_A",
    "m_schneider_540420085805_AC_PF_B",
    "m_schneider_540420085805_AC_PF_C",
    "m_schneider_540420085805_AC_PF",
    "m_schneider_540420085805_AC_Frequency",
    # Schneider 540420080451
    "m_schneider_540420080451_AC_Active_Power",
    "m_schneider_540420080451_AC_Reactive_Power",
    "m_schneider_540420080451_AC_Apparent_Power",
    "m_schneider_540420080451_kWh_Total_Active",
    "m_schneider_540420080451_kVARh_Total_Active",
    "m_schneider_540420080451_kVAh_Total_Active",
    "m_schneider_540420080451_AC_Current_A",
    "m_schneider_540420080451_AC_Current_B",
    "m_schneider_540420080451_AC_Current_C",
    "m_schneider_540420080451_AC_Voltage_AB",
    "m_schneider_540420080451_AC_Voltage_BC",
    "m_schneider_540420080451_AC_Voltage_CA",
    "m_schneider_540420080451_AC_Voltage_AN",
    "m_schneider_540420080451_AC_Voltage_BN",
    "m_schneider_540420080451_AC_Voltage_CN",
    "m_schneider_540420080451_AC_Active_Power_A",
    "m_schneider_540420080451_AC_Active_Power_B",
    "m_schneider_540420080451_AC_Active_Power_C",
    "m_schneider_540420080451_AC_Reactive_Power_A",
    "m_schneider_540420080451_AC_Reactive_Power_B",
    "m_schneider_540420080451_AC_Reactive_Power_C",
    "m_schneider_540420080451_AC_Apparent_Power_A",
    "m_schneider_540420080451_AC_Apparent_Power_B",
    "m_schneider_540420080451_AC_Apparent_Power_C",
    "m_schneider_540420080451_AC_PF_A",
    "m_schneider_540420080451_AC_PF_B",
    "m_schneider_540420080451_AC_PF_C",
    "m_schneider_540420080451_AC_PF",
    "m_schneider_540420080451_AC_Frequency",
    # Schneider 540420075852
    "m_schneider_540420075852_AC_Active_Power",
    "m_schneider_540420075852_AC_Reactive_Power",
    "m_schneider_540420075852_AC_Apparent_Power",
    "m_schneider_540420075852_kWh_Total_Active",
    "m_schneider_540420075852_kVARh_Total_Active",
    "m_schneider_540420075852_kVAh_Total_Active",
    "m_schneider_540420075852_AC_Current_A",
    "m_schneider_540420075852_AC_Current_B",
    "m_schneider_540420075852_AC_Current_C",
    "m_schneider_540420075852_AC_Voltage_AB",
    "m_schneider_540420075852_AC_Voltage_BC",
    "m_schneider_540420075852_AC_Voltage_CA",
    "m_schneider_540420075852_AC_Voltage_AN",
    "m_schneider_540420075852_AC_Voltage_BN",
    "m_schneider_540420075852_AC_Voltage_CN",
    "m_schneider_540420075852_AC_Active_Power_A",
    "m_schneider_540420075852_AC_Active_Power_B",
    "m_schneider_540420075852_AC_Active_Power_C",
    "m_schneider_540420075852_AC_Reactive_Power_A",
    "m_schneider_540420075852_AC_Reactive_Power_B",
    "m_schneider_540420075852_AC_Reactive_Power_C",
    "m_schneider_540420075852_AC_Apparent_Power_A",
    "m_schneider_540420075852_AC_Apparent_Power_B",
    "m_schneider_540420075852_AC_Apparent_Power_C",
    "m_schneider_540420075852_AC_PF_A",
    "m_schneider_540420075852_AC_PF_B",
    "m_schneider_540420075852_AC_PF_C",
    "m_schneider_540420075852_AC_PF",
    "m_schneider_540420075852_AC_Frequency",
    # Schneider 540420085806
    "m_schneider_540420085806_AC_Active_Power",
    "m_schneider_540420085806_AC_Reactive_Power",
    "m_schneider_540420085806_AC_Apparent_Power",
    "m_schneider_540420085806_kWh_Total_Active",
    "m_schneider_540420085806_kVARh_Total_Active",
    "m_schneider_540420085806_kVAh_Total_Active",
    "m_schneider_540420085806_AC_Current_A",
    "m_schneider_540420085806_AC_Current_B",
    "m_schneider_540420085806_AC_Current_C",
    "m_schneider_540420085806_AC_Voltage_AB",
    "m_schneider_540420085806_AC_Voltage_BC",
    "m_schneider_540420085806_AC_Voltage_CA",
    "m_schneider_540420085806_AC_Voltage_AN",
    "m_schneider_540420085806_AC_Voltage_BN",
    "m_schneider_540420085806_AC_Voltage_CN",
    "m_schneider_540420085806_AC_Active_Power_A",
    "m_schneider_540420085806_AC_Active_Power_B",
    "m_schneider_540420085806_AC_Active_Power_C",
    "m_schneider_540420085806_AC_Reactive_Power_A",
    "m_schneider_540420085806_AC_Reactive_Power_B",
    "m_schneider_540420085806_AC_Reactive_Power_C",
    "m_schneider_540420085806_AC_Apparent_Power_A",
    "m_schneider_540420085806_AC_Apparent_Power_B",
    "m_schneider_540420085806_AC_Apparent_Power_C",
    "m_schneider_540420085806_AC_PF_A",
    "m_schneider_540420085806_AC_PF_B",
    "m_schneider_540420085806_AC_PF_C",
    "m_schneider_540420085806_AC_PF",
    "m_schneider_540420085806_AC_Frequency",
    # Schneider 540420085810
    "m_schneider_540420085810_AC_Active_Power",
    "m_schneider_540420085810_AC_Reactive_Power",
    "m_schneider_540420085810_AC_Apparent_Power",
    "m_schneider_540420085810_kWh_Total_Active",
    "m_schneider_540420085810_kVARh_Total_Active",
    "m_schneider_540420085810_kVAh_Total_Active",
    "m_schneider_540420085810_AC_Current_A",
    "m_schneider_540420085810_AC_Current_B",
    "m_schneider_540420085810_AC_Current_C",
    "m_schneider_540420085810_AC_Voltage_AB",
    "m_schneider_540420085810_AC_Voltage_BC",
    "m_schneider_540420085810_AC_Voltage_CA",
    "m_schneider_540420085810_AC_Voltage_AN",
    "m_schneider_540420085810_AC_Voltage_BN",
    "m_schneider_540420085810_AC_Voltage_CN",
    "m_schneider_540420085810_AC_Active_Power_A",
    "m_schneider_540420085810_AC_Active_Power_B",
    "m_schneider_540420085810_AC_Active_Power_C",
    "m_schneider_540420085810_AC_Reactive_Power_A",
    "m_schneider_540420085810_AC_Reactive_Power_B",
    "m_schneider_540420085810_AC_Reactive_Power_C",
    "m_schneider_540420085810_AC_Apparent_Power_A",
    "m_schneider_540420085810_AC_Apparent_Power_B",
    "m_schneider_540420085810_AC_Apparent_Power_C",
    "m_schneider_540420085810_AC_PF_A",
    "m_schneider_540420085810_AC_PF_B",
    "m_schneider_540420085810_AC_PF_C",
    "m_schneider_540420085810_AC_PF",
    "m_schneider_540420085810_AC_Frequency",
    # Schneider 540420085804
    "m_schneider_540420085804_AC_Active_Power",
    "m_schneider_540420085804_AC_Reactive_Power",
    "m_schneider_540420085804_AC_Apparent_Power",
    "m_schneider_540420085804_kWh_Total_Active",
    "m_schneider_540420085804_kVARh_Total_Active",
    "m_schneider_540420085804_kVAh_Total_Active",
    "m_schneider_540420085804_AC_Current_A",
    "m_schneider_540420085804_AC_Current_B",
    "m_schneider_540420085804_AC_Current_C",
    "m_schneider_540420085804_AC_Voltage_AB",
    "m_schneider_540420085804_AC_Voltage_BC",
    "m_schneider_540420085804_AC_Voltage_CA",
    "m_schneider_540420085804_AC_Voltage_AN",
    "m_schneider_540420085804_AC_Voltage_BN",
    "m_schneider_540420085804_AC_Voltage_CN",
    "m_schneider_540420085804_AC_Active_Power_A",
    "m_schneider_540420085804_AC_Active_Power_B",
    "m_schneider_540420085804_AC_Active_Power_C",
    "m_schneider_540420085804_AC_Reactive_Power_A",
    "m_schneider_540420085804_AC_Reactive_Power_B",
    "m_schneider_540420085804_AC_Reactive_Power_C",
    "m_schneider_540420085804_AC_Apparent_Power_A",
    "m_schneider_540420085804_AC_Apparent_Power_B",
    "m_schneider_540420085804_AC_Apparent_Power_C",
    "m_schneider_540420085804_AC_PF_A",
    "m_schneider_540420085804_AC_PF_B",
    "m_schneider_540420085804_AC_PF_C",
    "m_schneider_540420085804_AC_PF",
    "m_schneider_540420085804_AC_Frequency",
    # Schneider 540420082234
    "m_schneider_540420082234_AC_Active_Power",
    "m_schneider_540420082234_AC_Reactive_Power",
    "m_schneider_540420082234_AC_Apparent_Power",
    "m_schneider_540420082234_kWh_Total_Active",
    "m_schneider_540420082234_kVARh_Total_Active",
    "m_schneider_540420082234_kVAh_Total_Active",
    "m_schneider_540420082234_AC_Current_A",
    "m_schneider_540420082234_AC_Current_B",
    "m_schneider_540420082234_AC_Current_C",
    "m_schneider_540420082234_AC_Voltage_AB",
    "m_schneider_540420082234_AC_Voltage_BC",
    "m_schneider_540420082234_AC_Voltage_CA",
    "m_schneider_540420082234_AC_Voltage_AN",
    "m_schneider_540420082234_AC_Voltage_BN",
    "m_schneider_540420082234_AC_Voltage_CN",
    "m_schneider_540420082234_AC_Active_Power_A",
    "m_schneider_540420082234_AC_Active_Power_B",
    "m_schneider_540420082234_AC_Active_Power_C",
    "m_schneider_540420082234_AC_Reactive_Power_A",
    "m_schneider_540420082234_AC_Reactive_Power_B",
    "m_schneider_540420082234_AC_Reactive_Power_C",
    "m_schneider_540420082234_AC_Apparent_Power_A",
    "m_schneider_540420082234_AC_Apparent_Power_B",
    "m_schneider_540420082234_AC_Apparent_Power_C",
    "m_schneider_540420082234_AC_PF_A",
    "m_schneider_540420082234_AC_PF_B",
    "m_schneider_540420082234_AC_PF_C",
    "m_schneider_540420082234_AC_PF",
    "m_schneider_540420082234_AC_Frequency",
    # Schneider 540420085811
    "m_schneider_540420085811_AC_Active_Power",
    "m_schneider_540420085811_AC_Reactive_Power",
    "m_schneider_540420085811_AC_Apparent_Power",
    "m_schneider_540420085811_kWh_Total_Active",
    "m_schneider_540420085811_kVARh_Total_Active",
    "m_schneider_540420085811_kVAh_Total_Active",
    "m_schneider_540420085811_AC_Current_A",
    "m_schneider_540420085811_AC_Current_B",
    "m_schneider_540420085811_AC_Current_C",
    "m_schneider_540420085811_AC_Voltage_AB",
    "m_schneider_540420085811_AC_Voltage_BC",
    "m_schneider_540420085811_AC_Voltage_CA",
    "m_schneider_540420085811_AC_Voltage_AN",
    "m_schneider_540420085811_AC_Voltage_BN",
    "m_schneider_540420085811_AC_Voltage_CN",
    "m_schneider_540420085811_AC_Active_Power_A",
    "m_schneider_540420085811_AC_Active_Power_B",
    "m_schneider_540420085811_AC_Active_Power_C",
    "m_schneider_540420085811_AC_Reactive_Power_A",
    "m_schneider_540420085811_AC_Reactive_Power_B",
    "m_schneider_540420085811_AC_Reactive_Power_C",
    "m_schneider_540420085811_AC_Apparent_Power_A",
    "m_schneider_540420085811_AC_Apparent_Power_B",
    "m_schneider_540420085811_AC_Apparent_Power_C",
    "m_schneider_540420085811_AC_PF_A",
    "m_schneider_540420085811_AC_PF_B",
    "m_schneider_540420085811_AC_PF_C",
    "m_schneider_540420085811_AC_PF",
    "m_schneider_540420085811_AC_Frequency",
    # Schneider 540420080682
    "m_schneider_540420080682_AC_Active_Power",
    "m_schneider_540420080682_AC_Reactive_Power",
    "m_schneider_540420080682_AC_Apparent_Power",
    "m_schneider_540420080682_kWh_Total_Active",
    "m_schneider_540420080682_kVARh_Total_Active",
    "m_schneider_540420080682_kVAh_Total_Active",
    "m_schneider_540420080682_AC_Current_A",
    "m_schneider_540420080682_AC_Current_B",
    "m_schneider_540420080682_AC_Current_C",
    "m_schneider_540420080682_AC_Voltage_AB",
    "m_schneider_540420080682_AC_Voltage_BC",
    "m_schneider_540420080682_AC_Voltage_CA",
    "m_schneider_540420080682_AC_Voltage_AN",
    "m_schneider_540420080682_AC_Voltage_BN",
    "m_schneider_540420080682_AC_Voltage_CN",
    "m_schneider_540420080682_AC_Active_Power_A",
    "m_schneider_540420080682_AC_Active_Power_B",
    "m_schneider_540420080682_AC_Active_Power_C",
    "m_schneider_540420080682_AC_Reactive_Power_A",
    "m_schneider_540420080682_AC_Reactive_Power_B",
    "m_schneider_540420080682_AC_Reactive_Power_C",
    "m_schneider_540420080682_AC_Apparent_Power_A",
    "m_schneider_540420080682_AC_Apparent_Power_B",
    "m_schneider_540420080682_AC_Apparent_Power_C",
    "m_schneider_540420080682_AC_PF_A",
    "m_schneider_540420080682_AC_PF_B",
    "m_schneider_540420080682_AC_PF_C",
    "m_schneider_540420080682_AC_PF",
    "m_schneider_540420080682_AC_Frequency",
    # Rishabh 2303051510
    "m_rishabh_2303051510_AC_Active_Power",
    "m_rishabh_2303051510_AC_Reactive_Power",
    "m_rishabh_2303051510_AC_Apparent_Power",
    "m_rishabh_2303051510_kWh_Total_Import",
    "m_rishabh_2303051510_kWh_Total_Export",
    "m_rishabh_2303051510_AC_Voltage_AN",
    "m_rishabh_2303051510_AC_Voltage_BN",
    "m_rishabh_2303051510_AC_Voltage_CN",
    "m_rishabh_2303051510_AC_Current_A",
    "m_rishabh_2303051510_AC_Current_B",
    "m_rishabh_2303051510_AC_Current_C",
    "m_rishabh_2303051510_AC_Active_Power_A",
    "m_rishabh_2303051510_AC_Active_Power_B",
    "m_rishabh_2303051510_AC_Active_Power_C",
    "m_rishabh_2303051510_AC_PF",
    "m_rishabh_2303051510_AC_Frequency",
    "m_rishabh_2303051510_kVARh_Lead",
    "m_rishabh_2303051510_kVARh_Lag",
    "m_rishabh_2303051510_kVAh_Total_Active",
]


class WattmonReading(db.Model):
    """Entity-Attribute-Value: one row per (device_key, column_name, value, time-point).

    A 216-column CSV row expands into N rows here (one per cell), all sharing
    the same ``row_index`` and ``epoch_ts``. Pivot is query-time, not schema-time:

        SELECT column_name, value
          FROM wattmon_readings
         WHERE upload_id = :uid AND epoch_ts = :ts
         ORDER BY column_name

    ``epoch_ts`` is copied from the CSV's ``ts`` column and propagated down to
    every EAV row of that time-point. When the header has no ``ts`` column, the
    caller falls back to ``row_index`` for grouping.
    """

    __tablename__ = "wattmon_readings"
    __table_args__ = (
        db.Index("ix_wattmon_readings_lookup", "device_key", "epoch_ts"),
        db.Index("ix_wattmon_readings_upload_row", "upload_id", "row_index"),
    )

    id = db.Column(db.Integer, primary_key=True)
    upload_id = db.Column(
        db.Integer,
        db.ForeignKey("wattmon_uploads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    device_key = db.Column(db.String(128), nullable=True, index=True)
    column_name = db.Column(db.String(256), nullable=False, index=True)
    value = db.Column(db.Text, nullable=True)
    row_index = db.Column(db.Integer, nullable=False, index=True)
    epoch_ts = db.Column(db.Integer, nullable=True, index=True)


# ─── EXTRUSION MASTER DATA: CUSTOMER / PART NUMBER / BOM ──────────────────────

class Customer(db.Model):
    """Customer master data for BOM-driven order management."""
    __tablename__ = "customers"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    customer_code = db.Column(db.String(64), unique=True, nullable=False)
    customer_name = db.Column(db.String(128), nullable=False)
    contact_email = db.Column(db.String(128), nullable=True)
    contact_phone = db.Column(db.String(32), nullable=True)
    address = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Backref for CustomerPartNumber relationship (created automatically via backref in CustomerPartNumber)


class PartNumber(db.Model):
    """Part number master data for BOM-driven order management."""
    __tablename__ = "part_numbers"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    part_code = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    profile_code = db.Column(db.String(64), nullable=True)
    alloy = db.Column(db.String(64), nullable=True)
    unit_weight_kg = db.Column(db.Float, nullable=True)
    uom = db.Column(db.String(16), default="KG")
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CustomerPartNumber(db.Model):
    """Mapping between customers and their approved part numbers."""
    __tablename__ = "customer_part_numbers"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    customer_id = db.Column(db.String(36), db.ForeignKey("customers.id"), nullable=False)
    part_number_id = db.Column(db.String(36), db.ForeignKey("part_numbers.id"), nullable=False)
    customer_part_ref = db.Column(db.String(64), nullable=True)  # Customer's internal part reference
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    customer = db.relationship("Customer", backref="customer_part_numbers")
    part_number = db.relationship("PartNumber", backref="customer_part_numbers")
    __table_args__ = (
        db.UniqueConstraint("customer_id", "part_number_id", name="uq_customer_part"),
    )


class PartNumberBOM(db.Model):
    """Bill of Materials linking a part number to its die and billet types."""
    __tablename__ = "part_number_boms"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    part_number_id = db.Column(db.String(36), db.ForeignKey("part_numbers.id"), nullable=False)
    version = db.Column(db.Integer, nullable=False, default=1)
    die_type_id = db.Column(db.String(36), db.ForeignKey("dies.id"), nullable=False)
    billet_type_id = db.Column(db.String(36), db.ForeignKey("billets.id"), nullable=False)
    billet_weight_kg = db.Column(db.Float, nullable=True)
    extrusion_ratio = db.Column(db.Float, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.String(128), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    part_number = db.relationship("PartNumber", backref="boms")
    die_type = db.relationship("Die", backref="bom_entries")
    billet_type = db.relationship("Billet", backref="bom_entries")


class CustomerOrderLine(db.Model):
    """Individual line items within a customer order, linked to part numbers."""
    __tablename__ = "customer_order_lines"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    order_id = db.Column(db.String(36), db.ForeignKey("customer_orders.id"), nullable=False)
    part_number_id = db.Column(db.String(36), db.ForeignKey("part_numbers.id"), nullable=False)
    line_number = db.Column(db.Integer, nullable=False, default=1)
    ordered_qty = db.Column(db.Float, nullable=False)
    uom = db.Column(db.String(16), default="KG")
    required_date = db.Column(db.Date, nullable=True)
    customer_po_reference = db.Column(db.String(64), nullable=True)
    status = db.Column(db.String(32), nullable=False, default="OPEN")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    order = db.relationship("CustomerOrder", backref="order_lines")
    part_number = db.relationship("PartNumber", backref="order_lines")

# ──────────────────────────────────────────────────────────────────────────────
# QUALITY REPORTING & CONTROL SYSTEM - NEW MODELS (Phase 1)
# Tables created by migration: 20260720_add_quality_schema.py
# ──────────────────────────────────────────────────────────────────────────────

# Enum types for quality tables (defined here for model relationships)
defect_categories_enum = ENUM('surface', 'dimensional', 'functional', 'aesthetic', name='defect_categories')
defect_severity_enum = ENUM('minor', 'moderate', 'major', 'critical', name='defect_severity')
inspection_types_enum = ENUM('dimensional', 'visual', 'process_parameter', 'first_piece', name='inspection_types')
inspection_stages_enum = ENUM('pre_production', 'in_process', 'post_extrusion', name='inspection_stages')
inspection_pass_fail_enum = ENUM('PASS', 'FAIL', 'PENDING', name='inspection_pass_fail')
test_types_enum = ENUM('webster', 'barcol', 'vickers', 'uts', 'ut', name='test_types')
alarm_categories_enum = ENUM('mechanical', 'electrical', 'hydraulic', 'thermal', 'safety', name='alarm_categories')
alarm_severity_levels_enum = ENUM('info', 'warning', 'critical', name='alarm_severity_levels')
violation_types_enum = ENUM('low_limit', 'high_limit', name='violation_types')
alert_severity_enum = ENUM('warning', 'critical', name='alert_severity')
alert_status_enum = ENUM('active', 'acknowledged', 'resolved', name='alert_status')
trend_directions_enum = ENUM('up', 'down', 'stable', name='trend_directions')
traceability_status_enum = ENUM('in_production', 'completed', 'shipped', 'returned', name='traceability_status')


class DefectCode(db.Model):
    """Master list of defect types with categories and severity levels.

    Used for standardized defect tracking across all quality inspections.
    Categories: surface, dimensional, functional, aesthetic
    Severity: minor, moderate, major, critical
    """
    __tablename__ = "defect_codes"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    code = db.Column(db.String(32), nullable=False, unique=True)
    name = db.Column(db.String(128), nullable=False)
    category = db.Column(defect_categories_enum, nullable=False)
    severity = db.Column(defect_severity_enum, default='moderate')
    is_active = db.Column(db.Boolean, default=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    quality_inspections = db.relationship("QualityInspection", backref="defect_code_ref")


class QualityParameter(db.Model):
    """Process parameter limits per profile/alloy.

    Stores acceptable ranges for all extrusion process parameters:
    - Billet, container, die, exit temperatures
    - Ram speed, main cylinder pressure
    - Extrusion force, cycle time
    """
    __tablename__ = "quality_parameters"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    profile_code = db.Column(db.String(128), nullable=False)
    alloy = db.Column(db.String(64), nullable=False)

    # Process parameter limits - billet heating
    billet_temp_min = db.Column(db.Float, nullable=True)
    billet_temp_max = db.Column(db.Float, nullable=True)

    # Container temperature limits
    container_temp_min = db.Column(db.Float, nullable=True)
    container_temp_max = db.Column(db.Float, nullable=True)

    # Die temperature limits
    die_temp_min = db.Column(db.Float, nullable=True)
    die_temp_max = db.Column(db.Float, nullable=True)

    # Exit temperature limits
    exit_temp_min = db.Column(db.Float, nullable=True)
    exit_temp_max = db.Column(db.Float, nullable=True)

    # Ram speed limits (mm/s)
    ram_speed_min = db.Column(db.Float, nullable=True)
    ram_speed_max = db.Column(db.Float, nullable=True)

    # Main cylinder pressure limits (bar)
    pressure_min = db.Column(db.Float, nullable=True)
    pressure_max = db.Column(db.Float, nullable=True)

    # Extrusion force limits (kN)
    force_min = db.Column(db.Float, nullable=True)
    force_max = db.Column(db.Float, nullable=True)

    # Cycle time limits (seconds)
    cycle_time_min = db.Column(db.Float, nullable=True)
    cycle_time_max = db.Column(db.Float, nullable=True)

    # Metadata
    setpoint_profile_id = db.Column(db.String(36), db.ForeignKey("setpoint_profiles.id"), nullable=True)
    version = db.Column(db.Integer, default=1)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    parameter_readings = db.relationship("ParameterReading", backref="quality_parameter_ref")


class ParameterReading(db.Model):
    """Real-time PLC parameter capture during extrusion runs.

    Stores time-series sensor data from the press PLC for each process run:
    - Temperature readings (billet, container, die, exit)
    - Ram speed, main cylinder pressure, extrusion force
    - Cycle time, stem position, puller speed
    - Cooling parameters as JSONB
    """
    __tablename__ = "parameter_readings"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    run_id = db.Column(db.String(36), db.ForeignKey("process_runs.id"), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Process parameter readings from PLC
    billet_temp = db.Column(db.Float, nullable=True)
    container_temp = db.Column(db.Float, nullable=True)
    die_temp = db.Column(db.Float, nullable=True)
    exit_temp = db.Column(db.Float, nullable=True)
    ram_speed = db.Column(db.Float, nullable=True)
    main_cylinder_pressure = db.Column(db.Float, nullable=True)
    extrusion_force = db.Column(db.Float, nullable=True)
    cycle_time = db.Column(db.Float, nullable=True)

    # Additional sensor readings
    stem_position = db.Column(db.Float, nullable=True)
    puller_speed = db.Column(db.Float, nullable=True)
    cooling_params = db.Column(db.JSON(), default=dict)

    # Validation flags
    all_within_limits = db.Column(db.Boolean, nullable=True)
    violation_count = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    process_run = db.relationship("ProcessRun", backref="parameter_readings")
    alerts = db.relationship("ProcessParameterAlert", backref="parameter_reading_ref", lazy="dynamic")


class QualityInspection(db.Model):
    """Unified inspection records across all quality stages.

    Replaces and extends DieInspection/BilletInspection patterns with:
    - Flexible inspection types (dimensional, visual, process_parameter, first_piece)
    - Stage tracking (pre_production, in_process, post_extrusion)
    - JSONB results for flexible schema per inspection type
    - Link to any production entity (WO, billet, die, run)
    """
    __tablename__ = "quality_inspections"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    inspection_type = db.Column(inspection_types_enum, nullable=False)
    stage = db.Column(inspection_stages_enum, nullable=False)

    # Link to production entities (nullable for flexibility)
    wo_id = db.Column(db.String(36), db.ForeignKey("work_orders.id"), nullable=True)
    billet_id = db.Column(db.String(36), db.ForeignKey("billets.id"), nullable=True)
    die_id = db.Column(db.String(36), db.ForeignKey("dies.id"), nullable=True)
    run_id = db.Column(db.String(36), db.ForeignKey("process_runs.id"), nullable=True)

    # Operator info
    operator_id = db.Column(db.String(64), nullable=True)
    inspector_name = db.Column(db.String(128), nullable=True)

    # Inspection results
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    results = db.Column(db.JSON(), default=dict)
    pass_fail = db.Column(inspection_pass_fail_enum, default='PENDING')
    measured_values = db.Column(db.JSON(), default=dict)

    # Notes and ERP integration
    notes = db.Column(db.Text, nullable=True)
    erp_posted = db.Column(db.Boolean, default=False)
    erp_posted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class TestEvent(db.Model):
    """Mechanical and NDT test results.

    Stores test data from various testing methods:
    - Webster bend test (alloy hardness verification)
    - Barcol hardness test
    - Vickers microhardness test
    - Ultimate Tensile Strength (UTS) tests
    - Ultrasonic Testing (UT) for solid sections
    """
    __tablename__ = "test_events"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    test_type = db.Column(test_types_enum, nullable=False)

    # Link to production/order entities
    wo_id = db.Column(db.String(36), db.ForeignKey("work_orders.id"), nullable=True)
    specimen_id = db.Column(db.String(128), nullable=True)  # Specimen identifier from test machine

    # Test results
    result_value = db.Column(db.Float, nullable=True)
    acceptance_limit = db.Column(db.Float, nullable=True)
    passed = db.Column(db.Boolean, nullable=True)
    test_data = db.Column(db.JSON(), default=dict)  # Full test data dump

    # Tester info and timing
    tested_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    tester_id = db.Column(db.String(64), nullable=True)
    tester_name = db.Column(db.String(128), nullable=True)
    equipment_id = db.Column(db.String(64), nullable=True)  # Test machine ID
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AlarmBreakdownLog(db.Model):
    """Machine alarm and downtime tracking.

    Records all machine alarms with duration tracking:
    - Alarm code and name from HMI/PLC
    - Duration in minutes (filled when resolved)
    - Category classification (mechanical, electrical, hydraulic, thermal, safety)
    - Severity levels (info, warning, critical)
    - Resolution info (who resolved, notes)
    """
    __tablename__ = "alarm_breakdown_log"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    machine_id = db.Column(db.String(36), nullable=False)
    alarm_code = db.Column(db.String(32), nullable=False)
    alarm_name = db.Column(db.String(128), nullable=False)

    # Duration tracking (minutes)
    duration_min = db.Column(db.Float, nullable=True)

    # Timing
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ended_at = db.Column(db.DateTime, nullable=True)

    # Alarm classification
    is_recurring = db.Column(db.Boolean, default=False)
    category = db.Column(alarm_categories_enum, nullable=True)
    severity = db.Column(alarm_severity_levels_enum, default='warning')

    # Resolution info (filled when alarm cleared)
    resolved_by = db.Column(db.String(64), nullable=True)
    resolution_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('machine_id', 'alarm_code', 'started_at', name='uq_machine_alarm_start'),
    )


class ProcessParameterAlert(db.Model):
    """Auto-triggered parameter violations.

    Created when real-time parameter readings exceed configured limits:
    - Parameter name and actual value at violation time
    - Threshold bounds (low/high) from quality_parameters table
    - Violation type (high_limit or low_limit)
    - Auto-stop trigger status
    - Alert lifecycle (active, acknowledged, resolved)
    """
    __tablename__ = "process_parameter_alerts"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    run_id = db.Column(db.String(36), db.ForeignKey("process_runs.id"), nullable=False)
    parameter_name = db.Column(db.String(64), nullable=False)  # e.g., 'billet_temp', 'die_temp'
    actual_value = db.Column(db.Float, nullable=False)
    threshold_low = db.Column(db.Float, nullable=True)  # Lower limit
    threshold_high = db.Column(db.Float, nullable=True)  # Upper limit

    triggered_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Auto-stop behavior
    auto_stop_triggered = db.Column(db.Boolean, default=False)
    stop_confirmed_by = db.Column(db.String(64), nullable=True)  # Operator who confirmed stop
    violation_type = db.Column(violation_types_enum, nullable=False)
    severity = db.Column(alert_severity_enum, default='warning')
    status = db.Column(alert_status_enum, default='active')
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SPCRecord(db.Model):
    """SPC chart data points with shift grouping.

    Stores dimension measurements for Statistical Process Control:
    - Dimension type (OD, ID, thickness, etc.)
    - Target and measured values with control limits
    - Sample number within subgroup for X-bar charts
    - Shift group classification (morning, afternoon, night)
    - Out-of-control detection flags
    """
    __tablename__ = "spc_records"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    wo_id = db.Column(db.String(36), db.ForeignKey("work_orders.id"), nullable=False)

    # Dimension type being tracked (e.g., 'OD', 'ID', 'thickness')
    dimension_type = db.Column(db.String(64), nullable=False)
    target_value = db.Column(db.Float, nullable=False)  # Nominal/target dimension
    measured_value = db.Column(db.Float, nullable=False)  # Actual measurement

    # Control limits (calculated or specified)
    upper_limit = db.Column(db.Float, nullable=True)  # UCL/UML
    lower_limit = db.Column(db.Float, nullable=True)  # LCL/LML

    # Shift grouping for X-bar charts
    sample_number = db.Column(db.Integer, nullable=False)
    shift_group = db.Column(db.String(32), nullable=False)  # e.g., 'morning', 'afternoon', 'night'

    # Timing and operator info
    sample_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    operator_id = db.Column(db.String(64), nullable=True)
    inspector_name = db.Column(db.String(128), nullable=True)

    # SPC status flags
    out_of_control = db.Column(db.Boolean, default=False)
    trend_direction = db.Column(trend_directions_enum, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class MaterialTraceability(db.Model):
    """End-to-end traceability chain.

    Links all production entities from raw material to customer shipment:
    - Batch number and heat number (from foundry)
    - Billet code and die code used
    - Work order association
    - Process parameters snapshot at extrusion time
    - Customer order linkage for forward traceability
    - Shipment batch ID for delivery tracking
    """
    __tablename__ = "material_traceability"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))

    # Traceability identifiers
    batch_number = db.Column(db.String(64), nullable=False)  # Production batch ID
    heat_number = db.Column(db.String(64), nullable=True)     # Heat/lot number from foundry
    billet_code = db.Column(db.String(64), nullable=True)
    die_code = db.Column(db.String(64), nullable=True)
    work_order_id = db.Column(db.String(36), db.ForeignKey("work_orders.id"), nullable=False)

    # Timestamps and operator info
    extrusion_timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    operator_id = db.Column(db.String(64), nullable=True)

    # Process parameters snapshot (JSON for flexibility)
    process_params = db.Column(db.JSON(), default=dict)

    # Customer order linkage for forward traceability
    customer_order_line_id = db.Column(db.String(36), nullable=True)
    shipment_batch_id = db.Column(db.String(64), nullable=True)  # For customer shipments

    # Status tracking
    status = db.Column(traceability_status_enum, default='in_production')
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# Add indexes for new tables (matching migration)
DefectCode.__table_args__ = (
    db.Index('ix_defect_codes_code', 'code'),
    db.Index('ix_defect_codes_category', 'category'),
)

QualityParameter.__table_args__ = (
    db.Index('ix_quality_parameters_profile_code', 'profile_code'),
    db.Index('ix_quality_parameters_alloy', 'alloy'),
    db.Index('ix_quality_parameters_is_active', 'is_active'),
)

ParameterReading.__table_args__ = (
    db.Index('ix_parameter_readings_run_id', 'run_id'),
    db.Index('ix_parameter_readings_timestamp', 'timestamp'),
    db.Index('ix_parameter_readings_all_within_limits', 'all_within_limits'),
    db.Index('ix_parameter_readings_run_timestamp', 'run_id', 'timestamp'),
)

QualityInspection.__table_args__ = (
    db.Index('ix_quality_inspections_inspection_type', 'inspection_type'),
    db.Index('ix_quality_inspections_stage', 'stage'),
    db.Index('ix_quality_inspections_wo_id', 'wo_id'),
    db.Index('ix_quality_inspections_die_id', 'die_id'),
    db.Index('ix_quality_inspections_pass_fail', 'pass_fail'),
    db.Index('ix_quality_inspections_wo_die_timestamp', 'wo_id', 'die_id', 'timestamp'),
)

TestEvent.__table_args__ = (
    db.Index('ix_test_events_test_type', 'test_type'),
    db.Index('ix_test_events_wo_id', 'wo_id'),
    db.Index('ix_test_events_passed', 'passed'),
)

AlarmBreakdownLog.__table_args__ = (
    db.Index('ix_alarm_breakdown_log_machine_id', 'machine_id'),
    db.Index('ix_alarm_breakdown_log_started_at', 'started_at'),
    db.Index('ix_alarm_breakdown_log_is_recurring', 'is_recurring'),
)

ProcessParameterAlert.__table_args__ = (
    db.Index('ix_process_parameter_alerts_run_id', 'run_id'),
    db.Index('ix_process_parameter_alerts_status', 'status'),
    db.Index('ix_process_parameter_alerts_auto_stop_triggered', 'auto_stop_triggered'),
)

SPCRecord.__table_args__ = (
    db.Index('ix_spc_records_wo_id', 'wo_id'),
    db.Index('ix_spc_records_dimension_type', 'dimension_type'),
    db.Index('ix_spc_records_shift_group', 'shift_group'),
    db.Index('ix_spc_records_out_of_control', 'out_of_control'),
)

MaterialTraceability.__table_args__ = (
    db.Index('ix_material_traceability_batch_number', 'batch_number'),
    db.Index('ix_material_traceability_work_order_id', 'work_order_id'),
    db.Index('ix_material_traceability_heat_number', 'heat_number'),
)


