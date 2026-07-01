from flask import Blueprint, render_template, request, redirect, url_for, flash
from .. import db
from ..models import BOMItem

bp = Blueprint("bom", __name__)


@bp.route("/bom", methods=["GET"])
def list_bom():
    parent_filter = request.args.get("parent", "All")

    query = BOMItem.query
    if parent_filter and parent_filter != "All":
        query = query.filter_by(part_number=parent_filter)

    items = query.order_by(BOMItem.part_number.asc()).all()
    parent_parts = (
        db.session.query(BOMItem.part_number)
        .distinct()
        .order_by(BOMItem.part_number.asc())
        .all()
    )
    parent_parts = [p[0] for p in parent_parts]

    return render_template(
        "bom/management.html",
        items=items,
        parent_parts=parent_parts,
        parent_filter=parent_filter,
    )


@bp.route("/bom/new", methods=["GET", "POST"])
def create_bom_item():
    if request.method == "POST":
        parent_part_number = request.form.get("parent_part_number")
        component_part_number = request.form.get("component_part_number")
        quantity_per_unit = float(request.form.get("quantity_per_unit") or 0)
        designator = request.form.get("designator") or None
        revision = request.form.get("revision") or "A"

        if not parent_part_number or not component_part_number or quantity_per_unit <= 0:
            flash("Parent part, component, and positive quantity are required.", "error")
            return redirect(url_for("bom.create_bom_item"))

        item = BOMItem(
            part_number=parent_part_number,
            component_part_number=component_part_number,
            quantity_per_unit=quantity_per_unit,
            designator=designator,
            revision=revision,
        )
        db.session.add(item)
        db.session.commit()
        flash("BOM item created.", "success")
        return redirect(url_for("bom.list_bom"))

    return render_template("bom/form.html")
