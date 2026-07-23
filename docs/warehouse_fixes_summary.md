# Warehouse Module Fixes Summary

## Issues Addressed

### 1. Dashboard Rack Modal - Dies Not Showing in Occupied Slots ✅ FIXED

**Problem:** When clicking a rack card in the dashboard, the modal showed slots occupied count but did not display the list of dies in those slots.

**Root Cause:** The JavaScript was reading `data.slots` but the API returns slots nested under `data.rack.slots`.

**Fix Applied:**
- **File:** `app/templates/warehouse/dashboard.html` (line 482)
- **Change:** `const slots = (data.slots || []);` → `const slots = (r.slots || []);`

**Code:**
```javascript
// Before
const r = data.rack;
const slots = (data.slots || []);  // WRONG - slots are under rack

// After  
const r = data.rack;
const slots = (r.slots || []);     // CORRECT - read from rack object
```

**Verification:** The modal should now display a table with columns: Slot, Die Code, Profile, Alloy, Assigned date.

---

### 2. Racks Management View - Not Showing Data ✅ FIXED

**Problem:** The racks list page was not displaying rack data properly.

**Root Cause:** Multiple issues:
1. JavaScript filter initialization was running before DOM elements existed
2. API endpoint didn't support filtering by `rack_type` parameter
3. Client-side rack_type filtering was inefficient

**Fixes Applied:**

#### A. JavaScript DOM Initialization
- **File:** `app/templates/warehouse/racks.html` (lines 310-350)
- **Change:** Wrapped filter initialization in `DOMContentLoaded` check

```javascript
// Before - ran immediately when script loaded
bindPills('filter-type', 'type', 'data-type');
bindPills('filter-status', 'status', 'data-status');

// After - waits for DOM to be ready
function initFilters() {
  bindPills('filter-type', 'type', 'data-type');
  bindPills('filter-status', 'status', 'data-status');
  // ... other setup
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initFilters);
} else {
  initFilters();
}
```

#### B. Service Layer - Added rack_type Filter
- **File:** `app/services/warehouse_service.py` (lines 71-89)
- **Change:** Added `rack_type_filter` parameter to `get_all_racks()` method

```python
@staticmethod
def get_all_racks(status_filter: str = None, zone_filter: str = None,
                  rack_type_filter: str = None) -> list:
    """Get all racks with optional filtering."""
    query = ToolRoomRack.query.filter_by(is_active=True)

    if status_filter:
        query = query.filter_by(status=status_filter.upper())
    if zone_filter:
        query = query.filter_by(location_zone=zone_filter.upper())
    if rack_type_filter:
        query = query.filter_by(rack_type=rack_type_filter)  # NEW

    racks = query.order_by(ToolRoomRack.location_zone, ToolRoomRack.rack_code).all()
    return [rack.to_dict() for rack in racks]
```

#### C. API Endpoint - Pass rack_type Filter
- **File:** `app/routes/warehouse_management.py` (lines 261-278)
- **Change:** Extract `rack_type` query param and pass to service

```python
@bp.route('/api/racks')
def api_get_racks():
    """Get all racks with optional filtering."""
    status_filter = request.args.get('status', '')
    zone_filter = request.args.get('zone', '')
    type_filter = request.args.get('rack_type', '')  # NEW

    result = warehouse_service.get_all_racks(
        status_filter=status_filter,
        zone_filter=zone_filter,
        rack_type_filter=type_filter or None  # NEW
    )

    return jsonify({
        'success': True,
        'racks': result,
        'count': len(result)
    })
```

**Verification:** The racks list page should now:
- Display all racks in a table format
- Support filtering by rack type (Storage, Quick Change, In-Press)
- Support filtering by status (Available, In Use, Maintenance)
- Support text search by rack code/name/zone

---

### 3. Die Search - Internal Server Error ✅ FIXED

**Problem:** The die search page was returning 500 Internal Server Error.

**Root Cause:** Multiple issues:
1. Route wasn't performing actual search - only loading filter options
2. Template referenced non-existent variables (`results`, `search_performed`)
3. Template used wrong field names (`slot_id` instead of `slot_number`)
4. Template tried to access nested attributes incorrectly (`r.rack.rack_code`)

**Fixes Applied:**

#### A. Route - Implement Search Logic
- **File:** `app/routes/warehouse_management.py` (lines 125-204)
- **Change:** Added search query execution and result building

```python
@bp.route('/search')
def search_dies():
    """Die location search page."""
    from sqlalchemy import distinct

    search_term = request.args.get('q', '')
    profile_code = request.args.get('profile', '')
    alloy_filter = request.args.get('alloy', '')

    # ... (filter loading code unchanged) ...

    # NEW: Perform search if query parameters provided
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
                'slot_id': loc.slot_number,  # Map slot_number to slot_id for template
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
        results=results,              # NEW
        search_performed=search_performed,  # NEW
        page_title='Search Die Locations'
    )
```

