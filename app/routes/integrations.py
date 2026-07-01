from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from .. import db
from ..models import Integration, ErpSyncLog, Webhook, ApiKey, IntegrationJob
from datetime import datetime, timedelta

bp = Blueprint("integrations", __name__, url_prefix="/integrations")


@bp.route("/", methods=["GET"])
def hub():
    integrations = Integration.query.order_by(Integration.name.asc()).all()
    cutoff = datetime.utcnow() - timedelta(hours=24)
    failed_jobs_24h = IntegrationJob.query.filter(
        IntegrationJob.status == "Failed",
        IntegrationJob.created_at >= cutoff,
    ).count()
    return render_template(
        "integrations/hub.html",
        integrations=integrations,
        failed_jobs_24h=failed_jobs_24h,
    )


@bp.route("/toggle/<int:id>", methods=["POST"])
def toggle(id):
    intg = Integration.query.get_or_404(id)
    intg.is_active = not intg.is_active
    intg.updated_at = datetime.utcnow()
    db.session.commit()
    flash(f"Integration '{intg.name}' {'enabled' if intg.is_active else 'disabled'}.", "success")
    return redirect(url_for("integrations.hub"))


@bp.route("/erp", methods=["GET"])
def erp_sync():
    logs = ErpSyncLog.query.order_by(ErpSyncLog.started_at.desc()).limit(100).all()

    # ERP configuration for this foundry (Lighthouse Info System V15 on Oracle)
    erp_config = {
        "name": "Lighthouse Info System Pvt Ltd",
        "version": "V15",
        "database": "Oracle Database",
        "database_location": "local server",
        "connection": "Direct DB (JDBC/ODBC)",
    }

    # Sync entities mapped to actual Oracle tables in Lighthouse V15
    sync_entities = [
        {"value": "all", "label": "All Entities", "table": None,
         "description": "Sync every enabled entity below"},
        {"value": "customer_orders", "label": "Customer Orders", "table": "Itemtran_Head",
         "description": "Sales order headers — customer, due date, alloy, tons"},
        {"value": "item_master", "label": "Item Master", "table": "Item_Mast",
         "description": "Bills of material and extrusion item definitions"},
        {"value": "chart_of_accounts", "label": "Chart of Accounts", "table": "Acc_Mast",
         "description": "Customer / vendor / ledger account master"},
        {"value": "transaction_body", "label": "Transaction Body", "table": "Itemtran_Body",
         "description": "Line-item detail (quantities, rates, batches)"},
    ]

    # Major production tables exposed in Lighthouse V15
    production_tables = [
        {"name": "Itemtran_Head",  "description": "Transaction headers — customer orders, GRN, delivery challans"},
        {"name": "Itemtran_Body",  "description": "Line-item detail linked to each header record"},
        {"name": "Acc_Mast",       "description": "Account master — customers, vendors, ledgers"},
        {"name": "Item_Mast",      "description": "Item master — profiles, alloys, dies, BOMs"},
    ]

    # Mock preview: metadata a real run would surface before committing
    mock_preview = [
        {"entity": "Customer Orders",  "table": "Itemtran_Head", "pending": 12,
         "last_sync": "2026-06-30 08:15", "direction": "INBOUND"},
        {"entity": "Item Master",      "table": "Item_Mast",     "pending": 3,
         "last_sync": "2026-06-29 22:00", "direction": "INBOUND"},
        {"entity": "Chart of Accounts","table": "Acc_Mast",      "pending": 0,
         "last_sync": "2026-06-30 06:00", "direction": "INBOUND"},
        {"entity": "Transaction Body", "table": "Itemtran_Body", "pending": 47,
         "last_sync": "2026-06-30 08:15", "direction": "INBOUND"},
        {"entity": "Die Inspections",  "table": "OUTBOUND → ERP","pending": 2,
         "last_sync": "2026-06-30 07:40", "direction": "OUTBOUND"},
        {"entity": "Die Tests",        "table": "OUTBOUND → ERP","pending": 1,
         "last_sync": "2026-06-30 07:40", "direction": "OUTBOUND"},
        {"entity": "Nitriding Records","table": "OUTBOUND → ERP","pending": 0,
         "last_sync": "2026-06-30 07:40", "direction": "OUTBOUND"},
    ]

    return render_template(
        "integrations/erp_sync.html",
        logs=logs,
        erp_config=erp_config,
        sync_entities=sync_entities,
        production_tables=production_tables,
        mock_preview=mock_preview,
    )


