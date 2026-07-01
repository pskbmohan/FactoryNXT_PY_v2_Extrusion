from flask import Blueprint, render_template, request, redirect, url_for, flash
from .. import db
from ..models import Station, WorkOrder, OperationTransaction, SerialNumber, RoutingStep

bp = Blueprint("stations", __name__, url_prefix="/stations")


@bp.route("/")
def manage():
    """Station Management (CRUD List)"""
    stations = Station.query.order_by(Station.name).all()
    return render_template("stations/manage.html", stations=stations)


@bp.route("/create", methods=["GET", "POST"])
def create():
    """Create a new Station"""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip()
        description = request.form.get("description", "").strip()

        if not name or not code:
            flash("Station Name and Code are required.", "error")
            return redirect(url_for("stations.create"))

        if Station.query.filter_by(name=name).first():
            flash("Station name already exists.", "error")
            return redirect(url_for("stations.create"))

        if Station.query.filter_by(code=code).first():
            flash("Station code already exists.", "error")
            return redirect(url_for("stations.create"))

        new_station = Station(name=name, code=code, description=description, is_active=True)
        db.session.add(new_station)
        db.session.commit()

        flash("Station created successfully.", "success")
        return redirect(url_for("stations.manage"))

    return render_template("stations/form.html", station=None)


@bp.route("/<int:station_id>/edit", methods=["GET", "POST"])
def edit(station_id):
    """Edit an existing Station"""
    station = Station.query.get_or_404(station_id)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip()
        description = request.form.get("description", "").strip()
        is_active = request.form.get("is_active") == "on"

        if not name or not code:
            flash("Station Name and Code are required.", "error")
            return redirect(url_for("stations.edit", station_id=station.id))

        # Check for uniqueness, excluding current station
        if Station.query.filter(Station.name == name, Station.id != station.id).first():
            flash("Station name already exists.", "error")
            return redirect(url_for("stations.edit", station_id=station.id))

        if Station.query.filter(Station.code == code, Station.id != station.id).first():
            flash("Station code already exists.", "error")
            return redirect(url_for("stations.edit", station_id=station.id))

        station.name = name
        station.code = code
        station.description = description
        station.is_active = is_active
        db.session.commit()

        flash("Station updated successfully.", "success")
        return redirect(url_for("stations.manage"))

    return render_template("stations/form.html", station=station)


@bp.route("/<int:station_id>/delete", methods=["POST"])
def delete(station_id):
    """Delete a Station"""
    station = Station.query.get_or_404(station_id)

    # Optional: Check if station is in use before deleting
    in_use = RoutingStep.query.filter_by(station_name=station.name).first() or \
             OperationTransaction.query.filter_by(station_id=station.id).first()

    if in_use:
        flash("Cannot delete station: it is currently referenced in routings or operation history.", "error")
    else:
        db.session.delete(station)
        db.session.commit()
        flash("Station deleted successfully.", "success")

    return redirect(url_for("stations.manage"))


@bp.route("/summary")
def summary():
    """Station Operational Summary Dashboard"""
    stations = Station.query.filter_by(is_active=True).order_by(Station.name).all()

    # Current running work orders
    running_wos = WorkOrder.query.filter(WorkOrder.status == "RUNNING").all()

    station_id = request.args.get("station_id", type=int)
    selected_station = Station.query.get(station_id) if station_id else (stations[0] if stations else None)

    ready_for_checkin = []
    checked_out_pass = []
    checked_out_fail = []

    if selected_station:
        # Recent transactions for this station
        recent_tx = OperationTransaction.query.filter_by(station_id=selected_station.id)\
            .order_by(OperationTransaction.created_at.desc()).limit(20).all()

        checked_out_pass = [tx for tx in recent_tx if tx.result == "OK"]
        checked_out_fail = [tx for tx in recent_tx if tx.result == "NG"]

        # Ready for check-in: Serials in RUNNING WOs that are routed to this station
        running_wo_ids = [wo.id for wo in running_wos]
        if running_wo_ids:
            serials = SerialNumber.query.filter(SerialNumber.work_order_id.in_(running_wo_ids)).all()

            ready_list = []
            for s in serials:
                wo = WorkOrder.query.get(s.work_order_id)
                if not wo:
                    continue

                station_step = RoutingStep.query.filter_by(part_number=wo.part_number, station_name=selected_station.name).first()
                if station_step:
                    # Check if already processed OK at this station
                    has_ok = OperationTransaction.query.filter_by(
                        serial_number=s.serial_number,
                        station_id=selected_station.id,
                        result="OK"
                    ).first()

                    if not has_ok:
                        all_steps = RoutingStep.query.filter_by(part_number=wo.part_number).order_by(RoutingStep.operation_sequence).all()
                        current_step_idx = next((i for i, step in enumerate(all_steps) if step.operation_sequence == station_step.operation_sequence), 0)

                        if current_step_idx == 0:
                            ready_list.append(s)
                        else:
                            prev_step = all_steps[current_step_idx - 1]
                            prev_tx = OperationTransaction.query.filter_by(
                                serial_number=s.serial_number,
                                routing_step=prev_step.operation_sequence,
                                result="OK"
                            ).first()
                            if prev_tx:
                                ready_list.append(s)

            ready_for_checkin = ready_list[:20]  # Limit to 20 for UI performance

    return render_template(
        "stations/summary.html",
        stations=stations,
        selected_station=selected_station,
        running_wos=running_wos,
        ready_for_checkin=ready_for_checkin,
        checked_out_pass=checked_out_pass,
        checked_out_fail=checked_out_fail
    )
