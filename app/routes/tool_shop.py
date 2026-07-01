"""Tool Shop blueprint.

Dies workflow: inward → inspection → testing → nitriding → registry.
Also die shortage view.
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
    Die,
    DieInspection,
    DieTest,
    NitridingRecord,
)
from ..services.erp_adapter import ERPAdapter

bp = Blueprint("tool_shop", __name__, template_folder="../templates/tool_shop")


# ── Dashboard (registry + pipeline) ─────────────────────────────────────────
@bp.route("/tool-shop")
def index():
    """Tool shop dashboard: die registry and pipeline overview."""
    if "username" not in session:
        return redirect(url_for("auth.login"))

    total_dies = Die.query.count()

    # Bucket dies by status for the pipeline widget
    raw_buckets = {}
    for d in Die.query.all():
        raw_buckets[d.status] = raw_buckets.get(d.status, 0) + 1

    # Template uses NORMALIZED keys (uppercase + underscores).
    pipeline = {
        "NEW": raw_buckets.get("New", 0),
        "INSPECTED": raw_buckets.get("Inspected", 0),
        "TESTING_PENDING": raw_buckets.get("TestingPending", 0),
        "TESTING_PASSED": raw_buckets.get("TestingPassed", 0),
        "NITRIDING_PENDING": raw_buckets.get("NitridingPending", 0),
        "NITRIDED": raw_buckets.get("Nitrided", 0),
        "AVAILABLE": raw_buckets.get("Available", 0),
    }

    # Recent inspections (from DieInspection, with die loaded for display)
    recent_inspections = (
        DieInspection.query.order_by(DieInspection.inspection_date.desc())
        .limit(5)
        .all()
    )

    # Active shortages (die shortages — die codes where scheduled plans
    # require more dies than are Available).
    try:
        from ..services.scheduler import ScheduleOptimizer
        shortage_result = ScheduleOptimizer.compute_shortages()
        die_shortages = shortage_result.get("die_shortages", [])
        shortages = [
            {
                "die_code": s.get("alloy") or "DIE",
                "profile_code": s.get("profile_shape") or "-",
            }
            for s in die_shortages[:5]
        ]
    except Exception:
        shortages = []

    recent = (
        Die.query.order_by(Die.created_at.desc()).limit(10).all()
    )

    # Demo-hero counts derived from status buckets
    available_count = pipeline["AVAILABLE"]
    qc_count = (
        pipeline["TESTING_PENDING"]
        + pipeline["NEW"]
        + pipeline["INSPECTED"]
    )
    nitriding_count = pipeline["NITRIDING_PENDING"]
    rejected_count = (
        raw_buckets.get("Rejected", 0) + raw_buckets.get("TestingFailed", 0)
    )

    return render_template(
        "tool_shop/index.html",
        total_dies=total_dies,
        buckets=raw_buckets,
        pipeline=pipeline,
        recent=recent,
        recent_inspections=recent_inspections,
        shortages=shortages,
        available_count=available_count,
        qc_count=qc_count,
        nitriding_count=nitriding_count,
        rejected_count=rejected_count,
        username=session.get("username"),
    )


@bp.route("/tool-shop/dies")
def die_list():
    if "username" not in session:
        return redirect(url_for("auth.login"))
    status = request.args.get("status", "")
    q = Die.query
    if status:
        q = q.filter_by(status=status)
    dies = q.order_by(Die.die_code.asc()).all()
    return render_template(
        "tool_shop/die_list.html",
        dies=dies,
        status=status,
        username=session.get("username"),
    )


@bp.route("/tool-shop/dies/new", methods=["GET", "POST"])
def die_new():
    """Inward a new die from the store."""
    if "username" not in session:
        return redirect(url_for("auth.login"))
    if request.method == "GET":
        return render_template(
            "tool_shop/die_form.html",
            form=None,
            username=session.get("username"),
        )
    die = Die(
        id=str(uuid.uuid4()),
        die_code=request.form.get("die_code", "").strip(),
        profile_code=request.form.get("profile_code"),
        alloy=request.form.get("alloy"),
        supplier=request.form.get("supplier"),
        location=request.form.get("location"),
        status="New",
        erp_asset_id=request.form.get("erp_asset_id"),
    )
    if not die.die_code:
        flash("Die code is required.", "error")
        return redirect(url_for("tool_shop.die_list"))

    existing = Die.query.filter_by(die_code=die.die_code).first()
    if existing:
        flash(f"Die {die.die_code} already exists.", "error")
        return redirect(url_for("tool_shop.die_list"))

    db.session.add(die)
    db.session.commit()
    flash(f"Die {die.die_code} registered inward.", "success")
    return redirect(url_for("tool_shop.die_detail", id=die.id))


@bp.route("/tool-shop/dies/<string:id>")
def die_detail(id):
    if "username" not in session:
        return redirect(url_for("auth.login"))
    die = Die.query.get_or_404(id)
    inspections = die.inspections.order_by(DieInspection.inspection_date.desc()).all()
    tests = die.tests.order_by(DieTest.test_date.desc()).all()
    nitridings = die.nitriding_records.order_by(NitridingRecord.created_at.desc()).all()

    # Build a combined history list for display (newest first)
    history = []
    for ins in inspections:
        passed = bool(ins.dimensions_ok and ins.surface_ok)
        history.append({
            "date": datetime.combine(ins.inspection_date, datetime.min.time()) if ins.inspection_date else None,
            "record_type": "Inspection",
            "result": "PASS" if passed else "FAIL",
            "notes": ins.notes or "",
            "inspector_name": ins.inspector or "-",
        })
    for t in tests:
        history.append({
            "date": datetime.combine(t.test_date, datetime.min.time()) if t.test_date else None,
            "record_type": "Test",
            "result": t.result or "PENDING",
            "notes": f"Force={t.press_force}t Temp={t.temperature}°C Quality={t.profile_quality or '-'}",
            "inspector_name": t.tester or "-",
        })
    for n in nitridings:
        history.append({
            "date": n.created_at,
            "record_type": "Nitriding",
            "result": "Complete",
            "notes": f"Furnace {n.furnace_id or '-'} {n.start_temp}→{n.end_temp}°C {n.duration_hours}h HV {n.hardness_before}→{n.hardness_after}",
            "inspector_name": n.operator or "-",
        })
    history.sort(key=lambda h: h["date"] or datetime.min, reverse=True)

    return render_template(
        "tool_shop/die_detail.html",
        die=die,
        inspections=inspections,
        tests=tests,
        nitridings=nitridings,
        history=history,
        today_str=date.today().isoformat(),
        username=session.get("username"),
    )


def _parse_date(s):
    if not s:
        return date.today()
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return date.today()


# ── Inspections ──────────────────────────────────────────────────────────────
@bp.route("/tool-shop/dies/<string:id>/inspect", methods=["POST"])
def die_inspect(id):
    if "username" not in session:
        return redirect(url_for("auth.login"))
    die = Die.query.get_or_404(id)
    inspection = DieInspection(
        id=str(uuid.uuid4()),
        die_id=die.id,
        inspection_date=_parse_date(request.form.get("inspection_date")),
        inspector=request.form.get("inspector"),
        dimensions_ok=request.form.get("dimensions_ok") == "on",
        surface_ok=request.form.get("surface_ok") == "on",
        hardness=float(request.form.get("hardness") or 0) or None,
        notes=request.form.get("notes"),
    )
    db.session.add(inspection)

    # Advance die status: New/Inspected -> TestingPending
    if die.status in ("New", "Inspected"):
        die.status = "TestingPending"
    die.last_inspected_at = datetime.utcnow()
    db.session.commit()

    # Optional ERP post
    if "post_erp" in request.form:
        try:
            result = ERPAdapter.post_inspection(inspection)
            flash(
                f"ERP post: {'success' if result.get('success') else 'failed'} "
                f"(job {result.get('job_id')}).",
                "success" if result.get("success") else "warning",
            )
        except Exception as exc:
            flash(f"ERP post failed: {exc}", "error")

    flash("Inspection recorded.", "success")
    return redirect(url_for("tool_shop.die_detail", id=die.id))


# ── Testing ──────────────────────────────────────────────────────────────────
@bp.route("/tool-shop/dies/<string:id>/test", methods=["POST"])
def die_test(id):
    if "username" not in session:
        return redirect(url_for("auth.login"))
    die = Die.query.get_or_404(id)
    test = DieTest(
        id=str(uuid.uuid4()),
        die_id=die.id,
        test_date=_parse_date(request.form.get("test_date")),
        tester=request.form.get("tester"),
        press_force=float(request.form.get("press_force") or 0) or None,
        temperature=float(request.form.get("temperature") or 0) or None,
        profile_quality=request.form.get("profile_quality"),
        result=request.form.get("result", "FAIL"),
    )
    db.session.add(test)

    # Advance die status
    if test.result == "PASS" and die.status in ("TestingPending", "TestingPassed"):
        die.status = "TestingPassed"
    elif test.result == "FAIL":
        die.status = "TestingFailed"
    die.last_tested_at = datetime.utcnow()
    db.session.commit()

    if "post_erp" in request.form:
        try:
            result = ERPAdapter.post_test(test)
            flash(
                f"ERP post: {'success' if result.get('success') else 'failed'} "
                f"(job {result.get('job_id')}).",
                "success" if result.get("success") else "warning",
            )
        except Exception as exc:
            flash(f"ERP post failed: {exc}", "error")

    flash("Test recorded.", "success")
    return redirect(url_for("tool_shop.die_detail", id=die.id))


# ── Nitriding ────────────────────────────────────────────────────────────────
@bp.route("/tool-shop/dies/<string:id>/nitride", methods=["POST"])
def die_nitride(id):
    if "username" not in session:
        return redirect(url_for("auth.login"))
    die = Die.query.get_or_404(id)
    record = NitridingRecord(
        id=str(uuid.uuid4()),
        die_id=die.id,
        furnace_id=request.form.get("furnace_id"),
        start_temp=float(request.form.get("start_temp") or 0) or None,
        end_temp=float(request.form.get("end_temp") or 0) or None,
        duration_hours=float(request.form.get("duration_hours") or 0) or None,
        atmosphere=request.form.get("atmosphere"),
        hardness_before=float(request.form.get("hardness_before") or 0) or None,
        hardness_after=float(request.form.get("hardness_after") or 0) or None,
        operator=request.form.get("operator"),
    )
    db.session.add(record)

    if die.status in ("TestingPassed", "NitridingPending"):
        die.status = "Nitrided"
    die.last_nitrided_at = datetime.utcnow()
    # Auto-increment lifecycle counter
    die.life_cycles_total = (die.life_cycles_total or 0) + 1
    db.session.commit()

    if "post_erp" in request.form:
        try:
            result = ERPAdapter.post_nitriding(record)
            flash(
                f"ERP post: {'success' if result.get('success') else 'failed'} "
                f"(job {result.get('job_id')}).",
                "success" if result.get("success") else "warning",
            )
        except Exception as exc:
            flash(f"ERP post failed: {exc}", "error")

    flash("Nitriding recorded.", "success")
    return redirect(url_for("tool_shop.die_detail", id=die.id))


# ── Release to production (Nitrided → Available) ────────────────────────────
@bp.route("/tool-shop/dies/<string:id>/release", methods=["POST"])
def die_release(id):
    """Mark a nitrided die as Available for production scheduling."""
    if "username" not in session:
        return redirect(url_for("auth.login"))
    die = Die.query.get_or_404(id)

    if die.status == "Nitrided":
        die.status = "Available"
        db.session.commit()
        flash(f"Die {die.die_code} released to production.", "success")
    else:
        flash(
            f"Die {die.die_code} cannot be released from status '{die.status}'. "
            "Only nitrided dies can be released.",
            "warning",
        )

    return redirect(url_for("tool_shop.die_detail", id=die.id))


# ── Index lists ──────────────────────────────────────────────────────────────
@bp.route("/tool-shop/inspections")
def inspection_list():
    if "username" not in session:
        return redirect(url_for("auth.login"))
    inspections = (
        DieInspection.query.order_by(DieInspection.inspection_date.desc()).limit(200).all()
    )
    return render_template(
        "tool_shop/inspections.html",
        inspections=inspections,
        username=session.get("username"),
    )


@bp.route("/tool-shop/tests")
def test_list():
    if "username" not in session:
        return redirect(url_for("auth.login"))
    tests = (
        DieTest.query.order_by(DieTest.test_date.desc()).limit(200).all()
    )
    return render_template(
        "tool_shop/tests.html",
        tests=tests,
        username=session.get("username"),
    )


@bp.route("/tool-shop/nitriding")
def nitriding_list():
    if "username" not in session:
        return redirect(url_for("auth.login"))
    records = (
        NitridingRecord.query.order_by(NitridingRecord.created_at.desc()).limit(200).all()
    )
    return render_template(
        "tool_shop/nitriding.html",
        records=records,
        username=session.get("username"),
    )


@bp.route("/tool-shop/shortages")
def shortages():
    if "username" not in session:
        return redirect(url_for("auth.login"))
    from ..services.scheduler import ScheduleOptimizer

    result = ScheduleOptimizer.compute_shortages()
    die_shortages = result.get("die_shortages", [])
    billet_shortages = result.get("billet_shortages", [])

    # Build template-friendly shortage rows with extra context
    shortages = []
    for s in die_shortages:
        shortages.append({
            "die_code": s.get("alloy") or "DIE",
            "profile_code": s.get("profile_shape") or "-",
            "order_number": None,
            "scheduled_date": None,
            "current_status": "SHORTAGE",
            "severity": "CRITICAL" if s.get("shortage", 0) >= 3 else "HIGH",
        })

    return render_template(
        "tool_shop/shortages.html",
        shortages=shortages,
        shortages_count=len(shortages),
        critical_count=sum(1 for s in shortages if s["severity"] == "CRITICAL"),
        at_risk_count=sum(1 for s in shortages if s["severity"] == "HIGH"),
        username=session.get("username"),
    )
