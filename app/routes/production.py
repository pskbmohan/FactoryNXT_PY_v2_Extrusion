from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from .. import db
from ..models import WorkOrder, ProductionSchedule, OeeSnapshot, DowntimeEvent, SmtLine
from datetime import datetime, timedelta

bp = Blueprint("production", __name__, url_prefix="/production")


# ── Work Orders ──────────────────────────────────────────────────────────────────
@bp.route("/work-orders", methods=["GET"])
def work_order_list():
    status = request.args.get("status", "")
    q = WorkOrder.query
    if status:
        q = q.filter_by(status=status)
    orders = q.order_by(WorkOrder.due_date.asc()).all()
    return render_template("production/work_order_list.html", orders=orders, status=status)


def _parse_dt(s):
    """Parse a datetime string from the Gantt chart or HTML form.

    Accepts (in rough order of likelihood):
      - "2026-06-30T09:00:00"      ISO with T, seconds
      - "2026-06-30T09:00"         ISO with T, no seconds  (HTML form default)
      - "2026-06-30 09:00:00"      ISO with space, seconds (moment.js default)
      - "2026-06-30 09:00"         ISO with space, no seconds
      - "2026-06-30"               date-only
    Tolerates leading/trailing whitespace and trailing 'Z' (UTC marker).
    Returns None for anything it can't unambiguously parse.
    """
    if not s or not isinstance(s, str):
        return None
    s = s.strip().rstrip("Z").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


@bp.route("/work-orders/new", methods=["GET", "POST"])
def work_order_new():
    if request.method == "POST":
        import uuid
        scheduled_start = _parse_dt(request.form.get("scheduled_start"))
        scheduled_end = _parse_dt(request.form.get("scheduled_end"))
        wo = WorkOrder(
            id=str(uuid.uuid4()),
            order_number=request.form["wo_number"],
            part_number=request.form["part_number"],
            description=request.form.get("description"),
            quantity=int(request.form.get("quantity", 1)),
            priority=request.form.get("priority", "normal"),
            due_date=scheduled_end,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            status="DRAFT",
        )
        db.session.add(wo)
        db.session.commit()
        flash(f"Work order {wo.order_number} created as draft.", "success")
        return redirect(url_for("production.work_order_list"))
    return render_template("production/work_order_form.html")


@bp.route("/work-orders/<string:id>/status", methods=["POST"])
def work_order_status(id):
    wo = WorkOrder.query.get_or_404(id)
    new_status = request.form["status"]
    # Guard: RELEASED requires a schedule window — refuse with a clear message
    # so we never put a "released" WO onto the floor without dates.
    if new_status == "RELEASED" and (not wo.scheduled_start or not wo.scheduled_end):
        flash(f"WO {wo.order_number} cannot be released without scheduled start and end dates.", "error")
        return redirect(url_for("production.work_order_list"))
    wo.status = new_status
    if new_status == "RELEASED" and not wo.released_at:
        wo.released_at = datetime.utcnow()
    if new_status == "RUNNING" and not wo.started_at:
        wo.started_at = datetime.utcnow()
    if new_status == "COMPLETED" and not wo.completed_at:
        wo.completed_at = datetime.utcnow()
    db.session.commit()
    flash(f"WO {wo.order_number} status updated to '{new_status}'.", "success")
    return redirect(url_for("production.work_order_list"))


# ── Release shortcut (DRAFT -> RELEASED) ────────────────────────────────────────
# Distinct endpoint so the "Release" button on the list is a single explicit
# action that can't be accidentally fired from the general status dropdown.
@bp.route("/work-orders/<string:id>/release", methods=["POST"])
def work_order_release(id):
    wo = WorkOrder.query.get_or_404(id)
    if wo.status != "DRAFT":
        flash(f"WO {wo.order_number} is not in draft; cannot release.", "error")
        return redirect(url_for("production.work_order_list"))
    if not wo.scheduled_start or not wo.scheduled_end:
        flash(f"WO {wo.order_number} has no schedule window. Edit the order first.", "error")
        return redirect(url_for("production.work_order_list"))
    wo.status = "RELEASED"
    if not wo.released_at:
        wo.released_at = datetime.utcnow()
    db.session.commit()
    flash(f"WO {wo.order_number} released.", "success")
    return redirect(url_for("production.work_order_list"))


# ── Gantt / Scheduler ─────────────────────────────────────────────────────────
@bp.route("/gantt", methods=["GET"])
def gantt_board():
    # Summary table now reads schedule columns directly from WorkOrder.
    orders = (
        WorkOrder.query
        .filter(WorkOrder.scheduled_start.isnot(None))
        .order_by(WorkOrder.scheduled_start.asc())
        .all()
    )
    rows = []
    for o in orders:
        dur_hours = None
        if o.scheduled_start and o.scheduled_end:
            dur_hours = round((o.scheduled_end - o.scheduled_start).total_seconds() / 3600, 1)
        rows.append({
            "wo": o,
            "scheduled_start": o.scheduled_start,
            "scheduled_end": o.scheduled_end,
            "duration_hours": dur_hours,
        })
    return render_template("production/gantt_board.html", rows=rows)


