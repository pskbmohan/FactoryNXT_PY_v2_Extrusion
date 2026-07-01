from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
from .. import db
from ..models import FinishingOrder, FinishingProcessType, WorkOrder, Container, NCR
import json
import uuid

bp = Blueprint("finishing", __name__)


@bp.route("/finishing")
def list_orders():
    process_types = FinishingProcessType.query.order_by(FinishingProcessType.name).all()
    orders = FinishingOrder.query.order_by(FinishingOrder.created_at.desc()).all()
    counts = {}
    for pt in process_types:
        counts[pt.id] = FinishingOrder.query.filter_by(
            process_type_id=pt.id, status="pending"
        ).count()
    return render_template("finishing/list.html", orders=orders, process_types=process_types, counts=counts)


@bp.route("/finishing/new", methods=["GET", "POST"])
def create_order():
    if request.method == "POST":
        order_number = request.form.get("order_number")
        wo_id = request.form.get("wo_id")
        process_type_id = request.form.get("process_type_id")
        if not order_number or not wo_id or not process_type_id:
            flash("Order number, Work Order, and Process Type required.", "error")
            return redirect(url_for("finishing.create_order"))

        params_json = request.form.get("parameters_json") or "{}"
        try:
            params = json.loads(params_json)
        except Exception:
            params = {}

        order = FinishingOrder(
            id=str(uuid.uuid4()),
            order_number=order_number,
            wo_id=wo_id,
            process_type_id=process_type_id,
            container_id=request.form.get("container_id") or None,
            sequence=int(request.form.get("sequence") or 1),
            parameters=params,
            operator_id=request.form.get("operator_id") or "Operator",
        )
        db.session.add(order)
        db.session.commit()
        flash("Finishing order created.", "success")
        return redirect(url_for("finishing.detail", id=order.id))

    work_orders = WorkOrder.query.filter(WorkOrder.status.in_(["RELEASED", "RUNNING"])).order_by(WorkOrder.order_number).all()
    process_types = FinishingProcessType.query.order_by(FinishingProcessType.name).all()
    containers = Container.query.filter_by(status="in_use").order_by(Container.container_code).all()
    return render_template("finishing/form.html", work_orders=work_orders, process_types=process_types, containers=containers, order=None)


@bp.route("/finishing/<id>")
def detail(id):
    order = FinishingOrder.query.get_or_404(id)
    return render_template("finishing/detail.html", order=order)


@bp.route("/finishing/<id>/start", methods=["POST"])
def start(id):
    order = FinishingOrder.query.get_or_404(id)
    order.started_at = datetime.utcnow()
    order.status = "running"

    if order.process_type and order.process_type.requires_plc_instruction:
        plc_payload = {
            "command": "EXECUTE",
            "process_type": order.process_type.code,
            "parameters": order.parameters or {},
            "order_number": order.order_number,
        }
        order.plc_command = plc_payload
        order.plc_ack_status = "PENDING"
    db.session.commit()
    flash("Finishing order started.", "success")
    return redirect(url_for("finishing.detail", id=order.id))


@bp.route("/finishing/<id>/complete", methods=["POST"])
def complete(id):
    order = FinishingOrder.query.get_or_404(id)
    order.completed_at = datetime.utcnow()
    order.status = "completed"
    params_json = request.form.get("actual_parameters_json")
    if params_json:
        try:
            order.parameters = json.loads(params_json)
        except Exception:
            pass
    db.session.commit()
    flash("Finishing order completed.", "success")
    return redirect(url_for("finishing.detail", id=order.id))


@bp.route("/finishing/<id>/reject", methods=["POST"])
def reject(id):
    order = FinishingOrder.query.get_or_404(id)
    order.status = "rejected"
    reason = request.form.get("remarks") or "Rejected by operator"

    ncr = NCR(
        id=str(datetime.utcnow().timestamp()),
        work_order_id=order.wo_id,
        description=f"Finishing rejection [{order.order_number}]: {reason}",
        severity="Major",
        status="Open",
        created_at=datetime.utcnow(),
    )
    order.remarks = reason
    db.session.add(ncr)
    db.session.commit()
    flash("Order rejected. NCR created.", "error")
    return redirect(url_for("finishing.detail", id=order.id))


@bp.route("/finishing/operator/<process_type_code>")
def operator_screen(process_type_code):
    pt = FinishingProcessType.query.filter_by(code=process_type_code).first_or_404()
    pending = (
        FinishingOrder.query
        .filter_by(process_type_id=pt.id, status="pending")
        .order_by(FinishingOrder.sequence, FinishingOrder.created_at)
        .all()
    )
    running = FinishingOrder.query.filter_by(process_type_id=pt.id, status="running").first()
    return render_template(
        "finishing/operator_screen.html",
        process_type=pt,
        pending=pending,
        running=running,
    )


@bp.route("/api/finishing/queue")
def queue_json():
    process_code = request.args.get("process_type")
    query = FinishingOrder.query.filter(FinishingOrder.status.in_(["pending", "running"]))
    if process_code:
        from ..models import FinishingProcessType
        pt = FinishingProcessType.query.filter_by(code=process_code).first()
        if pt:
            query = query.filter_by(process_type_id=pt.id)
    orders = query.order_by(FinishingOrder.created_at).all()
    return jsonify([
        {
            "id": o.id,
            "order_number": o.order_number,
            "wo": o.work_order.order_number if o.work_order else None,
            "process_type": o.process_type.code if o.process_type else None,
            "status": o.status,
            "parameters": o.parameters,
        }
        for o in orders
    ])
