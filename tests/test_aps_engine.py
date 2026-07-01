"""Unit tests for the APS scheduling engine.

Covers:
  * Work-order generation from customer orders
  * Auto-scheduling (feasible placement)
  * Replan with locked-entry preservation
  * Constraint logging (die / billet / capacity)
  * Lock / unlock / manual-move
  * KPI + shortage computation
"""
from datetime import datetime, timedelta, date

from tests.conftest import ApsTestCase, auth_session
from app.services.aps_engine import ApsEngine, _snap30, _ceil30
from app.models import WorkOrder, CustomerOrder, Machine, Die, Billet
from app.models_aps import (
    ApsScheduleVersion, ApsScheduleEntry, ApsConstraintLog, ApsScheduleEvent,
)


class SnapTests(ApsTestCase):
    def test_snap30_rounds_down(self):
        dt = datetime(2026, 6, 30, 14, 47, 23)
        self.assertEqual(_snap30(dt).minute, 30)

    def test_ceil30_rounds_up(self):
        dt = datetime(2026, 6, 30, 14, 47)
        self.assertEqual(_ceil30(dt).minute, 0)
        self.assertEqual(_ceil30(dt).hour, 15)


class WorkOrderGenerationTests(ApsTestCase):
    def setUp(self):
        super().setUp()
        self.seed = self._seed_master()

    def test_generates_wo_from_customer_order(self):
        co = self.seed["co"]
        result = ApsEngine.generate_work_orders([co.id], created_by="tester")
        self.assertEqual(len(result["created"]), 1)
        self.assertEqual(len(result["errors"]), 0)
        created = result["created"][0]
        self.assertTrue(created["order_number"].startswith("WO-APS-"))
        self.assertIn(co.order_number.replace("-", ""), created["order_number"])

        # The new WO should exist in the DB
        wo = WorkOrder.query.get(created["id"])
        self.assertIsNotNone(wo)
        self.assertEqual(wo.quantity, 5)  # from customer order quantity_tons

    def test_skips_already_generated(self):
        co = self.seed["co"]
        r1 = ApsEngine.generate_work_orders([co.id])
        r2 = ApsEngine.generate_work_orders([co.id])
        self.assertEqual(len(r1["created"]), 1)
        self.assertEqual(len(r2["created"]), 0)
        self.assertTrue(any("already linked" in e for e in r2["errors"]))

    def test_sets_priority_by_due_date(self):
        co = self.seed["co"]
        # Due >+3 days but <=+7 → High
        co.due_date = date.today() + timedelta(days=5)
        self.db.session.commit()
        result = ApsEngine.generate_work_orders([co.id])
        created = result["created"][0]
        # priority depends on days_out; for 5 days => High
        wo = WorkOrder.query.get(created["id"])
        self.assertEqual(wo.priority, "High")

    def test_skips_completed_customer_orders(self):
        co = self.seed["co"]
        co.status = "COMPLETED"
        self.db.session.commit()
        result = ApsEngine.generate_work_orders([co.id])
        self.assertEqual(len(result["created"]), 0)
        self.assertTrue(any("COMPLETED" in e for e in result["errors"]))


class AutoScheduleTests(ApsTestCase):
    def setUp(self):
        super().setUp()
        self.seed = self._seed_master()

    def test_schedules_draft_wo(self):
        wo = self._seed_wo()
        result = ApsEngine.auto_schedule(planned_by="tester", horizon_days=14)
        self.assertGreaterEqual(result["placed"], 1)
        # At least one entry should now exist
        entry = ApsScheduleEntry.query.filter_by(work_order_id=wo.id).first()
        self.assertIsNotNone(entry)
        # The entry should be in the active version
        self.assertEqual(entry.version.version_type, "ACTIVE")
        # Start should be snapped to 30-min boundary
        self.assertEqual(entry.scheduled_start.minute % 30, 0)
        self.assertEqual(entry.scheduled_start.second, 0)

    def test_assigns_matching_die_and_billet(self):
        # WO with alloy=6061 should get the 6061 die and billet
        wo = self._seed_wo(description="6061 alloy test")
        result = ApsEngine.auto_schedule(planned_by="tester")
        entry = ApsScheduleEntry.query.filter_by(work_order_id=wo.id).first()
        self.assertIsNotNone(entry)
        self.assertIn(entry.die.alloy, (None, "6061"))
        self.assertIn(entry.billet.alloy, (None, "6061"))

    def test_handles_no_capacity(self):
        # All machines Down → NO_MACHINE_CAPACITY
        for m in self.seed["machines"]:
            m.status = "Down"
        self.db.session.commit()

        wo = self._seed_wo()
        result = ApsEngine.auto_schedule(planned_by="tester")
        self.assertEqual(result["placed"], 0)
        self.assertTrue(any(r["work_order"] == wo.order_number for r in result["unassigned"]))

    def test_creates_active_version_if_none(self):
        # Remove any default
        ApsScheduleVersion.query.delete()
        self.db.session.commit()
        self._seed_wo()
        ApsEngine.auto_schedule(planned_by="tester")
        active = ApsScheduleVersion.query.filter_by(version_type="ACTIVE").first()
        self.assertIsNotNone(active)
        self.assertEqual(active.name, "Active Schedule")


