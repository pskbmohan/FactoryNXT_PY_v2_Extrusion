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
from ..models import db, ToolRoomRack, DieRackAssignment, RackTransaction, DieLocationIndex

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

    # Get available profiles
    profiles = [r[0] for r in db.session.query(distinct(DieLocationIndex.profile_code))
                .filter(DieLocationIndex.profile_code.isnot(None)).all() if r[0]]

    # Get rack types
    rack_types = [r[0] for r in db.session.query(distinct(ToolRoomRack.rack_type)).all()]

    # Perform search if query parameters provided
    results = []
    search_performed = bool(search_term or profile_code or alloy_filter)
    if search_performed:
        query = db.session.query(DieLocationIndex).filter_by(status='IN_STOCK')

        if search_term:
            term = '%' + search_term.upper() + '%'
            query = query.filter(
                db.or_(
                    DieLocationIndex.die_code.ilike(term),
                    DieLocationIndex.profile_code.ilike(term)
                )
            )

        if profile_code:
            query = query.filter(DieLocationIndex.profile_code == profile_code.upper())

        if alloy_filter:
            query = query.filter(DieLocationIndex.alloy == alloy_filter.upper())

        locations = query.limit(100).all()

        # Build results with rack info
        for loc in locations:
            rack = ToolRoomRack.query.get(loc.rack_id) if loc.rack_id else None
            results.append({
                'die_code': loc.die_code,
                'profile_code': loc.profile_code,
                'alloy': loc.alloy,
                'rack_id': loc.rack_id,
                'rack_code': rack.rack_code if rack else None,
                'rack_name': rack.rack_name if rack else None,
                'slot_id': loc.slot_number,
                'status': loc.status,
                'updated_at': loc.last_updated_at
            })

    return render_template(
        'warehouse/search.html',
        current_search=search_term,
        current_profile=profile_code,
        current_alloy=alloy_filter,
        available_alloys=available_alloys,
        alloys=available_alloys,
        profiles=profiles,
        rack_types=rack_types,
        results=results,
        search_performed=search_performed,
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
    type_filter = request.args.get('rack_type', '')

    result = warehouse_service.get_all_racks(
        status_filter=status_filter,
        zone_filter=zone_filter,
        rack_type_filter=type_filter or None
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
    """Advanced search for dies with pagination and sorting support.

    Query parameters:
        q: Search term (die_code or profile_code partial match)
        profile: Exact profile code filter
        alloy: Exact alloy type filter
        rack: Rack UUID or code filter
        page: Page number (default: 1, max: 200 per page)
        per_page: Results per page (default: 50, range: 10-200)
        sort_by: Sort field ('die_code', 'slot_number', 'last_updated_at')
        sort_order: Sort direction ('asc' or 'desc')

    Returns paginated results grouped by rack with search statistics.
    """
    # Extract and validate query parameters
    search_term = request.args.get('q', '').strip() if request.args.get('q') else None
    profile_code = request.args.get('profile', '').strip() if request.args.get('profile') else None
    alloy_filter = request.args.get('alloy', '').strip() if request.args.get('alloy') else None
    rack_id_or_code = request.args.get('rack', '').strip() if request.args.get('rack') else None

    # Pagination parameters with defaults and validation
    try:
        page = max(1, int(request.args.get('page', 1)))
        per_page = min(max(10, int(request.args.get('per_page', 50))), 200)
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': f'Invalid pagination parameters: {str(e)}'
        }), 400

    sort_by = request.args.get('sort_by', 'die_code')
    sort_order = request.args.get('sort_order', 'asc').lower()

    result = search_service.search_dies(
        search_term=search_term or None,
        profile_code=profile_code or None,
        alloy=alloy_filter or None,
        rack_id_or_code=rack_id_or_code or None,
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_order=sort_order
    )

    return jsonify(result)


@bp.route('/api/search/dies/fuzzy')
def api_search_dies_fuzzy():
    """Fuzzy search for dies with typo tolerance.

    Query parameters:
        q: Search term (minimum 3 characters required)
        threshold: Maximum edit distance allowed (default: 2, range: 1-5)

    Returns suggestions sorted by match quality, useful for autocomplete
    and misspelling correction in search interfaces.

    Example: Searching 'AB123' with threshold=1 finds 'ABC123', 'AB124', etc.
    """
    search_term = request.args.get('q', '').strip() if request.args.get('q') else ''

    try:
        threshold = min(max(1, int(request.args.get('threshold', 2))), 5)
    except ValueError:
        return jsonify({
            'success': False,
            'error': 'Invalid threshold value'
        }), 400

    if not search_term or len(search_term) < 3:
        return jsonify({
            'success': False,
            'error': 'Search term must be at least 3 characters',
            'total_matches': 0,
            'suggestions': []
        }), 400

    result = search_service.search_dies_fuzzy(search_term, threshold)
    return jsonify(result)


