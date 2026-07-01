"""Visual Routing Builder routes for FactoryNXT.

Blueprint: routing_builder
URL prefix: none (flat)
"""
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, jsonify
)
from .. import db
from ..models import Station, WorkOrder
from ..models_routing import (
    RoutingMaster, RoutingStepV2, RoutingConnection,
    RoutingProductAssignment, WorkOrderRoutingSnapshot
)
from datetime import datetime
import copy

bp = Blueprint("routing_builder", __name__)


# ─────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────

NEXT_REVISION = {
    "A": "B", "B": "C", "C": "D", "D": "E", "E": "F",
    "F": "G", "G": "H", "H": "I", "I": "J", "J": "K",
}


def _next_rev(rev):
    return NEXT_REVISION.get(rev.upper(), rev + "1")


def _validate_routing(routing_id):
    """Return list of validation error strings (empty = valid)."""
    errors = []
    steps = RoutingStepV2.query.filter_by(routing_id=routing_id).all()
    conns = RoutingConnection.query.filter_by(routing_id=routing_id).all()

    if not steps:
        errors.append("Routing has no steps defined.")
        return errors

    # Duplicate step numbers
    step_nos = [s.step_no for s in steps]
    if len(step_nos) != len(set(step_nos)):
        errors.append("Duplicate step numbers found.")

    # All station IDs must exist
    station_ids = {s.station_id for s in steps if s.station_id}
    existing_ids = {s.id for s in Station.query.filter(Station.id.in_(station_ids)).all()}
    missing = station_ids - existing_ids
    if missing:
        errors.append(f"Station IDs not found: {missing}")

    # With >1 step, at least one connection must exist
    if len(steps) > 1 and not conns:
        errors.append("Steps are not connected. Add connections between steps.")

    # Circular routing detection (simple DFS)
    step_ids = {s.id for s in steps}
    adj = {sid: [] for sid in step_ids}
    for c in conns:
        if c.from_step in adj:
            adj[c.from_step].append(c.to_step)

    visited, rec_stack = set(), set()

    def dfs(node):
        visited.add(node)
        rec_stack.add(node)
        for nbr in adj.get(node, []):
            if nbr not in visited:
                if dfs(nbr):
                    return True
            elif nbr in rec_stack:
                return True
        rec_stack.discard(node)
        return False

    for sid in step_ids:
        if sid not in visited:
            if dfs(sid):
                errors.append("Circular routing loop detected.")
                break

    # At least one start step (no incoming connections)
    to_steps = {c.to_step for c in conns}
    starts = [s for s in steps if s.id not in to_steps]
    if not starts:
        errors.append("No start step found (every step has incoming connections).")

    # At least one end step (no outgoing connections)
    from_steps = {c.from_step for c in conns}
    ends = [s for s in steps if s.id not in from_steps]
    if not ends:
        errors.append("No end step found (every step has outgoing connections).")

    return errors


# ─────────────────────────────────────────────────
# UI Routes
# ─────────────────────────────────────────────────

@bp.route("/routing/design/manage", methods=["GET"])
def manage_routings():
    """Routing Management list page."""
    search = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "")
    query = RoutingMaster.query
    if search:
        query = query.filter(
            db.or_(
                RoutingMaster.routing_code.ilike(f"%{search}%"),
                RoutingMaster.routing_name.ilike(f"%{search}%"),
                RoutingMaster.product_id.ilike(f"%{search}%"),
            )
        )
    if status_filter:
        query = query.filter_by(status=status_filter)
    routings = query.order_by(RoutingMaster.routing_code, RoutingMaster.revision).all()
    return render_template(
        "routing_builder/manage.html",
        routings=routings,
        search=search,
        status_filter=status_filter,
    )


