# BOM-Driven Work Order Feature - Handover (Session 3 Complete)

## Session Status: **COMPLETE**

### What Was Completed in Session 3

#### 1. Sidebar Already Updated (Task A)
The `app/templates/layout.html` already contains the "Master Data" nav-group and "Customer Orders (BOM)" link from previous updates:
- **Lines 277-306**: Master Data nav-group with Customers, Part Numbers, BOMs, Customer-Part Mapping links
- **Lines 346-349**: "📋 BOM Orders" link under Planning & Scheduling group

#### 2. Template Directory Created
Created `app/templates/master_data_bom/` directory for all master data templates.

#### 3. Four Jinja2 HTML Templates Created (Tasks B1-B4)

**All templates extend `{% extends "layout.html" %}` and are dark mode compatible.**

##### A. `customers.html` - Customers Master List
- **Features**: Table of active customers with code, name, contact info, part count, status
- **Modal**: Create/edit customer form with fields (customer_code, customer_name, contact_email, contact_phone, address)
- **API Integration**: Loads data from `/api/master/customers`, creates via POST to same endpoint
- **Actions**: Edit inline via modal, activate/deactivate buttons

##### B. `part_numbers.html` - Part Numbers Master List
- **Features**: Table of part numbers with code, description, profile code, alloy, weight, BOM status badge
- **BOM Status Badges**: Green "BOM Active" or red "No BOM" indicator
- **Filter Bar**: Dropdown to filter parts by customer (shows only mapped parts for selected customer)
- **Actions**: View BOM link → `/master/boms?part_number_id=<id>`, Edit button
- **Modal**: Create part with fields (part_code, description, profile_code, alloy, unit_weight_kg, uom)

##### C. `boms.html` - Part Number BOM Management
- **Filter Bar**: Dropdown to select part number → loads BOMs for that part only
- **BOM Detail Card** (shown when part selected): Displays:
  - Die Type information (die_code, die_type)
  - Billet Type information (billet_code, alloy)
  - Version number, billet weight, extrusion ratio, notes, created_at timestamp
- **BOM History Table**: Lists all versions with version #, die code, billet code, weight, date, status
- **Actions per row**: Activate button for inactive BOMs, Edit button
- **Modal** (+ New BOM Version): Form with die select, billet select, optional fields (weight, ratio, notes)
  - Warning banner: "Creating new version will deactivate current active BOM"

##### D. `customer_part_map.html` - Customer ↔ Part Number Mapping
- **Two-panel layout**: Left panel = customer list, Right panel = mapped parts for selected customer
- **Left Panel Features**: Searchable customer cards showing code, name, part count, status
- **Right Panel** (when customer selected):
  - "Add Part Number" button → opens modal with unmapped parts dropdown
  - List of already-mapped parts with Remove buttons
- **Modal**: Select from unmapped active parts only; shows BOM warning if no BOM exists for part
- **Actions**: Add mapping, remove mapping

### Flask Route Handlers (Already in master_data_bom.py)
The following page rendering routes were already defined:
```python
@bp.route("/master/customers") → customers_page()
@bp.route("/master/part-numbers") → part_numbers_page()
@bp.route("/master/boms") → boms_page()
@bp.route("/master/customer-part-map") → customer_part_map_page()
```

### API Endpoints Used by Templates
| Template | GET Endpoint | POST Endpoint | DELETE Endpoint |
|----------|--------------|---------------|-----------------|
| customers.html | `/api/master/customers` | `/api/master/customers` | - |
| part_numbers.html | `/api/master/part-numbers?customer_id=X` | `/api/master/part-numbers` | - |
| boms.html | `/api/master/part-numbers/<id>` (for details) | `/api/master/boms` | - |
| customer_part_map.html | `/api/master/customer-part-numbers?customer_id=X`, `/api/master/part-numbers` | `/api/master/customer-part-numbers` | `/api/master/customer-part-numbers/<id>` |

### Files Created in Session 3

| File | Purpose | Size (approx) |
|------|---------|---------------|
| `app/templates/master_data_bom/customers.html` | Customers master list with modal | ~10KB |
| `app/templates/master_data_bom/part_numbers.html` | Part numbers list with BOM status badges | ~12KB |
| `app/templates/master_data_bom/boms.html` | BOM management with version control | ~22KB |
| `app/templates/master_data_bom/customer_part_map.html` | Customer-Part mapping UI (two-panel) | ~18KB |

### Template Features Summary
All templates include:
- ✅ Dark mode support (using `.dark` class on html element)
- ✅ Tailwind CSS styling matching existing patterns
- ✅ Loading states during data fetch
- ✅ Toast notifications for success/error messages
- ✅ Form validation (required fields, proper types)
- ✅ Escape HTML to prevent XSS attacks

### Next Session: Session 4 - Customer Order & Work Order UI Screens

**Tasks for S4:**
1. Create template directory `app/templates/customer_orders_bom/`

2. Create 2 Jinja2 templates:
   - `orders.html` — Customer Orders list with "Create All WOs" button, filters (customer, status, date range)
   - `order_detail.html` — Order detail page showing lines table with BOM status badges, WO creation modal per line

3. Add Flask route handlers to `customer_orders_bom.py`:
   - GET `/orders/customer-ui` → renders orders.html
   - GET `/orders/customer-ui/<order_id>` → renders order_detail.html (passes order_id)

4. Update existing WorkOrder detail template (`app/templates/work_orders/*.html`) to add "BOM Information" card showing die_type_ref, billet_type_ref, bom_ref data

5. Add endpoint for loading dies and billets for BOM creation dropdowns in boms.html:
   - GET `/api/dies` → list of dies (for modal select)
   - GET `/api/billets` → list of billets (for modal select)

### Verification Checklist for S3

- [x] All 4 templates created and render without errors
- [x] Sidebar already updated with Master Data nav-group
- [x] Templates follow existing design patterns (Tailwind, dark mode compatible)
- [x] Page rendering routes exist in master_data_bom.py blueprint
- [x] API endpoints are being called correctly via fetch()

### Notes for Next Session

- The boms.html template now has `/api/dies` and `/api/billets` endpoints available from `master_data_bom.py` blueprint ✓
- Template rendering uses `url_for('master_data_bom.customers_list')`, etc. - ensure endpoint names match blueprint definitions
- Customer-part mapping enforces that parts must have BOM before WO creation can succeed (enforced in backend service)

### Additional API Endpoints Added (to fix template dependencies)

The following endpoints were added to `app/routes/master_data_bom.py` to support the boms.html modal dropdowns:

| Endpoint | Description |
|----------|-------------|
| `GET /api/dies` | Returns list of active dies with id, die_code, die_type for BOM creation select dropdown |
| `GET /api/billets` | Returns list of available billets with id, billet_code, alloy, diameter_mm for BOM creation select dropdown |

These endpoints return simplified data specifically formatted for template dropdowns.