@bp.route('/api/search/facets')
def api_get_search_facets():
    """Get searchable facets for filter dropdowns.

    Returns aggregated counts of all unique values in the warehouse index:
        - alloys: Available alloy types with die counts
        - profiles: Profile codes with die counts
        - rack_types: Rack type distribution
        - zones: Location zone breakdown

    Useful for building dynamic filter UIs without loading full result sets.
    """
    result = search_service.get_search_facets()
    return jsonify(result)


@bp.route('/api/search/dies/autocomplete')
def api_autocomplete_dies():
    """Autocomplete suggestions for die codes.

    Query parameters:
        q: Partial die code or profile to match (minimum 2 characters)
        limit: Maximum number of suggestions (default: 10, max: 50)
        include_profile: Include matching profiles in results (default: false)

    Returns quick suggestions for search input completion.
    """
    search_term = request.args.get('q', '').strip() if request.args.get('q') else ''

    try:
        limit = min(max(1, int(request.args.get('limit', 10))), 50)
    except ValueError:
        return jsonify({
            'success': False,
            'error': 'Invalid limit parameter'
        }), 400

    if not search_term or len(search_term) < 2:
        return jsonify({
            'success': True,
            'suggestions': [],
            'total_matches': 0
        })

    # Search by die code (case-insensitive prefix match)
    term = search_term.upper().strip() + '%'
    query = db.session.query(DieLocationIndex).filter(
        DieLocationIndex.die_code.ilike(term),
        DieLocationIndex.status == 'IN_STOCK'
    ).order_by(DieLocationIndex.die_code).limit(limit)

    suggestions = []
    for location in query.all():
        rack_code = search_service._get_rack_code(location.rack_id)
        suggestions.append({
            'type': 'die',
            'value': location.die_code,
            'display': f"{location.die_code} (Slot {location.slot_number}, {rack_code})",
            'profile_code': location.profile_code,
            'alloy': location.alloy,
            'slot_number': location.slot_number,
            'rack_code': rack_code
        })

    # Optionally include profile matches
    if request.args.get('include_profile', '').lower() == 'true':
        profile_query = db.session.query(DieLocationIndex).filter(
            DieLocationIndex.profile_code.ilike(term),
            DieLocationIndex.status == 'IN_STOCK'
        ).order_by(DieLocationIndex.profile_code).limit(limit)

        for location in profile_query.all():
            if not any(s['value'] == location.profile_code for s in suggestions):
                rack_code = search_service._get_rack_code(location.rack_id)
                suggestions.append({
                    'type': 'profile',
                    'value': location.profile_code,
                    'display': f"{location.profile_code} ({len([l for l in query.filter(DieLocationIndex.profile_code == location.profile_code).all()])} dies)",
                    'alloy': location.alloy,
                    'rack_code': rack_code
                })

    return jsonify({
        'success': True,
        'suggestions': suggestions[:limit],
        'total_matches': len(suggestions),
        'search_term': search_term
    })


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

    # Enrich transactions with human-readable rack codes so the UI shows
    # rack names instead of raw UUIDs.
    if result.get('success') and result.get('transactions'):
        rack_ids = set()
        for t in result['transactions']:
            for key in ('rack_id', 'from_rack_id', 'to_rack_id'):
                if t.get(key):
                    rack_ids.add(t[key])
        rack_cache = {}
        if rack_ids:
            racks = ToolRoomRack.query.filter(ToolRoomRack.id.in_(rack_ids)).all()
            rack_cache = {r.id: {'code': r.rack_code, 'name': r.rack_name} for r in racks}
        for t in result['transactions']:
            for key, code_key, name_key in [
                ('rack_id', 'rack_code', 'rack_name'),
                ('from_rack_id', 'from_rack_code', 'from_rack_name'),
                ('to_rack_id', 'to_rack_code', 'to_rack_name'),
            ]:
                rid = t.get(key)
                info = rack_cache.get(rid) if rid else None
                t[code_key] = info['code'] if info else None
                t[name_key] = info['name'] if info else None

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
