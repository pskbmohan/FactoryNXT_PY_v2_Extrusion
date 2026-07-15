"""Customer Orders & Work Order API routes for BOM-driven order management.

This blueprint provides RESTful endpoints for:
- Customer orders with line items
- Adding/order lines to customer orders (with BOM validation)
- Creating work orders from order lines with automatic die/billet resolution
- Bulk WO creation for all lines in an order
"""

import uuid
from datetime import datetime, date as dt_module

from flask import Blueprint, jsonify, request, g
from .. import db
from ..models import (
    CustomerOrder,
    CustomerOrderLine,
    WorkOrder,
    PartNumberBOM,
)
from ..services.work_order_service import create_wo_from_order_line

bp = Blueprint("customer_orders_bom", __name__, url_prefix="/api/orders")


# ──────────────────────── Customer Orders Endpoints ──────────────────────────

@bp.route("/customer", methods=["GET"])
def orders_list():
    """List customer orders with line counts and status."""
    statuses = request.args.get("status").split(",") if request.args.get("status") else None
    customer_id = request.args.get("customer_id")

    q = CustomerOrder.query

    if statuses:
        q = q.filter(CustomerOrder.status.in_(statuses))

    if customer_id:
        q = q.filter_by(customer_id=customer_id)

    orders = q.order_by(CustomerOrder.created_at.desc()).all()

    return jsonify([{
        "id": o.id,
        "order_number": o.order_number,
        "customer_id": o.customer_id,
        "customer_name": o.customer_name if hasattr(o, 'customer_name') else None,
        "status": o.status,
        "due_date": o.due_date.isoformat() if o.due_date else None,
        "created_at": o.created_at.isoformat(),
        "line_count": len(o.order_lines or []),
    } for o in orders])


@bp.route("/customer", methods=["POST"])
def create_customer_order():
    """Create a new customer order header."""
    data = request.get_json()

    if not all([data.get("customer_id"), data.get("order_number")]):
        return jsonify({"error": "customer_id and order_number are required"}), 400

    try:
        # Validate customer exists
        Customer.query.get_or_404(data["customer_id"])

        due_date = None
        if data.get("due_date"):
            if isinstance(data["due_date"], str):
                due_date = datetime.strptime(data["due_date"], "%Y-%m-%d").date()
            elif isinstance(data["due_date"], dt_module):
                due_date = data["due_date"]

        order = CustomerOrder(
            id=str(uuid.uuid4()),
            customer_id=data["customer_id"],
            order_number=data["order_number"],
            status="PENDING",
            due_date=due_date,
            created_at=datetime.utcnow(),
        )
        db.session.add(order)
        db.session.commit()

        return jsonify({
            "id": order.id,
            "order_number": order.order_number,
            "customer_id": order.customer_id,
            "message": "Order created successfully"
        }), 201

    except Exception as e:
        db.session.rollback()
        if "uq_customer_orders_order_number" in str(e):
            return jsonify({"error": f"Order number {data['order_number']} already exists"}), 409
        return jsonify({"error": str(e)}), 500


@bp.route("/customer/<order_id>", methods=["GET"])
def get_customer_order(order_id):
    """Get a single customer order with all lines and WO references."""
    order = CustomerOrder.query.get_or_404(order_id)

    # Build order detail with line information
    lines_data = []
    for line in sorted(order.order_lines or [], key=lambda x: x.line_number):
        # Check if active BOM exists for this part
        bom_status = "BOM Ready" if PartNumberBOM.query.filter_by(
            part_number_id=line.part_number_id, is_active=True
        ).first() else "No BOM"

        lines_data.append({
            "id": line.id,
            "line_number": line.line_number,
            "part_number_id": line.part_number_id,
            "part_code": line.part_number.part_code if line.part_number else None,
            "description": line.part_number.description if line.part_number else None,
            "ordered_qty": line.ordered_qty,
            "uom": line.uom,
            "required_date": line.required_date.isoformat() if line.required_date else None,
            "customer_po_reference": line.customer_po_reference,
            "status": line.status,
            "bom_status": bom_status,
            "work_order_id": line.work_orders[0].id if hasattr(line, 'work_orders') and line.work_orders else None,
            "work_order_number": line.work_orders[0].order_number if hasattr(line, 'work_orders') and line.work_orders else None,
        })

    return jsonify({
        "id": order.id,
        "order_number": order.order_number,
        "customer_id": order.customer_id,
        "status": order.status,
        "due_date": order.due_date.isoformat() if order.due_date else None,
        "created_at": order.created_at.isoformat(),
        "lines": lines_data,
    })


