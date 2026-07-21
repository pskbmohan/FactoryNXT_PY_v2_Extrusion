"""End-to-End Traceability Viewer Dashboard.

This blueprint provides material traceability tracking from raw materials through customer delivery:
- Heat number and batch number tracking
- Billet to die association tracking
- Work order linkage with process parameters
- Customer order connection for forward traceability
- Root cause analysis support for complaints

Routes under /quality/traceability/* per quality-buildplan.md requirement #13.
"""

from datetime import date, timedelta
from flask import Blueprint, render_template, request, jsonify
from sqlalchemy import func, or_
from .. import db
from ..models import (
    MaterialTraceability, SPCRecord, QualityInspection, TestEvent, WorkOrder,
    ProcessRun, Die, Billet, CustomerOrderLine
)

bp = Blueprint("traceability_viewer", __name__, url_prefix="/quality/traceability")


@bp.route("/", methods=["GET"])
def index():
    """Main traceability dashboard with search and tracking overview."""
    # Search parameters
    batch_number = request.args.get("batch")
    heat_number = request.args.get("heat")
    billet_code = request.args.get("billet")
    die_code = request.args.get("die")
    wo_order_number = request.args.get("wo")

    # Build search query
    query = MaterialTraceability.query

    if batch_number:
        query = query.filter(MaterialTraceability.batch_number.ilike(f"%{batch_number}%"))
    if heat_number:
        query = query.filter(MaterialTraceability.heat_number.ilike(f"%{heat_number}%"))
    if billet_code:
        query = query.filter(MaterialTraceability.billet_code.ilike(f"%{billet_code}%"))
    if die_code:
        query = query.filter(MaterialTraceability.die_code.ilike(f"%{die_code}%"))

    # Filter by work order number (join with WorkOrder)
    if wo_order_number:
        wo_subquery = (
            db.session.query(WorkOrder.id)
            .filter(WorkOrder.order_number.ilike(f"%{wo_order_number}%"))
            .subquery()
        )
        query = query.filter(MaterialTraceability.work_order_id == wo_subquery.c.id)

    # Execute search and get results with work order details
    trace_records = (
        query.join(WorkOrder, MaterialTraceability.work_order_id == WorkOrder.id)
        .order_by(MaterialTraceability.extrusion_timestamp.desc())
        .limit(100)
        .all()
    )

    # Get summary statistics
    total_traces = MaterialTraceability.query.count()

    recent_batches = (
        db.session.query(
            MaterialTraceability.batch_number,
            func.count(MaterialTraceability.id).label("trace_count"),
            func.max(MaterialTraceability.extrusion_timestamp).label("last_extrusion")
        )
        .group_by(MaterialTraceability.batch_number)
        .order_by(func.max(MaterialTraceability.extrusion_timestamp).desc())
        .limit(10)
        .all()
    )

    return render_template(
        "quality/traceability_viewer/index.html",
        trace_records=trace_records,
        total_traces=total_traces,
        recent_batches=recent_batches,
        search_params={
            "batch": batch_number or "",
            "heat": heat_number or "",
            "billet": billet_code or "",
            "die": die_code or "",
            "wo": wo_order_number or "",
        },
    )


@bp.route("/trace/<trace_id>", methods=["GET"])
def trace_detail(trace_id):
    """Detailed view of a single material traceability record."""
    try:
        trace_record = MaterialTraceability.query.get(trace_id)
    except ValueError:
        return render_template("quality/traceability_viewer/error.html", error="Invalid trace ID"), 400

    if not trace_record:
        return render_template("quality/traceability_viewer/error.html", error="Trace record not found"), 404

    # Get linked work order details
    work_order = WorkOrder.query.get(trace_record.work_order_id)

    # Get SPC data for this trace (same work order, same time period)
    extrusion_date = trace_record.extrusion_timestamp.date() if trace_record.extrusion_timestamp else None
    spc_records = []
    if extrusion_date:
        start_time = extrusion_date.replace(hour=0, minute=0, second=0)
        end_time = extrusion_date.replace(hour=23, minute=59, second=59)

        spc_records = (
            SPCRecord.query.filter(
                SPCRecord.wo_id == trace_record.work_order_id,
                SPCRecord.sample_time >= start_time,
                SPCRecord.sample_time <= end_time
            )
            .order_by(SPCRecord.sample_number)
            .all()
        )

    # Get quality inspections for this work order
    inspections = (
        QualityInspection.query.filter_by(wo_id=trace_record.work_order_id)
        .order_by(QualityInspection.timestamp.desc())
        .limit(20)
        .all()
    )

    # Get test events for this work order
    tests = (
        TestEvent.query.filter_by(wo_id=trace_record.work_order_id)
        .order_by(TestEvent.tested_at.desc())
        .limit(20)
        .all()
    )

    return render_template(
        "quality/traceability_viewer/trace_detail.html",
        trace_record=trace_record,
        work_order=work_order,
        spc_records=spc_records,
        inspections=inspections,
        tests=tests,
    )


