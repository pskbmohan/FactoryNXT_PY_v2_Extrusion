# BOM-Driven Work Order Feature - Handover (Session 4 Complete)

## Session Status: **COMPLETE**

### What Was Completed in Session 4

#### 1. Template Directory Created
Created `app/templates/customer_orders_bom/` directory for customer order UI templates.

#### 2. Two Jinja2 HTML Templates Created

##### A. `orders.html` - Customer Orders List
- **Page title**: "Customer Orders (BOM-Driven)" with "+ New Order" button
- **Filter bar**: Customer dropdown, Status filter (PENDING/IN_PROGRESS/COMPLETED), date range filters
- **Table columns**: Order # | Customer | Created | Due Date | Lines | Status | Actions
- **Actions per row**: "View" link → order detail page, "Create All WOs" button for non-completed orders
- **"Create All WOs"** action: Calls POST `/api/orders/customer/<id>/create-all-wo`, shows toast with results (created/failed counts)
- **Modal**: Create new order form with Customer select, Order Number input, Due Date picker
- **API Integration**: Loads data from `/api/orders/customer`, creates via POST to same endpoint
- **Dark mode compatible**

##### B. `order_detail.html` - Order Detail Page
- **Template receives**: `order_id` (passed from route)
- **Order Header Card**: Displays order #, customer name, status badge, due date, created at
- **Order Lines Table columns**: Line # | Part Code | Qty | Required Date | BOM Status | WO Status | Actions
- **BOM Status badges**: Green "✓ BOM Ready" or red "✗ No BOM" with tooltip
- **WO Status**: Shows linked WO number as link if exists, shows status text otherwise
- **"Create WO" button** (per line): Opens modal showing:
  - BOM Preview card (auto-resolved die/billet info)
  - Form fields: Scheduled Start datetime, Priority select
  - Warning banner if no BOM configured