@bp.route("/routing/design/new", methods=["GET", "POST"])
def create_routing():
    """Create new routing header."""
    if request.method == "POST":
        routing_code = request.form.get("routing_code", "").strip().upper()
        routing_name = request.form.get("routing_name", "").strip()
        product_id   = request.form.get("product_id", "").strip().upper()
        revision     = request.form.get("revision", "A").strip().upper()
        description  = request.form.get("description", "").strip()

        if not routing_code or not routing_name:
            flash("Routing Code and Name are required.", "error")
            return redirect(url_for("routing_builder.create_routing"))

        # Check uniqueness of code+revision
        exists = RoutingMaster.query.filter_by(
            routing_code=routing_code, revision=revision
        ).first()
        if exists:
            flash(f"Routing {routing_code} Rev {revision} already exists.", "error")
            return redirect(url_for("routing_builder.create_routing"))

        routing = RoutingMaster(
            routing_code=routing_code,
            routing_name=routing_name,
            product_id=product_id or None,
            revision=revision,
            description=description,
            status="DRAFT",
            created_by="system",
        )
        db.session.add(routing)
        db.session.commit()
        flash(f"Routing {routing_code} Rev {revision} created.", "success")
        return redirect(url_for("routing_builder.designer", routing_id=routing.id))

    return render_template("routing_builder/create.html")


@bp.route("/routing/design/builder/<int:routing_id>", methods=["GET"])
def designer(routing_id):
    """Visual routing designer canvas page."""
    routing = RoutingMaster.query.get_or_404(routing_id)
    stations = Station.query.filter_by(is_active=True).order_by(Station.name).all()
    steps = RoutingStepV2.query.filter_by(routing_id=routing_id).order_by(RoutingStepV2.step_no).all()
    return render_template(
        "routing_builder/designer.html",
        routing=routing,
        stations=stations,
        steps=steps,
    )


@bp.route("/routing/design/builder/<int:routing_id>/save", methods=["POST"])
def save_routing(routing_id):
    """Save canvas data (steps + connections) from Drawflow JSON."""
    routing = RoutingMaster.query.get_or_404(routing_id)

    if routing.status == "RELEASED":
        return jsonify({"ok": False, "error": "Released routing cannot be edited directly. Clone it to create a new revision."}), 400

    data = request.get_json(force=True)
    canvas_data   = data.get("canvas_data", {})
    steps_payload = data.get("steps", [])
    conns_payload = data.get("connections", [])

    # Validate step numbers
    step_nos = [s.get("step_no") for s in steps_payload]
    if len(step_nos) != len(set(step_nos)):
        return jsonify({"ok": False, "error": "Duplicate step numbers detected."}), 400

    # Delete existing steps + connections
    RoutingConnection.query.filter_by(routing_id=routing_id).delete()
    RoutingStepV2.query.filter_by(routing_id=routing_id).delete()
    db.session.flush()

    # Re-create steps
    node_id_to_step = {}  # node_id -> RoutingStepV2
    for s in steps_payload:
        station = None
        if s.get("station_id"):
            station = Station.query.get(s["station_id"])
        step = RoutingStepV2(
            routing_id=routing_id,
            step_no=int(s["step_no"]),
            station_id=station.id if station else None,
            step_name=s.get("step_name", ""),
            cycle_time=s.get("cycle_time") or None,
            operator_skill=s.get("operator_skill") or None,
            parallel=bool(s.get("parallel", False)),
            qc_required=bool(s.get("qc_required", False)),
            mandatory=bool(s.get("mandatory", True)),
            rework_allowed=bool(s.get("rework_allowed", True)),
            remarks=s.get("remarks") or None,
            node_id=s.get("node_id"),
            pos_x=s.get("pos_x"),
            pos_y=s.get("pos_y"),
        )
        db.session.add(step)
        db.session.flush()
        if s.get("node_id"):
            node_id_to_step[s["node_id"]] = step

    # Re-create connections using node_ids
    for c in conns_payload:
        from_step_obj = node_id_to_step.get(c.get("from_node_id"))
        to_step_obj   = node_id_to_step.get(c.get("to_node_id"))
        if from_step_obj and to_step_obj:
            conn = RoutingConnection(
                routing_id=routing_id,
                from_step=from_step_obj.id,
                to_step=to_step_obj.id,
            )
            db.session.add(conn)

    routing.canvas_data = canvas_data
    routing.updated_at  = datetime.utcnow()
    db.session.commit()

    return jsonify({"ok": True, "message": "Routing saved successfully."})


