#!/usr/bin/env python3
"""FactoryNXT foundry demo seed + ERP/PLC simulators.

Usage:
  # Apply migrations first:
  flask db upgrade

  # Then, from project root:
  python scripts/seed_data.py

  Or inside Docker:
  docker-compose exec web python scripts/seed_data.py

All seed functions are idempotent (skip if rows exist) so they can be
re-run after schema resets safely.
"""
import os
import sys
import uuid
import random
from datetime import datetime, timedelta, date

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

random.seed(42)

from app import create_app, db
from app.models import (
    Line, Machine, Alarm, Station,
    CustomerOrder, Die, DieInspection, DieTest, NitridingRecord,
    Billet, BilletInspection, MaterialGrade,
    SetpointProfile, ProcessRun, QuenchRecord, CutRecord,
    StretchRecord, OvenRecord,
    AlertRule, Alert, KPIRecord, IntegrationJob, PLCSignalMapping,
    Plant, Role, UserProfile, Integration,
    WorkOrder, PcbPanel, PcbBoard, UnitHistory, SmtLine, OeeSnapshot, DowntimeEvent,
    ProcessPlan, ProductionSchedule, AuditLog, GenealogyEvent, TraceabilityRecord,
    InspectionPlan,
)
from app.models_aps import (
    ApsScheduleVersion, ApsScheduleEntry, ApsConstraintLog, ApsScheduleEvent,
)
from app.models_routing import RoutingMaster, RoutingStepV2
from app.services.aps_engine import ApsEngine

def _u():
    return str(uuid.uuid4())


# ── Seed data ────────────────────────────────────────────────────────────
def seed_plant_master_data():
    print("[1/12] Seeding plant master data (lines / machines / stations) ...")
    if Line.query.first():
        print("  skipped")
        return

    lines = [Line(name=n, status=s) for n, s in [
        ("Extrusion Line 1", "Running"), ("Extrusion Line 2", "Running"), ("Extrusion Line 3", "Idle"),
    ]]
    db.session.add_all(lines)
    db.session.flush()

    # Machine name prefixes must align with process-line logic (HLS/Press/Quench/Pull/Stretch/Oven)
    machine_specs = [
        (lines[0].id, "HLS-01", "Running"), (lines[0].id, "Press-01", "Running"),
        (lines[0].id, "Quench-01", "Running"), (lines[0].id, "Puller-01", "Running"),
        (lines[0].id, "Stretch-01", "Running"), (lines[0].id, "Oven-01", "Running"),
        (lines[1].id, "HLS-02", "Running"), (lines[1].id, "Press-02", "Idle"),
        (lines[1].id, "Quench-02", "Running"), (lines[1].id, "Puller-02", "Running"),
        (lines[1].id, "Stretch-02", "Idle"), (lines[1].id, "Oven-02", "Running"),
        (lines[2].id, "HLS-03", "Idle"), (lines[2].id, "Press-03", "Idle"),
        (lines[2].id, "Quench-03", "Idle"), (lines[2].id, "Puller-03", "Idle"),
        (lines[2].id, "Stretch-03", "Idle"), (lines[2].id, "Oven-03", "Idle"),
    ]
    machines = [Machine(line_id=l, name=n, status=s) for l, n, s in machine_specs]
    db.session.add_all(machines)
    db.session.flush()  # persist machine IDs so alarms can reference them

    alarms = [
        Alarm(machine_id=machines[1].id, severity="CRITICAL",
              message="Hydraulic pressure < 120 bar (setpoint 180)", is_active=True),
        Alarm(machine_id=machines[8].id, severity="WARNING",
              message="Quench water temperature +5C above target", is_active=True),
        Alarm(machine_id=machines[3].id, severity="INFO",
              message="PM schedule due in 48h", is_active=False),
    ]
    db.session.add_all(alarms)

    stations = [Station(name=n, code=c, description=d, is_active=True) for n, c, d in [
        ("Billet Preheat", "BILLET_PH", "Billet preheating furnace station"),
        ("HLS", "HLS", "Hot Log Shear - billet cropping"),
        ("Pressing", "PRESS", "Main extrusion press"),
        ("Quenching", "QUENCH", "Water / air / mist quench station"),
        ("Puller", "PULL", "Profile puller station"),
        ("Stretching", "STRETCH", "Stretcher / straightener"),
        ("Final Cut", "CUT", "Final cut with segregation"),
        ("Die Oven", "OVEN", "Die preheat / aging oven"),
    ]]
    db.session.add_all(stations)

    print(f"  added {len(lines)} lines, {len(machines)} machines, {len(alarms)} alarms, {len(stations)} stations")


def seed_material_grades():
    print("[2/12] Seeding material grades ...")
    if MaterialGrade.query.first():
        print("  skipped"); return
    grades = [
        MaterialGrade(id=_u(), code="6061-T6", name="Aluminum 6061-T6",
                      alloy_family="6xxx", density=2.70, melting_point=652.0),
        MaterialGrade(id=_u(), code="6063-T5", name="Aluminum 6063-T5",
                      alloy_family="6xxx", density=2.68, melting_point=654.0),
        MaterialGrade(id=_u(), code="6082-T6", name="Aluminum 6082-T6",
                      alloy_family="6xxx", density=2.70, melting_point=650.0),
        MaterialGrade(id=_u(), code="7075-T6", name="Aluminum 7075-T6",
                      alloy_family="7xxx", density=2.81, melting_point=635.0),
    ]
    db.session.add_all(grades)
    print(f"  added {len(grades)} material grades")


def seed_customer_orders():
    print("[3/12] Seeding customer orders (ERP import simulator) ...")
    if CustomerOrder.query.first():
        print("  skipped"); return
    customers = ["AutoTech GmbH", "BuildPro Inc", "MetroRail Co", "SolarField AG", "AeroSpaceParts Ltd"]
    alloys = ["6061-T6", "6063-T5", "6082-T6", "7075-T6"]
    profiles = ["Window Frame WF-100", "Door Frame DF-55", "Hollow Bar HB-40",
                "Channel CH-80", "Heat Sink HS-20", "I-Beam IB-120"]
    today = date.today()
    orders = []
    for i in range(18):
        orders.append(CustomerOrder(
            id=_u(),
            order_number=f"CO-{2026 + i:04d}",
            customer_name=random.choice(customers),
            product_profile=random.choice(profiles),
            alloy=random.choice(alloys),
            quantity_tons=round(random.uniform(0.5, 18.0), 2),
            due_date=today + timedelta(days=random.randint(-5, 30)),
            erp_reference=f"SAP-{random.randint(500000, 599999)}",
            status=random.choice(["CONFIRMED", "IN_PROGRESS", "CONFIRMED", "DRAFT", "CONFIRMED"]),
        ))
    db.session.add_all(orders)
    print(f"  added {len(orders)} customer orders")


