from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
from .. import db
from ..models import Furnace, HeatTreatmentProgram, FurnaceSession, Container, WorkOrder
import json
import uuid

bp = Blueprint("furnace", __name__)


@bp.route("/furnace")
def list_furnaces():
    furnaces = Furnace.query.order_by(Furnace.name).all()
    return render_template("furnace/list.html", furnaces=furnaces)


@bp.route("/furnace/programs")
def list_programs():
    programs = HeatTreatmentProgram.query.order_by(HeatTreatmentProgram.program_code).all()
    return render_template("furnace/programs.html", programs=programs)


@bp.route("/furnace/programs/new", methods=["GET", "POST"])
def create_program():
    if request.method == "POST":
        program_code = request.form.get("program_code")
        if not program_code:
            flash("Program Code is required.", "error")
            return redirect(url_for("furnace.create_program"))

        stages_json = request.form.get("stages_json") or "[]"
        try:
            stages = json.loads(stages_json)
        except Exception:
            stages = []
        total = sum(int(s.get("duration_min") or 0) for s in stages)

        prog = HeatTreatmentProgram(
            id=str(uuid.uuid4()),
            program_code=program_code,
            name=request.form.get("name") or program_code,
            alloy_code=request.form.get("alloy_code"),
            temper_designation=request.form.get("temper_designation"),
            stages=stages,
            total_duration_minutes=total,
        )
        db.session.add(prog)
        db.session.commit()
        flash(f"Program {prog.program_code} created.", "success")
        return redirect(url_for("furnace.list_programs"))

    return render_template("furnace/program_form.html", program=None)


@bp.route("/furnace/<id>")
def detail(id):
    furnace = Furnace.query.get_or_404(id)
    active_session = (
        furnace.sessions
        .filter(FurnaceSession.status.in_(["queued", "loading", "running"]))
        .first()
    )
    recent = furnace.sessions.order_by(FurnaceSession.created_at.desc()).limit(10).all()
    programs = HeatTreatmentProgram.query.order_by(HeatTreatmentProgram.name).all()
    containers = Container.query.filter_by(status="available").order_by(Container.container_code).all()
    work_orders = WorkOrder.query.filter(WorkOrder.status.in_(["RELEASED", "RUNNING"])).order_by(WorkOrder.order_number).all()
    return render_template(
        "furnace/detail.html",
        furnace=furnace,
        active_session=active_session,
        recent=recent,
        programs=programs,
        containers=containers,
        work_orders=work_orders,
    )


@bp.route("/furnace/<id>/start-session", methods=["POST"])
def start_session(id):
    furnace = Furnace.query.get_or_404(id)
    program_id = request.form.get("program_id")
    if not program_id:
        flash("Program is required to start a session.", "error")
        return redirect(url_for("furnace.detail", id=id))

    containers_json = request.form.get("loaded_containers_json") or "[]"
    try:
        loaded = json.loads(containers_json)
    except Exception:
        loaded = []

    program = HeatTreatmentProgram.query.get(program_id)
    session = FurnaceSession(
        id=str(uuid.uuid4()),
        furnace_id=id,
        program_id=program_id,
        wo_id=request.form.get("wo_id") or None,
        batch_reference=request.form.get("batch_reference"),
        loaded_containers=loaded,
        total_load_kg=float(request.form.get("total_load_kg") or 0) or None,
        status="running",
        current_stage_index=0,
        started_at=datetime.utcnow(),
        operator_id=request.form.get("operator_id") or "Operator",
    )
    if program and program.stages and len(program.stages) > 0:
        session.current_temp_celsius = program.stages[0].get("target_temp")
    furnace.status = "heating"
    furnace.current_program_id = program_id
    db.session.add(session)
    db.session.commit()
    flash("Furnace session started.", "success")
    return redirect(url_for("furnace.detail", id=id))


@bp.route("/furnace/sessions/<session_id>/advance-stage", methods=["POST"])
def advance_stage(session_id):
    session = FurnaceSession.query.get_or_404(session_id)
    program = HeatTreatmentProgram.query.get(session.program_id)
    if program and program.stages:
        if session.current_stage_index < len(program.stages) - 1:
            session.current_stage_index += 1
            next_stage = program.stages[session.current_stage_index]
            session.current_temp_celsius = next_stage.get("target_temp")
        else:
            session.status = "cooling"
    db.session.commit()
    flash("Advanced to next stage.", "success")
    return redirect(url_for("furnace.detail", id=session.furnace_id))


@bp.route("/furnace/sessions/<session_id>/log-temp", methods=["POST"])
def log_temp(session_id):
    session = FurnaceSession.query.get_or_404(session_id)
    temp = float(request.form.get("current_temp_celsius") or 0)
    session.current_temp_celsius = temp
    ts_log = session.temperature_log or []
    ts_log.append({"timestamp": datetime.utcnow().isoformat(), "temp": temp})
    session.temperature_log = ts_log
    db.session.commit()
    return jsonify({"ok": True, "temp": temp})


@bp.route("/furnace/sessions/<session_id>/complete", methods=["POST"])
def complete_session(session_id):
    session = FurnaceSession.query.get_or_404(session_id)
    session.status = "completed"
    session.completed_at = datetime.utcnow()
    session.result = request.form.get("result") or "PASS"
    furnace = Furnace.query.get(session.furnace_id)
    if furnace:
        furnace.status = "idle"
        furnace.current_program_id = None
    db.session.commit()
    flash("Furnace session completed.", "success")
    return redirect(url_for("furnace.detail", id=session.furnace_id))


@bp.route("/api/furnace/<id>/live-status")
def live_status(id):
    furnace = Furnace.query.get_or_404(id)
    session = (
        furnace.sessions
        .filter(FurnaceSession.status.in_(["running", "loading"]))
        .first()
    )
    data = {
        "furnace_code": furnace.furnace_code,
        "status": furnace.status,
        "current_temp_celsius": session.current_temp_celsius if session else None,
        "stage_index": session.current_stage_index if session else None,
        "temperature_log": (session.temperature_log or [])[-30:] if session else [],
    }
    if session and session.program:
        stages = session.program.stages or []
        total_min = session.program.total_duration_minutes or 0
        if total_min and session.started_at:
            elapsed = (datetime.utcnow() - session.started_at).total_seconds() / 60
            data["progress_pct"] = min(100, round(100 * elapsed / total_min))
        data["stage_count"] = len(stages)
    return jsonify(data)
