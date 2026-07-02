"""KPI & Alerts blueprint.

Consolidates OEE-style metrics for extrusion with threshold-based
alerting and sync-failure / planning-risk alerts.
"""

import uuid
from datetime import datetime, date

from flask import (
    Blueprint,
    render_template,
    session,
    redirect,
    url_for,
    request,
    flash,
)
from .. import db
from ..models import (
    Alert,
    AlertRule,
    DowntimeEvent,
    KPIRecord,
    Machine,
    NitridingRecord,
    OeeSnapshot,
    ProcessRun,
)
from ..services.kpi_engine import KPIEngine

bp = Blueprint("kpi_alerts", __name__, template_folder="../templates/kpi_alerts")


# ── Dashboard ────────────────────────────────────────────────────────────────
@bp.route("/kpi-alerts")
def index():
    if "username" not in session:
        return redirect(url_for("auth.login"))

    recent_kpis = (
        KPIRecord.query.order_by(KPIRecord.calculated_at.desc()).limit(50).all()
    )
    open_alerts = Alert.query.filter_by(status="Open").order_by(
        Alert.created_at.desc()
    ).limit(20).all()
    machines = Machine.query.order_by(Machine.name.asc()).all()

    # Compute demo-view KPIs from recent_kpis (latest value per type)
    oee = 0.0
    throughput_kg_h = 0.0
    rejection_pct = 0.0
    avg_die_cycles = 0
    downtime_min = 0
    for kpi in recent_kpis:
        if kpi.kpi_type == "OEE" and oee == 0.0:
            oee = float(kpi.value or 0) / 100.0
        elif kpi.kpi_type == "THROUGHPUT" and throughput_kg_h == 0.0:
            throughput_kg_h = float(kpi.value or 0)
        elif kpi.kpi_type == "REJECTION_RATE" and rejection_pct == 0.0:
            rejection_pct = float(kpi.value or 0)
        elif kpi.kpi_type == "DIE_LIFETIME" and avg_die_cycles == 0:
            avg_die_cycles = int(float(kpi.value or 0))
        elif kpi.kpi_type == "MACHINE_DOWNTIME" and downtime_min == 0:
            downtime_min = int(float(kpi.value or 0))

    alerts = open_alerts
    critical_alerts_count = sum(
        1 for a in open_alerts if a.severity in ("CRITICAL", "HIGH")
    )

    return render_template(
        "kpi_alerts/index.html",
        recent_kpis=recent_kpis,
        open_alerts=open_alerts,
        machines=machines,
        username=session.get("username"),
        oee=oee,
        throughput_kg_h=throughput_kg_h,
        rejection_pct=rejection_pct,
        avg_die_cycles=avg_die_cycles,
        downtime_min=downtime_min,
        alerts=alerts,
        critical_alerts_count=critical_alerts_count,
    )