# ──────────────────────── Order Lines Endpoints ─────────────────────────────

@bp.route("/customer/<order_id>/lines", methods=["GET"])
def get_order_lines(order_id):
    """List all order lines for a customer order with BOM status."""
    order = CustomerOrder.query.get_or_404(order_id)

    # Check if this is the parent of an existing WorkOrder (legacy compatibility)
    existing_wo = None
    try:
        existing_wo = WorkOrder.query.filter_by(customer_order_line__order=order).first()
    except Exception:
        pass

    lines_data = []
    for line in sorted(order.order_lines or [], key=lambda x: x.line_number):
        # Check if active BOM exists for this part
        bom_status = "BOM Ready" if PartNumberBOM.query.filter_by(
            part_number_id=line.part_number_id, is_active=True
        ).first() else "No BOM"

        lines_data.append({
            "id": line.id,
            "line_number": line.line_number,
            "part_number_id": line.part_number_id,
            "part_code": line.part_number.part_code if line.part_number else None,
            "description": line.part_number.description if line.part_number else None,
            "ordered_qty": line.ordered_qty,
            "uom": line.uom,
            "required_date": line.required_date.isoformat() if line.required_date else None,
            "customer_po_reference": line.customer_po_reference,
            "status": line.status,
            "bom_status": bom_status,
        })

    return jsonify({
        "order_id": order.id,
        "order_number": order.order_number,
        "lines": lines_data,
    })


