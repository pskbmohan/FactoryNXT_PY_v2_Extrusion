from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
from .. import db
from ..models import Container, ContainerWeighEvent, ContainerMovement, WorkOrder
import uuid

bp = Blueprint("containers", __name__)


@bp.route("/containers")
def list_containers():
    containers = Container.query.order_by(Container.container_code).all()
    return render_template("containers/list.html", containers=containers)


@bp.route("/containers/new", methods=["GET", "POST"])
def create_container():
    if request.method == "POST":
        container_code = request.form.get("container_code")
        if not container_code:
            flash("Container Code is required.", "error")
            return redirect(url_for("containers.create_container"))
        container = Container(
            id=str(uuid.uuid4()),
            container_code=container_code,
            container_type=request.form.get("container_type") or "tray",
            tare_weight_kg=float(request.form.get("tare_weight_kg") or 0) or None,
            max_capacity_kg=float(request.form.get("max_capacity_kg") or 0) or None,
            max_capacity_units=int(request.form.get("max_capacity_units") or 0) or None,
            status="available",
            current_location=request.form.get("current_location") or "Store",
            material=request.form.get("material"),
        )
        db.session.add(container)
        db.session.commit()
        flash(f"Container {container.container_code} created.", "success")
        return redirect(url_for("containers.detail", id=container.id))

    return render_template("containers/form.html", container=None)


@bp.route("/containers/<id>")
def detail(id):
    container = Container.query.get_or_404(id)
    weigh_events = container.weigh_events.order_by(ContainerWeighEvent.weighed_at.desc()).limit(50).all()
    movements = container.movements.order_by(ContainerMovement.moved_at.desc()).limit(50).all()
    return render_template(
        "containers/detail.html",
        container=container,
        weigh_events=weigh_events,
        movements=movements,
    )


@bp.route("/containers/<id>/weigh", methods=["POST"])
def weigh(id):
    container = Container.query.get_or_404(id)
    gross = float(request.form.get("gross_weight_kg") or 0)
    tare = float(request.form.get("tare_weight_kg") or container.tare_weight_kg or 0)
    net = round(gross - tare, 3)
    expected = float(request.form.get("expected_weight_kg") or 0) or None
    variance_pct = None
    status = "OK"
    if expected and expected > 0:
        variance_pct = round(100 * (net - expected) / expected, 2)
        if variance_pct > 5:
            status = "OVER"
        elif variance_pct < -5:
            status = "UNDER"

    event = ContainerWeighEvent(
        id=str(uuid.uuid4()),
        container_id=container.id,
        wo_id=request.form.get("wo_id") or container.current_wo_id,
        gross_weight_kg=gross,
        tare_weight_kg=tare,
        net_weight_kg=net,
        expected_weight_kg=expected,
        weight_variance_percent=variance_pct,
        weigh_station=request.form.get("weigh_station"),
        operator_id=request.form.get("operator_id") or "Operator",
    )
    event.status = status
    db.session.add(event)
    db.session.commit()
    flash(f"Weigh event recorded: net {net} kg [{status}].", "success" if status == "OK" else "error")
    return redirect(url_for("containers.detail", id=container.id))


@bp.route("/containers/<id>/move", methods=["POST"])
def move(id):
    container = Container.query.get_or_404(id)
    new_location = request.form.get("to_location")
    if not new_location:
        flash("Destination location required.", "error")
        return redirect(url_for("containers.detail", id=container.id))
    movement = ContainerMovement(
        id=str(uuid.uuid4()),
        container_id=container.id,
        from_location=container.current_location,
        to_location=new_location,
        moved_by=request.form.get("moved_by") or "Operator",
        wo_id=container.current_wo_id,
    )
    container.current_location = new_location
    db.session.add(movement)
    db.session.commit()
    flash(f"Container moved to {new_location}.", "success")
    return redirect(url_for("containers.detail", id=container.id))


@bp.route("/containers/<id>/assign-wo", methods=["POST"])
def assign_wo(id):
    container = Container.query.get_or_404(id)
    wo_id = request.form.get("wo_id")
    container.current_wo_id = wo_id or None
    container.status = "in_use" if wo_id else "available"
    db.session.commit()
    flash("Work Order assigned to container." if wo_id else "Work Order cleared.", "success")
    return redirect(url_for("containers.detail", id=container.id))


@bp.route("/api/containers/real-time-locations")
def real_time_locations():
    from sqlalchemy import func
    locs = (
        db.session.query(Container.current_location, func.count(Container.id))
        .group_by(Container.current_location)
        .all()
    )
    return jsonify([{"location": l or "Unassigned", "count": c} for l, c in locs])
