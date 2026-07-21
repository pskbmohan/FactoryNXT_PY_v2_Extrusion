"""SPC Charts Dashboard - Statistical Process Control visualization.

This blueprint provides SPC chart visualizations with:
- X-bar and R control charts with UCL/LCL boundaries
- Cp/Cpk/Pp/Ppk capability indices display
- Control violation detection and alerts
- Capability trend analysis over time

Routes under /quality/spc/* per quality-buildplan.md requirement #14.
"""

from datetime import date, timedelta
from flask import Blueprint, render_template, request, jsonify
from sqlalchemy import func
from .. import db
from ..models import SPCRecord, WorkOrder
from ..services.spc_engine import SPCEngine

bp = Blueprint("spc_charts", __name__, url_prefix="/quality/spc")


@bp.route("/", methods=["GET"])
def index():
    """Main SPC dashboard with all capability indices and control charts overview."""
    # Get unique dimension types tracked
    dimension_types = db.session.query(
        func.distinct(SPCRecord.dimension_type)
    ).filter(SPCRecord.dimension_type.isnot(None)).all()
    dimension_types = [dt[0] for dt in dimension_types if dt[0]]

    # Get recent work orders with SPC data
    recent_wo_queries = (
        db.session.query(
            SPCRecord.wo_id,
            func.count(SPCRecord.id).label("measurement_count"),
            func.max(SPCRecord.sample_time).label("last_sample"),
            WorkOrder.order_number
        )
        .join(WorkOrder, SPCRecord.wo_id == WorkOrder.id)
        .group_by(SPCRecord.wo_id, WorkOrder.order_number)
        .order_by(func.max(SPCRecord.sample_time).desc())
        .limit(20)
        .all()
    )

    recent_work_orders = [
        {
            "wo_id": wo.wo_id,
            "order_number": wo.order_number,
            "measurement_count": wo.measurement_count,
            "last_sample_date": wo.last_sample.strftime("%Y-%m-%d") if wo.last_sample else None,
        }
        for wo in recent_wo_queries
    ]

    # Overall SPC summary statistics
    total_records = SPCRecord.query.count()
    out_of_control_count = SPCRecord.query.filter_by(out_of_control=True).count()

    return render_template(
        "quality/spc_charts/index.html",
        dimension_types=dimension_types,
        recent_work_orders=recent_work_orders,
        total_spc_records=total_records,
        out_of_control_count=out_of_control_count,
        selected_dimension=None,
        selected_wo_id=None,
    )


@bp.route("/overview/<wo_id>", methods=["GET"])
def wo_overview(wo_id):
    """Work order SPC overview with all dimension types."""
    try:
        wo_id = int(wo_id)
    except (ValueError, TypeError):
        return render_template("quality/spc_charts/error.html", error="Invalid work order ID"), 400

    # Get work order details
    work_order = WorkOrder.query.get(wo_id)
    if not work_order:
        return render_template("quality/spc_charts/error.html", error="Work order not found"), 404

    # Get all dimension types for this WO
    dimensions = db.session.query(SPCRecord.dimension_type).filter_by(wo_id=wo_id).distinct().all()
    dimensions = [d[0] for d in dimensions if d[0]]

    # Summary stats per dimension
    summary_data = []
    for dim_type in dimensions:
        records = SPCRecord.query.filter_by(wo_id=wo_id, dimension_type=dim_type).all()
        if not records:
            continue

        values = [r.measured_value for r in records]
        n = len(values)
        mean = sum(values) / n if n > 0 else 0
        variance = sum((x - mean) ** 2 for x in values) / (n - 1) if n > 1 else 0
        import math
        std_dev = math.sqrt(variance)

        # Get spec limits from first record
        upper_spec = records[0].upper_limit if records[0].upper_limit else None
        lower_spec = records[0].lower_limit if records[0].lower_limit else None

        summary_data.append({
            "dimension_type": dim_type,
            "measurement_count": n,
            "mean": round(mean, 4),
            "std_dev": round(std_dev, 4),
            "min_value": min(values),
            "max_value": max(values),
            "upper_spec_limit": upper_spec,
            "lower_spec_limit": lower_spec,
            "out_of_control_count": sum(1 for r in records if r.out_of_control),
        })

    return render_template(
        "quality/spc_charts/wo_overview.html",
        work_order=work_order,
        dimension_types=dimensions,
        summary_data=summary_data,
    )


@bp.route("/capability/<int:wo_id>", methods=["GET"])
def capability_view(wo_id):
    """Process capability analysis with Cp/Cpk/Pp/Ppk indices."""
    try:
        wo_id = int(wo_id)
    except (ValueError, TypeError):
        return render_template("quality/spc_charts/error.html", error="Invalid work order ID"), 400

    # Get work order details
    work_order = WorkOrder.query.get(wo_id)
    if not work_order:
        return render_template("quality/spc_charts/error.html", error="Work order not found"), 404

    dimension_type = request.args.get("dimension_type")

    # Compute capability indices using SPCEngine
    result = SPCEngine.compute_capability_indices(wo_id, dimension_type=dimension_type)

    if not result["success"]:
        return render_template("quality/spc_charts/error.html", error=result.get("error", "Computation failed")), 400

    # Get all dimensions for filter dropdown
    all_dimensions = db.session.query(SPCRecord.dimension_type).filter_by(wo_id=wo_id).distinct().all()
    all_dimensions = [d[0] for d in all_dimensions if d[0]]

    return render_template(
        "quality/spc_charts/capability.html",
        work_order=work_order,
        capability_result=result,
        dimension_type_filter=dimension_type or None,
        available_dimensions=all_dimensions,
    )


