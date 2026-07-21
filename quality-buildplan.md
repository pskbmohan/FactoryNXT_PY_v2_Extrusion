# Quality Reporting & Control System - Build Plan

## Context

**Why this change is being made:** The Global Aluminium quality team has identified critical gaps in their current manual quality assurance processes. They need automated systems for production performance dashboards, First Pass Yield tracking, scrap/rejection reporting, die performance analytics, process parameter traceability, SPC capability monitoring, and end-to-end material traceability from raw materials to customer delivery.

**Current pain points:**
- Manual die identification using punched numbers and ERP entry
- Manual dimension verification with Vernier instruments and handwritten reports
- Slow manual inspection unable to support real-time decision making
- Rejection quantities manually entered into ERP after inspection
- Material test certificate data compilation is difficult from ERP

**Intended outcome:** A comprehensive automated quality management system that captures machine/process/inspection/test data in real-time, provides instant dashboards for operators and management, enables zero-defect manufacturing through automatic alarm triggers when parameters exceed limits, and maintains full traceability for root cause analysis.

---

## Recommended Implementation Approach

This plan organizes the 22 identified requirements into **7 implementation phases** that build upon existing infrastructure in FactoryNXT-PY-v2-Extrusion:

### Phase 1: Database Schema Extensions (Foundation)
**Goal:** Add missing tables and columns to support quality tracking.

#### New Tables Required:

| Table Name | Purpose | Key Columns | Reuse Existing? |
|------------|---------|-------------|-----------------|
| `quality_parameters` | Store process parameter limits per profile/alloy | profile_code, alloy, billet_temp_min/max, container_temp_min/max, die_temp_min/max, exit_temp_min/max, ram_speed_min/max, pressure_min/max, force_min/max, cycle_time_min/max | No - new table |
| `parameter_readings` | Real-time parameter capture from PLC | run_id (FK), timestamp, billet_temp, container_temp, die_temp, exit_temp, ram_speed, main_cylinder_pressure, extrusion_force, cycle_time, stem_position, puller_speed, cooling_params | No - new table |
| `defect_codes` | Master list of defect types with categories | code, name, category (surface/functional/aesthetic/dimensional), severity, is_active | No - new table |
| `quality_inspections` | Unified inspection records across all stages | inspection_type, stage, wo_id, billet_id, die_id, operator_id, timestamp, results(JSON), pass_fail, measured_values(JSON) | Extend existing DieInspection/BilletInspection patterns |
| `test_events` | Mechanical/NDT test results | test_type (Webster/Barcol/Vickers/UTS/UT), wo_id, specimen_id, result_value, acceptance_limit, passed, tested_at, tester_id | No - new table |
| `alarm_breakdown_log` | Machine alarm and downtime tracking | machine_id, alarm_code, alarm_name, duration_min, started_at, ended_at, is_recurring | Extend Alarm model |
| `process_parameter_alerts` | Auto-triggered parameter violations | run_id, parameter_name, actual_value, threshold_low, threshold_high, triggered_at, auto_stop_triggered | No - new table |
| `spc_records` | SPC chart data points | wo_id, dimension_type, target_value, measured_value, upper_limit, lower_limit, sample_time, shift_group | No - new table |
| `material_traceability` | End-to-end traceability chain | batch_number, heat_number, billet_code, die_code, work_order_id, extrusion_timestamp, operator_id, process_params(JSON) | Extend genealogy.py patterns |

#### Existing Models to Extend:

1. **Die model** (already exists at `app/models.py:706`)
   - Add: `die_life_cycles_remaining` (calculated from press_count/press_count_limit)
   - Add: `last_failure_reason` 
   - Add: `total_setup_time_minutes` (cumulative)
   - Add: `average_setup_time_minutes` (computed)

2. **WorkOrder model** (already exists)
   - Extend to track FPY metrics at work order level
   - Link to quality_inspections and test_events

3. **KPIRecord model** (already exists)
   - Add new kpi_type values: "FPY", "PPM", "COPQ", "ENERGY_CONSUMPTION"

---

### Phase 2: Quality Data Services Layer
**Goal:** Create service classes for quality operations (following KPIEngine pattern).

#### New Service Classes:

