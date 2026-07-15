# FactoryNXT — Aluminum Extrusion Digitalization Platform

Manufacturing Execution System (MES) for aluminum extrusion plants, providing advance planning & scheduling, tool shop automation, process line integration, quality traceability, and KPI monitoring with ERP/PLC connectivity.

Built on a Flask 3.0 foundation with PostgreSQL, SQLAlchemy, and Tailwind CSS.

---

## Overview

FactoryNXT orchestrates the complete aluminum extrusion workflow:
- **Advance Planning & Scheduling** — Customer order import, die/billet stock availability, machine availability, schedule optimization, projected shortage detection, plan-vs-actual tracking
- **Tool Shop Automation** — Die lifecycle management (inward → inspection → testing → nitriding → available), ERP auto-posting for inspection/testing/nitriding, die shortage visibility linked to schedule
- **Process Line Integration** — Billet inspection, HLS/pressing/quenching setpoint loading and actual capture from PLC, puller/cutting/stretching sensor data, die oven preheating records
- **Quality & Traceability** — Die/billet/lot traceability, machine parameter history, inspection/test records, operator audit trail, ERP transaction log
- **KPI & Alerts** — OEE, throughput, rejection rate, die lifecycle KPIs, machine downtime, threshold-based alerts, sync failure alerts, planning risk alerts
- **Integrations** — ERP connectors (order import, inspection/test/nitriding posting), PLC connectors (setpoint load, actual capture), signal mapping, integration job monitoring, failed transaction reprocess
- **Administration** — Master data, user/role management, machine master, process parameters, thresholds & rules, audit log

## Features by Module

### 1. Dashboard
Executive overview with plant status, work order summary, machine availability, die availability, active alerts, production bottlenecks, ERP/PLC sync health.

### 2. Planning & Scheduling
- Order import from ERP
- Stock availability check (dies + billets)
- Machine availability aggregation
- Schedule optimizer (greedy algorithm respecting constraints)
- Gantt-like schedule view
- Projected shortages (die/billet)
- Plan vs actual comparison

### 3. Tool Shop
- New die inward from store
- Die inspection workflow + auto ERP posting
- Die testing workflow + auto ERP posting
- Nitriding workflow + auto data capture
- Die status registry (22 statuses)
- Die shortage view linked to schedule

### 4. Process Line
- Billet inspection
- HLS setpoint load + actual capture
- Pressing setpoint load + actual capture
- Quenching automation + temperature trend
- Puller sensor-based capture
- Stretching tension automation
- Final cut auto-length + segregation
- Die oven preheating set/actual capture

### 5. Quality & Traceability
- Lot/batch/die traceability
- Machine parameter history
- Inspection/test records
- Material-based process history
- Operator/action audit trail
- ERP transaction log

### 6. KPI & Alerts
- OEE (Availability × Performance × Quality)
- Throughput / rejection / delays / shortage indicators
- Die lifecycle KPIs (avg cycles, time per stage, rejection rate)
- Machine downtime + alarm summaries
- Threshold-based alerts (configurable rules)
- Sync failure alerts
- Planning risk alerts

### 7. Integrations
- ERP connectors (order import, inspection/test/nitriding posting)
- PLC/machine data connectors (setpoint load, actual capture)
- Tag/signal mapping (PLC signal configuration)
- Sync job monitoring (IntegrationJob list with retry)
- Failed transaction reprocess
- Integration audit logs (ERPTransactionLog)

### 8. Administration
- Master data (plants, materials, machines)
- User/role management
- Configuration (thresholds, machine master, process params)
- Rule engines / thresholds / scheduling parameters
- Reference mappings (PLC signal mapping)
- Audit log

---

## Tech Stack

- **Backend:** Python 3.10+, Flask 3.0, Flask-SQLAlchemy 3.1, Flask-Migrate 4.0
- **Database:** PostgreSQL 15
- **Frontend:** Tailwind CSS (CDN), Jinja2 templates, dark mode support
- **Containerization:** Docker, docker-compose
- **Migration:** Alembic (via Flask-Migrate)

---

## Architecture

