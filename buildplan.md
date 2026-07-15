# BOM-Driven Work Order Feature — Build Plan
**Repo:** `pskbmohan/FactoryNXT_PY_v2_Extrusion`
**Feature:** Customer → Part Number → BOM → Die/Billet → Work Order → APS Planning
**Estimated Sessions:** 5 focused Claude Code sessions

---

## Architecture Overview

```
Customer Master
    └── CustomerPartNumber (mapping)
            └── PartNumber Master
                    └── PartNumberBOM (active BOM)
                            ├── die_type_id → Die (existing)
                            └── billet_type_id → Billet (existing)

CustomerOrder (header)
    └── CustomerOrderLine (per part)
            └── [create-wo] → WorkOrder (auto-resolves BOM)
                                └── ProcessPlan (APS uses die + billet)
```

---

## Session Map

| Session | Scope | Deliverables |
|---|---|---|
| **S1** | Models + Migration | 5 new models, WorkOrder patch, Alembic migration |
| **S2** | Backend Services + APIs | bom_service, work_order_service, 3 route blueprints |
| **S3** | Master Data UI | Customers, Part Numbers, BOM screens + sidebar |
| **S4** | Customer Order + WO UI | Order list/form, order lines, WO creation with BOM preview |
| **S5** | APS Integration + Testing | ProcessPlan BOM-aware scheduling, seed data, end-to-end test |

---

## Session 1 — Models & Migration

### Objective
Add all new SQLAlchemy models, patch `WorkOrder`, generate and apply Alembic migration.

### Prompt

```
You are working on the FactoryNXT_PY_v2_Extrusion Flask/SQLAlchemy MES application.

TASK: Add new database models for BOM-driven Work Order creation.

## Step 1 — Read existing models first
Read `app/models.py` in full before making any changes. The existing models you must NOT modify (except WorkOrder patch below) are:
- Customer (does NOT exist yet — create it)
- WorkOrder (exists — append new columns only)
- Die (exists, table=dies — use for FK)
- Billet (exists, table=billets — use for FK)
- CustomerOrder (exists, table=customer_orders)

## Step 2 — Add the following to app/models.py

Add `import uuid as _uuid` at the top if not present.

Append these 5 new model classes at the END of app/models.py under the comment:
# ─── EXTRUSION MASTER DATA: CUSTOMER / PART NUMBER / BOM ──────────────────────

### Customer
```python
class Customer(db.Model):
    __tablename__ = "customers"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    customer_code = db.Column(db.String(64), unique=True, nullable=False)
    customer_name = db.Column(db.String(128), nullable=False)
    contact_email = db.Column(db.String(128), nullable=True)
    contact_phone = db.Column(db.String(32), nullable=True)
    address = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

