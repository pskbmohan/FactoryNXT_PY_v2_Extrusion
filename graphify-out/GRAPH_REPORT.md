# FactoryNXT_PY_v2_Extrusion — Structural Knowledge Graph

## Repository Overview

FactoryNXT is a **production-grade Manufacturing Execution System (MES)** for aluminum extrusion plants, built on a **Flask 3.0 + SQLAlchemy + PostgreSQL** backend with a Jinja2/Tailwind CSS server-rendered frontend. The repository is ~80 Python files, ~105 domain models, ~39 blueprints, and 254 templates — the result of sustained feature build-out (extrusion core, tool shop, APS scheduling, quality/traceability, integrations). It is deployed via Docker/docker-compose, uses Alembic for migrations, and ships with an auto-seeding startup path that guarantees every screen has data on first launch. Maturity: **production MES with a demo/seed layer**.

## What the repo does

- MES for **aluminum extrusion**: billet → HLS → press → quench → puller → stretch → cut → furnace → finishing → packaging → shipment.
- **APS (Advanced Planning & Scheduling)** engine — finite-capacity deterministic greedy scheduler with 30 min slot resolution, versioning, constraint annotations, lock/preserve across replans, shortage projection.
- **Visual routing builder** (V2) alongside legacy `RoutingStep` — drag-and-drop-like DAG of routing steps with connections.
- **Tool shop automation** — die inward → inspection → testing → nitriding → available, with 22 die statuses and ERP auto-posting.
- **Quality & traceability** — inspection plans, NCR/CAPA, PPAP, genealogy events, traceability records, operator certification & electronic signature, lot/die/billet trace.
- **ERP & PLC integration** — adapters for Lighthouse V15 ERP (Oracle) and OPC-UA/Modbus/MQTT PLCs, both wrapped in `IntegrationJob` for retry/audit; Wattmon energy-meter upload (216 columns).
- **KPI engine** — OEE, die-life, shortage risk, throughput; persisted to `KPIRecord`.
- **Demo/reference** — seeded plant master data, simulated sensor data, process-line simulator for offline UI.

## Top-Level Architecture

- **App factory pattern** in `app/__init__.py :: create_app()`.
- **~39 Flask blueprints** registered in `app/__init__.py` lines 17-105; some use `url_prefix`, some hardcode routes — **inconsistency flagged**.
- **~105 SQLAlchemy models** split across **3 files**: `models.py` (94 classes, 1724 lines), `models_aps.py` (6 classes, 188 lines), `models_routing.py` (5 classes, 175 lines).
- **6 services** under `app/services/`: `aps_engine`, `erp_adapter`, `plc_adapter`, `scheduler`, `kpi_engine`, `process_simulator`.
- **Jinja2 templates** under `app/templates/[module]/` — 254 HTML templates, no SPA framework.
- **Migrations** under `migrations/versions/` (Alembic) + `_archived_versions/`.
- **Seed layer** under `scripts/seed_data.py` (2061 lines) — invoked at startup by `__init__.py` lines 119-188; **do NOT remove**.
- **Standalone planning seed** `seed_planning_aps.py` (also registered as `flask seed-planning` CLI command).

## Module Inventory

| Module path | Purpose | File count | Key models |
|---|---|---|---|
| `app/models.py` | Core domain models (all legacy + extrusion add-on) | 1 | 94 classes, see Model Inventory |
| `app/models_aps.py` | APS scheduling-domain models (versioning, entries, constraints, events) | 1 | `ApsScheduleVersion`, `ApsScheduleEntry`, `ApsConstraintLog`, `ApsScheduleEvent` |
| `app/models_routing.py` | V2 visual routing builder models | 1 | `RoutingMaster`, `RoutingStepV2`, `RoutingConnection`, `RoutingProductAssignment`, `WorkOrderRoutingSnapshot` |
| `app/routes/` | Blueprint route handlers | 39 | — |
| `app/services/` | Application services | 6 | — |
| `app/templates/` | Jinja2 HTML templates | 254 | — |
| `scripts/` | Seed data + utilities | 4 | `seed_data.py` (2061 lines) |
| `migrations/` | Alembic migrations | ~15 | — |
| `tests/` | pytest tests | 5 | — |
| `run.py` | Entry point: `from app import create_app; create_app().run()` | 1 | — |
| `seed_planning_aps.py` | APS planning-side seed data | 1 | — |