```
FactoryNXT/
├── app/
│   ├── __init__.py           # Flask app factory (28 blueprints)
│   ├── config.py             # Configuration (DB, secrets)
│   ├── models.py             # 73 SQLAlchemy models (51 legacy + 22 new)
│   ├── services/             # Business logic layer
│   │   ├── erp_adapter.py    # ERP integration + retry via IntegrationJob
│   │   ├── plc_adapter.py    # PLC integration + signal mapping
│   │   ├── scheduler.py      # Greedy optimizer + shortage computation
│   │   └── kpi_engine.py     # OEE / die-lifetime / shortage KPIs
│   ├── routes/               # Blueprint-based route handlers
│   │   ├── dashboard.py
│   │   ├── planning.py       # NEW: /planning/*
│   │   ├── tool_shop.py      # NEW: /tool-shop/*
│   │   ├── process_line.py   # NEW: /process-line/*
│   │   ├── kpi_alerts.py     # NEW: /kpi-alerts/*
│   │   ├── integrations.py   # Extended: PLC connectors, signal mapping, jobs
│   │   ├── admin.py          # Extended: thresholds, machine master
│   │   └── [21 legacy blueprints preserved for backward compatibility]
│   └── templates/
│       ├── layout.html       # Main shell (sidebar rewritten: 8 modules)
│       ├── dashboard.html    # Refactored with foundry KPIs
│       ├── planning/         # 7 pages
│       ├── tool_shop/        # 8 pages
│       ├── process_line/     # 11 pages
│       ├── kpi_alerts/       # 6 pages
│       └── [legacy templates preserved]
├── migrations/
│   └── versions/
│       └── 8b1c2d3e4f5g_foundry_domain.py  # Consolidation migration (22 new tables)
└── docker-compose.yml
```

### Service Layer

**ERP Adapter** (`app/services/erp_adapter.py`)
- `ERPAdapter.post_inspection(die_inspection)` → create IntegrationJob, post to ERP, log to ERPTransactionLog
- `ERPAdapter.post_test(die_test)` → same pattern
- `ERPAdapter.post_nitriding(nitriding_record)` → same pattern
- `ERPAdapter.import_orders()` → fetch customer orders from ERP, create CustomerOrder rows
- All operations wrap in IntegrationJob for retry capability (max_retries=3)

**PLC Adapter** (`app/services/plc_adapter.py`)
- `PLCAdapter.load_setpoint(machine_name, setpoint_profile)` → load setpoint to machine via PLC
- `PLCAdapter.capture_actuals(machine_name, process_run)` → capture actual values from PLC
- `PLCAdapter.query_signal(machine_name, signal_tag)` → read signal value
- Uses PLCSignalMapping table for tag configuration

**Scheduler** (`app/services/scheduler.py`)
- `ScheduleOptimizer.optimize(constraint_inputs)` → greedy scheduler respecting die/billet/machine availability
- `ScheduleOptimizer.compute_shortages()` → returns projected die/billet shortages linked to ProcessPlan

**KPI Engine** (`app/services/kpi_engine.py`)
- `KPIEngine.compute_oee(machine_id, shift_date)` → Availability × Performance × Quality
- `KPIEngine.compute_die_lifetime()` → aggregates die lifecycle data (cycles, time per stage)
- `KPIEngine.compute_shortage_risk()` → returns planning risk alerts

---

## Database Schema

### BOM-Driven Work Order Creation

New feature enabling customer-part number mappings with automatic die/billet resolution for work orders.

**Key Features:**
- **Customer Master Data**: Manage customers with contact information and approved part numbers
- **Part Number Master**: Define profiles, alloys, weights as production requirements
- **Customer-Part Mapping**: Enforce which parts each customer can order (prevents invalid orders)
- **BOM Management**: Link parts to specific dies and billets with version control
- **Auto-Resolution**: When creating work orders from customer lines, die/billet automatically populated from active BOM
- **APS Integration**: Scheduling respects BOM-assigned dies; checks billet availability before scheduling

**Data Flow:**
```
Customer → CustomerPartNumber (mapping) → PartNumber → PartNumberBOM → die_type_id + billet_type_id
           ↓
    CustomerOrder → CustomerOrderLine → [create-wo] → WorkOrder (auto-resolved BOM fields populated)
                                                   ↓
                                            ProcessPlan (uses BOM die/billet for scheduling)
```

**API Endpoints:**
| Endpoint | Description |
|----------|-------------|
| `GET/POST /api/master/customers` | Customer master data management |
| `GET/POST /api/master/part-numbers` | Part number master data |
| `POST /api/master/customer-part-numbers` | Map customer to approved parts (validates uniqueness) |
| `POST /PUT /api/master/boms` | Manage BOM versions with die/billet assignments |
| `GET/POST /api/orders/customer` | Customer orders with line management |
| `POST /api/orders/customer/<id>/lines/<line_id>` | Create WO from order line (auto-resolves BOM) |

