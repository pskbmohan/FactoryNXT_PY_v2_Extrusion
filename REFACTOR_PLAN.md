# FactoryNXT Foundry Refactor Plan

## Domain Shift
- FROM: SMT/PCB Electronics MES
- TO:   Aluminum Extrusion Plant Digitalization (dies, billets, extrusion process lines)

## Sidebar Target (8 modules ONLY)

| # | Module | Reuse source | Refactor scope |
|---|---|---|---|
| 1 | Dashboard | `dashboard.py` + `dashboard.html` | Extend with extrusion KPIs |
| 2 | Planning & Scheduling | `production.py` + `scheduling.py` | Merge into one module: orders, stock, availability, optimizer, Gantt, plan-vs-actual |
| 3 | Tool Shop | NEW | Die workflows: inward, inspection, testing, nitriding, registry, shortage |
| 4 | Process Line | `operations.py` + `machines.py` | Station-oriented: billet inspection, HLS/pressing/quenching/puller/cut/stretch/oven capture |
| 5 | Quality & Traceability | `quality_ext.py` + `traceability.py` + `genealogy.py` + `ncr.py` | Merge: die/billet/lot trace, inspection/test records, audit trail, ERP tx log |
| 6 | KPI & Alerts | `oee.py` + NEW alerts | OEE repurposed as extrusion KPIs; threshold alerts, sync failure alerts, planning risk |
| 7 | Integrations | `integrations.py` | Extend with PLC connectors, signal mapping, reprocess tools |
| 8 | Administration | `admin.py` + `users.py` + `stations.py` + `maintenance.py` | Master data, users, stations, PM, calibration, thresholds, reference mappings |

## Obsolete / Hidden sidebar items (move under Admin or retire)
- Work Orders (standalone) → absorbed into Planning & Scheduling
- Production (group) → split into Planning (scheduler) + Process Line (floor)
- Operations → Process Line
- Scheduling (standalone) → Planning & Scheduling
- Inventory → absorbed in Planning (stock) + Tool Shop (dies)
- Kitting → HIDE (SMT-only)
- SMT Materials → HIDE (SMT-only)
- Routing / Routing Builder → HIDE (fixed process flow in extrusion)
- NCR (standalone) → Quality & Traceability
- Quality (standalone group) → Quality & Traceability
- OEE (standalone) → KPI & Alerts
- PCB → HIDE (SMT-only)
- Machines (standalone) → Process Line (floor panel) + Admin (maintenance)
- Maintenance (standalone group) → Administration
- Traceability / Genealogy (standalone) → Quality & Traceability

## Models to Add (one consolidation migration)
- CustomerOrder, WorkOrder(kept/extended), ProcessPlan, ProjectedShortage
- Die, DieInspection, DieTest, NitridingRecord
- Billet, BilletInspection, MaterialGrade
- SetpointProfile, ProcessRun
- QuenchRecord, CutRecord, StretchRecord, OvenRecord
- Alert, AlertRule
- KPIRecord (extends OeeSnapshot → rename to machine KPI)
- IntegrationJob (extends Integration), ERPTransactionLog
- PLCSignalMapping
- TraceabilityRecord (generic process trace)

## Workflow state machines enforced
- Die.status: New → Inspected → TestingPending → TestingPassed → NitridingPending → Nitrided → Available | Rework | Rejected | TestingFailed
- ProcessPlan.status: Draft → Optimized → Released → InProgress → Delayed → Completed
- IntegrationJob.status: Pending → Running → Success → Failed → RetryQueued
- Alert.status: Open → Acknowledged → Closed

## File Ownership
- BACKEND AGENT (Python only): `app/models.py`, new `app/services/`, `app/integrations/`, new route files, `migrations/versions/`, `app/__init__.py` blueprint registration, existing blueprints that need endpoint updates
- FRONTEND AGENT (HTML/CSS only): `app/templates/layout.html`, all new template dirs (`planning/`, `tool_shop/`, `process_line/`, `kpi_alerts/`), refactor of `dashboard.html`, retire stale sidebar groups

## Implementation Sequence
1. Domain mapping (this doc) → DONE
2. Backend: models + migration + services + adapters
3. Frontend: layout + new templates + dashboard
4. Backend: routes + API
5. Integration: ERP + PLC adapters
6. QA: smoke tests + integrity checks

## Assumptions (pending customer input)
- ERP connector API (endpoint, auth, payload shape) not specified → adapter layer with mock/default
- PLC protocol (OPC-UA / Modbus / MQTT) not specified → signal mapping table is generic; ingester is pluggable
- Sensor hardware vendors → abstracted via `plc_adapters/`