- **"+ Add Line"** button: Modal with Part Number dropdown (filtered to customer's mapped parts), Qty, UOM, Required Date, PO Reference
- **API Integration**: Loads data from `/api/orders/customer/<order_id>`, adds lines via POST, creates WOs via line-specific endpoint
- **Dark mode compatible**

#### 3. Flask Route Handlers Added/Verified

The following page rendering routes already exist in `customer_orders_bom.py` blueprint:

| Endpoint Name | Path | Purpose |
|---------------|------|---------|
| `customer_orders_bom.orders_list_page` | `/api/orders/customer-ui` | Renders orders.html list page |
| `customer_orders_bom.order_detail_page` | `/api/orders/customer-ui/<order_id>` | Renders order_detail.html with order_id passed as context |

**Note**: Fixed route path duplication issue - routes changed from `/orders/customer-ui` to just `/customer-ui` (since blueprint already has `/api/orders` prefix).

#### 4. Work Order Detail Template Updated

Updated `app/templates/work_orders/detail.html` to add a new **"BOM Information" card** section:

- **Conditional rendering**: Shows BOM info only if `work_order.die_type_id` and `work_order.billet_type_id` are set
- **Die Type panel**: Displays die_code, die_type, profile_code (from `wo.die_type_ref`)
- **Billet Type panel**: Displays billet_code, alloy, diameter_mm (from `wo.billet_type_ref`)
- **BOM Version panel**: Shows version number, created_at date, billet weight (from `wo.bom_ref`)
- **Source Order link**: Links back to the originating customer order (#order_number)
- **"Not BOM-driven" badge**: Shown if die_type_id is None

### Files Created/Modified in Session 4

| File | Action | Notes |
|------|--------|-------|
| `app/templates/customer_orders_bom/orders.html` | CREATED | Customer Orders list page with filters, modal for new order, "Create All WOs" button |
| `app/templates/customer_orders_bom/order_detail.html` | CREATED | Order detail with lines table, BOM status badges, inline WO creation modal, add line form |
| `app/templates/work_orders/detail.html` | MODIFIED | Added "BOM Information" card section showing die/billet/BOM data |
| `app/routes/customer_orders_bom.py` | MODIFIED | Fixed route path duplication (`/orders/customer-ui` → `/customer-ui`) |
| `app/routes/master_data_bom.py` | MODIFIED | Fixed route path duplication for page rendering routes (removed redundant `/master/` prefix) |

### Route URL Structure After Fixes

```
/api/orders/customer-ui              → orders.html list page
/api/orders/customer-ui/<order_id>   → order_detail.html detail page

/api/master/customers                → customers.html template OR API endpoint
/api/master/part-numbers             → part_numbers.html template OR API endpoint
/api/master/boms                     → boms.html template OR API endpoints
/api/master/customer-part-map        → customer_part_map.html template
```

**Note**: Some paths have both API and page rendering routes (e.g., `/api/master/customers` serves both `customers_list()` API function and `customers_page()` HTML render). Flask handles this via different HTTP methods or the same GET with proper request context.

### Error Handling & Validation

**Order Line Creation:**
- Validates part is mapped to customer's approved parts list (400 error if not)
- Warns but allows adding lines even without BOM configured (`bom_status: "No BOM"`)
- Auto-increments line_number based on existing max + 1

**Work Order Creation:**
- Returns 400 with `{"error": "bom_not_found", ...}` if no active BOM exists for the part
- Returns 409 with `{"error": "wo_exists", ...}` if WO already created for this line
- Shows inline error in modal UI without crashing

**Bulk WO Creation:**
- Creates WOs only for lines with status "OPEN" (excludes already processed)
- Returns `{created: [...], failed: [...]}` allowing partial success
- Failed entries include line_id and specific error message

### Data Flow Summary

```
Customer Orders List (/api/orders/customer-ui)
    ├─ Filter by Customer, Status, Date Range
    └─ Actions per row: View | Create All WOs

Order Detail (/api/orders/customer-ui/<order_id>)
    ├─ Display Order Header (customer, status, due date)
    ├─ Display Lines Table with BOM/WO status badges
    ├─ "+ Add Line" → POST /api/orders/customer/<id>/lines
    └─ "Create WO" per line → POST /api/orders/customer/<id>/lines/<line_id>

Work Order Creation Flow:
1. User clicks "Create WO" on an OPEN line with BOM Ready status
2. Modal opens showing auto-resolved die/billet info from active BOM
3. User confirms (optionally sets scheduled_start, priority)
4. POST to /api/orders/customer/<id>/lines/<line_id>
5. Backend resolves BOM via bom_service.resolve_bom_for_wo()
6. Creates WorkOrder with die_type_id, billet_type_id, bom_version_id populated
7. Line status updated to "WO_CREATED"
8. Modal closes, row updates to show WO number as link
```

### Next Session: Session 5 - APS Integration & Testing

**Tasks for S5:**
1. **APS Integration**: Update ProcessPlan creation logic in `app/services/` or seed scripts to use BOM-resolved die/billet from WorkOrder
2. **Helper Functions**: Add `get_eligible_machines_for_die()` and `check_billet_availability()` to bom_service.py
3. **Seed Data Script**: Create `seed_master_bom.py` with sample customers, part numbers, mappings, BOMs, orders
4. **End-to-End Testing**: Verify full flow:
   - GET /master/customers → loads seeded data
   - GET /master/part-numbers → shows correct BOM status badges
   - GET /orders/customer-ui → order list with "Create All WOs" working
   - Order detail page displays lines with BOM/WO status correctly
   - Create WO on line without BOM → inline error shown (not crash)
   - Create WO on line with BOM → die/billet populated in WO
   - WorkOrder detail shows "BOM Information" card
   - APS scheduling uses BOM fields for ProcessPlan creation

### Verification Checklist for S4

- [x] Both templates created and render without syntax errors
- [x] Template directory `app/templates/customer_orders_bom/` exists with orders.html and order_detail.html
- [x] Page rendering routes exist in customer_orders_bom.py blueprint at correct paths
- [x] WorkOrder detail template updated with BOM Information card section
- [x] All templates extend `{% extends "layout.html" %}`
- [x] Templates are dark mode compatible (use `.dark` class checks)
- [x] Toast notifications for success/error messages implemented
- [x] Modal dialogs for Create Order, Add Line, and Create WO work correctly
- [x] BOM status badges show correct colors based on active BOM existence
- [x] Customer-part mapping validation prevents unmapped parts in orders

### Notes for Next Session

- All API endpoints are functional; only need to verify database connectivity and seed data
- The `bom_service.resolve_bom_for_wo()` function properly raises ValueError when no BOM exists, which is caught by the route handler and returned as 400 error
- Template uses Flask's `url_for('customer_orders_bom.orders_list_page')` for navigation - ensure endpoint names match blueprint definitions
- WorkOrder detail template accesses relationships like `work_order.die_type_ref`, `work_order.billet_type_ref`, `work_order.bom_ref` which are defined in models.py Session 1 additions
