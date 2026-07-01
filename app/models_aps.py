"""APS models: MachineResourceMapping, WorkOrderResource, and the full
Advanced Planning & Scheduling (APS) schedule engine models.

Backref naming convention: every backref in this file is prefixed with
``aps_`` so it never collides with backrefs registered by models.py or
models_routing.py (e.g. ProductionSchedule already owns
WorkOrder.schedule_entries via backref='schedule_entries').
"""

from app import db
from datetime import datetime
import uuid


def _u():
    return str(uuid.uuid4())


# ── Resource mapping models ───────────────────────────────────────────────────

class MachineResourceMapping(db.Model):
    """Maps a part number to required machine resources (machine, die, consumables, time params)."""

    __tablename__ = 'machine_resource_mapping'

    id = db.Column(db.Integer, primary_key=True)
    part_number = db.Column(db.String(100), nullable=False, index=True)
    machine_id = db.Column(db.Integer, db.ForeignKey('machines.id'), nullable=False)
    # dies.id is VARCHAR(36) — FK type must match
    die_id = db.Column(db.String(36), db.ForeignKey('dies.id'), nullable=True)
    consumable_ids = db.Column(db.JSON, nullable=True)
    cycle_time_sec = db.Column(db.Integer, nullable=False, default=60)
    changeover_time_sec = db.Column(db.Integer, nullable=False, default=1800)
    setup_time_sec = db.Column(db.Integer, nullable=False, default=900)
    transport_time_sec = db.Column(db.Integer, nullable=False, default=300)
    preferred = db.Column(db.Boolean, default=False)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # backref names prefixed with aps_ to avoid collision with any future
    # backrefs added in models.py / models_routing.py
    machine = db.relationship('Machine', backref='aps_resource_mappings')
    die = db.relationship('Die', backref='aps_resource_mappings')

    __table_args__ = (
        db.UniqueConstraint('part_number', 'machine_id', name='uq_part_machine'),
    )

    def __repr__(self):
        return f'<MachineResourceMapping part={self.part_number} machine={self.machine_id}>'


class WorkOrderResource(db.Model):
    """Tracks which resources were assigned to a work order at schedule time."""

    __tablename__ = 'work_order_resources'

    id = db.Column(db.Integer, primary_key=True)
    work_order_id = db.Column(db.String(36), db.ForeignKey('work_orders.id'), nullable=False, index=True)
    machine_id = db.Column(db.Integer, db.ForeignKey('machines.id'), nullable=False)
    die_id = db.Column(db.String(36), db.ForeignKey('dies.id'), nullable=True)
    consumable_ids = db.Column(db.JSON, nullable=True)
    cycle_time_sec = db.Column(db.Integer, nullable=False)
    changeover_time_sec = db.Column(db.Integer, nullable=False)
    setup_time_sec = db.Column(db.Integer, nullable=False)
    transport_time_sec = db.Column(db.Integer, nullable=False)
    scheduled_start = db.Column(db.DateTime, nullable=False)
    scheduled_end = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    work_order = db.relationship('WorkOrder', backref='aps_assigned_resources')
    machine = db.relationship('Machine', backref='aps_assigned_resources')
    die = db.relationship('Die', backref='aps_assigned_resources')

    def __repr__(self):
        return f'<WorkOrderResource wo={self.work_order_id} machine={self.machine_id}>'


# ── APS schedule engine models ────────────────────────────────────────────────

class ApsScheduleVersion(db.Model):
    """A named snapshot of the production schedule (active, draft, or archived)."""

    __tablename__ = 'aps_schedule_versions'

    id = db.Column(db.String(36), primary_key=True, default=_u)
    name = db.Column(db.String(200), nullable=False)
    version_type = db.Column(db.String(50), nullable=False, default='DRAFT')  # ACTIVE | DRAFT | ARCHIVED
    planning_horizon_days = db.Column(db.Integer, nullable=False, default=14)
    published_at = db.Column(db.DateTime, nullable=True)
    created_by = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notes = db.Column(db.Text, nullable=True)

    entries = db.relationship('ApsScheduleEntry', backref='version', lazy='dynamic',
                               cascade='all, delete-orphan')
    constraint_logs = db.relationship('ApsConstraintLog', backref='version', lazy='dynamic',
                                       cascade='all, delete-orphan')
    events = db.relationship('ApsScheduleEvent', backref='version', lazy='dynamic',
                              cascade='all, delete-orphan')

    def __repr__(self):
        return f'<ApsScheduleVersion {self.name} [{self.version_type}]>'