### PartNumber
```python
class PartNumber(db.Model):
    __tablename__ = "part_numbers"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    part_code = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    profile_code = db.Column(db.String(64), nullable=True)
    alloy = db.Column(db.String(64), nullable=True)
    unit_weight_kg = db.Column(db.Float, nullable=True)
    uom = db.Column(db.String(16), default="KG")
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

### CustomerPartNumber
```python
class CustomerPartNumber(db.Model):
    __tablename__ = "customer_part_numbers"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    customer_id = db.Column(db.String(36), db.ForeignKey("customers.id"), nullable=False)
    part_number_id = db.Column(db.String(36), db.ForeignKey("part_numbers.id"), nullable=False)
    customer_part_ref = db.Column(db.String(64), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    customer = db.relationship("Customer", backref="customer_part_numbers")
    part_number = db.relationship("PartNumber", backref="customer_part_numbers")
    __table_args__ = (db.UniqueConstraint("customer_id", "part_number_id", name="uq_customer_part"),)
```

### PartNumberBOM
```python
class PartNumberBOM(db.Model):
    __tablename__ = "part_number_boms"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    part_number_id = db.Column(db.String(36), db.ForeignKey("part_numbers.id"), nullable=False)
    version = db.Column(db.Integer, nullable=False, default=1)
    die_type_id = db.Column(db.String(36), db.ForeignKey("dies.id"), nullable=False)
    billet_type_id = db.Column(db.String(36), db.ForeignKey("billets.id"), nullable=False)
    billet_weight_kg = db.Column(db.Float, nullable=True)
    extrusion_ratio = db.Column(db.Float, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.String(128), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    part_number = db.relationship("PartNumber", backref="boms")
    die_type = db.relationship("Die", backref="bom_entries")
    billet_type = db.relationship("Billet", backref="bom_entries")
```

### CustomerOrderLine
```python
class CustomerOrderLine(db.Model):
    __tablename__ = "customer_order_lines"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    order_id = db.Column(db.String(36), db.ForeignKey("customer_orders.id"), nullable=False)
    part_number_id = db.Column(db.String(36), db.ForeignKey("part_numbers.id"), nullable=False)
    line_number = db.Column(db.Integer, nullable=False, default=1)
    ordered_qty = db.Column(db.Float, nullable=False)
    uom = db.Column(db.String(16), default="KG")
    required_date = db.Column(db.Date, nullable=True)
    customer_po_reference = db.Column(db.String(64), nullable=True)
    status = db.Column(db.String(32), nullable=False, default="OPEN")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    order = db.relationship("CustomerOrder", backref="order_lines")
    part_number = db.relationship("PartNumber", backref="order_lines")
```

## Step 3 — Patch WorkOrder model
Append these columns INSIDE the existing `WorkOrder` class body (after `completed_at`):
```python
    customer_order_line_id = db.Column(db.String(36), db.ForeignKey("customer_order_lines.id"), nullable=True)
    part_number_id = db.Column(db.String(36), db.ForeignKey("part_numbers.id"), nullable=True)
    die_type_id = db.Column(db.String(36), db.ForeignKey("dies.id"), nullable=True)
    billet_type_id = db.Column(db.String(36), db.ForeignKey("billets.id"), nullable=True)
    bom_version_id = db.Column(db.String(36), db.ForeignKey("part_number_boms.id"), nullable=True)
    customer_order_line = db.relationship("CustomerOrderLine", backref="work_orders", foreign_keys=[customer_order_line_id])
    part_number_ref = db.relationship("PartNumber", backref="work_orders", foreign_keys=[part_number_id])
    die_type_ref = db.relationship("Die", backref="work_orders", foreign_keys=[die_type_id])
    billet_type_ref = db.relationship("Billet", backref="work_orders", foreign_keys=[billet_type_id])
    bom_ref = db.relationship("PartNumberBOM", backref="work_orders", foreign_keys=[bom_version_id])
```

## Step 4 — Generate and apply migration
```bash
flask db migrate -m "add_customer_part_bom_wo_fields"
flask db upgrade
```

Verify the migration file captures all 5 new tables and the 5 new columns on work_orders.

## Verification
After migration runs, confirm with:
```bash
flask shell
>>> from app.models import Customer, PartNumber, CustomerPartNumber, PartNumberBOM, CustomerOrderLine
>>> print("All models imported OK")
```
```

---

## Session 2 — Backend Services & API Routes

### Objective
Create BOM resolution service, Work Order creation service, and all REST API endpoints.

### Prompt

```
You are working on FactoryNXT_PY_v2_Extrusion. Session 1 is complete:
- Models Customer, PartNumber, CustomerPartNumber, PartNumberBOM, CustomerOrderLine are in app/models.py
- WorkOrder has: customer_order_line_id, part_number_id, die_type_id, billet_type_id, bom_version_id
- Migration has been applied

TASK: Create backend services and API route blueprints.

## Step 1 — Create app/services/bom_service.py

```python
from app.models import PartNumberBOM, CustomerPartNumber, PartNumber
from app import db

def get_active_bom(part_number_id: str):
    return (PartNumberBOM.query
            .filter_by(part_number_id=part_number_id, is_active=True)
            .order_by(PartNumberBOM.version.desc())
            .first())

def validate_part_for_customer(customer_id: str, part_number_id: str) -> bool:
    return bool(CustomerPartNumber.query
                .filter_by(customer_id=customer_id, part_number_id=part_number_id, is_active=True)
                .first())

def resolve_bom_for_wo(part_number_id: str) -> dict:
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
```

## Step 2 — Create app/services/work_order_service.py

```python
import uuid
from datetime import datetime
from app import db
from app.models import WorkOrder, CustomerOrderLine, CustomerOrder
from app.services.bom_service import resolve_bom_for_wo

def create_wo_from_order_line(order_line_id: str, scheduled_start=None, scheduled_end=None, priority="MEDIUM") -> WorkOrder:
    line = CustomerOrderLine.query.get(order_line_id)
    if not line:
        raise ValueError(f"Order line {order_line_id} not found.")
    if line.status == "WO_CREATED":
        raise RuntimeError(f"WO already exists for order line {order_line_id}.")
    order = CustomerOrder.query.get(line.order_id)
    bom_data = resolve_bom_for_wo(line.part_number_id)
    wo_number = f"WO-{order.order_number}-L{line.line_number:02d}"
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
    all_lines = CustomerOrderLine.query.filter_by(order_id=order.id).all()
    if all(l.status in ("WO_CREATED", "COMPLETED", "CANCELLED") for l in all_lines):
        order.status = "IN_PROGRESS"
    db.session.commit()
    return wo
```

## Step 3 — Create app/routes/master_data_bom.py

Blueprint name: `master_data_bom`, url_prefix: `/api/master`

Implement these endpoints — all return JSON, follow existing route patterns in the codebase:

GET  /customers           → list all active customers
POST /customers           → create customer {customer_code, customer_name, contact_email, contact_phone, address}
GET  /customers/<id>      → get single customer with their part number mappings

GET  /part-numbers        → list all part numbers (optional ?customer_id= filter returns only mapped PNs)
POST /part-numbers        → create part number {part_code, description, profile_code, alloy, unit_weight_kg, uom}
GET  /part-numbers/<id>   → get part number with active BOM summary

GET  /customer-part-numbers           → list mappings (?customer_id= filter)
POST /customer-part-numbers           → {customer_id, part_number_id, customer_part_ref}; validate no duplicate; return 409 on IntegrityError
DELETE /customer-part-numbers/<id>    → soft delete (is_active=False)

GET  /boms                → list BOMs (?part_number_id= filter)
POST /boms                → {part_number_id, die_type_id, billet_type_id, billet_weight_kg, extrusion_ratio, notes}
                            validate die exists and status != 'Rejected'; validate billet exists
                            auto-deactivate existing active BOM for same part_number_id; version = max(existing)+1
PUT  /boms/<id>           → update BOM (creates new version, deactivates old)
POST /boms/<id>/activate  → set is_active=True for this BOM, is_active=False for all others with same part_number_id

## Step 4 — Create app/routes/customer_orders_bom.py

Blueprint name: `customer_orders_bom`, url_prefix: `/api/orders`

GET  /customer                                → list customer orders with line counts
POST /customer                               → create order header {customer_id, order_number, due_date}
GET  /customer/<order_id>                    → order detail with lines + WO refs

POST /customer/<order_id>/lines              → add line {part_number_id, ordered_qty, uom, required_date, customer_po_reference}
     VALIDATE: part_number_id mapped to order's customer_id (CustomerPartNumber)
     VALIDATE: active BOM exists for part_number_id (warn but allow if no BOM, set flag bom_ready: false)
     auto-set line_number = max existing + 1

GET  /customer/<order_id>/lines              → list lines with BOM status and WO refs

POST /customer/<order_id>/lines/<line_id>/create-wo  → calls create_wo_from_order_line(line_id)
     accepts body: {scheduled_start, scheduled_end, priority}
     returns: {work_order: {...}, die: {...}, billet: {...}}
     on ValueError: return 400 {error: "bom_not_found", message: "..."}
     on RuntimeError: return 409 {error: "wo_exists", message: "..."}

POST /customer/<order_id>/create-all-wo     → creates WOs for all OPEN lines
     returns: {created: [...], failed: [{line_id, error}]}

## Step 5 — Register blueprints in app/__init__.py

Add:
from app.routes.master_data_bom import master_data_bom_bp
from app.routes.customer_orders_bom import customer_orders_bom_bp
app.register_blueprint(master_data_bom_bp)
app.register_blueprint(customer_orders_bom_bp)

## Verification
Test with curl or httpie:
- POST /api/master/customers  →  201
- POST /api/master/part-numbers  →  201
- POST /api/master/boms  →  201
- POST /api/orders/customer  →  201
- POST /api/orders/customer/<id>/lines  →  201
- POST /api/orders/customer/<id>/lines/<line_id>/create-wo  →  201 with die + billet populated
```

---

## Session 3 — Master Data UI Screens + Sidebar Update

### Objective
Build Jinja2 HTML templates for Customers, Part Numbers, and BOM management. Add a new "Master Data" nav group to `app/templates/layout.html`.

### Prompt

```
You are working on FactoryNXT_PY_v2_Extrusion. Sessions 1 and 2 are complete.
The app uses: Tailwind CSS (CDN), Inter font, dark/light mode via class "dark" on html.
The sidebar is in app/templates/layout.html — study the existing nav-group pattern carefully before editing.

Active sidebar patterns from layout.html:
- nav-group with group-header (icon + label-text + arrow) + nav-children (list of <a> tags)
- Active link: class="{% if request.endpoint == 'blueprint.endpoint' %}active{% endif %}"
- Blueprint active group: class="nav-group {% if request.blueprint == 'master_data_bom' %}open{% endif %}"
- Child link indent: padding: 8px 16px 8px 50px (from nav-children a CSS)
- Section divider: <div class="sidebar-label">Section Name</div>

TASK A — Update app/templates/layout.html sidebar

Insert a new sidebar section AFTER the `<div class="sidebar-label">Operations</div>` line and BEFORE the Planning & Scheduling nav-group.

Add a sidebar-label: "Master Data"

Add this nav-group:
```html
<div class="nav-group {% if request.blueprint == 'master_data_bom' %}open{% endif %}">
  <div class="group-header" data-tip="Master Data">
    <svg class="icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
      <path stroke-linecap="round" stroke-linejoin="round"
        d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 5.625c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125" />
    </svg>
    <span class="label-text">Master Data</span>
    <svg class="arrow" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
      <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
    </svg>
  </div>
  <div class="nav-children">
    <a href="{{ url_for('master_data_bom.customers_list') }}"
       class="{% if request.endpoint == 'master_data_bom.customers_list' %}active{% endif %}">
      Customers
    </a>
    <a href="{{ url_for('master_data_bom.part_numbers_list') }}"
       class="{% if request.endpoint == 'master_data_bom.part_numbers_list' %}active{% endif %}">
      Part Numbers
    </a>
    <a href="{{ url_for('master_data_bom.boms_list') }}"
       class="{% if request.endpoint == 'master_data_bom.boms_list' %}active{% endif %}">
      Part Number BOM
    </a>
    <a href="{{ url_for('master_data_bom.customer_part_map') }}"
       class="{% if request.endpoint == 'master_data_bom.customer_part_map' %}active{% endif %}">
      Customer-Part Mapping
    </a>
  </div>
</div>
```

Also add inside the existing "Planning & Scheduling" nav-children, after the "Customer Orders" link:
```html
<a href="{{ url_for('customer_orders_bom.orders_list') }}"
   class="{% if request.endpoint == 'customer_orders_bom.orders_list' %}active{% endif %}">
  Customer Orders (BOM)
</a>
```

TASK B — Create template directory app/templates/master_data_bom/

Create these 4 Jinja2 HTML template files, all extending {% extends "layout.html" %}:

### 1. app/templates/master_data_bom/customers.html
Page: Customers Master List
- Page title: "Customers" with "+ New Customer" button (opens modal)
- Table columns: Customer Code | Customer Name | Contact | Part Numbers (count) | Status | Actions
- Modal: form with fields customer_code, customer_name, contact_email, contact_phone, address
- Edit row inline or via modal
- Submits to POST /api/master/customers via fetch() then reloads table
- Style: match existing table patterns — white card, border, rounded-lg, text-sm, dark mode compatible

### 2. app/templates/master_data_bom/part_numbers.html
Page: Part Numbers Master List
- Page title: "Part Numbers" with "+ New Part Number" button (opens modal)
- Table columns: Part Code | Description | Profile Code | Alloy | Weight (kg) | BOM Status | Actions
- BOM Status column: green badge "BOM Active" if active BOM exists, red badge "No BOM" if not
- Actions: "View BOM" link → /master/boms?part_number_id=<id>
- Modal: form with fields part_code, description, profile_code, alloy, unit_weight_kg, uom
- Loads data via fetch('/api/master/part-numbers') on DOMContentLoaded
- Dark mode compatible

### 3. app/templates/master_data_bom/boms.html
Page: Part Number BOM Management
- Filter bar at top: dropdown to select Part Number (loads from /api/master/part-numbers)
- BOM detail card showing: Die Type (die_code, die_type, profile_code), Billet Type (billet_code, alloy, diameter_mm), version, billet_weight_kg, extrusion_ratio, notes, is_active status
- "+ New BOM Version" button: form with part_number_id (preselected from filter), die select (loads from /api/dies), billet select (loads from /api/billets), billet_weight_kg, extrusion_ratio, notes
- BOM history table: version | die | billet | created_at | active (toggle)
- Activate button per row: calls POST /api/master/boms/<id>/activate
- Important: when creating new BOM, warn user "This will deactivate the current active BOM for this part."
- Dark mode compatible

### 4. app/templates/master_data_bom/customer_part_map.html
Page: Customer ↔ Part Number Mapping
- Left panel: Customer list (cards or list), click to select
- Right panel: Part Numbers mapped to selected customer
  - List of mapped part numbers with: Part Code | BOM Status | Remove button
  - "+ Add Part Number" dropdown: shows only unmapped active part numbers for this customer
  - On add: POST /api/master/customer-part-numbers
  - On remove: DELETE /api/master/customer-part-numbers/<id>
- Dark mode compatible

TASK C — Add Flask route handlers for template rendering in master_data_bom.py blueprint

Add these page-rendering routes (separate from the API routes):
GET /master/customers         → renders master_data_bom/customers.html
GET /master/part-numbers      → renders master_data_bom/part_numbers.html
GET /master/boms              → renders master_data_bom/boms.html
GET /master/customer-part-map → renders master_data_bom/customer_part_map.html

Register url_for endpoints as:
master_data_bom.customers_list
master_data_bom.part_numbers_list
master_data_bom.boms_list
master_data_bom.customer_part_map
```

---

## Session 4 — Customer Order & Work Order UI Screens

### Objective
Build the Customer Order management UI with order line entry, BOM preview, and one-click WO creation. Update sidebar Planning group.

### Prompt

```
You are working on FactoryNXT_PY_v2_Extrusion. Sessions 1–3 are complete.
The sidebar already has a "Master Data" group and "Customer Orders (BOM)" link in Planning.

TASK A — Create app/templates/customer_orders_bom/ directory with 2 templates

### 1. app/templates/customer_orders_bom/orders.html
Page: Customer Orders List
- Header: "Customer Orders" + "+ New Order" button
- Filter bar: Customer dropdown, Status filter (PENDING / IN_PROGRESS / COMPLETED), date range
- Table: Order # | Customer | Created | Due Date | Lines | Status | Actions (View / Create All WOs)
- "Create All WOs" button → calls POST /api/orders/customer/<id>/create-all-wo
  - Shows result toast: "3 WOs created, 1 failed (No BOM for PN-001)"
  - Failures shown in red inline below the row
- Clicking Order # → navigates to order detail page
- Loads via fetch('/api/orders/customer') on DOMContentLoaded
- Dark mode compatible

### 2. app/templates/customer_orders_bom/order_detail.html
Page: Customer Order Detail
Template receives: order_id (from URL parameter)

Layout:
- Top card: Order header info — Order #, Customer, Status badge, Due Date, Created At
- "Order Lines" section (table):
  Columns: Line # | Part Code | Qty | UOM | Required Date | BOM Status | WO Status | Actions

  BOM Status badge:
  - Green "BOM Ready" if active BOM exists for the part
  - Red "No BOM" if not — show tooltip "Configure BOM in Master Data first"

  WO Status:
  - "DRAFT / RELEASED / RUNNING" badge if WO exists (link to WO detail)
  - "Create WO" button if line.status == "OPEN" and BOM is ready
  - Grey "No BOM" disabled button if BOM is not ready

  "Create WO" button action:
  - Opens a small inline modal / slide-down panel showing BOM preview:
    - Die: die_code, die_type, profile_code
    - Billet: billet_code, alloy, diameter_mm
    - Optional: scheduled_start datetime input, priority select (HIGH/MEDIUM/LOW)
  - On confirm: POST /api/orders/customer/<order_id>/lines/<line_id>/create-wo
  - On success: update row WO Status to "DRAFT" with WO number as link
  - On error (bom_not_found): show red inline error "No BOM configured for this part number"

- "+ Add Line" button:
  - Slide-down form: Part Number select (loaded from /api/master/part-numbers?customer_id=<customer_id>), Qty, UOM, Required Date, Customer PO Ref
  - On submit: POST /api/orders/customer/<order_id>/lines
  - After success: refresh lines table

- Loads data via fetch('/api/orders/customer/<order_id>') on DOMContentLoaded
- Dark mode compatible

TASK B — Add Flask template rendering routes to customer_orders_bom.py blueprint

GET /orders/customer-ui          → renders customer_orders_bom/orders.html (endpoint: customer_orders_bom.orders_list)
GET /orders/customer-ui/<order_id> → renders customer_orders_bom/order_detail.html (endpoint: customer_orders_bom.order_detail, passes order_id)

TASK C — Update WorkOrder detail page (in app/templates/work_orders/)
Find the existing WO detail template. Add a new "BOM Information" card/section that shows:
- Die Type: die_code, die_type, profile_code (from wo.die_type_ref)
- Billet Type: billet_code, alloy, diameter_mm (from wo.billet_type_ref)
- BOM Version: version number, created_at (from wo.bom_ref)
- Source Order: order_number link (from wo.customer_order_line.order.order_number)
If die_type_id is None, show grey "Not BOM-driven" badge.
Style: same card style as existing WO detail sections.

TASK D — Update Planning sidebar link
In layout.html, the existing "Customer Orders" link in Planning group at url_for('planning.orders')
Add a second link below it:
<a href="{{ url_for('customer_orders_bom.orders_list') }}"
   class="{% if request.blueprint == 'customer_orders_bom' %}active{% endif %}">
  📋 BOM Orders
</a>
```

---

## Session 5 — APS Integration, Seed Data & End-to-End Verification

### Objective
Update APS ProcessPlan creation to use BOM-resolved die/billet from WO. Add seed data. Verify full flow end-to-end.

### Prompt

```
You are working on FactoryNXT_PY_v2_Extrusion. Sessions 1–4 are complete.
The full BOM data model, services, APIs, and UI screens are implemented.

TASK A — APS Integration: Update ProcessPlan creation to use BOM fields from WorkOrder

Read the existing APS planning service (check app/services/ for any aps_service or planning_service,
and also seed_planning_aps.py to understand the ProcessPlan model and scheduling logic).

Update the ProcessPlan creation logic (wherever process plans are created from work orders):
1. When building a ProcessPlan from a WorkOrder, check if wo.die_type_id is set
2. If set: use wo.die_type_id as the die for this plan (preferred over any calculated value)
3. If set: use wo.billet_type_id as the billet for this plan
4. Add helper function in app/services/bom_service.py:

```python
def get_eligible_machines_for_die(die_type_id: str) -> list:
    """Returns machines compatible with the given die based on machine type/capacity."""
    from app.models import Machine, Die
    die = Die.query.get(die_type_id)
    if not die:
        return []
    return Machine.query.filter_by(is_active=True, status='Idle').all()

def check_billet_availability(billet_type_id: str, required_kg: float) -> dict:
    """Check if enough billet stock is available."""
    from app.models import Billet
    billet = Billet.query.get(billet_type_id)
    if not billet:
        return {"available": False, "reason": "Billet type not found"}
    if billet.status in ('REJECTED', 'CONSUMED'):
        return {"available": False, "reason": f"Billet status is {billet.status}"}
    if required_kg and billet.quantity_kg and billet.quantity_kg < required_kg:
        return {"available": False, "reason": f"Insufficient stock: {billet.quantity_kg}kg available, {required_kg}kg required"}
    return {"available": True, "billet": billet}
```

5. In ProcessPlan creation: after die/billet are resolved from WO BOM:
   - Call check_billet_availability(wo.billet_type_id, wo_bom_billet_weight_kg * wo.quantity)
   - If not available: set ProcessPlan.status = "Blocked", plan_notes = f"BLOCKED: {reason}"
   - Call get_eligible_machines_for_die(wo.die_type_id) and use first eligible machine
   - If no eligible machine: set ProcessPlan.status = "Blocked", plan_notes = "BLOCKED: No compatible press for die"

TASK B — Create seed_master_bom.py

Create a standalone seed script that:
1. Creates 3 Customer records (if not exist, check by customer_code):
   - CUST-001, Apex Profiles Pvt Ltd
   - CUST-002, Delta Systems Ltd
   - CUST-003, Vertex Metals
2. Creates 5 PartNumber records (if not exist):
   - PN-6063-H-100, 6063 alloy hollow profile
   - PN-6063-S-200, 6063 alloy solid profile
   - PN-6082-H-300, 6082 alloy hollow profile
   - PN-6082-S-400, 6082 alloy solid profile
   - PN-7075-H-500, 7075 alloy hollow profile
3. Maps customers to parts:
   - CUST-001: PN-6063-H-100, PN-6063-S-200, PN-6082-H-300
   - CUST-002: PN-6082-H-300, PN-6082-S-400
   - CUST-003: PN-7075-H-500, PN-6063-H-100
4. For each PartNumber, create active PartNumberBOM using first available Die and Billet from DB
5. Create 2 CustomerOrder records with 2–3 CustomerOrderLine each using CUST-001 and CUST-002

Run with: `python seed_master_bom.py`

TASK C — End-to-end verification checklist

Run these checks and fix any issues found:

1. flask db upgrade runs clean (no errors)
2. python seed_master_bom.py runs clean
3. GET /master/customers → page loads, shows seeded customers
4. GET /master/part-numbers → page loads, BOM status badges correct
5. GET /master/boms → page loads, BOM detail card shows die + billet
6. GET /master/customer-part-map → page loads, mapping functional
7. GET /orders/customer-ui → order list loads
8. GET /orders/customer-ui/<order_id> → order detail with lines and BOM status
9. "Create WO" on a line with BOM → WO created with die_type_id and billet_type_id populated
10. "Create WO" on a line WITHOUT BOM → 400 error shown inline, not a crash
11. GET work order detail → "BOM Information" card visible with die + billet
12. APS planning run → ProcessPlans created using BOM die/billet; blocked WOs flagged correctly
13. Sidebar: "Master Data" group visible, all 4 links work
14. Dark mode: all new pages render correctly in dark mode

Fix all issues before closing this session.

TASK D — Update CHANGELOG.md or README.md (if exists)

Add a section:
## Feature: BOM-Driven Work Order Creation
- Customer and Part Number master data management
- Part Number BOM with die and billet mappings
- Customer-Part mapping enforcement
- Auto-resolution of die and billet when creating WOs from customer orders
- APS integration: die/billet availability checks during scheduling
```

---

## Files Created/Modified Summary

| File | Session | Action |
|---|---|---|
| `app/models.py` | S1 | Add 5 models + patch WorkOrder |
| `migrations/versions/xxx_add_customer_part_bom_wo_fields.py` | S1 | Auto-generated |
| `app/services/bom_service.py` | S2 | NEW |
| `app/services/work_order_service.py` | S2 | NEW |
| `app/routes/master_data_bom.py` | S2+S3 | NEW (API + page routes) |
| `app/routes/customer_orders_bom.py` | S2+S4 | NEW (API + page routes) |
| `app/__init__.py` | S2 | Register 2 blueprints |
| `app/templates/layout.html` | S3 | Add Master Data nav-group + BOM Orders link |
| `app/templates/master_data_bom/customers.html` | S3 | NEW |
| `app/templates/master_data_bom/part_numbers.html` | S3 | NEW |
| `app/templates/master_data_bom/boms.html` | S3 | NEW |
| `app/templates/master_data_bom/customer_part_map.html` | S3 | NEW |
| `app/templates/customer_orders_bom/orders.html` | S4 | NEW |
| `app/templates/customer_orders_bom/order_detail.html` | S4 | NEW |
| `app/templates/work_orders/<detail>.html` | S4 | UPDATE: add BOM card |
| `app/services/bom_service.py` | S5 | UPDATE: add APS helpers |
| `seed_master_bom.py` | S5 | NEW |

---

## Session Restart Context Snippet

Paste this at the START of any new Claude Code session to restore context:

```
CONTEXT (FactoryNXT_PY_v2_Extrusion BOM Feature):
This is session [N] of 5 for the BOM-driven Work Order feature.

Completed in prior sessions:
- S1: Models (Customer, PartNumber, CustomerPartNumber, PartNumberBOM, CustomerOrderLine) added to app/models.py; WorkOrder patched with die_type_id, billet_type_id, bom_version_id; migration applied.
- S2: app/services/bom_service.py, app/services/work_order_service.py; API blueprints master_data_bom and customer_orders_bom registered.
- S3: Sidebar updated (Master Data nav-group); templates in app/templates/master_data_bom/.
- S4: Customer Order + WO creation UI in app/templates/customer_orders_bom/; WO detail BOM card added.

Data flow: Customer → CustomerPartNumber → PartNumber → PartNumberBOM → die_type_id + billet_type_id
           CustomerOrder → CustomerOrderLine → [create-wo] → WorkOrder (BOM auto-resolved) → ProcessPlan

Current task for this session: [paste the session prompt below]
```
