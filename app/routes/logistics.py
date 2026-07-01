from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime, date
from .. import db
from ..models import (
    Shipment, ShipmentLine, PackagingOrder, PackagingSpec, WorkOrder,
)
import uuid

bp = Blueprint("logistics", __name__)


@bp.route("/logistics")
def index():
    shipments = Shipment.query.order_by(Shipment.created_at.desc()).all()
    packaging_count = PackagingOrder.query.filter(PackagingOrder.status.in_(["pending", "packed"])).count()
    return render_template("logistics/index.html", shipments=shipments, packaging_count=packaging_count)


# ── Packaging ─────────────────────────────────────────────────────────
@bp.route("/logistics/packaging")
def packaging_queue():
    packages = PackagingOrder.query.order_by(PackagingOrder.created_at.desc()).all()
    return render_template("logistics/packaging.html", packages=packages)


@bp.route("/logistics/packaging/new", methods=["GET", "POST"])
def create_package():
    if request.method == "POST":
        wo_id = request.form.get("wo_id")
        pack_number = request.form.get("pack_number")
        if not wo_id or not pack_number:
            flash("Work Order and Pack Number required.", "error")
            return redirect(url_for("logistics.create_package"))

        spec_id = request.form.get("packaging_spec_id") or None
        spec = PackagingSpec.query.get(spec_id) if spec_id else None
        theoretical = spec.theoretical_weight_per_pack_kg if spec else None
        units_per_pack = spec.units_per_pack if spec else None

        package = PackagingOrder(
            id=str(uuid.uuid4()),
            wo_id=wo_id,
            packaging_spec_id=spec_id,
            pack_number=pack_number,
            barcode=f"PK-{pack_number}-{str(uuid.uuid4())[:8].upper()}",
            quantity_packed=int(request.form.get("quantity_packed") or units_per_pack or 0) or None,
            theoretical_weight_kg=theoretical,
            status="pending",
            packed_by=request.form.get("packed_by"),
        )
        db.session.add(package)
        db.session.commit()
        flash(f"Package {package.pack_number} created.", "success")
        return redirect(url_for("logistics.packaging_queue"))

    work_orders = WorkOrder.query.filter(WorkOrder.status.in_(["RUNNING", "COMPLETED"])).order_by(WorkOrder.order_number).all()
    specs = PackagingSpec.query.order_by(PackagingSpec.part_number).all()
    return render_template("logistics/package_form.html", work_orders=work_orders, specs=specs)


@bp.route("/logistics/packaging/<id>/weigh", methods=["POST"])
def weigh_package(id):
    package = PackagingOrder.query.get_or_404(id)
    actual = float(request.form.get("actual_weight_kg") or 0)
    package.actual_weight_kg = actual
    package.packed_at = datetime.utcnow()
    package.status = "packed"

    if package.theoretical_weight_kg and package.theoretical_weight_kg > 0:
        variance = 100 * (actual - package.theoretical_weight_kg) / package.theoretical_weight_kg
        package.weight_variance_percent = round(variance, 2)
    db.session.commit()
    flash(f"Package weighed: {actual} kg (variance {package.weight_variance_percent or 0}%).", "success")
    return redirect(url_for("logistics.packaging_queue"))


@bp.route("/logistics/packaging/<id>/print-label", methods=["POST"])
def print_label(id):
    package = PackagingOrder.query.get_or_404(id)
    package.label_printed = True
    if package.status == "pending":
        package.status = "labelled"
    db.session.commit()
    flash(f"Label for {package.pack_number} marked as printed.", "success")
    return redirect(url_for("logistics.packaging_queue"))


# ── Shipments ─────────────────────────────────────────────────────────
@bp.route("/logistics/shipments")
def shipments_list():
    shipments = Shipment.query.order_by(Shipment.created_at.desc()).all()
    return render_template("logistics/shipments.html", shipments=shipments)


@bp.route("/logistics/shipments/new", methods=["GET", "POST"])
def create_shipment():
    if request.method == "POST":
        shipment_number = request.form.get("shipment_number")
        if not shipment_number:
            flash("Shipment Number required.", "error")
            return redirect(url_for("logistics.create_shipment"))

        shipment = Shipment(
            id=str(uuid.uuid4()),
            shipment_number=shipment_number,
            customer_name=request.form.get("customer_name"),
            delivery_address=request.form.get("delivery_address"),
            carrier=request.form.get("carrier"),
            truck_reference=request.form.get("truck_reference"),
            scheduled_ship_date=_parse_date(request.form.get("scheduled_ship_date")),
            status="open",
        )
        db.session.add(shipment)
        db.session.commit()
        flash(f"Shipment {shipment.shipment_number} created.", "success")
        return redirect(url_for("logistics.shipment_detail", id=shipment.id))

    return render_template("logistics/shipment_form.html", shipment=None)


