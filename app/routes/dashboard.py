from datetime import date, datetime
from flask import Blueprint, render_template, session, redirect, url_for
from sqlalchemy import func
from .. import db
from ..models import (
    Alert,
    Billet,
    CustomerOrder,
    Die,
    FinishingOrder,
    FinishingProcessType,
    Furnace,
    FurnaceSession,
    IntegrationJob,
    Line,
    MaterialReceipt,
    AlloyComposition,
    Machine,
    Alarm,
    Shipment,
)

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index():
    username = session.get("username")
    if not username:
        return redirect(url_for("auth.login"))
    lines = Line.query.all()
    machines = Machine.query.all()
    active_alarms = Alarm.query.filter_by(is_active=True).all()

    # ── Extrusion KPIs for the dashboard context ─────────────────────────
    total_orders = CustomerOrder.query.count()
    active_orders = CustomerOrder.query.filter(
        CustomerOrder.status.in_(["CONFIRMED", "IN_PROGRESS"])
    ).count()

    die_available_count = Die.query.filter_by(status="Available").count()
    die_rejected_count = Die.query.filter_by(status="Rejected").count()
    billet_available_count = Billet.query.filter_by(status="AVAILABLE").count()

    active_alerts_count = Alert.query.filter_by(status="Open").count()
    recent_alerts = (
        Alert.query.order_by(Alert.created_at.desc()).limit(5).all()
    )

    # OEE today: latest KPI record for today, or fallback to 0
    today = date.today()
    from ..models import KPIRecord
    oee_today = 0.0
    oee_record = (
        KPIRecord.query.filter_by(
            kpi_type="OEE", shift_date=today
        ).order_by(KPIRecord.calculated_at.desc()).first()
    )
    if oee_record is not None:
        oee_today = oee_record.value or 0.0

    # Sync health: ERP/PLC success/failure counts from IntegrationJob
    erp_job_filter = IntegrationJob.job_type.in_(
        ["ERP_POST_INSPECTION", "ERP_POST_TEST", "ERP_POST_NITRIDING", "ERP_ORDER_IMPORT"]
    )
    plc_job_filter = IntegrationJob.job_type.in_(
        ["PLC_SETPOINT_LOAD", "PLC_CAPTURE"]
    )
    sync_health = {
        "erp_success": IntegrationJob.query.filter(erp_job_filter, IntegrationJob.status == "Success").count(),
        "erp_failed": IntegrationJob.query.filter(erp_job_filter, IntegrationJob.status == "Failed").count(),
        "plc_success": IntegrationJob.query.filter(plc_job_filter, IntegrationJob.status == "Success").count(),
        "plc_failed": IntegrationJob.query.filter(plc_job_filter, IntegrationJob.status == "Failed").count(),
    }

    # ── New widgets for extrusion dashboard ─────────────────────────────
    # 1. Alloy stock: available qty per alloy code
    alloy_stock = (
        db.session.query(
            MaterialReceipt.alloy_code,
            func.sum(MaterialReceipt.quantity_available),
        )
        .filter(MaterialReceipt.alloy_code.isnot(None), MaterialReceipt.quantity_available > 0)
        .group_by(MaterialReceipt.alloy_code)
        .order_by(func.sum(MaterialReceipt.quantity_available).desc())
        .limit(6)
        .all()
    )
    alloy_names = {a.alloy_code: a.alloy_name for a in AlloyComposition.query.all()}
    alloy_stock_data = [
        {"alloy_code": c, "alloy_name": alloy_names.get(c, c), "qty": q or 0}
        for c, q in alloy_stock
    ]

    # 2. Die store status — 4 buckets matching dies_mgmt logic
    die_status_counts = dict(
        db.session.query(Die.status, func.count(Die.id)).group_by(Die.status).all()
    )
    die_store_status = {
        "available": die_status_counts.get("Available", 0),
        "in_furnace": die_status_counts.get("In_Furnace", 0),
        "repair": (die_status_counts.get("Repair", 0) or 0) + (die_status_counts.get("Rework", 0) or 0),
        "in_press": die_status_counts.get("In_Press", 0),
    }

    # 3. Furnace status: each furnace + current session info
    furnaces_status = []
    for f in Furnace.query.filter_by(is_active=True).order_by(Furnace.name).limit(6).all():
        active = (
            f.sessions
            .filter(FurnaceSession.status.in_(["running", "loading"]))
            .first()
        )
        progr = None
        if active and active.program:
            progr = active.program.name
            total_min = active.program.total_duration_minutes or 0
            pct = 0
            if total_min and active.started_at:
                elapsed = (datetime.utcnow() - active.started_at).total_seconds() / 60
                pct = min(100, round(100 * elapsed / total_min))
            active_prog_info = {"name": progr, "pct": pct}
        else:
            active_prog_info = None
        furnaces_status.append({
            "name": f.name,
            "status": f.status or "idle",
            "active_prog": active_prog_info,
        })

    # 4. Finishing queue by process type
    finishing_queue = []
    for pt in FinishingProcessType.query.order_by(FinishingProcessType.name).limit(8).all():
        pending_count = FinishingOrder.query.filter_by(
            process_type_id=pt.id, status="pending"
        ).count()
        finishing_queue.append({
            "name": pt.name,
            "code": pt.code,
            "pending": pending_count,
        })

    # 5. Shipments today
    today_shipments = Shipment.query.filter_by(scheduled_ship_date=date.today()).count()
    weight_checks_pending = Shipment.query.filter(
        Shipment.status == "weight_check",
        Shipment.weight_check_status.isnot(None),
    ).count()

    return render_template(
        "dashboard.html",
        lines=lines,
        machines=machines,
        active_alarms=active_alarms,
        username=username,
        # extrusion context
        total_orders=total_orders,
        active_orders=active_orders,
        die_available_count=die_available_count,
        die_rejected_count=die_rejected_count,
        billet_available_count=billet_available_count,
        active_alerts_count=active_alerts_count,
        recent_alerts=recent_alerts,
        oee_today=oee_today,
        sync_health=sync_health,
        # new extrusion widgets
        alloy_stock=alloy_stock_data,
        die_store=die_store_status,
        furnaces_status=furnaces_status,
        finishing_queue=finishing_queue,
        shipments_today_count=today_shipments,
        weight_checks_pending=weight_checks_pending,
    )
