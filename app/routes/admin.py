import uuid
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash

from .. import db
from ..models import (
    AlertRule,
    Machine,
    Plant,
    Role,
    UserProfile,
    AuditLog,
    OperatorCertification,
    ElectronicSignature,
    MaterialGrade,
    SetpointProfile,
)

bp = Blueprint("admin", __name__)


@bp.route("/admin", methods=["GET"])
def admin_dashboard():
    plant_count = Plant.query.count()
    user_count = UserProfile.query.count()
    role_count = Role.query.count()
    recent_audit = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(10).all()
    alert_rules_active = AlertRule.query.filter_by(is_active=True).count()

    return render_template(
        "admin/dashboard.html",
        plant_count=plant_count,
        user_count=user_count,
        role_count=role_count,
        recent_audit=recent_audit,
        alert_rules_active=alert_rules_active,
    )


@bp.route("/admin/plants", methods=["GET"])
def plants():
    plants = Plant.query.order_by(Plant.code.asc()).all()
    return render_template("admin/plants.html", plants=plants)


@bp.route("/admin/users", methods=["GET"])
def users():
    plant_id = request.args.get("plant")
    role_id = request.args.get("role")

    query = UserProfile.query
    if plant_id:
        query = query.filter(UserProfile.plant_id == plant_id)
    if role_id:
        query = query.filter(UserProfile.role_id == role_id)

    users = query.order_by(UserProfile.full_name.asc()).all()
    roles = Role.query.order_by(Role.display_name.asc()).all()
    plants = Plant.query.order_by(Plant.code.asc()).all()

    return render_template(
        "admin/users.html",
        users=users,
        roles=roles,
        plants=plants,
        plant_id=plant_id or "",
        role_id=role_id or "",
    )


@bp.route("/admin/roles", methods=["GET"])
def roles():
    roles = Role.query.order_by(Role.display_name.asc()).all()
    return render_template("admin/roles.html", roles=roles)


@bp.route("/admin/audit", methods=["GET"])
def audit_log():
    table_name = request.args.get("table")

    query = AuditLog.query
    if table_name:
        query = query.filter(AuditLog.table_name == table_name)

    entries = query.order_by(AuditLog.created_at.desc()).limit(200).all()
    return render_template(
        "admin/audit_log.html",
        entries=entries,
        table_name=table_name or "",
    )


@bp.route("/admin/certifications", methods=["GET"])
def certifications():
    user_id = request.args.get("user")

    query = OperatorCertification.query
    if user_id:
        query = query.filter(OperatorCertification.user_id == user_id)

    certs = query.order_by(OperatorCertification.certified_at.desc()).limit(200).all()
    return render_template(
        "admin/certifications.html",
        certs=certs,
        user_id=user_id or "",
    )


@bp.route("/admin/esignatures", methods=["GET"])
def esignatures():
    record_type = request.args.get("type")

    query = ElectronicSignature.query
    if record_type:
        query = query.filter(ElectronicSignature.record_type == record_type)

    sigs = query.order_by(ElectronicSignature.signed_at.desc()).limit(200).all()
    return render_template(
        "admin/esignatures.html",
        sigs=sigs,
        record_type=record_type or "",
    )


# ── Thresholds management (wraps AlertRule) ──────────────────────────────────
@bp.route("/admin/thresholds", methods=["GET"])
def thresholds():
    """Manage alert thresholds for KPIs and planning metrics."""
    rules = AlertRule.query.order_by(AlertRule.created_at.desc()).all()
    return render_template(
        "admin/thresholds.html",
        rules=rules,
    )


@bp.route("/admin/thresholds/new", methods=["POST"])
def thresholds_new():
    """Create a new alert threshold rule."""
    name = request.form.get("name", "").strip()
    if not name:
        flash("Rule name is required.", "error")
        return redirect(url_for("admin.thresholds"))

    operator = request.form.get("operator", "GT").upper()
    threshold_value = {}
    if operator == "BETWEEN":
        threshold_value = {
            "low": float(request.form.get("low") or 0),
            "high": float(request.form.get("high") or 0),
        }
    else:
        try:
            threshold_value = {"value": float(request.form.get("threshold_value") or 0)}
        except (TypeError, ValueError):
            threshold_value = {"value": 0}

    rule = AlertRule(
        id=str(uuid.uuid4()),
        name=name,
        metric=request.form.get("metric", "OEE"),
        operator=operator,
        threshold_value=threshold_value,
        severity=request.form.get("severity", "WARNING"),
        is_active="is_active" in request.form,
    )
    db.session.add(rule)
    db.session.commit()
    flash(f"Threshold rule '{rule.name}' created.", "success")
    return redirect(url_for("admin.thresholds"))