@bp.route("/logistics/shipments/<id>")
def shipment_detail(id):
    shipment = Shipment.query.get_or_404(id)
    lines = shipment.lines.order_by(ShipmentLine.scanned_at.desc()).all()
    packages = PackagingOrder.query.filter(PackagingOrder.status.in_(["labelled", "staged", "packed"])).order_by(PackagingOrder.pack_number).all()
    return render_template("logistics/shipment_detail.html", shipment=shipment, lines=lines, packages=packages)


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


@bp.route("/logistics/shipments/<id>/scan-package", methods=["POST"])
def scan_package(id):
    shipment = Shipment.query.get_or_404(id)
    barcode = request.form.get("barcode")
    if not barcode:
        flash("Barcode is required to scan.", "error")
        return redirect(url_for("logistics.shipment_detail", id=id))

    package = PackagingOrder.query.filter_by(barcode=barcode).first()
    if not package:
        package = PackagingOrder.query.filter_by(pack_number=barcode).first()
    if not package:
        flash(f"Package '{barcode}' not found.", "error")
        return redirect(url_for("logistics.shipment_detail", id=id))

    existing = ShipmentLine.query.filter_by(
        shipment_id=id, packaging_order_id=package.id
    ).first()
    if existing:
        flash(f"{package.pack_number} already in this shipment.", "error")
        return redirect(url_for("logistics.shipment_detail", id=id))

    line = ShipmentLine(
        id=str(uuid.uuid4()),
        shipment_id=id,
        packaging_order_id=package.id,
        wo_id=package.wo_id,
        quantity=package.quantity_packed,
        scanned_at=datetime.utcnow(),
        scanned_by=request.form.get("scanned_by") or "Loader",
    )
    package.status = "staged"
    db.session.add(line)
    db.session.commit()
    flash(f"Scanned {package.pack_number} into shipment.", "success")
    return redirect(url_for("logistics.shipment_detail", id=id))


@bp.route("/logistics/shipments/<id>/weight-check", methods=["POST"])
def weight_check(id):
    shipment = Shipment.query.get_or_404(id)
    theoretical = 0.0
    for line in shipment.lines.all():
        pkg = line.packaging_order
        if pkg and pkg.theoretical_weight_kg:
            theoretical += pkg.theoretical_weight_kg
    shipment.theoretical_total_weight_kg = theoretical

    actual = float(request.form.get("actual_total_weight_kg") or 0) or None
    shipment.actual_total_weight_kg = actual
    if actual and theoretical and theoretical > 0:
        variance = 100 * (actual - theoretical) / theoretical
        shipment.weight_check_variance_percent = round(variance, 2)
        if abs(variance) <= 2:
            shipment.weight_check_status = "OK"
        elif abs(variance) <= 5:
            shipment.weight_check_status = "VARIANCE"
        else:
            shipment.weight_check_status = "HOLD"
    shipment.status = "weight_check"
    db.session.commit()
    flash(f"Weight check: {shipment.weight_check_status or 'PENDING'} (variance {shipment.weight_check_variance_percent or 0}%).",
          "success" if shipment.weight_check_status == "OK" else "error")
    return redirect(url_for("logistics.shipment_detail", id=id))


@bp.route("/logistics/shipments/<id>/approve", methods=["POST"])
def approve_shipment(id):
    shipment = Shipment.query.get_or_404(id)
    shipment.status = "approved"
    db.session.commit()
    flash("Shipment approved.", "success")
    return redirect(url_for("logistics.shipment_detail", id=id))


@bp.route("/logistics/shipments/<id>/ship", methods=["POST"])
def ship(id):
    shipment = Shipment.query.get_or_404(id)
    shipment.status = "shipped"
    shipment.actual_ship_date = date.today()
    for line in shipment.lines.all():
        pkg = line.packaging_order
        if pkg:
            pkg.status = "shipped"
    db.session.commit()
    flash(f"Shipment {shipment.shipment_number} marked as shipped.", "success")
    return redirect(url_for("logistics.shipment_detail", id=id))


@bp.route("/api/logistics/shipments/<id>/weight-breakdown")
def weight_breakdown(id):
    shipment = Shipment.query.get_or_404(id)
    breakdown = []
    total_theoretical = 0.0
    for line in shipment.lines.order_by(ShipmentLine.scanned_at).all():
        pkg = line.packaging_order
        theo = pkg.theoretical_weight_kg if pkg and pkg.theoretical_weight_kg else 0
        breakdown.append({
            "pack_number": pkg.pack_number if pkg else "?",
            "wo": pkg.work_order.order_number if pkg and pkg.work_order else None,
            "theoretical": theo,
            "actual": pkg.actual_weight_kg if pkg else None,
        })
        total_theoretical += theo
    return jsonify({
        "shipment_number": shipment.shipment_number,
        "lines": breakdown,
        "total_theoretical": round(total_theoretical, 2),
        "actual_total": shipment.actual_total_weight_kg,
        "variance_percent": shipment.weight_check_variance_percent,
    })
