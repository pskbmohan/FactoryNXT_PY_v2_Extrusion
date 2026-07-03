import csv
import io
import os
import threading
from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.utils import secure_filename
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


# ── Wattmon integration: CSV upload & log viewer ─────────────────────────────
#
# The Wattmon integration device pushes its energy-meter data as a POST to
# /integrations/csv-upload with ``application/x-www-form-urlencoded``:
#
#     key=<MAC>&data=<csv-body>
#
# where ``<csv-body>`` is the full CSV (header row + data rows, ``\n``
# separated). The endpoint below parses that body, stores rows in the
# :class:`WattmonReading` table with fixed columns mirroring the canonical
# header list (216 columns: ts, timestamp, 9 Schneider series × 31 cols each,
# 1 Rishabh series × 19 cols), and returns ``{"status":"ok",...}`` so the
# device does not time out.
#
# Browser-style multipart uploads and raw ``text/csv`` POSTs are still
# accepted for ad-hoc testing.
#
# View pages:
#   GET  /integrations/csv-upload          — upload form + API docs
#   GET  /integrations/wattmon             — list of uploads w/ timestamps
#   GET  /integrations/wattmon/<id>        — one upload + all its readings
#   POST /integrations/wattmon/<id>/delete — remove an upload

_WATMON_HEADER_TO_COL = None  # lazily populated by _wattmon_map()


def _wattmon_map():
    """Return {csv_header_name: WattmonReading column attribute} once."""
    global _WATMON_HEADER_TO_COL
    from .. import models as m
    if _WATMON_HEADER_TO_COL is None:
        _WATMON_HEADER_TO_COL = {}
        for h in m._WATMON_COLUMNS:
            attr = getattr(m.WattmonReading, h, None)
            if attr is not None:
                _WATMON_HEADER_TO_COL[h] = attr
    return _WATMON_HEADER_TO_COL


def _wants_json():
    """Return True when the caller is a server / API client (not a browser form)."""
    best = request.accept_mimetypes.best_match(["application/json", "text/html"])
    return (
        best == "application/json"
        or (request.content_type or "").startswith("text/csv")
        or (request.content_type or "").startswith("application/json")
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    )


def _parse_csv_body(raw_bytes):
    """Decode + parse CSV bytes, returning (headers, rows).
    Raises ``ValueError`` on empty / unparseable inputs.
    """
    text = raw_bytes.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    try:
        headers = next(reader)
    except StopIteration:
        raise ValueError("The CSV file is empty.")
    rows = [r for r in reader if any(cell.strip() for cell in r)]
    if not rows:
        raise ValueError("CSV has headers but no data rows.")
    # Normalise header whitespace (keep column names as-is, they include dots)
    headers = [h.strip() for h in headers]
    return headers, rows


@bp.route("/csv-upload", methods=["GET"])
def csv_upload():
    """Display the CSV upload form (Wattmon integration)."""
    from ..models import WattmonUpload
    latest = WattmonUpload.query.order_by(WattmonUpload.uploaded_at.desc()).first()
    return render_template("integrations/csv_upload.html", latest=latest)


def _parse_form_urlencoded_raw(raw_bytes):
    """Parse the integration device's quirky mixed-format body.

    The device sends ONE POST with:
      - ``key=<MAC>&data=<header row>``  (URL-encoded)
      - followed by literal ``\\n`` + raw CSV data rows (NOT URL-encoded)

    This function extracts ``key`` and the full CSV text (header + data rows).
    Standard form parsers choke on this mix; we do a two-stage parse:
      1. Split on the first ``\\n``/``\\r`` to separate the form-encoded prefix
         from the raw trailer.
      2. URL-decode the prefix to pull ``key`` and ``data`` (header).
      3. Concatenate the header with the raw trailer to form the full CSV.
    """
    try:
        text = raw_bytes.decode("utf-8", errors="replace")
    except Exception:
        return {"key": None, "csv": ""}

    # Find the first newline — everything before it is the form-encoded key&data=...
    idx = -1
    for i, ch in enumerate(text):
        if ch == "\n" or ch == "\r":
            idx = i
            break

    if idx == -1:
        # No data rows after header — just key=...&data=<header>
        prefix = text
        trailer = ""
    else:
        prefix = text[:idx]
        trailer = text[idx:].lstrip("\r\n")

    # Parse key=...&data=... from the prefix
    key = None
    header = ""
    for pair in prefix.split("&"):
        if "=" not in pair:
            continue
        k, v = pair.split("=", 1)
        from urllib.parse import unquote_plus
        k = unquote_plus(k)
        if k == "key":
            key = unquote_plus(v)
        elif k == "data":
            header = unquote_plus(v)

    csv_text = header + ("\n" + trailer if trailer else "")
    return {"key": key, "csv": csv_text}


