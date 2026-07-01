from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime
from .. import db
from ..models import (
    InventoryItem,
    InventoryLocation,
    Kit,
    FeederReel,
    SolderPasteLot,
    WorkOrder,
)

bp = Blueprint("inventory", __name__)


@bp.route("/inventory", methods=["GET"])
def inventory_list():
    part = request.args.get("part")
    location = request.args.get("location")
    nearing_expiry_only = request.args.get("nearing_expiry") == "1"

    query = InventoryItem.query.join(InventoryLocation, isouter=True)

    if part:
        query = query.filter(InventoryItem.part_number.ilike(f"%{part}%"))
    if location:
        query = query.filter(InventoryLocation.code == location)

    today = datetime.utcnow().date()
    if nearing_expiry_only:
        query = query.filter(
            InventoryItem.expiry_date.isnot(None),
            InventoryItem.expiry_date <= today,
        )

    items = query.order_by(InventoryItem.part_number.asc()).all()
    locations = InventoryLocation.query.order_by(InventoryLocation.code.asc()).all()

    return render_template(
        "inventory/list.html",
        items=items,
        locations=locations,
        part_filter=part or "",
        location_filter=location or "",
        nearing_expiry_only=nearing_expiry_only,
        today=today,
    )


@bp.route("/inventory/new", methods=["GET", "POST"])
def inventory_form():
    locations = InventoryLocation.query.order_by(InventoryLocation.code.asc()).all()

    if request.method == "POST":
        part_number = request.form.get("part_number")
        description = request.form.get("description")
        quantity_on_hand = float(request.form.get("quantity_on_hand") or 0)
        location_id = request.form.get("location_id") or None
        lot_number = request.form.get("lot_number") or None

        if not part_number:
            flash("Part number is required", "error")
            return redirect(url_for("inventory.inventory_form"))

        item = InventoryItem(
            id=str(datetime.utcnow().timestamp()),
            part_number=part_number,
            description=description,
            quantity_on_hand=quantity_on_hand,
            location_id=location_id,
            lot_number=lot_number,
        )
        db.session.add(item)
        db.session.commit()
        flash("Inventory item created", "success")
        return redirect(url_for("inventory.inventory_list"))

    return render_template("inventory/form.html", locations=locations)


@bp.route("/kits", methods=["GET"])
def kits():
    status = request.args.get("status", "all")
    query = Kit.query.join(WorkOrder)

    if status != "all":
        query = query.filter(Kit.status == status)

    kits = query.order_by(Kit.created_at.desc()).all()

    return render_template(
        "inventory/kits.html",
        kits=kits,
        status_filter=status,
    )


@bp.route("/feeders", methods=["GET"])
def feeders():
    part = request.args.get("part")
    line = request.args.get("line")

    query = FeederReel.query
    if part:
        query = query.filter(FeederReel.part_number.ilike(f"%{part}%"))
    # line filter could join to machines/smt_lines in future

    reels = query.order_by(FeederReel.created_at.desc()).all()
    return render_template(
        "inventory/feeders.html",
        reels=reels,
        part_filter=part or "",
        line_filter=line or "",
    )


@bp.route("/msd", methods=["GET"])
def msd_management():
    items = (
        InventoryItem.query.filter(InventoryItem.msd_level.isnot(None))
        .order_by(InventoryItem.msd_level.asc())
        .all()
    )
    return render_template("inventory/msd.html", items=items)


@bp.route("/solder-paste", methods=["GET"])
def solder_paste():
    status = request.args.get("status", "all")
    query = SolderPasteLot.query
    if status != "all":
        query = query.filter(SolderPasteLot.status == status)

    lots = query.order_by(SolderPasteLot.expiry_date.asc()).all()
    return render_template(
        "inventory/solder_paste.html",
        lots=lots,
        status_filter=status,
    )