@bp.route("/routing/design/clone/<int:routing_id>", methods=["POST"])
def clone_routing(routing_id):
    """Clone a routing to create a new revision."""
    source = RoutingMaster.query.get_or_404(routing_id)
    new_rev = _next_rev(source.revision)

    # Check new revision doesn't exist
    exists = RoutingMaster.query.filter_by(
        routing_code=source.routing_code, revision=new_rev
    ).first()
    if exists:
        flash(f"Revision {new_rev} already exists for {source.routing_code}.", "error")
        return redirect(url_for("routing_builder.manage_routings"))

    new_routing = RoutingMaster(
        routing_code=source.routing_code,
        routing_name=source.routing_name,
        product_id=source.product_id,
        revision=new_rev,
        description=source.description,
        status="DRAFT",
        created_by="system",
        canvas_data=copy.deepcopy(source.canvas_data),
    )
    db.session.add(new_routing)
    db.session.flush()

    # Copy steps
    old_to_new = {}
    for step in source.steps:
        new_step = RoutingStepV2(
            routing_id=new_routing.id,
            step_no=step.step_no,
            station_id=step.station_id,
            step_name=step.step_name,
            cycle_time=step.cycle_time,
            operator_skill=step.operator_skill,
            parallel=step.parallel,
            qc_required=step.qc_required,
            mandatory=step.mandatory,
            rework_allowed=step.rework_allowed,
            remarks=step.remarks,
            node_id=step.node_id,
            pos_x=step.pos_x,
            pos_y=step.pos_y,
        )
        db.session.add(new_step)
        db.session.flush()
        old_to_new[step.id] = new_step.id

    # Copy connections
    for conn in source.connections:
        if conn.from_step in old_to_new and conn.to_step in old_to_new:
            new_conn = RoutingConnection(
                routing_id=new_routing.id,
                from_step=old_to_new[conn.from_step],
                to_step=old_to_new[conn.to_step],
            )
            db.session.add(new_conn)

    db.session.commit()
    flash(f"Cloned to {new_routing.routing_code} Rev {new_rev}.", "success")
    return redirect(url_for("routing_builder.designer", routing_id=new_routing.id))


@bp.route("/routing/design/<int:routing_id>/status", methods=["POST"])
def change_status(routing_id):
    """Change routing status: DRAFT -> RELEASED or RELEASED -> OBSOLETE."""
    routing = RoutingMaster.query.get_or_404(routing_id)
    new_status = request.form.get("status", "").upper()

    allowed_transitions = {
        "DRAFT":    ["RELEASED"],
        "RELEASED": ["OBSOLETE"],
        "OBSOLETE": [],
    }
    if new_status not in allowed_transitions.get(routing.status, []):
        flash(f"Cannot transition from {routing.status} to {new_status}.", "error")
        return redirect(url_for("routing_builder.manage_routings"))

    # Before releasing, validate
    if new_status == "RELEASED":
        errors = _validate_routing(routing_id)
        if errors:
            flash("Validation failed: " + " | ".join(errors), "error")
            return redirect(url_for("routing_builder.designer", routing_id=routing_id))

    routing.status = new_status
    routing.updated_at = datetime.utcnow()
    db.session.commit()
    flash(f"Routing {routing.routing_code} Rev {routing.revision} is now {new_status}.", "success")
    return redirect(url_for("routing_builder.manage_routings"))


@bp.route("/routing/design/<int:routing_id>/assign", methods=["GET", "POST"])
def assign_routing(routing_id):
    """Assign routing to a product."""
    routing = RoutingMaster.query.get_or_404(routing_id)
    if request.method == "POST":
        product_id = request.form.get("product_id", "").strip().upper()
        if not product_id:
            flash("Product / Part Number is required.", "error")
            return redirect(url_for("routing_builder.assign_routing", routing_id=routing_id))
        # Deactivate old assignment for same product
        RoutingProductAssignment.query.filter_by(
            product_id=product_id, is_active=True
        ).update({"is_active": False})
        assignment = RoutingProductAssignment(
            product_id=product_id,
            routing_id=routing_id,
            assigned_by="system",
            is_active=True,
        )
        db.session.add(assignment)
        db.session.commit()
        flash(f"Routing assigned to {product_id}.", "success")
        return redirect(url_for("routing_builder.manage_routings"))

    assignments = RoutingProductAssignment.query.filter_by(
        routing_id=routing_id
    ).order_by(RoutingProductAssignment.assigned_at.desc()).all()
    return render_template(
        "routing_builder/assign.html",
        routing=routing,
        assignments=assignments,
    )


@bp.route("/routing/design/<int:routing_id>/history")
def routing_history(routing_id):
    """Show all revisions of the same routing code."""
    routing = RoutingMaster.query.get_or_404(routing_id)
    history = RoutingMaster.query.filter_by(
        routing_code=routing.routing_code
    ).order_by(RoutingMaster.revision).all()
    return render_template(
        "routing_builder/history.html",
        current=routing,
        history=history,
    )


