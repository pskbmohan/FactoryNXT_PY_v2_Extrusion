"""Master Data API routes for Customer, Part Number, and BOM management.

This blueprint provides RESTful endpoints for:
- Customers master data CRUD operations
- Part Numbers master data CRUD operations
- Customer-to-Part mappings (enforcing approved part list per customer)
- Part Number BOMs with version control and die/billet resolution
"""

import uuid
from datetime import datetime

from flask import Blueprint, jsonify, request, g
from .. import db
from ..models import (
    Customer,
    PartNumber,
    CustomerPartNumber,
    PartNumberBOM,
    Die,
    Billet,
)

bp = Blueprint("master_data_bom", __name__, url_prefix="/api/master")


# ──────────────────────── Customers Endpoints ────────────────────────────────

@bp.route("/customers", methods=["GET"])
def customers_list():
    """List all active customers with their part number mapping counts."""
    customers = Customer.query.filter_by(is_active=True).order_by(Customer.customer_name).all()
    return jsonify([{
        "id": c.id,
        "customer_code": c.customer_code,
        "customer_name": c.customer_name,
        "contact_email": c.contact_email,
        "contact_phone": c.contact_phone,
        "address": c.address,
        "part_count": len(c.customer_part_numbers),
    } for c in customers])


@bp.route("/customers", methods=["POST"])
def create_customer():
    """Create a new customer record."""
    data = request.get_json()

    # Validate required fields
    if not data.get("customer_code") or not data.get("customer_name"):
        return jsonify({"error": "customer_code and customer_name are required"}), 400

    try:
        customer = Customer(
            id=str(uuid.uuid4()),
            customer_code=data["customer_code"],
            customer_name=data["customer_name"],
            contact_email=data.get("contact_email"),
            contact_phone=data.get("contact_phone"),
            address=data.get("address"),
            is_active=True,
        )
        db.session.add(customer)
        db.session.commit()

        return jsonify({
            "id": customer.id,
            "customer_code": customer.customer_code,
            "customer_name": customer.customer_name,
            "message": "Customer created successfully"
        }), 201

    except Exception as e:
        db.session.rollback()
        if "uq_customers_customer_code" in str(e):
            return jsonify({"error": f"Customer code {data['customer_code']} already exists"}), 409
        return jsonify({"error": str(e)}), 500


@bp.route("/customers/<customer_id>", methods=["GET"])
def get_customer(customer_id):
    """Get a single customer with their part number mappings."""
    customer = Customer.query.get_or_404(customer_id)

    # Include active part number mappings
    mappings = [cpn for cpn in customer.customer_part_numbers if cpn.is_active]
    return jsonify({
        "id": customer.id,
        "customer_code": customer.customer_code,
        "customer_name": customer.customer_name,
        "contact_email": customer.contact_email,
        "contact_phone": customer.contact_phone,
        "address": customer.address,
        "is_active": customer.is_active,
        "part_mappings": [{
            "id": m.id,
            "part_number_id": m.part_number_id,
            "customer_part_ref": m.customer_part_ref,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        } for m in mappings],
    })


# ──────────────────────── Part Numbers Endpoints ─────────────────────────────

@bp.route("/part-numbers", methods=["GET"])
def part_numbers_list():
    """List all active part numbers with optional customer filter."""
    customer_id = request.args.get("customer_id")
    include_inactive = request.args.get("include_inactive", "false").lower() == "true"

    q = PartNumber.query
    if not include_inactive:
        q = q.filter_by(is_active=True)
    if customer_id:
        # Filter to only parts mapped to this customer
        q = q.join(PartNumber.customer_part_numbers).filter(
            CustomerPartNumber.customer_id == customer_id,
            CustomerPartNumber.is_active == True
        )

    part_numbers = q.order_by(PartNumber.part_code).all()

    return jsonify([{
        "id": p.id,
        "part_code": p.part_code,
        "description": p.description,
        "profile_code": p.profile_code,
        "alloy": p.alloy,
        "unit_weight_kg": p.unit_weight_kg,
        "uom": p.uom or "KG",
        "is_active": p.is_active,
    } for p in part_numbers])


@bp.route("/part-numbers/<part_number_id>", methods=["GET"])
def get_part_number(part_number_id):
    """Get a single part number with active BOM info."""
    part = PartNumber.query.get_or_404(part_number_id)

    # Get active BOM if exists
    active_bom = PartNumberBOM.query.filter_by(
        part_number_id=part.id, is_active=True
    ).first()

    return jsonify({
        "id": part.id,
        "part_code": part.part_code,
        "description": part.description,
        "profile_code": part.profile_code,
        "alloy": part.alloy,
        "unit_weight_kg": part.unit_weight_kg,
        "uom": part.uom or "KG",
        "is_active": part.is_active,
        "bom_status": "BOM Ready" if active_bom else "No BOM",
    })