**UI Pages:**
- `/master/customers` — Customers master list
- `/master/part-numbers` — Part numbers with BOM status badges
- `/master/boms` — BOM management with version control
- `/master/customer-part-map` — Customer ↔ Part mapping interface
- `/orders/customer-ui` — BOM-driven customer orders (enhanced planning view)

**Total tables:** 73 (51 legacy SMT/PCB + 22 new foundry domain + 5 new BOM models)

### New Models for BOM Feature:

| Model | Table | Description |
|-------|-------|-------------|
| `Customer` | `customers` | Customer master data with contact info and active status |
| `PartNumber` | `part_numbers` | Part number master with alloy, weight, profile code |
| `CustomerPartNumber` | `customer_part_numbers` | Junction table mapping customers to approved parts (enforces valid orders) |
| `PartNumberBOM` | `part_number_boms` | BOM linking part numbers to dies and billets with version tracking |
| `CustomerOrderLine` | `customer_order_lines` | Line items within customer orders, linked to part numbers |

**Total tables:** 73 (51 legacy SMT/PCB + 22 new foundry domain)

### New Foundry Domain Models (22 tables)

**Core Production:**
- `CustomerOrder` — ERP customer orders (order_number, customer_name, product_profile, alloy, quantity_tons, due_date)
- `ProcessPlan` — Production schedule plans (alloy, profile_shape, scheduled_start/end, status: Draft/Optimized/Released/InProgress/Delayed/Completed)
- `MaterialGrade` — Material grade master (code, alloy_family, density, melting_point)

**Tool Shop:**
- `Die` — Die registry (die_code, profile_code, alloy, supplier, location, status: New/Inspected/TestingPending/TestingPassed/TestingFailed/Rework/NitridingPending/Nitrided/Available/Rejected, life_cycles_total)
- `DieInspection` — Inspection records (dimensions_ok, surface_ok, hardness, erp_posted)
- `DieTest` — Test records (press_force, temperature, profile_quality, result: PASS/FAIL, erp_posted)
- `NitridingRecord` — Nitriding records (furnace_id, start/end_temp, duration_hours, atmosphere, hardness_before/after, erp_posted)

**Material Stock:**
- `Billet` — Billet registry (billet_code, alloy, diameter_mm, length_mm, supplier, lot_number, quantity_kg, status: AVAILABLE/INSPECTED/CONSUMED/REJECTED)
- `BilletInspection` — Inspection records (chemical_composition, temperature, result)

**Process Line:**
- `SetpointProfile` — Process setpoint profiles (process_type: HLS/PRESSING/QUENCHING/STRETCHING/OVEN, alloy, profile_code, parameters: JSON, version)
- `ProcessRun` — Process execution runs (process_type, plan_id, machine_id, operator_id, setpoint_profile_id, billet_id, die_id, started_at, ended_at, status: RUNNING/COMPLETED/FAILED)
- `QuenchRecord` — Quenching records (run_id, quench_type, sensor_temperatures: JSON, start/end_time)
- `CutRecord` — Cutting records (run_id, target_length_mm, actual_length_mm, cut_method: AUTO/MANUAL, sensor_data: JSON, segregation_status)
- `StretchRecord` — Stretching records (run_id, tension_actual, tension_setpoint, position_transducer_reading, pressure_transducer_reading)
- `OvenRecord` — Oven records (run_id, oven_id, set_temperature, actual_temperature, soak_time_minutes)

**KPI & Alerts:**
- `AlertRule` — Alert threshold rules (name, metric, operator: GT/LT/EQ/BETWEEN, threshold_value: JSON, severity)
- `Alert` — Alert instances (rule_id, severity: INFO/WARNING/CRITICAL, title, message, source: DIE/PROCESS_LINE/PLANNING/INTEGRATION/MACHINE, source_id, status: Open/Acknowledged/Closed)
- `KPIRecord` — KPI snapshots (kpi_type: OEE/THROUGHPUT/REJECTION_RATE/DIE_LIFETIME/MACHINE_DOWNTIME/SHORTAGE, machine_id, shift_date, value, unit, details: JSON)