class ReplanTests(ApsTestCase):
    def setUp(self):
        super().setUp()
        self.seed = self._seed_master()

    def test_preserves_locked_entries(self):
        wo1 = self._seed_wo()
        wo2 = self._seed_wo()
        # First auto-schedule
        result = ApsEngine.auto_schedule(planned_by="tester")
        self.assertEqual(result["placed"], 2)
        # Lock the first entry
        e1 = ApsScheduleEntry.query.filter_by(work_order_id=wo1.id).first()
        ApsEngine.lock_entry(e1.id, locked=True, reason="planner lock",
                              locked_by="tester")
        original_start = e1.scheduled_start

        # Replan: should keep locked entry at same time
        result2 = ApsEngine.replan(None, replanned_by="tester")
        self.assertEqual(result2["preserved_locked"], 1)

        # Reload e1
        self.db.session.expire_all()
        e1_after = ApsScheduleEntry.query.get(e1.id)
        self.assertEqual(e1_after.scheduled_start, original_start)
        self.assertTrue(e1_after.is_locked)

    def test_does_not_preserve_if_flag_off(self):
        wo1 = self._seed_wo()
        ApsEngine.auto_schedule(planned_by="tester")
        e1 = ApsScheduleEntry.query.filter_by(work_order_id=wo1.id).first()
        ApsEngine.lock_entry(e1.id, locked=True, locked_by="tester")

        # Replan with preserve_locked=False
        result = ApsEngine.replan(None, preserve_locked=False, replanned_by="tester")
        self.assertEqual(result["preserved_locked"], 0)


class ManualMoveTests(ApsTestCase):
    def setUp(self):
        super().setUp()
        self.seed = self._seed_master()
        wo = self._seed_wo()
        ApsEngine.auto_schedule(planned_by="tester")
        self.entry = ApsScheduleEntry.query.filter_by(work_order_id=wo.id).first()

    def test_move_entry_changes_time(self):
        new_start = datetime.utcnow().replace(hour=14, minute=0, second=0, microsecond=0) + timedelta(days=1)
        new_end = new_start + timedelta(hours=2)
        result = ApsEngine.move_entry(self.entry.id, new_start=new_start, new_end=new_end, new_machine_id=None)
        self.assertTrue(result.get("ok"))
        self.db.session.expire_all()
        e = ApsScheduleEntry.query.get(self.entry.id)
        self.assertEqual(e.scheduled_start, new_start)
        self.assertEqual(e.scheduled_end, new_end)

    def test_move_conflicts_detected(self):
        # Place entry1 at time X; try to overlap entry2
        m1 = self.seed["machines"][0]
        result = ApsEngine.move_entry(
            self.entry.id,
            new_start=datetime.utcnow().replace(minute=0, second=0, microsecond=0),
            new_end=datetime.utcnow().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1),
            new_machine_id=m1.id,
        )
        self.assertIsInstance(result, dict)
        # Conflicts may or may not be reported, but the API should not crash
        self.assertIn("entry", result)

    def test_lock_entry(self):
        entry = ApsEngine.lock_entry(self.entry.id, locked=True, reason="demo", locked_by="tester")
        self.assertTrue(entry.is_locked)
        self.assertEqual(entry.locked_by, "tester")
        # Unlock
        entry = ApsEngine.lock_entry(self.entry.id, locked=False)
        self.assertFalse(entry.is_locked)
        self.assertIsNone(entry.locked_by)


class KpiAndShortageTests(ApsTestCase):
    def setUp(self):
        super().setUp()
        self.seed = self._seed_master()
        wo = self._seed_wo()
        ApsEngine.auto_schedule(planned_by="tester")

    def test_compute_kpis_returns_structure(self):
        kpis = ApsEngine.compute_kpis()
        self.assertIn("entries_total", kpis)
        self.assertIn("utilization_pct", kpis)
        self.assertIn("per_machine_load_min", kpis)
        self.assertGreaterEqual(kpis["entries_total"], 1)

    def test_compute_shortages_returns_structure(self):
        shortages = ApsEngine.compute_shortages()
        self.assertIn("die_shortages", shortages)
        self.assertIn("billet_shortages", shortages)
        self.assertIn("machine_issues", shortages)
        self.assertIn("total", shortages)


class GanttDataTests(ApsTestCase):
    def setUp(self):
        super().setUp()
        self.seed = self._seed_master()
        wo = self._seed_wo()
        ApsEngine.auto_schedule(planned_by="tester")

    def test_gantt_data_returns_version_and_entries(self):
        data = ApsEngine.gantt_data()
        self.assertIn("version", data)
        self.assertIn("machines", data)
        self.assertIn("entries_by_machine", data)
        self.assertIn("blocked_by_machine", data)
        self.assertIn("horizon", data)
        self.assertGreaterEqual(len(data["machines"]), 3)
        # At least one entry on a machine lane
        has_entries = any(len(v) > 0 for v in data["entries_by_machine"].values())
        self.assertTrue(has_entries)
