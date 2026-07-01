# Endpoint Contract (shared between backend and frontend agents)

This file defines the URL/endpoint mapping both agents MUST follow.

## New Blueprints + Primary Endpoints

### planning (Blueprint prefix none - root)
- `GET /planning` → `planning.index` (orders + stock + availability overview)
- `GET /planning/orders` → `planning.orders` (customer orders from ERP)
- `POST /planning/orders/import` → `planning.import_order`
- `GET /planning/stock` → `planning.stock` (dies + billets availability)
- `GET /planning/availability` → `planning.availability` (machines)
- `GET /planning/scheduler` → `planning.scheduler` (Gantt board — refactored from production.scheduler)
- `POST /planning/optimize` → `planning.optimize`
- `GET /planning/shortages` → `planning.shortages` (projected die/billet shortages)
- `GET /planning/plan-vs-actual` → `planning.plan_vs_actual` (migrated from production)

### tool_shop
- `GET /tool-shop` → `tool_shop.index` (dashboard: die registry + pipeline)
- `GET /tool-shop/dies` → `tool_shop.die_list`
- `POST /tool-shop/dies/new` → `tool_shop.die_new` (inward from store)
- `GET /tool-shop/dies/<id>` → `tool_shop.die_detail`
- `POST /tool-shop/dies/<id>/inspect` → `tool_shop.die_inspect`
- `POST /tool-shop/dies/<id>/test` → `tool_shop.die_test`
- `POST /tool-shop/dies/<id>/nitride` → `tool_shop.die_nitride`
- `GET /tool-shop/inspections` → `tool_shop.inspection_list`
- `GET /tool-shop/tests` → `tool_shop.test_list`
- `GET /tool-shop/nitriding` → `tool_shop.nitriding_list`
- `GET /tool-shop/shortages` → `tool_shop.shortages`

### process_line
- `GET /process-line` → `process_line.index` (floor overview)
- `GET /process-line/billet-inspection` → `process_line.billet_inspection`
- `POST /process-line/billet-inspection/new` → `process_line.billet_inspection_new`
- `GET /process-line/hls` → `process_line.hls`
- `POST /process-line/hls/load-setpoint` → `process_line.hls_load`
- `POST /process-line/hls/<run_id>/capture` → `process_line.hls_capture`
- `GET /process-line/pressing` → `process_line.pressing`
- `GET /process-line/quenching` → `process_line.quenching`
- `GET /process-line/quenching/<run_id>/trend` → `process_line.quench_trend`
- `GET /process-line/puller` → `process_line.puller`
- `GET /process-line/cutting` → `process_line.cutting`
- `GET /process-line/stretching` → `process_line.stretching`
- `GET /process-line/final-cut` → `process_line.final_cut`
- `GET /process-line/die-oven` → `process_line.die_oven`

### kpi_alerts
- `GET /kpi-alerts` → `kpi_alerts.index` (KPI dashboard)
- `GET /kpi-alerts/oee` → `kpi_alerts.oee` (repurposed OEE)
- `GET /kpi-alerts/die-lifecycle` → `kpi_alerts.die_lifecycle`
- `GET /kpi-alerts/downtime` → `kpi_alerts.downtime`
- `GET /kpi-alerts/alerts` → `kpi_alerts.alerts_list`
- `POST /kpi-alerts/alerts/<id>/acknowledge` → `kpi_alerts.alert_ack`
- `POST /kpi-alerts/alerts/<id>/close` → `kpi_alerts.alert_close`
- `GET /kpi-alerts/rules` → `kpi_alerts.rules`
- `POST /kpi-alerts/rules/new` → `kpi_alerts.rule_new`

### Retained existing endpoints that stay in sidebar
- `dashboard.index`
- `integrations.hub`, `integrations.erp_sync`, `integrations.webhooks`, `integrations.api_docs`
  + NEW: `integrations.plc_connectors`, `integrations.signal_mapping`, `integrations.jobs`
- `admin.admin_dashboard`, `admin.plants`, `admin.users`, `admin.roles`, `admin.audit_log`
  + NEW: `admin.thresholds`, `admin.machine_master`, `admin.process_params`

## Sidebar Contract
The sidebar (layout.html) MUST show exactly these top-level items (plus group children):
1. Dashboard (single nav-item → dashboard.index)
2. Planning & Scheduling (group → planning.*)
3. Tool Shop (group → tool_shop.*)
4. Process Line (group → process_line.*)
5. Quality & Traceability (group → quality_ext, traceability, genealogy combined OR keep as separate routes under one label)
6. KPI & Alerts (group → kpi_alerts.*)
7. Integrations (group → integrations.*)
8. Administration (group → admin.*)

## Obsolete routes: DO NOT DELETE, but DO NOT link from sidebar
- work_orders.* — still accessible via planning if needed
- production.* — legacy scheduler; refactored into planning
- operations.* — process_line is the new entry
- scheduling.* — merged into planning
- inventory.*, kitting.*, smt_materials.* — absorbed
- routing.*, routing_builder.* — retired
- pcb.* — retired
- ncr.* — merged into quality_ext
- oee.* — merged into kpi_alerts
- stations.*, maintenance.* — folded into admin