@bp.route("/scheduler", methods=["GET"])
def scheduler():
    schedules = ProductionSchedule.query.order_by(ProductionSchedule.scheduled_start.asc()).all()
    lines = SmtLine.query.filter_by(is_active=True).all()
    return render_template("production/scheduler.html", schedules=schedules, lines=lines)


@bp.route("/scheduler/new", methods=["POST"])
def scheduler_new():
    import uuid
    sched = ProductionSchedule(
        id=str(uuid.uuid4()),
        plant_id=request.form.get("plant_id", "default"),
        wo_id=request.form["wo_id"],
        smt_line_id=request.form.get("smt_line_id"),
        scheduled_start=datetime.strptime(request.form["scheduled_start"], "%Y-%m-%dT%H:%M"),
        scheduled_end=datetime.strptime(request.form["scheduled_end"], "%Y-%m-%dT%H:%M"),
        sequence_order=int(request.form.get("sequence_order", 0)),
    )
    db.session.add(sched)
    db.session.commit()
    flash("Schedule entry added.", "success")
    return redirect(url_for("production.scheduler"))


# ── Plan vs Actual ───────────────────────────────────────────────────────────────
@bp.route("/plan-vs-actual", methods=["GET"])
def plan_vs_actual():
    rows = ProductionSchedule.query.order_by(
        ProductionSchedule.scheduled_start.desc()
    ).limit(100).all()
    return render_template("production/plan_vs_actual.html", rows=rows)


# ── OEE / Downtime ────────────────────────────────────────────────────────────────
@bp.route("/oee", methods=["GET"])
def oee_dashboard():
    snapshots = OeeSnapshot.query.order_by(OeeSnapshot.shift_date.desc()).limit(50).all()
    return render_template("production/oee_dashboard.html", snapshots=snapshots)


@bp.route("/downtime", methods=["GET"])
def downtime_log():
    events = DowntimeEvent.query.order_by(DowntimeEvent.started_at.desc()).limit(50).all()
    return render_template("production/downtime_log.html", events=events)


@bp.route("/production-floor", methods=["GET"])
def production_floor():
    return render_template("production/production_floor.html")


# ── API ────────────────────────────────────────────────────────────────────────
@bp.route("/api/work-orders", methods=["GET"])
def api_work_orders():
    orders = WorkOrder.query.all()
    return jsonify([{
        "id": o.id,
        "order_number": o.order_number,
        "part_number": o.part_number,
        "quantity": o.quantity,
        "status": o.status,
        "priority": o.priority,
        "due_date": o.due_date.isoformat() if o.due_date else None,
    } for o in orders])


# ── Gantt data for Frappe Gantt ────────────────────────────────────────────────
# Builds an array of tasks compatible with Frappe Gantt:
#   { id, name, start, end, status, priority, progress, dependencies, custom_class }
# Source of truth: WorkOrder.scheduled_start / scheduled_end.
# Skip orders with no schedule window (they won't appear on the chart).
@bp.route("/api/gantt-data", methods=["GET"])
def api_gantt_data():
    orders = WorkOrder.query.all()
    tasks = []
    for o in orders:
        start = o.scheduled_start
        end = o.scheduled_end
        if not start or not end:
            # Skip — WO has no schedule window and won't appear on the chart.
            continue
        if end <= start:
            end = start + timedelta(hours=8)

        # Progress from status lifecycle
        progress = 0
        if o.status == "RUNNING":
            progress = 50
        elif o.status == "COMPLETED":
            progress = 100
        elif o.status == "RELEASED":
            progress = 10

        # CSS class per priority/status for visual differentiation
        css_class = "gantt-task-default"
        if o.status == "COMPLETED":
            css_class = "gantt-task-completed"
        elif o.status == "RUNNING":
            css_class = "gantt-task-running"
        elif o.status == "RELEASED":
            css_class = "gantt-task-released"
        elif o.status == "CANCELLED":
            css_class = "gantt-task-cancelled"
        elif o.status == "DRAFT":
            css_class = "gantt-task-draft"
        elif o.priority == "urgent":
            css_class = "gantt-task-urgent"

        tasks.append({
            "id": o.id,
            "name": f"{o.order_number} · {o.part_number}",
            "start": start.strftime("%Y-%m-%d %H:%M:%S"),
            "end": end.strftime("%Y-%m-%d %H:%M:%S"),
            "status": o.status,
            "priority": o.priority or "normal",
            "progress": progress,
            "dependencies": "",
            "custom_class": css_class,
            "order_number": o.order_number,
            "part_number": o.part_number,
            "quantity": o.quantity,
            "due_date": o.due_date.strftime("%Y-%m-%d %H:%M") if o.due_date else None,
        })
    return jsonify(tasks)