@bp.route("/forward/<batch_number>", methods=["GET"])
def forward_trace(batch_number):
    """Forward traceability - find all customer orders associated with a batch."""
    # Find the batch record(s)
    batch_records = MaterialTraceability.query.filter(
        MaterialTraceability.batch_number.ilike(f"%{batch_number}%")
    ).all()

    if not batch_records:
        return render_template("quality/traceability_viewer/error.html", error="Batch number not found"), 404

    # Collect all customer order line IDs from the batches
    customer_order_lines = set()
    for record in batch_records:
        if record.customer_order_line_id:
            customer_order_lines.add(record.customer_order_line_id)

    # Get associated orders
    customer_orders = []
    for col_id in customer_order_lines:
        col = CustomerOrderLine.query.get(col_id)
        if col and col.order_number:
            customer_orders.append({
                "order_number": col.order_number,
                "line_id": col.id,
                "quantity_ordered": str(col.quantity),
            })

    return render_template(
        "quality/traceability_viewer/forward_trace.html",
        batch_records=batch_records,
        associated_orders=customer_orders,
        search_batch=batch_number,
    )


@bp.route("/backward/<wo_id>", methods=["GET"])
def backward_trace(wo_id):
    """Backward traceability - find all raw materials used for a work order."""
    try:
        wo_id = int(wo_id)
    except (ValueError, TypeError):
        return render_template("quality/traceability_viewer/error.html", error="Invalid work order ID"), 400

    # Get the trace records for this work order
    trace_records = MaterialTraceability.query.filter_by(work_order_id=wo_id).all()

    if not trace_records:
        return render_template("quality/traceability_viewer/error.html", error="No trace data found for this work order"), 404

    # Get all unique billets and dies used
    billets = []
    dies = []

    for record in trace_records:
        if record.billet_code:
            billets.append({
                "billet_code": record.billet_code,
                "heat_number": record.heat_number or "Unknown",
                "batch_number": record.batch_number,
            })
        if record.die_code:
            dies.append({
                "die_code": record.die_code,
                "batch_number": record.batch_number,
            })

    # Get work order details
    work_order = WorkOrder.query.get(wo_id)

    return render_template(
        "quality/traceability_viewer/backward_trace.html",
        work_order=work_order,
        trace_records=trace_records,
        unique_billets=billets,
        unique_dies=dies,
    )


@bp.route("/complaint/<wo_id>", methods=["GET"])
def complaint_investigation(wo_id):
    """Root cause analysis support for customer complaints."""
    try:
        wo_id = int(wo_id)
    except (ValueError, TypeError):
        return render_template("quality/traceability_viewer/error.html", error="Invalid work order ID"), 400

    # Get the trace records for this work order
    trace_records = MaterialTraceability.query.filter_by(work_order_id=wo_id).all()

    if not trace_records:
        return render_template("quality/traceability_viewer/error.html", error="No trace data found for this work order"), 404

    # Get SPC capability analysis for the work order
    spc_data = {}
    try:
        from ..services.spc_engine import SPCEngine
        cap_result = SPCEngine.compute_capability_indices(wo_id)
        if cap_result["success"]:
            spc_data["capability"] = cap_result["capability_indices"]
            spc_data["interpretation"] = cap_result.get("interpretation", {})

        viol_result = SPCEngine.detect_control_violations(wo_id=wo_id)
        spc_data["violations_count"] = viol_result["total_violations"]
    except Exception as e:
        spc_data["error"] = str(e)

    # Get quality inspection summary for this work order
    inspections = QualityInspection.query.filter_by(wo_id=wo_id).all()
    inspection_summary = {
        "total_inspections": len(inspections),
        "passed": sum(1 for i in inspections if i.pass_fail == 'PASS'),
        "failed": sum(1 for i in inspections if i.pass_fail == 'FAIL'),
        "pending": sum(1 for i in inspections if i.pass_fail == 'PENDING'),
    }

    # Get test results summary
    tests = TestEvent.query.filter_by(wo_id=wo_id).all()
    test_summary = {
        "total_tests": len(tests),
        "passed": sum(1 for t in tests if t.passed is True),
        "failed": sum(1 for t in tests if t.passed is False),
        "pending": sum(1 for t in tests if t.passed is None),
    }

    return render_template(
        "quality/traceability_viewer/complaint_investigation.html",
        trace_records=trace_records,
        work_order=WorkOrder.query.get(wo_id),
        spc_data=spc_data,
        inspection_summary=inspection_summary,
        test_summary=test_summary,
    )