@bp.route("/control-charts/<int:wo_id>", methods=["GET"])
def control_charts_view(wo_id):
    """X-bar and R control charts with UCL/LCL boundaries."""
    try:
        wo_id = int(wo_id)
    except (ValueError, TypeError):
        return render_template("quality/spc_charts/error.html", error="Invalid work order ID"), 400

    # Get work order details
    work_order = WorkOrder.query.get(wo_id)
    if not work_order:
        return render_template("quality/spc_charts/error.html", error="Work order not found"), 404

    dimension_type = request.args.get("dimension_type")

    # Compute X-bar and R charts using SPCEngine
    result = SPCEngine.compute_xbar_r_charts(wo_id, dimension_type=dimension_type)

    if not result["success"]:
        return render_template("quality/spc_charts/error.html", error=result.get("error", "Computation failed")), 400

    # Get all dimensions for filter dropdown
    all_dimensions = db.session.query(SPCRecord.dimension_type).filter_by(wo_id=wo_id).distinct().all()
    all_dimensions = [d[0] for d in all_dimensions if d[0]]

    return render_template(
        "quality/spc_charts/control_charts.html",
        work_order=work_order,
        xbar_r_result=result,
        dimension_type_filter=dimension_type or None,
        available_dimensions=all_dimensions,
    )


@bp.route("/violations/<int:wo_id>", methods=["GET"])
def violations_view(wo_id):
    """Control violation detection dashboard."""
    try:
        wo_id = int(wo_id)
    except (ValueError, TypeError):
        return render_template("quality/spc_charts/error.html", error="Invalid work order ID"), 400

    # Get work order details
    work_order = WorkOrder.query.get(wo_id)
    if not work_order:
        return render_template("quality/spc_charts/error.html", error="Work order not found"), 404

    dimension_type = request.args.get("dimension_type")

    # Detect violations using SPCEngine
    result = SPCEngine.detect_control_violations(wo_id=wo_id)

    if dimension_type:
        # Filter violations by dimension type
        filtered_violations = []
        for v in result["violations"]:
            if v.get("dimension_type") == dimension_type:
                filtered_violations.append(v)
        result["violations"] = filtered_violations

    return render_template(
        "quality/spc_charts/violations.html",
        work_order=work_order,
        violations_result=result,
        dimension_type_filter=dimension_type or None,
    )


@bp.route("/trend/<int:wo_id>", methods=["GET"])
def trend_view(wo_id):
    """Capability trend analysis over time."""
    try:
        wo_id = int(wo_id)
    except (ValueError, TypeError):
        return render_template("quality/spc_charts/error.html", error="Invalid work order ID"), 400

    # Get work order details
    work_order = WorkOrder.query.get(wo_id)
    if not work_order:
        return render_template("quality/spc_charts/error.html", error="Work order not found"), 404

    dimension_type = request.args.get("dimension_type")
    days_back = int(request.args.get("days", 30))

    # Get capability trend using SPCEngine
    result = SPCEngine.get_capability_trend(wo_id, dimension_type=dimension_type, days_back=days_back)

    return render_template(
        "quality/spc_charts/trend.html",
        work_order=work_order,
        trend_result=result,
        dimension_type_filter=dimension_type or None,
        days_back=days_back,
    )


@bp.route("/api/capability/<int:wo_id>", methods=["GET"])
def api_capability(wo_id):
    """API endpoint for capability indices."""
    try:
        wo_id = int(wo_id)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid work order ID"}), 400

    dimension_type = request.args.get("dimension_type")
    result = SPCEngine.compute_capability_indices(wo_id, dimension_type=dimension_type)

    if not result["success"]:
        return jsonify(result), 400

    return jsonify(result)


@bp.route("/api/control-charts/<int:wo_id>", methods=["GET"])
def api_control_charts(wo_id):
    """API endpoint for X-bar and R chart data."""
    try:
        wo_id = int(wo_id)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid work order ID"}), 400

    dimension_type = request.args.get("dimension_type")
    result = SPCEngine.compute_xbar_r_charts(wo_id, dimension_type=dimension_type)

    if not result["success"]:
        return jsonify(result), 400

    return jsonify(result)


@bp.route("/api/violations/<int:wo_id>", methods=["GET"])
def api_violations(wo_id):
    """API endpoint for control violation detection."""
    try:
        wo_id = int(wo_id)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid work order ID"}), 400

    dimension_type = request.args.get("dimension_type")
    result = SPCEngine.detect_control_violations(wo_id=wo_id)

    if dimension_type:
        filtered_violations = [v for v in result["violations"] if v.get("dimension_type") == dimension_type]
        result["violations"] = filtered_violations

    return jsonify(result)


@bp.route("/dimensions", methods=["GET"])
def dimensions_list():
    """API endpoint listing all tracked dimension types."""
    dimension_types = db.session.query(
        func.distinct(SPCRecord.dimension_type)
    ).filter(SPCRecord.dimension_type.isnot(None)).all()

    return jsonify({
        "dimension_types": [dt[0] for dt in dimension_types if dt[0]],
        "total_count": len([dt for dt in dimension_types if dt[0]]),
    })


# Error handler template will be created with other templates
