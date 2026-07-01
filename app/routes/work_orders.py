from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime
from .. import db
from ..models import WorkOrder, BOMItem, RoutingStep

bp = Blueprint("work_orders", __name__)


@bp.route("/work-orders", methods=["GET", "POST"])
def list_create_work_orders():
    if request.method == "POST":
        order_number = request.form.get("wo_number")
        part_number = request.form.get("part_number")
        description = request.form.get("description")
        quantity = int(request.form.get("quantity") or 0)
        due_date_raw = request.form.get("due_date")
        priority = request.form.get("priority") or "Normal"
        status = request.form.get("status") or "Draft"

        if not order_number or not part_number or quantity <= 0 or not due_date_raw:
            flash("Order number, part number, quantity, and due date are required.", "error")
            return redirect(url_for("work_orders.list_create_work_orders"))

        due_date = datetime.fromisoformat(due_date_raw) if due_date_raw else None

        wo = WorkOrder(
            id=str(datetime.utcnow().timestamp()),
            order_number=order_number,
            part_number=part_number,
            description=description,
            quantity=quantity,
            status=status,
            due_date=due_date,
            priority=priority,
        )
        db.session.add(wo)
        db.session.commit()
        flash("Work order created", "success")
        return redirect(url_for("work_orders.list_create_work_orders"))

    status_filter = request.args.get("status", "all")
    min_qty = int(request.args.get("min_qty", "0"))

    query = WorkOrder.query
    if status_filter != "all":
        query = query.filter_by(status=status_filter)
    if min_qty > 0:
        query = query.filter(WorkOrder.quantity >= min_qty)

    work_orders = query.order_by(WorkOrder.due_date.asc().nullslast()).all()

    return render_template(
        "work_orders/management.html",
        work_orders=work_orders,
        status_filter=status_filter,
        min_qty=min_qty,
    )


@bp.route("/work-orders/<id>/status", methods=["POST"])
def update_status(id):
    new_status = request.form.get("status")
    wo = WorkOrder.query.get_or_404(id)

    allowed_transitions = {
        "Draft": ["Released", "Cancelled"],
        "Released": ["InProgress", "OnHold", "Cancelled"],
        "InProgress": ["Completed", "OnHold", "Cancelled"],
        "OnHold": ["InProgress", "Cancelled"],
        "Completed": ["Closed"],
        "Closed": [],
        "Cancelled": [],
    }

    if new_status not in allowed_transitions.get(wo.status, []):
        flash(f"Invalid status transition from {wo.status} to {new_status}", "error")
        return redirect(url_for("work_orders.list_create_work_orders"))

    wo.status = new_status
    db.session.commit()
    flash(f"Work order status updated to {new_status}", "success")
    return redirect(url_for("work_orders.list_create_work_orders"))


@bp.route("/work-orders/<id>/traveler", methods=["GET"])
def traveler(id):
    wo = WorkOrder.query.get_or_404(id)
    bom_items = BOMItem.query.filter_by(part_number=wo.part_number).all()
    routing_steps = RoutingStep.query.filter_by(part_number=wo.part_number).order_by(
        RoutingStep.operation_sequence.asc()
    ).all()

    return render_template(
        "work_orders/traveler.html",
        work_order=wo,
        bom_items=bom_items,
        routing_steps=routing_steps,
    )


@bp.route("/work-orders/<id>", methods=["GET"])
def detail(id):
    wo = WorkOrder.query.get_or_404(id)
    bom_items = BOMItem.query.filter_by(part_number=wo.part_number).all()
    routing_steps = RoutingStep.query.filter_by(part_number=wo.part_number).order_by(
        RoutingStep.operation_sequence.asc()
    ).all()

    return render_template(
        "work_orders/detail.html",
        work_order=wo,
        bom_items=bom_items,
        routing_steps=routing_steps,
    )