@bp.route("/part-numbers", methods=["POST"])
def create_part_number():
    """Create a new part number."""
    data = request.get_json()

    # Validate required fields
    if not all([data.get("part_code"), data.get("description")]):
        return jsonify({"error": "part_code and description are required"}), 400

    try:
        part = PartNumber(
            id=str(uuid.uuid4()),
            part_code=data["part_code"],
            description=data["description"],
            profile_code=data.get("profile_code"),
            alloy=data.get("alloy"),
            unit_weight_kg=float(data.get("unit_weight_kg", 0)),
            uom=data.get("uom", "KG"),
            is_active=True,
        )
        db.session.add(part)
        db.session.commit()

        return jsonify({
            "id": part.id,
            "part_code": part.part_code,
            "description": part.description,
            "message": "Part number created successfully"
        }), 201

    except Exception as e:
        db.session.rollback()
        if "uq_part_numbers_part_code" in str(e):
            return jsonify({"error": f"Part code {data['part_code']} already exists"}), 409
        return jsonify({"error": str(e)}), 500


# ──────────────────────── Customer-Part Mapping Endpoints ───────────────────

@bp.route("/customer-part-numbers", methods=["GET"])
def customer_part_mappings():
    """List all active customer-to-part mappings."""
    customer_id = request.args.get("customer_id")

    q = db.session.query(CustomerPartNumber).join(
        Customer, CustomerPartNumber.customer_id == Customer.id
    ).join(PartNumber, CustomerPartNumber.part_number_id == PartNumber.id)

    if customer_id:
        q = q.filter(CustomerPartNumber.customer_id == customer_id)

    mappings = q.all()

    return jsonify([{
        "id": m.id,
        "customer_id": m.customer_id,
        "customer_code": m.customer.customer_code,
        "customer_name": m.customer.customer_name,
        "part_number_id": m.part_number_id,
        "part_code": m.part_number.part_code,
        "customer_part_ref": m.customer_part_ref,
        "is_active": m.is_active,
    } for m in mappings])