def seed_dies_and_workflow():
    print("[4/12] Seeding dies + inspection/test/nitriding workflow ...")
    if Die.query.first():
        print("  skipped"); return
    suppliers = ["DieTech AG", "Precision Tooling Ltd", "Extrusion Master GmbH"]
    locations = ["A-1", "A-2", "B-1", "B-3", "C-2", "C-4", "D-1", "D-2"]
    # Weight distribution: most dies Available, few Rejected
    statuses = ["Available"] * 10 + ["Inspected", "TestingPending", "TestingPassed",
               "NitridingPending", "Nitrided", "Nitrided", "Rework", "Rejected"]
    inspectors = ["A. Kumar", "S. Smith", "M. Garcia"]; testers = ["P. Rao", "J. Chen", "T. Brown"]
    nitride_ops = ["R. Singh", "A. Patel"]; dies = []
    for i in range(24):
        st = random.choice(statuses)
        dies.append(Die(
            id=_u(), die_code=f"DIE-{2000 + i:04d}", profile_code=f"P{100 + (i % 8):03d}",
            alloy=random.choice(["6061", "6063", "6082"]),
            supplier=random.choice(suppliers), location=random.choice(locations),
            status=st, life_cycles_total=random.randint(0, 800),
            last_inspected_at=datetime.now() - timedelta(days=random.randint(5, 90)) if st != "New" else None,
            last_tested_at=datetime.now() - timedelta(days=random.randint(5, 90)) if st in ("TestingPassed", "NitridingPending", "Nitrided", "Available") else None,
            last_nitrided_at=datetime.now() - timedelta(days=random.randint(5, 120)) if st in ("Nitrided", "Available") else None,
            erp_asset_id=f"ERP-A{1000 + i:04d}",
        ))
    db.session.add_all(dies)

    inspections = [DieInspection(
        id=_u(), die_id=d.id, inspection_date=(d.last_inspected_at or datetime.now()).date()
        if hasattr(d.last_inspected_at, 'date') else (d.last_inspected_at or datetime.now()),
        inspector=random.choice(inspectors),
        dimensions_ok=random.random() > 0.2, surface_ok=random.random() > 0.3,
        hardness=round(random.uniform(58, 65), 1),
        notes="OK" if random.random() > 0.2 else "Minor surface pitting",
        erp_posted=random.random() > 0.4
    ) for d in dies[:14]]
    db.session.add_all(inspections)

    tests = [DieTest(
        id=_u(), die_id=d.id, test_date=d.last_tested_at or datetime.now(),
        tester=random.choice(testers), press_force=random.randint(85, 100),
        temperature=random.randint(460, 490),
        profile_quality=random.choice(["A", "B", "C"]),
        result="PASS" if random.random() > 0.15 else "FAIL",
        erp_posted=random.random() > 0.4
    ) for d in dies[6:18]]
    db.session.add_all(tests)

    nitridings = [NitridingRecord(
        id=_u(), die_id=d.id,
        furnace_id=f"FUR-{random.randint(1, 3):02d}",
        start_temp=random.randint(500, 515), end_temp=random.randint(530, 545),
        duration_hours=random.randint(8, 14), atmosphere="NH3",
        hardness_before=round(random.uniform(55, 60), 1),
        hardness_after=round(random.uniform(65, 72), 1),
        operator=random.choice(nitride_ops), erp_posted=random.random() > 0.35
    ) for d in dies[10:18]]
    db.session.add_all(nitridings)
    print(f"  added {len(dies)} dies, {len(inspections)} inspections, {len(tests)} tests, {len(nitridings)} nitridings")


def seed_inspection_plans():
    """Seed extrusion-relevant inspection plans (AQL sampling) for dies,
    billets, profiles, bundles, process stages, and machine setups."""
    print("[4b] Seeding inspection plans ...")
    if InspectionPlan.query.first():
        print("  skipped"); return
    dies = Die.query.limit(6).all()
    billets = Billet.query.limit(4).all()
    profile_codes = sorted({
        d.profile_code for d in Die.query.filter(Die.profile_code.isnot(None)).all()
        if d.profile_code
    })[:3]

    plans = []

    # Die inspection plans (inward dimensional + surface check)
    for d in dies[:3]:
        plans.append(InspectionPlan(
            id=_u(),
            part_number=d.die_code,
            operation_name="DIE_INSPECTION",
            target_type="DIE",
            target_code=d.die_code,
            operation_step="DIE_INSPECTION",
            aql_level="1.0",
            sample_size=20,
            accept_limit=0,
            reject_limit=1,
        ))

    # Billet incoming inspection
    for b in billets[:2]:
        plans.append(InspectionPlan(
            id=_u(),
            part_number=b.billet_code,
            operation_name="INWARD",
            target_type="BILLET",
            target_code=b.billet_code,
            operation_step="INWARD",
            aql_level="2.5",
            sample_size=50,
            accept_limit=2,
            reject_limit=3,
        ))

    # Profile dimension check after pressing
    for pcode in profile_codes[:2]:
        plans.append(InspectionPlan(
            id=_u(),
            part_number=pcode,
            operation_name="PRESSING",
            target_type="PROFILE",
            target_code=pcode,
            operation_step="PRESSING",
            aql_level="2.5",
            sample_size=80,
            accept_limit=2,
            reject_limit=3,
        ))

    # Bundle / pack final inspection
    plans.append(InspectionPlan(
        id=_u(),
        part_number="BUNDLE-FINAL-001",
        operation_name="FINAL_INSPECTION",
        target_type="BUNDLE",
        target_code="BUNDLE-FINAL-001",
        operation_step="FINAL_INSPECTION",
        aql_level="4.0",
        sample_size=32,
        accept_limit=3,
        reject_limit=4,
    ))

    # Process stage plans (HLS, Quenching, Stretching)
    for stage, aql in [("HLS", "2.5"), ("QUENCHING", "2.5"), ("STRETCHING", "2.5")]:
        plans.append(InspectionPlan(
            id=_u(),
            part_number=f"STAGE-{stage}",
            operation_name=stage,
            target_type="PROCESS_STAGE",
            target_code=stage,
            operation_step=stage,
            aql_level=aql,
            sample_size=50,
            accept_limit=2,
            reject_limit=3,
        ))

    # Machine setup verification (start of shift / die change)
    plans.append(InspectionPlan(
        id=_u(),
        part_number="SETUP-PRESS-01",
        operation_name="MACHINE_SETUP",
        target_type="MACHINE_SETUP",
        target_code="PRESS-01",
        operation_step="MACHINE_SETUP",
        aql_level="1.0",
        sample_size=5,
        accept_limit=0,
        reject_limit=1,
    ))

    db.session.add_all(plans)
    print(f"  +{len(plans)} inspection plans")


def seed_billets():
    print("[5/12] Seeding billets ...")
    if Billet.query.first():
        print("  skipped"); return
    suppliers = ["Primedex Metals", "AL-Co Billets", "Hydro Billet"]
    billets, today = [], date.today()
    for i in range(20):
        billets.append(Billet(
            id=_u(), billet_code=f"BIL-{5000 + i:04d}",
            alloy=random.choice(["6061", "6063", "6082"]),
            diameter_mm=random.choice([152.0, 178.0, 203.0, 229.0]),
            length_mm=650.0, supplier=random.choice(suppliers),
            lot_number=f"LOT-{random.randint(10000, 19999)}",
            quantity_kg=round(random.uniform(90, 130), 1),
            status=random.choice(["AVAILABLE", "AVAILABLE", "INSPECTED", "CONSUMED"]),
        ))
    db.session.add_all(billets)
    insps = [BilletInspection(
        id=_u(), billet_id=b.id, inspection_date=today - timedelta(days=random.randint(1, 30)),
        inspector=random.choice(["K. Li", "D. Meyer"]),
        chemical_composition={"Si": round(random.uniform(0.3, 0.6), 3),
                              "Fe": round(random.uniform(0.15, 0.35), 3),
                              "Cu": round(random.uniform(0.01, 0.08), 3),
                              "Mg": round(random.uniform(0.7, 1.2), 3)},
        temperature=round(random.uniform(20, 25), 1), result="PASS",
        notes=f"Billet {b.billet_code} - nominal composition verified",
    ) for b in billets[:8]]
    db.session.add_all(insps)
    print(f"  added {len(billets)} billets, {len(insps)} inspections")


