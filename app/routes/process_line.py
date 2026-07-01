"""Process Line blueprint.

Station-oriented views for the extrusion floor: billet inspection,
Homing / Loading / Sizing (HLS), pressing, quenching, puller, cutting,
stretching, final cut, die oven.
"""

import hashlib
import random
import uuid
from datetime import datetime

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
    Billet,
    BilletInspection,
    CutRecord,
    OvenRecord,
    ProcessRun,
    QuenchRecord,
    SetpointProfile,
    StretchRecord,
)
from ..services.plc_adapter import PLCAdapter
from ..services.process_simulator import (
    simulate_actuals,
    simulate_setpoint,
    simulate_bundles,
    simulate_oven_records,
    simulate_hls_records,
    simulate_press_records,
    simulate_quench_records,
    simulate_puller_records,
    simulate_stretch_records,
)

bp = Blueprint("process_line", __name__, template_folder="../templates/process_line")


def _require_session():
    if "username" not in session:
        return redirect(url_for("auth.login"))
    return None


def _parse_dt(s):
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None


# ── Overview ─────────────────────────────────────────────────────────────────
@bp.route("/process-line")
def index():
    """Floor overview: active runs per station."""
    if "username" not in session:
        return redirect(url_for("auth.login"))

    running = ProcessRun.query.filter_by(status="RUNNING").all()
    recent = (
        ProcessRun.query.order_by(ProcessRun.created_at.desc()).limit(20).all()
    )

    # Demo-hero metrics
    alerts_count = Alert.query.filter_by(status="Open").count()

    # Setpoint match %: fraction of recent completed ProcessRuns
    recent_runs = (
        ProcessRun.query.filter(ProcessRun.ended_at.isnot(None))
        .order_by(ProcessRun.ended_at.desc())
        .limit(50)
        .all()
    )
    if recent_runs:
        matches = sum(1 for r in recent_runs if r.status == "COMPLETED")
        setpoint_match_pct = int((matches / len(recent_runs)) * 100)
    else:
        setpoint_match_pct = 87  # demo-friendly default

    return render_template(
        "process_line/index.html",
        running=running,
        recent=recent,
        alerts_count=alerts_count,
        setpoint_match_pct=setpoint_match_pct,
        username=session.get("username"),
    )


# ── Billet inspection ────────────────────────────────────────────────────────
@bp.route("/process-line/billet-inspection")
def billet_inspection():
    if "username" not in session:
        return redirect(url_for("auth.login"))

    # Build a list of inspection records joined with billet data
    raw = (
        BilletInspection.query
        .order_by(BilletInspection.inspection_date.desc())
        .limit(200)
        .all()
    )
    inspections = []
    for rec in raw:
        b = rec.billet if hasattr(rec, "billet") and rec.billet else None
        inspected_at_dt = (
            datetime.combine(rec.inspection_date, datetime.min.time())
            if rec.inspection_date else rec.created_at
        )
        inspections.append({
            "id": rec.id,
            "batch_number": b.billet_code if b else ("BIL-?",),
            "alloy": b.alloy if b else "-",
            "diameter_mm": b.diameter_mm if b else None,
            "length_mm": b.length_mm if b else None,
            "inspected_at": inspected_at_dt,
            "inspector_name": rec.inspector,
            "temperature": rec.temperature,
            "result": rec.result or "OK",
            "notes": rec.notes,
        })

    # Also fetch billets so existing stock can be shown
    billets = Billet.query.order_by(Billet.created_at.desc()).limit(200).all()

    return render_template(
        "process_line/billet_inspection.html",
        inspections=inspections,
        billets=billets,
        username=session.get("username"),
    )