# ─────────────────────────────────────────────────
# REST API
# ─────────────────────────────────────────────────

@bp.route("/api/routings", methods=["GET"])
def api_list_routings():
    status = request.args.get("status")
    q = RoutingMaster.query
    if status:
        q = q.filter_by(status=status.upper())
    routings = q.order_by(RoutingMaster.routing_code, RoutingMaster.revision).all()
    return jsonify([r.to_dict() for r in routings])


@bp.route("/api/routing", methods=["POST"])
def api_create_routing():
    data = request.get_json(force=True)
    routing_code = data.get("routing_code", "").strip().upper()
    routing_name = data.get("routing_name", "").strip()
    if not routing_code or not routing_name:
        return jsonify({"error": "routing_code and routing_name are required"}), 400
    routing = RoutingMaster(
        routing_code=routing_code,
        routing_name=routing_name,
        product_id=data.get("product_id"),
        revision=data.get("revision", "A").upper(),
        description=data.get("description"),
        status="DRAFT",
        created_by=data.get("created_by", "api"),
    )
    db.session.add(routing)
    db.session.commit()
    return jsonify(routing.to_dict()), 201


@bp.route("/api/routing/design/<int:routing_id>", methods=["GET"])
def api_get_routing(routing_id):
    routing = RoutingMaster.query.get_or_404(routing_id)
    result = routing.to_dict()
    result["steps"]       = [s.to_dict() for s in routing.steps]
    result["connections"] = [c.to_dict() for c in routing.connections]
    return jsonify(result)


@bp.route("/api/routing/design/<int:routing_id>", methods=["PUT"])
def api_update_routing(routing_id):
    routing = RoutingMaster.query.get_or_404(routing_id)
    if routing.status == "RELEASED":
        return jsonify({"error": "Released routing is read-only."}), 400
    data = request.get_json(force=True)
    for field in ["routing_name", "product_id", "description"]:
        if field in data:
            setattr(routing, field, data[field])
    routing.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(routing.to_dict())


@bp.route("/api/routing/design/<int:routing_id>", methods=["DELETE"])
def api_delete_routing(routing_id):
    routing = RoutingMaster.query.get_or_404(routing_id)
    if routing.status == "RELEASED":
        return jsonify({"error": "Cannot delete a released routing."}), 400
    db.session.delete(routing)
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/api/stations", methods=["GET"])
def api_stations():
    stations = Station.query.filter_by(is_active=True).order_by(Station.name).all()
    return jsonify([
        {"id": s.id, "name": s.name, "code": s.code, "description": s.description}
        for s in stations
    ])


@bp.route("/api/routing/design/validate", methods=["POST"])
def api_validate_routing():
    data = request.get_json(force=True)
    routing_id = data.get("routing_id")
    if not routing_id:
        return jsonify({"error": "routing_id required"}), 400
    errors = _validate_routing(int(routing_id))
    return jsonify({"valid": len(errors) == 0, "errors": errors})


@bp.route("/api/routing/design/<int:routing_id>/copy-to-wo/<string:wo_id>", methods=["POST"])
def api_copy_to_wo(routing_id, wo_id):
    """Freeze routing snapshot into a Work Order (called on WO release)."""
    routing = RoutingMaster.query.get_or_404(routing_id)
    wo = WorkOrder.query.get_or_404(wo_id)

    # Validate before freezing
    errors = _validate_routing(routing_id)
    if errors:
        return jsonify({"ok": False, "errors": errors}), 400

    # Delete any existing snapshot for this WO
    WorkOrderRoutingSnapshot.query.filter_by(work_order_id=wo_id).delete()

    for step in routing.steps:
        snap = WorkOrderRoutingSnapshot(
            work_order_id=wo_id,
            routing_id=routing_id,
            routing_code=routing.routing_code,
            routing_revision=routing.revision,
            step_no=step.step_no,
            station_name=step.station.name if step.station else None,
            step_name=step.step_name,
            cycle_time=step.cycle_time,
            qc_required=step.qc_required,
            mandatory=step.mandatory,
            rework_allowed=step.rework_allowed,
            remarks=step.remarks,
        )
        db.session.add(snap)

    db.session.commit()
    return jsonify({"ok": True, "steps_frozen": len(routing.steps)})