def seed_setpoint_profiles():
    print("[6/12] Seeding setpoint profiles ...")
    if SetpointProfile.query.first():
        print("  skipped"); return
    profiles = [
        SetpointProfile(id=_u(), process_type="HLS", alloy="6061", profile_code="P100",
                        parameters={"billet_temp_c": 460, "ram_speed_mms": 6.5, "target_force_ton": 1800}, version=1, is_active=True),
        SetpointProfile(id=_u(), process_type="HLS", alloy="6063", profile_code="P100",
                        parameters={"billet_temp_c": 450, "ram_speed_mms": 7.0, "target_force_ton": 1600}, version=1, is_active=True),
        SetpointProfile(id=_u(), process_type="PRESSING", alloy="6061", profile_code="*",
                        parameters={"container_temp_c": 460, "ram_speed_mms": 5.0, "max_pressure_bar": 280}, version=1, is_active=True),
        SetpointProfile(id=_u(), process_type="PRESSING", alloy="6063", profile_code="*",
                        parameters={"container_temp_c": 450, "ram_speed_mms": 5.5, "max_pressure_bar": 260}, version=1, is_active=True),
        SetpointProfile(id=_u(), process_type="QUENCHING", alloy="6061", profile_code="*",
                        parameters={"quench_type": "Water", "target_exit_temp_c": 520, "cooling_rate_cs": 50}, version=1, is_active=True),
        SetpointProfile(id=_u(), process_type="QUENCHING", alloy="6063", profile_code="*",
                        parameters={"quench_type": "Air", "target_exit_temp_c": 530, "cooling_rate_cs": 25}, version=1, is_active=True),
        SetpointProfile(id=_u(), process_type="STRETCHING", alloy="6061", profile_code="*",
                        parameters={"tension_setpoint_pct": 1.5, "target_force_kn": 25}, version=1, is_active=True),
        SetpointProfile(id=_u(), process_type="STRETCHING", alloy="6063", profile_code="*",
                        parameters={"tension_setpoint_pct": 1.2, "target_force_kn": 22}, version=1, is_active=True),
        SetpointProfile(id=_u(), process_type="OVEN", alloy="6061", profile_code="*",
                        parameters={"set_temp_c": 175, "soak_time_min": 120}, version=1, is_active=True),
    ]
    db.session.add_all(profiles)
    print(f"  added {len(profiles)} setpoint profiles")


def seed_process_runs_and_records():
    print("[7/12] Seeding process runs and sensor records (last 7 days) ...")
    if ProcessRun.query.first():
        print("  skipped"); return
    machines = Machine.query.all()
    if not machines:
        print("  skipped (no machines)"); return

    name_to_machine = {m.name: m for m in machines}
    now = datetime.now()
    # Map process types to machine name prefixes
    proc_machine_prefix = {"hls": ["HLS"], "pressing": ["Press"], "quenching": ["Quench"],
                           "puller": ["Puller"], "cutting": ["Puller"],  # same station
                           "stretching": ["Stretch"], "oven": ["Oven"]}
    runs, quench_recs, cut_recs, stretch_recs, oven_recs = [], [], [], [], []

    for i in range(55):
        process_type = random.choice(list(proc_machine_prefix.keys()))
        prefix = random.choice(proc_machine_prefix[process_type])
        machine = random.choice([m for m in machines if m.name.startswith(prefix)]) if any(
            m.name.startswith(prefix) for m in machines) else random.choice(machines)
        hours_back = random.uniform(0.5, 168)  # 0.5..168h = 7 days
        started = now - timedelta(hours=hours_back)
        duration = random.uniform(15, 75)
        ended = started + timedelta(minutes=duration)
        run = ProcessRun(id=_u(), process_type=process_type,
                         machine_id=str(machine.id),  # model field is String of int id
                         operator_id=random.choice(["OP-001", "OP-002", "OP-003"]),
                         billet_id=None, die_id=None,
                         started_at=started, ended_at=ended,
                         status=random.choices(["COMPLETED", "COMPLETED", "FAILED"], weights=[9, 9, 2])[0])
        runs.append(run); runs_and_records = [(run, machine, started, ended)]

        if process_type == "quenching":
            # Synthesize temp sensor readings from ~490C down to ~240C
            temps = [round(490 - (490 - 240) * (t / 10), 1) for t in range(11)]
            quench_recs.append(QuenchRecord(id=_u(), run_id=run.id,
                quench_type=random.choice(["Water", "Air", "Mist"]),
                sensor_temperatures=temps,
                start_time=started, end_time=ended))
        elif process_type in ("puller", "cutting"):
            target = random.choice([6000.0, 6500.0, 7000.0])
            cut_recs.append(CutRecord(id=_u(), run_id=run.id,
                target_length_mm=target,
                actual_length_mm=target + random.uniform(-8, 8),
                cut_method="AUTO" if random.random() > 0.1 else "MANUAL",
                sensor_data={"laser_sensor_mm": round(target + random.uniform(-3, 3), 2),
                             "vision_confidence": round(random.uniform(0.92, 0.99), 3)},
                segregation_status="COMPLIED"))
        elif process_type == "stretching":
            stretch_recs.append(StretchRecord(id=_u(), run_id=run.id,
                tension_actual=round(random.uniform(20, 30), 2),
                tension_setpoint=25.0,
                position_transducer_reading=round(random.uniform(0.45, 0.65), 3),
                pressure_transducer_reading=round(random.uniform(175, 210), 1)))
        elif process_type == "oven":
            oven_recs.append(OvenRecord(id=_u(), run_id=run.id,
                oven_id=f"OVEN-{random.randint(1, 3):02d}",
                set_temperature=175.0,
                actual_temperature=175.0 + random.uniform(-4, 4),
                soak_time_minutes=random.uniform(115, 130)))

    db.session.add_all(runs)
    db.session.add_all(quench_recs + cut_recs + stretch_recs + oven_recs)
    print(f"  added {len(runs)} runs — {len(quench_recs)} quench, {len(cut_recs)} cut, "
          f"{len(stretch_recs)} stretch, {len(oven_recs)} oven records")


def seed_plc_signal_mappings():
    print("[8/12] Seeding PLC signal mappings (simulator) ...")
    if PLCSignalMapping.query.first():
        print("  skipped"); return
    mapping_specs = [
        # (machine_name, signal_tag, signal_type, unit, process_type, scale, offset)
        ("HLS-01", "DB101.DBD0", "SETPOINT", "C", "HLS", 1.0, 0.0),
        ("HLS-01", "DB101.DBD4", "ACTUAL", "C", "HLS", 1.0, 0.0),
        ("HLS-01", "DB101.DBD8", "SETPOINT", "mm/s", "HLS", 1.0, 0.0),
        ("HLS-01", "DB101.DBD12", "ACTUAL", "mm/s", "HLS", 1.0, 0.0),
        ("HLS-01", "DB101.DBX0.0", "ALARM", "", "HLS", 1.0, 0.0),
        ("Press-01", "DB201.DBD0", "SETPOINT", "bar", "PRESSING", 0.01, 0.0),
        ("Press-01", "DB201.DBD4", "ACTUAL", "bar", "PRESSING", 0.01, 0.0),
        ("Press-01", "DB201.DBD8", "ACTUAL", "C", "PRESSING", 1.0, 0.0),
        ("Press-01", "DB201.DBD12", "ACTUAL", "ton", "PRESSING", 0.01, 0.0),
        ("Press-01", "DB201.DBX0.0", "ALARM", "", "PRESSING", 1.0, 0.0),
        ("Quench-01", "DB301.DBD0", "SETPOINT", "C", "QUENCHING", 1.0, 0.0),
        ("Quench-01", "DB301.DBD4", "ACTUAL", "C", "QUENCHING", 1.0, 0.0),
        ("Quench-01", "DB301.DBD8", "ACTUAL", "l/min", "QUENCHING", 1.0, 0.0),
        ("Puller-01", "DB401.DBD0", "SETPOINT", "mm", "CUTTING", 1.0, 0.0),
        ("Puller-01", "DB401.DBD4", "ACTUAL", "mm", "CUTTING", 1.0, 0.0),
        ("Stretch-01", "DB501.DBD0", "SETPOINT", "%", "STRETCHING", 1.0, 0.0),
        ("Stretch-01", "DB501.DBD4", "ACTUAL", "%", "STRETCHING", 1.0, 0.0),
        ("Stretch-01", "DB501.DBD8", "ACTUAL", "kN", "STRETCHING", 0.01, 0.0),
        ("Oven-01", "DB601.DBD0", "SETPOINT", "C", "OVEN", 1.0, 0.0),
        ("Oven-01", "DB601.DBD4", "ACTUAL", "C", "OVEN", 1.0, 0.0),
    ]
    mappings = [PLCSignalMapping(id=_u(), machine_name=mn, signal_tag=st, signal_type=sig,
        unit=u, process_type=pt, scale_factor=sf, offset=of, is_active=True)
        for mn, st, sig, u, pt, sf, of in mapping_specs]
    db.session.add_all(mappings)
    print(f"  added {len(mappings)} PLC signal mappings")


