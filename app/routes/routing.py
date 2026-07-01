from flask import Blueprint, render_template, request, redirect, url_for, flash
from .. import db
from ..models import RoutingStep

bp = Blueprint("routing", __name__)


@bp.route("/routing", methods=["GET"])
def list_routing():
    part_filter = request.args.get("part", "")

    query = RoutingStep.query.order_by(RoutingStep.operation_sequence.asc())
    if part_filter:
        query = query.filter_by(part_number=part_filter)

    steps = query.all()
    part_numbers = (
        db.session.query(RoutingStep.part_number)
        .distinct()
        .order_by(RoutingStep.part_number.asc())
        .all()
    )
    part_numbers = [p[0] for p in part_numbers]

    return render_template(
        "routing/management.html",
        steps=steps,
        part_numbers=part_numbers,
        part_filter=part_filter,
    )


@bp.route("/routing/new", methods=["GET", "POST"])
def create_routing_step():
    if request.method == "POST":
        part_number = request.form.get("part_number")
        operation_sequence = int(request.form.get("operation_sequence") or 0)
        operation_name = request.form.get("operation_name")
        workstation_type = request.form.get("workstation_type") or None
        standard_cycle_time_sec = float(request.form.get("standard_cycle_time_sec") or 0)

        if not part_number or not operation_name or operation_sequence <= 0 or standard_cycle_time_sec <= 0:
            flash("Part, operation, sequence, and positive cycle time are required.", "error")
            return redirect(url_for("routing.create_routing_step"))

        step = RoutingStep(
            part_number=part_number,
            operation_sequence=operation_sequence,
            operation_name=operation_name,
            workstation_type=workstation_type,
            standard_cycle_time_sec=standard_cycle_time_sec,
        )
        db.session.add(step)
        db.session.commit()
        flash("Routing step created.", "success")
        return redirect(url_for("routing.list_routing"))

    return render_template("routing/form.html")
