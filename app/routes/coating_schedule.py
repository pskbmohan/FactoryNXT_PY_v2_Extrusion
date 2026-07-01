from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
from .. import db
from ..models import CoatingColor, CoatingScheduleEntry, WorkOrder
import uuid

bp = Blueprint("coating_schedule", __name__)


@bp.route("/coating-schedule")
def list_entries():
    entries = (
        CoatingScheduleEntry.query
        .order_by(CoatingScheduleEntry.scheduled_start.asc().nullslast())
        .all()
    )
    colors = CoatingColor.query.order_by(CoatingColor.color_code).all()
    # Group by color for wheel view
    grouped = {}
    for e in entries:
        key = e.color.color_name if e.color else "Uncolored"
        grouped.setdefault(key, []).append(e)
    return render_template("coating_schedule/list.html", entries=entries, colors=colors, grouped=grouped)


@bp.route("/coating-schedule/new", methods=["GET", "POST"])
def create_entry():
    if request.method == "POST":
        wo_id = request.form.get("wo_id")
        color_id = request.form.get("color_id")
        if not wo_id:
            flash("Work Order is required.", "error")
            return redirect(url_for("coating_schedule.create_entry"))

        entry = CoatingScheduleEntry(
            id=str(uuid.uuid4()),
            wo_id=wo_id,
            coating_line_id=request.form.get("coating_line_id"),
            color_id=color_id or None,
            color_group_sequence=int(request.form.get("color_group_sequence") or 1),
            scheduled_start=_parse_dt(request.form.get("scheduled_start")),
            scheduled_end=_parse_dt(request.form.get("scheduled_end")),
            powder_quantity_kg=float(request.form.get("powder_quantity_kg") or 0) or None,
            status="planned",
        )
        db.session.add(entry)
        db.session.commit()
        flash("Coating schedule entry created.", "success")
        return redirect(url_for("coating_schedule.list_entries"))

    work_orders = WorkOrder.query.filter(WorkOrder.status.in_(["RELEASED", "RUNNING"])).order_by(WorkOrder.order_number).all()
    colors = CoatingColor.query.order_by(CoatingColor.color_code).all()
    return render_template("coating_schedule/form.html", work_orders=work_orders, colors=colors, entry=None)


def _parse_dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


@bp.route("/coating-schedule/<id>/start", methods=["POST"])
def start(id):
    entry = CoatingScheduleEntry.query.get_or_404(id)
    entry.actual_start = datetime.utcnow()
    entry.status = "running"
    db.session.commit()
    flash("Coating job started.", "success")
    return redirect(url_for("coating_schedule.list_entries"))


@bp.route("/coating-schedule/<id>/complete", methods=["POST"])
def complete(id):
    entry = CoatingScheduleEntry.query.get_or_404(id)
    entry.actual_end = datetime.utcnow()
    entry.status = "completed"
    entry.actual_powder_used_kg = float(request.form.get("actual_powder_used_kg") or 0) or None
    db.session.commit()
    flash("Coating job completed.", "success")
    return redirect(url_for("coating_schedule.list_entries"))


@bp.route("/coating-schedule/gantt")
def gantt():
    entries = CoatingScheduleEntry.query.filter(
        CoatingScheduleEntry.scheduled_start.isnot(None)
    ).order_by(CoatingScheduleEntry.scheduled_start).all()
    data = []
    for e in entries:
        data.append({
            "id": e.id,
            "wo": e.work_order.order_number if e.work_order else "",
            "color": e.color.color_name if e.color else "Uncolored",
            "hex": e.color.hex_value if e.color else "#cccccc",
            "start": e.scheduled_start.isoformat() if e.scheduled_start else None,
            "end": e.scheduled_end.isoformat() if e.scheduled_end else None,
            "status": e.status,
        })
    return jsonify(data)


@bp.route("/api/coating-schedule/powder-savings")
def powder_savings():
    """Estimate cleaning time saved by grouping colors vs naive ordering."""
    entries = CoatingScheduleEntry.query.filter(
        CoatingScheduleEntry.scheduled_start.isnot(None)
    ).order_by(CoatingScheduleEntry.scheduled_start).all()
    if not entries:
        return jsonify({"clean_time_saved_min": 0, "entries": 0})

    # Naive: every consecutive pair = cleanup time
    naive_time = 0
    from ..models import CoatingColor
    for i in range(1, len(entries)):
        color_a = entries[i - 1].color_id
        color_b = entries[i].color_id
        if color_a != color_b:
            c = CoatingColor.query.get(color_b) if color_b else None
            naive_time += (c.clean_time_minutes if c else 30)

    # Grouped: only cleanup when color changes (entries already sorted by color grouping)
    grouped_time = 0
    prev_color = None
    for e in entries:
        if e.color_id and e.color_id != prev_color and prev_color is not None:
            grouped_time += (e.color.clean_time_minutes if e.color else 30)
        prev_color = e.color_id

    return jsonify({
        "clean_time_saved_min": max(0, naive_time - grouped_time),
        "naive_cleaning_min": naive_time,
        "grouped_cleaning_min": grouped_time,
        "entries": len(entries),
    })
