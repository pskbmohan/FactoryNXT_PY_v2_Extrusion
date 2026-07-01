from flask import Blueprint, render_template, request, jsonify
from datetime import datetime
from .. import db
from ..models import (
    WorkOrder, RoutingStep, Station, SerialNumber,
    OperationTransaction, UserProfile
)

bp = Blueprint("operations", __name__)


# ─────────────────────────────────────────────
# PAGE ROUTE
# ─────────────────────────────────────────────

@bp.route("/operations")
def index():
    """Operation Execution Screen — main page."""
    return render_template("operations/index.html")


# ─────────────────────────────────────────────
# API: Work Orders (RELEASED or RUNNING)
# ─────────────────────────────────────────────

@bp.route("/api/operations/work-orders")
def get_work_orders():
    """Return work orders that are RELEASED or RUNNING."""
    wos = WorkOrder.query.filter(
        WorkOrder.status.in_(["RELEASED", "RUNNING"])
    ).all()
    return jsonify([
        {
            "id": wo.id,
            "order_number": wo.order_number,
            "part_number": wo.part_number,
            "quantity": wo.quantity,
            "status": wo.status,
        }
        for wo in wos
    ])


# ─────────────────────────────────────────────
# API: Stations for a Work Order (routing-filtered)
# ─────────────────────────────────────────────

@bp.route("/api/operations/stations/<wo_id>")
def get_stations_for_wo(wo_id):
    """Return only stations that appear in the WO routing."""
    wo = WorkOrder.query.get_or_404(wo_id)
    routing_steps = RoutingStep.query.filter_by(
        part_number=wo.part_number
    ).order_by(RoutingStep.operation_sequence).all()

    station_names = [s.station_name for s in routing_steps if s.station_name]
    stations = Station.query.filter(
        Station.name.in_(station_names),
        Station.is_active == True,
    ).all()

    return jsonify([
        {
            "id": s.id,
            "name": s.name,
            "code": s.code,
        }
        for s in stations
    ])


# ─────────────────────────────────────────────
# API: Release WO — generate serial numbers
# ─────────────────────────────────────────────

@bp.route("/api/operations/work-orders/<wo_id>/release", methods=["POST"])
def release_work_order(wo_id):
    """
    Release a Work Order:
    - Change status DRAFT -> RELEASED
    - Generate serial numbers based on WO quantity
    Format: <order_number>-<zero-padded-seq>
    """
    wo = WorkOrder.query.get_or_404(wo_id)

    if wo.status != "DRAFT":
        return jsonify({"error": f"Work Order is already {wo.status}. Only DRAFT orders can be released."}), 400

    # Generate serial numbers
    width = len(str(wo.quantity))
    for i in range(1, wo.quantity + 1):
        sn = SerialNumber(
            work_order_id=wo.id,
            serial_number=f"{wo.order_number}-{str(i).zfill(max(width, 5))}",
            current_step=None,
            current_status="PENDING",
        )
        db.session.add(sn)

    wo.status = "RELEASED"
    wo.released_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        "message": f"Work Order {wo.order_number} released. {wo.quantity} serial numbers generated.",
        "status": wo.status,
    })


# ─────────────────────────────────────────────
# CORE: Scan Validation & Operation Execution
# ─────────────────────────────────────────────