def seed_integration_jobs():
    print("[9/12] Seeding integration jobs + ERP transaction log records ...")
    if IntegrationJob.query.first():
        print("  skipped"); return
    now = datetime.now()
    jobs = []
    # ERP jobs: inspection/test/nitriding posted with mostly success, a few failures
    for i in range(18):
        failed = random.random() < 0.2
        jobs.append(IntegrationJob(id=_u(),
            job_type=random.choice(["ERP_POST_INSPECTION", "ERP_POST_TEST", "ERP_POST_NITRIDING"]),
            status="Failed" if failed else "Success",
            payload={"die_code": f"DIE-{random.randint(2000, 2023):04d}",
                     "erp_asset_id": f"ERP-A{random.randint(1000, 1023):04d}"},
            result={"code": 500, "error": "ERP timeout"} if failed else {"code": 200, "tx_id": f"TX-{random.randint(1000, 9999)}"},
            retries=3 if failed else 0, max_retries=3,
            started_at=now - timedelta(hours=random.randint(1, 72)),
            completed_at=now - timedelta(hours=random.randint(0, 48)) if not failed else None))
    # PLC jobs
    for i in range(15):
        failed = random.random() < 0.15
        jobs.append(IntegrationJob(id=_u(),
            job_type=random.choice(["PLC_SETPOINT_LOAD", "PLC_CAPTURE"]),
            status="Failed" if failed else "Success",
            payload={"machine": random.choice(["HLS-01", "Press-01", "Quench-01"]),
                     "signal_count": random.randint(3, 8)},
            result={"error": "PLC timeout"} if failed else {"ok": True},
            retries=3 if failed else 0, max_retries=3,
            started_at=now - timedelta(hours=random.randint(1, 72))))
    db.session.add_all(jobs)
    print(f"  added {len(jobs)} integration jobs")


def seed_alert_rules():
    print("[10/12] Seeding alert rules ...")
    if AlertRule.query.first():
        print("  skipped"); return
    rules = [
        AlertRule(id=_u(), name="Press force out of range", metric="press_force",
                  operator="BETWEEN", threshold_value={"low": 250, "high": 300}, severity="CRITICAL", is_active=True),
        AlertRule(id=_u(), name="Quench exit temp high", metric="quench_exit_temp",
                  operator="GT", threshold_value={"value": 560}, severity="WARNING", is_active=True),
        AlertRule(id=_u(), name="Die rejection rate", metric="die_rejection_rate",
                  operator="GT", threshold_value={"value": 5}, severity="WARNING", is_active=True),
        AlertRule(id=_u(), name="OEE below target", metric="oee",
                  operator="LT", threshold_value={"value": 75}, severity="WARNING", is_active=True),
        AlertRule(id=_u(), name="Die shortage", metric="die_available_count",
                  operator="LT", threshold_value={"value": 5}, severity="CRITICAL", is_active=True),
        AlertRule(id=_u(), name="Sync integration failures", metric="integration_failures_1h",
                  operator="GT", threshold_value={"value": 10}, severity="WARNING", is_active=True),
    ]
    db.session.add_all(rules)
    print(f"  added {len(rules)} alert rules")


def seed_alerts():
    print("[11/12] Seeding alerts ...")
    if Alert.query.first():
        print("  skipped"); return
    rules = AlertRule.query.all()
    now = datetime.now()
    alerts = [
        Alert(id=_u(), rule_id=rules[0].id if rules else None, severity="CRITICAL",
              title="Press-01 force exceeded 320 bar",
              message="Hydraulic force 322 bar > setpoint 280 bar. Auto-reduced.",
              source="PROCESS_LINE", source_id="Press-01", status="Open"),
        Alert(id=_u(), rule_id=rules[2].id if rules else None, severity="WARNING",
              title="Die rejection rate at 8.3%", message="Trend above 5% threshold (7-day rolling).",
              source="DIE", status="Acknowledged",
              acknowledged_by="P.Rao", acknowledged_at=now - timedelta(hours=3)),
        Alert(id=_u(), rule_id=rules[3].id if rules else None, severity="WARNING",
              title="Line-1 OEE dropped to 72.4%", message="Shift OEE below 75% target.",
              source="PLANNING", status="Open"),
        Alert(id=_u(), severity="CRITICAL",
              title="Die stock critically low", message="Only 3 dies available; forecast shows 2-day shortage.",
              source="PLANNING", status="Open"),
        Alert(id=_u(), severity="WARNING",
              title="ERP sync job failed", message="ERP_POST_NITRIDING job failed (timeout). 3 retries exhausted.",
              source="INTEGRATION", status="Open"),
        Alert(id=_u(), severity="INFO",
              title="PLC capture drift", message="DB301.DBD4 reading drift detected; calibration recommended.",
              source="INTEGRATION", status="Closed",
              acknowledged_by="K.Li", acknowledged_at=now - timedelta(days=1),
              closed_at=now - timedelta(hours=22)),
    ]
    db.session.add_all(alerts)
    print(f"  added {len(alerts)} alerts")


def seed_kpi_records():
    print("[12/12] Seeding KPI records (last 7 days) ...")
    if KPIRecord.query.first():
        print("  skipped"); return
    today = date.today(); kpis = []
    # OEE per day, per machine (6 running machines only)
    running_machines = [m.id for m in Machine.query.filter(Machine.status.in_(["Running", "Idle"])).limit(6).all()]
    for day_offset in range(7):
        d = today - timedelta(days=day_offset)
        for m_id in running_machines:
            kpis.append(KPIRecord(id=_u(), kpi_type="OEE", machine_id=str(m_id),
                                  shift_date=d, value=round(random.uniform(70, 92), 1),
                                  unit="%",
                                  details={"availability": round(random.uniform(85, 98), 1),
                                           "performance": round(random.uniform(80, 95), 1),
                                           "quality": round(random.uniform(95, 99.5), 1)}))
        # One throughput record per line/day
        kpis.append(KPIRecord(id=_u(), kpi_type="THROUGHPUT", machine_id=None,
                              shift_date=d, value=round(random.uniform(4.5, 7.5), 2),
                              unit="t/h", details={"unit": "tons"}))
        kpis.append(KPIRecord(id=_u(), kpi_type="REJECTION_RATE", machine_id=None,
                              shift_date=d, value=round(random.uniform(0.5, 4.5), 2),
                              unit="%"))
        kpis.append(KPIRecord(id=_u(), kpi_type="DIE_LIFETIME", machine_id=None,
                              shift_date=d, value=round(random.uniform(400, 800), 0),
                              unit="cycles"))
        kpis.append(KPIRecord(id=_u(), kpi_type="MACHINE_DOWNTIME", machine_id=None,
                              shift_date=d, value=round(random.uniform(15, 95), 0),
                              unit="min"))
    db.session.add_all(kpis)
    print(f"  added {len(kpis)} KPI records")


# ── ERP / PLC simulators ──────────────────────────────────────────────
def erp_order_import_simulator():
    """Simulate ERP polling for new customer orders. Creates a fresh order
    each time the script runs to show live data ingestion."""
    print("\n[ERP SIM] Polling for new customer orders ...")
    before = CustomerOrder.query.count()
    today = date.today()
    new_count = random.randint(1, 3)
    for i in range(new_count):
        n = CustomerOrder.query.count()
        db.session.add(CustomerOrder(
            id=_u(), order_number=f"CO-2026-{1000 + before + i:04d}",
            customer_name=random.choice(["FreshAuto GmbH", "NewBuild Inc", "QuickRail"]),
            product_profile=random.choice(["Frame FR-10", "Beam BM-50"]),
            alloy=random.choice(["6061-T6", "6063-T5"]),
            quantity_tons=round(random.uniform(1.0, 8.0), 2),
            due_date=today + timedelta(days=random.randint(10, 40)),
            erp_reference=f"SAP-{random.randint(700000, 799999)}",
            status="CONFIRMED"))
    db.session.commit()
    print(f"  +{new_count} new orders imported (total now: {CustomerOrder.query.count()})")


