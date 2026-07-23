"""Warehouse Management System - Tool Room Routes

Provides API endpoints and UI pages for:
- Rack management (create, view racks)
- Die-to-rack assignment with barcode scanning
- In/out transactions tracking
- Location search and die lookup
- Transaction history
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session
from datetime import datetime, timedelta
from ..services.warehouse_service import (
    warehouse_service, location_service, transaction_service, search_service
)
from ..models import db, ToolRoomRack, DieRackAssignment, RackTransaction

bp = Blueprint('warehouse', __name__, url_prefix='/warehouse')


# ============================================================================
# UI PAGES
# ============================================================================

@bp.route('/')
def warehouse_dashboard():
    """Main warehouse dashboard - rack visualization."""
    # Get current user from session or default to 'system'
    operator_id = session.get('user', {}).get('employee_id', session.get('user_id', 'system'))

    return render_template(
        'warehouse/dashboard.html',
        operator_id=operator_id,
        page_title='Warehouse Management - Tool Room'
    )


@bp.route('/racks')
def racks_list():
    """Rack list view with visualization."""
    from sqlalchemy import func

    status_filter = request.args.get('status', '')
    zone_filter = request.args.get('zone', '')

    # Build query for rack data with slot counts
    query = db.session.query(
        ToolRoomRack.id,
        ToolRoomRack.rack_code,
        ToolRoomRack.rack_name,
        ToolRoomRack.rack_type,
        ToolRoomRack.location_zone,
        ToolRoomRack.total_slots,
        ToolRoomRack.available_slots,
        ToolRoomRack.status,
        func.count(DieRackAssignment.id).label('filled_count')
    ).outerjoin(
        DieRackAssignment,
        db.and_(ToolRoomRack.id == DieRackAssignment.rack_id, DieRackAssignment.assignment_status == 'ASSIGNED')
    )

    if status_filter:
        query = query.filter(ToolRoomRack.status == status_filter.upper())
    if zone_filter:
        query = query.filter(ToolRoomRack.location_zone == zone_filter.upper())

    racks_data = query.group_by(
        ToolRoomRack.id,
        ToolRoomRack.rack_code,
        ToolRoomRack.rack_name,
        ToolRoomRack.rack_type,
        ToolRoomRack.location_zone,
        ToolRoomRack.total_slots,
        ToolRoomRack.available_slots,
        ToolRoomRack.status
    ).all()

    # Format for template
    racks_list = []
    for r in racks_data:
        rack_dict = {
            'id': r.id,
            'rack_code': r.rack_code,
            'rack_name': r.rack_name,
            'rack_type': r.rack_type,
            'location_zone': r.location_zone,
            'total_slots': r.total_slots,
            'available_slots': r.available_slots,
            'status': r.status,
            'filled_slots': r.filled_count or 0
        }
        racks_list.append(rack_dict)

    return render_template(
        'warehouse/racks.html',
        current_status=status_filter,
        current_zone=zone_filter,
        racks_data=racks_list,
        page_title='Rack Management'
    )


@bp.route('/racks/create')
def create_rack_page():
    """Create new rack form."""
    return render_template(
        'warehouse/create_rack.html',
        page_title='Create New Rack'
    )


@bp.route('/rack/<rack_id>')
def rack_detail(rack_id):
    """Detailed view of a specific rack with slot visualization."""
    operator_id = session.get('user', {}).get('employee_id', session.get('user_id', 'system'))

    return render_template(
        'warehouse/rack_detail.html',
        rack_identifier=rack_id,
        operator_id=operator_id,
        page_title='Rack Details'
    )


@bp.route('/search')
def search_dies():
    """Die location search page."""
    from sqlalchemy import distinct

    search_term = request.args.get('q', '')
    profile_code = request.args.get('profile', '')
    alloy_filter = request.args.get('alloy', '')

    # Get available alloys dynamically for dropdown
    alloys_query = db.session.query(
        distinct(DieLocationIndex.alloy)
    ).filter(
        DieLocationIndex.status == 'IN_STOCK',
        DieLocationIndex.alloy.isnot(None)
    )

    if alloy_filter:
        alloys_query = alloys_query.filter(DieLocationIndex.alloy.ilike('%' + alloy_filter + '%'))

    available_alloys = [a[0] for a in alloys_query.all() if a[0]]

    return render_template(
        'warehouse/search.html',
        current_search=search_term,
        current_profile=profile_code,
        current_alloy=alloy_filter,
        available_alloys=available_alloys,
        page_title='Search Die Locations'
    )


@bp.route('/transactions')
def transactions_history():
    """Transaction history view."""
    from sqlalchemy import func

    # Get filter parameters (from query string or form)
    type_filter = request.args.get('type', '')
    die_code_filter = request.args.get('die_code', '')
    rack_filter = request.args.get('rack', '')
    start_date_str = request.args.get('start_date', '')
    end_date_str = request.args.get('end_date', '')

    # Build query with filters
    query = RackTransaction.query.order_by(RackTransaction.transaction_time.desc())

    if type_filter:
        query = query.filter_by(transaction_type=type_filter.upper())
    if die_code_filter:
        query = query.filter(RackTransaction.die_code.ilike(die_code_filter + '%'))
    if rack_filter:
        # Find racks matching the filter and include their transactions
        pass  # Rack filtering would require joining with ToolRoomRack

    # Date filtering
    try:
        if start_date_str:
            query = query.filter(RackTransaction.transaction_time >= datetime.strptime(start_date_str, '%Y-%m-%d'))
        if end_date_str:
            query = query.filter(RackTransaction.transaction_time <= datetime.combine(
                datetime.strptime(end_date_str, '%Y-%m-%d').date(),
                datetime.max.time()
            ))
    except ValueError:
        pass  # Invalid date format, skip filtering

    transactions = query.limit(100).all()

    return render_template(
        'warehouse/transactions.html',
        current_type=type_filter,
        current_die_code=die_code_filter,
        current_rack=rack_filter,
        current_start_date=start_date_str,
        current_end_date=end_date_str,
        transactions=transactions,
        operator_id=session.get('user', {}).get('employee_id', session.get('user_id', 'system')),
        page_title='Transaction History'
    )


# ============================================================================
# API ENDPOINTS - RACK MANAGEMENT
# ============================================================================

@bp.route('/api/racks')
def api_get_racks():
    """Get all racks with optional filtering."""
    status_filter = request.args.get('status', '')
    zone_filter = request.args.get('zone', '')

    result = warehouse_service.get_all_racks(
        status_filter=status_filter,
        zone_filter=zone_filter
    )

    return jsonify({
        'success': True,
        'racks': result,
        'count': len(result)
    })


@bp.route('/api/racks/<rack_id>')
def api_get_rack(rack_id):
    """Get details of a specific rack."""
    result = warehouse_service.get_rack(rack_id)

    if not result['success']:
        return jsonify(result), 404

    return jsonify(result)


@bp.route('/api/racks', methods=['POST'])
def api_create_rack():
    """Create a new rack."""
    data = request.get_json()

    required_fields = ['rack_code', 'rack_name', 'rack_type']
    for field in required_fields:
        if not data.get(field):
            return jsonify({
                'success': False,
                'error': f'Missing required field: {field}'
            }), 400

    operator_id = session.get('user', {}).get('employee_id', 'system')

    result = warehouse_service.create_rack(
        rack_code=data['rack_code'],
        rack_name=data['rack_name'],
        rack_type=data['rack_type'],
        location_zone=data.get('location_zone'),
        total_slots=data.get('total_slots', 20),
        description=data.get('description'),
        operator_id=operator_id
    )

    if not result['success']:
        return jsonify(result), 400

    return jsonify(result), 201


@bp.route('/api/racks/<rack_id>/status', methods=['PUT'])
def api_update_rack_status(rack_id):
    """Update rack status."""
    data = request.get_json()
    new_status = data.get('status')

    if not new_status:
        return jsonify({'success': False, 'error': 'No status provided'}), 400

    try:
        rack = ToolRoomRack.query.get(rack_id) or \
               ToolRoomRack.query.filter_by(rack_code=rack_id.upper()).first()

        if not rack:
            return jsonify({'success': False, 'error': 'Rack not found'}), 404

        old_status = rack.status
        rack.status = new_status
        rack.updated_at = datetime.utcnow()

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Rack status updated from {old_status} to {new_status}',
            'rack': rack.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# API ENDPOINTS - DIE ASSIGNMENT & LOCATION
# ============================================================================

@bp.route('/api/die/location', methods=['GET'])
def api_find_die_location():
    """Find current location of a die."""
    die_code = request.args.get('die_code', '')

    if not die_code:
        return jsonify({'success': False, 'error': 'No die code provided'}), 400

    result = location_service.find_die_location(die_code)

    if not result['success']:
        return jsonify(result), 404

    return jsonify(result)


@bp.route('/api/die/assign', methods=['POST'])
def api_assign_die():
    """Assign a die to a rack slot."""
    data = request.get_json()

    required_fields = ['die_code', 'rack_id_or_code', 'slot_number']
    for field in required_fields:
        if not data.get(field):
            return jsonify({
                'success': False,
                'error': f'Missing required field: {field}'
            }), 400

    operator_id = session.get('user', {}).get('employee_id', 'system')

    result = warehouse_service.assign_die_to_rack(
        die_code=data['die_code'],
        rack_id_or_code=data['rack_id_or_code'],
        slot_number=int(data['slot_number']),
        operator_id=operator_id,
        die_id=data.get('die_id'),
        notes=data.get('notes')
    )

    if not result['success']:
        return jsonify(result), 400

    return jsonify(result), 201


@bp.route('/api/die/remove', methods=['POST'])
def api_remove_die():
    """Remove a die from rack (OUT transaction)."""
    data = request.get_json()

    required_fields = ['die_code']
    for field in required_fields:
        if not data.get(field):
            return jsonify({
                'success': False,
                'error': f'Missing required field: {field}'
            }), 400

    operator_id = session.get('user', {}).get('employee_id', 'system')

    result = warehouse_service.remove_die_from_rack(
        die_code=data['die_code'],
        rack_id_or_code=data.get('rack_id_or_code'),
        slot_number=data.get('slot_number'),
        operator_id=operator_id
    )

    if not result['success']:
        return jsonify(result), 400

    return jsonify(result)


@bp.route('/api/die/scan-in', methods=['POST'])
def api_scan_die_in():
    """Quick scan-in endpoint for barcode scanner (IN transaction)."""
    data = request.get_json() or {}

    die_code = data.get('die_code')
    rack_id_or_code = data.get('rack_id_or_code')
    slot_number = data.get('slot_number')

    if not die_code:
        return jsonify({'success': False, 'error': 'Die code required for scan-in'}), 400

    # If no rack/slot specified, try to find a default or prompt user
    operator_id = session.get('user', {}).get('employee_id', 'system')

    result = warehouse_service.assign_die_to_rack(
        die_code=die_code,
        rack_id_or_code=rack_id_or_code if rack_id_or_code else None,
        slot_number=int(slot_number) if slot_number else None,
        operator_id=operator_id,
        notes="Barcode scan-in"
    )

    return jsonify(result)


@bp.route('/api/die/scan-out', methods=['POST'])
def api_scan_die_out():
    """Quick scan-out endpoint for barcode scanner (OUT transaction)."""
    data = request.get_json() or {}

    die_code = data.get('die_code')

    if not die_code:
        return jsonify({'success': False, 'error': 'Die code required for scan-out'}), 400

    operator_id = session.get('user', {}).get('employee_id', 'system')

    result = warehouse_service.remove_die_from_rack(
        die_code=die_code,
        operator_id=operator_id,
        notes="Barcode scan-out"
    )

    return jsonify(result)


# ============================================================================
# API ENDPOINTS - SEARCH & FILTERING
# ============================================================================

@bp.route('/api/search/dies')
def api_search_dies():
    """Search for dies by various criteria."""
    search_term = request.args.get('q', '')
    profile_code = request.args.get('profile', '')
    alloy_filter = request.args.get('alloy', '')
    rack_id_or_code = request.args.get('rack', '')

    result = search_service.search_dies(
        search_term=search_term if search_term else None,
        profile_code=profile_code if profile_code else None,
        alloy=alloy_filter if alloy_filter else None,
        rack_id_or_code=rack_id_or_code if rack_id_or_code else None
    )

    return jsonify(result)


@bp.route('/api/search/alloys')
def api_get_alloys():
    """Get unique alloys in warehouse."""
    from sqlalchemy import distinct

    alloys = db.session.query(
        distinct(DieLocationIndex.alloy)
    ).filter(
        DieLocationIndex.status == 'IN_STOCK',
        DieLocationIndex.alloy.isnot(None)
    ).all()

    return jsonify({
        'success': True,
        'alloys': [a[0] for a in alloys if a[0]]
    })


@bp.route('/api/search/profiles')
def api_get_profiles():
    """Get unique profile codes in warehouse."""
    from sqlalchemy import distinct

    profiles = db.session.query(
        distinct(DieLocationIndex.profile_code)
    ).filter(
        DieLocationIndex.status == 'IN_STOCK',
        DieLocationIndex.profile_code.isnot(None)
    ).all()

    return jsonify({
        'success': True,
        'profiles': [p[0] for p in profiles if p[0]]
    })


# ============================================================================
# API ENDPOINTS - TRANSACTION HISTORY
# ============================================================================

@bp.route('/api/transactions')
def api_get_transactions():
    """Get transaction history with filters."""
    die_code = request.args.get('die_code', '')
    rack_id_or_code = request.args.get('rack', '')
    transaction_type = request.args.get('type', '')
    limit = int(request.args.get('limit', 100))

    # Date filtering
    start_date = None
    end_date = None

    if request.args.get('start_date'):
        try:
            start_date = datetime.fromisoformat(request.args.get('start_date'))
        except ValueError:
            pass

    if request.args.get('end_date'):
        try:
            end_date = datetime.fromisoformat(request.args.get('end_date'))
        except ValueError:
            pass

    result = transaction_service.get_transaction_history(
        die_code=die_code,
        rack_id_or_code=rack_id_or_code,
        transaction_type=transaction_type if transaction_type else None,
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )

    return jsonify(result)


@bp.route('/api/transactions/stats')
def api_get_transaction_stats():
    """Get transaction statistics."""
    # Count by type
    from sqlalchemy import func

    stats = db.session.query(
        RackTransaction.transaction_type,
        func.count(RackTransaction.id).label('count'),
        func.min(RackTransaction.transaction_time).label('first_occurrence'),
        func.max(RackTransaction.transaction_time).label('last_occurrence')
    ).group_by(RackTransaction.transaction_type).all()

    return jsonify({
        'success': True,
        'statistics': [
            {
                'type': s[0],
                'count': s[1],
                'first_occurrence': s[2].isoformat() if s[2] else None,
                'last_occurrence': s[3].isoformat() if s[3] else None
            }
            for s in stats
        ]
    })


# ============================================================================
# API ENDPOINTS - RACK VISUALIZATION DATA
# ============================================================================

@bp.route('/api/racks/<rack_id>/slots')
def api_get_rack_slots(rack_id):
    """Get all slots for a rack with their status."""
    result = warehouse_service.get_rack(rack_id)

    if not result['success']:
        return jsonify(result), 404

    # Format slot data for visualization
    slots_data = []
    total_slots = result['rack']['total_slots']

    for i in range(1, total_slots + 1):
        assignment = DieRackAssignment.query.filter_by(
            rack_id=result['rack']['id'],
            slot_number=i,
            assignment_status='ASSIGNED'
        ).first()

        if assignment:
            slots_data.append({
                'slot_number': i,
                'status': 'occupied',
                'die_code': assignment.die_code,
                'profile_code': assignment.profile_code,
                'alloy': assignment.alloy,
                'assigned_at': assignment.assigned_at.isoformat() if assignment.assigned_at else None,
                'last_accessed': assignment.last_accessed_at.isoformat() if assignment.last_accessed_at else None
            })
        else:
            slots_data.append({
                'slot_number': i,
                'status': 'empty',
                'die_code': None,
                'profile_code': None,
                'alloy': None
            })

    return jsonify({
        'success': True,
        'rack_id': result['rack']['id'],
        'rack_code': result['rack']['rack_code'],
        'total_slots': total_slots,
        'slots': slots_data
    })


# ============================================================================
# UTILITY ENDPOINTS
# ============================================================================

@bp.route('/api/stats/overview')
def api_overview_stats():
    """Get warehouse overview statistics."""
    # Total racks
    total_racks = ToolRoomRack.query.filter_by(is_active=True).count()

    # Racks by status
    racks_by_status = db.session.query(
        ToolRoomRack.status,
        func.count(ToolRoomRack.id)
    ).filter(
        ToolRoomRack.is_active == True
    ).group_by(ToolRoomRack.status).all()

    # Total dies in storage
    total_dies = db.session.query(
        func.count(DieLocationIndex.id)
    ).filter(
        DieLocationIndex.status == 'IN_STOCK'
    ).scalar() or 0

    # Recent activity (last 24 hours)
    yesterday = datetime.utcnow() - timedelta(days=1)
    recent_transactions = db.session.query(
        func.count(RackTransaction.id)
    ).filter(
        RackTransaction.transaction_time >= yesterday
    ).scalar() or 0

    return jsonify({
        'success': True,
        'statistics': {
            'total_racks': total_racks,
            'racks_by_status': [
                {'status': r[0], 'count': r[1]} for r in racks_by_status
            ],
            'total_dies_stored': total_dies,
            'recent_transactions_24h': recent_transactions,
            'timestamp': datetime.utcnow().isoformat()
        }
    })


@bp.route('/api/rack-types')
def api_get_rack_types():
    """Get available rack types."""
    return jsonify({
        'success': True,
        'rack_types': [
            {'code': 'STORAGE_RACK', 'name': 'Storage Rack'},
            {'code': 'QUICK_CHANGE_RACK', 'name': 'Quick Change Rack'},
            {'code': 'INPRESS_RACK', 'name': 'In-Press Rack'}
        ]
    })
