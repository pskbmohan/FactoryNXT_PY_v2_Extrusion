"""Visual Routing Builder models for FactoryNXT.

Separate file to avoid merge conflicts with existing models.py.
Import these models in app/__init__.py or where needed.
"""
from . import db
from datetime import datetime


class RoutingMaster(db.Model):
    """Routing header – one record per routing revision."""
    __tablename__ = "routing_master"

    id = db.Column(db.Integer, primary_key=True)
    routing_code = db.Column(db.String(64), nullable=False, index=True)
    routing_name = db.Column(db.String(256), nullable=False)
    product_id   = db.Column(db.String(64), nullable=True, index=True)   # part number / product code
    revision     = db.Column(db.String(16), nullable=False, default="A")
    description  = db.Column(db.Text, nullable=True)
    # DRAFT | RELEASED | OBSOLETE
    status       = db.Column(db.String(32), nullable=False, default="DRAFT")
    created_by   = db.Column(db.String(128), nullable=True)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at   = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Canvas layout – Drawflow JSON blob
    canvas_data  = db.Column(db.JSON, nullable=True)

    steps       = db.relationship("RoutingStepV2",
                                   backref="routing",
                                   cascade="all, delete-orphan",
                                   order_by="RoutingStepV2.step_no")
    connections = db.relationship("RoutingConnection",
                                   backref="routing",
                                   cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id":           self.id,
            "routing_code": self.routing_code,
            "routing_name": self.routing_name,
            "product_id":   self.product_id,
            "revision":     self.revision,
            "description":  self.description,
            "status":       self.status,
            "created_by":   self.created_by,
            "created_at":   self.created_at.isoformat() if self.created_at else None,
            "canvas_data":  self.canvas_data,
        }


class RoutingStepV2(db.Model):
    """Individual step / operation in a routing."""
    __tablename__ = "routing_steps_v2"

    id              = db.Column(db.Integer, primary_key=True)
    routing_id      = db.Column(db.Integer, db.ForeignKey("routing_master.id", ondelete="CASCADE"), nullable=False)
    step_no         = db.Column(db.Integer, nullable=False)
    station_id      = db.Column(db.Integer, db.ForeignKey("stations.id"), nullable=True)
    step_name       = db.Column(db.String(256), nullable=False)
    cycle_time      = db.Column(db.Float, nullable=True)        # seconds
    operator_skill  = db.Column(db.String(128), nullable=True)
    parallel        = db.Column(db.Boolean, default=False)
    qc_required     = db.Column(db.Boolean, default=False)
    mandatory       = db.Column(db.Boolean, default=True)
    rework_allowed  = db.Column(db.Boolean, default=True)
    remarks         = db.Column(db.Text, nullable=True)
    # Drawflow node position
    node_id         = db.Column(db.String(64), nullable=True)
    pos_x           = db.Column(db.Float, nullable=True)
    pos_y           = db.Column(db.Float, nullable=True)

    station = db.relationship("Station", backref="routing_steps_v2")

    def to_dict(self):
        return {
            "id":             self.id,
            "routing_id":     self.routing_id,
            "step_no":        self.step_no,
            "station_id":     self.station_id,
            "station_name":   self.station.name if self.station else None,
            "step_name":      self.step_name,
            "cycle_time":     self.cycle_time,
            "operator_skill": self.operator_skill,
            "parallel":       self.parallel,
            "qc_required":    self.qc_required,
            "mandatory":      self.mandatory,
            "rework_allowed": self.rework_allowed,
            "remarks":        self.remarks,
            "node_id":        self.node_id,
            "pos_x":          self.pos_x,
            "pos_y":          self.pos_y,
        }


class RoutingConnection(db.Model):
    """Directed connection between two routing steps (DAG edge)."""
    __tablename__ = "routing_connections"

    id          = db.Column(db.Integer, primary_key=True)
    routing_id  = db.Column(db.Integer, db.ForeignKey("routing_master.id", ondelete="CASCADE"), nullable=False)
    from_step   = db.Column(db.Integer, db.ForeignKey("routing_steps_v2.id", ondelete="CASCADE"), nullable=False)
    to_step     = db.Column(db.Integer, db.ForeignKey("routing_steps_v2.id", ondelete="CASCADE"), nullable=False)

    def to_dict(self):
        return {
            "id":         self.id,
            "routing_id": self.routing_id,
            "from_step":  self.from_step,
            "to_step":    self.to_step,
        }


class RoutingProductAssignment(db.Model):
    """Links a product/part number to a specific routing revision."""
    __tablename__ = "routing_product_assignments"

    id          = db.Column(db.Integer, primary_key=True)
    product_id  = db.Column(db.String(64), nullable=False, index=True)
    routing_id  = db.Column(db.Integer, db.ForeignKey("routing_master.id"), nullable=False)
    assigned_by = db.Column(db.String(128), nullable=True)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active   = db.Column(db.Boolean, default=True)

    routing = db.relationship("RoutingMaster", backref="assignments")

    def to_dict(self):
        return {
            "id":          self.id,
            "product_id":  self.product_id,
            "routing_id":  self.routing_id,
            "assigned_by": self.assigned_by,
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None,
            "is_active":   self.is_active,
        }


class WorkOrderRoutingSnapshot(db.Model):
    """Frozen copy of routing steps taken when a Work Order is released.
    Future changes to RoutingMaster do NOT affect existing WO snapshots.
    """
    __tablename__ = "wo_routing_snapshots"

    id              = db.Column(db.Integer, primary_key=True)
    work_order_id   = db.Column(db.String(36), db.ForeignKey("work_orders.id"), nullable=False)
    routing_id      = db.Column(db.Integer, db.ForeignKey("routing_master.id"), nullable=False)
    routing_code    = db.Column(db.String(64), nullable=False)
    routing_revision = db.Column(db.String(16), nullable=False)
    step_no         = db.Column(db.Integer, nullable=False)
    station_name    = db.Column(db.String(128), nullable=True)
    step_name       = db.Column(db.String(256), nullable=False)
    cycle_time      = db.Column(db.Float, nullable=True)
    qc_required     = db.Column(db.Boolean, default=False)
    mandatory       = db.Column(db.Boolean, default=True)
    rework_allowed  = db.Column(db.Boolean, default=True)
    remarks         = db.Column(db.Text, nullable=True)
    snapshot_at     = db.Column(db.DateTime, default=datetime.utcnow)

    work_order = db.relationship("WorkOrder", backref="routing_snapshots")
    routing    = db.relationship("RoutingMaster", backref="wo_snapshots")

    def to_dict(self):
        return {
            "id":               self.id,
            "work_order_id":    self.work_order_id,
            "routing_code":     self.routing_code,
            "routing_revision": self.routing_revision,
            "step_no":          self.step_no,
            "station_name":     self.station_name,
            "step_name":        self.step_name,
            "cycle_time":       self.cycle_time,
            "qc_required":      self.qc_required,
            "mandatory":        self.mandatory,
            "rework_allowed":   self.rework_allowed,
        }