def plc_live_signal_simulator():
    """Simulate a PLC reading live signal values from machines. Writes a
    fresh ProcessRun for the last cycle and a corresponding sensor record.

    Also demonstrates an intentional PLC-CAPTURE integration job."""
    print("[PLC SIM] Capturing current machine cycle ...")
    machines = Machine.query.filter_by(status="Running").all()
    if not machines:
        print("  no running machines, skip"); return
    machine = random.choice(machines)
    now = datetime.now()
    # Decide process_type from machine name prefix
    prefix = machine.name.split("-")[0].rstrip("01234567890")
    if prefix == "Puller": prefix = "Puller"
    process_type = {"HLS": "hls", "Press": "pressing", "Quench": "quenching",
                    "Puller": "puller", "Stretch": "stretching", "Oven": "oven"}.get(prefix, "hls")
    run = ProcessRun(id=_u(), process_type=process_type,
                     machine_id=str(machine.id), operator_id="PLC-AUTO",
                     started_at=now - timedelta(minutes=random.randint(5, 30)),
                     ended_at=now, status="COMPLETED")
    db.session.add(run); db.session.flush()
    # Create record matching process_type
    if process_type == "quenching":
        db.session.add(QuenchRecord(id=_u(), run_id=run.id, quench_type="Water",
                                    sensor_temperatures=[round(490 - i * 25 + random.uniform(-2, 2), 1) for i in range(11)],
                                    start_time=run.started_at, end_time=run.ended_at))
    elif process_type in ("puller", "cutting"):
        db.session.add(CutRecord(id=_u(), run_id=run.id, target_length_mm=6000.0,
                                 actual_length_mm=6000.0 + random.uniform(-5, 5),
                                 cut_method="AUTO", sensor_data={"laser_sensor_mm": 6000},
                                 segregation_status="COMPLIED"))
    elif process_type == "stretching":
        db.session.add(StretchRecord(id=_u(), run_id=run.id, tension_actual=round(random.uniform(20, 30), 2),
                                     tension_setpoint=25.0,
                                     position_transducer_reading=round(random.uniform(0.45, 0.65), 3),
                                     pressure_transducer_reading=round(random.uniform(175, 210), 1)))
    elif process_type == "oven":
        db.session.add(OvenRecord(id=_u(), run_id=run.id, oven_id="OVEN-01",
                                  set_temperature=175.0,
                                  actual_temperature=175.0 + random.uniform(-4, 4),
                                  soak_time_minutes=random.uniform(115, 130)))
    # Log a PLC integration job (success 85%, failure 15%)
    success = random.random() > 0.15
    db.session.add(IntegrationJob(id=_u(),
        job_type="PLC_CAPTURE", status="Success" if success else "Failed",
        payload={"machine": machine.name, "run_id": run.id},
        result={"ok": True} if success else {"error": "PLC read timeout"},
        retries=0 if success else 1,
        started_at=now - timedelta(seconds=30), completed_at=now if success else None))
    db.session.commit()
    print(f"  +1 live {process_type.upper()} run on {machine.name}, status={'SUCCESS' if success else 'FAILED (will retry)'}")


def erp_posting_simulator():
    """Simulate ERP posting of unposted die records — demonstrates the
    reprocess pathway used by /integrations/erp/reprocess."""
    print("[ERP SIM] Posting unposted die workflow records ...")
    from app.models import DieInspection, DieTest, NitridingRecord
    unposted = (
        DieInspection.query.filter_by(erp_posted=False).count() +
        DieTest.query.filter_by(erp_posted=False).count() +
        NitridingRecord.query.filter_by(erp_posted=False).count())
    if unposted == 0:
        print("  no unposted records"); return

    # Mark all unposted as posted (simulating a successful batch run)
    for ins in DieInspection.query.filter_by(erp_posted=False).all():
        ins.erp_posted = True
    for tst in DieTest.query.filter_by(erp_posted=False).all():
        tst.erp_posted = True
    for nit in NitridingRecord.query.filter_by(erp_posted=False).all():
        nit.erp_posted = True
    db.session.add(IntegrationJob(id=_u(), job_type="ERP_REPROCESS_BATCH",
        status="Success", payload={"scope": "inspections+tests+nitridings"},
        result={"posted": unposted}, started_at=datetime.now(), completed_at=datetime.now()))
    db.session.commit()
    print(f"  posted {unposted} records to ERP (batch ERP_REPROCESS_BATCH job)")


