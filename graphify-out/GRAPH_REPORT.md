# Graph Report - FactoryNXT_PY_v2_Extrusion  (2026-07-23)

## Corpus Check
- 149 files · ~359,789 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2555 nodes · 4325 edges · 169 communities (143 shown, 26 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 397 edges (avg confidence: 0.67)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `6ff5eb4d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- ._create_job() ._finalize() ._get_signals() .capture_actuals
- .__repr__() ._extract_alloy_from_description() ._log_constra
- .__repr__() ._seed_master() ._seed_wo() .tearDown()
- .to_dict() Assign routing to a product. Change routing statu
- Check actual_composition against alloy composition tolerance
- BurnInSession CalibrationRecord Capa DefectRecord
- Alarm & Event History dashboard. DowntimeEvent Parse a datet
- Add a new material grade. Create a new alert threshold rule.
- ApiKey Create a new PLC signal mapping. Decode + parse CSV b
- Edit an existing Station Full audit trail of every operation
- Assign a WO to a machine+day slot via drag-and-drop. AuditLo
- Block until the background worker flips status off 'pending'
- .test_move_entry_endpoint() Create WorkOrders and ApsSchedul
- AlloyComposition CostPriceConfig FinishingOrder FinishingPro
- Get a single customer with their part number mappings. Get a
- .__repr__() ._find_earliest_slot() ._find_earliest_slot_for_
- DieInspection DieTest ERP adapter service — Lighthouse Info
- CoatingColor CoatingScheduleEntry DieFurnaceLog DieRepairRec
- Add a new line to a customer order with BOM validation. Crea
- Estimate cleaning time saved by grouping colors vs naive ord
- ._call_erp() ._create_job() ._finalize_job() ._new_log_id()
- BilletInspection Create extrusion-chain genealogy events + t
- Furnace FurnaceSession HeatTreatmentProgram Seed furnaces, h
- APS routes  Two blueprints:   aps          – page views (/ap
- _parse_date() approve_shipment() create_package() create_shi
- .__init__() ._load() .generate_work_orders() .test_generates
- Customer Customer master data for BOM-driven order managemen
- complete() create_ncr() create_order() detail()
- Demo workspace for camera-based extrusion die visual inspect
- .compute_die_lifetime() Aggregate die lifecycle data: avg cy
- .setUp() .test_cockpit_page_loads_without_version() .test_cr
- Container ContainerMovement ContainerWeighEvent assign_wo()
- API endpoint to get details of a specific upload.     Return
- .compute_shortages() .optimize() Compute projected die/bille
- .evaluate_rules() Compute and persist foundry KPIs. Evaluate
- Config DigitalOcean App Platform injects DATABASE_URL as pos
- PcbBoard PcbPanel UnitHistory board_detail()
- BOMItem bom.py create_bom_item() detail()
- Gantt-style board combining legacy SMT schedule and new extr
- Activate a specific BOM version, deactivating others for sam
- APS cockpit dashboard. Build the full context dict required
- Create a work order from a customer order line with BOM auto
- Run migrations in 'offline' mode.      This configures the c
- .test_api_aps_entries() .test_api_aps_events() .test_api_aps
- breakdown_json() cost_price.py create_config() delete_config
- Return True if *column* already exists on *table*. Return Tr
- 20260704_wattmon_eav_schema.py Column definitions for the ne
- Alarm OeeSnapshot create_app() run.py
- Replan: preserve locked entries, reschedule the rest. Return
- Accept a Wattmon CSV POST (no authentication required).
- .__getattr__() .__init__() Material traceability - billet an
- ._count_routing_steps() ._duration_for() ._routing_total_min
- Test a single endpoint with form-encoded payload. Test backw
- Build a minimal Wattmon-format CSV blob (header + rows joine
- Extrusion traceability dashboard - shows material flow and p
- 20260707_add_machine_resource_mapping.py Return True if the
- _has_column() _has_table() aps_add_notes_columns.py downgrad
- Check if a table exists in the current database. _has_table(
- .start() Thread that runs ``target(*args, **kwargs)`` synchr
- .compute_shortage_risk() Alert Compute planning risk alerts
- .__repr__() MachineResourceMapping Maps a part number to req
- RoutingStep create_routing_step() list_routing() routing.py
- .__repr__() Tracks which resources were assigned to a work o
- .compute_oee() Compute OEE for a machine on a specific shift
- DATABASE_URL entrypoint.sh entrypoint.sh script
- 20260715_add_customer_part_bom_wo_fields.py downgrade() upgr
- .setUp() Build a test app with in-memory SQLite. make_app()
- Run scheduling with algorithm selection (FIFO / DUE_DATE / O
- Lock or unlock a schedule entry. api_lock_entry()
- Calculate a Schedule Score (0-100) for the current version.
- APS Gantt / scheduler view. scheduler()
- List all part number BOMs with optional filter. boms_list()
- Create a new customer record. create_customer()
- Create a mapping between customer and part number. create_cu
- Create a new part number. create_part_number()
- Validate that a customer is mapped to a specific part number
- FactoryNXT BOM Feature - Final Summary & Verification Report
- BOM-Driven Work Order Feature — Gap Analysis Summary Report
- Session Status: **COMPLETE**
- DefectCode
- DefectTrackingService
- Quality Reporting & Control System - Handover (P3 Enhancement COMPLETE)
- Recommended Implementation Approach
- Session Status: **COMPLETE**
- InspectionService
- Quality Feature Implementation Loop Configuration
- mtc_reports.py
- _qp_to_dict
- Session Log
- Changelog
- Database Migration Status Report
- warehouse-dashboard.js
- users.py
- Phase Completion Checklist
- Session Status: **COMPLETE**
- Session Status: **COMPLETE**
- 20260720_add_quality_schema.py
- Quality Reporting & Control System - Build Plan
- Session Status: **COMPLETE**
- New Blueprints + Primary Endpoints
- FactoryNXT Foundry Refactor Plan
- warehouse-transactions.js
- coating_schedule.py
- stations.py
- warehouse-rack-detail.js
- FactoryNXT Demo Mode Design
- Files Changed Summary
- Current Session (P3 Enhancement COMPLETE):
- Session Completion Log (Current Session - 2026-07-21)
- 20260723_add_warehouse_management.py
- warehouse-search.js
- OperationTransaction
- SerialNumber
- TransactionService
- P3 MTC Reports Dashboard (NEW)
- dies_list
- .track_batch_dies
- SearchService
- Success Criteria per Session
- P3 Traceability Viewer Dashboard (NEW)
- P3 SPC Charts Dashboard (NEW)
- Current Session Execution Summary (2026-07-21)
- Phase 1: Database Schema Extensions - COMPLETE
- Key Features Implemented in P3 Enhancement:
- Migration File: `migrations/versions/YYYY_MM_DD_add_quality_schema.py`
- activate_bom
- billets_list
- customers_list
- delete_customer_part_mapping
- get_customer
- get_part_number
- part_numbers_list
- Implementation Summary
- Next Steps: Ready for Testing & Deployment
- alloy_compositions_list
- boms_page
- coating_colors_list
- create_finishing_process_type
- customers_page
- defect_codes_list
- delete_alloy_composition
- delete_coating_color
- delete_defect_code
- delete_finishing_process_type
- delete_packaging_spec
- finishing_process_types_list
- get_alloy_composition
- get_packaging_spec
- get_raw_material_type
- update_defect_code
- update_coating_color
- raw_material_types_list
- update_raw_material_type
- update_alloy_composition
- update_finishing_process_type
- CLAUDE.md

## God Nodes (most connected - your core abstractions)
1. `WorkOrder` - 76 edges
2. `Die` - 66 edges
3. `Billet` - 46 edges
4. `ApsEngine` - 43 edges
5. `Machine` - 42 edges
6. `CustomerOrder` - 39 edges
7. `ApsScheduleEntry` - 35 edges
8. `ProcessRun` - 34 edges
9. `main()` - 33 edges
10. `_u()` - 32 edges

## Surprising Connections (you probably didn't know these)
- `create_app()` --calls--> `seed_plant_master_data()`  [INFERRED]
  app/__init__.py → scripts/seed_data.py
- `ApsTestCase` --uses--> `Config`  [INFERRED]
  tests/conftest.py → app/config.py
- `ApsTestCase` --uses--> `Line`  [INFERRED]
  tests/conftest.py → app/models.py
- `AutoScheduleTests` --uses--> `Machine`  [INFERRED]
  tests/test_aps_engine.py → app/models.py
- `ManualMoveTests` --uses--> `Machine`  [INFERRED]
  tests/test_aps_engine.py → app/models.py

## Import Cycles
- 3-file cycle: `app/__init__.py -> app/routes/aps.py -> app/models.py -> app/__init__.py`
- 3-file cycle: `app/__init__.py -> app/routes/machines.py -> app/models.py -> app/__init__.py`
- 3-file cycle: `app/__init__.py -> app/routes/warehouse_management.py -> app/models.py -> app/__init__.py`
- 4-file cycle: `app/__init__.py -> app/routes/warehouse_management.py -> app/services/warehouse_service.py -> app/models.py -> app/__init__.py`

## Communities (169 total, 26 thin omitted)

### Community 0 - "._create_job() ._finalize() ._get_signals() .capture_actuals"
Cohesion: 0.05
Nodes (56): cutting(), die_oven(), final_cut(), hls(), hls_capture(), hls_capture_new(), hls_load(), index() (+48 more)

### Community 1 - ".__repr__() ._extract_alloy_from_description() ._log_constra"
Cohesion: 0.06
Nodes (23): Any, ApsEngine, _as_datetime(), _new_id(), datetime, Manually move or reassign an APS entry.          Returns the updated entry plus, Coerce a date or datetime to datetime (midnight UTC). Returns None if None., Resolves per-day working windows for a plant.      Reads ShiftCalendar rows if a (+15 more)

### Community 2 - ".__repr__() ._seed_master() ._seed_wo() .tearDown()"
Cohesion: 0.08
Nodes (41): ApsConstraintLog, ApsScheduleEntry, ApsScheduleVersion, One scheduled block: a work order assigned to a machine in a time window., Records a scheduling constraint violation or warning for a version/entry., A named snapshot of the production schedule (active, draft, or archived)., CustomerOrder, Machine (+33 more)

### Community 3 - ".to_dict() Assign routing to a product. Change routing statu"
Cohesion: 0.06
Nodes (34): Routing header – one record per routing revision., Links a product/part number to a specific routing revision., Frozen copy of routing steps taken when a Work Order is released.     Future cha, Individual step / operation in a routing., Directed connection between two routing steps (DAG edge)., RoutingConnection, RoutingMaster, RoutingProductAssignment (+26 more)

### Community 4 - "Check actual_composition against alloy composition tolerance"
Cohesion: 0.06
Nodes (23): FeederReel, GoldenBoard, InventoryItem, InventoryLocation, Kit, PpapRecord, SolderPasteLot, inventory_form() (+15 more)

### Community 5 - "BurnInSession CalibrationRecord Capa DefectRecord"
Cohesion: 0.06
Nodes (19): BurnInSession, CalibrationRecord, Capa, DefectRecord, InspectionPlan, MaintenanceLog, PmSchedule, Stencil (+11 more)

### Community 6 - "Alarm & Event History dashboard. DowntimeEvent Parse a datet"
Cohesion: 0.06
Nodes (19): DowntimeEvent, ProductionSchedule, ShiftCalendar, SmtLine, alarms(), detailed(), downtime_new(), Alarm & Event History dashboard. (+11 more)

### Community 7 - "Add a new material grade. Create a new alert threshold rule."
Cohesion: 0.09
Nodes (14): machine_master(), machine_master_new(), process_params(), process_params_grade_new(), process_params_profile_new(), Manage alert thresholds for KPIs and planning metrics., Toggle a threshold rule's active status., List all machines with their maintenance and calibration status. (+6 more)

### Community 8 - "ApiKey Create a new PLC signal mapping. Decode + parse CSV b"
Cohesion: 0.06
Nodes (27): ApiKey, ErpSyncLog, Webhook, api_key_generate(), csv_upload(), erp_trigger(), hub(), job_retry() (+19 more)

### Community 9 - "Edit an existing Station Full audit trail of every operation"
Cohesion: 0.18
Nodes (10): get_operation_history(), get_serial_numbers(), get_stations_for_wo(), get_work_orders(), index(), Operation Execution Screen — main page., List all serial numbers and their current status for a given WO., Return work orders that are RELEASED or RUNNING. (+2 more)

### Community 10 - "Assign a WO to a machine+day slot via drag-and-drop. AuditLo"
Cohesion: 0.03
Nodes (61): Config, _normalise_db_url(), DigitalOcean App Platform injects DATABASE_URL as postgres://...     SQLAlchemy, MachineResourceMapping, Maps a part number to required machine resources (machine, die, consumables, tim, Billet, Die, Line (+53 more)

### Community 11 - "Block until the background worker flips status off 'pending'"
Cohesion: 0.05
Nodes (52): Metadata for each POST to /integrations/csv-upload., Metadata for each POST to /integrations/csv-upload., Entity-Attribute-Value: one row per (device_key, column_name, value, time-point), Entity-Attribute-Value: one row per (device_key, column_name, value, time-point), WattmonReading, WattmonUpload, csv_upload(), get_upload() (+44 more)

### Community 12 - ".test_move_entry_endpoint() Create WorkOrders and ApsSchedul"
Cohesion: 0.09
Nodes (40): QualityInspection, Unified inspection records across all quality stages.      Replaces and extends, _get_die_setup_time_comparison(), Get comparison of die setup times., _analyze_surface_defects(), by_alloy(), by_profile(), by_shift() (+32 more)

### Community 13 - "AlloyComposition CostPriceConfig FinishingOrder FinishingPro"
Cohesion: 0.06
Nodes (67): Alarm, Alert, AlloyComposition, AuditLog, CoatingColor, CoatingScheduleEntry, CostPriceConfig, DieFurnaceLog (+59 more)

### Community 14 - "Get a single customer with their part number mappings. Get a"
Cohesion: 0.07
Nodes (27): create_alloy_composition(), create_coating_color(), create_defect_code(), create_packaging_spec(), create_raw_material_type(), customer_part_map_page(), delete_quality_parameter(), delete_raw_material_type() (+19 more)

### Community 15 - ".__repr__() ._find_earliest_slot() ._find_earliest_slot_for_"
Cohesion: 0.11
Nodes (15): ApsScheduleEvent, APS models: MachineResourceMapping, WorkOrderResource, and the full Advanced Pla, Audit trail of changes to schedule entries (locks, overrides, replans)., Visual Routing Builder models for FactoryNXT.  Separate file to avoid merge conf, _ceil30(), _is_same_day(), Advanced Planning System (APS) scheduling engine.  Provides finite-capacity sche, Create one WorkOrder per selected CustomerOrder.          Rules:           * Ski (+7 more)

### Community 16 - "DieInspection DieTest ERP adapter service — Lighthouse Info"
Cohesion: 0.16
Nodes (8): DieTest, die_new(), die_release(), die_test(), _parse_date(), Tool Shop blueprint.  Dies workflow: inward → inspection → testing → nitriding →, Inward a new die from the store., Mark a nitrided die as Available for production scheduling.

### Community 17 - "CoatingColor CoatingScheduleEntry DieFurnaceLog DieRepairRec"
Cohesion: 0.04
Nodes (43): api_assign_die(), api_find_die_location(), api_get_alloys(), api_get_profiles(), api_get_rack(), api_get_rack_slots(), api_get_rack_types(), api_get_racks() (+35 more)

### Community 18 - "Add a new line to a customer order with BOM validation. Crea"
Cohesion: 0.06
Nodes (43): CustomerOrderLine, CustomerPartNumber, PartNumberBOM, Mapping between customers and their approved part numbers., Bill of Materials linking a part number to its die and billet types., Individual line items within a customer order, linked to part numbers., Mapping between customers and their approved part numbers., Bill of Materials linking a part number to its die and billet types. (+35 more)

### Community 19 - "Estimate cleaning time saved by grouping colors vs naive ord"
Cohesion: 0.28
Nodes (5): RepairRecord, _json_field_like(), Return a filter expression matching JSON `column` containing key=value.      Wor, repair_new(), search()

### Community 20 - "._call_erp() ._create_job() ._finalize_job() ._new_log_id()"
Cohesion: 0.14
Nodes (17): DieInspection, ERPTransactionLog, NitridingRecord, erp_reprocess(), Re-process a batch of unposted ERP records (inspections, tests, nitridings)., import_order(), Trigger an ERP order import job., die_inspect() (+9 more)

### Community 21 - "BilletInspection Create extrusion-chain genealogy events + t"
Cohesion: 0.13
Nodes (22): CutRecord, IntegrationJob, OeeSnapshot, OvenRecord, ParameterReading, PLCSignalMapping, ProcessParameterAlert, ProcessRun (+14 more)

### Community 22 - "Furnace FurnaceSession HeatTreatmentProgram Seed furnaces, h"
Cohesion: 0.16
Nodes (7): FurnaceSession, HeatTreatmentProgram, create_program(), start_session(), Seed furnaces, heat treatment programs, and sessions., Seed furnaces, heat treatment programs, and sessions., seed_furnace_module()

### Community 23 - "APS routes  Two blueprints:   aps          – page views (/ap"
Cohesion: 0.05
Nodes (35): Tracks which resources were assigned to a work order at schedule time., WorkOrderResource, status(), api_gantt(), api_kpis(), api_lock_entry(), api_move_entry(), api_publish() (+27 more)

### Community 24 - "_parse_date() approve_shipment() create_package() create_shi"
Cohesion: 0.14
Nodes (4): create_package(), create_shipment(), _parse_date(), scan_package()

### Community 25 - ".__init__() ._load() .generate_work_orders() .test_generates"
Cohesion: 0.06
Nodes (35): SPC chart data points with shift grouping.      Stores dimension measurements fo, SPCRecord, api_capability(), api_control_charts(), api_violations(), capability_view(), control_charts_view(), dimensions_list() (+27 more)

### Community 26 - "Customer Customer master data for BOM-driven order managemen"
Cohesion: 0.22
Nodes (9): Customer, Customer master data for BOM-driven order management., Customer master data for BOM-driven order management., create_customer(), customer_part_mappings(), List all active customer-to-part mappings., List all active customer-to-part mappings., Create a new customer record. (+1 more)

### Community 27 - "complete() create_ncr() create_order() detail()"
Cohesion: 0.16
Nodes (4): NCR, create_order(), reject(), create_ncr()

### Community 28 - "Demo workspace for camera-based extrusion die visual inspect"
Cohesion: 0.14
Nodes (7): create_die(), inspection(), inspection_scenarios(), Demo workspace for camera-based extrusion die visual inspection.      Renders a, Return the mock inspection scenarios as JSON.      Front-end demo uses this to i, send_to_furnace(), send_to_repair()

### Community 29 - ".compute_die_lifetime() Aggregate die lifecycle data: avg cy"
Cohesion: 0.14
Nodes (7): AlertRule, Create a new alert threshold rule., thresholds_new(), die_lifecycle(), KPI & Alerts blueprint.  Consolidates OEE-style metrics for extrusion with thres, rule_new(), Aggregate die lifecycle data: avg cycles, min/max, count by status.

### Community 30 - ".setUp() .test_cockpit_page_loads_without_version() .test_cr"
Cohesion: 0.13
Nodes (3): auth_session(), Set `username` in the session so auth-requiring routes resolve., GanttDataTests

### Community 31 - "Container ContainerMovement ContainerWeighEvent assign_wo()"
Cohesion: 0.20
Nodes (9): Container, ContainerMovement, ContainerWeighEvent, create_container(), move(), weigh(), Seed containers, weigh events, and movements., Seed containers, weigh events, and movements. (+1 more)

### Community 32 - "API endpoint to get details of a specific upload.     Return"
Cohesion: 0.05
Nodes (42): 10. SPC Charts Dashboard (P3), 11. MTC Report Generation (P3), 1. Comprehensive Review, 1. First Pass Yield (FPY) Tracking, 2. Issues Fixed, 2. Scrap & Rejection Analytics, 3. Die Performance Metrics, 3. Documentation Updated (+34 more)

### Community 33 - ".compute_shortages() .optimize() Compute projected die/bille"
Cohesion: 0.18
Nodes (9): index(), Planning overview: orders, stock, availability snapshot., Projected die/billet shortages., shortages(), index(), Tool shop dashboard: die registry and pipeline overview., shortages(), Compute projected die/billet shortages.          Returns a dict with:         - (+1 more)

### Community 34 - ".evaluate_rules() Compute and persist foundry KPIs. Evaluate"
Cohesion: 0.21
Nodes (8): oee(), KPIEngine, KPI engine service.  Computes aggregate KPIs for the foundry domain: - OEE (avai, Evaluate active AlertRules against the provided KPI records.          Any rule b, Compute and persist foundry KPIs., Compute OEE for a machine on a specific shift_date.          OEE = availability, Greedy scheduler for aluminum extrusion orders., ScheduleOptimizer

### Community 35 - "Config DigitalOcean App Platform injects DATABASE_URL as pos"
Cohesion: 0.05
Nodes (41): 1. Dashboard, 2. Planning & Scheduling, 3. Tool Shop, 4. Process Line, 5. Quality & Traceability, 6. KPI & Alerts, 7. Integrations, 8. Administration (+33 more)

### Community 36 - "PcbBoard PcbPanel UnitHistory board_detail()"
Cohesion: 0.25
Nodes (6): PcbBoard, PcbPanel, UnitHistory, history_add(), panel_new(), seed_work_orders_and_traceability()

### Community 37 - "BOMItem bom.py create_bom_item() detail()"
Cohesion: 0.25
Nodes (3): BOMItem, create_bom_item(), list_create_work_orders()

### Community 38 - "Gantt-style board combining legacy SMT schedule and new extr"
Cohesion: 0.05
Nodes (38): 1. Database Schema - FULLY IMPLEMENTED ✅, 1. Execute Database Migration, 2. Model Classes - FULLY IMPLEMENTED ✅, 2. Seed Defect Codes Data, 3. Route Blueprints - FULLY IMPLEMENTED ✅, 3. Verify Dashboard Routes, 4. HTML Templates - FULLY IMPLEMENTED ✅, 4. Test Service Layer (+30 more)

### Community 39 - "Activate a specific BOM version, deactivating others for sam"
Cohesion: 0.33
Nodes (6): create_bom(), Create a new BOM version (auto-deactivates existing active BOM)., Create a new BOM version (auto-deactivates existing active BOM)., Update BOM by creating new version (same as create - versions are immutable)., Update BOM by creating new version (same as create - versions are immutable)., update_bom()

### Community 40 - "APS cockpit dashboard. Build the full context dict required"
Cohesion: 0.05
Nodes (37): ✅ All 6 Service Modules Implemented, Completed Items (Phase 2 - Service Layer) — VERIFIED, Data Model Gaps (No Action Required - Design Decisions), ⏳ DefectTrackingService (Created but needs completion), DEPLOYMENT REQUIRED — ALL CODE COMPLETE ✓, ⏳ DiePerformanceService (Created but needs completion), Executive Summary, Files Created/Modified Summary (+29 more)

### Community 41 - "Create a work order from a customer order line with BOM auto"
Cohesion: 0.09
Nodes (25): by_alloy(), by_die(), by_profile(), by_status(), die_failures(), index(), Die Performance Dashboard - Quality Reporting & Control System.  This blueprint, Die Failure Analysis View.      Focused view on failure history for a specific d (+17 more)

### Community 42 - "Run migrations in 'offline' mode.      This configures the c"
Cohesion: 0.39
Nodes (7): get_engine(), get_engine_url(), get_metadata(), Run migrations in 'offline' mode.      This configures the context with just a U, Run migrations in 'online' mode.      In this scenario we need to create an Engi, run_migrations_offline(), run_migrations_online()

### Community 43 - ".test_api_aps_entries() .test_api_aps_events() .test_api_aps"
Cohesion: 0.08
Nodes (31): _calc_param_stats(), CASE_PARAM_WITHIN_LIMITS(), _compute_parameter_trends(), _compute_profile_parameter_statistics(), _get_overall_parameter_statistics(), _get_recent_extrusion_runs(), _get_recent_parameter_readings(), _get_violations_for_run() (+23 more)

### Community 45 - "Return True if *column* already exists on *table*. Return Tr"
Cohesion: 0.33
Nodes (5): _column_exists(), Return True if *column* already exists on *table*., Return True if *table* already exists in the public schema., _table_exists(), upgrade()

### Community 46 - "20260704_wattmon_eav_schema.py Column definitions for the ne"
Cohesion: 0.33
Nodes (6): downgrade(), _eav_columns(), Wattmon: replace 216-column reading table with Entity-Attribute-Value schema  Re, Re-create the old wide table so that downgrading is non-destructive., Column definitions for the new EAV reading table., upgrade()

### Community 47 - "Alarm OeeSnapshot create_app() run.py"
Cohesion: 0.13
Nodes (16): create_app(), DieLocationIndex, DieRackAssignment, RackTransaction, Tool room rack for die storage and organization.      Supports three rack types:, Tracks which die is stored in which rack slot.      Links dies to specific rack, Transaction log for all die movements in/out of racks.      Records IN (scan-in), Current location index for all dies in warehouse.      Provides fast lookup of w (+8 more)

### Community 48 - "Replan: preserve locked entries, reschedule the rest. Return"
Cohesion: 0.06
Nodes (29): Quality Reporting & Control System Memories, Blockers / Notes for Future Sessions, Completed (20 of 22):, Files Created in This Session (Phase 3 P3 Enhancement), Flask App Initialization:, Next Steps for Execution & Testing, P1 Priority (High):, P2 Priority (Medium): (+21 more)

### Community 49 - "Accept a Wattmon CSV POST (no authentication required)."
Cohesion: 0.09
Nodes (29): by_work_order(), compliance_view(), _compute_inspection_compliance(), first_piece_validation(), _get_active_inspection_plans(), _get_completed_first_piece_inspections(), _get_compliance_by_inspection_type(), _get_first_piece_validation_summary() (+21 more)

### Community 50 - ".__getattr__() .__init__() Material traceability - billet an"
Cohesion: 0.33
Nodes (4): _EventView, material_traceability(), Uniform wrapper so the material template can iterate over both     TraceabilityR, Material traceability - billet and die tracking.

### Community 51 - "._count_routing_steps() ._duration_for() ._routing_total_min"
Cohesion: 0.07
Nodes (28): 6 Specialized Services (~20.8K lines), All Blueprints Registered ✓, API Endpoints Available, Before Production Deployment:, Database Schema Implementation, Deployment Checklist, Executive Summary, Flask App Test - PASSED ✓ (+20 more)

### Community 52 - "Test a single endpoint with form-encoded payload. Test backw"
Cohesion: 0.47
Nodes (5): main(), Test a single endpoint with form-encoded payload., Test backward compatibility with /integrations/csv-upload., test_older_endpoint(), test_payload()

### Community 53 - "Build a minimal Wattmon-format CSV blob (header + rows joine"
Cohesion: 0.10
Nodes (27): _compute_fpy_breakdown(), _compute_fpy_for_period(), _compute_parameter_compliance(), _compute_scrap_by_category(), _compute_scrap_by_dimension(), _compute_scrap_metrics(), fpy_view(), _get_alarm_downtime_summary() (+19 more)

### Community 54 - "Extrusion traceability dashboard - shows material flow and p"
Cohesion: 0.07
Nodes (26): 1. Traceability Viewer (`app/routes/traceability_viewer.py`), 2. SPC Charts Dashboard (`app/routes/spc_charts.py`), 3. MTC Reports Dashboard (`app/routes/mtc_reports.py`), API Endpoints:, API Endpoints:, API Endpoints:, Configuration Updates:, Executive Summary (+18 more)

### Community 55 - "20260707_add_machine_resource_mapping.py Return True if the"
Cohesion: 0.60
Nodes (4): downgrade(), Return True if the table already exists in the DB (handles re-run after partial, _table_exists(), upgrade()

### Community 56 - "_has_column() _has_table() aps_add_notes_columns.py downgrad"
Cohesion: 0.80
Nodes (4): downgrade(), _has_column(), _has_table(), upgrade()

### Community 57 - "Check if a table exists in the current database. _has_table("
Cohesion: 0.60
Nodes (4): downgrade(), _has_table(), Check if a table exists in the current database., upgrade()

### Community 58 - ".start() Thread that runs ``target(*args, **kwargs)`` synchr"
Cohesion: 0.10
Nodes (25): AlarmBreakdownLog, Machine alarm and downtime tracking.      Records all machine alarms with durati, by_category(), by_machine(), _compute_alarms_by_category(), _compute_alarms_by_dimension(), detail(), _get_downtime_trend() (+17 more)

### Community 59 - ".compute_shortage_risk() Alert Compute planning risk alerts"
Cohesion: 0.12
Nodes (12): KPIRecord, Compute planning risk alerts due to die/billet shortages.          Returns a dic, QualityService, Compute FPY grouped by shift (morning/afternoon/night).          Args:, Compute Parts Per Million defect rate.          PPM = (Total defects / Total opp, Compute PPM broken down by defect category.          Args:             shift_dat, Compute quality metrics for the Quality Reporting & Control System., Compute PPM broken down by individual defect codes.          Args:             s (+4 more)

### Community 60 - ".__repr__() MachineResourceMapping Maps a part number to req"
Cohesion: 0.08
Nodes (25): 1. APS Domain Model, 2. Scheduling Engine (`app/services/aps_engine.py`), 3. Planning Cockpit (`/aps`), 4. Gantt Scheduler (`/aps/scheduler`), 5. REST API (`/api/aps/*`), 6. Seed Data (`scripts/seed_data.py`), Access the APS, Advanced Planning System (APS) - Implementation Summary (+17 more)

### Community 62 - ".__repr__() Tracks which resources were assigned to a work o"
Cohesion: 0.08
Nodes (25): BOM-Driven Work Order Feature — Comprehensive Gap Analysis, ✅ Completed Items: 48/49, Completed Items Summary (All 49 Expected Items), Conclusion:, Detailed Gap Analysis Matrix, Detailed Gap Analysis Matrix, Executive Summary, Feature Flow Diagram (+17 more)

### Community 63 - ".compute_oee() Compute OEE for a machine on a specific shift"
Cohesion: 0.08
Nodes (24): Dependencies Verified, Executive Summary, Files Modified This Session, Flask App Test (SQLite) - PASSED ✓, Immediate Actions Required:, Implementation Status Summary, Issue #1: Syntax Error in parameter_monitoring.py (Lines 461-465), Issue #2: Missing ENUM Import in models.py (Line 1834) (+16 more)

### Community 74 - "20260715_add_customer_part_bom_wo_fields.py downgrade() upgr"
Cohesion: 0.26
Nodes (10): _create_table_if_missing(), _has_column(), _has_fk(), _has_table(), add_customer_part_bom_wo_fields  Revision ID: 20260715_add_customer_part_bom_wo_, Check whether a table already exists in the target schema., Check whether a column already exists on a table., Check whether a named FK constraint already exists on a table. (+2 more)

### Community 76 - ".setUp() Build a test app with in-memory SQLite. make_app()"
Cohesion: 0.11
Nodes (23): by_die(), by_shift(), _compute_daily_changeover_frequency(), _count_dies_with_setup_time(), _get_changeover_metrics_by_shift(), _get_changeover_trends(), _get_overall_changeover_metrics(), _get_setup_time_distribution() (+15 more)

### Community 77 - "Run scheduling with algorithm selection (FIFO / DUE_DATE / O"
Cohesion: 0.13
Nodes (23): by_alloy(), by_profile(), by_shift(), _compare_periods(), _compute_fpy_for_period(), _get_fpy_by_alloy(), _get_fpy_by_die(), _get_fpy_by_profile() (+15 more)

### Community 78 - "Lock or unlock a schedule entry. api_lock_entry()"
Cohesion: 0.08
Nodes (23): alloy_compositions_page(), boms_page(), coating_colors_page(), customer_part_map_page(), customers_page(), defect_codes_page(), finishing_process_types_page(), packaging_specs_page() (+15 more)

### Community 79 - "Calculate a Schedule Score (0-100) for the current version."
Cohesion: 0.09
Nodes (22): API Routes ✅, APS Integration ✅, Backend Services ✅, Completed Items Summary (39/46), Critical Issues Summary, Detailed Gap Analysis Table, Documentation ✅, Error Handling & Validation ✅ (+14 more)

### Community 80 - "APS Gantt / scheduler view. scheduler()"
Cohesion: 0.13
Nodes (21): by_die(), _compute_scrap_by_category(), _compute_scrap_by_dimension(), defect_detail(), _get_overall_scrap_metrics(), _get_rejection_comparison(), _get_scrap_for_die(), _get_scrap_trend() (+13 more)

### Community 81 - "List all part number BOMs with optional filter. boms_list()"
Cohesion: 0.22
Nodes (9): PartNumber, Part number master data for BOM-driven order management., Part number master data for BOM-driven order management., boms_list(), create_part_number(), Create a new part number., Create a new part number., List all part number BOMs with optional filter. (+1 more)

### Community 82 - "Create a new customer record. create_customer()"
Cohesion: 0.12
Nodes (12): ParameterMonitoringService, Check if current parameter readings are within setpoint limits.          Args:, Get quality parameter limits from quality_parameters table.          Args:, Determine severity of a parameter violation.          Args:             actual_v, Monitor process parameters and trigger alerts on violations., Generate process parameter alerts for each violation.          Args:, Evaluate whether an auto-stop should be triggered.          Checks for active cr, Manually confirm an auto-stop trigger by an operator.          Args: (+4 more)

### Community 83 - "Create a mapping between customer and part number. create_cu"
Cohesion: 0.67
Nodes (3): create_customer_part_mapping(), Create a mapping between customer and part number., Create a mapping between customer and part number.

### Community 84 - "Create a new part number. create_part_number()"
Cohesion: 0.10
Nodes (14): LocationService, RackService, Assign a die to a specific rack slot.          Args:             die_code: The d, Service class for warehouse management operations., Create a new storage rack.          Args:             rack_code: Unique identifi, Remove a die from a rack (OUT transaction).          Args:             die_code:, Rack management service., Create a rack transaction record (internal method). (+6 more)

### Community 85 - "Validate that a customer is mapped to a specific part number"
Cohesion: 0.10
Nodes (20): Architecture Overview, BOM-Driven Work Order Feature — Build Plan, Files Created/Modified Summary, Objective, Objective, Objective, Objective, Objective (+12 more)

### Community 88 - "FactoryNXT BOM Feature - Final Summary & Verification Report"
Cohesion: 0.10
Nodes (20): 1. Code Implementation ✅, 2. Documentation Created ✅, 3. Code Verification ✅, API Endpoints Summary, Check Git Status:, Conclusion, Executive Summary, FactoryNXT BOM Feature - Final Summary & Verification Report (+12 more)

### Community 89 - "BOM-Driven Work Order Feature — Gap Analysis Summary Report"
Cohesion: 0.11
Nodes (18): API Endpoints ✅ (19 total), APS Integration ✅, Backend Services ✅, BOM-Driven Work Order Feature — Gap Analysis Summary Report, Documentation ✅, End-to-End Flow Verification (Test Script), Files Created/Modified Summary, Final Recommendation (+10 more)

### Community 90 - "Session Status: **COMPLETE**"
Cohesion: 0.11
Nodes (18): 1. Sidebar Already Updated (Task A), 2. Template Directory Created, 3. Four Jinja2 HTML Templates Created (Tasks B1-B4), A. `customers.html` - Customers Master List, Additional API Endpoints Added (to fix template dependencies), API Endpoints Used by Templates, B. `part_numbers.html` - Part Numbers Master List, BOM-Driven Work Order Feature - Handover (Session 3 Complete) (+10 more)

### Community 91 - "DefectCode"
Cohesion: 0.12
Nodes (16): BilletInspection, DefectCode, GenealogyEvent, Master list of defect types with categories and severity levels.      Used for s, TraceabilityRecord, billet_inspection_new(), Defect Tracking Service - Scrap and defect management.  This service handles: -, Create extrusion-chain genealogy events + traceability records so     /traceabil (+8 more)

### Community 92 - "DefectTrackingService"
Cohesion: 0.15
Nodes (10): DefectTrackingService, Record multiple defects for a single inspection.          Args:             insp, Categorize scrap by type, die, operator, alloy for a date range.          Args:, Compute scrap rate as percentage of total production.          Args:, Track and categorize defects for scrap analysis., Get top N defect codes by frequency.          Args:             defects_by_code:, Record a new defect occurrence linked to an inspection.          Args:, Compute scrap rate broken down by die.          Args:             start_date: St (+2 more)

### Community 93 - "Quality Reporting & Control System - Handover (P3 Enhancement COMPLETE)"
Cohesion: 0.11
Nodes (17): Blockers / Notes for Future Sessions, Completed Blueprints (P1):, Completed Blueprints (P2):, Completed Blueprints (P3):, Current Session Status: **PHASE 3 P3 ITEMS COMPLETE**, Files Created (6 new service modules):, P2: Medium Priority - COMPLETE, P3 Enhancement: COMPLETE (Current Session) (+9 more)

### Community 94 - "Recommended Implementation Approach"
Cohesion: 0.11
Nodes (18): Existing Infrastructure to Leverage:, Existing Models to Extend:, Existing Patterns to Follow:, Implementation Approach:, Implementation Details:, New Blueprints to Add:, New Service Classes:, New Tables Required: (+10 more)

### Community 95 - "Session Status: **COMPLETE**"
Cohesion: 0.12
Nodes (16): 1. Template Directory Created, 2. Two Jinja2 HTML Templates Created, 3. Flask Route Handlers Added/Verified, 4. Work Order Detail Template Updated, A. `orders.html` - Customer Orders List, B. `order_detail.html` - Order Detail Page, BOM-Driven Work Order Feature - Handover (Session 4 Complete), Data Flow Summary (+8 more)

### Community 96 - "InspectionService"
Cohesion: 0.13
Nodes (9): InspectionService, Query inspections with optional filters.          Args:             filters: Dic, Validate first-piece dimensions before production starts.          This is a pre, Evaluate if measured dimensions are within tolerance.          Args:, Handle unified quality inspections and MTC generation., Generate a complete Material Test Certificate for a work order.          The MTC, Create a new unified quality inspection record.          Args:             inspe, Return HTML template for MTC generation.          Returns:             Jinja2 Te (+1 more)

### Community 97 - "Quality Feature Implementation Loop Configuration"
Cohesion: 0.13
Nodes (15): 1. Check if Phase 1 migrations exist, 2. Check if services were created, 3. Check if routes were created, Blocker Resolution, Current State Detection Logic, Documentation Updates Required Per Session, Loop Trigger Commands, Manual trigger to continue: (+7 more)

### Community 98 - "mtc_reports.py"
Cohesion: 0.14
Nodes (13): MaterialTraceability, End-to-end traceability chain.      Links all production entities from raw mater, api_export_pdf(), api_mtc(), export_pdf(), generate_mtc(), index(), Material Test Certificate (MTC) Report Generation.  This blueprint provides auto (+5 more)

### Community 99 - "_qp_to_dict"
Cohesion: 0.15
Nodes (14): QualityParameter, Process parameter limits per profile/alloy.      Stores acceptable ranges for al, _apply_qp_data(), create_quality_parameter(), get_quality_parameter(), _qp_to_dict(), quality_parameters_list(), Serialize a QualityParameter record to a dict. (+6 more)

### Community 100 - "Session Log"
Cohesion: 0.14
Nodes (14): Session Log, Session S1 - Database Schema Extensions (Phase 1) **COMPLETED**, Session S2 - Quality Services Layer Part 1, Session S2 - Quality Services Layer Part 1 **COMPLETED**, Session S3 - Quality Services Layer Part 2, Session S3 - Quality Services Layer Part 2 **COMPLETED**, Session S4 - Dashboard Routes Part 1 **COMPLETED**, Session S4 - Quality Services Layer Part 3 **COMPLETED** (+6 more)

### Community 101 - "Changelog"
Cohesion: 0.14
Nodes (13): [1.x.x] - Legacy Versions, [2.0.0] - 2026-07-01, [2.4.0] - 2026-07-11, [2.5.0] - 2026-07-15, Added, Added, Aluminum Extrusion Foundry Domain Migration, BOM-Driven Work Order Creation Feature (Sessions S1-S5) (+5 more)

### Community 102 - "Database Migration Status Report"
Cohesion: 0.14
Nodes (13): Check table counts:, Conclusion, Current Status: ⚠️ Migration File Exists, Cannot Apply (PostgreSQL Not Running), Database Migration Status Report, Migration File Verification ✅, Next Steps to Apply Migration:, Option 1: Start PostgreSQL locally (if available), Option 2: Connect to remote PostgreSQL instance (+5 more)

### Community 103 - "warehouse-dashboard.js"
Cohesion: 0.26
Nodes (13): calculateAvailableSlots(), escapeHtml(), getRackStatusColor(), getRackTypeBadge(), getTimeAgo(), getTypeBadge(), loadRacks(), loadRecentActivity() (+5 more)

### Community 104 - "users.py"
Cohesion: 0.19
Nodes (7): ElectronicSignature, OperatorCertification, Plant, UserProfile, certification_new(), new(), plant_new()

### Community 105 - "Phase Completion Checklist"
Cohesion: 0.15
Nodes (13): Build Plan Reference, Current Status: **PHASE 1 IN PROGRESS**, Next Session Start Command, Phase 0: Setup (Completed), Phase 1: Database Schema Extensions [COMPLETE], Phase 2: Quality Services Layer [COMPLETE - Sessions S2-S5], Phase 3: Dashboard Routes [PENDING], Phase 4: PLC Integration [PENDING] (+5 more)

### Community 106 - "Session Status: **COMPLETE**"
Cohesion: 0.15
Nodes (12): 1. Services Created, 2. API Route Blueprints Created, 3. Blueprint Registration, BOM-Driven Work Order Feature - Handover (Session 2 Complete), Data Flow Summary, Error Handling & Validation, Files Created/Modified in Session 2, Next Session: Session 3 - Master Data UI Screens + Sidebar Update (+4 more)

### Community 107 - "Session Status: **COMPLETE**"
Cohesion: 0.15
Nodes (12): 1. APS Integration with BOM Support, 2. Helper Functions Added to bom_service.py, 3. Seed Data Script Created, BOM-Driven Work Order Feature - Handover (Session 5 Complete), End-to-End Flow Summary, Files Created/Modified in Session 5, Next Steps (Post-S5 Recommendations), Notes for Future Sessions (+4 more)

### Community 108 - "20260720_add_quality_schema.py"
Cohesion: 0.24
Nodes (12): _create_index_if_missing(), _create_table_if_missing(), downgrade(), _has_column(), _has_index(), _has_table(), insert_default_defect_codes(), add quality schema - Quality Reporting & Control System  Revision ID: 20260720_a (+4 more)

### Community 109 - "Quality Reporting & Control System - Build Plan"
Cohesion: 0.15
Nodes (13): Context, End-to-End Test Scenarios:, Existing Infrastructure to Reuse, Implementation Priority Order, Manual Testing Checklist:, Models:, Next Steps After Plan Approval, Quality Reporting & Control System - Build Plan (+5 more)

### Community 110 - "Session Status: **COMPLETE**"
Cohesion: 0.17
Nodes (11): 1. New Database Models Added to `app/models.py`, 2. WorkOrder Model Patched, 3. Alembic Migration Created, BOM-Driven Work Order Feature - Handover (Session 1 Complete), Data Flow (Session 1 Foundation), Files Modified/Created, Next Session: Session 2 - Backend Services & API Routes, Notes for Next Session (+3 more)

### Community 111 - "New Blueprints + Primary Endpoints"
Cohesion: 0.20
Nodes (9): Endpoint Contract (shared between backend and frontend agents), kpi_alerts, New Blueprints + Primary Endpoints, Obsolete routes: DO NOT DELETE, but DO NOT link from sidebar, planning (Blueprint prefix none - root), process_line, Retained existing endpoints that stay in sidebar, Sidebar Contract (+1 more)

### Community 112 - "FactoryNXT Foundry Refactor Plan"
Cohesion: 0.20
Nodes (9): Assumptions (pending customer input), Domain Shift, FactoryNXT Foundry Refactor Plan, File Ownership, Implementation Sequence, Models to Add (one consolidation migration), Obsolete / Hidden sidebar items (move under Admin or retire), Sidebar Target (8 modules ONLY) (+1 more)

### Community 113 - "warehouse-transactions.js"
Cohesion: 0.31
Nodes (8): downloadCSV(), exportTransactions(), formatDate(), getBadgeColor(), getDateString(), loadTransactionStats(), TODO: Implement modal with full transaction details, showNotification()

### Community 114 - "coating_schedule.py"
Cohesion: 0.25
Nodes (4): create_entry(), _parse_dt(), powder_savings(), Estimate cleaning time saved by grouping colors vs naive ordering.

### Community 115 - "stations.py"
Cohesion: 0.22
Nodes (7): create(), edit(), manage(), Station Management (CRUD List), Station Operational Summary Dashboard, Edit an existing Station, summary()

### Community 116 - "warehouse-rack-detail.js"
Cohesion: 0.47
Nodes (8): getRackTypeBadge(), getStatusClass(), loadRackInfo(), loadRackSlots(), renderRackInfo(), renderSlotCard(), renderSlotGrid(), showError()

### Community 117 - "FactoryNXT Demo Mode Design"
Cohesion: 0.25
Nodes (7): CSS Hook, Demo Mode Toggle, FactoryNXT Demo Mode Design, Per-Screen Pattern, Presenter Drawer, Purpose, Walkthrough Sequence

### Community 118 - "Files Changed Summary"
Cohesion: 0.25
Nodes (8): Files Changed Summary, Modified Files:, Original (Phase 3 Start):, P2 Dashboard Routes:, **P3 Enhancement Routes (Current Session):**, Phase 1:, Phase 2 Services:, Phase 3 Routes:

### Community 119 - "Current Session (P3 Enhancement COMPLETE):"
Cohesion: 0.29
Nodes (7): Blueprint Registration Update:, Current Session (P3 Enhancement COMPLETE):, MTC Reports Dashboard COMPLETE:, Next Session Focus:, Session Completion Log (Previous Sessions):, SPC Charts Dashboard COMPLETE:, Traceability Viewer Dashboard COMPLETE:

### Community 120 - "Session Completion Log (Current Session - 2026-07-21)"
Cohesion: 0.33
Nodes (6): App Verification (Current Session):, Files Verified:, Next Steps:, Quality Dashboard URLs Verified:, Session Completion Log (Current Session - 2026-07-21), Syntax Errors Fixed:

### Community 121 - "20260723_add_warehouse_management.py"
Cohesion: 0.40
Nodes (5): downgrade(), _idx_exists(), Drop warehouse management tables., Create warehouse management tables for tool room.      Idempotent: tables may al, upgrade()

### Community 122 - "warehouse-search.js"
Cohesion: 0.47
Nodes (4): loadAvailableAlloys(), loadAvailableRacks(), searchDie(), showNotification()

### Community 123 - "OperationTransaction"
Cohesion: 0.40
Nodes (5): OperationTransaction, Full audit trail of every operation performed against a serial number., Full audit trail of every operation performed against a serial number., Scan a serial number at a station and submit an operation result.      Expected, scan_serial()

### Community 124 - "SerialNumber"
Cohesion: 0.40
Nodes (5): Serial numbers generated when a Work Order is released., Serial numbers generated when a Work Order is released., SerialNumber, Release a Work Order:     - Change status DRAFT -> RELEASED     - Generate seria, release_work_order()

### Community 125 - "TransactionService"
Cohesion: 0.40
Nodes (4): datetime, Transaction history and reporting service., Get transaction history with filters.          Args:             die_code: Filte, TransactionService

### Community 126 - "P3 MTC Reports Dashboard (NEW)"
Cohesion: 0.40
Nodes (5): API Endpoints:, Features:, P3 MTC Reports Dashboard (NEW), Routes Created (`app/routes/mtc_reports.py` ~6,200 lines):, Templates Created (3 HTML files, ~15KB total):

### Community 127 - "dies_list"
Cohesion: 0.50
Nodes (4): dies_list(), part_numbers_page(), List all dies for use in BOM creation dropdown.      Returns simplified die data, List all dies for use in BOM creation dropdown.      Returns simplified die data

### Community 129 - "SearchService"
Cohesion: 0.50
Nodes (3): Search and filter service for warehouse items., Search for dies in the warehouse.          Args:             search_term: Genera, SearchService

### Community 130 - "Success Criteria per Session"
Cohesion: 0.50
Nodes (4): Phase 1 (Database Schema):, Phase 2-3 (Services & Routes):, Phase 4+ (Integration Features):, Success Criteria per Session

### Community 131 - "P3 Traceability Viewer Dashboard (NEW)"
Cohesion: 0.50
Nodes (4): API Endpoints:, P3 Traceability Viewer Dashboard (NEW), Routes Created (`app/routes/traceability_viewer.py` ~4,500 lines):, Templates Created (6 HTML files, ~40KB total):

### Community 132 - "P3 SPC Charts Dashboard (NEW)"
Cohesion: 0.50
Nodes (4): API Endpoints:, P3 SPC Charts Dashboard (NEW), Routes Created (`app/routes/spc_charts.py` ~4,000 lines):, Templates Created (5 HTML files, ~30KB total):

### Community 133 - "Current Session Execution Summary (2026-07-21)"
Cohesion: 0.50
Nodes (4): Current Session Execution Summary (2026-07-21), Files Verified:, Next Session Tasks:, Verification Checklist:

### Community 134 - "Phase 1: Database Schema Extensions - COMPLETE"
Cohesion: 0.50
Nodes (4): Files Created/Modified:, Model Extensions:, New Tables Created (9 total):, Phase 1: Database Schema Extensions - COMPLETE

### Community 135 - "Key Features Implemented in P3 Enhancement:"
Cohesion: 0.50
Nodes (4): Key Features Implemented in P3 Enhancement:, Req #13: End-to-End Traceability Viewer - COMPLETE, Req #14: SPC Charts with Cp/Cpk/Pp/Ppk - COMPLETE, Req #20-#21: Automated MTC Report Generation - COMPLETE

### Community 136 - "Migration File: `migrations/versions/YYYY_MM_DD_add_quality_schema.py`"
Cohesion: 0.50
Nodes (4): Additions (in order):, Backward Compatibility:, Database Migration Strategy, Migration File: `migrations/versions/YYYY_MM_DD_add_quality_schema.py`

### Community 137 - "activate_bom"
Cohesion: 0.67
Nodes (3): activate_bom(), Activate a specific BOM version, deactivating others for same part., Activate a specific BOM version, deactivating others for same part.

### Community 138 - "billets_list"
Cohesion: 0.67
Nodes (3): billets_list(), List all available billets for use in BOM creation dropdown.      Returns simpli, List all available billets for use in BOM creation dropdown.      Returns simpli

### Community 139 - "customers_list"
Cohesion: 0.67
Nodes (3): customers_list(), List all active customers with their part number mapping counts., List all active customers with their part number mapping counts.

### Community 140 - "delete_customer_part_mapping"
Cohesion: 0.67
Nodes (3): delete_customer_part_mapping(), Soft-delete a customer-to-part mapping., Soft-delete a customer-to-part mapping.

### Community 141 - "get_customer"
Cohesion: 0.67
Nodes (3): get_customer(), Get a single customer with their part number mappings., Get a single customer with their part number mappings.

### Community 142 - "get_part_number"
Cohesion: 0.67
Nodes (3): get_part_number(), Get a single part number with active BOM info., Get a single part number with active BOM info.

### Community 143 - "part_numbers_list"
Cohesion: 0.67
Nodes (3): part_numbers_list(), List all active part numbers with optional customer filter., List all active part numbers with optional customer filter.

### Community 145 - "Implementation Summary"
Cohesion: 0.67
Nodes (3): Implementation Summary, What's Complete:, What's Pending:

### Community 146 - "Next Steps: Ready for Testing & Deployment"
Cohesion: 0.67
Nodes (3): Next Steps: Ready for Testing & Deployment, **P3 COMPLETE - All Enhancement Items Done:**, Priority Order for Implementation:

## Knowledge Gaps
- **500 isolated node(s):** `entrypoint.sh script`, `DATABASE_URL`, `Overview`, `Session Execution Pattern`, `1. Check if Phase 1 migrations exist` (+495 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **26 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Die` connect `Assign a WO to a machine+day slot via drag-and-drop. AuditLo` to `.__repr__() ._extract_alloy_from_description() ._log_constra`, `.__repr__() ._seed_master() ._seed_wo() .tearDown()`, `BurnInSession CalibrationRecord Capa DefectRecord`, `.test_move_entry_endpoint() Create WorkOrders and ApsSchedul`, `AlloyComposition CostPriceConfig FinishingOrder FinishingPro`, `Get a single customer with their part number mappings. Get a`, `.__repr__() ._find_earliest_slot() ._find_earliest_slot_for_`, `DieInspection DieTest ERP adapter service — Lighthouse Info`, `Add a new line to a customer order with BOM validation. Crea`, `BilletInspection Create extrusion-chain genealogy events + t`, `APS routes  Two blueprints:   aps          – page views (/ap`, `Demo workspace for camera-based extrusion die visual inspect`, `.compute_die_lifetime() Aggregate die lifecycle data: avg cy`, `.setUp() .test_cockpit_page_loads_without_version() .test_cr`, `.evaluate_rules() Compute and persist foundry KPIs. Evaluate`, `Create a work order from a customer order line with BOM auto`, `Alarm OeeSnapshot create_app() run.py`, `Accept a Wattmon CSV POST (no authentication required).`, `Build a minimal Wattmon-format CSV blob (header + rows joine`, `.compute_shortage_risk() Alert Compute planning risk alerts`, `.setUp() Build a test app with in-memory SQLite. make_app()`, `Run scheduling with algorithm selection (FIFO / DUE_DATE / O`, `APS Gantt / scheduler view. scheduler()`, `DefectCode`, `DefectTrackingService`?**
  _High betweenness centrality (0.034) - this node is a cross-community bridge._
- **Why does `WorkOrder` connect `.__repr__() ._seed_master() ._seed_wo() .tearDown()` to `.__repr__() ._extract_alloy_from_description() ._log_constra`, `.to_dict() Assign routing to a product. Change routing statu`, `Check actual_composition against alloy composition tolerance`, `BurnInSession CalibrationRecord Capa DefectRecord`, `Alarm & Event History dashboard. DowntimeEvent Parse a datet`, `Edit an existing Station Full audit trail of every operation`, `Assign a WO to a machine+day slot via drag-and-drop. AuditLo`, `.test_move_entry_endpoint() Create WorkOrders and ApsSchedul`, `AlloyComposition CostPriceConfig FinishingOrder FinishingPro`, `.__repr__() ._find_earliest_slot() ._find_earliest_slot_for_`, `Add a new line to a customer order with BOM validation. Crea`, `Estimate cleaning time saved by grouping colors vs naive ord`, `BilletInspection Create extrusion-chain genealogy events + t`, `Furnace FurnaceSession HeatTreatmentProgram Seed furnaces, h`, `APS routes  Two blueprints:   aps          – page views (/ap`, `_parse_date() approve_shipment() create_package() create_shi`, `.__init__() ._load() .generate_work_orders() .test_generates`, `complete() create_ncr() create_order() detail()`, `.setUp() .test_cockpit_page_loads_without_version() .test_cr`, `Container ContainerMovement ContainerWeighEvent assign_wo()`, `PcbBoard PcbPanel UnitHistory board_detail()`, `BOMItem bom.py create_bom_item() detail()`, `Alarm OeeSnapshot create_app() run.py`, `Accept a Wattmon CSV POST (no authentication required).`, `mtc_reports.py`, `coating_schedule.py`, `stations.py`?**
  _High betweenness centrality (0.025) - this node is a cross-community bridge._
- **Why does `_EventView` connect `.__getattr__() .__init__() Material traceability - billet an` to `Assign a WO to a machine+day slot via drag-and-drop. AuditLo`?**
  _High betweenness centrality (0.014) - this node is a cross-community bridge._
- **Are the 159 inferred relationships involving `timedelta` (e.g. with `by_category()` and `by_machine()`) actually correct?**
  _`timedelta` has 159 INFERRED edges - model-reasoned connections that need verification._
- **Are the 23 inferred relationships involving `WorkOrder` (e.g. with `_get_recent_inspections()` and `kits()`) actually correct?**
  _`WorkOrder` has 23 INFERRED edges - model-reasoned connections that need verification._
- **Are the 23 inferred relationships involving `Die` (e.g. with `_get_changeover_metrics_by_shift()` and `_get_changeover_trends()`) actually correct?**
  _`Die` has 23 INFERRED edges - model-reasoned connections that need verification._
- **Are the 16 inferred relationships involving `Billet` (e.g. with `ApsTestCase` and `AutoScheduleTests`) actually correct?**
  _`Billet` has 16 INFERRED edges - model-reasoned connections that need verification._