@bp.route("/customer-part-numbers", methods=["POST"])
def create_customer_part_mapping():
    """Create a mapping between customer and part number."""
    data = request.get_json()

    if not all([data.get("customer_id"), data.get("part_number_id")]):
        return jsonify({"error": "customer_id and part_number_id are required"}), 400

    try:
        # Validate both entities exist
        customer = Customer.query.get_or_404(data["customer_id"])
        part = PartNumber.query.get_or_404(data["part_number_id"])

        # Check for existing mapping (prevent duplicates)
        existing = CustomerPartNumber.query.filter_by(
            customer_id=data["customer_id"],
            part_number_id=data["part_number_id"]
        ).first()
        if existing:
            return jsonify({
                "error": f"Mapping already exists between {customer.customer_name} and {part.part_code}"
            }), 409

        mapping = CustomerPartNumber(
            id=str(uuid.uuid4()),
            customer_id=data["customer_id"],
            part_number_id=data["part_number_id"],
            customer_part_ref=f"{customer.customer_code}-{part.part_code}",
            is_active=True,
        )
        db.session.add(mapping)
        db.session.commit()

        return jsonify({
            "id": mapping.id,
            "customer_id": mapping.customer_id,
            "part_number_id": mapping.part_number_id,
            "message": f"Mapping created: {customer.customer_name} <-> {part.part_code}"
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route("/customer-part-numbers/<mapping_id>", methods=["DELETE"])
def delete_customer_part_mapping(mapping_id):
    """Soft-delete a customer-to-part mapping."""
    try:
        mapping = CustomerPartNumber.query.get_or_404(mapping_id)

        # Check if this mapping is used in any order lines (prevent deletion)
        from ..models import CustomerOrderLine
        has_orders = db.session.query(CustomerOrderLine).join(
            CustomerOrder, CustomerOrderLine.order_id == CustomerOrder.id
        ).filter(
            CustomerOrder.customer_id == mapping.customer_id,
            CustomerOrderLine.part_number_id == mapping.part_number_id,
            CustomerOrder.status.in_(['PENDING', 'IN_PROGRESS'])
        ).count() > 0

        if has_orders:
            return jsonify({
                "error": f"Cannot delete mapping - {mapping.part_number.part_code} is used in active orders for {mapping.customer.customer_name}"
            }), 400

        # Soft-delete by setting is_active=False
        mapping.is_active = False
        db.session.commit()

        return jsonify({
            "message": f"Mapping removed: {mapping.customer.customer_name} <-> {mapping.part_number.part_code}"
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ──────────────────────── BOM Endpoints ────────────────────────────────────

@bp.route("/boms", methods=["GET"])
def boms_list():
    """List all part number BOMs with optional filter."""
    part_number_id = request.args.get("part_number_id")

    q = PartNumberBOM.query.join(PartNumber, PartNumberBOM.part_number_id == PartNumber.id)
    if part_number_id:
        q = q.filter(PartNumberBOM.part_number_id == part_number_id)

    boms = q.order_by(PartNumberBOM.version.desc()).all()

    return jsonify([{
        "id": b.id,
        "part_number_id": b.part_number_id,
        "die_type_id": b.die_type_id,
        "billet_type_id": b.billet_type_id,
        "version": b.version,
        "billet_weight_kg": b.billet_weight_kg,
        "extrusion_ratio": b.extrusion_ratio,
        "notes": b.notes,
        "is_active": b.is_active,
    } for b in boms])


@bp.route("/boms", methods=["POST"])
def create_bom():
    """Create a new BOM version (auto-deactivates existing active BOM)."""
    data = request.get_json()

    if not all([data.get("part_number_id"), data.get("die_type_id"), data.get("billet_type_id")]):
        return jsonify({"error": "part_number_id, die_type_id, and billet_type_id are required"}), 400

    try:
        # Validate entities exist
        part = PartNumber.query.get_or_404(data["part_number_id"])
        die = Die.query.get_or_404(data["die_type_id"])
        billet = Billet.query.get_or_404(data["billet_type_id"])

        # Check if die is rejected (prevent using rejected dies)
        if hasattr(die, 'status') and die.status == "Rejected":
            return jsonify({"error": f"Cannot use rejected die: {die.die_code}"}), 400

        # Get current active BOM version to increment
        max_version = db.session.query(db.func.max(PartNumberBOM.version)).filter_by(
            part_number_id=data["part_number_id"]
        ).scalar() or 0

        # Deactivate any existing active BOMs for this part
        db.session.query(PartNumberBOM).filter_by(
            part_number_id=data["part_number_id"], is_active=True
        ).update({"is_active": False})

        bom = PartNumberBOM(
            id=str(uuid.uuid4()),
            part_number_id=data["part_number_id"],
            die_type_id=data["die_type_id"],
            billet_type_id=data["billet_type_id"],
            version=max_version + 1,
            billet_weight_kg=float(data.get("billet_weight_kg", billet.quantity_kg or 0)),
            extrusion_ratio=float(data.get("extrusion_ratio")),
            notes=data.get("notes"),
            is_active=True,
        )
        db.session.add(bom)
        db.session.commit()

        return jsonify({
            "id": bom.id,
            "part_number_id": bom.part_number_id,
            "version": bom.version,
            "message": f"BOM version {bom.version} created for {part.part_code}"
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route("/boms/<bom_id>", methods=["PUT"])
def update_bom(bom_id):
    """Update BOM by creating new version (same as create - versions are immutable)."""
    data = request.get_json()

    if not all([data.get("die_type_id"), data.get("billet_type_id")]):
        return jsonify({"error": "die_type_id and billet_type_id are required"}), 400

    # Use same logic as create_bom - just creates new version
    return create_bom()


@bp.route("/boms/<bom_id>/activate", methods=["POST"])
def activate_bom(bom_id):
    """Activate a specific BOM version, deactivating others for same part."""
    try:
        bom = PartNumberBOM.query.get_or_404(bom_id)

        # Deactivate all other active BOMs for this part
        db.session.query(PartNumberBOM).filter_by(
            part_number_id=bom.part_number_id, is_active=True
        ).update({"is_active": False})

        # Activate selected BOM
        bom.is_active = True
        db.session.commit()

        return jsonify({
            "message": f"BOM version {bom.version} activated for {bom.part_number.part_code}"
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ──────────────────────── Page Rendering Routes (for S3 UI) ─────────────────

@bp.route("/customers")
def customers_page():
    """Render Customers master data page."""
    from flask import render_template
    return render_template("master_data_bom/customers.html")


@bp.route("/part-numbers")
def part_numbers_page():
    """Render Part Numbers master data page."""
    from flask import render_template
    return render_template("master_data_bom/part_numbers.html")


@bp.route("/boms")
def boms_page():
    """Render BOM management page."""
    from flask import render_template
    return render_template("master_data_bom/boms.html")


@bp.route("/customer-part-map")
def customer_part_map_page():
    """Render Customer-Part Mapping page."""
    from flask import render_template
    return render_template("master_data_bom/customer_part_map.html")


# ──────────────────────── Die & Billet List APIs (for BOM dropdowns) ─────────

@bp.route("/dies", methods=["GET"])
def dies_list():
    """List all dies for use in BOM creation dropdown.

    Returns simplified die data: id, die_code, die_type
    """
    dies = Die.query.filter_by(is_active=True).order_by(Die.die_code).all()
    return jsonify([{
        "id": d.id,
        "die_id": d.id,  # For backward compatibility with some templates
        "DIE_ID": d.id,  # For legacy template support
        "die_code": d.die_code,
        "die_type": d.die_type or (d.profile_code if hasattr(d, 'profile_code') else None),
    } for d in dies])


@bp.route("/billets", methods=["GET"])
def billets_list():
    """List all available billets for use in BOM creation dropdown.

    Returns simplified billet data: id, billet_code, alloy, diameter_mm
    """
    billets = Billet.query.filter_by(is_active=True).order_by(Billet.billet_code).all()
    return jsonify([{
        "id": b.id,
        "billet_id": b.id,  # For backward compatibility
        "BILLET_ID": b.id,  # For legacy template support
        "billet_code": b.billet_code,
        "alloy": b.alloy,
        "diameter_mm": b.diameter_mm,
    } for b in billets])