# ── APS seed: schedule version + finite-capacity plan + demo scenarios ────
def seed_aps_data():
    """Seed the Advanced Planning System with realistic data."""
    print("[APS-1/3] Seeding APS schedule version + auto-schedule …")
    if ApsScheduleVersion.query.first():
        print("  skipped (version already exists)")
        return

    machines = Machine.query.all()
    orders = CustomerOrder.query.limit(8).all()
    if not machines or not orders:
        print("  skipped (need machines + orders)")
        return

    version = ApsScheduleVersion(
        id=_u(), name="Active Schedule", version_type="ACTIVE",
        planning_horizon_days=14, published_at=datetime.now(),
        created_by="seed",
    )
    db.session.add(version)
    db.session.flush()

    # Generate WOs from the first 6 customer orders (if not already generated)
    co_ids = [o.id for o in orders[:6]]
    wo_result = ApsEngine.generate_work_orders(co_ids, created_by="seed")
    print(f"  +{len(wo_result.get('created', []))} WOs from customer orders "
          f"({len(wo_result.get('errors', []))} skipped)")

    # Add deliberate edge-case WOs (beyond auto-generated ones) for demo
    today = date.today()
    edge_wos = [
        WorkOrder(
            id=_u(), order_number=f"WO-APS-{4000+i}",
            part_number=f"PROFILE-P{500+i}",
            description=f"Edge-case {i}: {['overdue', 'urgent-no-die', 'locked-manual', 'split-run'][i % 4]}",
            quantity=2 + i, priority=p,
            status="DRAFT",
            due_date=today + timedelta(days=dd),
        )
        for i, (dd, p) in enumerate([(-3, "Urgent"), (1, "Urgent"), (7, "High"), (10, "Medium")])
    ]
    db.session.add_all(edge_wos)
    db.session.flush()

    # Auto-schedule all WOs on the active version (finite capacity).
    schedule_result = ApsEngine.auto_schedule(
        version_id=version.id,
        horizon_days=14,
        planned_by="seed",
        preserve_locked=True,
    )
    print(f"  auto-schedule: placed={schedule_result['placed']}, "
          f"preserved_locked={schedule_result['preserved_locked']}, "
          f"unassigned={len(schedule_result['unassigned'])}, "
          f"constraint_logs={schedule_result['constraint_logs']}")

    # ── Demo scenarios: locked entry, maintenance block, due_date at risk ──
    print("[APS-2/3] Adding locked / maintenance / due-at-risk demo scenarios …")
    entries = ApsScheduleEntry.query.filter_by(version_id=version.id).all()
    if entries:
        # Lock the first entry (planner override demo)
        first = entries[0]
        first.is_locked = True
        first.locked_by = "seed-planner"
        first.locked_at = datetime.now()
        first.lock_reason = "Demonstration: planner-locked entry not moved by replan"
        db.session.add(ApsScheduleEvent(
            id=_u(), version_id=version.id, entry_id=first.id,
            event_type="LOCKED",
            old_values={"is_locked": False},
            new_values={"is_locked": True, "reason": first.lock_reason},
            triggered_by="seed-planner",
        ))

        # Mark one entry's WO overdue by backdating scheduled_start
        if len(entries) > 1:
            late = entries[1]
            if late.work_order:
                late.work_order.due_date = today - timedelta(days=2)
                late.constraint_status = "WARNING"
                late.constraint_reasons = list(late.constraint_reasons or [])
                late.constraint_reasons.append("DUE_DATE_AT_RISK")
                db.session.add(ApsConstraintLog(
                    id=_u(), version_id=version.id,
                    work_order_id=late.work_order.id, entry_id=late.id,
                    reason_code="DUE_DATE_AT_RISK",
                    message=(
                        f"WO {late.work_order.order_number}: demo scheduled-end "
                        f"{late.scheduled_end:%Y-%m-%d} exceeds backdated due date."
                    ),
                    severity="WARNING",
                ))

    # Add a synthetic maintenance block on machine HLS-01 (today 14:00 → +2h)
    maint_start = datetime.now().replace(hour=14, minute=0, second=0, microsecond=0)
    maint_end = maint_start + timedelta(hours=2)
    maint_machine = Machine.query.filter_by(name="HLS-01").first() or Machine.query.first()
    if maint_machine:
        db.session.add(DowntimeEvent(
            id=_u(), machine_id=str(maint_machine.id),
            reason_code="Scheduled PM", reason_category="Mechanical",
            started_at=maint_start, ended_at=maint_end,
            duration_min=120, notes="APS seed: planned preventive maintenance block",
            reported_by="seed-planner",
        ))
        # Synthesize a maintenance-bar entry so it shows on the Gantt as a block
        # (no WO attached — placeholder that the scheduler treats as kept-forever)
        db.session.add(ApsScheduleEntry(
            id=_u(), version_id=version.id,
            machine_id=maint_machine.id,
            scheduled_start=maint_start, scheduled_end=maint_end,
            sequence_order=999,
            is_locked=True, status="PLANNED",
            constraint_status="FEASIBLE",
            constraint_reasons=["MACHINE_MAINTENANCE"],
            priority="Maintenance",
            setup_duration_min=0,
            notes=f"Planned maintenance on {maint_machine.name}",
        ))
        print(f"  +maintenance block on {maint_machine.name} "
              f"{maint_start:%Y-%m-%d %H:%M}-{maint_end:%H:%M}")

    # ── Constraint log samples for the shortages panel ─────────────────────
    print("[APS-3/3] Adding sample constraint-log rows for shortages panel …")
    sample_logs = [
        ("DIE_NOT_AVAILABLE", "No '6061' die available for alloy 6061 — only 6063/Nitrided dies in stock", "CRITICAL"),
        ("BILLET_SHORTAGE", "Insufficient billets with alloy=6082: demand 4, available 2", "WARNING"),
        ("MACHINE_MAINTENANCE", "Press-03 is in maintenance today 14:00–16:00", "WARNING"),
        ("NO_CAPACITY_IN_HORIZON", "WO-APS-4001 cannot be placed: all machines already full within 14-day horizon", "CRITICAL"),
    ]
    for code, msg, sev in sample_logs:
        db.session.add(ApsConstraintLog(
            id=_u(), version_id=version.id,
            reason_code=code, message=msg, severity=sev,
        ))

    print(f"  +{len(sample_logs)} sample constraint-log rows (die/billet/machine/capacity)")


# ── Main orchestrator ───────────────────────────────────────────────────
def seed_admin_master():
    print("[15/18] Seeding plant / roles / users / integrations ...")
    if Plant.query.first() and Integration.query.first() and UserProfile.query.first():
        print("  skipped"); return

    plants = [
        Plant(id=_u(), code="PLT-01", name="Extrusion Plant Pune", timezone="Asia/Kolkata"),
        Plant(id=_u(), code="PLT-02", name="Extrusion Plant Chennai", timezone="Asia/Kolkata"),
    ]; db.session.add_all(plants)

    roles = [
        Role(id=_u(), name="admin", display_name="Plant Administrator", permissions=["*"]),
        Role(id=_u(), name="planner", display_name="Production Planner", permissions=["planning.*", "tool_shop.*"]),
        Role(id=_u(), name="operator", display_name="Process Line Operator", permissions=["process_line.*"]),
        Role(id=_u(), name="quality_mgr", display_name="Quality Manager", permissions=["quality_ext.*", "traceability.*"]),
    ]; db.session.add_all(roles)
    db.session.flush()

    users = [
        UserProfile(id=_u(), plant_id=plants[0].id, role_id=roles[0].id,
                    full_name="Arjun Kapadia", employee_id="EMP-001", role="Plant Admin", is_active=True),
        UserProfile(id=_u(), plant_id=plants[0].id, role_id=roles[1].id,
                    full_name="Priya Raman", employee_id="EMP-002", role="Production Planner", is_active=True),
        UserProfile(id=_u(), plant_id=plants[0].id, role_id=roles[2].id,
                    full_name="Rahul Singh", employee_id="EMP-003", role="Line Operator", is_active=True),
        UserProfile(id=_u(), plant_id=plants[0].id, role_id=roles[2].id,
                    full_name="Suresh Menon", employee_id="EMP-004", role="Line Operator", is_active=True),
        UserProfile(id=_u(), plant_id=plants[0].id, role_id=roles[3].id,
                    full_name="Neha Iyer", employee_id="EMP-005", role="Quality Manager", is_active=True),
        UserProfile(id=_u(), plant_id=plants[0].id, role_id=roles[3].id,
                    full_name="Anil Desai", employee_id="EMP-006", role="Quality Engineer", is_active=True),
        UserProfile(id=_u(), plant_id=plants[1].id, role_id=roles[0].id,
                    full_name="Kavita Rao", employee_id="EMP-007", role="Plant Admin", is_active=True),
    ]; db.session.add_all(users)

    integrations = [
        Integration(name="SAP S/4HANA", description="ERP — sales orders, master data, asset posting", is_active=True),
        Integration(name="Siemens PCS7 OPC-UA", description="PLC bridge for Press/Puller/HLS stations", is_active=True),
        Integration(name="Keyence Vision", description="Final cut vision sensor for segregation", is_active=True),
        Integration(name="Trend Control MQTT", description="Quench/oven temperature telemetry", is_active=True),
        Integration(name="Renishaw CMM", description="Die inspection dimensional data", is_active=False),
    ]; db.session.add_all(integrations)
    print(f"  +{len(plants)} plants, {len(roles)} roles, {len(users)} users, {len(integrations)} integrations")


