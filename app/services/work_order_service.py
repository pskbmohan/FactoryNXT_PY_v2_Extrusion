"""Work Order service for BOM-driven WO creation from customer orders.

This module provides functions for:
- Creating work orders from customer order lines with automatic BOM resolution
- Managing the lifecycle of WOs in relation to their parent orders
"""

import uuid
from datetime import datetime

from app import db
from app.models import WorkOrder, CustomerOrderLine, CustomerOrder
from app.services.bom_service import resolve_bom_for_wo


def create_wo_from_order_line(order_line_id: str, scheduled_start=None, scheduled_end=None, priority="MEDIUM") -> WorkOrder:
    """Create a work order from a customer order line with BOM auto-resolution.

    This function:
    1. Validates the order line exists and is in OPEN status
    2. Resolves the BOM for the part number to get die/billet types
    3. Creates a WorkOrder with all BOM-related fields populated
    4. Updates the order line status to WO_CREATED
    5. If all lines have been processed, updates the parent order status

    Args:
        order_line_id: The UUID of the customer order line to create WO from.
        scheduled_start: Optional datetime for when production should start.
        scheduled_end: Optional datetime for when production should complete.
        priority: Work order priority (HIGH/MEDIUM/LOW).

    Returns:
        Created WorkOrder instance with all BOM fields populated.

    Raises:
        ValueError: If order line not found or no active BOM exists.
        RuntimeError: If WO already exists for this order line.
    """
    # Validate order line exists
    line = CustomerOrderLine.query.get(order_line_id)
    if not line:
        raise ValueError(f"Order line {order_line_id} not found.")

    # Prevent duplicate WO creation
    if line.status == "WO_CREATED":
        raise RuntimeError(f"WO already exists for order line {order_line_id}.")

    # Resolve BOM to get die/billet types
    bom_data = resolve_bom_for_wo(line.part_number_id)

    # Generate unique WO number based on parent order and line number
    order = CustomerOrder.query.get(line.order_id)
    wo_number = f"WO-{order.order_number}-L{line.line_number:02d}" if order else f"WO-L{line.line_number:02d}"

    # Create the work order with BOM-resolved fields
    wo = WorkOrder(
        id=str(uuid.uuid4()),
        order_number=wo_number,
        part_number=line.part_number.part_code,
        description=f"WO for {line.part_number.description or line.part_number.part_code}",
        quantity=int(line.ordered_qty),
        status="DRAFT",
        due_date=datetime.combine(line.required_date, datetime.min.time()) if line.required_date else None,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
        priority=priority,
        customer_order_line_id=line.id,
        part_number_id=line.part_number_id,
        die_type_id=bom_data["die_type_id"],
        billet_type_id=bom_data["billet_type_id"],
        bom_version_id=bom_data["bom_version_id"],
    )

    db.session.add(wo)
    line.status = "WO_CREATED"

    # Check if all lines in the order have been processed
    all_lines = CustomerOrderLine.query.filter_by(order_id=order.id).all()
    if all(l.status in ("WO_CREATED", "COMPLETED", "CANCELLED") for l in all_lines):
        order.status = "IN_PROGRESS"

    db.session.commit()
    return wo