```
app/services/
├── kpi_engine.py                    # Existing - keep and extend
├── quality_service.py               # NEW - core quality operations
│   ├── compute_fpy()                # First Pass Yield by profile/die/alloy/shift
│   ├── compute_ppm()                # Parts per million defect rate
│   ├── compute_rejection_rate()     # Internal/customer rejection %
│   ├── compute_opportunity_loss()   # COPQ calculation
├── parameter_monitoring_service.py  # NEW - process parameter tracking
│   ├── capture_parameter_reading()  # Store PLC-captured parameters
│   ├── check_parameter_limits()     # Validate against setpoints
│   ├── trigger_auto_stop()          # Machine stop on violation
│   └── generate_parameter_alerts()  # Create alerts for violations
├── defect_tracking_service.py       # NEW - defect management
│   ├── record_defect()              # Log defect with category/reason
│   ├── categorize_scrap()           # Sort scrap by type/die/operator/alloy
│   └── compute_scrap_rates()        # Scrap analytics
├── die_performance_service.py       # NEW - die lifecycle tracking
│   ├── track_die_usage()            # Count billets per die
│   ├── calculate_die_life_remaining()  % remaining life
│   ├── record_die_failure()         # Log failure reasons
│   └── compute_die_productivity()   # Output per die metric
├── inspection_service.py            # NEW - unified inspection handling
│   ├── create_inspection()          # Record dimension/process checks
│   ├── validate_first_piece()       # Pre-production verification
│   └── generate_mtc_report()        # Material Test Certificate generation
├── spc_engine.py                    # NEW - Statistical Process Control
│   ├── compute_xbar_r_charts()      # X-bar and R control charts
│   ├── compute_capability_indices() # Cp, Cpk, Pp, Ppk calculations
│   └── detect_control_violations()  # Out-of-control conditions
├── traceability_service.py          # NEW - end-to-end tracking
│   ├── build_traceability_chain()   # Link material to customer order
│   └── trace_complaint_root_cause() # Backward/forward tracing
└── maintenance_quality_service.py   # NEW - predictive maintenance inputs
    ├── track_hydraulic_oil_condition()
    ├── monitor_motor_vibration()
    ├── track_bearing_temperature()
    └── predict_component_life_remaining()
```

---

### Phase 3: Dashboard & Reporting Routes
**Goal:** Create Flask routes and templates for all dashboards.

#### New Blueprints to Add:

| Blueprint | Route Prefix | Purpose |
|-----------|--------------|---------|
| `quality_dashboard.py` | `/quality/dashboard` | Production Performance Dashboard (Req #1) |
| `fpy_reporting.py` | `/quality/fpy` | First Pass Yield reporting (Req #2) |
| `scrap_reporting.py` | `/quality/scrap` | Scrap and rejection analytics (Req #3) |
| `die_performance.py` | `/quality/die-perf` | Die performance metrics (Req #4) |
| `parameter_monitoring.py` | `/quality/parameters` | Process parameter traceability view (Req #5) |
| `alarm_downtime.py` | `/quality/alarm-downtime` | Alarm and breakdown monitoring (Req #6) |
| `changeover_analysis.py` | `/quality/changeover` | Changeover analysis dashboard (Req #7) |
| `quality_metrics.py` | `/quality/metrics` | Quality Metrics Dashboard with PPM, rework %, straightness, surface defects, bend-per-meter (Req #8-9) |
| `inspection_management.py` | `/quality/inspections` | Inspection frequency and method management (Req #10-12) |
| `traceability_viewer.py` | `/quality/traceability` | End-to-end traceability viewer (Req #13) |
| `spc_charts.py` | `/quality/spc` | SPC charts with Cp/Cpk/Pp/Ppk (Req #14) |
| `maintenance_quality.py` | `/quality/maintenance-quality` | Predictive maintenance quality linkage (Req #15) |
| `foundry_testing.py` | `/quality/foundry-testing` | Incoming and foundry-stage checks (Req #16-17) |
| `ndt_testing.py` | `/quality/ndt-testing` | Mechanical and NDT testing results (Req #18) |
| `inline_inspection.py` | `/quality/inline-inspection` | Automated inline inspection integration (Req #19) |
| `mtc_reports.py` | `/quality/mtc-reports` | Material Test Certificate generation (Req #20-21) |
| `management_kpi.py` | `/quality/management-kpi` | Management KPI Dashboard with OEE, FPY, production/scrap, downtime, energy, on-time delivery, COPQ, top 5 losses (Req #22) |

#### Existing Patterns to Follow:
- Use `dashboard.py` as template for multi-widget dashboard layouts
- Follow `kpi_alerts.py` pattern for KPI computation + display separation
- Reuse `genealogy.py` patterns for traceability views
- Extend `quality_ext.py` routes with quality domain features

---

### Phase 4: PLC Integration & Real-Time Parameter Capture
**Goal:** Enable automatic process parameter capture and alarm-triggered stops.

#### Existing Infrastructure to Leverage:
1. **PLC Adapter** (`app/services/plc_adapter.py`) - Already exists for setpoint loading
2. **Integration Jobs** (already exist) - For PLC_SETPOINT_LOAD, PLC_CAPTURE job types
3. **SetpointProfile model** (exists at `models.py:833`) - Use for parameter limits

#### Required Additions:
1. Extend `PLCAdapter` with methods to capture real-time parameters during extrusion runs
2. Create background task service that polls PLC every N seconds and writes to `parameter_readings` table
3. Implement threshold checking logic that triggers automatic machine stop when parameters exceed limits (per requirement #5)
4. Add HMI integration points for recipe-driven parameter control

---

### Phase 5: Automated Report Generation
**Goal:** Auto-generate daily QC reports, MTC/MTR documents, and customer-facing test certificates.

#### Implementation Approach:
1. **Template-based generation** using existing Jinja2 templates pattern
2. **PDF export capability** for Material Test Reports with:
   - Chemical composition data from `AlloyComposition` table
   - Mechanical properties (hardness, UTS) from `test_events` 
   - Batch/order references
3. **Scheduled report generation** using existing scheduler (`app/services/scheduler.py`)
4. **Customer portal integration** for MTC download

---

### Phase 6: Inline Inspection Automation Integration
**Goal:** Integrate automated visual/laser scanning and UT testing systems.

#### Required Integrations:
1. Visual inspection system API endpoints (image capture + comparison against golden board)
2. Laser-based dimension measurement data ingestion
3. UT testing machine integration for solid sections (360-degree scanning support)
4. Automated alert display when abnormalities detected
5. Red-light/visual indicator triggers on tolerance violations

---

### Phase 7: SPC Analytics & Capability Monitoring
**Goal:** Implement Statistical Process Control with control charts and capability indices.

#### Implementation Details:
1. **X-bar and R Charts** - Track dimension measurements over time with UCL/LCL boundaries
2. **Cp/Cpk Calculation** - Process capability (potential vs actual performance)
3. **Pp/Ppk Calculation** - Overall process performance metrics  
4. **Control Limit Violation Detection** - Auto-flag out-of-control conditions
5. **Trend Analysis** - Track capability degradation over time

---

## Database Migration Strategy

### Migration File: `migrations/versions/YYYY_MM_DD_add_quality_schema.py`

#### Additions (in order):
1. Create `quality_parameters` table with FK to profile/alloy constraints
2. Create `parameter_readings` table with indexes on run_id, timestamp
3. Create `defect_codes` master data table with category enum types
4. Extend existing inspection tables (`DieInspection`, `BilletInspection`) or create unified `quality_inspections` table
5. Create `test_events` table for mechanical/NDT testing
6. Create `alarm_breakdown_log` extending Alarm model patterns
7. Create `process_parameter_alerts` with auto-trigger flags
8. Create `spc_records` with shift_group indexing
9. Create `material_traceability` linking all traceable entities

#### Backward Compatibility:
- All new columns nullable during transition period
- Existing dashboards continue to work with NULL values (display as "Not Available")
- Migration includes seed data for default defect codes and parameter limits

---

## Verification & Testing Strategy

### End-to-End Test Scenarios:

1. **FPY Tracking:** Create work order → run extrusion → record first-piece inspection → verify FPY calculated correctly by profile/die/alloy/shift
2. **Scrap Reporting:** Log multiple defects with different categories → verify scrap reports aggregate correctly
3. **Die Performance:** Track die usage across multiple billets → compute life remaining, setup times, failure reasons
4. **Parameter Monitoring:** Simulate PLC parameter capture exceeding limits → verify auto-stop trigger and alert creation
5. **SPC Charts:** Input dimension measurements over shift → verify X-bar/R chart calculations and control violations detected
6. **Traceability:** Create end-to-end chain from billet through customer order → trace back from complaint to root cause
7. **MTC Generation:** Complete testing on work order → generate PDF certificate with all required data points

### Manual Testing Checklist:
- [ ] All 16 dashboard views render without errors
- [ ] Real-time parameter capture populates `parameter_readings` table within expected latency (<5 seconds)
- [ ] Auto-stop triggers when any parameter exceeds limits (test each parameter type)
- [ ] FPY calculation matches manual verification for sample work orders
- [ ] SPC control limits update dynamically as new data arrives
- [ ] MTC PDF exports contain all required fields and format correctly

---

## Existing Infrastructure to Reuse

### Models:
- `KPIRecord` - Persist quality KPIs (reuse pattern)
- `Alert/AlertRule` - Parameter violation alerts (extend usage)
- `Die/Billet/SetpointProfile/ProcessRun` - Core extrusion domain models
- `WorkOrder` - Link quality data to production orders

### Services:
- `KPIEngine` - Extend with FPY, PPM, COPQ computations
- `PLCAdapter` - Add real-time parameter capture methods
- `Scheduler` - Trigger automated report generation
- `IntegrationJob` - Track PLC/quality system sync status

### Routes/Templates:
- `dashboard.py` pattern for multi-widget layouts
- `kpi_alerts.py` pattern for KPI computation + display separation  
- `genealogy.py` patterns for traceability views
- Existing quality_ext templates as base for new views

---

## Implementation Priority Order

**P0 - Critical Path (Week 1-2):**
1. Database schema extensions (Phase 1)
2. Parameter monitoring service and real-time capture (Phase 4)
3. Production Performance Dashboard (Req #1)
4. First Pass Yield tracking (Req #2)

**P1 - High Priority (Week 3-4):**
5. Scrap/rejection reporting (Req #3)
6. Die performance analytics (Req #4)
7. Alarm/downtime monitoring (Req #6)
8. Quality metrics dashboard with PPM, surface defects, bend-per-meter (Req #8-9)

**P2 - Medium Priority (Week 5-6):**
9. Process parameter traceability view (Req #5)
10. Changeover analysis (Req #7)
11. Inspection management (Req #10-12)
12. End-to-end traceability viewer (Req #13)

**P3 - Enhancement (Week 7-8):**
13. SPC charts and capability monitoring (Req #14)
14. Maintenance-quality linkage (Req #15)
15. Foundry/testing stage checks (Req #16-18)
16. Inline inspection integration (Req #19)

**P4 - Advanced Features:**
17. Automated MTC report generation (Req #20-21)
18. Management KPI dashboard with COPQ, energy, on-time delivery (Req #22)

---

## Risk Mitigation

| Risk | Impact | Mitigation Strategy |
|------|--------|---------------------|
| PLC integration delays | High | Start with simulated data capture; parallelize template development while waiting for hardware access |
| Parameter limit configuration complexity | Medium | Provide default limits per alloy/profile; allow operator override with approval workflow |
| Real-time performance concerns | Low | Use database indexes on timestamp columns; paginate large query results; cache dashboard computations |
| Data quality from manual entry points | Medium | Implement validation rules at entry time; provide dropdowns for defect codes rather than free text |
| Auto-stop false positives | High | Require operator confirmation within N seconds before triggering full stop; add hysteresis to threshold checks |

---

## Success Metrics

- **FPY improvement:** Track baseline FPY vs. post-implementation target of 95% first-stroke pass rate
- **Scrap reduction:** Measure scrap by defect type before/after implementation
- **Report time savings:** Manual report preparation hours per week → automated generation (target: >80% reduction)
- **Traceability time:** Root cause analysis investigation time from hours to minutes
- **Parameter violation response:** Time from limit breach to auto-stop trigger (<1 second target)

---

## Next Steps After Plan Approval

1. Database migration script creation and review
2. Service layer implementation (quality_service.py, parameter_monitoring_service.py, etc.)
3. Dashboard route development following existing patterns
4. PLC integration testing with simulated data
5. Frontend template development for all 16 dashboards
6. End-to-end integration testing across all quality domains