@bp.route("/csv-upload", methods=["POST"])
def csv_upload_submit():
    """Accept a Wattmon CSV POST (no authentication required).

    The real integration device sends a hybrid body: a URL-encoded
    ``key=<MAC>&data=<header>`` prefix followed by raw CSV data rows. This
    endpoint saves the raw body to disk IMMEDIATELY and returns a ``200 OK``
    response within ~100 ms so the device doesn't time out. CSV parsing and
    row insertion happen in a background thread.

    Also accepts:
      - ``multipart/form-data`` with a ``csv_file`` field (browser upload)
      - Raw ``Content-Type: text/csv`` body (server-to-server push)
    """
    from ..models import WattmonUpload

    ct = (request.content_type or "").lower()
    source_key = None
    filename = "upload.csv"
    raw_bytes = b""

    try:
        if "multipart/form-data" in ct:
            uploaded = request.files.get("csv_file")
            if not uploaded or not uploaded.filename:
                return _error_response(400, "no_file", "No csv_file field in the multipart upload.")
            filename = uploaded.filename or "upload.csv"
            source_key = request.form.get("key")
            raw_bytes = uploaded.stream.read()
        elif "application/x-www-form-urlencoded" in ct:
            raw_bytes = request.get_data(cache=False)
        else:
            raw_bytes = request.get_data(cache=False)
            source_key = request.headers.get("X-Key") or request.args.get("key")
            filename = (
                request.headers.get("X-Filename")
                or request.args.get("filename")
                or f"wattmon_{source_key or 'unknown'}.csv"
            )
    except Exception as e:
        current_app.logger.exception("wattmon: error reading request body")
        return _error_response(500, "read_error", f"Could not read request body: {e}")

    if not raw_bytes:
        return _error_response(400, "empty_body", "The request body was empty.")

    # ── Step 1: create upload record IMMEDIATELY so we can return fast ────
    upload = WattmonUpload(
        source_key=source_key,
        filename=filename,
        row_count=0,
        uploaded_at=datetime.utcnow(),
        status="pending",
    )
    db.session.add(upload)
    db.session.flush()

    # Save raw body to disk so it's never lost even if parsing fails
    app = current_app._get_current_object()
    upload_dir = os.path.join(app.instance_path, "wattmon_uploads")
    os.makedirs(upload_dir, exist_ok=True)
    raw_path = os.path.join(upload_dir, f"{upload.id}.raw")
    with open(raw_path, "wb") as f:
        f.write(raw_bytes)

    upload_id = upload.id  # grab before committing
    db.session.commit()

    # ── Step 2: spawn background worker ────────────────────────────────────
    # Pass the app object explicitly — Flask context locals are not visible
    # inside the spawned thread.
    t = threading.Thread(
        target=_process_wattmon_upload,
        args=(app, upload_id, raw_bytes, raw_path),
        daemon=True,
    )
    t.start()

    # ── Step 3: return IMMEDIATELY ─────────────────────────────────────────
    elapsed = (datetime.utcnow() - upload.uploaded_at).total_seconds()
    result = {
        "status": "accepted",
        "upload_id": upload_id,
        "source_key": source_key,
        "filename": filename,
        "bytes_received": len(raw_bytes),
        "uploaded_at": upload.uploaded_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "handler_elapsed_s": round(elapsed, 3),
        "detail_url": url_for("integrations.wattmon_detail", upload_id=upload_id, _external=False),
    }
    if _wants_json():
        return jsonify(result), 200

    flash(f"Wattmon upload #{upload_id} accepted ({len(raw_bytes)} bytes). Processing in background.", "success")
    return redirect(url_for("integrations.wattmon_detail", upload_id=upload_id))


