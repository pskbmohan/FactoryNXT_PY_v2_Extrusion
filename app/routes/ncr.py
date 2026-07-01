from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime
from .. import db
from ..models import NCR, WorkOrder, BOMItem, RoutingStep

bp = Blueprint("ncr", __name__)


@bp.route("/quality/ncr", methods=["GET"])
def list_ncrs():
    filter_work_order = request.args.get("work_order", "all")
    filter_status = request.args.get("status", "all")

    query = NCR.query.order_by(NCR.created_at.desc())

    if filter_work_order != "all":
        query = query.filter(NCR.work_order_id == filter_work_order)
    if filter_status != "all":
        query = query.filter(NCR.status == filter_status)

    ncrs = query.all()

    work_orders = WorkOrder.query.order_by(WorkOrder.order_number.asc()).all()

    return render_template(
        "ncr/list.html",
        ncrs=ncrs,
        work_orders=work_orders,
        filter_work_order=filter_work_order,
        filter_status=filter_status,
    )


@bp.route("/quality/ncr/new", methods=["GET", "POST"])
def create_ncr():
    if request.method == "POST":
        defect_id = request.form.get("defect_id") or None
        work_order_id = request.form.get("work_order_id") or None
        description = request.form.get("description")
        severity = request.form.get("severity") or "Minor"
        status = request.form.get("status") or "Open"
        quarantine_location = request.form.get("quarantine_location") or None

        if not description:
            flash("Detailed NCR Description is required.", "error")
            return redirect(url_for("ncr.create_ncr"))

        now = datetime.utcnow()

        ncr = NCR(
            id=str(now.timestamp()),
            defect_id=defect_id,
            work_order_id=work_order_id,
            description=description,
            severity=severity,
            status=status,
            created_at=now,
            quarantine_location=quarantine_location,
        )
        db.session.add(ncr)
        db.session.commit()
        flash("NCR created successfully.", "success")
        return redirect(url_for("ncr.list_ncrs"))

    work_orders = WorkOrder.query.order_by(WorkOrder.order_number.asc()).all()

    return render_template("ncr/form.html", work_orders=work_orders)


@bp.route("/quality/ncr/<id>", methods=["GET"])
def detail(id):
    ncr = NCR.query.get_or_404(id)

    resolution_steps = []
    if ncr.disposition_details:
        resolution_steps.append(
            {
                "action": ncr.disposition_details,
                "completed_by": ncr.dispositioned_by or "Quality Manager",
                "date": ncr.resolved_at or ncr.created_at,
            }
        )
    else:
        resolution_steps.append(
            {
                "action": "Lock physical bins and quarantine boards on shelf",
                "completed_by": "Specialist",
                "date": ncr.created_at,
            }
        )

    return render_template(
        "ncr/detail.html",
        ncr=ncr,
        resolution_steps=resolution_steps,
    )