def seed_work_orders_and_traceability():
    print("[16/18] Seeding work orders + PCB panels/boards + unit history (traceability) ...")
    if WorkOrder.query.first() and PcbBoard.query.first() and UnitHistory.query.first():
        print("  skipped"); return

    machines = Machine.query.all()
    if not machines: print("  skipped — no machines"); return

    orders = [
        WorkOrder(id=f"WO-{202601+i:04d}", order_number=f"WO-{202601+i:04d}",
                  part_number=f"P{100+i%6:03d}", description=f"Frame/Beam production run {i+1}",
                  quantity=100 + i*5, status=s,
                  due_date=datetime.now() + timedelta(days=random.randint(-5, 30)),
                  priority=random.choice(["High", "Medium", "Low"]),
                  released_at=datetime.now() - timedelta(days=i+1),
                  started_at=datetime.now() - timedelta(hours=4*i),
                  completed_at=datetime.now() - timedelta(hours=4*i-4) if s == "COMPLETED" else None)
        for i, s in enumerate(["RELEASED", "RUNNING", "COMPLETED", "RUNNING", "RELEASED",
                                "COMPLETED", "DRAFT", "RUNNING"])]
    db.session.add_all(orders); db.session.flush()

    smt_line = SmtLine(id=_u(), plant_id="PLT-01", name="Extrusion Line 1",
                       code="EL-01", is_active=True) if not SmtLine.query.first() else SmtLine.query.first()
    db.session.add(smt_line); db.session.flush()

    panels, boards = [], []
    for wo in orders[:6]:
        panel = PcbPanel(id=_u(), wo_id=wo.id,
                         panel_serial=f"PAN-{1000 + len(boards)//3:04d}",
                         board_count=3, status="In-Assembly")
        db.session.add(panel); panels.append(panel)
        for b in range(3):
            boards.append(PcbBoard(id=_u(), panel_id=panel.id, wo_id=wo.id,
                                   serial_number=f"BRD-{1000*2+len(boards):05d}-{b}",
                                   status=random.choice(["in_progress", "completed", "completed"])))
    db.session.add_all(boards); db.session.flush()

    # UnitHistory — 3-4 operations per board
    histories = []
    for brd in boards:
        for op in ["HLS", "Press", "Quench", "Cut"]:
            histories.append(UnitHistory(
                id=_u(), board_id=brd.id, operation_name=op,
                status=random.choice(["OK", "OK", "OK", "NG"]) if brd.status != "in_progress" else "OK",
                machine_id=str(random.choice(machines).id),
                process_parameters={"temp_c": random.randint(450, 500),
                                     "force_ton": random.randint(150, 280),
                                     "cycle_sec": random.randint(45, 90)}))
    db.session.add_all(histories)
    print(f"  +{len(orders)} WOs, {len(panels)} panels, {len(boards)} boards, {len(histories)} history records")


def seed_oee_and_downtime():
    print("[17/18] Seeding OEE snapshots + downtime events ...")
    if OeeSnapshot.query.first() and DowntimeEvent.query.first():
        print("  skipped"); return

    machines = Machine.query.all()
    if not machines: return
    smt_lines = SmtLine.query.all()
    if not smt_lines: return
    smt = smt_lines[0]
    today = date.today()
    snaps = []
    for m in machines[:9]:  # first 9 machines
        for day_offset in range(7):
            d = today - timedelta(days=day_offset)
            avail = random.uniform(0.85, 0.98)
            perf = random.uniform(0.80, 0.96)
            qual = random.uniform(0.95, 0.99)
            planned = 480.0
            snaps.append(OeeSnapshot(
                id=random.randint(10**12, 10**13), machine_id=str(m.id), smt_line_id=smt.id,
                shift_date=d, shift_name="Day-Shift",
                planned_production_time_min=planned,
                downtime_min=planned*(1.0-avail),
                speed_loss_min=planned*avail*(1.0-perf),
                defect_loss_min=planned*avail*perf*(1.0-qual),
                availability=avail, performance=perf, quality=qual,
                oee=avail*perf*qual,
                units_planned=200, units_produced=int(200*avail*perf),
                units_defective=int(200*avail*perf*(1.0-qual)),
            ))
    db.session.add_all(snaps)

    downtimes = []
    reasons = ["Hydraulic pressure low", "Sensor drift", "Scheduled PM", "Material changeover",
               "Quench water flow", "Die change", "Power outage"]
    for m in machines[:6]:
        n = random.randint(2, 5)
        for _ in range(n):
            started = datetime.now() - timedelta(days=random.uniform(0.5, 6.0))
            dur = random.uniform(8, 95)
            downtimes.append(DowntimeEvent(
                id=_u(), machine_id=str(m.id),
                reason_code=random.choice(reasons),
                reason_category=random.choice(["Mechanical", "Electrical", "Process", "Facility"]),
                started_at=started, ended_at=started + timedelta(minutes=dur),
                duration_min=dur, notes="Auto-logged",
                reported_by=random.choice(["R.Singh", "S.Menon", "A.Patel"])))
    db.session.add_all(downtimes)
    print(f"  +{len(snaps)} OEE snapshots, +{len(downtimes)} downtime events")


def seed_routing_data():
    print("[18/18] Seeding routing master data ...")
    if RoutingMaster.query.first():
        print("  skipped")
        return

    stations = Station.query.all()
    if not stations:
        print("  skipped - no stations")
        return

    # Create routing masters for each profile
    profiles = [
        {"product_id": "PROF-A1", "routing_code": "RT-PROF-A1", "routing_name": "Profile A1 Standard"},
        {"product_id": "PROF-B2", "routing_code": "RT-PROF-B2", "routing_name": "Profile B2 Standard"},
        {"product_id": "PROF-C3", "routing_code": "RT-PROF-C3", "routing_name": "Profile C3 Standard"},
    ]

    routings = []
    for profile in profiles:
        routing = RoutingMaster(
            id=_u(),
            routing_code=profile["routing_code"],
            routing_name=profile["routing_name"],
            product_id=profile["product_id"],
            revision="1.0",
            description="Standard routing for extrusion profile",
            status="RELEASED"
        )
        db.session.add(routing)
        db.session.flush()  # Get the routing ID
        routings.append(routing)

        # Create routing steps (5 steps matching the process flow)
        step_names = ["HLS", "Pressing", "Quenching", "Final Cut", "Stretching"]
        station_map = {
            "HLS": next((s for s in stations if s.name == "HLS"), stations[0]),
            "Pressing": next((s for s in stations if s.name == "Pressing"), stations[0]),
            "Quenching": next((s for s in stations if s.name == "Quenching"), stations[0]),
            "Final Cut": next((s for s in stations if s.name == "Final Cut"), stations[0]),
            "Stretching": next((s for s in stations if s.name == "Stretching"), stations[0]),
        }

        for idx, step_name in enumerate(step_names):
            cycle_time = random.randint(45, 90)  # 45-90 seconds per unit
            step = RoutingStepV2(
                id=_u(),
                routing_id=routing.id,
                step_no=idx + 1,
                station_id=station_map[step_name].id,
                step_name=step_name,
                cycle_time_sec=cycle_time,
                setup_time_sec=120,  # 2 minutes setup
                changeover_time_sec=180 if idx == 0 else 0,  # Changeover only at first step
                transport_time_sec=30  # 30 seconds transport
            )
            db.session.add(step)

    db.session.commit()
    print(f"  +{len(routings)} routing masters with {len(routings) * 5} steps total")