def _process_wattmon_upload(app, upload_id, raw_bytes, raw_path):
    """Background worker: parse CSV, insert readings, update upload status.

    Runs in a daemon thread so the request returns immediately.
    ``app`` is the Flask application object passed explicitly by the request
    handler (Flask context locals are not visible inside spawned threads).
    """
    from ..models import WattmonUpload, WattmonReading

    with app.app_context():
        upload = db.session.get(WattmonUpload, upload_id)
        if upload is None:
            return

        try:
            # Extract CSV from the quirky device format
            csv_text = None
            ct_guess = "raw"
            if raw_bytes[:100].startswith(b"key=") or raw_bytes[:100].startswith(b"data="):
                # Device format: mixed form-encoded + raw rows
                parsed = _parse_form_urlencoded_raw(raw_bytes)
                if upload.source_key is None and parsed.get("key"):
                    upload.source_key = parsed["key"]
                csv_text = parsed.get("csv", "")
            else:
                # Plain CSV
                csv_text = raw_bytes.decode("utf-8-sig")

            if not csv_text:
                upload.status = "failed"
                upload.error_detail = "No CSV content found in body."
                db.session.commit()
                return

            # Parse CSV text
            reader = csv.reader(io.StringIO(csv_text))
            headers = next(reader, None)
            if not headers:
                upload.status = "failed"
                upload.error_detail = "CSV is empty."
                db.session.commit()
                return
            headers = [h.strip() for h in headers]
            header_index = {h: i for i, h in enumerate(headers)}

            col_by_name = _wattmon_map()
            rows = [r for r in reader if any(cell.strip() for cell in r)]

            upload.row_count = len(rows)

            # Bulk insert readings
            reading_dicts = []
            for row in rows:
                values = {"upload_id": upload_id}
                for col_name, col_attr in col_by_name.items():
                    idx = header_index.get(col_name)
                    if idx is not None and idx < len(row):
                        values[col_attr.key] = row[idx]
                ts_val = values.get("ts")
                if ts_val:
                    try:
                        epoch = int(float(str(ts_val).strip()))
                        values["timestamp"] = datetime.utcfromtimestamp(epoch).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                    except Exception:
                        values["timestamp"] = str(ts_val)
                reading_dicts.append(values)

            db.session.bulk_insert_mappings(WattmonReading, reading_dicts)
            upload.status = "success"
            upload.error_detail = None
            db.session.commit()
            app.logger.info(
                "wattmon #%d: inserted %d readings (key=%s)",
                upload_id, len(rows), upload.source_key or "-",
            )

        except Exception as e:
            db.session.rollback()
            app.logger.exception("wattmon #%d: background insert failed", upload_id)
            upload = db.session.get(WattmonUpload, upload_id)
            if upload:
                upload.status = "failed"
                upload.error_detail = f"{type(e).__name__}: {e}"
                db.session.commit()


def _error_response(status, code, message):
    """Return JSON for API callers or flash-and-redirect for browsers."""
    if _wants_json():
        return jsonify({"status": "error", "error": code, "message": message}), status
    flash(message, "warning")
    return redirect(url_for("integrations.csv_upload"))


@bp.route("/wattmon", methods=["GET"])
def wattmon_list():
    """List every Wattmon CSV upload with its source, timestamp and status."""
    from ..models import WattmonUpload
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    per_page = max(10, min(per_page, 500))
    q = WattmonUpload.query.order_by(WattmonUpload.uploaded_at.desc())
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)
    any_pending = any(u.status in ("pending", "processing") for u in pagination.items)
    return render_template(
        "integrations/wattmon_list.html",
        uploads=pagination.items,
        pagination=pagination,
        any_pending=any_pending,
    )


@bp.route("/wattmon/<int:upload_id>", methods=["GET"])
def wattmon_detail(upload_id):
    """Show one upload + its readings with uploaded timestamp."""
    from ..models import WattmonUpload, WattmonReading
    upload = db.session.get(WattmonUpload, upload_id)
    if upload is None:
        from flask import abort
        abort(404)

    # Paginate readings so huge uploads don't swamp the template
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 100, type=int)
    per_page = max(10, min(per_page, 1000))
    readings_q = upload.readings.order_by(WattmonReading.id.asc())
    readings_page = readings_q.paginate(page=page, per_page=per_page, error_out=False)

    import app.models as m
    columns = m._WATMON_COLUMNS

    # Pre-build per-row dicts keyed by column name so the template can do
    # `row[col]` on a plain dict (SQLAlchemy models don't support subscript).
    readings_rows = []
    for r in readings_page.items:
        row_dict = {col: (getattr(r, col) or "") for col in columns}
        readings_rows.append(row_dict)

    return render_template(
        "integrations/wattmon_detail.html",
        upload=upload,
        readings=readings_rows,
        readings_pagination=readings_page,
        columns=columns,
        total_readings=upload.row_count,
    )


@bp.route("/wattmon/<int:upload_id>/delete", methods=["POST"])
def wattmon_delete(upload_id):
    """Delete an upload and its readings (cascades)."""
    from ..models import WattmonUpload
    upload = WattmonUpload.query.get_or_404(upload_id)
    db.session.delete(upload)
    db.session.commit()
    flash(f"Wattmon upload #{upload.id} deleted.", "success")
    return redirect(url_for("integrations.wattmon_list"))

