# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.5.0] - 2026-07-15

### Added

#### BOM-Driven Work Order Creation Feature (Sessions S1-S5)

**New Models:**
- `Customer` — Customer master data with contact information and active status flags
- `PartNumber` — Part number master with alloy, weight, profile code specifications
- `CustomerPartNumber` — Junction table enforcing customer-part mappings (prevents invalid orders)
- `PartNumberBOM` — Bill of Materials linking parts to dies/billets with version control
- `CustomerOrderLine` — Line items within customer orders linked to part numbers

**New Services:**
- `app/services/bom_service.py` — Core BOM resolution logic:
  - `get_active_bom(part_number_id)` — Retrieve most recent active BOM for a part number
  - `validate_part_for_customer(customer_id, part_number_id)` — Validate customer-part mapping exists
  - `resolve_bom_for_wo(part_number_id)` — Auto-resolve die/billet when creating work orders
  - `get_eligible_machines_for_die(die_type_id)` — Find machines compatible with specific die (APS integration)
  - `check_billet_availability(billet_type_id, required_kg)` — Check stock availability for production runs

**API Endpoints:**
- `GET/POST /api/master/customers` — Customer master data CRUD operations
- `GET/POST /api/master/part-numbers` — Part number master management
- `POST /api/master/customer-part-numbers` — Create customer-part mappings (409 on duplicate)
- `DELETE /api/master/customer-part-numbers/<id>` — Soft delete customer-part mapping
- `GET/POST/PUT /api/master/boms` — BOM version management with auto-deactivation of old versions
- `POST /api/master/boms/<id>/activate` — Activate specific BOM, deactivate others for same part
- `GET/POST /api/orders/customer` — Customer orders list and creation
- `POST /api/orders/customer/<order_id>/lines` — Add order line (validates customer-part mapping)
- `POST /api/orders/customer/<order_id>/lines/<line_id>` — Create WO from line with auto-BOM resolution
- `POST /api/orders/customer/<order_id>/create-all-wo` — Bulk create WOs for all OPEN lines

**UI Pages:**
- `/master/customers` — Customers master list with modal forms, inline edit
- `/master/part-numbers` — Part numbers with BOM status badges (green "BOM Ready" / red "No BOM")
- `/master/boms` — BOM management interface with version history and activation controls
- `/master/customer-part-map` — Two-panel customer ↔ part mapping UI
- `/orders/customer-ui` — Enhanced order list with "Create All WOs" button
- `/orders/customer-ui/<order_id>` — Order detail with line-level BOM status, inline WO creation

**APS Integration:**
- Updated `app/services/aps_engine.py` to respect BOM fields from WorkOrders:
  - When creating ProcessPlans, checks for `wo.die_type_id` and `wo.billet_type_id` first
  - Uses exact die/billet assigned in PartNumberBOM when present (BOM-driven WOs)
  - Falls back to alloy/profile-based matching for legacy non-BOM WorkOrders
  - Checks billet availability before scheduling; blocks if insufficient stock
  - Validates machine compatibility with specified die

**Seed Data:**
- `seed_master_bom.py` — Standalone script populating sample BOM master data:
  - 3 Customers (Apex Profiles, Delta Systems, Vertex Metals)
  - 5 Part Numbers across alloys 6063, 6082, 7075
  - Customer-part mappings enforcing approved parts per customer
  - Active BOMs for each part number with die/billet assignments
  - Sample orders (CO-2026-100, CO-2026-101) with order lines

**Database Migration:**
- `migrations/versions/20260715_add_customer_part_bom_wo_fields.py` — Adds all new tables and WorkOrder BOM fields:
  - New columns on `work_orders`: `customer_order_line_id`, `part_number_id`, `die_type_id`, `billet_type_id`, `bom_version_id`

**Documentation:**
- `HANDOVER_S1.md` through `HANDOVER_S5.md` — Session-by-session handover documentation
- Updated README.md with BOM feature overview and API documentation
- buildplan.md — Detailed 5-session implementation plan (reference)

### Changed

- WorkOrder model extended with BOM relationships for traceability from WO → Die, Billet, PartNumberBOM, CustomerOrderLine
- Sidebar navigation updated: Added "Master Data" section with links to Customers, Part Numbers, BOMs, Mapping; Enhanced Planning group with "📋 BOM Orders" link

### Fixed

- Template rendering routes fixed in both blueprints (removed redundant `/master/` prefix from page routes)
- Route path duplication resolved for customer_orders_bom blueprint endpoints

---

## [2.4.0] - 2026-07-11

### Added

#### Aluminum Extrusion Foundry Domain Migration

Complete domain refactor mapping SMT/PCB MES to aluminum extrusion manufacturing:

**New Domain Models (Foundry):**
- Core Production: `CustomerOrder`, `ProcessPlan`, `MaterialGrade`
- Tool Shop: `Die`, `DieInspection`, `DieTest`, `NitridingRecord` with 22 die statuses
- Material Stock: `Billet`, `BilletInspection` with availability tracking
- Process Line: `SetpointProfile`, `ProcessRun`, `QuenchRecord`, `CutRecord`, `StretchRecord`, `OvenRecord`
- KPI & Alerts: `AlertRule`, `Alert`, `KPIRecord` (OEE, throughput, rejection rate)
- Integration: `IntegrationJob`, `ERPTransactionLog`, `PLCSignalMapping`
- Traceability: `TraceabilityRecord`

**APS Engine:**
- Advanced planning system with finite-capacity scheduling
- Greedy deterministic scheduler respecting machine/die/billet/shift/maintenance constraints
- Auto-scheduler with versioning, locking, and constraint annotations
- Availability resolver for machines, dies, billets based on status filtering

**New Features:**
- Die lifecycle management (22 statuses from New → Inspected → Testing → Nitriding → Available)
- Billet stock tracking with quantity_kg and availability status
- Process setpoint profiles per alloy/profile combination
- PLC signal mapping for automated data capture
- KPI dashboards: OEE, throughput, rejection rate, die lifetime, machine downtime

**Documentation:**
- `APS_IMPLEMENTATION_SUMMARY.md` — APS architecture and algorithm details
- `ENDPOINT_CONTRACT.md` — API endpoint specifications
- `DEMO_MODE_DESIGN.md` — Demo mode for testing without ERP/PLC connectivity
- `REFACTOR_PLAN.md` — Domain mapping from SMT to extrusion

### Changed

- Refactored existing SMT/PCB domain models to aluminum extrusion terminology
- Updated all 73 database tables (51 legacy preserved, 22 new foundry domain)
- Migration: `8b1c2d3e4f5g_foundry_domain.py` adds new tables without breaking existing data

---

## [2.0.0] - 2026-07-01

### Changed

**Major Version Bump:** Complete platform refactor from SMT/PCB MES to Aluminum Extrusion digitalization platform

---

## [1.x.x] - Legacy Versions

Earlier versions of the FactoryNXT SMT/PCB MES system. See git history for details.
