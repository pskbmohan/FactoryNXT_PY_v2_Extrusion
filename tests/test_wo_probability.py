"""Tests for the WO on-time delivery probability engine.

Covers the deterministic formula in app/services/wo_probability.py plus
the /aps/api/wo-probability HTTP endpoint.
"""
import json
from datetime import datetime, timedelta

from tests.conftest import ApsTestCase, auth_session
from app.services.wo_probability import calculate_wo_probability


class ProbabilityFormulaTests(ApsTestCase):
    """Direct unit tests against calculate_wo_probability(); no HTTP involved."""

    def test_complete_wo_is_100_percent(self):
        wo = self._seed_wo(quantity=100, produced_qty=100, status="RUNNING")
        result = calculate_wo_probability(wo)
        self.assertEqual(result["probability_pct"], 100.0)
        self.assertEqual(result["status"], "ahead")

    def test_overdue_incomplete_wo_is_0_percent(self):
        now = datetime.utcnow()
        wo = self._seed_wo(
            quantity=100, produced_qty=40, status="RUNNING",
            started_at=now - timedelta(hours=48),
            due_date=now - timedelta(hours=1),
        )
        result = calculate_wo_probability(wo, now=now)
        self.assertEqual(result["probability_pct"], 0.0)
        self.assertEqual(result["status"], "critical")

    def test_on_pace_wo_lands_near_50(self):
        # 50% of qty done, 50% of the time window elapsed -> pace_index == 1.0
        now = datetime.utcnow()
        wo = self._seed_wo(
            quantity=100, produced_qty=50, status="RUNNING",
            started_at=now - timedelta(hours=10),
            due_date=now + timedelta(hours=10),
        )
        result = calculate_wo_probability(wo, now=now)
        self.assertAlmostEqual(result["pace_index"], 1.0, places=2)
        self.assertTrue(45 <= result["probability_pct"] <= 60,
                         f"expected ~50-60, got {result['probability_pct']}")

    def test_ahead_of_pace_wo_scores_above_80(self):
        # 80% of qty done at 50% of the time window -> pace_index == 1.6,
        # with enough time buffer left to trigger the +10% boost.
        now = datetime.utcnow()
        wo = self._seed_wo(
            quantity=100, produced_qty=80, status="RUNNING",
            started_at=now - timedelta(hours=20),
            due_date=now + timedelta(hours=20),
        )
        result = calculate_wo_probability(wo, now=now)
        self.assertGreater(result["probability_pct"], 80)
        self.assertIn(result["status"], ("on_track", "ahead"))

    def test_critical_wo_scores_below_40(self):
        # 20% of qty done at 80% of the time window -> pace_index == 0.25
        now = datetime.utcnow()
        wo = self._seed_wo(
            quantity=100, produced_qty=20, status="RUNNING",
            started_at=now - timedelta(hours=8),
            due_date=now + timedelta(hours=2),
        )
        result = calculate_wo_probability(wo, now=now)
        self.assertLess(result["probability_pct"], 40)
        self.assertEqual(result["status"], "critical")


class WoProbabilityApiTests(ApsTestCase):
    def setUp(self):
        super().setUp()
        auth_session(self.client)
        now = datetime.utcnow()
        self._seed_wo(
            order_number="WO-PROB-1", quantity=100, produced_qty=90, status="RUNNING",
            started_at=now - timedelta(hours=5), due_date=now + timedelta(hours=20),
        )
        self._seed_wo(
            order_number="WO-PROB-2", quantity=100, produced_qty=10, status="RELEASED",
            started_at=now - timedelta(hours=18), due_date=now + timedelta(hours=2),
        )
        # DRAFT/COMPLETED WOs must be excluded from the endpoint entirely.
        self._seed_wo(order_number="WO-PROB-3", quantity=50, status="DRAFT")
        self._seed_wo(order_number="WO-PROB-4", quantity=50, produced_qty=50, status="COMPLETED")

    def test_endpoint_returns_200_with_expected_structure(self):
        r = self.client.get("/aps/api/wo-probability")
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertIn("as_of", data)
        self.assertIn("work_orders", data)
        self.assertIn("summary", data)
        for key in ("total", "critical", "at_risk", "on_track", "ahead"):
            self.assertIn(key, data["summary"])

    def test_endpoint_only_includes_released_and_running(self):
        r = self.client.get("/aps/api/wo-probability")
        data = json.loads(r.data)
        wo_numbers = {wo["wo_number"] for wo in data["work_orders"]}
        self.assertEqual(wo_numbers, {"WO-PROB-1", "WO-PROB-2"})
        self.assertEqual(data["summary"]["total"], 2)

    def test_endpoint_sorts_by_probability_ascending(self):
        r = self.client.get("/aps/api/wo-probability")
        data = json.loads(r.data)
        probs = [wo["probability_pct"] for wo in data["work_orders"]]
        self.assertEqual(probs, sorted(probs))