## Entry Points

- **`run.py`** — WSGI/dev entry point. Calls `create_app()` and runs Flask's dev server.
- **`app/__init__.py :: create_app()`** — app factory. Initializes `db`, `migrate`, imports all routes, registers blueprints, runs auto-seed (lines 119-188).
- **`Dockerfile` + `entrypoint.sh` + `docker-compose.yml`** — containerized deployment.
- **`flask seed-planning`** — CLI command for APS-side seed.

## Model Inventory (grouped by domain)

### Extrusion Core — Equipment
| Model | File | Lines |
|---|---|---|
| `Line` | models.py | 7 |
| `Machine` | models.py | 13 |
| `MachineResourceMapping` | models.py | 33 |
| `Alarm` | models.py | 11 |
| `Station` | models.py | 11 |
| `Die` | models.py | 38 |
| `DieInspection` | models.py | 15 |
| `DieTest` | models.py | 16 |
| `NitridingRecord` | models.py | 17 |
| `DieFurnaceLog` | models.py | 14 |
| `DieRepairRecord` | models.py | 13 |
| `Billet` | models.py | 17 |
| `BilletInspection` | models.py | 13 |
| `Furnace` | models.py | 14 |
| `HeatTreatmentProgram` | models.py | 12 |
| `FurnaceSession` | models.py | 25 |

### Extrusion Core — Process
| Model | File | Lines |
|---|---|---|
| `SetpointProfile` | models.py | 13 |
| `ProcessRun` | models.py | 24 |
| `QuenchRecord` | models.py | 13 |
| `CutRecord` | models.py | 15 |
| `StretchRecord` | models.py | 13 |
| `OvenRecord` | models.py | 13 |
| `ProcessPlan` | models.py | 24 |
| `FinishingProcessType` | models.py | 10 |
| `FinishingOrder` | models.py | 24 |

### Extrusion Core — Quality
| Model | File | Lines |
|---|---|---|
| `InspectionPlan` | models.py | 19 |
| `NCR` | models.py | 17 |
| `Capa` | models.py | 17 |
| `DefectRecord` | models.py | 15 |
| `RepairRecord` | models.py | 19 |
| `GoldenBoard` | models.py | 12 |
| `PpapRecord` | models.py | 13 |
| `TestResult` | models.py | 13 |

### Extrusion Core — Production
| Model | File | Lines |
|---|---|---|
| `WorkOrder` | models.py | 22 |
| `WorkOrderResource` | models.py | 28 |
| `SerialNumber` | models.py | 13 |
| `OperationTransaction` | models.py | 19 |
| `CustomerOrder` | models.py | 19 |
| `ProductionSchedule` | models.py | 19 |
| `ShiftCalendar` | models.py | 11 |
| `PackagingSpec` | models.py | 12 |
| `PackagingOrder` | models.py | 21 |
| `Shipment` | models.py | 18 |
| `ShipmentLine` | models.py | 32 |

### Extrusion Core — Material
| Model | File | Lines |
|---|---|---|
| `MaterialGrade` | models.py | 11 |
| `RawMaterialType` | models.py | 9 |
| `AlloyComposition` | models.py | 10 |
| `MaterialReceipt` | models.py | 25 |
| `Container` | models.py | 17 |
| `ContainerWeighEvent` | models.py | 19 |
| `ContainerMovement` | models.py | 15 |
| `CoatingColor` | models.py | 10 |
| `CoatingScheduleEntry` | models.py | 21 |

