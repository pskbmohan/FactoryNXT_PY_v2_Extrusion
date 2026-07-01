from datetime import date, datetime
from flask import Blueprint, render_template, session, redirect, url_for
from ..models import (
    Alert,
    Billet,
    CustomerOrder,
    Die,
    IntegrationJob,
    Line,
    Machine,
    Alarm,
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
    )