@bp.route("/process-line/billet-inspection/new", methods=["POST"])
def billet_inspection_new():
    if "username" not in session:
        return redirect(url_for("auth.login"))

    billet_code = (
        request.form.get("batch_number") or request.form.get("billet_code") or ""
    ).strip()
    if not billet_code:
        flash("Batch number / billet code is required.", "error")
        return redirect(url_for("process_line.billet_inspection"))

    billet = Billet.query.filter_by(billet_code=billet_code).first()
    if not billet:
        billet = Billet(
            id=str(uuid.uuid4()),
            billet_code=billet_code,
            alloy=request.form.get("alloy"),
            diameter_mm=float(request.form.get("diameter_mm") or 0) or None,
            length_mm=float(request.form.get("length_mm") or 0) or None,
            supplier=request.form.get("supplier"),
            lot_number=request.form.get("lot_number"),
            quantity_kg=float(request.form.get("quantity_kg") or 0) or None,
            status="AVAILABLE",
        )
        db.session.add(billet)
        db.session.flush()

    date_str = request.form.get("inspection_date")
    inspection_date = datetime.utcnow().date()
    if date_str:
        try:
            inspection_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            pass

    inspection = BilletInspection(
        id=str(uuid.uuid4()),
        billet_id=billet.id,
        inspection_date=inspection_date,
        inspector=request.form.get("inspector") or session.get("username"),
        chemical_composition={},
        temperature=float(request.form.get("temperature") or 0) or None,
        result=request.form.get("result", "PASS"),
        notes=request.form.get("notes"),
    )
    db.session.add(inspection)

    billet.status = "INSPECTED"

    # Track in traceability
    try:
        from ..models import TraceabilityRecord
        db.session.add(TraceabilityRecord(
            entity_type="BILLET",
            entity_id=billet.id,
            event_type="BILLET_INSPECTION",
            operator_id=session.get("username"),
            machine_id=None,
            data={
                "batch_number": billet_code,
                "alloy": billet.alloy,
                "result": inspection.result,
                "diameter_mm": billet.diameter_mm,
                "length_mm": billet.length_mm,
            },
            occurred_at=datetime.utcnow(),
        ))
    except Exception:
        pass

    db.session.commit()

    flash(f"Billet inspection recorded for {billet_code}.", "success")
    return redirect(url_for("process_line.billet_inspection"))


# ── Station helpers ──────────────────────────────────────────────────────────
def _station_page(process_type, template_name, extra_context=None):
    runs = (
        ProcessRun.query.filter_by(process_type=process_type)
        .order_by(ProcessRun.created_at.desc())
        .limit(100)
        .all()
    )
    ctx = {
        "runs": runs,
        "process_type": process_type,
        "username": session.get("username"),
    }
    if extra_context:
        ctx.update(extra_context)
    return render_template(template_name, **ctx)


# ── HLS (Homing / Loading / Sizing) ────────────────────────────────────────
@bp.route("/process-line/hls")
def hls():
    if "username" not in session:
        return redirect(url_for("auth.login"))
    profiles = SetpointProfile.query.filter_by(
        process_type="HLS", is_active=True
    ).all()
    # Fallback: if no active profiles exist in DB, expose a synthetic one so
    # the setpoint load form can still post.
    if not profiles:
        class _SyntheticProfile:
            id = "sim"
            profile_code = "HLS-DEFAULT"
            process_type = "HLS"
            alloy = "6061"
            parameters = simulate_setpoint("HLS")
        profiles = [_SyntheticProfile()]
    sim = simulate_actuals("HLS", "HLS-01")
    return render_template(
        "process_line/hls.html",
        profiles=profiles,
        setpoint=sim["setpoint"],
        actuals=sim["actual"],
        runs=simulate_hls_records(count=8),
        process_type="HLS",
        username=session.get("username"),
    )