# ── Summary table for the Gantt board ─────────────────────────────────────────
# JSON feed so the Schedule Summary table can be re-rendered without a full page
# reload — picked up by the Gantt page's refresh button, visibilitychange
# listener, and 30-second poll so WO status changes made elsewhere show here.
@bp.route("/api/gantt-summary", methods=["GET"])
def api_gantt_summary():
    orders = (
        WorkOrder.query
        .filter(WorkOrder.scheduled_start.isnot(None))
        .order_by(WorkOrder.scheduled_start.asc())
        .all()
    )
    rows = []
    for o in orders:
        dur = None
        if o.scheduled_start and o.scheduled_end:
            dur = round((o.scheduled_end - o.scheduled_start).total_seconds() / 3600, 1)
        rows.append({
            "id": o.id,
            "order_number": o.order_number,
            "part_number": o.part_number,
            "priority": o.priority or "normal",
            "scheduled_start": o.scheduled_start.strftime("%Y-%m-%d %H:%M") if o.scheduled_start else None,
            "scheduled_end": o.scheduled_end.strftime("%Y-%m-%d %H:%M") if o.scheduled_end else None,
            "status": o.status,
            "duration_hours": dur,
        })
    return jsonify({"rows": rows})


# ── Drag-to-reschedule sync with Gantt ────────────────────────────────────────
# Called by the Gantt chart's on_date_change / on_progress_change hooks.
# Persist the new schedule and force the WO back to DRAFT so the planner
# re-releases it. Returns the updated task payload so the client can re-apply it.
@bp.route("/api/work-orders/<string:id>/schedule", methods=["PATCH"])
def api_work_order_schedule(id):
    wo = WorkOrder.query.get_or_404(id)
    from flask import current_app

    # Parse the request body defensively — Frappe Gantt + fetch can land here
    # with Content-Type variations Flask's request.is_json doesn't always match.
    body = request.get_json(silent=True)
    if body is None:
        body = request.get_json(force=True, silent=True)
    if not body:
        body = request.form.to_dict()
    if not body:
        import json as _json
        try:
            raw = request.get_data(cache=False)
            if raw:
                body = _json.loads(raw)
        except Exception:
            body = {}

    current_app.logger.info(
        "gantt PATCH /api/work-orders/%s content_type=%s body=%r",
        id, request.content_type, body,
    )

    # Accept dates under either "scheduled_start/end" (canonical) or the
    # raw "start/end" keys Frappe Gantt hands to on_date_change.
    new_start = _parse_dt(body.get("scheduled_start")) or _parse_dt(body.get("start"))
    new_end = _parse_dt(body.get("scheduled_end")) or _parse_dt(body.get("end"))

    # Progress may arrive as a number, a numeric string, or 0 / "0".
    progress_raw = body.get("progress")
    progress_provided = progress_raw is not None and progress_raw != ""

    # If the client sent only one of the two dates (resize-only), fall back to
    # the WO's current window for the missing side rather than rejecting.
    if new_start is not None and new_end is None and wo.scheduled_end is not None:
        new_end = wo.scheduled_end
    if new_end is not None and new_start is None and wo.scheduled_start is not None:
        new_start = wo.scheduled_start

    dates_provided = new_start is not None and new_end is not None

    if not dates_provided and not progress_provided:
        return jsonify({
            "error": "scheduled_start and scheduled_end are required (or pass progress).",
            "received": body,
        }), 400
    if dates_provided and new_end <= new_start:
        return jsonify({"error": "scheduled_end must be after scheduled_start."}), 400

    if dates_provided:
        wo.scheduled_start = new_start
        wo.scheduled_end = new_end
        # Keep due_date in sync so legacy reports / list pages still make sense.
        wo.due_date = new_end

        # Downgrade to DRAFT unless the WO is already in a terminal/active state
        # that shouldn't be silently rewound (RUNNING, COMPLETED).
        if wo.status not in ("RUNNING", "COMPLETED"):
            wo.status = "DRAFT"
            wo.released_at = None

    if progress_provided:
        try:
            pct = int(float(progress_raw))
            pct = max(0, min(100, pct))
            if pct == 100:
                if not wo.completed_at:
                    wo.status = "COMPLETED"
                    wo.completed_at = datetime.utcnow()
        except (TypeError, ValueError):
            pass

    db.session.commit()

    return jsonify({
        "id": wo.id,
        "name": f"{wo.order_number} · {wo.part_number}",
        "start": wo.scheduled_start.strftime("%Y-%m-%d %H:%M:%S") if wo.scheduled_start else None,
        "end": wo.scheduled_end.strftime("%Y-%m-%d %H:%M:%S") if wo.scheduled_end else None,
        "status": wo.status,
        "priority": wo.priority or "normal",
        "order_number": wo.order_number,
        "part_number": wo.part_number,
        "quantity": wo.quantity,
        "due_date": wo.due_date.strftime("%Y-%m-%d %H:%M") if wo.due_date else None,
        "progress": 100 if wo.status == "COMPLETED" else (50 if wo.status == "RUNNING" else (10 if wo.status == "RELEASED" else 0)),
        "needs_release": wo.status == "DRAFT" and wo.scheduled_start is not None,
    })