### Extrusion Core — Traceability & Audit
| Model | File | Lines |
|---|---|---|
| `GenealogyEvent` | models.py | 21 |
| `UnitHistory` | models.py | 13 |
| `TraceabilityRecord` | models.py | 15 |
| `AuditLog` | models.py | 17 |
| `OperatorCertification` | models.py | 12 |
| `ElectronicSignature` | models.py | 11 |

### Extrusion Core — Integration
| Model | File | Lines |
|---|---|---|
| `Integration` | models.py | 10 |
| `IntegrationJob` | models.py | 18 |
| `ErpSyncLog` | models.py | 11 |
| `ERPTransactionLog` | models.py | 15 |
| `PLCSignalMapping` | models.py | 15 |
| `Webhook` | models.py | 12 |
| `ApiKey` | models.py | 19 |
| `WattmonUpload` | models.py | 321 |
| `WattmonReading` | models.py | 35 |

### Extrusion Core — KPI / Alert
| Model | File | Lines |
|---|---|---|
| `AlertRule` | models.py | 13 |
| `Alert` | models.py | 21 |
| `KPIRecord` | models.py | 14 |
| `OeeSnapshot` | models.py | 23 |
| `DowntimeEvent` | models.py | 13 |

### Extrusion Core — Admin / User / Misc
| Model | File | Lines |
|---|---|---|
| `Plant` | models.py | 9 |
| `Role` | models.py | 8 |
| `UserProfile` | models.py | 16 |
| `BOMItem` | models.py | 10 |
| `Kit` | models.py | 14 |
| `InventoryLocation` | models.py | 10 |
| `InventoryItem` | models.py | 23 |
| `PmSchedule` | models.py | 13 |
| `MaintenanceLog` | models.py | 14 |
| `CalibrationRecord` | models.py | 13 |
| `Stencil` | models.py | 15 |
| `CostPriceConfig` | models.py | 23 |
| `BurnInSession` | models.py | 12 |
| `RoutingStep` | models.py | 14 |

### Extrusion Add-on — APS (`models_aps.py`)
| Model | File | Lines |
|---|---|---|
| `ApsScheduleVersion` | models_aps.py | 26 |
| `ApsScheduleEntry` | models_aps.py | 41 |
| `ApsConstraintLog` | models_aps.py | 22 |
| `ApsScheduleEvent` | models_aps.py | ~17 |

### Routing (`models_routing.py`)
| Model | File | Lines |
|---|---|---|
| `RoutingMaster` | models_routing.py | 42 |
| `RoutingStepV2` | models_routing.py | 44 |
| `RoutingConnection` | models_routing.py | 18 |
| `RoutingProductAssignment` | models_routing.py | 24 |
| `WorkOrderRoutingSnapshot` | models_routing.py | ~37 |

### Legacy SMT/PCB (coexists from earlier product lineage)
| Model | File | Lines |
|---|---|---|
| `FeederReel` | models.py | 15 |
| `SolderPasteLot` | models.py | 15 |
| `SmtLine` | models.py | 10 |
| `PcbPanel` | models.py | 12 |
| `PcbBoard` | models.py | 14 |

---

## Service / Engine Inventory

| Service | File | Lines | Responsibility |
|---|---|---|---|
| `aps_engine` | `app/services/aps_engine.py` | 1300 | Finite-capacity deterministic scheduler; versioned schedule with lock/preserve on replan; availability resolver (machines/dies/billets); KPI + shortage projection; constraint annotation (FEASIBLE / INFEASIBLE); 30-min slot snapping; shift resolution. |
| `erp_adapter` | `app/services/erp_adapter.py` | 317 | Mock adapter to Lighthouse V15 (Oracle). Wraps `post_inspection`, `post_test`, `post_nitriding`, `import_orders` in `IntegrationJob`; writes `ERPTransactionLog`. Replace `_call_erp` with real bridge. |
| `plc_adapter` | `app/services/plc_adapter.py` | 151 | Mock OPC-UA/Modbus/MQTT façade. Wraps setpoint-load and actual-capture commands in `IntegrationJob`. Selected driver would come from `PLCSignalMapping` in production. |
| `kpi_engine` | `app/services/kpi_engine.py` | 332 | Aggregates OEE, die-life, shortage risk; reads `ProcessRun` + `OeeSnapshot`; writes `KPIRecord`. |
| `scheduler` (`ScheduleOptimizer`) | `app/services/scheduler.py` | 239 | Simple greedy scheduler (stateless CO → ProcessPlan path). Used by legacy planning screen; superseded by `aps_engine` for full APS. |
| `process_simulator` | `app/services/process_simulator.py` | 240 | Deterministic live-looking sensor values for HLS/Press/Quench/Puller/Stretch/Cut/Oven when no PLC attached. |

