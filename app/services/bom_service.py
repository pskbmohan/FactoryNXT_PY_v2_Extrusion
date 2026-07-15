"""BOM (Bill of Materials) service for Part Number to Die/Billet resolution.

This module provides functions for:
- Retrieving active BOMs for part numbers
- Validating customer-part mappings
- Resolving die and billet types when creating work orders
"""

from app.models import PartNumberBOM, CustomerPartNumber, PartNumber
from app import db


def get_active_bom(part_number_id: str):
    """Get the most recent active BOM for a part number.

    Args:
        part_number_id: The UUID of the part number to find BOM for.

    Returns:
        PartNumberBOM instance if found, None otherwise.
    """
    return (PartNumberBOM.query
            .filter_by(part_number_id=part_number_id, is_active=True)
            .order_by(PartNumberBOM.version.desc())
            .first())


def validate_part_for_customer(customer_id: str, part_number_id: str) -> bool:
    """Validate that a customer is mapped to a specific part number.

    Args:
        customer_id: The UUID of the customer.
        part_number_id: The UUID of the part number.

    Returns:
        True if mapping exists and is active, False otherwise.
    """
    return bool(CustomerPartNumber.query
                .filter_by(customer_id=customer_id, part_number_id=part_number_id, is_active=True)
                .first())


def resolve_bom_for_wo(part_number_id: str) -> dict:
    """Resolve BOM information for creating a work order.

    This function looks up the active BOM for a given part number and returns
    all necessary fields to auto-populate a WorkOrder's die/billet references.

    Args:
        part_number_id: The UUID of the part number.

    Returns:
        Dictionary with keys:
            - die_type_id: UUID of the required die
            - billet_type_id: UUID of the required billet
            - bom_version_id: UUID of the BOM version used
            - billet_weight_kg: Expected weight per piece in kg

    Raises:
        ValueError: If no active BOM exists for the part number.
    """
    bom = get_active_bom(part_number_id)
    if not bom:
        pn = PartNumber.query.get(part_number_id)
        part_code = pn.part_code if pn else part_number_id
        raise ValueError(f"No active BOM found for Part Number '{part_code}'. Configure BOM before creating WO.")
    return {
        "die_type_id": bom.die_type_id,
        "billet_type_id": bom.billet_type_id,
        "bom_version_id": bom.id,
        "billet_weight_kg": bom.billet_weight_kg,
    }


def get_eligible_machines_for_die(die_type_id: str) -> list:
    """Returns machines compatible with the given die based on machine type/capacity.

    Args:
        die_type_id: The UUID of the die type to find eligible machines for.

    Returns:
        List of Machine instances that are active and have status 'Idle'.
    """
    from app.models import Die, Machine
    die = Die.query.get(die_type_id)
    if not die:
        return []
    # Return all idle machines - can be extended with more specific matching logic
    return Machine.query.filter_by(is_active=True, status='Idle').all()


def check_billet_availability(billet_type_id: str, required_kg: float) -> dict:
    """Check if enough billet stock is available for a production run.

    Args:
        billet_type_id: The UUID of the billet type to check.
        required_kg: The amount of kg needed for the production run.

    Returns:
        Dictionary with keys:
            - available: Boolean indicating availability
            - reason: String explaining why unavailable if applicable, or "OK" if available
            - billet: Billet instance if available, None otherwise
    """
    from app.models import Billet
    billet = Billet.query.get(billet_type_id)
    if not billet:
        return {"available": False, "reason": "Billet type not found", "billet": None}
    if billet.status in ('REJECTED', 'CONSUMED'):
        return {"available": False, "reason": f"Billet status is {billet.status}", "billet": None}
    if required_kg and billet.quantity_kg and billet.quantity_kg < required_kg:
        return {"available": False, "reason": f"Insufficient stock: {billet.quantity_kg}kg available, {required_kg}kg required", "billet": None}
    return {"available": True, "reason": "OK", "billet": billet}

