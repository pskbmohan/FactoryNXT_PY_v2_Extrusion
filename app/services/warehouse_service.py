"""Warehouse Management Service for Tool Room

Provides services for:
- Rack management (create, update, list racks)
- Die-to-rack assignment tracking
- In/out transaction processing with barcode scanning support
- Location search and die lookup functionality
"""

from datetime import datetime
import uuid
from ..models import db, ToolRoomRack, DieRackAssignment, RackTransaction, DieLocationIndex, Die


class WarehouseService:
    """Service class for warehouse management operations."""

    @staticmethod
    def create_rack(rack_code: str, rack_name: str, rack_type: str, location_zone: str = None,
                    total_slots: int = 20, description: str = None, operator_id: str = "system") -> dict:
        """Create a new storage rack.

        Args:
            rack_code: Unique identifier for the rack (e.g., 'RACK-A-001')
            rack_name: Human-readable name for the rack
            rack_type: Type of rack - STORAGE_RACK, QUICK_CHANGE_RACK, or INPRESS_RACK
            location_zone: Zone designation (e.g., ZONE_A)
            total_slots: Total number of slots in this rack
            description: Optional description
            operator_id: User who created the rack

        Returns:
            dict with success status and rack data or error message
        """
        try:
            # Check if rack_code already exists
            existing = ToolRoomRack.query.filter_by(rack_code=rack_code, is_active=True).first()
            if existing:
                return {'success': False, 'error': f'Rack code {rack_code} already exists'}

            rack_id = str(uuid.uuid4())
            new_rack = ToolRoomRack(
                id=rack_id,
                rack_code=rack_code.upper(),
                rack_name=rack_name.title(),
                rack_type=rack_type,
                location_zone=location_zone.upper() if location_zone else None,
                total_slots=total_slots,
                available_slots=total_slots,
                status='AVAILABLE',
                description=description,
                is_active=True,
                created_by=operator_id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

            db.session.add(new_rack)
            db.session.commit()

            return {
                'success': True,
                'rack': new_rack.to_dict()
            }

        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': str(e)}

    @staticmethod
    def get_all_racks(status_filter: str = None, zone_filter: str = None,
                      rack_type_filter: str = None) -> list:
        """Get all racks with optional filtering.

        Args:
            status_filter: Filter by rack status (AVAILABLE, IN_USE, MAINTENANCE)
            zone_filter: Filter by location zone
            rack_type_filter: Filter by rack type (STORAGE_RACK, QUICK_CHANGE_RACK, INPRESS_RACK)

        Returns:
            List of rack dictionaries
        """
        query = ToolRoomRack.query.filter_by(is_active=True)

        if status_filter:
            query = query.filter_by(status=status_filter.upper())
        if zone_filter:
            query = query.filter_by(location_zone=zone_filter.upper())
        if rack_type_filter:
            query = query.filter_by(rack_type=rack_type_filter)

        racks = query.order_by(ToolRoomRack.location_zone, ToolRoomRack.rack_code).all()
        return [rack.to_dict() for rack in racks]

    @staticmethod
    def get_rack(rack_id: str) -> dict:
        """Get a specific rack by ID.

        Args:
            rack_id: Rack UUID or code

        Returns:
            dict with rack data or error message
        """
        # Try to find by ID first, then by rack_code
        rack = ToolRoomRack.query.get(rack_id)
        if not rack:
            rack = ToolRoomRack.query.filter_by(rack_code=rack_id.upper()).first()

        if not rack or not rack.is_active:
            return {'success': False, 'error': f'Rack {rack_id} not found'}

        # Get slot details for this rack
        slots = DieRackAssignment.query.filter_by(
            rack_id=rack.id,
            assignment_status='ASSIGNED'
        ).order_by(DieRackAssignment.slot_number).all()

        rack_data = rack.to_dict()
        rack_data['slots'] = [slot.to_dict() for slot in slots]
        rack_data['filled_slots'] = len(slots)

        return {'success': True, 'rack': rack_data}

    @staticmethod
    def assign_die_to_rack(die_code: str, rack_id_or_code: str, slot_number: int, operator_id: str,
                           die_id: str = None, notes: str = None) -> dict:
        """Assign a die to a specific rack slot.

        Args:
            die_code: The die barcode/code being assigned
            rack_id_or_code: Rack UUID or rack code
            slot_number: Slot number in the rack (1-based)
            operator_id: User performing the assignment
            die_id: Optional Die record ID if exists in system
            notes: Optional transaction notes

        Returns:
            dict with success status and result data
        """
        try:
            # Find the rack
            rack = ToolRoomRack.query.get(rack_id_or_code)
            if not rack:
                rack = ToolRoomRack.query.filter_by(rack_code=rack_id_or_code.upper()).first()

            if not rack or not rack.is_active:
                return {'success': False, 'error': f'Rack {rack_id_or_code} not found'}

            # Check slot is available in this rack
            existing_assignment = DieRackAssignment.query.filter_by(
                rack_id=rack.id,
                slot_number=slot_number
            ).first()

            if existing_assignment and existing_assignment.assignment_status == 'ASSIGNED':
                return {
                    'success': False,
                    'error': f'Slot {slot_number} in rack {rack.rack_code} is already occupied by die {existing_assignment.die_code}'
                }

            # Check if slot number is within valid range
            if slot_number < 1 or slot_number > rack.total_slots:
                return {'success': False, 'error': f'Slot {slot_number} is outside valid range (1-{rack.total_slots})'}

            # Get die information from dies table if die_id provided
            profile_code = None
            alloy = None
            if die_id:
                die_record = Die.query.get(die_id)
                if die_record:
                    profile_code = die_record.profile_code
                    alloy = die_record.alloy

            # Create assignment
            assignment_id = str(uuid.uuid4())
            assignment = DieRackAssignment(
                id=assignment_id,
                rack_id=rack.id,
                slot_number=slot_number,
                die_code=die_code.upper(),
                die_id=die_id,
                profile_code=profile_code,
                alloy=alloy,
                assignment_status='ASSIGNED',
                assigned_by=operator_id,
                last_accessed_at=datetime.utcnow()
            )

            db.session.add(assignment)

            # Update rack available slots count
            rack.available_slots -= 1
            if rack.available_slots == 0:
                rack.status = 'IN_USE'
            elif rack.status == 'MAINTENANCE':
                rack.status = 'AVAILABLE'

            # Create transaction record for IN
            RackService._create_transaction(
                transaction_type='IN',
                rack_id=rack.id,
                slot_number=slot_number,
                die_code=die_code.upper(),
                die_id=die_id,
                profile_code=profile_code,
                alloy=alloy,
                operator_id=operator_id,
                notes=f"Assigned to {rack.rack_code} slot {slot_number}" + (f' | {notes}' if notes else '')
            )

            # Update location index
            LocationService.update_die_location(die_code.upper(), rack.id, slot_number)

            db.session.commit()

            return {
                'success': True,
                'assignment_id': assignment_id,
                'message': f'Die {die_code} successfully assigned to Rack {rack.rack_code}, Slot {slot_number}'
            }

        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': str(e)}

    @staticmethod
    def remove_die_from_rack(die_code: str, rack_id_or_code: str = None, slot_number: int = None,
                             operator_id: str = "system") -> dict:
        """Remove a die from a rack (OUT transaction).

        Args:
            die_code: The die barcode being removed
            rack_id_or_code: Optional rack identifier to narrow search
            slot_number: Optional specific slot number
            operator_id: User performing the removal

        Returns:
            dict with success status and result data
        """
        try:
            # Find the assignment by die_code (most recent active)
            query = DieRackAssignment.query.filter_by(
                die_code=die_code.upper(),
                assignment_status='ASSIGNED'
            )

            if rack_id_or_code:
                rack = ToolRoomRack.query.get(rack_id_or_code) or \
                       ToolRoomRack.query.filter_by(rack_code=rack_id_or_code.upper()).first()
                if rack:
                    query = query.filter_by(rack_id=rack.id)

            if slot_number:
                query = query.filter_by(slot_number=slot_number)

            assignment = query.first()

            if not assignment:
                return {'success': False, 'error': f'Die {die_code} not found in active assignments'}

            # Get the rack for transaction logging
            rack_id = assignment.rack_id
            slot_num = assignment.slot_number

            # Mark assignment as removed
            assignment.assignment_status = 'REMOVED'
            assignment.last_accessed_at=datetime.utcnow()

            # Update rack available slots count
            rack = ToolRoomRack.query.get(rack_id)
            if rack:
                rack.available_slots += 1
                if rack.available_slots >= rack.total_slots:
                    rack.status = 'AVAILABLE'

            # Create transaction record for OUT
            RackService._create_transaction(
                transaction_type='OUT',
                rack_id=rack.id,
                slot_number=slot_num,
                die_code=die_code.upper(),
                die_id=assignment.die_id,
                profile_code=assignment.profile_code,
                alloy=assignment.alloy,
                operator_id=operator_id,
                notes=f"Removed from {rack.rack_code} slot {slot_num}" + (f' | {notes}' if notes else '')
            )

            # Update location index
            LocationService.update_die_location(die_code.upper(), None, None)

            db.session.commit()

            return {
                'success': True,
                'message': f'Die {die_code} successfully removed from Rack {rack.rack_code}, Slot {slot_num}',
                'die_data': {
                    'die_code': assignment.die_code,
                    'profile_code': assignment.profile_code,
                    'alloy': assignment.alloy
                }
            }

        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': str(e)}


class RackService:
    """Rack management service."""

    @staticmethod
    def _create_transaction(transaction_type: str, rack_id: str = None, slot_number: int = None,
                           die_code: str = None, die_id: str = None, profile_code: str = None,
                           alloy: str = None, from_rack_id: str = None, to_rack_id: str = None,
                           operator_id: str = "system", notes: str = None) -> dict:
        """Create a rack transaction record (internal method)."""
        try:
            trans_id = str(uuid.uuid4())
            transaction = RackTransaction(
                id=trans_id,
                transaction_type=transaction_type.upper(),
                rack_id=rack_id,
                slot_number=slot_number,
                die_code=die_code.upper() if die_code else None,
                die_id=die_id,
                profile_code=profile_code,
                alloy=alloy,
                from_rack_id=from_rack_id,
                to_rack_id=to_rack_id,
                operator_id=operator_id,
                transaction_time=datetime.utcnow(),
                notes=notes
            )

            db.session.add(transaction)
            db.session.commit()

            return {
                'success': True,
                'transaction_id': trans_id
            }

        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': str(e)}


class LocationService:
    """Die location tracking service."""

    @staticmethod
    def update_die_location(die_code: str, rack_id: str = None, slot_number: int = None) -> dict:
        """Update the location index for a die.

        Args:
            die_code: Die code to update
            rack_id: New rack ID (None if die is removed from storage)
            slot_number: New slot number (None if die is removed from storage)

        Returns:
            dict with success status and result data
        """
        try:
            # Get existing location record
            location = DieLocationIndex.query.filter_by(die_code=die_code).first()

            if rack_id is None or slot_number is None:
                # Removing die from storage
                if location:
                    db.session.delete(location)
                    return {
                        'success': True,
                        'message': f'Die {die_code} removed from location index'
                    }
                return {'success': True, 'message': f'Die {die_code} not in location index'}

            # Die is now at a specific location - create or update record
            if location:
                # Update existing record
                location.rack_id = rack_id
                location.slot_number = slot_number
                location.status = 'IN_STOCK'
                location.last_updated_at = datetime.utcnow()
            else:
                # Create new record
                location = DieLocationIndex(
                    id=str(uuid.uuid4()),
                    die_code=die_code,
                    rack_id=rack_id,
                    slot_number=slot_number,
                    status='IN_STOCK',
                    last_updated_at=datetime.utcnow()
                )
                db.session.add(location)

            db.session.commit()

            return {
                'success': True,
                'message': f'Location updated for die {die_code}'
            }

        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': str(e)}

    @staticmethod
    def find_die_location(die_code: str) -> dict:
        """Find the current location of a die.

        Args:
            die_code: Die code to search for (partial match supported)

        Returns:
            dict with location data or error message
        """
        try:
            # Try exact match first, then partial match
            location = DieLocationIndex.query.filter_by(
                die_code=die_code.upper(),
                status='IN_STOCK'
            ).first()

            if not location:
                # Partial match (starts with)
                location = DieLocationIndex.query.filter(
                    db.and_(
                        DieLocationIndex.die_code.ilike(die_code.upper() + '%'),
                        DieLocationIndex.status == 'IN_STOCK'
                    )
                ).first()

            if not location:
                return {
                    'success': False,
                    'error': f'Die {die_code} not found in warehouse or no longer stored',
                    'found': False
                }

            rack = ToolRoomRack.query.get(location.rack_id)
            rack_info = {
                'rack_code': rack.rack_code if rack else None,
                'rack_name': rack.rack_name if rack else None,
                'location_zone': rack.location_zone if rack else None,
                'status': rack.status if rack else None
            }

            return {
                'success': True,
                'found': True,
                'die_code': location.die_code,
                'rack_info': rack_info,
                'slot_number': location.slot_number,
                'profile_code': location.profile_code,
                'alloy': location.alloy,
                'last_updated_at': location.last_updated_at.isoformat() if location.last_updated_at else None
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}


class TransactionService:
    """Transaction history and reporting service."""

    @staticmethod
    def get_transaction_history(die_code: str = None, rack_id_or_code: str = None,
                               transaction_type: str = None, start_date: datetime = None,
                               end_date: datetime = None, limit: int = 100) -> dict:
        """Get transaction history with filters.

        Args:
            die_code: Filter by die code (partial match)
            rack_id_or_code: Filter by rack identifier
            transaction_type: Filter by type (IN, OUT, TRANSFER, ADJUSTMENT)
            start_date: Start date filter
            end_date: End date filter
            limit: Maximum number of records to return

        Returns:
            dict with paginated transaction results
        """
        try:
            query = RackTransaction.query.order_by(RackTransaction.transaction_time.desc())

            if die_code:
                query = query.filter(RackTransaction.die_code.ilike(die_code + '%'))

            if rack_id_or_code:
                rack = ToolRoomRack.query.get(rack_id_or_code) or \
                       ToolRoomRack.query.filter_by(rack_code=rack_id_or_code.upper()).first()
                if rack:
                    query = query.filter(RackTransaction.rack_id == rack.id)

            if transaction_type:
                query = query.filter_by(transaction_type=transaction_type.upper())

            if start_date:
                query = query.filter(RackTransaction.transaction_time >= start_date)

            if end_date:
                query = query.filter(RackTransaction.transaction_time <= end_date)

            transactions = query.limit(limit).all()

            return {
                'success': True,
                'transactions': [t.to_dict() for t in transactions],
                'total_count': len(transactions),
                'limit': limit
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}


class SearchService:
    """Search and filter service for warehouse items."""

    @staticmethod
    def search_dies(search_term: str = None, profile_code: str = None, alloy: str = None,
                    rack_id_or_code: str = None) -> dict:
        """Search for dies in the warehouse.

        Args:
            search_term: General search (matches die_code or profile_code)
            profile_code: Filter by specific profile code
            alloy: Filter by alloy type
            rack_id_or_code: Filter by rack location

        Returns:
            dict with search results and statistics
        """
        try:
            query = DieLocationIndex.query.filter_by(status='IN_STOCK')

            if search_term:
                # Search in die_code or profile_code
                term = '%' + search_term.upper() + '%'
                query = query.filter(
                    db.or_(
                        DieLocationIndex.die_code.ilike(term),
                        DieLocationIndex.profile_code.ilike(term)
                    )
                )

            if profile_code:
                query = query.filter_by(profile_code=profile_code.upper())

            if alloy:
                query = query.filter_by(alloy=alloy.upper())

            if rack_id_or_code:
                rack = ToolRoomRack.query.get(rack_id_or_code) or \
                       ToolRoomRack.query.filter_by(rack_code=rack_id_or_code.upper()).first()
                if rack:
                    query = query.filter_by(rack_id=rack.id)

            results = query.all()

            # Group by rack for display
            racks_map = {}
            total_dies = 0

            for location in results:
                rack_id = location.rack_id
                if rack_id not in racks_map:
                    rack = ToolRoomRack.query.get(rack_id)
                    racks_map[rack_id] = {
                        'rack_code': rack.rack_code,
                        'rack_name': rack.rack_name,
                        'location_zone': rack.location_zone,
                        'total_slots': rack.total_slots,
                        'available_slots': rack.available_slots,
                        'dies': []
                    }

                racks_map[rack_id]['dies'].append({
                    'die_code': location.die_code,
                    'slot_number': location.slot_number,
                    'profile_code': location.profile_code,
                    'alloy': location.alloy,
                    'last_updated_at': location.last_updated_at.isoformat() if location.last_updated_at else None
                })

                total_dies += 1

            return {
                'success': True,
                'total_results': total_dies,
                'racks_with_items': len(racks_map),
                'results_by_rack': list(racks_map.values())
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}


# Export service instances for use in routes
warehouse_service = WarehouseService()
rack_service = RackService()
location_service = LocationService()
transaction_service = TransactionService()
search_service = SearchService()