@bp.route("/kpi-alerts/oee")
def oee():
    if "username" not in session:
        return redirect(url_for("auth.login"))

    machines = Machine.query.order_by(Machine.name.asc()).all()
    selected = request.args.get("machine_id")
    shift_date = request.args.get("shift_date") or request.args.get("date")

    # Compute on demand if requested
    if request.args.get("compute") == "1" and selected and shift_date:
        try:
            result = KPIEngine.compute_oee(selected, shift_date)
            flash(f"OEE computed for machine {selected}: {result.get('oee')}%.", "success")
        except Exception as exc:
            flash(f"OEE compute failed: {exc}", "error")

    # Build per-machine OEE rows from records
    rows = []
    oee_records = (
        KPIRecord.query.filter_by(kpi_type="OEE")
        .order_by(KPIRecord.calculated_at.desc())
        .limit(200)
        .all()
        if not selected
        else KPIRecord.query.filter_by(kpi_type="OEE", machine_id=selected)
        .order_by(KPIRecord.calculated_at.desc())
        .limit(200)
        .all()
    )

    # Index OEE records by machine
    oee_by_machine = {}
    for rec in oee_records:
        if rec.machine_id not in oee_by_machine:
            oee_by_machine[rec.machine_id] = rec

    for m in machines:
        rec = oee_by_machine.get(m.id)
        if rec:
            v = float(rec.value or 0) / 100.0
            availability = v
            performance = v
            quality = 1.0
            if hasattr(rec, "value_details") and rec.value_details:
                # Use sub-fields when provided
                availability = float(rec.value_details.get("availability", v))
                performance = float(rec.value_details.get("performance", v))
                quality = float(rec.value_details.get("quality", 1.0))
            oee_val = availability * performance * quality
        else:
            # Fallback demo values (deterministic per machine)
            import hashlib
            # m.id may be int (Machine table) — stringify before hashing
            try:
                seed = int(hashlib.md5(str(m.id).encode()).hexdigest()[:8], 16) % 100
            except Exception:
                seed = 0
            availability = 0.82 + (seed % 16) / 100.0
            performance = 0.78 + (seed % 20) / 100.0
            quality = 0.92 + (seed % 8) / 100.0
            oee_val = availability * performance * quality

        rows.append({
            "machine_name": m.name,
            "availability": round(availability, 3),
            "performance": round(performance, 3),
            "quality": round(quality, 3),
            "oee": round(oee_val, 3),
        })

    return render_template(
        "kpi_alerts/oee.html",
        rows=rows,
        machines=machines,
        selected_machine=selected or "",
        selected_date=shift_date or "",
        username=session.get("username"),
    )


@bp.route("/kpi-alerts/die-lifecycle")
def die_lifecycle():
    if "username" not in session:
        return redirect(url_for("auth.login"))
    if request.args.get("compute") == "1":
        try:
            result = KPIEngine.compute_die_lifetime()
            flash(
                f"Die lifetime computed: avg {result.get('avg_cycles')} cycles "
                f"across {result.get('total_dies')} dies.",
                "success",
            )
        except Exception as exc:
            flash(f"Die lifetime compute failed: {exc}", "error")

    from ..models import Die
    dies = Die.query.order_by(Die.die_code.asc()).all()

    # Compute aggregated summary metrics
    total_dies = len(dies)
    avg_cycles = 0
    total_cycles = 0
    if total_dies:
        total_cycles = sum(d.life_cycles_total or 0 for d in dies)
        avg_cycles = total_cycles // max(total_dies, 1)

    rejected = sum(1 for d in dies if d.status in ("Rejected", "TestingFailed"))
    rejection_rate = (rejected / max(total_dies, 1)) * 100.0

    # Compute avg nitriding time from NitridingRecord.duration_hours
    nitriding_records = NitridingRecord.query.all()
    nitride_durations = [nr.duration_hours for nr in nitriding_records if nr.duration_hours]
    avg_nitriding_time_h = (
        round(sum(nitride_durations) / len(nitride_durations), 1)
        if nitride_durations else 0.0
    )

    # Compute avg production time from completed ProcessRun (ended_at - started_at)
    completed_runs = ProcessRun.query.filter(
        ProcessRun.status == "COMPLETED",
        ProcessRun.started_at.isnot(None),
        ProcessRun.ended_at.isnot(None),
    ).all()
    prod_durations_h = [
        (r.ended_at - r.started_at).total_seconds() / 3600.0
        for r in completed_runs
    ]
    avg_production_time_h = (
        round(sum(prod_durations_h) / len(prod_durations_h), 1)
        if prod_durations_h else 0.0
    )

    # Index nitriding totals per die
    nitride_by_die = {}
    for nr in nitriding_records:
        nitride_by_die.setdefault(nr.die_id, 0.0)
        nitride_by_die[nr.die_id] += nr.duration_hours or 0.0

    # Index press time per die from ProcessRun (completed runs linked to a die)
    press_by_die = {}
    for r in completed_runs:
        if r.die_id and r.started_at and r.ended_at:
            press_by_die.setdefault(r.die_id, 0.0)
            press_by_die[r.die_id] += (r.ended_at - r.started_at).total_seconds() / 3600.0

    # Build rows for the die-by-die table
    rows = []
    for d in dies:
        rows.append({
            "die_id": d.id,
            "die_code": d.die_code,
            "profile_code": d.profile_code or "-",
            "alloy": d.alloy or "-",
            "status": d.status,
            "total_cycles": d.life_cycles_total or 0,
            "press_time_h": round(press_by_die.get(d.id, 0.0), 1),
            "qc_time_h": 0.0,
            "nitride_time_h": round(nitride_by_die.get(d.id, 0.0), 1),
            "yield_kg": 0.0,
            "rejects": 0,
        })

    return render_template(
        "kpi_alerts/die_lifecycle.html",
        rows=rows,
        avg_cycles=avg_cycles,
        avg_nitriding_time_h=avg_nitriding_time_h,
        avg_production_time_h=avg_production_time_h,
        rejection_rate=round(rejection_rate, 1),
        total_dies=total_dies,
        username=session.get("username"),
    )


