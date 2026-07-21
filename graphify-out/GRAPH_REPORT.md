# Graph Report - .  (2026-07-20)

## Corpus Check
- 374 files · ~243,936 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1111 nodes · 2472 edges · 88 communities (72 shown, 16 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 257 edges (avg confidence: 0.6)
- Token cost: 0 input · 0 output

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

## God Nodes (most connected - your core abstractions)
1. `WorkOrder` - 64 edges
2. `Die` - 45 edges
3. `ApsEngine` - 43 edges
4. `Machine` - 42 edges
5. `Billet` - 41 edges
6. `CustomerOrder` - 39 edges
7. `ApsScheduleEntry` - 35 edges
8. `main()` - 32 edges
9. `_u()` - 31 edges
10. `ApsTestCase` - 31 edges

## Surprising Connections (you probably didn't know these)
- `ApsTestCase` --uses--> `Config`  [INFERRED]
  tests/conftest.py → app/config.py
- `AutoScheduleTests` --uses--> `Machine`  [INFERRED]
  tests/test_aps_engine.py → app/models.py
- `ManualMoveTests` --uses--> `Machine`  [INFERRED]
  tests/test_aps_engine.py → app/models.py
- `WorkOrderGenerationTests` --uses--> `Machine`  [INFERRED]
  tests/test_aps_engine.py → app/models.py
- `GanttDataTests` --uses--> `Machine`  [INFERRED]
  tests/test_aps_routes.py → app/models.py

## Import Cycles
- 3-file cycle: `app/__init__.py -> app/routes/aps.py -> app/models.py -> app/__init__.py`
- 3-file cycle: `app/__init__.py -> app/routes/machines.py -> app/models.py -> app/__init__.py`

## Communities (88 total, 16 thin omitted)

### Community 0 - "._create_job() ._finalize() ._get_signals() .capture_actuals"
Cohesion: 0.05
Nodes (57): cutting(), die_oven(), final_cut(), hls(), hls_capture(), hls_capture_new(), hls_load(), index() (+49 more)

### Community 1 - ".__repr__() ._extract_alloy_from_description() ._log_constra"
Cohesion: 0.08
Nodes (16): Any, ApsScheduleEvent, Audit trail of changes to schedule entries (locks, overrides, replans)., ApsEngine, _as_datetime(), _new_id(), Manually move or reassign an APS entry.          Returns the updated entry plus, Coerce a date or datetime to datetime (midnight UTC). Returns None if None. (+8 more)

### Community 2 - ".__repr__() ._seed_master() ._seed_wo() .tearDown()"
Cohesion: 0.14
Nodes (33): ApsConstraintLog, ApsScheduleVersion, Records a scheduling constraint violation or warning for a version/entry., A named snapshot of the production schedule (active, draft, or archived)., Billet, CustomerOrder, Die, Line (+25 more)

### Community 3 - ".to_dict() Assign routing to a product. Change routing statu"
Cohesion: 0.06
Nodes (35): Visual Routing Builder models for FactoryNXT.  Separate file to avoid merge conf, Routing header – one record per routing revision., Links a product/part number to a specific routing revision., Frozen copy of routing steps taken when a Work Order is released.     Future cha, Individual step / operation in a routing., Directed connection between two routing steps (DAG edge)., RoutingConnection, RoutingMaster (+27 more)

### Community 4 - "Check actual_composition against alloy composition tolerance"
Cohesion: 0.06
Nodes (23): FeederReel, GoldenBoard, InventoryItem, InventoryLocation, Kit, PpapRecord, SolderPasteLot, inventory_form() (+15 more)

### Community 5 - "BurnInSession CalibrationRecord Capa DefectRecord"
Cohesion: 0.06
Nodes (18): BurnInSession, CalibrationRecord, Capa, DefectRecord, MaintenanceLog, PmSchedule, Stencil, TestResult (+10 more)

### Community 6 - "Alarm & Event History dashboard. DowntimeEvent Parse a datet"
Cohesion: 0.07
Nodes (18): DowntimeEvent, ProductionSchedule, ShiftCalendar, SmtLine, alarms(), detailed(), downtime_new(), Alarm & Event History dashboard. (+10 more)

### Community 7 - "Add a new material grade. Create a new alert threshold rule."
Cohesion: 0.06
Nodes (23): ElectronicSignature, OperatorCertification, Plant, UserProfile, machine_master(), machine_master_new(), process_params(), process_params_grade_new() (+15 more)

### Community 8 - "ApiKey Create a new PLC signal mapping. Decode + parse CSV b"
Cohesion: 0.06
Nodes (27): ApiKey, ErpSyncLog, Webhook, api_key_generate(), csv_upload(), erp_trigger(), hub(), job_retry() (+19 more)

### Community 9 - "Edit an existing Station Full audit trail of every operation"
Cohesion: 0.08
Nodes (27): OperationTransaction, Serial numbers generated when a Work Order is released., Full audit trail of every operation performed against a serial number., Workstation/Station used in routing and operation execution., SerialNumber, Station, get_operation_history(), get_serial_numbers() (+19 more)

### Community 10 - "Assign a WO to a machine+day slot via drag-and-drop. AuditLo"
Cohesion: 0.09
Nodes (25): AuditLog, ProcessPlan, availability(), create_work_order(), import_order(), optimize(), orders(), plan_vs_actual() (+17 more)

### Community 11 - "Block until the background worker flips status off 'pending'"
Cohesion: 0.10
Nodes (24): Metadata for each POST to /integrations/csv-upload., Entity-Attribute-Value: one row per (device_key, column_name, value, time-point), WattmonReading, WattmonUpload, Show one upload + its EAV readings as a flat (key, column, value) list.      For, wattmon_detail(), clean_db(), _poll_upload() (+16 more)

### Community 12 - ".test_move_entry_endpoint() Create WorkOrders and ApsSchedul"
Cohesion: 0.17
Nodes (23): erp_order_import_simulator(), erp_posting_simulator(), main(), Create WorkOrders and ApsScheduleEntry rows for realistic demo data.      Previo, Populate a realistic admin audit trail., Seed containers, weigh events, and movements., Simulate ERP polling for new customer orders. Creates a fresh order     each tim, Simulate ERP posting of unposted die records — demonstrates the     reprocess pa (+15 more)

### Community 13 - "AlloyComposition CostPriceConfig FinishingOrder FinishingPro"
Cohesion: 0.17
Nodes (19): AlloyComposition, CostPriceConfig, FinishingOrder, FinishingProcessType, MaterialReceipt, PackagingOrder, PackagingSpec, RawMaterialType (+11 more)

### Community 14 - "Get a single customer with their part number mappings. Get a"
Cohesion: 0.09
Nodes (21): billets_list(), boms_page(), customer_part_map_page(), customers_list(), customers_page(), dies_list(), get_customer(), get_part_number() (+13 more)

### Community 15 - ".__repr__() ._find_earliest_slot() ._find_earliest_slot_for_"
Cohesion: 0.14
Nodes (12): ApsScheduleEntry, APS models: MachineResourceMapping, WorkOrderResource, and the full Advanced Pla, One scheduled block: a work order assigned to a machine in a time window., _ceil30(), Return machines considered 'available' at the given instant.          A machine, Earliest time a machine is free, based on already-placed entries., Find the earliest feasible slot start on the machine for the WO.          Model:, Find earliest slot >= required_start on the machine for a specific slice duratio (+4 more)

### Community 16 - "DieInspection DieTest ERP adapter service — Lighthouse Info"
Cohesion: 0.13
Nodes (14): DieInspection, DieTest, ERPTransactionLog, NitridingRecord, die_inspect(), die_new(), die_nitride(), die_release() (+6 more)

### Community 17 - "CoatingColor CoatingScheduleEntry DieFurnaceLog DieRepairRec"
Cohesion: 0.15
Nodes (19): CoatingColor, CoatingScheduleEntry, DieFurnaceLog, DieRepairRecord, InspectionPlan, Integration, MaterialGrade, Role (+11 more)

### Community 18 - "Add a new line to a customer order with BOM validation. Crea"
Cohesion: 0.10
Nodes (19): add_order_line(), create_all_wo_for_order(), create_customer_order(), create_wo_for_line(), get_customer_order(), get_order_lines(), order_detail_page(), orders_list() (+11 more)

### Community 19 - "Estimate cleaning time saved by grouping colors vs naive ord"
Cohesion: 0.12
Nodes (9): RepairRecord, create_entry(), _parse_dt(), powder_savings(), Estimate cleaning time saved by grouping colors vs naive ordering., _json_field_like(), Return a filter expression matching JSON `column` containing key=value.      Wor, repair_new() (+1 more)

### Community 20 - "._call_erp() ._create_job() ._finalize_job() ._new_log_id()"
Cohesion: 0.24
Nodes (9): erp_reprocess(), Re-process a batch of unposted ERP records (inspections, tests, nitridings)., ERPAdapter, Post a DieInspection record to the ERP.          Creates an IntegrationJob (so i, Post a DieTest record to the ERP., Post a NitridingRecord to the ERP., Fetch customer orders from the ERP and create ``CustomerOrder`` rows.          I, Thin adapter that wraps ERP-facing calls with retry + audit. (+1 more)

### Community 21 - "BilletInspection Create extrusion-chain genealogy events + t"
Cohesion: 0.20
Nodes (16): BilletInspection, CutRecord, GenealogyEvent, IntegrationJob, OvenRecord, PLCSignalMapping, ProcessRun, QuenchRecord (+8 more)

### Community 22 - "Furnace FurnaceSession HeatTreatmentProgram Seed furnaces, h"
Cohesion: 0.17
Nodes (7): Furnace, FurnaceSession, HeatTreatmentProgram, create_program(), start_session(), Seed furnaces, heat treatment programs, and sessions., seed_furnace_module()

### Community 23 - "APS routes  Two blueprints:   aps          – page views (/ap"
Cohesion: 0.13
Nodes (9): api_move_entry(), api_publish(), api_release_entry(), api_unscheduled_wos(), APS routes  Two blueprints:   aps          – page views (/aps/cockpit, /aps/sche, Move a schedule entry to a new time slot / machine., Release a schedule entry to the shop floor (dispatch)., Publish the current DRAFT schedule version to the shop floor. (+1 more)

### Community 24 - "_parse_date() approve_shipment() create_package() create_shi"
Cohesion: 0.14
Nodes (4): create_package(), create_shipment(), _parse_date(), scan_package()

### Community 25 - ".__init__() ._load() .generate_work_orders() .test_generates"
Cohesion: 0.17
Nodes (7): _is_same_day(), Resolves per-day working windows for a plant.      Reads ShiftCalendar rows if a, Return ordered list of (start, end) datetime windows for a day., Create one WorkOrder per selected CustomerOrder.          Rules:           * Ski, _ShiftResolver, date, WorkOrderGenerationTests

### Community 26 - "Customer Customer master data for BOM-driven order managemen"
Cohesion: 0.21
Nodes (13): Customer, CustomerOrderLine, CustomerPartNumber, PartNumber, Customer master data for BOM-driven order management., Part number master data for BOM-driven order management., Mapping between customers and their approved part numbers., Individual line items within a customer order, linked to part numbers. (+5 more)

### Community 27 - "complete() create_ncr() create_order() detail()"
Cohesion: 0.16
Nodes (4): NCR, create_order(), reject(), create_ncr()

### Community 28 - "Demo workspace for camera-based extrusion die visual inspect"
Cohesion: 0.14
Nodes (7): create_die(), inspection(), inspection_scenarios(), Demo workspace for camera-based extrusion die visual inspection.      Renders a, Return the mock inspection scenarios as JSON.      Front-end demo uses this to i, send_to_furnace(), send_to_repair()

### Community 29 - ".compute_die_lifetime() Aggregate die lifecycle data: avg cy"
Cohesion: 0.17
Nodes (5): AlertRule, die_lifecycle(), KPI & Alerts blueprint.  Consolidates OEE-style metrics for extrusion with thres, rule_new(), Aggregate die lifecycle data: avg cycles, min/max, count by status.

### Community 30 - ".setUp() .test_cockpit_page_loads_without_version() .test_cr"
Cohesion: 0.24
Nodes (3): auth_session(), Set `username` in the session so auth-requiring routes resolve., VersionTests

### Community 31 - "Container ContainerMovement ContainerWeighEvent assign_wo()"
Cohesion: 0.24
Nodes (6): Container, ContainerMovement, ContainerWeighEvent, create_container(), move(), weigh()

### Community 32 - "API endpoint to get details of a specific upload.     Return"
Cohesion: 0.22
Nodes (10): csv_upload(), get_upload(), list_uploads(), API endpoint to get details of a specific upload.     Returns JSON with upload m, Dedicated API endpoint for Wattmon CSV upload.      Accepts: application/x-www-f, API endpoint to list recent Wattmon uploads.     Returns JSON array of upload me, _extract_wattmon_csv(), _process_wattmon_upload() (+2 more)

### Community 33 - ".compute_shortages() .optimize() Compute projected die/bille"
Cohesion: 0.18
Nodes (9): index(), Planning overview: orders, stock, availability snapshot., Projected die/billet shortages., shortages(), index(), Tool shop dashboard: die registry and pipeline overview., shortages(), Compute projected die/billet shortages.          Returns a dict with:         - (+1 more)

### Community 34 - ".evaluate_rules() Compute and persist foundry KPIs. Evaluate"
Cohesion: 0.25
Nodes (7): KPIEngine, KPI engine service.  Computes aggregate KPIs for the foundry domain: - OEE (avai, Evaluate active AlertRules against the provided KPI records.          Any rule b, Compute and persist foundry KPIs., Schedule optimizer service.  Implements a simple greedy algorithm that respects, Greedy scheduler for aluminum extrusion orders., ScheduleOptimizer

### Community 35 - "Config DigitalOcean App Platform injects DATABASE_URL as pos"
Cohesion: 0.22
Nodes (3): Config, _normalise_db_url(), DigitalOcean App Platform injects DATABASE_URL as postgres://...     SQLAlchemy

### Community 36 - "PcbBoard PcbPanel UnitHistory board_detail()"
Cohesion: 0.24
Nodes (5): PcbBoard, PcbPanel, UnitHistory, history_add(), panel_new()

### Community 37 - "BOMItem bom.py create_bom_item() detail()"
Cohesion: 0.25
Nodes (3): BOMItem, create_bom_item(), list_create_work_orders()

### Community 38 - "Gantt-style board combining legacy SMT schedule and new extr"
Cohesion: 0.22
Nodes (9): status(), api_gantt(), _entry_to_dict(), Return current schedule version data for the Gantt chart., Return (horizon_start, horizon_end) datetimes for a version., Serialise an ApsScheduleEntry to a JSON-safe dict.      All relationship accesse, _version_horizon(), Gantt-style board combining legacy SMT schedule and new extrusion plans. (+1 more)

### Community 39 - "Activate a specific BOM version, deactivating others for sam"
Cohesion: 0.25
Nodes (8): PartNumberBOM, Bill of Materials linking a part number to its die and billet types., activate_bom(), create_bom(), Create a new BOM version (auto-deactivates existing active BOM)., Update BOM by creating new version (same as create - versions are immutable)., Activate a specific BOM version, deactivating others for same part., update_bom()

### Community 40 - "APS cockpit dashboard. Build the full context dict required"
Cohesion: 0.25
Nodes (8): api_kpis(), _build_cockpit_context(), cockpit(), Build the full context dict required by aps/cockpit.html., APS cockpit dashboard., Return high-level KPI metrics for the current schedule., Return schedule entries for a version; swallow errors and return []., _safe_entries_for_version()

### Community 41 - "Create a work order from a customer order line with BOM auto"
Cohesion: 0.29
Nodes (7): get_active_bom(), Get the most recent active BOM for a part number.      Args:         part_number, Resolve BOM information for creating a work order.      This function looks up t, resolve_bom_for_wo(), create_wo_from_order_line(), Work Order service for BOM-driven WO creation from customer orders.  This module, Create a work order from a customer order line with BOM auto-resolution.      Th

### Community 42 - "Run migrations in 'offline' mode.      This configures the c"
Cohesion: 0.39
Nodes (7): get_engine(), get_engine_url(), get_metadata(), Run migrations in 'offline' mode.      This configures the context with just a U, Run migrations in 'online' mode.      In this scenario we need to create an Engi, run_migrations_offline(), run_migrations_online()

### Community 45 - "Return True if *column* already exists on *table*. Return Tr"
Cohesion: 0.33
Nodes (5): _column_exists(), Return True if *column* already exists on *table*., Return True if *table* already exists in the public schema., _table_exists(), upgrade()

### Community 46 - "20260704_wattmon_eav_schema.py Column definitions for the ne"
Cohesion: 0.33
Nodes (6): downgrade(), _eav_columns(), Wattmon: replace 216-column reading table with Entity-Attribute-Value schema  Re, Re-create the old wide table so that downgrading is non-destructive., Column definitions for the new EAV reading table., upgrade()

### Community 47 - "Alarm OeeSnapshot create_app() run.py"
Cohesion: 0.33
Nodes (4): create_app(), Alarm, OeeSnapshot, seed_plant_master_data()

### Community 48 - "Replan: preserve locked entries, reschedule the rest. Return"
Cohesion: 0.33
Nodes (6): _active_machines(), api_auto_schedule(), api_replan(), Run finite-capacity auto-scheduling and create a new schedule version., Return active machines, defensively handling the missing `is_active` column., Replan: preserve locked entries, reschedule the rest.

### Community 49 - "Accept a Wattmon CSV POST (no authentication required)."
Cohesion: 0.40
Nodes (6): csv_upload_submit(), _error_response(), Return True when the caller is a server / API client (not a browser form)., Accept a Wattmon CSV POST (no authentication required).      The integration dev, Return JSON for API callers or flash-and-redirect for browsers., _wants_json()

### Community 50 - ".__getattr__() .__init__() Material traceability - billet an"
Cohesion: 0.33
Nodes (4): _EventView, material_traceability(), Uniform wrapper so the material template can iterate over both     TraceabilityR, Material traceability - billet and die tracking.

### Community 51 - "._count_routing_steps() ._duration_for() ._routing_total_min"
Cohesion: 0.33
Nodes (3): Compute total line-cycle-time (minutes) from master routing data.          Looks, Compute run duration for a WO.          Priority:           1. Sum of RoutingSte, Count routing steps for the WO's part (helper for overhead calc).

### Community 52 - "Test a single endpoint with form-encoded payload. Test backw"
Cohesion: 0.47
Nodes (5): main(), Test a single endpoint with form-encoded payload., Test backward compatibility with /integrations/csv-upload., test_older_endpoint(), test_payload()

### Community 53 - "Build a minimal Wattmon-format CSV blob (header + rows joine"
Cohesion: 0.33
Nodes (6): build_csv(), Build a minimal Wattmon-format CSV blob (header + rows joined by \\r\\n)., POST with key=<MAC> + data=<header\\r\\nrow1\\r\\nrow2>     Should return 200 +, POST with data=<csv> but no key.     Should return 200 + "OK"; source_key = "unk, test_csv_upload_missing_key(), test_csv_upload_standard_form()

### Community 54 - "Extrusion traceability dashboard - shows material flow and p"
Cohesion: 0.40
Nodes (4): genealogy_view(), Extrusion traceability dashboard - shows material flow and process events., Process genealogy - track work orders and process runs., traceability_dashboard()

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
Cohesion: 0.40
Nodes (4): app(), Thread that runs ``target(*args, **kwargs)`` synchronously in the     current th, Create a Flask app for testing with a file-backed SQLite DB.      We use a tempf, _SyncThread

### Community 59 - ".compute_shortage_risk() Alert Compute planning risk alerts"
Cohesion: 0.50
Nodes (3): Alert, KPIRecord, Compute planning risk alerts due to die/billet shortages.          Returns a dic

### Community 60 - ".__repr__() MachineResourceMapping Maps a part number to req"
Cohesion: 0.50
Nodes (3): MachineResourceMapping, Maps a part number to required machine resources (machine, die, consumables, tim, create_mapping()

## Knowledge Gaps
- **2 isolated node(s):** `entrypoint.sh script`, `DATABASE_URL`
  These have ≤1 connection - possible missing edges or undocumented components.
- **16 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `WorkOrder` connect `.__repr__() ._seed_master() ._seed_wo() .tearDown()` to `.__repr__() ._extract_alloy_from_description() ._log_constra`, `.to_dict() Assign routing to a product. Change routing statu`, `Check actual_composition against alloy composition tolerance`, `BurnInSession CalibrationRecord Capa DefectRecord`, `Alarm & Event History dashboard. DowntimeEvent Parse a datet`, `Edit an existing Station Full audit trail of every operation`, `Assign a WO to a machine+day slot via drag-and-drop. AuditLo`, `.test_move_entry_endpoint() Create WorkOrders and ApsSchedul`, `.__repr__() ._find_earliest_slot() ._find_earliest_slot_for_`, `CoatingColor CoatingScheduleEntry DieFurnaceLog DieRepairRec`, `Add a new line to a customer order with BOM validation. Crea`, `Estimate cleaning time saved by grouping colors vs naive ord`, `BilletInspection Create extrusion-chain genealogy events + t`, `Furnace FurnaceSession HeatTreatmentProgram Seed furnaces, h`, `APS routes  Two blueprints:   aps          – page views (/ap`, `_parse_date() approve_shipment() create_package() create_shi`, `.__init__() ._load() .generate_work_orders() .test_generates`, `Customer Customer master data for BOM-driven order managemen`, `complete() create_ncr() create_order() detail()`, `.setUp() .test_cockpit_page_loads_without_version() .test_cr`, `Container ContainerMovement ContainerWeighEvent assign_wo()`, `PcbBoard PcbPanel UnitHistory board_detail()`, `BOMItem bom.py create_bom_item() detail()`, `Create a work order from a customer order line with BOM auto`, `.test_api_aps_entries() .test_api_aps_events() .test_api_aps`, `._count_routing_steps() ._duration_for() ._routing_total_min`, `Extrusion traceability dashboard - shows material flow and p`?**
  _High betweenness centrality (0.064) - this node is a cross-community bridge._
- **Why does `Billet` connect `.__repr__() ._seed_master() ._seed_wo() .tearDown()` to `._create_job() ._finalize() ._get_signals() .capture_actuals`, `.__repr__() ._extract_alloy_from_description() ._log_constra`, `.evaluate_rules() Compute and persist foundry KPIs. Evaluate`, `BurnInSession CalibrationRecord Capa DefectRecord`, `Assign a WO to a machine+day slot via drag-and-drop. AuditLo`, `.test_api_aps_entries() .test_api_aps_events() .test_api_aps`, `.test_move_entry_endpoint() Create WorkOrders and ApsSchedul`, `AlloyComposition CostPriceConfig FinishingOrder FinishingPro`, `Get a single customer with their part number mappings. Get a`, `CoatingColor CoatingScheduleEntry DieFurnaceLog DieRepairRec`, `Add a new line to a customer order with BOM validation. Crea`, `BilletInspection Create extrusion-chain genealogy events + t`, `Extrusion traceability dashboard - shows material flow and p`, `.__init__() ._load() .generate_work_orders() .test_generates`, `Customer Customer master data for BOM-driven order managemen`, `.setUp() .test_cockpit_page_loads_without_version() .test_cr`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **Why does `Machine` connect `.__repr__() ._seed_master() ._seed_wo() .tearDown()` to `.__repr__() ._extract_alloy_from_description() ._log_constra`, `.evaluate_rules() Compute and persist foundry KPIs. Evaluate`, `BurnInSession CalibrationRecord Capa DefectRecord`, `Alarm & Event History dashboard. DowntimeEvent Parse a datet`, `Add a new material grade. Create a new alert threshold rule.`, `ApiKey Create a new PLC signal mapping. Decode + parse CSV b`, `Assign a WO to a machine+day slot via drag-and-drop. AuditLo`, `.test_api_aps_entries() .test_api_aps_events() .test_api_aps`, `AlloyComposition CostPriceConfig FinishingOrder FinishingPro`, `.__repr__() ._find_earliest_slot() ._find_earliest_slot_for_`, `Alarm OeeSnapshot create_app() run.py`, `CoatingColor CoatingScheduleEntry DieFurnaceLog DieRepairRec`, `BilletInspection Create extrusion-chain genealogy events + t`, `APS routes  Two blueprints:   aps          – page views (/ap`, `.__init__() ._load() .generate_work_orders() .test_generates`, `.compute_die_lifetime() Aggregate die lifecycle data: avg cy`, `.setUp() .test_cockpit_page_loads_without_version() .test_cr`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `datetime` (e.g. with `api_auto_schedule_v2()` and `.test_ceil30_rounds_up()`) actually correct?**
  _`datetime` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `WorkOrder` (e.g. with `kits()` and `weekly_assign()`) actually correct?**
  _`WorkOrder` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 52 inferred relationships involving `timedelta` (e.g. with `api_auto_schedule()` and `api_auto_schedule_v2()`) actually correct?**
  _`timedelta` has 52 INFERRED edges - model-reasoned connections that need verification._
- **Are the 16 inferred relationships involving `Die` (e.g. with `ApsTestCase` and `AutoScheduleTests`) actually correct?**
  _`Die` has 16 INFERRED edges - model-reasoned connections that need verification._