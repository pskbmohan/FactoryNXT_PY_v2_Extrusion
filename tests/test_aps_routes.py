"""Integration tests for the APS HTTP routes.

Uses the Flask test client. Each test gets a fresh DB. The session
`username` is set via `auth_session` so the auth check in the route
passes without going through the login flow.
"""
import json
import uuid
from datetime import date, datetime, timedelta

from tests.conftest import ApsTestCase, auth_session
from app.models import Machine, Die, Billet, CustomerOrder, WorkOrder
from app.models_aps import ApsScheduleVersion, ApsScheduleEntry, ApsConstraintLog
from app.services.aps_engine import ApsEngine


class CockpitTests(ApsTestCase):
    def test_cockpit_page_loads_without_version(self):
        auth_session(self.client)
        r = self.client.get("/aps")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Advanced Planning System", r.data)

    def test_cockpit_redirects_without_login(self):
        r = self.client.get("/aps")
        # Should redirect to login
        self.assertIn(r.status_code, (302, 301, 303))


class SchedulerPageTests(ApsTestCase):
    def test_scheduler_page_loads(self):
        auth_session(self.client)
        r = self.client.get("/aps/scheduler")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"APS Scheduler", r.data)


class GanttDataTests(ApsTestCase):
    def setUp(self):
        super().setUp()
        auth_session(self.client)
        self.seed = self._seed_master()
        wo = self._seed_wo()
        ApsEngine.auto_schedule(planned_by="tester")

    def test_api_gantt_data_returns_json(self):
        r = self.client.get("/api/aps/gantt")
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertIn("version", data)
        self.assertIn("machines", data)
        self.assertIn("entries_by_machine", data)

    def test_api_aps_kpis_returns_json(self):
        r = self.client.get("/api/aps/kpis")
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertIn("entries_total", data)

    def test_api_aps_shortages(self):
        r = self.client.get("/api/aps/shortages")
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertIn("die_shortages", data)

    def test_api_aps_entries(self):
        r = self.client.get("/api/aps/entries")
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertIn("entries", data)
        self.assertGreaterEqual(len(data["entries"]), 1)

    def test_api_aps_events(self):
        r = self.client.get("/api/aps/events")
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertIn("events", data)

    def test_api_aps_unscheduled(self):
        r = self.client.get("/api/aps/unscheduled")
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertIn("unscheduled", data)

    def test_api_aps_versions(self):
        r = self.client.get("/api/aps/versions")
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertIn("versions", data)
        self.assertGreaterEqual(len(data["versions"]), 1)


class AutoScheduleTests(ApsTestCase):
    def setUp(self):
        super().setUp()
        auth_session(self.client)
        self.seed = self._seed_master()

    def test_auto_schedule_endpoint(self):
        wo = self._seed_wo()
        r = self.client.post(
            "/api/aps/auto-schedule",
            json={"horizon_days": 14},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertTrue(data.get("ok"))
        self.assertIn("placed", data)

    def test_auto_schedule_empty_form(self):
        # form-based POST (no json body)
        r = self.client.post("/api/aps/auto-schedule", data={})
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertTrue(data["ok"])


class ReplanTests(ApsTestCase):
    def setUp(self):
        super().setUp()
        auth_session(self.client)
        self.seed = self._seed_master()

    def test_replan_preserves_locked(self):
        wo = self._seed_wo()
        ApsEngine.auto_schedule(planned_by="tester")
        entry = ApsScheduleEntry.query.filter_by(work_order_id=wo.id).first()
        ApsEngine.lock_entry(entry.id, locked=True, locked_by="tester")

        r = self.client.post("/api/aps/replan", json={"preserve_locked": True},
                              content_type="application/json")
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertTrue(data["ok"])
        self.assertGreaterEqual(data["preserved_locked"], 1)


class WorkOrderGenerationTests(ApsTestCase):
    def setUp(self):
        super().setUp()
        auth_session(self.client)
        self.seed = self._seed_master()

    def test_generate_work_orders_from_co_ids(self):
        co = self.seed["co"]
        r = self.client.post(
            "/api/aps/generate-wo",
            json={"customer_order_ids": [co.id]},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertTrue(data["ok"])
        self.assertEqual(data["created"], 1)

    def test_generate_work_orders_requires_customer_order_ids(self):
        r = self.client.post(
            "/api/aps/generate-wo",
            json={},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)
        data = json.loads(r.data)
        self.assertFalse(data["ok"])


class MoveLockReleaseTests(ApsTestCase):
    def setUp(self):
        super().setUp()
        auth_session(self.client)
        self.seed = self._seed_master()
        wo = self._seed_wo()
        ApsEngine.auto_schedule(planned_by="tester")
        self.entry = ApsScheduleEntry.query.filter_by(work_order_id=wo.id).first()

    def test_move_entry_endpoint(self):
        new_start = datetime.utcnow() + timedelta(days=3)
        new_start = new_start.replace(hour=10, minute=0, second=0, microsecond=0)
        new_end = new_start + timedelta(hours=2)
        r = self.client.post(
            f"/api/aps/entries/{self.entry.id}/move",
            json={
                "scheduled_start": new_start.strftime("%Y-%m-%d %H:%M:%S"),
                "scheduled_end": new_end.strftime("%Y-%m-%d %H:%M:%S"),
            },
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertTrue(data["ok"])

    def test_lock_and_unlock(self):
        # Lock
        r = self.client.post(
            f"/api/aps/entries/{self.entry.id}/lock",
            json={"locked": True, "reason": "testing"},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertTrue(data["ok"])
        self.assertTrue(data["entry"]["is_locked"])

        # Unlock
        r2 = self.client.post(
            f"/api/aps/entries/{self.entry.id}/lock",
            json={"locked": False},
            content_type="application/json",
        )
        self.assertEqual(r2.status_code, 200)
        data2 = json.loads(r2.data)
        self.assertFalse(data2["entry"]["is_locked"])

    def test_release_to_floor(self):
        r = self.client.post(
            f"/api/aps/entries/{self.entry.id}/release",
            json={"status": "DISPATCHED"},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertTrue(data["ok"])
        self.assertEqual(data["entry"]["status"], "DISPATCHED")


class VersionTests(ApsTestCase):
    def test_create_version(self):
        auth_session(self.client)
        r = self.client.post(
            "/api/aps/versions",
            json={"name": "Test What-If", "horizon_days": 7},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertTrue(data["ok"])
        self.assertEqual(data["version"]["name"], "Test What-If")

    def test_publish_version(self):
        auth_session(self.client)
        # Create a draft first
        r = self.client.post(
            "/api/aps/versions",
            json={"name": "Draft 1"},
            content_type="application/json",
        )
        data = json.loads(r.data)
        vid = data["version"]["id"]

        r2 = self.client.post(f"/api/aps/versions/{vid}/publish", json={})
        self.assertEqual(r2.status_code, 200)
        data = json.loads(r2.data)
        self.assertTrue(data["ok"])
        self.assertEqual(data["version"]["version_type"], "ACTIVE")
