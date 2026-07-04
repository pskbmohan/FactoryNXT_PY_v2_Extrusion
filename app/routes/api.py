from flask import Blueprint, jsonify, request, current_app
from ..models import Line, WattmonUpload
from .. import db
import threading
from datetime import datetime

bp = Blueprint("api", __name__)


@bp.get("/status")
def status():
    lines = Line.query.all()
    return jsonify(
        {
            "lines": [
                {"id": line.id, "name": line.name, "status": line.status}
                for line in lines
            ]
        }
    )


@bp.post("/csv-upload")
def csv_upload():
    """
    Dedicated API endpoint for Wattmon CSV upload.

    Accepts: application/x-www-form-urlencoded
    Fields:  key=<device_key>&data=<csv_blob>

    Returns: JSON response with upload status
    - Returns immediately (fast response)
    - Processes CSV in background thread
    - Saves raw payload to disk for audit trail
    """
    # Parse the CSV using the same logic as integrations.py
    from .integrations import _extract_wattmon_csv, _process_wattmon_upload
    import os

    try:
        parsed = _extract_wattmon_csv(request)
        source_key = parsed["key"]
        csv_text = parsed["csv"]

        if not csv_text:
            return jsonify({
                "status": "error",
                "message": "No CSV data found",
                "device_key": source_key
            }), 400

        # Create upload record
        upload = WattmonUpload(
            source_key=source_key or "api-upload",
            row_count=0,
            status="pending"
        )
        db.session.add(upload)
        db.session.commit()

        # Save raw CSV to disk
        app = current_app._get_current_object()
        upload_dir = os.path.join(app.instance_path, "wattmon_uploads")
        os.makedirs(upload_dir, exist_ok=True)

        csv_path = os.path.join(upload_dir, f"{upload.id}.csv")
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write(csv_text)

        # Process in background thread (same as integrations endpoint).
        # Pass csv_bytes=None so the worker reads the on-disk CSV we just saved.
        t = threading.Thread(
            target=_process_wattmon_upload,
            args=(app, upload.id, None, csv_path),
            daemon=True
        )
        t.start()

        # Return immediately (fast response)
        return jsonify({
            "status": "success",
            "message": "Upload accepted, processing in background",
            "upload_id": upload.id,
            "device_key": source_key
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"API csv-upload failed: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@bp.get("/uploads")
def list_uploads():
    """
    API endpoint to list recent Wattmon uploads.
    Returns JSON array of upload metadata.
    """
    try:
        # Get last 50 uploads
        uploads = WattmonUpload.query.order_by(
            WattmonUpload.uploaded_at.desc()
        ).limit(50).all()

        result = []
        for u in uploads:
            result.append({
                "id": u.id,
                "source_key": u.source_key,
                "filename": u.filename,
                "row_count": u.row_count,
                "status": u.status,
                "uploaded_at": u.uploaded_at.strftime("%Y-%m-%d %H:%M:%S"),
                "error_detail": u.error_detail
            })

        return jsonify({
            "status": "success",
            "count": len(result),
            "uploads": result
        }), 200

    except Exception as e:
        current_app.logger.error(f"API list_uploads failed: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@bp.get("/uploads/<int:upload_id>")
def get_upload(upload_id):
    """
    API endpoint to get details of a specific upload.
    Returns JSON with upload metadata and a sample of EAV rows.

    Readings are now stored as flat (device_key, column_name, value, row_index,
    epoch_ts) tuples — one DB row per CSV cell, not per CSV row. Sample is the
    first 50 EAV rows ordered by insertion order.
    """
    try:
        upload = WattmonUpload.query.get(upload_id)
        if not upload:
            return jsonify({
                "status": "error",
                "message": f"Upload {upload_id} not found"
            }), 404

        # First 50 EAV rows in insertion order
        sample_rows = []
        for r in upload.readings.limit(50):
            sample_rows.append({
                "column_name": r.column_name,
                "value": r.value,
                "row_index": r.row_index,
                "epoch_ts": r.epoch_ts,
            })

        return jsonify({
            "status": "success",
            "upload": {
                "id": upload.id,
                "source_key": upload.source_key,
                "filename": upload.filename,
                "row_count": upload.row_count,          # CSV rows accepted (not EAV rows)
                "status": upload.status,
                "uploaded_at": upload.uploaded_at.strftime("%Y-%m-%d %H:%M:%S"),
                "error_detail": upload.error_detail,
                "sample_rows": sample_rows,
            }
        }), 200

    except Exception as e:
        current_app.logger.error(f"API get_upload failed: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