def seed_process_plans_and_schedule():
    """Create WorkOrders and ApsScheduleEntry rows for realistic demo data.

    Previously created ProcessPlan rows; switched to WorkOrder + APS entries
    so the APS scheduler and Gantt board have data to display.
    """
    from app.models import WorkOrder
    print("[14a] Seeding work orders + APS schedule entries ...")
    if WorkOrder.query.first():
        print("  skipped")
        return
    orders = CustomerOrder.query.limit(12).all()
    machines = Machine.query.all()
    dies = Die.query.filter_by(status="Available").limit(12).all()
    billets = Billet.query.filter_by(status="AVAILABLE").limit(12).all()
    if not orders or not machines:
        print(f"  skipped (orders={len(orders)} machines={len(machines)})")
        return

    # Create WorkOrders for each customer order
    wos = []
    for idx, co in enumerate(orders):
        wo = WorkOrder(
            id=_u(),
            order_number=f"WO-APS-{co.order_number.replace('-','')[:4]}",
            part_number=co.product_profile or "PROF-001",
            description=f"Work order for {co.customer_name} - {co.product_profile}",
            quantity=int(co.quantity_tons or 1.0),
            priority="High" if co.status == "IN_PROGRESS" else "Medium",
            status="DRAFT",
            due_date=co.due_date,
        )
        db.session.add(wo)
        wos.append(wo)
    db.session.flush()

    # Create APS schedule entries - cascade across all machines
    aps_entries = []
    machine_count = len(machines)
    for idx, wo in enumerate(wos):
        # Each WO gets scheduled on the next machine in round-robin
        machine = machines[idx % machine_count]
        start = datetime.utcnow().replace(hour=8, minute=0, second=0, microsecond=0) + timedelta(days=idx // machine_count, hours=idx % machine_count)
        end = start + timedelta(hours=8)

        # Get die and billet (if available)
        die = dies[idx % len(dies)] if dies else None
        billet = billets[idx % len(billets)] if billets else None

        entry = ApsScheduleEntry(
            id=_u(),
            work_order_id=wo.id,
            machine_id=machine.id,
            die_id=die.id if die else None,
            billet_id=billet.id if billet else None,
            scheduled_start=start,
            scheduled_end=end,
            priority=wo.priority,
            sequence_order=idx + 1,
            status="Planned",
            is_locked=False,
            constraint_status="Feasible",
            notes=f"Planned by ApsEngine for WO {wo.order_number}"
        )
        db.session.add(entry)
        aps_entries.append(entry)

    db.session.add_all(wos)
    db.session.add_all(aps_entries)
    print(f"  +{len(wos)} work orders, +{len(aps_entries)} APS schedule entries")


def seed_audit_trail():
    """Populate a realistic admin audit trail."""
    from app.models import AuditLog
    print("[14b] Seeding audit trail ...")
    if AuditLog.query.first():
        print("  skipped")
        return
    tables = ["dies", "customer_orders", "process_plans", "alert_rules",
              "machines", "die_inspections", "die_tests", "nitriding_records",
              "setpoint_profiles", "integration_jobs"]
    users = ["admin", "qa_supervisor", "plant_manager", "operator1"]
    actions = ["INSERT", "UPDATE"]
    # Use the first plant's UUID rather than a hardcoded value — admin_master
    # creates Plants with UUIDs so "plant-1" would violate the FK constraint.
    first_plant = Plant.query.first()
    plant_id = first_plant.id if first_plant else None
    entries = []
    for i in range(20):
        tbl = random.choice(tables)
        action = random.choice(actions)
        entries.append(AuditLog(
            user_id=random.choice(users),
            plant_id=plant_id,
            table_name=tbl,
            action=action,
            record_id=_u(),
            old_values={"status": "Idle"} if action == "UPDATE" else None,
            new_values={"status": "Running"} if action == "UPDATE" else {"created": True},
            esig_reason="Seed audit entry" if random.random() > 0.6 else None,
            ip_address="127.0.0.1",
            created_at=datetime.utcnow() - timedelta(hours=i * 3),
        ))
    db.session.add_all(entries)
    print(f"  +{len(entries)} audit log entries")


def seed_extrusion_traceability():
    """Create extrusion-chain genealogy events + traceability records so
    /traceability and /genealogy show end-to-end data instead of PCB-centric data."""
    from app.models import GenealogyEvent, TraceabilityRecord
    print("[14c] Seeding extrusion traceability + genealogy ...")
    # Guard initial SELECTs with no_autoflush — a prior seed may have dirty
    # rows (e.g. audit_log inserts with FKs against seed-only rows) that
    # would cascade-flush here and error out if we didn't.
    with db.session.no_autoflush:
        if TraceabilityRecord.query.first():
            print("  skipped")
            return
        dies = Die.query.limit(6).all()
        billets = Billet.query.limit(6).all()
        orders = CustomerOrder.query.limit(6).all()
        runs = ProcessRun.query.limit(20).all()
    events = []
    traces = []
    stage_order = ["ORDER_RECEIVED", "DIE_ALLOCATED", "BILLET_ALLOCATED",
                   "HLS_RUN", "PRESSING_RUN", "QUENCHING_RUN", "PULLING_RUN",
                   "STRETCHING_RUN", "FINAL_CUT", "BUNDLE_READY"]
    for idx, o in enumerate(orders):
        die = dies[idx % len(dies)] if dies else None
        billet = billets[idx % len(billets)] if billets else None
        for step, stage in enumerate(stage_order):
            when = datetime.utcnow() - timedelta(hours=(len(stage_order) - step) * 2)
            events.append(GenealogyEvent(
                board_id=None,
                wo_id=None,
                event_type=stage,
                machine_id=None,
                operator_id=random.choice(["R.Singh", "S.Menon", "A.Patel"]),
                reel_id=None,
                part_number=o.product_profile,
                lot_number=billet.lot_number if billet else None,
                data={
                    "order_number": o.order_number,
                    "die_code": die.die_code if die else None,
                    "billet": billet.billet_code if billet else None,
                    "alloy": o.alloy,
                },
                occurred_at=when,
            ))
            traces.append(TraceabilityRecord(
                entity_type="ORDER",
                entity_id=o.id,
                event_type=stage,
                operator_id=random.choice(["R.Singh", "S.Menon", "A.Patel"]),
                machine_id=None,
                data={
                    "order_number": o.order_number,
                    "die_code": die.die_code if die else None,
                    "billet": billet.billet_code if billet else None,
                    "alloy": o.alloy,
                    "customer": o.customer_name,
                },
                occurred_at=when,
            ))
    # Link some runs to a die/billet
    for r in runs:
        traces.append(TraceabilityRecord(
            entity_type="PROCESS_RUN",
            entity_id=r.id,
            event_type=f"{r.process_type}_RUN",
            operator_id=r.operator_id or "operator1",
            machine_id=r.machine_id,
            data={"process_type": r.process_type, "status": r.status},
            occurred_at=r.created_at or datetime.utcnow(),
        ))
    db.session.add_all(events)
    db.session.add_all(traces)
    print(f"  +{len(events)} genealogy events, +{len(traces)} traceability records")


def main():
    app = create_app()
    with app.app_context():
        print("=" * 70)
        print("FactoryNXT Foundry — Demo Seed Data + ERP/PLC Simulators")
        print("=" * 70)
        seed_plant_master_data()
        seed_material_grades()
        seed_customer_orders()
        seed_dies_and_workflow()
        seed_billets()
        seed_setpoint_profiles()
        seed_process_runs_and_records()
        seed_plc_signal_mappings()
        seed_integration_jobs()
        seed_alert_rules()
        seed_alerts()
        seed_kpi_records()
        # --- NEW additions that power admin/traceability dashboard heroes ---
        seed_admin_master()
        seed_work_orders_and_traceability()
        seed_oee_and_downtime()
        seed_process_plans_and_schedule()
        seed_audit_trail()
        seed_extrusion_traceability()
        seed_aps_data()
        db.session.commit()

        print()
        erp_order_import_simulator()
        plc_live_signal_simulator()
        erp_posting_simulator()

        # Summary
        print()
        print("=" * 70)
        print("Summary:")
        counts = {
            "Plants": Plant.query.count(),
            "Users": UserProfile.query.count(),
            "Integrations (ERP/PLC)": Integration.query.count(),
            "Customer Orders": CustomerOrder.query.count(),
            "Work Orders": WorkOrder.query.count(),
            "Dies (all statuses)": Die.query.count(),
            "Billets": Billet.query.count(),
            "Process Runs": ProcessRun.query.count(),
            "PLC Signal Mappings": PLCSignalMapping.query.count(),
            "Integration Jobs": IntegrationJob.query.count(),
            "KPI Records": KPIRecord.query.count(),
            "OEE Snapshots": OeeSnapshot.query.count(),
            "Downtime Events": DowntimeEvent.query.count(),
            "PCB Boards (traceability)": PcbBoard.query.count(),
            "Unit-History entries": UnitHistory.query.count(),
            "Alert Rules": AlertRule.query.count(),
            "Alerts": Alert.query.count(),
            "Process Plans": ProcessPlan.query.count(),
            "Traceability Records": TraceabilityRecord.query.count(),
            "Audit Log Entries": AuditLog.query.count(),
            "APS Schedule Versions": ApsScheduleVersion.query.count(),
            "APS Schedule Entries": ApsScheduleEntry.query.count(),
            "APS Constraint Logs": ApsConstraintLog.query.count(),
        }
        for name, c in counts.items():
            print(f"  {name:32s} {c:>5d}")
        print("=" * 70)
        print("Demo complete! Open http://<host>:5555/ to view the dashboard.")
        print()


if __name__ == "__main__":
    main()
