from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
from .. import db
from ..models import Die, DieFurnaceLog, DieRepairRecord
from sqlalchemy import func
import uuid

bp = Blueprint("dies_mgmt", __name__)


@bp.route("/dies")
def list_dies():
    status_counts = (
        db.session.query(Die.status, func.count(Die.id))
        .group_by(Die.status)
        .all()
    )
    counts = dict(status_counts)
    dies = Die.query.order_by(Die.die_code).all()
    return render_template("dies/list.html", dies=dies, counts=counts)


@bp.route("/dies/new", methods=["GET", "POST"])
def create_die():
    if request.method == "POST":
        die_code = request.form.get("die_code")
        if not die_code:
            flash("Die Code is required.", "error")
            return redirect(url_for("dies_mgmt.create_die"))
        die = Die(
            id=str(uuid.uuid4()),
            die_code=die_code,
            profile_code=request.form.get("profile_code"),
            alloy=request.form.get("alloy"),
            supplier=request.form.get("supplier") or request.form.get("manufacturer"),
            location=request.form.get("location") or "Store Rack A",
            status="Available",
            description=request.form.get("description"),
            die_type=request.form.get("die_type"),
            manufacturer=request.form.get("manufacturer"),
            press_count_limit=int(request.form.get("press_count_limit") or 0) or None,
            life_cycles_total=int(request.form.get("life_cycles_total") or 0),
        )
        db.session.add(die)
        db.session.commit()
        flash(f"Die {die.die_code} created.", "success")
        return redirect(url_for("dies_mgmt.detail", id=die.id))

    return render_template("dies/form.html", die=None)


@bp.route("/dies/<id>")
def detail(id):
    die = Die.query.get_or_404(id)
    furnace_logs = die.furnace_logs.order_by(DieFurnaceLog.started_at.desc()).limit(20).all()
    repair_records = die.repair_records.order_by(DieRepairRecord.performed_at.desc()).limit(20).all()
    press_pct = 0
    if die.press_count_limit and die.press_count_limit > 0:
        press_pct = min(100, round(100 * (die.press_count or 0) / die.press_count_limit))
    return render_template(
        "dies/detail.html",
        die=die,
        furnace_logs=furnace_logs,
        repair_records=repair_records,
        press_pct=press_pct,
    )


@bp.route("/dies/<id>/edit", methods=["GET", "POST"])
def update_die(id):
    die = Die.query.get_or_404(id)
    if request.method == "POST":
        die.profile_code = request.form.get("profile_code")
        die.alloy = request.form.get("alloy")
        die.supplier = request.form.get("supplier")
        die.location = request.form.get("location")
        die.description = request.form.get("description")
        die.die_type = request.form.get("die_type")
        die.manufacturer = request.form.get("manufacturer")
        lim = request.form.get("press_count_limit")
        die.press_count_limit = int(lim) if lim else None
        db.session.commit()
        flash("Die updated.", "success")
        return redirect(url_for("dies_mgmt.detail", id=die.id))
    return render_template("dies/form.html", die=die)


@bp.route("/dies/<id>/send-to-furnace", methods=["POST"])
def send_to_furnace(id):
    die = Die.query.get_or_404(id)
    die.status = "In_Furnace"
    log = DieFurnaceLog(
        id=str(uuid.uuid4()),
        die_id=die.id,
        furnace_id=request.form.get("furnace_id"),
        target_temp_celsius=float(request.form.get("target_temp_celsius") or 480),
        started_at=datetime.utcnow(),
        operator_id=request.form.get("operator_id") or "Operator",
        status="heating",
    )
    db.session.add(log)
    db.session.commit()
    flash("Die sent to furnace.", "success")
    return redirect(url_for("dies_mgmt.detail", id=die.id))


@bp.route("/dies/<id>/furnace-ready", methods=["POST"])
def furnace_ready(id):
    die = Die.query.get_or_404(id)
    open_log = (
        die.furnace_logs
        .filter(DieFurnaceLog.status != "aborted")
        .order_by(DieFurnaceLog.started_at.desc())
        .first()
    )
    if open_log:
        open_log.completed_at = datetime.utcnow()
        open_log.status = "ready"
        open_log.actual_temp_celsius = float(request.form.get("actual_temp_celsius") or open_log.target_temp_celsius)
        open_log.soak_time_minutes = int(request.form.get("soak_time_minutes") or 0)
    die.status = "Available"
    die.updated_at = datetime.utcnow()
    db.session.commit()
    flash("Die is ready and returned to store.", "success")
    return redirect(url_for("dies_mgmt.detail", id=die.id))


@bp.route("/dies/<id>/send-to-repair", methods=["POST"])
def send_to_repair(id):
    die = Die.query.get_or_404(id)
    die.status = "Repair"
    repair = DieRepairRecord(
        id=str(uuid.uuid4()),
        die_id=die.id,
        repair_type=request.form.get("repair_type") or "inspection",
        description=request.form.get("description"),
        performed_by=request.form.get("performed_by") or "Technician",
        performed_at=datetime.utcnow(),
        cost=float(request.form.get("cost") or 0) or None,
    )
    die.repair_count = (die.repair_count or 0) + 1
    db.session.add(repair)
    db.session.commit()
    flash("Die sent to repair.", "success")
    return redirect(url_for("dies_mgmt.detail", id=die.id))


@bp.route("/dies/<id>/retire", methods=["POST"])
def retire(id):
    die = Die.query.get_or_404(id)
    die.status = "Retired"
    db.session.commit()
    flash("Die retired.", "success")
    return redirect(url_for("dies_mgmt.detail", id=die.id))


@bp.route("/api/dies/status-summary")
def status_summary_json():
    counts = dict(db.session.query(Die.status, func.count(Die.id)).group_by(Die.status).all())
    return jsonify({
        "available": counts.get("Available", 0),
        "in_furnace": counts.get("In_Furnace", 0),
        "repair": counts.get("Repair", 0) + counts.get("Rework", 0),
        "in_press": counts.get("In_Press", 0),
    })
