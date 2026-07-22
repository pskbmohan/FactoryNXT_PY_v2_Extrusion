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
    CoatingColor,
    RawMaterialType,
    AlloyComposition,
    FinishingProcessType,
    PackagingSpec,
    DefectCode,
    QualityParameter,
)

bp = Blueprint("master_data_bom", __name__, url_prefix="/api/master")


# ──────────────────────── Customers Endpoints ────────────────────────────────

@bp.route("/customers", methods=["GET"], endpoint="customers_list")
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


# ──────────────────────── Coating Colors Endpoints ───────────────────────────

@bp.route("/coating-colors", methods=["GET"], endpoint="coating_colors_list")
def coating_colors_list():
    """List all coating colors."""
    colors = CoatingColor.query.order_by(CoatingColor.color_name).all()
    return jsonify([{
        "id": c.id,
        "color_code": c.color_code,
        "color_name": c.color_name,
        "hex_value": c.hex_value,
        "clean_time_minutes": c.clean_time_minutes,
        "ral_code": c.ral_code,
    } for c in colors])


@bp.route("/coating-colors", methods=["POST"])
def create_coating_color():
    """Create a new coating color record."""
    data = request.get_json()

    if not data.get("color_code") or not data.get("color_name"):
        return jsonify({"error": "color_code and color_name are required"}), 400

    try:
        color = CoatingColor(
            id=str(uuid.uuid4()),
            color_code=data["color_code"],
            color_name=data["color_name"],
            hex_value=data.get("hex_value"),
            clean_time_minutes=int(data.get("clean_time_minutes", 30)),
            ral_code=data.get("ral_code"),
        )
        db.session.add(color)
        db.session.commit()

        return jsonify({
            "id": color.id,
            "color_code": color.color_code,
            "color_name": color.color_name,
            "message": "Coating color created successfully"
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route("/coating-colors/<color_id>", methods=["GET"])
def get_coating_color(color_id):
    """Get a single coating color by id."""
    color = CoatingColor.query.get_or_404(color_id)
    return jsonify({
        "id": color.id,
        "color_code": color.color_code,
        "color_name": color.color_name,
        "hex_value": color.hex_value,
        "clean_time_minutes": color.clean_time_minutes,
        "ral_code": color.ral_code,
    })


@bp.route("/coating-colors/<color_id>", methods=["PUT"])
def update_coating_color(color_id):
    """Update an existing coating color."""
    color = CoatingColor.query.get_or_404(color_id)
    data = request.get_json()

    try:
        if "color_code" in data:
            color.color_code = data["color_code"]
        if "color_name" in data:
            color.color_name = data["color_name"]
        if "hex_value" in data:
            color.hex_value = data["hex_value"]
        if "clean_time_minutes" in data:
            color.clean_time_minutes = int(data["clean_time_minutes"])
        if "ral_code" in data:
            color.ral_code = data["ral_code"]

        db.session.commit()

        return jsonify({
            "id": color.id,
            "color_code": color.color_code,
            "color_name": color.color_name,
            "message": "Coating color updated successfully"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route("/coating-colors/<color_id>", methods=["DELETE"])
def delete_coating_color(color_id):
    """Hard-delete a coating color (no is_active column)."""
    try:
        color = CoatingColor.query.get_or_404(color_id)
        db.session.delete(color)
        db.session.commit()
        return jsonify({"message": "Coating color deleted successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ──────────────────────── Raw Material Types Endpoints ───────────────────────

@bp.route("/raw-material-types", methods=["GET"], endpoint="raw_material_types_list")
def raw_material_types_list():
    """List all raw material types."""
    types = RawMaterialType.query.order_by(RawMaterialType.name).all()
    return jsonify([{
        "id": t.id,
        "code": t.code,
        "name": t.name,
        "category": t.category,
        "uom": t.uom,
    } for t in types])


@bp.route("/raw-material-types", methods=["POST"])
def create_raw_material_type():
    """Create a new raw material type record."""
    data = request.get_json()

    if not data.get("code") or not data.get("name"):
        return jsonify({"error": "code and name are required"}), 400

    try:
        rmt = RawMaterialType(
            id=str(uuid.uuid4()),
            code=data["code"],
            name=data["name"],
            category=data.get("category"),
            uom=data.get("uom", "KG"),
        )
        db.session.add(rmt)
        db.session.commit()

        return jsonify({
            "id": rmt.id,
            "code": rmt.code,
            "name": rmt.name,
            "message": "Raw material type created successfully"
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route("/raw-material-types/<rmt_id>", methods=["GET"])
def get_raw_material_type(rmt_id):
    """Get a single raw material type by id."""
    rmt = RawMaterialType.query.get_or_404(rmt_id)
    return jsonify({
        "id": rmt.id,
        "code": rmt.code,
        "name": rmt.name,
        "category": rmt.category,
        "uom": rmt.uom,
    })


@bp.route("/raw-material-types/<rmt_id>", methods=["PUT"])
def update_raw_material_type(rmt_id):
    """Update an existing raw material type."""
    rmt = RawMaterialType.query.get_or_404(rmt_id)
    data = request.get_json()

    try:
        if "code" in data:
            rmt.code = data["code"]
        if "name" in data:
            rmt.name = data["name"]
        if "category" in data:
            rmt.category = data["category"]
        if "uom" in data:
            rmt.uom = data["uom"]

        db.session.commit()

        return jsonify({
            "id": rmt.id,
            "code": rmt.code,
            "name": rmt.name,
            "message": "Raw material type updated successfully"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route("/raw-material-types/<rmt_id>", methods=["DELETE"])
def delete_raw_material_type(rmt_id):
    """Hard-delete a raw material type (no is_active column)."""
    try:
        rmt = RawMaterialType.query.get_or_404(rmt_id)
        db.session.delete(rmt)
        db.session.commit()
        return jsonify({"message": "Raw material type deleted successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ──────────────────────── Alloy Compositions Endpoints ───────────────────────

@bp.route("/alloy-compositions", methods=["GET"], endpoint="alloy_compositions_list")
def alloy_compositions_list():
    """List all alloy compositions."""
    alloys = AlloyComposition.query.order_by(AlloyComposition.alloy_code).all()
    return jsonify([{
        "id": a.id,
        "alloy_code": a.alloy_code,
        "alloy_name": a.alloy_name,
        "composition": a.composition,
        "standard": a.standard,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    } for a in alloys])


@bp.route("/alloy-compositions", methods=["POST"])
def create_alloy_composition():
    """Create a new alloy composition record."""
    data = request.get_json()

    if not data.get("alloy_code") or not data.get("alloy_name"):
        return jsonify({"error": "alloy_code and alloy_name are required"}), 400

    try:
        alloy = AlloyComposition(
            id=str(uuid.uuid4()),
            alloy_code=data["alloy_code"],
            alloy_name=data["alloy_name"],
            composition=data.get("composition", {}),
            standard=data.get("standard"),
        )
        db.session.add(alloy)
        db.session.commit()

        return jsonify({
            "id": alloy.id,
            "alloy_code": alloy.alloy_code,
            "alloy_name": alloy.alloy_name,
            "message": "Alloy composition created successfully"
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route("/alloy-compositions/<alloy_id>", methods=["GET"])
def get_alloy_composition(alloy_id):
    """Get a single alloy composition by id."""
    alloy = AlloyComposition.query.get_or_404(alloy_id)
    return jsonify({
        "id": alloy.id,
        "alloy_code": alloy.alloy_code,
        "alloy_name": alloy.alloy_name,
        "composition": alloy.composition,
        "standard": alloy.standard,
        "created_at": alloy.created_at.isoformat() if alloy.created_at else None,
    })


@bp.route("/alloy-compositions/<alloy_id>", methods=["PUT"])
def update_alloy_composition(alloy_id):
    """Update an existing alloy composition."""
    alloy = AlloyComposition.query.get_or_404(alloy_id)
    data = request.get_json()

    try:
        if "alloy_code" in data:
            alloy.alloy_code = data["alloy_code"]
        if "alloy_name" in data:
            alloy.alloy_name = data["alloy_name"]
        if "composition" in data:
            alloy.composition = data["composition"]
        if "standard" in data:
            alloy.standard = data["standard"]

        db.session.commit()

        return jsonify({
            "id": alloy.id,
            "alloy_code": alloy.alloy_code,
            "alloy_name": alloy.alloy_name,
            "message": "Alloy composition updated successfully"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route("/alloy-compositions/<alloy_id>", methods=["DELETE"])
def delete_alloy_composition(alloy_id):
    """Hard-delete an alloy composition (no is_active column)."""
    try:
        alloy = AlloyComposition.query.get_or_404(alloy_id)
        db.session.delete(alloy)
        db.session.commit()
        return jsonify({"message": "Alloy composition deleted successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ──────────────────────── Finishing Process Types Endpoints ──────────────────

@bp.route("/finishing-process-types", methods=["GET"], endpoint="finishing_process_types_list")
def finishing_process_types_list():
    """List all finishing process types."""
    types = FinishingProcessType.query.order_by(FinishingProcessType.name).all()
    return jsonify([{
        "id": t.id,
        "code": t.code,
        "name": t.name,
        "description": t.description,
        "requires_plc_instruction": t.requires_plc_instruction,
        "default_parameters": t.default_parameters,
    } for t in types])


@bp.route("/finishing-process-types", methods=["POST"])
def create_finishing_process_type():
    """Create a new finishing process type record."""
    data = request.get_json()

    if not data.get("code") or not data.get("name"):
        return jsonify({"error": "code and name are required"}), 400

    try:
        fpt = FinishingProcessType(
            id=str(uuid.uuid4()),
            code=data["code"],
            name=data["name"],
            description=data.get("description"),
            requires_plc_instruction=bool(data.get("requires_plc_instruction", False)),
            default_parameters=data.get("default_parameters", {}),
        )
        db.session.add(fpt)
        db.session.commit()

        return jsonify({
            "id": fpt.id,
            "code": fpt.code,
            "name": fpt.name,
            "message": "Finishing process type created successfully"
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route("/finishing-process-types/<fpt_id>", methods=["GET"])
def get_finishing_process_type(fpt_id):
    """Get a single finishing process type by id."""
    fpt = FinishingProcessType.query.get_or_404(fpt_id)
    return jsonify({
        "id": fpt.id,
        "code": fpt.code,
        "name": fpt.name,
        "description": fpt.description,
        "requires_plc_instruction": fpt.requires_plc_instruction,
        "default_parameters": fpt.default_parameters,
    })


@bp.route("/finishing-process-types/<fpt_id>", methods=["PUT"])
def update_finishing_process_type(fpt_id):
    """Update an existing finishing process type."""
    fpt = FinishingProcessType.query.get_or_404(fpt_id)
    data = request.get_json()

    try:
        if "code" in data:
            fpt.code = data["code"]
        if "name" in data:
            fpt.name = data["name"]
        if "description" in data:
            fpt.description = data["description"]
        if "requires_plc_instruction" in data:
            fpt.requires_plc_instruction = bool(data["requires_plc_instruction"])
        if "default_parameters" in data:
            fpt.default_parameters = data["default_parameters"]

        db.session.commit()

        return jsonify({
            "id": fpt.id,
            "code": fpt.code,
            "name": fpt.name,
            "message": "Finishing process type updated successfully"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route("/finishing-process-types/<fpt_id>", methods=["DELETE"])
def delete_finishing_process_type(fpt_id):
    """Hard-delete a finishing process type (no is_active column)."""
    try:
        fpt = FinishingProcessType.query.get_or_404(fpt_id)
        db.session.delete(fpt)
        db.session.commit()
        return jsonify({"message": "Finishing process type deleted successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ──────────────────────── Packaging Specs Endpoints ──────────────────────────

@bp.route("/packaging-specs", methods=["GET"], endpoint="packaging_specs_list")
def packaging_specs_list():
    """List all packaging specs."""
    specs = PackagingSpec.query.order_by(PackagingSpec.part_number).all()
    return jsonify([{
        "id": s.id,
        "part_number": s.part_number,
        "packing_method": s.packing_method,
        "units_per_pack": s.units_per_pack,
        "theoretical_weight_per_pack_kg": s.theoretical_weight_per_pack_kg,
        "label_template": s.label_template,
        "special_instructions": s.special_instructions,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    } for s in specs])


@bp.route("/packaging-specs", methods=["POST"])
def create_packaging_spec():
    """Create a new packaging spec record."""
    data = request.get_json()

    if not data.get("part_number"):
        return jsonify({"error": "part_number is required"}), 400

    try:
        spec = PackagingSpec(
            id=str(uuid.uuid4()),
            part_number=data["part_number"],
            packing_method=data.get("packing_method"),
            units_per_pack=int(data.get("units_per_pack")) if data.get("units_per_pack") is not None else None,
            theoretical_weight_per_pack_kg=float(data.get("theoretical_weight_per_pack_kg")) if data.get("theoretical_weight_per_pack_kg") is not None else None,
            label_template=data.get("label_template"),
            special_instructions=data.get("special_instructions"),
        )
        db.session.add(spec)
        db.session.commit()

        return jsonify({
            "id": spec.id,
            "part_number": spec.part_number,
            "message": "Packaging spec created successfully"
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route("/packaging-specs/<spec_id>", methods=["GET"])
def get_packaging_spec(spec_id):
    """Get a single packaging spec by id."""
    spec = PackagingSpec.query.get_or_404(spec_id)
    return jsonify({
        "id": spec.id,
        "part_number": spec.part_number,
        "packing_method": spec.packing_method,
        "units_per_pack": spec.units_per_pack,
        "theoretical_weight_per_pack_kg": spec.theoretical_weight_per_pack_kg,
        "label_template": spec.label_template,
        "special_instructions": spec.special_instructions,
        "created_at": spec.created_at.isoformat() if spec.created_at else None,
    })


@bp.route("/packaging-specs/<spec_id>", methods=["PUT"])
def update_packaging_spec(spec_id):
    """Update an existing packaging spec."""
    spec = PackagingSpec.query.get_or_404(spec_id)
    data = request.get_json()

    try:
        if "part_number" in data:
            spec.part_number = data["part_number"]
        if "packing_method" in data:
            spec.packing_method = data["packing_method"]
        if "units_per_pack" in data:
            spec.units_per_pack = int(data["units_per_pack"]) if data["units_per_pack"] is not None else None
        if "theoretical_weight_per_pack_kg" in data:
            spec.theoretical_weight_per_pack_kg = float(data["theoretical_weight_per_pack_kg"]) if data["theoretical_weight_per_pack_kg"] is not None else None
        if "label_template" in data:
            spec.label_template = data["label_template"]
        if "special_instructions" in data:
            spec.special_instructions = data["special_instructions"]

        db.session.commit()

        return jsonify({
            "id": spec.id,
            "part_number": spec.part_number,
            "message": "Packaging spec updated successfully"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route("/packaging-specs/<spec_id>", methods=["DELETE"])
def delete_packaging_spec(spec_id):
    """Hard-delete a packaging spec (no is_active column)."""
    try:
        spec = PackagingSpec.query.get_or_404(spec_id)
        db.session.delete(spec)
        db.session.commit()
        return jsonify({"message": "Packaging spec deleted successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ──────────────────────── Defect Codes Endpoints ─────────────────────────────

@bp.route("/defect-codes", methods=["GET"], endpoint="defect_codes_list")
def defect_codes_list():
    """List all active defect codes."""
    codes = DefectCode.query.filter_by(is_active=True).order_by(DefectCode.code).all()
    return jsonify([{
        "id": d.id,
        "code": d.code,
        "name": d.name,
        "category": d.category,
        "severity": d.severity,
        "is_active": d.is_active,
        "description": d.description,
    } for d in codes])


@bp.route("/defect-codes", methods=["POST"])
def create_defect_code():
    """Create a new defect code record."""
    data = request.get_json()

    if not data.get("code") or not data.get("name") or not data.get("category"):
        return jsonify({"error": "code, name, and category are required"}), 400

    valid_categories = ("surface", "dimensional", "functional", "aesthetic")
    valid_severities = ("minor", "moderate", "major", "critical")

    if data["category"] not in valid_categories:
        return jsonify({"error": f"category must be one of: {', '.join(valid_categories)}"}), 400

    severity = data.get("severity", "moderate")
    if severity not in valid_severities:
        return jsonify({"error": f"severity must be one of: {', '.join(valid_severities)}"}), 400

    try:
        defect = DefectCode(
            id=str(uuid.uuid4()),
            code=data["code"],
            name=data["name"],
            category=data["category"],
            severity=severity,
            is_active=True,
            description=data.get("description"),
        )
        db.session.add(defect)
        db.session.commit()

        return jsonify({
            "id": defect.id,
            "code": defect.code,
            "name": defect.name,
            "message": "Defect code created successfully"
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route("/defect-codes/<defect_id>", methods=["GET"])
def get_defect_code(defect_id):
    """Get a single defect code by id."""
    defect = DefectCode.query.get_or_404(defect_id)
    return jsonify({
        "id": defect.id,
        "code": defect.code,
        "name": defect.name,
        "category": defect.category,
        "severity": defect.severity,
        "is_active": defect.is_active,
        "description": defect.description,
    })


@bp.route("/defect-codes/<defect_id>", methods=["PUT"])
def update_defect_code(defect_id):
    """Update an existing defect code."""
    defect = DefectCode.query.get_or_404(defect_id)
    data = request.get_json()

    valid_categories = ("surface", "dimensional", "functional", "aesthetic")
    valid_severities = ("minor", "moderate", "major", "critical")

    try:
        if "code" in data:
            defect.code = data["code"]
        if "name" in data:
            defect.name = data["name"]
        if "category" in data:
            if data["category"] not in valid_categories:
                return jsonify({"error": f"category must be one of: {', '.join(valid_categories)}"}), 400
            defect.category = data["category"]
        if "severity" in data:
            if data["severity"] not in valid_severities:
                return jsonify({"error": f"severity must be one of: {', '.join(valid_severities)}"}), 400
            defect.severity = data["severity"]
        if "is_active" in data:
            defect.is_active = bool(data["is_active"])
        if "description" in data:
            defect.description = data["description"]

        db.session.commit()

        return jsonify({
            "id": defect.id,
            "code": defect.code,
            "name": defect.name,
            "message": "Defect code updated successfully"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route("/defect-codes/<defect_id>", methods=["DELETE"])
def delete_defect_code(defect_id):
    """Soft-delete a defect code (sets is_active=False)."""
    try:
        defect = DefectCode.query.get_or_404(defect_id)
        defect.is_active = False
        db.session.commit()
        return jsonify({"message": "Defect code deactivated successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ──────────────────────── Quality Parameters Endpoints ───────────────────────

def _qp_to_dict(qp):
    """Serialize a QualityParameter record to a dict."""
    return {
        "id": qp.id,
        "profile_code": qp.profile_code,
        "alloy": qp.alloy,
        "billet_temp_min": qp.billet_temp_min,
        "billet_temp_max": qp.billet_temp_max,
        "container_temp_min": qp.container_temp_min,
        "container_temp_max": qp.container_temp_max,
        "die_temp_min": qp.die_temp_min,
        "die_temp_max": qp.die_temp_max,
        "exit_temp_min": qp.exit_temp_min,
        "exit_temp_max": qp.exit_temp_max,
        "ram_speed_min": qp.ram_speed_min,
        "ram_speed_max": qp.ram_speed_max,
        "pressure_min": qp.pressure_min,
        "pressure_max": qp.pressure_max,
        "force_min": qp.force_min,
        "force_max": qp.force_max,
        "cycle_time_min": qp.cycle_time_min,
        "cycle_time_max": qp.cycle_time_max,
    }


_QP_FLOAT_FIELDS = [
    "billet_temp_min", "billet_temp_max",
    "container_temp_min", "container_temp_max",
    "die_temp_min", "die_temp_max",
    "exit_temp_min", "exit_temp_max",
    "ram_speed_min", "ram_speed_max",
    "pressure_min", "pressure_max",
    "force_min", "force_max",
    "cycle_time_min", "cycle_time_max",
]


def _apply_qp_data(qp, data):
    """Apply request data fields to a QualityParameter instance."""
    if "profile_code" in data:
        qp.profile_code = data["profile_code"]
    if "alloy" in data:
        qp.alloy = data["alloy"]
    for field in _QP_FLOAT_FIELDS:
        if field in data:
            val = data[field]
            setattr(qp, field, float(val) if val is not None else None)


@bp.route("/quality-parameters", methods=["GET"], endpoint="quality_parameters_list")
def quality_parameters_list():
    """List all active quality parameters."""
    params = QualityParameter.query.filter_by(is_active=True).order_by(
        QualityParameter.profile_code, QualityParameter.alloy
    ).all()
    return jsonify([_qp_to_dict(p) for p in params])


@bp.route("/quality-parameters", methods=["POST"])
def create_quality_parameter():
    """Create a new quality parameter record."""
    data = request.get_json()

    if not data.get("profile_code") or not data.get("alloy"):
        return jsonify({"error": "profile_code and alloy are required"}), 400

    try:
        qp = QualityParameter(
            id=str(uuid.uuid4()),
            profile_code=data["profile_code"],
            alloy=data["alloy"],
            is_active=True,
        )
        _apply_qp_data(qp, data)
        db.session.add(qp)
        db.session.commit()

        result = _qp_to_dict(qp)
        result["message"] = "Quality parameter created successfully"
        return jsonify(result), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route("/quality-parameters/<qp_id>", methods=["GET"])
def get_quality_parameter(qp_id):
    """Get a single quality parameter by id."""
    qp = QualityParameter.query.get_or_404(qp_id)
    return jsonify(_qp_to_dict(qp))


@bp.route("/quality-parameters/<qp_id>", methods=["PUT"])
def update_quality_parameter(qp_id):
    """Update an existing quality parameter."""
    qp = QualityParameter.query.get_or_404(qp_id)
    data = request.get_json()

    try:
        _apply_qp_data(qp, data)
        db.session.commit()

        result = _qp_to_dict(qp)
        result["message"] = "Quality parameter updated successfully"
        return jsonify(result), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route("/quality-parameters/<qp_id>", methods=["DELETE"])
def delete_quality_parameter(qp_id):
    """Soft-delete a quality parameter (sets is_active=False)."""
    try:
        qp = QualityParameter.query.get_or_404(qp_id)
        qp.is_active = False
        db.session.commit()
        return jsonify({"message": "Quality parameter deactivated successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