@bp.route("/kpi-alerts/downtime")
def downtime():
    if "username" not in session:
        return redirect(url_for("auth.login"))

    models_events = (
        DowntimeEvent.query.order_by(DowntimeEvent.started_at.desc()).limit(200).all()
    )

    # The model uses reason_code/ended_at/reported_by/machine_id (String) but
    # the template expects reason/resolved_at/resolved_by/machine_name.
    # Build a Machine-id -> name index so we can resolve machine_name,
    # then produce enriched event objects that expose both the legacy names
    # and a safe ``reason`` fallback.
    machines = Machine.query.order_by(Machine.name.asc()).all()
    machine_name_map = {m.id: m.name for m in machines}
    # Some installs also store machine_id as its name string — add self-mapping
    for m in machines:
        machine_name_map[str(m.id)] = m.name
        machine_name_map[m.name] = m.name

    resolved_events = []
    for ev in models_events:
        # Build a tiny namespace that lets Jinja do ``ev.reason`` / ``ev.resolved_at``
        # etc. while the underlying model still uses the real column names.
        resolved_at = getattr(ev, "ended_at", None) or getattr(ev, "resolved_at", None)
        resolved_by = getattr(ev, "reported_by", None) or getattr(ev, "resolved_by", None)
        reason = (
            getattr(ev, "reason", None)
            or getattr(ev, "reason_code", None)
            or "Unknown"
        )
        if getattr(ev, "reason_category", None):
            reason = f"{ev.reason_category} — {reason}"
        machine_id = getattr(ev, "machine_id", None)
        machine_name = machine_name_map.get(machine_id, machine_id or "-")

        # Attach friendly attrs onto the event object for the template.
        # (We don't mutate the model; these shadow SQLAlchemy descriptor behaviour
        # only on this instance copy within the route's lifetime.)
        ev.reason = reason
        ev.resolved_at = resolved_at
        ev.resolved_by = resolved_by
        ev.machine_name = machine_name
        resolved_events.append(ev)

    events = resolved_events

    # Compute summary stats (use safe getattr everywhere)
    total_downtime_min = sum(int(getattr(ev, "duration_min", 0) or 0) for ev in events)
    events_count = len(events)
    resolved = [ev for ev in events if getattr(ev, "resolved_at", None) and getattr(ev, "started_at", None)]
    mttr_min = (
        round(
            sum(
                (getattr(ev, "resolved_at") - getattr(ev, "started_at")).total_seconds() / 60.0
                for ev in resolved
            )
            / max(len(resolved), 1),
            1,
        )
        if resolved
        else 0
    )
    sorted_events = sorted((e for e in events if getattr(e, "started_at", None)), key=lambda e: e.started_at)
    if len(sorted_events) >= 2:
        gaps = [
            (sorted_events[i + 1].started_at - sorted_events[i].started_at).total_seconds() / 60.0
            for i in range(len(sorted_events) - 1)
        ]
        mtbf_min = round(sum(gaps) / len(gaps), 1) if gaps else 0
    else:
        mtbf_min = 0

    # Pareto breakdown
    reason_totals = {}
    for ev in events:
        key = getattr(ev, "reason", None) or "Unknown"
        reason_totals[key] = reason_totals.get(key, 0) + int(getattr(ev, "duration_min", 0) or 0)
    pareto = [
        {"reason": r, "duration_min": d}
        for r, d in sorted(reason_totals.items(), key=lambda x: -x[1])
    ][:10]
    max_duration = max((p["duration_min"] for p in pareto), default=1) or 1

    return render_template(
        "kpi_alerts/downtime.html",
        events=events,
        total_downtime_min=total_downtime_min,
        events_count=events_count,
        mtbf_min=mtbf_min,
        mttr_min=mttr_min,
        pareto=pareto,
        max_duration=max_duration,
        username=session.get("username"),
    )