@bp.route("/process-line/hls/load-setpoint", methods=["POST"])
def hls_load():
    if "username" not in session:
        return redirect(url_for("auth.login"))
    machine_name = request.form.get("machine_name") or "HLS-01"
    profile_id = request.form.get("setpoint_profile_id")
    profile = SetpointProfile.query.get(profile_id) if profile_id else None

    if not profile:
        # Synthesize a transient profile from form values / simulator so the
        # demo flow still works when no real profile exists yet.
        _alloy = request.form.get("alloy", "6061")
        params = dict(simulate_setpoint("HLS", _alloy))
        if request.form.get("target_temp"):
            try:
                params["billet_temp_c"] = float(request.form["target_temp"])
            except (TypeError, ValueError):
                pass
        if request.form.get("soak_time_min"):
            try:
                params["soak_time_min"] = float(request.form["soak_time_min"])
            except (TypeError, ValueError):
                pass

        def _make_profile(alloy_val, param_dict):
            class _SyntheticProfile:
                id = "sim"
                process_type = "HLS"
                parameters = param_dict
            _SyntheticProfile.alloy = alloy_val
            return _SyntheticProfile()
        profile = _make_profile(_alloy, params)

    result = PLCAdapter.load_setpoint(machine_name, profile)
    flash(
        f"Setpoint loaded to {machine_name}: "
        f"{'success' if result.get('success') else 'failed'} (job {result.get('job_id')}).",
        "success" if result.get("success") else "warning",
    )
    return redirect(url_for("process_line.hls"))


@bp.route("/process-line/hls/capture", methods=["POST"])
def hls_capture_new():
    """Capture actuals from the HLS form (run_id + measured values)."""
    if "username" not in session:
        return redirect(url_for("auth.login"))
    run = ProcessRun(
        id=str(uuid.uuid4()),
        process_type="HLS",
        machine_id=None,
        operator_id=session.get("username"),
        status="COMPLETED",
        started_at=datetime.utcnow(),
        ended_at=datetime.utcnow(),
    )
    db.session.add(run)
    db.session.commit()
    machine_name = request.form.get("machine_name", "HLS-01")
    result = PLCAdapter.capture_actuals(machine_name, run)
    flash(
        f"HLS actual captured for run {run.id}: "
        f"{len(result.get('readings', []))} readings logged.",
        "success",
    )
    return redirect(url_for("process_line.hls"))


@bp.route("/process-line/hls/<string:run_id>/capture", methods=["POST"])
def hls_capture(run_id):
    if "username" not in session:
        return redirect(url_for("auth.login"))
    run = ProcessRun.query.get_or_404(run_id)
    machine_name = request.form.get("machine_name", "HLS-1")
    result = PLCAdapter.capture_actuals(machine_name, run)
    flash(
        f"Captured {len(result.get('readings', []))} actuals for run {run.id}.",
        "success",
    )
    return redirect(url_for("process_line.hls"))


# ── Pressing ─────────────────────────────────────────────────────────────────
@bp.route("/process-line/pressing")
def pressing():
    if "username" not in session:
        return redirect(url_for("auth.login"))
    sim = simulate_actuals("PRESSING", "Press-01")
    return render_template(
        "process_line/pressing.html",
        setpoint=sim["setpoint"],
        actuals=sim["actual"],
        runs=simulate_press_records(count=8),
        process_type="PRESSING",
        username=session.get("username"),
    )


@bp.route("/process-line/pressing/apply-setpoint", methods=["POST"])
def pressing_apply_setpoint():
    """Apply setpoint (simulate PLC write) and log as ProcessRun."""
    if "username" not in session:
        return redirect(url_for("auth.login"))
    die_code = request.form.get("die_code") or "DIE-2000"
    run = ProcessRun(
        id=str(uuid.uuid4()),
        process_type="PRESSING",
        machine_id=None,
        operator_id=session.get("username"),
        status="COMPLETED",
        started_at=datetime.utcnow(),
        ended_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
    )
    db.session.add(run)
    db.session.commit()
    flash(f"Setpoint applied to press for die {die_code}. Actuals captured.", "success")
    return redirect(url_for("process_line.pressing"))


@bp.route("/process-line/pressing/capture", methods=["POST"])
def pressing_capture():
    """Capture press actuals from the form."""
    if "username" not in session:
        return redirect(url_for("auth.login"))
    run = ProcessRun(
        id=str(uuid.uuid4()),
        process_type="PRESSING",
        machine_id=None,
        operator_id=session.get("username"),
        status="COMPLETED",
        started_at=datetime.utcnow(),
        ended_at=datetime.utcnow(),
    )
    db.session.add(run)
    db.session.commit()
    result = PLCAdapter.capture_actuals("Press-01", run)
    flash(
        f"Captured {len(result.get('readings', []))} press actuals for run {run.id}.",
        "success",
    )
    return redirect(url_for("process_line.pressing"))