@bp.route("/api/operations/scan", methods=["POST"])
def scan_serial():
    """
    Scan a serial number at a station and submit an operation result.

    Expected JSON body:
    {
        "serial_number": "WO240001-00001",
        "station_id": 3,
        "operator_id": "OP-001",
        "result": "OK" | "NG",
        "remarks": "optional text"
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    serial_no = data.get("serial_number", "").strip()
    station_id = data.get("station_id")
    operator_id = data.get("operator_id", "").strip()
    result = data.get("result", "").upper()
    remarks = data.get("remarks", "")

    if not all([serial_no, station_id, operator_id, result]):
        return jsonify({"error": "serial_number, station_id, operator_id, and result are required"}), 400

    if result not in ("OK", "NG"):
        return jsonify({"error": "result must be OK or NG"}), 400

    # ── Lookup serial number record
    sn_rec = SerialNumber.query.filter_by(serial_number=serial_no).first()
    if not sn_rec:
        return jsonify({"error": f"Serial number '{serial_no}' not found"}), 404

    wo = WorkOrder.query.get(sn_rec.work_order_id)
    if not wo:
        return jsonify({"error": "Work Order not found for this serial number"}), 404

    # ── Get station
    station = Station.query.get(station_id)
    if not station:
        return jsonify({"error": "Station not found"}), 404

    # ── Get routing for this WO's part number, ordered by sequence
    routing = RoutingStep.query.filter_by(
        part_number=wo.part_number
    ).order_by(RoutingStep.operation_sequence).all()

    if not routing:
        return jsonify({"error": "No routing defined for this part number"}), 400

    # ── Find which routing step corresponds to the selected station
    current_step = None
    for step in routing:
        if step.station_name == station.name:
            current_step = step
            break

    if not current_step:
        return jsonify({"error": f"Station '{station.name}' is not part of the routing for WO {wo.order_number}"}), 400

    first_step = routing[0]
    is_first_step = (current_step.operation_sequence == first_step.operation_sequence)

    # ── VALIDATION RULES ──
    if is_first_step:
        # First operation: WO must be RELEASED or RUNNING, SN must not have been processed
        if wo.status not in ("RELEASED", "RUNNING"):
            return jsonify({"error": f"Work Order status is '{wo.status}'. First operation requires RELEASED or RUNNING status."}), 400

        existing = OperationTransaction.query.filter_by(
            serial_number=serial_no,
            routing_step=current_step.operation_sequence,
        ).first()
        if existing:
            return jsonify({"error": f"Serial number '{serial_no}' has already been processed at the first routing step."}), 400
    else:
        # Subsequent operations: previous step must be completed with OK
        step_index = next(i for i, s in enumerate(routing) if s.operation_sequence == current_step.operation_sequence)
        prev_step = routing[step_index - 1]

        prev_history = OperationTransaction.query.filter_by(
            serial_number=serial_no,
            routing_step=prev_step.operation_sequence,
        ).order_by(OperationTransaction.created_at.desc()).first()

        if prev_history is None:
            return jsonify({
                "error": "Previous operation not completed.",
                "required_step": prev_step.operation_sequence,
                "required_station": prev_step.station_name,
            }), 400

        if prev_history.result != "OK":
            return jsonify({
                "error": "Previous operation is not approved. Cannot continue processing.",
                "previous_result": prev_history.result,
                "required_step": prev_step.operation_sequence,
            }), 400

    # ── ALLOW: Record the operation transaction
    now = datetime.utcnow()
    tx = OperationTransaction(
        work_order_id=wo.id,
        serial_number=serial_no,
        routing_step=current_step.operation_sequence,
        station_id=station.id,
        operator_id=operator_id,
        start_time=now,
        end_time=now,
        result=result,
        remarks=remarks,
    )
    db.session.add(tx)

    # ── Update serial number current step and status
    sn_rec.current_step = current_step.operation_sequence
    if result == "OK":
        sn_rec.current_status = "IN_PROGRESS"
    else:
        sn_rec.current_status = "REJECTED"

    # ── WO Status Transitions
    if is_first_step and wo.status == "RELEASED":
        wo.status = "RUNNING"
        wo.started_at = now

    # ── Check COMPLETED: all SNs finished the last step with OK
    last_step = routing[-1]
    if current_step.operation_sequence == last_step.operation_sequence and result == "OK":
        sn_rec.current_status = "COMPLETED"
        # Check if all serial numbers for this WO have completed the final step with OK
        all_sns = SerialNumber.query.filter_by(work_order_id=wo.id).all()
        all_completed = all(s.current_status == "COMPLETED" for s in all_sns)
        if all_completed:
            wo.status = "COMPLETED"
            wo.completed_at = now

    db.session.commit()

    return jsonify({
        "message": "Operation recorded successfully.",
        "serial_number": serial_no,
        "routing_step": current_step.operation_sequence,
        "operation_name": current_step.operation_name,
        "result": result,
        "wo_status": wo.status,
    })


# ─────────────────────────────────────────────
# API: Serial Numbers for a Work Order
# ─────────────────────────────────────────────

@bp.route("/api/operations/serial-numbers/<wo_id>")
def get_serial_numbers(wo_id):
    """List all serial numbers and their current status for a given WO."""
    sns = SerialNumber.query.filter_by(work_order_id=wo_id).order_by(
        SerialNumber.serial_number
    ).all()
    return jsonify([
        {
            "id": s.id,
            "serial_number": s.serial_number,
            "current_step": s.current_step,
            "current_status": s.current_status,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in sns
    ])


# ─────────────────────────────────────────────
# API: Operation History for a Serial Number
# ─────────────────────────────────────────────

@bp.route("/api/operations/history/<path:serial_number>")
def get_operation_history(serial_number):
    """Full operation history (audit trail) for a serial number."""
    txns = OperationTransaction.query.filter_by(
        serial_number=serial_number
    ).order_by(OperationTransaction.created_at.asc()).all()

    if not txns:
        return jsonify({"message": "No operation history found.", "history": []})

    return jsonify({
        "serial_number": serial_number,
        "history": [
            {
                "id": t.id,
                "work_order_id": t.work_order_id,
                "routing_step": t.routing_step,
                "station_id": t.station_id,
                "operator_id": t.operator_id,
                "start_time": t.start_time.isoformat() if t.start_time else None,
                "end_time": t.end_time.isoformat() if t.end_time else None,
                "result": t.result,
                "remarks": t.remarks,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in txns
        ],
    })