## Hub Files / High Blast Radius List

| File | Why high blast radius |
|---|---|
| `app/models.py` | **94 classes / 1724 lines**. Imported by every route, every service, seeds, tests. Any column change ripples across migrations, forms, templates, APS engine, simulators. **Highest blast radius in repo.** |
| `app/__init__.py` | App factory + blueprint registration (40 registrations) + auto-seed. Adding/removing a blueprint here affects URL space. Auto-seed block is order-sensitive. |
| `app/models_aps.py` | APS schedule versioning — changes affect `aps_engine.py`, `routes/aps.py`, `seed_planning_aps.py`, and `scripts/seed_data.py::seed_aps_data`. |
| `app/models_routing.py` | V2 visual routing; consumed by `routes/routing_builder.py` AND `aps_engine.py` (APS reads `RoutingStepV2` for constraint validation). |
| `app/services/aps_engine.py` | ~1300 lines, deterministic scheduler — touch only with deep understanding of constraint annotations and lock semantics. |
| `scripts/seed_data.py` | 2061 lines, **invoked at every startup** (lines 119-188 of `__init__.py`). Mutations affect demo data and first-run behavior. |
| `app/routes/aps.py` | 891 lines — page views + JSON API combined in one file. |
| `app/routes/planning.py` | 867 lines — large single-page planning surface. |
| `app/routes/integrations.py` | 801 lines — ERP/PLC job list, retry, reprocess, audit log. |
| `app/routes/process_line.py` | 670 lines — one route file per extrusion station. |

## Safe to Edit