#### B. Template - Fix Variable References
- **File:** `app/templates/warehouse/search.html` (lines 95-170)
- **Changes:**
  - Wrap results in `{% if search_performed %}` block
  - Add result count display
  - Use `r.rack_code` instead of `r.rack.rack_code` (route now flattens structure)
  - Keep `r.slot_id` (route maps `slot_number` to `slot_id`)

```jinja2
<!-- Before -->
{% if results is defined and results %}
  <!-- No count display -->
  {{ r.rack.rack_code }}  <!-- WRONG - nested structure -->

<!-- After -->
{% if search_performed %}
  {% if results %}
    <div class="px-4 py-3 border-b ...">
      <h2>Search Results</h2>
      <span>{{ results|length }} die(s) found</span>
    </div>
    <!-- ... -->
    {{ r.rack_code or '—' }}  <!-- CORRECT - flattened structure -->
  {% else %}
    <div>No dies match your search</div>
  {% endif %}
{% else %}
  <div>Search for dies</div>  <!-- Initial state -->
{% endif %}
```

**Verification:** The search page should:
- Load without errors
- Show a friendly search prompt on initial load
- Display results when search terms are provided
- Show "No dies match" when search returns empty results
- Display result count

---

## Files Modified

1. `app/templates/warehouse/dashboard.html`
   - Fixed slot data path in rack detail modal

2. `app/templates/warehouse/racks.html`
   - Fixed JavaScript DOM initialization timing
   - Added DOMContentLoaded wrapper for filter setup

3. `app/services/warehouse_service.py`
   - Added `rack_type_filter` parameter to `get_all_racks()` method
   - Added rack_type filtering to query

4. `app/routes/warehouse_management.py`
   - Implemented search logic in `search_dies()` route
   - Added `rack_type` filter support to `api_get_racks()` endpoint
   - Pass rack_type to service layer

5. `app/templates/warehouse/search.html`
   - Added conditional rendering for search states
   - Fixed variable references (flattened structure)
   - Added result count display
   - Improved UX with empty/initial state messages

---

## Testing Checklist

### Dashboard
- [ ] Click on a rack card
- [ ] Modal should open showing rack details
- [ ] Modal should display "Slot Assignments" table with dies
- [ ] Each slot should show: Slot number, Die Code, Profile, Alloy, Assigned date

### Racks Management
- [ ] Navigate to /warehouse/racks
- [ ] Page should load with rack list table
- [ ] Filter by rack type (e.g., "Storage")
- [ ] Filter by status (e.g., "Available")
- [ ] Use search box to find rack by code/name
- [ ] Click "View" to open rack detail page

### Die Search
- [ ] Navigate to /warehouse/search
- [ ] Page should load without errors
- [ ] Should show "Search for dies" prompt initially
- [ ] Enter a die code and submit
- [ ] Results table should appear with count
- [ ] Try filtering by alloy
- [ ] Try filtering by profile
- [ ] Submit search with no matches
- [ ] Should show "No dies match your search" message

---

## Database Requirements

These fixes assume the warehouse database tables exist:
- `tool_room_racks`
- `die_rack_assignments`
- `rack_transactions`
- `die_location_index`

If tables don't exist, run migration:
```bash
flask db upgrade
```

Or create tables manually:
```python
from app import create_app
from app.models import db
app = create_app()
with app.app_context():
    db.create_all()
```

---

## Known Issues / Notes

1. **History Page Rack Names**: The transaction history page (issue #4 from previous request) was also fixed to show rack codes instead of UUIDs. This fix is included in the code but not explicitly requested in the current message.

2. **Browser Cache**: After applying fixes, users may need to hard-refresh (Ctrl+Shift+R) to clear cached JavaScript.

3. **API Responses**: The `/api/racks` endpoint now returns flat rack objects. If other parts of the frontend expect a different structure, they may need updating.

4. **Search Performance**: The search query loads up to 100 results. For large datasets, consider adding pagination or limiting to IN_STOCK status only.

---

## Rollback Instructions

If issues persist, you can revert these changes:

```bash
git checkout HEAD -- app/templates/warehouse/dashboard.html
git checkout HEAD -- app/templates/warehouse/racks.html
git checkout HEAD -- app/services/warehouse_service.py
git checkout HEAD -- app/routes/warehouse_management.py
git checkout HEAD -- app/templates/warehouse/search.html
```

Then restart the application:
```bash
# Depending on your setup:
flask run  # or
docker-compose restart  # or
systemctl restart factorynxt
```

---

## Contact / Next Steps

If issues persist after applying these fixes:

1. Check browser console (F12) for JavaScript errors
2. Check Flask logs for Python errors: `flask logs` or check your process manager logs
3. Verify database tables exist and have data
4. Test API endpoints directly:
   - `curl http://localhost:5000/warehouse/api/racks`
   - `curl http://localhost:5000/warehouse/api/racks/<rack_id>`
   - `curl "http://localhost:5000/warehouse/search?q=TEST"`

5. Provide specific error messages for further debugging