# ── Alerts ───────────────────────────────────────────────────────────────────
@bp.route("/kpi-alerts/alerts")
def alerts_list():
    if "username" not in session:
        return redirect(url_for("auth.login"))
    status = request.args.get("status", "")
    q = Alert.query
    if status:
        q = q.filter_by(status=status)
    alerts = q.order_by(Alert.created_at.desc()).limit(200).all()
    return render_template(
        "kpi_alerts/alerts_list.html",
        alerts=alerts,
        status=status,
        username=session.get("username"),
    )


@bp.route("/kpi-alerts/alerts/<string:id>/acknowledge", methods=["POST"])
def alert_ack(id):
    if "username" not in session:
        return redirect(url_for("auth.login"))
    alert = Alert.query.get_or_404(id)
    alert.status = "Acknowledged"
    alert.acknowledged_by = session.get("username")
    alert.acknowledged_at = datetime.utcnow()
    db.session.commit()
    flash("Alert acknowledged.", "success")
    return redirect(url_for("kpi_alerts.alerts_list"))


@bp.route("/kpi-alerts/alerts/<string:id>/close", methods=["POST"])
def alert_close(id):
    if "username" not in session:
        return redirect(url_for("auth.login"))
    alert = Alert.query.get_or_404(id)
    alert.status = "Closed"
    alert.closed_at = datetime.utcnow()
    db.session.commit()
    flash("Alert closed.", "success")
    return redirect(url_for("kpi_alerts.alerts_list"))


# ── Rules ────────────────────────────────────────────────────────────────────
@bp.route("/kpi-alerts/rules")
def rules():
    if "username" not in session:
        return redirect(url_for("auth.login"))
    rules_list = AlertRule.query.order_by(AlertRule.created_at.desc()).all()
    return render_template(
        "kpi_alerts/rules.html",
        rules=rules_list,
        username=session.get("username"),
    )


@bp.route("/kpi-alerts/rules/new", methods=["POST"])
def rule_new():
    if "username" not in session:
        return redirect(url_for("auth.login"))

    threshold_value = {}
    operator = (request.form.get("operator") or "GT").upper()
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
        name=request.form.get("name", "").strip() or "Untitled rule",
        metric=request.form.get("metric", "OEE"),
        operator=operator,
        threshold_value=threshold_value,
        severity=request.form.get("severity", "WARNING"),
        is_active="is_active" in request.form,
    )
    if not rule.name:
        flash("Rule name is required.", "error")
        return redirect(url_for("kpi_alerts.rules"))

    db.session.add(rule)
    db.session.commit()
    flash(f"Alert rule '{rule.name}' created.", "success")
    return redirect(url_for("kpi_alerts.rules"))