@bp.route("/admin/thresholds/<string:id>/toggle", methods=["POST"])
def thresholds_toggle(id):
    """Toggle a threshold rule's active status."""
    rule = AlertRule.query.get_or_404(id)
    rule.is_active = not rule.is_active
    db.session.commit()
    flash(
        f"Rule '{rule.name}' {'enabled' if rule.is_active else 'disabled'}.",
        "success",
    )
    return redirect(url_for("admin.thresholds"))


# ── Machine master ───────────────────────────────────────────────────────────
@bp.route("/admin/machine-master", methods=["GET"])
def machine_master():
    """List all machines with their maintenance and calibration status."""
    machines = Machine.query.order_by(Machine.name.asc()).all()
    return render_template(
        "admin/machine_master.html",
        machines=machines,
    )


@bp.route("/admin/machine-master/new", methods=["POST"])
def machine_master_new():
    """Register a new machine."""
    name = request.form.get("name", "").strip()
    if not name:
        flash("Machine name is required.", "error")
        return redirect(url_for("admin.machine_master"))

    machine = Machine(
        line_id=int(request.form.get("line_id", 1)),
        name=name,
        status=request.form.get("status", "Idle"),
    )
    db.session.add(machine)
    db.session.commit()
    flash(f"Machine '{machine.name}' registered.", "success")
    return redirect(url_for("admin.machine_master"))


# ── Process params ───────────────────────────────────────────────────────────
@bp.route("/admin/process-params", methods=["GET"])
def process_params():
    """List material grades and setpoint profiles."""
    grades = MaterialGrade.query.order_by(MaterialGrade.code.asc()).all()
    profiles = SetpointProfile.query.order_by(
        SetpointProfile.process_type.asc(),
        SetpointProfile.alloy.asc(),
    ).all()
    return render_template(
        "admin/process_params.html",
        grades=grades,
        profiles=profiles,
    )


@bp.route("/admin/process-params/grade-new", methods=["POST"])
def process_params_grade_new():
    """Add a new material grade."""
    code = request.form.get("code", "").strip()
    if not code:
        flash("Material grade code is required.", "error")
        return redirect(url_for("admin.process_params"))

    if MaterialGrade.query.filter_by(code=code).first():
        flash(f"Material grade '{code}' already exists.", "error")
        return redirect(url_for("admin.process_params"))

    grade = MaterialGrade(
        id=str(uuid.uuid4()),
        code=code,
        name=request.form.get("name", ""),
        alloy_family=request.form.get("alloy_family"),
        density=float(request.form.get("density") or 0) or None,
        melting_point=float(request.form.get("melting_point") or 0) or None,
    )
    db.session.add(grade)
    db.session.commit()
    flash(f"Material grade '{grade.code}' added.", "success")
    return redirect(url_for("admin.process_params"))


@bp.route("/admin/process-params/profile-new", methods=["POST"])
def process_params_profile_new():
    """Add a new setpoint profile."""
    process_type = request.form.get("process_type", "").strip()
    if not process_type:
        flash("Process type is required.", "error")
        return redirect(url_for("admin.process_params"))

    # Accept parameters as JSON string
    import json
    params_raw = request.form.get("parameters", "{}")
    try:
        params = json.loads(params_raw) if params_raw else {}
    except (json.JSONDecodeError, ValueError):
        params = {}

    profile = SetpointProfile(
        id=str(uuid.uuid4()),
        process_type=process_type,
        alloy=request.form.get("alloy"),
        profile_code=request.form.get("profile_code"),
        parameters=params,
        version=int(request.form.get("version") or 1),
        is_active="is_active" in request.form,
    )
    db.session.add(profile)
    db.session.commit()
    flash(f"Setpoint profile for {profile.process_type}/{profile.alloy} added.", "success")
    return redirect(url_for("admin.process_params"))