**Integration:**
- `IntegrationJob` — Integration jobs (job_type: ERP_POST_INSPECTION/ERP_POST_TEST/ERP_POST_NITRIDING/ERP_ORDER_IMPORT/PLC_SETPOINT_LOAD/PLC_CAPTURE, status: Pending/Running/Success/Failed/RetryQueued, payload: JSON, result: JSON, retries, max_retries=3, next_retry_at)
- `ERPTransactionLog` — ERP transaction audit log (direction: OUTBOUND/INBOUND, entity_type, entity_id, payload: JSON, erp_response: JSON, status: SUCCESS/FAILED/PENDING)
- `PLCSignalMapping` — PLC signal configuration (machine_name, signal_tag, signal_type: SETPOINT/ACTUAL/ALARM/STATUS, unit, process_type, scale_factor, offset, is_active)

**Traceability:**
- `TraceabilityRecord` — Generic traceability events (entity_type: DIE/BILLET/PROCESS_RUN/ORDER, entity_id, event_type, operator_id, machine_id, data: JSON, occurred_at)

### Migration

**Migration:** `8b1c2d3e4f5g_foundry_domain.py`
- **Revision:** `8b1c2d3e4f5g`
- **Down revision:** `7a42c1b9e2d5` (current head)
- **Tables created:** 22 new foundry domain tables
- **Tables preserved:** All 51 existing SMT/PCB tables untouched

---

## Workflow State Machines

### Die Lifecycle
```
New → Inspected → TestingPending → TestingPassed → NitridingPending → Nitrided → Available
                                          ↓                                    ↑
                                    TestingFailed → Rework ────────────────────┘
                                                                              
                                    (or) Rejected
```

### ProcessPlan Status
```
Draft → Optimized → Released → InProgress → (Delayed) → Completed
```

### IntegrationJob Status
```
Pending → Running → Success
              ↓
           Failed → RetryQueued → Running (retry)
```

### Alert Status
```
Open → Acknowledged → Closed
```

---

## Setup

### Docker (Recommended)

```bash
# Clone repo
git clone <repo-url>
cd FactoryNXT_PY_v2_foundry

# Start PostgreSQL + Flask app
docker-compose up -d

# Flask app runs at http://localhost:5555
# PostgreSQL runs at localhost:5432
```

The `entrypoint.sh` script automatically:
1. Initializes migrations folder if needed
2. Runs `flask db migrate` (auto-generate migration if needed)
3. Runs `flask db upgrade` (apply all migrations)
4. Starts Flask on `0.0.0.0:5555` with debug=True

### Local Development

```bash
# Prerequisites
# - Python 3.10+
# - PostgreSQL 15+

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql+psycopg2://postgres:postgres@localhost:5432/factorynxt"
export SECRET_KEY="your-secret-key-here"
export FLASK_APP=run.py

# Initialize database (if fresh install)
flask db upgrade

# Run app
flask run --host=0.0.0.0 --port=5000
# App runs at http://localhost:5000
```

---

## Database Migration

Database migrations are managed via Flask-Migrate (Alembic wrapper).

```bash
# Apply all pending migrations
flask db upgrade

# Generate new migration after model changes
flask db migrate -m "description of changes"

# Rollback last migration
flask db downgrade -1

# Rollback to specific revision
flask db downgrade <revision-id>

# Show migration history
flask db history
```

**Current migration chain:**
```
f60e6a92c60b (initial) → f4bc0852bb9a (routing builder) → 322b85370ef9 (integrations) → 7a42c1b9e2d5 (WO schedule window) → 8b1c2d3e4f5g (foundry domain)
```

---

## API Endpoints

**Total endpoints:** 212 (43 new + 169 legacy)

### New Endpoints by Module

**Planning & Scheduling** (`/planning/*`)
- `GET /planning` — Overview (orders, stock, availability)
- `GET /planning/orders` — Customer orders list
- `POST /planning/orders/import` — Import orders from ERP
- `GET /planning/stock` — Die + billet availability
- `GET /planning/availability` — Machine availability
- `GET /planning/scheduler` — Gantt schedule view
- `POST /planning/optimize` — Run schedule optimizer
- `GET /planning/shortages` — Projected shortages
- `GET /planning/plan-vs-actual` — Plan vs actual comparison

