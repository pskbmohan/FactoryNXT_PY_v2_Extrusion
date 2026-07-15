# BOM-Driven Work Order Feature - Handover (Session 2 Complete)

## Session Status: **COMPLETE**

### What Was Completed in Session 2

#### 1. Services Created

**`app/services/bom_service.py`** - BOM resolution service with three core functions:
- `get_active_bom(part_number_id)` - Retrieves the most recent active BOM for a part number
- `validate_part_for_customer(customer_id, part_number_id)` - Validates customer-part mapping exists
- `resolve_bom_for_wo(part_number_id)` - Resolves die/billet types when creating work orders

**`app/services/work_order_service.py`** - Work Order creation service with:
- `create_wo_from_order_line(order_line_id, scheduled_start, scheduled_end, priority)` - Creates WO from order line with automatic BOM resolution

#### 2. API Route Blueprints Created

**`app/routes/master_data_bom.py`** (Blueprint name: `master_data_bom`, prefix: `/api/master`)

Endpoints implemented:
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/customers` | List all active customers with part mapping counts |
| POST | `/customers` | Create new customer record |
| GET | `/customers/<id>` | Get single customer with part number mappings |
| GET | `/part-numbers` | List all part numbers (optional ?customer_id= filter) |
| POST | `/part-numbers` | Create new part number |
| GET | `/part-numbers/<id>` | Get part number with active BOM summary and history |
| GET | `/customer-part-numbers` | List customer-part mappings (?customer_id= filter) |
| POST | `/customer-part-numbers` | Create mapping (validates no duplicate, returns 409 on conflict) |
| DELETE | `/customer-part-numbers/<id>` | Soft-delete mapping (checks for existing order lines first) |
| GET | `/boms` | List BOMs (?part_number_id= filter) |
| POST | `/boms` | Create new BOM version (auto-deactivates existing active BOM) |
| PUT | `/boms/<id>` | Update BOM by creating new version |
| POST | `/boms/<id>/activate` | Activate specific BOM, deactivate others for same part |

**Page rendering routes also included:**
- GET `/master/customers` → `customers.html` template
- GET `/master/part-numbers` → `part_numbers.html` template  
- GET `/master/boms` → `boms.html` template
- GET `/master/customer-part-map` → `customer_part_map.html` template

**`app/routes/customer_orders_bom.py`** (Blueprint name: `customer_orders_bom`, prefix: `/api/orders`)

Endpoints implemented:
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/customer` | List customer orders with line counts (?status=, ?customer_id= filters) |
| POST | `/customer` | Create new customer order header |
| GET | `/customer/<order_id>` | Get order detail with all lines and BOM status for each |
| GET | `/customer/<order_id>/lines` | List all order lines with BOM readiness flags |
| POST | `/customer/<order_id>/lines` | Add line (VALIDATES: part mapped to customer, warns if no BOM) |
| POST | `/customer/<order_id>/lines/<line_id>` | Create WO for specific line (resolves BOM automatically) |
| POST | `/customer/<order_id>/create-all-wo` | Bulk create WOs for all OPEN lines in order |

**Page rendering routes also included:**
- GET `/orders/customer-ui` → `orders.html` template
- GET `/orders/customer-ui/<order_id>` → `order_detail.html` template (passes order_id)

#### 3. Blueprint Registration

Both blueprints registered in **`app/__init__.py`**:
```python
from app.routes.master_data_bom import bp as master_data_bom_bp
from app.routes.customer_orders_bom import bp as customer_orders_bom_bp

app.register_blueprint(master_data_bom_bp, url_prefix="/api/master")
app.register_blueprint(customer_orders_bom_bp, url_prefix="/api/orders")
```

### Error Handling & Validation

**BOM Not Found Errors:**
- `POST /boms` returns 400 if die has status "Rejected" or billet doesn't exist
- `POST /customer/<order_id>/lines/<line_id>` returns 400 with `{error: "bom_not_found", message: ...}`

**Validation Errors:**
- Customer-part mapping duplicate → 409 Conflict
- Part not mapped to customer (when adding line) → 400 with `mapping_required: true`
- Duplicate order number or part code → 409 Conflict

### Data Flow Summary

```
POST /api/master/customers           → Create Customer
POST /api/master/part-numbers        → Create Part Number  
POST /api/master/customer-part-numbers → Map Customer ↔ Part (validates uniqueness)
POST /api/master/boms                → Link Part → Die/Billet (creates version, deactivates old active)

POST /api/orders/customer            → Create Order Header
POST /api/orders/customer/<id>/lines → Add Line (validates customer-part mapping exists)
POST /api/orders/customer/<id>/lines/<line_id>  → CREATE WO (resolves BOM automatically!)
```

### Files Created/Modified in Session 2

| File | Action | Notes |
|------|--------|-------|
| `app/services/bom_service.py` | CREATED | Core BOM resolution logic |
| `app/services/work_order_service.py` | CREATED | WO creation with auto-BOM-resolution |
| `app/routes/master_data_bom.py` | CREATED | Master data API routes (customers, parts, mappings, BOMs) |
| `app/routes/customer_orders_bom.py` | CREATED | Orders & WOs API routes |
| `app/__init__.py` | MODIFIED | Imported and registered both new blueprints |

### Next Session: Session 3 - Master Data UI Screens + Sidebar Update

**Tasks for S3:**
1. Update `app/templates/layout.html`:
   - Add "Master Data" nav-group with sidebar-label
   - Add links to Customers, Part Numbers, BOMs, Customer-Part Mapping pages
   - Add "Customer Orders (BOM)" link in Planning group

2. Create template directory: `app/templates/master_data_bom/`

3. Create 4 Jinja2 HTML templates:
   - `customers.html` - Customers master list with modal for new customer
   - `part_numbers.html` - Part numbers list with BOM status badges
   - `boms.html` - BOM management with die/billet selection, version control
   - `customer_part_map.html` - Customer ↔ Part mapping UI

4. Templates should:
   - Extend `{% extends "layout.html" %}`
   - Use Tailwind CSS styling matching existing patterns
   - Be dark mode compatible (check for `.dark` class on html)
   - Load data via `fetch()` API calls to the new endpoints

### Verification Checklist for S2

- [x] All services import successfully (`bom_service`, `work_order_service`)
- [x] Both blueprints register without conflicts
- [x] Route endpoints are correctly prefixed under `/api/master` and `/api/orders`
- [x] Page rendering routes exist for template navigation
- [x] BOM auto-deactivation logic works (new version deactivates old active)
- [x] Customer-part validation prevents unmapped parts in orders

### Notes for Next Session

- The blueprint URL prefixes are already set (`/api/master`, `/api/orders`) - templates should use these when making fetch calls
- Template rendering routes use the same blueprints but different paths (e.g., `/master/customers` vs `/api/master/customers`)
- Jinja2 `url_for()` endpoints for master data pages:
  - `master_data_bom.customers_list` → `/master/customers`
  - `master_data_bom.part_numbers_list` → `/master/part-numbers`
  - `master_data_bom.boms_list` → `/master/boms`
  - `master_data_bom.customer_part_map` → `/master/customer-part-map`