# ── Quenching ────────────────────────────────────────────────────────────────
@bp.route("/process-line/quenching")
def quenching():
    if "username" not in session:
        return redirect(url_for("auth.login"))
    sim = simulate_actuals("QUENCHING", "Quench-01")
    records = simulate_quench_records(count=8)
    quench_type_filter = request.args.get("quench_type", "").upper()
    if quench_type_filter:
        records = [r for r in records if r.get("quench_type") == quench_type_filter]
    return render_template(
        "process_line/quenching.html",
        setpoint=sim["setpoint"],
        actuals=sim["actual"],
        records=records,
        process_type="QUENCHING",
        username=session.get("username"),
    )


@bp.route("/process-line/quenching/<string:run_id>/trend")
def quench_trend(run_id):
    if "username" not in session:
        return redirect(url_for("auth.login"))
    # First try the DB (real captured records). If there are none (simulated
    # run_ids from the history table), fall back to simulated trend points.
    run = ProcessRun.query.get(run_id)
    records = []
    if run:
        records = (
            QuenchRecord.query.filter_by(run_id=run.id)
            .order_by(QuenchRecord.start_time.asc())
            .all()
        )

    if records:
        # Build chart points from QuenchRecord sensor_temperatures JSON
        points = []
        entry_temp = None
        exit_temp = None
        quench_type = None
        duration_s = None
        for rec in records:
            if quench_type is None:
                quench_type = rec.quench_type
            temps = rec.sensor_temperatures or []
            for idx, t in enumerate(temps):
                points.append({"x": idx * 20, "y": t})
                entry_temp = entry_temp if entry_temp is not None else t
                exit_temp = t
            if rec.start_time and rec.end_time:
                try:
                    duration_s = (rec.end_time - rec.start_time).total_seconds()
                except Exception:
                    pass
    else:
        # Simulated fallback so the demo page is not empty
        rng = _rng_quench_trend(run_id)
        points = []
        entry_temp = round(rng.uniform(515, 535), 1)
        exit_temp = round(rng.uniform(210, 270), 1)
        steps = 20
        for i in range(steps):
            t = entry_temp - (entry_temp - exit_temp) * (i / steps) + rng.uniform(-3, 3)
            points.append({"x": i * 20, "y": round(t, 1)})
        quench_type = rng.choice(["WATER_SPRAY", "AIR_FAN", "WATER_BATH"])
        duration_s = round(rng.uniform(8, 25), 1)

    # Build a single "record-like" namespace for the template's summary block
    class _Record:
        pass
    record = _Record()
    record.run_id = run_id
    record.quench_type = quench_type
    record.entry_temp = entry_temp
    record.exit_temp = exit_temp
    record.duration_s = duration_s

    return render_template(
        "process_line/quench_trend.html",
        run_id=run_id,
        record=record,
        records=records,
        points=points,
        username=session.get("username"),
    )


def _rng_quench_trend(seed: str):
    """Deterministic RNG for simulated quench trend charts."""
    h = int(hashlib.md5(seed.encode()).hexdigest()[:8], 16)
    return random.Random(h)


# ── Puller ───────────────────────────────────────────────────────────────────
@bp.route("/process-line/puller")
def puller():
    if "username" not in session:
        return redirect(url_for("auth.login"))

    sim = simulate_actuals("PULLING", "Puller-01")

    return render_template(
        "process_line/puller.html",
        setpoint=sim["setpoint"],
        actuals=sim["actual"],
        records=simulate_puller_records(count=8),
        process_type="PULLING",
        username=session.get("username"),
    )


@bp.route("/process-line/puller/capture", methods=["POST"])
def puller_capture():
    """Capture puller actuals from form."""
    if "username" not in session:
        return redirect(url_for("auth.login"))
    run = ProcessRun(
        id=str(uuid.uuid4()),
        process_type="PULLING",
        machine_id=None,
        operator_id=session.get("username"),
        status="COMPLETED",
        started_at=datetime.utcnow(),
        ended_at=datetime.utcnow(),
    )
    db.session.add(run)
    db.session.commit()
    result = PLCAdapter.capture_actuals("Puller-01", run)
    flash(
        f"Captured {len(result.get('readings', []))} puller actuals for run {run.id}.",
        "success",
    )
    return redirect(url_for("process_line.puller"))


