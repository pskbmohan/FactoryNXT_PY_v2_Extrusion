#!/usr/bin/env python3
"""
Seed script for Planning/Weekly and APS modules.
Populates: Machines, Dies, Billets, WorkOrders, ProcessPlans,
           MachineResourceMappings, ApsScheduleVersion + Entries

Run with:  python seed_planning_aps.py
       or: flask seed-planning
"""
import uuid
from datetime import datetime, timedelta, date


def seed():
    from app import create_app, db
    from app.models import (
        Machine, Die, Billet, WorkOrder, ProcessPlan, CustomerOrder, Line
    )
    from app.models_aps import (
        MachineResourceMapping, ApsScheduleVersion, ApsScheduleEntry
    )

    app = create_app()
    with app.app_context():

        print("🌱 Starting seed for Planning & APS...")

        # ── 1. Ensure a Line exists ────────────────────────────────────────
        line = Line.query.first()
        if not line:
            line = Line(name="Extrusion Line 1", status="Active")
            db.session.add(line)
            db.session.flush()
            print("  ✅ Created Line: Extrusion Line 1")

        # ── 2. Seed Machines (3 extrusion presses) ────────────────────────
        machine_defs = [
            {"name": "Press-01", "status": "Available"},
            {"name": "Press-02", "status": "Available"},
            {"name": "Press-03", "status": "Idle"},
        ]
        machines = []
        for md in machine_defs:
            m = Machine.query.filter_by(name=md["name"]).first()
            if not m:
                m = Machine(
                    name=md["name"],
                    status=md["status"],
                    line_id=line.id,
                )
                try:
                    m.is_active = True
                except Exception:
                    pass
                db.session.add(m)
                db.session.flush()
                print(f"  ✅ Created Machine: {md['name']}")
            else:
                # Ensure is_active is True and status is set
                try:
                    m.is_active = True
                    m.status = md["status"]
                except Exception:
                    pass
            machines.append(m)
        db.session.flush()

        # ── 3. Seed Dies ───────────────────────────────────────────────────
        die_defs = [
            {"die_code": "DIE-6063-FH-40X20", "alloy": "6063", "profile_code": "PROF-FH-40X20", "status": "Available"},
            {"die_code": "DIE-6063-SQ-50X50", "alloy": "6063", "profile_code": "PROF-SQ-50X50", "status": "Available"},
            {"die_code": "DIE-6082-RD-25",    "alloy": "6082", "profile_code": "PROF-RD-25",    "status": "Available"},
            {"die_code": "DIE-6063-CH-30X60", "alloy": "6063", "profile_code": "PROF-CH-30X60", "status": "Available"},
            {"die_code": "DIE-6061-TU-50X3",  "alloy": "6061", "profile_code": "PROF-TU-50X3",  "status": "In Furnace"},
        ]
        dies = []
        for dd in die_defs:
            d = Die.query.filter_by(die_code=dd["die_code"]).first()
            if not d:
                d = Die(
                    id=str(uuid.uuid4()),
                    die_code=dd["die_code"],
                    alloy=dd.get("alloy", "6063"),
                    profile_code=dd.get("profile_code", ""),
                    status=dd["status"],
                )
                db.session.add(d)
                db.session.flush()
                print(f"  ✅ Created Die: {dd['die_code']}")
            dies.append(d)
        db.session.flush()

        # ── 4. Seed Billets (model uses quantity_kg) ───────────────────────
        billet_defs = [
            {"billet_code": "BLT-6063-240601", "alloy": "6063", "quantity_kg": 2000.0, "status": "AVAILABLE"},
            {"billet_code": "BLT-6063-240602", "alloy": "6063", "quantity_kg": 1800.0, "status": "AVAILABLE"},
            {"billet_code": "BLT-6082-240601", "alloy": "6082", "quantity_kg": 1500.0, "status": "AVAILABLE"},
            {"billet_code": "BLT-6061-240601", "alloy": "6061", "quantity_kg": 1200.0, "status": "AVAILABLE"},
        ]
        for bd in billet_defs:
            b = Billet.query.filter_by(billet_code=bd["billet_code"]).first()
            if not b:
                b = Billet(
                    id=str(uuid.uuid4()),
                    billet_code=bd["billet_code"],
                    alloy=bd["alloy"],
                    quantity_kg=bd["quantity_kg"],
                    status=bd["status"],
                )
                db.session.add(b)
                print(f"  ✅ Created Billet: {bd['billet_code']}")
        db.session.flush()

        # ── 5. Seed Customer Orders (due_date is a Date field) ─────────────
        today = date.today()
        co_defs = [
            {"order_number": "CO-2026-001", "customer_name": "Aluminium India Ltd",
             "product_profile": "PROF-FH-40X20", "alloy": "6063",
             "quantity_tons": 5.0, "status": "CONFIRMED",
             "due_date": today + timedelta(days=7)},
            {"order_number": "CO-2026-002", "customer_name": "KM Windows Pvt Ltd",
             "product_profile": "PROF-SQ-50X50", "alloy": "6063",
             "quantity_tons": 3.5, "status": "CONFIRMED",
             "due_date": today + timedelta(days=5)},
            {"order_number": "CO-2026-003", "customer_name": "Jindal Facades",
             "product_profile": "PROF-RD-25", "alloy": "6082",
             "quantity_tons": 2.0, "status": "IN_PROGRESS",
             "due_date": today + timedelta(days=3)},
            {"order_number": "CO-2026-004", "customer_name": "Hindalco Systems",
             "product_profile": "PROF-CH-30X60", "alloy": "6063",
             "quantity_tons": 4.0, "status": "CONFIRMED",
             "due_date": today + timedelta(days=10)},
            {"order_number": "CO-2026-005", "customer_name": "BuildRight Corp",
             "product_profile": "PROF-TU-50X3", "alloy": "6061",
             "quantity_tons": 1.5, "status": "DRAFT",
             "due_date": today + timedelta(days=14)},
        ]
        customer_orders = []
        for cd in co_defs:
            co = CustomerOrder.query.filter_by(order_number=cd["order_number"]).first()
            if not co:
                co = CustomerOrder(
                    id=str(uuid.uuid4()),
                    order_number=cd["order_number"],
                    customer_name=cd["customer_name"],
                    product_profile=cd["product_profile"],
                    alloy=cd["alloy"],
                    quantity_tons=cd["quantity_tons"],
                    status=cd["status"],
                    due_date=cd["due_date"],
                )
                db.session.add(co)
                print(f"  ✅ Created CustomerOrder: {cd['order_number']}")
            customer_orders.append(co)
        db.session.flush()

        # ── 6. Seed Work Orders (id is UUID string) ────────────────────────
        wo_defs = [
            {"order_number": "WO-2026-001", "part_number": "PROF-FH-40X20",
             "quantity": 500, "status": "RELEASED", "priority": "High",
             "due_date": today + timedelta(days=7)},
            {"order_number": "WO-2026-002", "part_number": "PROF-SQ-50X50",
             "quantity": 350, "status": "RELEASED", "priority": "Medium",
             "due_date": today + timedelta(days=5)},
            {"order_number": "WO-2026-003", "part_number": "PROF-RD-25",
             "quantity": 200, "status": "RELEASED", "priority": "Critical",
             "due_date": today + timedelta(days=3)},
            {"order_number": "WO-2026-004", "part_number": "PROF-CH-30X60",
             "quantity": 400, "status": "RELEASED", "priority": "High",
             "due_date": today + timedelta(days=10)},
            {"order_number": "WO-2026-005", "part_number": "PROF-TU-50X3",
             "quantity": 150, "status": "DRAFT", "priority": "Low",
             "due_date": today + timedelta(days=14)},
            {"order_number": "WO-2026-006", "part_number": "PROF-FH-40X20",
             "quantity": 600, "status": "RELEASED", "priority": "Medium",
             "due_date": today + timedelta(days=8)},
        ]
        work_orders = []
        for wd in wo_defs:
            wo = WorkOrder.query.filter_by(order_number=wd["order_number"]).first()
            if not wo:
                wo_id = str(uuid.uuid4())
                wo = WorkOrder(
                    id=wo_id,
                    order_number=wd["order_number"],
                    part_number=wd["part_number"],
                    description=f"Work order for {wd['part_number']}",
                    quantity=wd["quantity"],
                    status=wd["status"],
                    priority=wd["priority"],
                    due_date=datetime.combine(wd["due_date"], datetime.min.time()) if hasattr(wd["due_date"], "year") and not hasattr(wd["due_date"], "hour") else wd["due_date"],
                )
                db.session.add(wo)
                print(f"  ✅ Created WorkOrder: {wd['order_number']}")
            work_orders.append(wo)
        db.session.flush()

        # ── 7. Seed ProcessPlans (for weekly board) ────────────────────────
        # Assign first 4 RELEASED WOs to machines on specific days this week
        monday = datetime.combine(today - timedelta(days=today.weekday()), datetime.min.time())
        plan_assignments = [
            # (wo_index, machine_index, day_offset)
            (0, 0, 0),   # WO-001 → Press-01 → Monday
            (1, 1, 1),   # WO-002 → Press-02 → Tuesday
            (2, 0, 2),   # WO-003 → Press-01 → Wednesday
            (3, 2, 3),   # WO-004 → Press-03 → Thursday
        ]
        for wi, mi, day_offset in plan_assignments:
            wo = work_orders[wi]
            m  = machines[mi]
            start = monday + timedelta(days=day_offset, hours=6)
            end   = start  + timedelta(hours=16)
            plan_number = f"PLAN-{wo.order_number.replace('WO-', '')}"

            existing = ProcessPlan.query.filter_by(plan_number=plan_number).first()
            if not existing:
                plan = ProcessPlan(
                    id=str(uuid.uuid4()),
                    plan_number=plan_number,
                    machine_id=m.id,
                    scheduled_start=start,
                    scheduled_end=end,
                    status="Scheduled",
                    priority=wo.priority or "Medium",
                    created_by="seed",
                    profile_shape=wo.part_number,
                    alloy="6063",
                )
                # Link to customer order if possible
                try:
                    if wi < len(customer_orders):
                        plan.order_id = customer_orders[wi].id
                except Exception:
                    pass
                db.session.add(plan)
                # Update WO status to PLANNED and set schedule window
                wo.status = "PLANNED"
                wo.scheduled_start = start
                wo.scheduled_end   = end
                print(f"  ✅ Created ProcessPlan: {plan_number} → {m.name} on day+{day_offset}")

        db.session.flush()

        # ── 8. Seed MachineResourceMappings (critical for APS auto-schedule) ─
        mapping_defs = [
            {
                "part_number": "PROF-FH-40X20",
                "machine_idx": 0,   # Press-01
                "die_idx": 0,
                "cycle_time_sec": 45,
                "setup_time_sec": 900,
                "changeover_time_sec": 1800,
            },
            {
                "part_number": "PROF-SQ-50X50",
                "machine_idx": 1,   # Press-02
                "die_idx": 1,
                "cycle_time_sec": 60,
                "setup_time_sec": 900,
                "changeover_time_sec": 1800,
            },
            {
                "part_number": "PROF-RD-25",
                "machine_idx": 0,   # Press-01
                "die_idx": 2,
                "cycle_time_sec": 30,
                "setup_time_sec": 600,
                "changeover_time_sec": 1200,
            },
            {
                "part_number": "PROF-CH-30X60",
                "machine_idx": 2,   # Press-03
                "die_idx": 3,
                "cycle_time_sec": 55,
                "setup_time_sec": 900,
                "changeover_time_sec": 1800,
            },
            {
                "part_number": "PROF-TU-50X3",
                "machine_idx": 1,   # Press-02
                "die_idx": 4,
                "cycle_time_sec": 75,
                "setup_time_sec": 1200,
                "changeover_time_sec": 2400,
            },
        ]
        for md in mapping_defs:
            m   = machines[md["machine_idx"]]
            d   = dies[md["die_idx"]]
            existing = MachineResourceMapping.query.filter_by(
                part_number=md["part_number"], machine_id=m.id
            ).first()
            if not existing:
                mapping = MachineResourceMapping(
                    part_number=md["part_number"],
                    machine_id=m.id,
                    die_id=d.id,
                    cycle_time_sec=md["cycle_time_sec"],
                    setup_time_sec=md["setup_time_sec"],
                    changeover_time_sec=md["changeover_time_sec"],
                    transport_time_sec=300,
                    preferred=True,
                    active=True,
                )
                db.session.add(mapping)
                print(f"  ✅ Created MachineResourceMapping: {md['part_number']} → {m.name}")

        db.session.flush()

        # ── 9. Seed an APS Schedule Version with entries ───────────────────
        existing_version = ApsScheduleVersion.query.filter_by(name="SEED-INITIAL").first()
        if not existing_version:
            version = ApsScheduleVersion(
                id=str(uuid.uuid4()),
                name="SEED-INITIAL",
                version_type="DRAFT",
                planning_horizon_days=7,
                created_by="seed",
            )
            db.session.add(version)
            db.session.flush()

            cursor = {m.id: datetime.utcnow() for m in machines}

            # Only schedule RELEASED and PLANNED WOs
            schedulable = [
                wo for wo in work_orders
                if wo.status in ("RELEASED", "PLANNED")
            ]

            for wo in schedulable:
                mapping = MachineResourceMapping.query.filter_by(
                    part_number=wo.part_number, active=True
                ).first()

                if mapping:
                    m = db.session.get(Machine, mapping.machine_id) or min(machines, key=lambda x: cursor[x.id])
                    die = db.session.get(Die, mapping.die_id) if mapping.die_id else None
                    cycle_min  = int(mapping.cycle_time_sec / 60)
                    setup_min  = int(mapping.setup_time_sec / 60)
                    chover_min = int(mapping.changeover_time_sec / 60)
                else:
                    m = min(machines, key=lambda x: cursor[x.id])
                    die = None
                    cycle_min = 60
                    setup_min = 15
                    chover_min = 30

                qty = getattr(wo, 'quantity', 1) or 1
                duration_min = setup_min + cycle_min * qty
                start = cursor[m.id]
                end   = start + timedelta(minutes=duration_min)

                entry = ApsScheduleEntry(
                    id=str(uuid.uuid4()),
                    version_id=version.id,
                    work_order_id=wo.id,
                    machine_id=m.id,
                    die_id=die.id if die else None,
                    scheduled_start=start,
                    scheduled_end=end,
                    status="PLANNED",
                    constraint_status="FEASIBLE",
                    priority=getattr(wo, "priority", "medium"),
                    setup_duration_min=setup_min,
                )
                db.session.add(entry)
                cursor[m.id] = end + timedelta(minutes=chover_min)

            print(f"  ✅ Created APS Schedule Version: SEED-INITIAL with {len(schedulable)} entries")

        # ── 10. Commit everything ──────────────────────────────────────────
        try:
            db.session.commit()
            print("\n✅ Seed complete! Summary:")
            from app.models import Machine, WorkOrder, ProcessPlan
            from app.models_aps import MachineResourceMapping, ApsScheduleVersion, ApsScheduleEntry
            print(f"   Machines:              {Machine.query.count()}")
            print(f"   Work Orders:           {WorkOrder.query.count()}")
            print(f"   Process Plans:         {ProcessPlan.query.count()}")
            print(f"   Resource Mappings:     {MachineResourceMapping.query.count()}")
            print(f"   APS Versions:          {ApsScheduleVersion.query.count()}")
            print(f"   APS Entries:           {ApsScheduleEntry.query.count()}")
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Seed FAILED: {e}")
            raise


if __name__ == "__main__":
    seed()
