from flask import Blueprint, render_template, request
from datetime import datetime
from ..models import (
    Machine,
    PmSchedule,
    MaintenanceLog,
    CalibrationRecord,
    Stencil,
    TestResult,
    BurnInSession,
)

bp = Blueprint("machines", __name__)


@bp.route("/machines", methods=["GET"])
def dashboard():
    # Machine summary view
    machines = Machine.query.all()
    pm_due = PmSchedule.query.filter(PmSchedule.status != "Completed").all()
    recent_maint = MaintenanceLog.query.order_by(MaintenanceLog.performed_at.desc()).limit(10).all()
    return render_template(
        "machines/dashboard.html",
        machines=machines,
        pm_due=pm_due,
        recent_maint=recent_maint,
    )


@bp.route("/maintenance", methods=["GET"])
def maintenance():
    machine = request.args.get("machine")
    query = MaintenanceLog.query
    if machine:
        query = query.filter(MaintenanceLog.machine_id == machine)

    logs = query.order_by(MaintenanceLog.performed_at.desc()).limit(200).all()
    return render_template(
        "machines/maintenance.html",
        logs=logs,
        machine=machine or "",
    )


@bp.route("/pm", methods=["GET"])
def pm_schedule():
    status = request.args.get("status", "all")
    query = PmSchedule.query
    if status != "all":
        query = query.filter(PmSchedule.status == status)

    schedules = query.order_by(PmSchedule.due_at.asc().nullslast()).all()
    return render_template(
        "machines/pm.html",
        schedules=schedules,
        status=status,
    )


@bp.route("/calibration", methods=["GET"])
def calibration():
    machine = request.args.get("machine")
    query = CalibrationRecord.query
    if machine:
        query = query.filter(CalibrationRecord.machine_id == machine)

    records = query.order_by(CalibrationRecord.performed_at.desc()).limit(200).all()
    return render_template(
        "machines/calibration.html",
        records=records,
        machine=machine or "",
    )


@bp.route("/stencils", methods=["GET"])
def stencils():
    part = request.args.get("part")
    query = Stencil.query
    if part:
        query = query.filter(Stencil.part_number == part)

    stencils = query.order_by(Stencil.part_number.asc()).all()
    return render_template(
        "machines/stencils.html",
        stencils=stencils,
        part=part or "",
    )


@bp.route("/test-results", methods=["GET"])
def test_results():
    wo = request.args.get("wo")
    test_type = request.args.get("type")

    query = TestResult.query
    if wo:
        query = query.filter(TestResult.wo_id == wo)
    if test_type:
        query = query.filter(TestResult.test_type == test_type)

    results = query.order_by(TestResult.tested_at.desc()).limit(200).all()
    return render_template(
        "machines/test_results.html",
        results=results,
        wo=wo or "",
        test_type=test_type or "",
    )


@bp.route("/burn-in", methods=["GET"])
def burn_in():
    status = request.args.get("status", "all")
    query = BurnInSession.query
    if status != "all":
        query = query.filter(BurnInSession.status == status)

    sessions = query.order_by(BurnInSession.started_at.desc().nullslast()).all()
    return render_template(
        "machines/burn_in.html",
        sessions=sessions,
        status=status,
    )


@bp.route("/connectivity", methods=["GET"])
def connectivity():
    """Machine Connectivity Hub - Real-time telemetry and state monitoring."""
    machines = Machine.query.all()
    return render_template(
        "machines/connectivity.html",
        machines=machines,
    )