@bp.route("/customer/<order_id>/lines", methods=["POST"])
def add_order_line(order_id):
    """Add a new line to a customer order with BOM validation."""
    data = request.get_json()

    if not all([data.get("part_number_id"), data.get("ordered_qty")]):
        return jsonify({"error": "part_number_id and ordered_qty are required"}), 400

    try:
        # Validate order exists
        order = CustomerOrder.query.get_or_404(order_id)

        # Validate part number exists
        part = PartNumber.query.get_or_404(data["part_number_id"])

        # VALIDATE: Check if this part is mapped to the order's customer
        has_mapping = any(
            cpn.is_active and cpn.part_number_id == data["part_number_id"]
            for cpn in order.customer.customer_part_numbers or []
        )
        if not has_mapping:
            return jsonify({
                "error": f"Part number {part.part_code} is not mapped to customer {order.customer.customer_name}. Please add mapping in Master Data first.",
                "mapping_required": True,
            }), 400

        # Check if active BOM exists for this part (warn but allow)
        has_bom = PartNumberBOM.query.filter_by(
            part_number_id=data["part_number_id"], is_active=True
        ).first()

        # Auto-increment line number
        max_line_num = db.session.query(db.func.max(CustomerOrderLine.line_number)).filter_by(
            order_id=order_id
        ).scalar() or 0

        required_date = None
        if data.get("required_date"):
            if isinstance(data["required_date"], str):
                required_date = datetime.strptime(data["required_date"], "%Y-%m-%d").date()
            elif isinstance(data["required_date"], dt_module):
                required_date = data["required_date"]

        line = CustomerOrderLine(
            id=str(uuid.uuid4()),
            order_id=order.id,
            part_number_id=data["part_number_id"],
            line_number=max_line_num + 1,
            ordered_qty=float(data["ordered_qty"]),
            uom=data.get("uom", "KG"),
            required_date=required_date,
            customer_po_reference=data.get("customer_po_reference"),
            status="OPEN",
        )
        db.session.add(line)

        # Update order status if first line or not already IN_PROGRESS
        if len(order.order_lines) == 1 and order.status != "IN_PROGRESS":
            order.status = "IN_PROGRESS"

        db.session.commit()

        return jsonify({
            "id": line.id,
            "line_number": line.line_number,
            "part_code": part.part_code,
            "bom_status": "BOM Ready" if has_bom else "No BOM",
            "bom_ready": bool(has_bom),
            "message": f"Line {line.line_number} added to order"
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route("/customer/<order_id>/lines/<line_id>", methods=["POST"])
def create_wo_for_line(order_id, line_id):
    """Create a work order for a specific order line with BOM auto-resolution."""
    try:
        # Validate the line belongs to this order
        line = CustomerOrderLine.query.filter_by(
            id=line_id, order_id=order_id
        ).first_or_404()

        if line.status == "WO_CREATED":
            return jsonify({
                "error": f"Work order already exists for line {line.line_number}",
                "work_order_id": line.work_orders[0].id if hasattr(line, 'work_orders') and line.work_orders else None,
            }), 409

        # Parse optional request body fields
        data = request.get_json() or {}
        scheduled_start = datetime.fromisoformat(data["scheduled_start"]) if data.get("scheduled_start") else None
        scheduled_end = datetime.fromisoformat(data["scheduled_end"]) if data.get("scheduled_end") else None
        priority = data.get("priority", "MEDIUM")

        # Create the work order using service function (will resolve BOM)
        wo = create_wo_from_order_line(
            line_id=line_id,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            priority=priority,
        )

        # Fetch die and billet info for response
        from ..models import Die, Billet
        die = Die.query.get(wo.die_type_id) if wo.die_type_id else None
        billet = Billet.query.get(wo.billet_type_id) if wo.billet_type_id else None

        return jsonify({
            "work_order": {
                "id": wo.id,
                "order_number": wo.order_number,
                "part_number": wo.part_number,
                "quantity": wo.quantity,
                "status": wo.status,
                "priority": wo.priority,
                "due_date": wo.due_date.isoformat() if wo.due_date else None,
            },
            "die": {
                "id": die.id,
                "die_code": die.die_code,
                "die_type": die.die_type,
                "profile_code": die.profile_code,
            } if die else None,
            "billet": {
                "id": billet.id,
                "billet_code": billet.billet_code,
                "alloy": billet.alloy,
                "diameter_mm": billet.diameter_mm,
            } if billet else None,
        }), 201

    except ValueError as e:
        # BOM not found error from service
        return jsonify({
            "error": "bom_not_found",
            "message": str(e),
        }), 400

    except RuntimeError as e:
        # WO already exists error from service
        return jsonify({
            "error": "wo_exists",
            "message": str(e),
        }), 409

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route("/customer/<order_id>/create-all-wo", methods=["POST"])
def create_all_wo_for_order(order_id):
    """Create work orders for all OPEN lines in a customer order."""
    try:
        # Validate order exists
        order = CustomerOrder.query.get_or_404(order_id)

        result = {"created": [], "failed": []}

        # Get all OPEN lines (exclude those already with WO)
        open_lines = [
            line for line in order.order_lines or []
            if line.status == "OPEN" and not any(w for w in line.work_orders)
        ]

        for line in open_lines:
            try:
                wo = create_wo_from_order_line(line.id)

                # Fetch die info for response
                from ..models import Die, Billet
                die = Die.query.get(wo.die_type_id) if wo.die_type_id else None
                billet = Billet.query.get(wo.billet_type_id) if wo.billet_type_id else None

                result["created"].append({
                    "line_id": line.id,
                    "line_number": line.line_number,
                    "work_order_id": wo.id,
                    "work_order_number": wo.order_number,
                    "die_code": die.die_code if die else None,
                    "billet_code": billet.billet_code if billet else None,
                })

            except ValueError as e:
                result["failed"].append({
                    "line_id": line.id,
                    "error": "bom_not_found",
                    "message": str(e),
                })
            except RuntimeError as e:
                result["failed"].append({
                    "line_id": line.id,
                    "error": "wo_exists",
                    "message": str(e),
                })

        return jsonify(result)

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ──────────────────────── Page Rendering Routes (for S4 UI) ─────────────────

@bp.route("/customer-ui")
def orders_list_page():
    """Render Customer Orders list page."""
    from flask import render_template
    return render_template("customer_orders_bom/orders.html")


@bp.route("/customer-ui/<order_id>")
def order_detail_page(order_id):
    """Render Customer Order detail page with lines."""
    from flask import render_template
    return render_template("customer_orders_bom/order_detail.html", order_id=order_id)