**Tool Shop** (`/tool-shop/*`)
- `GET /tool-shop` — Dashboard (die registry + workflow pipeline)
- `GET /tool-shop/dies` — Die list with status filter
- `POST /tool-shop/dies/new` — New die inward
- `GET /tool-shop/dies/<id>` — Die detail
- `POST /tool-shop/dies/<id>/inspect` — Record inspection
- `POST /tool-shop/dies/<id>/test` — Record test
- `POST /tool-shop/dies/<id>/nitride` — Record nitriding
- `GET /tool-shop/inspections` — Inspection records
- `GET /tool-shop/tests` — Test records
- `GET /tool-shop/nitriding` — Nitriding records
- `GET /tool-shop/shortages` — Die shortages

**Process Line** (`/process-line/*`)
- `GET /process-line` — Floor overview (station cards)
- `GET /process-line/billet-inspection` — Billet inspection
- `POST /process-line/billet-inspection/new` — Record billet inspection
- `GET /process-line/hls` — HLS setpoint + capture
- `POST /process-line/hls/load-setpoint` — Load setpoint to PLC
- `POST /process-line/hls/<run_id>/capture` — Capture actuals from PLC
- `GET /process-line/pressing` — Pressing setpoint + capture
- `GET /process-line/quenching` — Quenching automation
- `GET /process-line/quenching/<run_id>/trend` — Temperature trend
- `GET /process-line/puller` — Puller sensor capture
- `GET /process-line/cutting` — Cutting auto-length
- `GET /process-line/stretching` — Stretching tension
- `GET /process-line/final-cut` — Final cut + segregation
- `GET /process-line/die-oven` — Die oven preheating

**KPI & Alerts** (`/kpi-alerts/*`)
- `GET /kpi-alerts` — KPI dashboard
- `GET /kpi-alerts/oee` — Machine-wise OEE
- `GET /kpi-alerts/die-lifecycle` — Die lifecycle analytics
- `GET /kpi-alerts/downtime` — Downtime events
- `GET /kpi-alerts/alerts` — Alerts list
- `POST /kpi-alerts/alerts/<id>/acknowledge` — Acknowledge alert
- `POST /kpi-alerts/alerts/<id>/close` — Close alert
- `GET /kpi-alerts/rules` — Alert rules
- `POST /kpi-alerts/rules/new` — Create alert rule

**Integrations** (Extended)
- `GET /integrations/plc-connectors` — PLC connector list
- `GET /integrations/signal-mapping` — Signal mapping CRUD
- `GET /integrations/jobs` — Integration jobs list
- `POST /integrations/jobs/<id>/retry` — Retry failed job

**Administration** (Extended)
- `GET /admin/thresholds` — Alert threshold management
- `GET /admin/machine-master` — Machine master data
- `GET /admin/process-params` — Process parameters

---

## Sidebar Navigation

**Before refactor:** 21 top-level items (16 nav-groups + 4 loose items + dashboard)
**After refactor:** 8 top-level modules (1 dashboard + 7 nav-groups)

1. **Dashboard** (single link)
2. **Planning & Scheduling** (7 children: overview, orders, stock, availability, scheduler, shortages, plan-vs-actual)
3. **Tool Shop** (7 children: overview, die registry, new die, inspections, tests, nitriding, shortages)
4. **Process Line** (9 children: floor overview, billet inspection, HLS, pressing, quenching, puller/cutting, stretching, final cut, die oven)
5. **Quality & Traceability** (6 children: traceability search, material trace, genealogy, defects, inspection records, audit trail)
6. **KPI & Alerts** (6 children: overview, OEE, die lifecycle, downtime, alerts, rules)
7. **Integrations** (7 children: hub, ERP connectors, PLC connectors, signal mapping, jobs, webhooks, API docs)
8. **Administration** (8 children: overview, plants, users, roles, machine master, process params, thresholds, audit log)

**Obsolete items removed from sidebar** (backend preserved for backward compatibility):
- Work Orders, Production, Operations, Stations, Scheduling, Inventory, Kitting, SMT Materials, Routing, Routing Builder, NCR, Quality, OEE, PCB, Machines, Maintenance, Traceability, Genealogy

---

## Integration Points

### ERP Integration

**Adapter:** `app/services/erp_adapter.py` (currently uses generic mock)

**Operations:**
- `import_orders()` — Fetch customer orders from ERP
- `post_inspection(die_inspection)` — Post die inspection result to ERP
- `post_test(die_test)` — Post die test result to ERP
- `post_nitriding(nitriding_record)` — Post nitriding record to ERP