@bp.route("/api/search", methods=["GET"])
def api_search():
    """API endpoint for traceability search."""
    batch_number = request.args.get("batch")
    heat_number = request.args.get("heat")
    billet_code = request.args.get("billet")
    die_code = request.args.get("die")

    query = MaterialTraceability.query

    if batch_number:
        query = query.filter(MaterialTraceability.batch_number.ilike(f"%{batch_number}%"))
    if heat_number:
        query = query.filter(MaterialTraceability.heat_number.ilike(f"%{heat_number}%"))
    if billet_code:
        query = query.filter(MaterialTraceability.billet_code.ilike(f"%{billet_code}%"))
    if die_code:
        query = query.filter(MaterialTraceability.die_code.ilike(f"%{die_code}%"))

    results = []
    for record in query.limit(50).all():
        work_order = WorkOrder.query.get(record.work_order_id)
        results.append({
            "trace_id": str(record.id),
            "batch_number": record.batch_number,
            "heat_number": record.heat_number,
            "billet_code": record.billet_code,
            "die_code": record.die_code,
            "order_number": work_order.order_number if work_order else None,
            "extrusion_date": record.extrusion_timestamp.isoformat() if record.extrusion_timestamp else None,
        })

    return jsonify({
        "total_results": len(results),
        "results": results,
    })


@bp.route("/api/trace/<trace_id>", methods=["GET"])
def api_trace_detail(trace_id):
    """API endpoint for detailed trace record."""
    try:
        trace_record = MaterialTraceability.query.get(trace_id)
    except ValueError:
        return jsonify({"error": "Invalid trace ID"}), 400

    if not trace_record:
        return jsonify({"error": "Record not found"}), 404

    work_order = WorkOrder.query.get(trace_record.work_order_id)

    return jsonify({
        "trace_id": str(trace_record.id),
        "batch_number": trace_record.batch_number,
        "heat_number": trace_record.heat_number,
        "billet_code": trace_record.billet_code,
        "die_code": trace_record.die_code,
        "work_order_id": str(trace_record.work_order_id),
        "order_number": work_order.order_number if work_order else None,
        "extrusion_timestamp": trace_record.extrusion_timestamp.isoformat() if trace_record.extrusion_timestamp else None,
        "customer_order_line_id": trace_record.customer_order_line_id,
        "shipment_batch_id": trace_record.shipment_batch_id,
        "status": trace_record.status,
    })


@bp.route("/api/forward/<batch_number>", methods=["GET"])
def api_forward_trace(batch_number):
    """API endpoint for forward traceability."""
    batch_records = MaterialTraceability.query.filter(
        MaterialTraceability.batch_number.ilike(f"%{batch_number}%")
    ).all()

    customer_order_lines = set()
    for record in batch_records:
        if record.customer_order_line_id:
            customer_order_lines.add(record.customer_order_line_id)

    orders = []
    for col_id in customer_order_lines:
        col = CustomerOrderLine.query.get(col_id)
        if col and col.order_number:
            orders.append({
                "order_number": col.order_number,
                "line_id": str(col.id),
                "quantity_ordered": str(col.quantity),
            })

    return jsonify({
        "batch_number": batch_number,
        "trace_records_found": len(batch_records),
        "associated_customer_orders": orders,
    })


@bp.route("/api/backward/<wo_id>", methods=["GET"])
def api_backward_trace(wo_id):
    """API endpoint for backward traceability."""
    try:
        wo_id = int(wo_id)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid work order ID"}), 400

    trace_records = MaterialTraceability.query.filter_by(work_order_id=wo_id).all()

    raw_materials = []
    for record in trace_records:
        raw_materials.append({
            "batch_number": record.batch_number,
            "heat_number": record.heat_number,
            "billet_code": record.billet_code,
            "die_code": record.die_code,
        })

    return jsonify({
        "work_order_id": wo_id,
        "trace_records_found": len(trace_records),
        "raw_materials_used": raw_materials,
    })


@bp.route("/dimensions", methods=["GET"])
def dimensions_list():
    """API endpoint listing all tracked dimension types in SPC data."""
    from sqlalchemy import func

    dimension_types = db.session.query(
        func.distinct(SPCRecord.dimension_type)
    ).filter(SPCRecord.dimension_type.isnot(None)).all()

    return jsonify({
        "dimension_types": [dt[0] for dt in dimension_types if dt[0]],
        "total_count": len([dt for dt in dimension_types if dt[0]]),
    })