@bp.route("/erp/trigger", methods=["POST"])
def erp_trigger():
    entity = request.form.get("entity", "all")
    log = ErpSyncLog(
        entity_type=entity,
        status="pending",
        triggered_by=request.form.get("triggered_by", "manual"),
        started_at=datetime.utcnow(),
    )
    db.session.add(log)
    db.session.commit()
    flash(f"ERP sync for '{entity}' queued (id={log.id}).", "info")
    return redirect(url_for("integrations.erp_sync"))


@bp.route("/webhooks", methods=["GET"])
def webhooks():
    hooks = Webhook.query.order_by(Webhook.created_at.desc()).all()
    return render_template("integrations/webhooks.html", hooks=hooks)


@bp.route("/webhooks/create", methods=["POST"])
def webhook_create():
    hook = Webhook(
        name=request.form["name"],
        url=request.form["url"],
        event_type=request.form["event_type"],
        secret=request.form.get("secret", ""),
        is_active=True,
    )
    db.session.add(hook)
    db.session.commit()
    flash(f"Webhook '{hook.name}' created.", "success")
    return redirect(url_for("integrations.webhooks"))


@bp.route("/webhooks/delete/<int:id>", methods=["POST"])
def webhook_delete(id):
    hook = Webhook.query.get_or_404(id)
    db.session.delete(hook)
    db.session.commit()
    flash("Webhook deleted.", "success")
    return redirect(url_for("integrations.webhooks"))


@bp.route("/api-docs", methods=["GET"])
def api_docs():
    keys = ApiKey.query.order_by(ApiKey.created_at.desc()).all()
    return render_template("integrations/api_docs.html", keys=keys)


@bp.route("/api-docs/generate", methods=["POST"])
def api_key_generate():
    import secrets
    key = ApiKey(
        name=request.form["name"],
        key_value=secrets.token_hex(32),
        scope=request.form.get("scope", "read"),
        is_active=True,
    )
    db.session.add(key)
    db.session.commit()
    flash(f"API key '{key.name}' generated.", "success")
    return redirect(url_for("integrations.api_docs"))


@bp.route("/api-docs/revoke/<int:id>", methods=["POST"])
def api_key_revoke(id):
    key = ApiKey.query.get_or_404(id)
    key.is_active = False
    db.session.commit()
    flash(f"API key '{key.name}' revoked.", "warning")
    return redirect(url_for("integrations.api_docs"))


# ── PLC connectors ───────────────────────────────────────────────────────────
@bp.route("/plc-connectors", methods=["GET"])
def plc_connectors():
    """List all machines with their PLC mappings."""
    from ..models import Machine, PLCSignalMapping
    machines = Machine.query.order_by(Machine.name.asc()).all()

    # Group signal mappings by machine
    machine_signals = {}
    for mapping in PLCSignalMapping.query.order_by(PLCSignalMapping.signal_tag.asc()).all():
        machine = mapping.machine_name
        if machine not in machine_signals:
            machine_signals[machine] = []
        machine_signals[machine].append(mapping)

    return render_template(
        "integrations/plc_connectors.html",
        machines=machines,
        machine_signals=machine_signals,
    )


# ── Signal mapping ───────────────────────────────────────────────────────────
@bp.route("/signal-mapping", methods=["GET"])
def signal_mapping():
    """View/edit PLC signal mappings."""
    from ..models import PLCSignalMapping
    mappings = PLCSignalMapping.query.order_by(
        PLCSignalMapping.machine_name.asc(),
        PLCSignalMapping.signal_tag.asc()
    ).all()
    return render_template(
        "integrations/signal_mapping.html",
        mappings=mappings,
    )