**Flow:**
1. User action triggers service method
2. Create IntegrationJob (status: Pending)
3. Mark IntegrationJob as Running
4. Call ERP API (mock/real)
5. Log to ERPTransactionLog (direction: OUTBOUND, entity_type, payload, erp_response, status)
6. On success: mark IntegrationJob as Success
7. On failure: mark IntegrationJob as Failed, set next_retry_at, increment retries
8. Background job or manual retry attempts failed jobs

**Customer input needed:**
- ERP API endpoint, authentication method, payload schema
- Field mapping between FactoryNXT models and ERP entities
- Error codes and retry logic

### PLC Integration

**Adapter:** `app/services/plc_adapter.py` (currently uses generic mock)

**Operations:**
- `load_setpoint(machine_name, setpoint_profile)` — Load setpoint to machine
- `capture_actuals(machine_name, process_run)` — Capture actual values from PLC
- `query_signal(machine_name, signal_tag)` — Read signal value

**Signal Mapping:**
- `PLCSignalMapping` table stores: machine_name, signal_tag, signal_type (SETPOINT/ACTUAL/ALARM/STATUS), unit, process_type, scale_factor, offset, is_active
- Used to translate between PLC raw values and engineering units

**Flow:**
1. User action triggers service method
2. Look up PLCSignalMapping for machine/process
3. Call PLC API (mock/real)
4. Create IntegrationJob for audit trail
5. On success: update ProcessRun with captured values
6. On failure: mark IntegrationJob as Failed, trigger Alert

**Customer input needed:**
- PLC protocol (OPC-UA / Modbus / MQTT)
- Hardware vendor, API/SDK
- Signal list with tags, units, scaling formulas
- Connection parameters (IP, port, credentials)

---

## Assumptions & Customer Input Required

### Immediate (Blocking)
1. **ERP API** — Customer to provide ERP API documentation (endpoint, auth, payload shape)
2. **PLC Hardware** — Customer to provide PLC protocol (OPC-UA / Modbus / MQTT), vendor, API/SDK
3. **Sensor Vendors** — Customer to provide sensor vendors, calibration logic, scaling formulas
4. **Die Workflow Statuses** — Confirm match: New → Inspected → TestingPending → TestingPassed → NitridingPending → Nitrided → Available | Rework | Rejected | TestingFailed
5. **Billet Inspection Criteria** — Finalize inspection form fields (chemical_composition, temperature, result)

### Short-term (Post-deployment)
1. **Gantt Scheduler** — Replace static SVG with interactive JS library (dhtmlxGantt, FullCalendar)
2. **Real-time PLC Data** — Add WebSockets or background jobs for live dashboard updates
3. **KPI Visualizations** — Add Chart.js or similar for interactive time-series charts
4. **Mobile-responsive** — Optimize shop floor screens for tablets/phones
5. **Barcode/RFID** — Integrate scanning for die/billet tracking

### Assumptions Made
- ERP is source of truth for customer orders; FactoryNXT posts back inspection/test/nitriding results
- PLC is source of truth for real-time machine/process/sensor values; FactoryNXT orchestrates setpoint load/capture
- FactoryNXT acts as orchestration, traceability, optimization, and monitoring layer (not data origin)
- All integration operations are auditable (IntegrationJob + ERPTransactionLog)
- Retry logic for failed integrations (max_retries=3, exponential backoff)

---

## Project Status

**Implementation:** ✓ COMPLETE  
**Verification:** ✓ PASSED  
**Deployment:** ✓ READY (pending customer ERP/PLC hardware details)

**Commit:** `a40ffec` — "feat: refactor SMT/PCB MES to Aluminum Extrusion digitalization platform"

**Files:**
- 46 new files created
- 7 files modified
- 0 files deleted (backward compatibility preserved)
- 6,637 lines added, 680 lines removed

**Documentation:**
- `REFACTOR_PLAN.md` — Domain architecture mapping
- `ENDPOINT_CONTRACT.md` — Backend/frontend endpoint contract
- `COMMIT_MSG.txt` — Detailed commit message

---

## License

[Add your license here — MIT, Apache 2.0, Proprietary, etc.]

---

## Contact

[Add contact information, team name, or support email]

---

**Version:** 2.0 (Foundry)  
**Last updated:** 2026-06-30  
**Flask version:** 3.0.0  
**Python version:** 3.10+