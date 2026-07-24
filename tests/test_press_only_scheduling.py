"""Tests for press-only scheduling and the BOM-driven WO -> Press flow.

Covers:
- is_press_machine() / get_eligible_machines_for_die() (app/services/bom_service.py)
- ApsEngine.auto_schedule only ever places entries on Press machines
  (app/services/aps_engine.py)
- End-to-end: create_wo_from_order_line -> auto_schedule lands a
  BOM-resolved WO on a press
- Weekly Board / Scheduler (Legacy) routes read the same ApsScheduleEntry
  data as APS Planning / APS Scheduler
"""
import uuid
from datetime import date, timedelta

from tests.conftest import ApsTestCase, auth_session
from app.models import Machine, PartNumber, PartNumberBOM, CustomerOrderLine
from app.models_aps import ApsScheduleEntry
from app.services.aps_engine import ApsEngine
from app.services.bom_service import is_press_machine, get_eligible_machines_for_die
from app.services.work_order_service import create_wo_from_order_line


class IsPressMachineTests(ApsTestCase):
    def test_press_named_machines_are_press(self):
        seed = self._seed_master()
        for m in seed["machines"]:
            self.assertTrue(is_press_machine(m), f"{m.name} should be a press")

    def test_non_press_named_machine_is_not_press(self):
        self._seed_master()
        hls = Machine(id=99, line_id=1, name="HLS-01", status="Available")
        self.assertFalse(is_press_machine(hls))

    def test_get_eligible_machines_for_die_excludes_non_press(self):
        seed = self._seed_master()
        hls = Machine(id=99, line_id=seed["line"].id, name="HLS-01", status="Idle")
        self.db.session.add(hls)
        self.db.session.commit()

        eligible = get_eligible_machines_for_die(seed["dies"][0].id)
        names = {m.name for m in eligible}
        self.assertTrue(names, "expected at least one eligible press machine")
        self.assertNotIn("HLS-01", names)
        for name in names:
            self.assertTrue(name.lower().startswith("press"))


class AutoScheduleIsPressOnlyTests(ApsTestCase):
    def test_auto_schedule_never_uses_non_press_machines(self):
        seed = self._seed_master()
        # A non-press machine that's MORE available than any press (Idle,
        # no load) — if press-filtering were broken, the scheduler would
        # prefer this one first.
        hls = Machine(id=50, line_id=seed["line"].id, name="HLS-01", status="Idle")
        self.db.session.add(hls)
        self.db.session.commit()

        self._seed_wo(quantity=2, status="RELEASED")
        self._seed_wo(quantity=2, status="RELEASED")

        result = ApsEngine.auto_schedule(planned_by="tester")
        self.assertGreater(result["placed"], 0)

        entries = ApsScheduleEntry.query.filter(ApsScheduleEntry.work_order_id.isnot(None)).all()
        self.assertTrue(entries)
        machine_ids = {e.machine_id for e in entries}
        machines = {m.id: m for m in Machine.query.filter(Machine.id.in_(machine_ids))}
        for mid in machine_ids:
            self.assertTrue(
                is_press_machine(machines[mid]),
                f"entry scheduled on non-press machine {machines[mid].name}",
            )
        self.assertNotIn(hls.id, machine_ids)


class BomDrivenWoToPressTests(ApsTestCase):
    def test_create_wo_from_order_line_then_auto_schedule_lands_on_press(self):
        seed = self._seed_master()
        die = seed["dies"][0]
        billet = seed["billets"][0]

        part = PartNumber(
            id=str(uuid.uuid4()), part_code="PN-TEST-100", profile_code=die.profile_code,
            alloy=billet.alloy, unit_weight_kg=2.0, is_active=True,
        )
        self.db.session.add(part)
        self.db.session.flush()

        bom = PartNumberBOM(
            id=str(uuid.uuid4()), part_number_id=part.id, version=1,
            die_type_id=die.id, billet_type_id=billet.id,
            billet_weight_kg=2.0, is_active=True,
        )
        self.db.session.add(bom)

        line = CustomerOrderLine(
            id=str(uuid.uuid4()), order_id=seed["co"].id, part_number_id=part.id,
            line_number=1, ordered_qty=10, required_date=date.today() + timedelta(days=5),
            status="OPEN",
        )
        self.db.session.add(line)
        self.db.session.commit()

        wo = create_wo_from_order_line(line.id)
        self.assertEqual(wo.die_type_id, die.id)
        self.assertEqual(wo.billet_type_id, billet.id)
        self.assertEqual(wo.status, "DRAFT")

        result = ApsEngine.auto_schedule(planned_by="tester")
        self.assertEqual(result["unassigned"], [])

        entry = ApsScheduleEntry.query.filter_by(work_order_id=wo.id).first()
        self.assertIsNotNone(entry, "BOM-driven WO should have been scheduled")
        machine = Machine.query.get(entry.machine_id)
        self.assertTrue(is_press_machine(machine))
        self.assertEqual(entry.die_id, die.id)


class PlanningPagesReadApsScheduleEntryTests(ApsTestCase):
    """Weekly Board and Scheduler (Legacy) must read the same data as
    APS Planning / APS Scheduler, not the old ProcessPlan/ProductionSchedule
    models."""

    def setUp(self):
        super().setUp()
        auth_session(self.client)
        self.seed = self._seed_master()
        self.wo = self._seed_wo(quantity=2, status="RELEASED")
        ApsEngine.auto_schedule(planned_by="tester")

    def test_weekly_board_loads_and_shows_scheduled_entry(self):
        r = self.client.get("/planning/weekly")
        self.assertEqual(r.status_code, 200)
        entry = ApsScheduleEntry.query.filter_by(work_order_id=self.wo.id).first()
        self.assertIsNotNone(entry)
        # The order number (from the entry's WorkOrder) should render
        # somewhere on the page — proves the route pulled it from
        # ApsScheduleEntry, not an empty legacy ProcessPlan table.
        self.assertIn(self.wo.order_number.encode(), r.data)

    def test_scheduler_legacy_loads_and_shows_scheduled_entry(self):
        r = self.client.get("/planning/scheduler")
        self.assertEqual(r.status_code, 200)
        self.assertIn(self.wo.order_number.encode(), r.data)

    def test_weekly_board_only_lists_press_machines(self):
        hls = Machine(id=77, line_id=self.seed["line"].id, name="HLS-01", status="Available")
        self.db.session.add(hls)
        self.db.session.commit()

        r = self.client.get("/planning/weekly")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(b"HLS-01", r.data)