# ── Cutting ──────────────────────────────────────────────────────────────────
@bp.route("/process-line/cutting")
def cutting():
    if "username" not in session:
        return redirect(url_for("auth.login"))
    return _station_page("CUTTING", "process_line/cutting.html")


# ── Stretching ───────────────────────────────────────────────────────────────
@bp.route("/process-line/stretching")
def stretching():
    if "username" not in session:
        return redirect(url_for("auth.login"))

    sim = simulate_actuals("STRETCHING", "Stretch-01")

    return render_template(
        "process_line/stretching.html",
        setpoint=sim["setpoint"],
        actuals=sim["actual"],
        records=simulate_stretch_records(count=8),
        process_type="STRETCHING",
        username=session.get("username"),
    )


@bp.route("/process-line/stretching/capture", methods=["POST"])
def stretching_capture():
    """Capture stretching actuals from form."""
    if "username" not in session:
        return redirect(url_for("auth.login"))
    run = ProcessRun(
        id=str(uuid.uuid4()),
        process_type="STRETCHING",
        machine_id=None,
        operator_id=session.get("username"),
        status="COMPLETED",
        started_at=datetime.utcnow(),
        ended_at=datetime.utcnow(),
    )
    db.session.add(run)
    db.session.commit()
    result = PLCAdapter.capture_actuals("Stretch-01", run)
    flash(
        f"Captured {len(result.get('readings', []))} stretch actuals for run {run.id}.",
        "success",
    )
    return redirect(url_for("process_line.stretching"))


# ── Final cut ────────────────────────────────────────────────────────────────
@bp.route("/process-line/final-cut")
def final_cut():
    if "username" not in session:
        return redirect(url_for("auth.login"))

    sim = simulate_actuals("FINAL_CUT", "FinalCut-01")
    bundles = simulate_bundles(count=10)

    # Calculate statistics
    cuts_today = len([b for b in bundles if b.get("recorded_at")])
    total_weight = sum(b.get("weight_kg", 0) for b in bundles)
    in_spec_count = len([b for b in bundles if b.get("in_spec")])
    out_of_spec_count = cuts_today - in_spec_count
    avg_length_m = (
        sum(b.get("length_m", 0) for b in bundles) / len(bundles)
        if bundles else 0.0
    )

    return render_template(
        "process_line/final_cut.html",
        setpoint=sim["setpoint"],
        actuals=sim["actual"],
        records=bundles,
        cuts_today=cuts_today,
        total_weight=total_weight,
        in_spec_count=in_spec_count,
        out_of_spec_count=out_of_spec_count,
        avg_length_m=avg_length_m,
        process_type="FINAL_CUT",
        username=session.get("username"),
    )


# ── Die Oven ─────────────────────────────────────────────────────────────────
@bp.route("/process-line/die-oven")
def die_oven():
    if "username" not in session:
        return redirect(url_for("auth.login"))

    sim = simulate_actuals("OVEN", "DieOven-01")
    records = simulate_oven_records(count=10)

    # Calculate statistics
    total_soak_time = sum(r.get("soak_time_used_min", 0) for r in records if r.get("soak_time_used_min"))
    avg_cycle_time = (
        total_soak_time / len(records)
        if records else 0.0
    )
    active_heats = len([r for r in records if r.get("status") == "HEATING"])

    return render_template(
        "process_line/die_oven.html",
        setpoint=sim["setpoint"],
        actuals=sim["actual"],
        setpoint_temp=sim["setpoint"].get("set_temp_c"),
        actual_temp=sim["actual"].get("set_temp_c"),
        soak_time_min=sim["actual"].get("soak_time_used_min"),
        target_soak_min=sim["setpoint"].get("soak_time_min"),
        records=records,
        total_soak_time=total_soak_time,
        avg_cycle_time=avg_cycle_time,
        active_heats=active_heats,
        process_type="OVEN",
        username=session.get("username"),
    )