@bp.route("/signal-mapping/new", methods=["POST"])
def signal_mapping_new():
    """Create a new PLC signal mapping."""
    import uuid
    from ..models import PLCSignalMapping

    mapping = PLCSignalMapping(
        id=str(uuid.uuid4()),
        machine_name=request.form.get("machine_name", ""),
        signal_tag=request.form.get("signal_tag", ""),
        signal_type=request.form.get("signal_type", "ACTUAL"),
        unit=request.form.get("unit"),
        process_type=request.form.get("process_type"),
        scale_factor=float(request.form.get("scale_factor") or 1.0),
        offset=float(request.form.get("offset") or 0.0),
        is_active="is_active" in request.form,
    )
    db.session.add(mapping)
    db.session.commit()
    flash(f"Signal mapping '{mapping.signal_tag}' created.", "success")
    return redirect(url_for("integrations.signal_mapping"))


@bp.route("/signal-mapping/toggle/<string:id>", methods=["POST"])
def signal_mapping_toggle(id):
    """Toggle a signal mapping's active status."""
    import uuid
    from ..models import PLCSignalMapping
    mapping = PLCSignalMapping.query.get_or_404(id)
    mapping.is_active = not mapping.is_active
    db.session.commit()
    flash(f"Signal mapping '{mapping.signal_tag}' {'enabled' if mapping.is_active else 'disabled'}.", "success")
    return redirect(url_for("integrations.signal_mapping"))


# ── Integration jobs ─────────────────────────────────────────────────────────
@bp.route("/jobs", methods=["GET"])
def jobs():
    """List all integration jobs (ERP + PLC)."""
    from ..models import IntegrationJob
    status_filter = request.args.get("status", "")
    q = IntegrationJob.query
    if status_filter:
        q = q.filter_by(status=status_filter)
    jobs_list = q.order_by(IntegrationJob.created_at.desc()).limit(200).all()
    return render_template(
        "integrations/jobs.html",
        jobs=jobs_list,
        status=status_filter,
    )


@bp.route("/jobs/<string:id>/retry", methods=["POST"])
def job_retry(id):
    """Re-queue a failed integration job."""
    import uuid
    from ..models import IntegrationJob
    from datetime import timedelta
    job = IntegrationJob.query.get_or_404(id)
    if job.status == "Failed":
        job.status = "RetryQueued"
        job.retries = 0
        job.next_retry_at = datetime.utcnow() + timedelta(minutes=1)
        db.session.commit()
        flash(f"Job {job.id} queued for retry.", "success")
    else:
        flash(f"Job {job.id} is not in Failed status.", "warning")
    return redirect(url_for("integrations.jobs"))


# ── ERP reprocess ────────────────────────────────────────────────────────────
@bp.route("/erp/reprocess", methods=["POST"])
def erp_reprocess():
    """Re-process a batch of unposted ERP records (inspections, tests, nitridings)."""
    from ..models import DieInspection, DieTest, NitridingRecord
    from ..services.erp_adapter import ERPAdapter

    unposted_inspections = DieInspection.query.filter_by(erp_posted=False).all()
    unposted_tests = DieTest.query.filter_by(erp_posted=False).all()
    unposted_nitridings = NitridingRecord.query.filter_by(erp_posted=False).all()

    posted = 0
    failed = 0
    for rec in unposted_inspections:
        result = ERPAdapter.post_inspection(rec)
        if result.get("success"):
            posted += 1
        else:
            failed += 1
    for rec in unposted_tests:
        result = ERPAdapter.post_test(rec)
        if result.get("success"):
            posted += 1
        else:
            failed += 1
    for rec in unposted_nitridings:
        result = ERPAdapter.post_nitriding(rec)
        if result.get("success"):
            posted += 1
        else:
            failed += 1

    flash(
        f"ERP reprocess: {posted} posted, {failed} failed.",
        "success" if failed == 0 else "warning",
    )
    return redirect(url_for("integrations.erp_sync"))