class ApsScheduleEntry(db.Model):
    """One scheduled block: a work order assigned to a machine in a time window."""

    __tablename__ = 'aps_schedule_entries'

    id = db.Column(db.String(36), primary_key=True, default=_u)
    version_id = db.Column(db.String(36), db.ForeignKey('aps_schedule_versions.id'), nullable=False, index=True)
    work_order_id = db.Column(db.String(36), db.ForeignKey('work_orders.id'), nullable=True, index=True)
    machine_id = db.Column(db.Integer, db.ForeignKey('machines.id'), nullable=False)
    die_id = db.Column(db.String(36), db.ForeignKey('dies.id'), nullable=True)
    billet_id = db.Column(db.String(36), db.ForeignKey('billets.id'), nullable=True)

    scheduled_start = db.Column(db.DateTime, nullable=False)
    scheduled_end = db.Column(db.DateTime, nullable=False)
    sequence_order = db.Column(db.Integer, nullable=False, default=0)
    setup_duration_min = db.Column(db.Integer, nullable=False, default=0)

    status = db.Column(db.String(50), nullable=False, default='PLANNED')
    priority = db.Column(db.String(50), nullable=True)
    constraint_status = db.Column(db.String(50), nullable=True, default='FEASIBLE')
    constraint_reasons = db.Column(db.JSON, nullable=True)

    is_locked = db.Column(db.Boolean, default=False)
    locked_by = db.Column(db.String(100), nullable=True)
    locked_at = db.Column(db.DateTime, nullable=True)
    lock_reason = db.Column(db.Text, nullable=True)

    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ProductionSchedule in models.py already registered backref='schedule_entries'
    # on WorkOrder — use distinct names here.
    work_order = db.relationship('WorkOrder', backref='aps_schedule_entries')
    machine = db.relationship('Machine', backref='aps_schedule_entries')
    die = db.relationship('Die', backref='aps_schedule_entries')

    def __repr__(self):
        return f'<ApsScheduleEntry wo={self.work_order_id} machine={self.machine_id} {self.scheduled_start}>'


class ApsConstraintLog(db.Model):
    """Records a scheduling constraint violation or warning for a version/entry."""

    __tablename__ = 'aps_constraint_logs'

    id = db.Column(db.String(36), primary_key=True, default=_u)
    version_id = db.Column(db.String(36), db.ForeignKey('aps_schedule_versions.id'), nullable=False, index=True)
    work_order_id = db.Column(db.String(36), db.ForeignKey('work_orders.id'), nullable=True, index=True)
    entry_id = db.Column(db.String(36), db.ForeignKey('aps_schedule_entries.id'), nullable=True)

    reason_code = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(20), nullable=False, default='WARNING')  # INFO | WARNING | CRITICAL

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    work_order = db.relationship('WorkOrder', backref='aps_constraint_logs')

    def __repr__(self):
        return f'<ApsConstraintLog {self.reason_code} [{self.severity}]>'


class ApsScheduleEvent(db.Model):
    """Audit trail of changes to schedule entries (locks, overrides, replans)."""

    __tablename__ = 'aps_schedule_events'

    id = db.Column(db.String(36), primary_key=True, default=_u)
    version_id = db.Column(db.String(36), db.ForeignKey('aps_schedule_versions.id'), nullable=False, index=True)
    entry_id = db.Column(db.String(36), db.ForeignKey('aps_schedule_entries.id'), nullable=True)

    event_type = db.Column(db.String(100), nullable=False)  # LOCKED | UNLOCKED | RESCHEDULED | CANCELLED
    old_values = db.Column(db.JSON, nullable=True)
    new_values = db.Column(db.JSON, nullable=True)
    triggered_by = db.Column(db.String(100), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<ApsScheduleEvent {self.event_type} entry={self.entry_id}>'