- **Route files** for single-module changes (each route maps cleanly to one template directory).
- **Templates** under `app/templates/[module]/` — localized to one blueprint (with the caveat: shared `layout.html`, `layout-wo-side-bar.html`).
- **`app/services/process_simulator.py`** — isolated, no persistent state, returns dicts.
- **`app/services/plc_adapter.py`** — isolated façade.
- **Individual seed functions** in `scripts/seed_data.py` (if you don't change the calling order in `__init__.py`).

## Edit with Caution

- **`app/models.py`** — touch anything else that imports from it (all routes, all services, all seed functions, tests, migrations).
- **`app/__init__.py`** — affects blueprint registration AND the startup seed order. Do NOT remove the auto-seed block; do NOT reorder the seed function calls without checking dependencies (e.g., `seed_dies_and_workflow` must run before `seed_die_lifecycle_extended`).
- **`app/services/aps_engine.py`** — deterministic scheduling is delicate; changes can silently alter schedule outputs. Always run `tests/test_aps_engine.py` after.
- **`app/models_routing.py` / `app/models_aps.py`** — shared across route + engine layer, needs migrations.
- **`scripts/seed_data.py` top-level sequence** — order of seed functions matters; dependencies flow downstream.

## Workflows Implemented (state machines)

- **WorkOrder lifecycle**: `DRAFT` → `RELEASED` → `RUNNING` → `COMPLETED` | `CANCELLED`. (Enforced in `routes/operations.py`.)
- **Die lifecycle**: `New` → `Inspected` → `Testing` → `Nitrided` → `Available` (plus 17 other statuses = 22 total — see `routes/tool_shop.py`, `DIE_READY_STATUSES` set in `aps_engine.py`).
- **Routing revision**: `DRAFT` → `RELEASED` → `OBSOLETE`. (In `routes/routing_builder.py`.)
- **Alert lifecycle**: `Open` → `Acknowledged` → `Closed`. (In `models.py:938`, `routes/kpi_alerts.py`.)
- **IntegrationJob**: `Pending` → `Running` → `Success` | `Failed` → `RetryQueued`. (In `models.py:967`, `routes/integrations.py`.)
- **Billet status (partial)**: `AVAILABLE` → `INSPECTED` (in `process_line.py` + `planning.py`).
- **ProcessRun status (partial)**: `RUNNING` → `COMPLETED` | `FAILED` (in `models.py:849`).
- **WattmonUpload status (partial)**: `SUCCESS` | `FAILED` | `PENDING` (in `models.py:989`).
- **CustomerOrder status (partial)**: `DRAFT` → `CONFIRMED` → (`COMPLETED` | `CANCELLED`) (in `aps_engine.py`).

## API Boundaries

Flask blueprints, mostly REST-like. Some use `url_prefix`:
- `/auth`, `/api`, `/integrations`, `/docs`, `/genealogy`, `/kitting`, `/maintenance`, `/oee`, `/pcb`, `/quality/ext`, `/scheduling`, `/stations`, `/users`, `/production`, `/aps`, `/aps/resource`.

Others hardcode routes at `/` via `url_for` conventions (`/work_orders`, `/routing/builder`, `/tool_shop`, etc.).

**Inconsistency flagged**: half the blueprints use `url_prefix`, the other half hardcode `@bp.route("/…")`. Not blocking, but a future refactor target.

Two APS blueprints from the same file: `aps_page_bp` (HTML views, prefix `/aps`) and `aps_resource_bp` (JSON API, prefix `/aps/resource`). (inferred: the split keeps endpoint names distinct — `aps.cockpit` vs `aps_resource.list_mappings`.)

## Uncertain / Inferred Relationships

- **V2 visual routing vs legacy `RoutingStep`**: Both coexist. `RoutingStepV2` (in `models_routing.py`) powers the new builder UI; `RoutingStep` (in `models.py` line 79) is still referenced by `ProcessPlan`/operation execution. **Integration gap (inferred)**: the APS engine reads `RoutingStepV2` for constraint validation (`aps_engine.py` imports `RoutingStepV2`), but the operation-execution path in `routes/operations.py` appears to read the legacy `RoutingStep`. The bridge between V2 builder output and runtime execution is unclear.
- **Wattmon upload schema** (216 columns on `WattmonUpload`, 321 lines): energy meter integration, purpose partially inferred from migration names (async status, EAV schema). Likely a recent add-on; not all columns are exercised by seed data.
- **Feature overlap across blueprints (inferred)**: `maintenance` + `tool_shop` + `dies` all touch die lifecycle; `quality_ext` + `ncr` + `inspection_plans` overlap on quality records; `material_receipt` + `containers` + `inventory` all deal with stock. This is duplication or split-domain modeling, not a bug.
- **APS vs legacy scheduling**: both `services/scheduler.py` (`ScheduleOptimizer`) and `services/aps_engine.py` (`ApsEngine`) exist. They serve different surfaces (`routes/planning.py` vs `routes/aps.py` + `routes/scheduling.py`). Coexistence appears intentional but adds maintenance burden.
- **Auto-seed is invoked at every startup** — not just first run. The `try/except` silently swallows errors, so a failing seed does not crash the app (but silently leaves screens empty).

## Session Memory

> Paste the block below verbatim into a future Claude Code session's prompt before opening any file.

---

### Session Memory: FactoryNXT_PY_v2_Extrusion

**Repo role:** Production MES (Manufacturing Execution System) for aluminum extrusion plants. Python (NOT TypeScript). Reference source — we extract patterns (domain modeling, Flask app factory, APS scheduling, state machines, seed-data ergonomics), not copy code verbatim.

**Tech stack:**
- Backend: Python 3.10+ / Flask 3.0 / Flask-SQLAlchemy 3.1 / Flask-Migrate 4.0 / PostgreSQL 15
- Frontend: Jinja2 + Tailwind CSS (CDN) — server-rendered, no SPA framework
- Containerization: Docker + docker-compose + Alembic migrations
- Services: 6 under `app/services/` (`aps_engine`, `erp_adapter`, `plc_adapter`, `scheduler`, `kpi_engine`, `process_simulator`)

**Model layout (105 classes across 3 files):**
- `app/models.py` — 94 classes / 1724 lines. **Highest blast radius.** Equipment, process, quality, production, material, traceability, integration, admin, SMT-PCB legacy, plus extrusion extensions (die, billet, furnace, finishing, logistics, coating, containers, Wattmon).
- `app/models_aps.py` — 6 classes / 188 lines. APS versioning: `ApsScheduleVersion`, `ApsScheduleEntry`, `ApsConstraintLog`, `ApsScheduleEvent`.
- `app/models_routing.py` — 5 classes / 175 lines. V2 visual routing: `RoutingMaster`, `RoutingStepV2`, `RoutingConnection`, `RoutingProductAssignment`, `WorkOrderRoutingSnapshot`.
- Coexistence note: `RoutingStep` (legacy) and `RoutingStepV2` (V2 builder) both exist; the operation execution engine reads the legacy one.

**Key services:**
- `app/services/aps_engine.py` (~1300 lines) — deterministic finite-capacity scheduler, 30-min slots, constraint FEASIBLE/INFEASIBLE, lock-preserved replans. DO NOT TOUCH without running `tests/test_aps_engine.py`.
- `app/services/erp_adapter.py` — Lighthouse V15 (Oracle) mock; `IntegrationJob` wraps every ERP call.
- `app/services/plc_adapter.py` — OPC-UA/Modbus/MQTT mock façade.
- `app/services/kpi_engine.py` — OEE, die-life, shortage aggregation; writes `KPIRecord`.
- `app/services/scheduler.py` — legacy greedy scheduler (`ScheduleOptimizer`); coexists with `aps_engine`.
- `app/services/process_simulator.py` — deterministic fake sensor values for demo.

**What to read first (in order):**
1. `README.md` first 100 lines — domain overview, module list, tech stack.
2. `app/models.py` first 200 lines — establishes base model pattern (`Line`, `Machine`, `Station`, `WorkOrder`, `BOMItem`, `RoutingStep`).
3. `app/__init__.py` (full, 190 lines) — blueprint registration + auto-startup seed logic.
4. `app/services/aps_engine.py` first 150 lines — slot math, constants, imports reveal architecture.

**What NOT to touch (without understanding):**
- **Auto-seed logic at startup** in `app/__init__.py` lines 119-188. It runs on EVERY launch, silently swallowed on error. The function call order matters (downstream seeds depend on upstream master data). Removing it makes the demo look empty.
- **`aps_engine.py` internals** — deterministic scheduling; replanning preserves manual locks. Subtle bugs produce silently wrong schedules. Run `tests/test_aps_engine.py` after any change.
- **`__init__.py` blueprint registration order** — affects endpoint resolution and `url_for`. Some blueprints depend on others being registered first (inferred, not verified).
- **`scripts/seed_data.py` top-level sequence** — called at startup; same ordering caveat as `__init__.py`.
- **`app/models.py`** — every route, service, seed function, and migration imports from it. Column changes break multiple surfaces.

**Top-level architecture facts:**
- App factory pattern: `create_app()` in `app/__init__.py`.
- ~39 blueprints, 254 templates, ~80 Python files.
- Hub files by blast radius: `models.py` > `__init__.py` > `models_aps.py` / `models_routing.py` > `aps_engine.py` > `seed_data.py` > route files > templates.
- API boundaries inconsistent: half use `url_prefix`, half hardcode routes — known, not blocking.
- State machines exist for WorkOrder, Die, Routing, Alert, IntegrationJob — see `graphify-out/GRAPH_REPORT.md` for the transitions.

---

End of Session Memory.
