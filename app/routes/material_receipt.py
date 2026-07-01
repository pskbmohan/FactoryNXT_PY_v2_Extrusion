from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
from .. import db
from ..models import (
    MaterialReceipt, RawMaterialType, AlloyComposition,
    InventoryLocation,
)
import uuid

bp = Blueprint("material_receipt", __name__)


def check_composition(receipt):
    """Check actual_composition against alloy composition tolerances."""
    if not receipt.alloy or not receipt.alloy_code or not receipt.actual_composition:
        return "PENDING"
    spec = receipt.alloy.composition or {}
    for element, limits in spec.items():
        actual = receipt.actual_composition.get(element)
        if actual is None:
            continue
        mn = limits.get("min", 0)
        mx = limits.get("max", 100)
        if actual < mn or actual > mx:
            return "FAIL"
    return "PASS"


@bp.route("/material-receipt")
def list_receipts():
    receipts = MaterialReceipt.query.order_by(MaterialReceipt.received_at.desc()).all()
    return render_template("material_receipt/list.html", receipts=receipts)


@bp.route("/material-receipt/new", methods=["GET", "POST"])
def create_receipt():
    if request.method == "POST":
        receipt_number = request.form.get("receipt_number")
        lot_number = request.form.get("lot_number")
        quantity = float(request.form.get("quantity_received") or 0)
        if not receipt_number or not lot_number or quantity <= 0:
            flash("Receipt number, lot number, and positive quantity required.", "error")
            return redirect(url_for("material_receipt.create_receipt"))

        receipt = MaterialReceipt(
            id=str(uuid.uuid4()),
            receipt_number=receipt_number,
            supplier_name=request.form.get("supplier_name"),
            truck_reference=request.form.get("truck_reference"),
            material_type_id=request.form.get("material_type_id") or None,
            alloy_code=request.form.get("alloy_code") or None,
            lot_number=lot_number,
            quantity_received=quantity,
            quantity_available=quantity,
            uom=request.form.get("uom") or "KG",
            actual_composition=_parse_composition(request.form.get("actual_composition_json")),
            received_by=request.form.get("received_by") or "Operator",
            location_id=request.form.get("location_id") or None,
            notes=request.form.get("notes"),
        )
        receipt.composition_status = check_composition(receipt)
        db.session.add(receipt)
        db.session.commit()
        flash(f"Receipt {receipt.receipt_number} created. Composition: {receipt.composition_status}.", "success")
        return redirect(url_for("material_receipt.detail", id=receipt.id))

    material_types = RawMaterialType.query.order_by(RawMaterialType.code).all()
    alloys = AlloyComposition.query.order_by(AlloyComposition.alloy_code).all()
    locations = InventoryLocation.query.filter_by(is_active=True).order_by(InventoryLocation.name).all()
    return render_template(
        "material_receipt/form.html",
        material_types=material_types,
        alloys=alloys,
        locations=locations,
    )


def _parse_composition(json_str):
    if not json_str:
        return {}
    try:
        import json
        return json.loads(json_str)
    except Exception:
        return {}


@bp.route("/material-receipt/<id>")
def detail(id):
    receipt = MaterialReceipt.query.get_or_404(id)
    spec_elements = []
    if receipt.alloy and receipt.alloy.composition:
        for element, limits in receipt.alloy.composition.items():
            actual = receipt.actual_composition.get(element)
            in_spec = (
                limits.get("min", 0) <= actual <= limits.get("max", 100)
                if actual is not None else None
            )
            spec_elements.append({
                "element": element,
                "min": limits.get("min"),
                "max": limits.get("max"),
                "actual": actual,
                "in_spec": in_spec,
            })
    return render_template("material_receipt/detail.html", receipt=receipt, spec_elements=spec_elements)


@bp.route("/material-receipt/<id>/verify-composition", methods=["POST"])
def verify_composition(id):
    receipt = MaterialReceipt.query.get_or_404(id)
    receipt.composition_status = check_composition(receipt)
    db.session.commit()
    flash(f"Composition verified: {receipt.composition_status}.", "success")
    return redirect(url_for("material_receipt.detail", id=receipt.id))


@bp.route("/material-receipt/alloy-stock")
def alloy_stock():
    from sqlalchemy import func
    stock = (
        db.session.query(
            MaterialReceipt.alloy_code,
            func.sum(MaterialReceipt.quantity_available),
        )
        .filter(MaterialReceipt.alloy_code.isnot(None), MaterialReceipt.quantity_available > 0)
        .group_by(MaterialReceipt.alloy_code)
        .all()
    )
    alloys = {a.alloy_code: a.alloy_name for a in AlloyComposition.query.all()}
    data = [{"alloy_code": c, "alloy_name": alloys.get(c, c), "qty": q or 0} for c, q in stock]
    return render_template("material_receipt/alloy_stock.html", stock=data)


@bp.route("/api/material-receipt/alloy-stock")
def alloy_stock_json():
    from sqlalchemy import func
    stock = (
        db.session.query(
            MaterialReceipt.alloy_code,
            func.sum(MaterialReceipt.quantity_available),
        )
        .filter(MaterialReceipt.alloy_code.isnot(None), MaterialReceipt.quantity_available > 0)
        .group_by(MaterialReceipt.alloy_code)
        .all()
    )
    alloys = {a.alloy_code: a.alloy_name for a in AlloyComposition.query.all()}
    return jsonify([{"alloy_code": c, "alloy_name": alloys.get(c, c), "qty": q or 0} for c, q in stock])
