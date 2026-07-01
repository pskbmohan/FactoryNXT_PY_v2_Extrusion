"""Test fixtures for APS tests.

Uses an in-memory SQLite DB and a minimal Flask app context. Each test
gets a fresh app so side-effects (seed data, APS rows) never leak.
"""
import os
import sys
import unittest
from datetime import date, datetime, timedelta

import uuid

# Ensure repo root is on sys.path for the `app` package.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Force SQLite for tests — faster, no PG needed.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"


def make_app():
    """Build a test app with in-memory SQLite."""
    from app import create_app, db
    from app.config import Config

    class TestConfig(Config):
        TESTING = True
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
        SECRET_KEY = "test-secret"
        WTF_CSRF_ENABLED = False

    app = create_app(config_class=TestConfig)
    app.config["WTF_CSRF_ENABLED"] = False
    with app.app_context():
        # Create tables (models + aps + routing). db.create_all() is called
        # in create_app, but re-run to be safe after test setup.
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        if "aps_schedule_versions" not in tables:
            db.create_all()
        # Skip the production seed path by overriding its guard:
        # the production `seed_...` functions are all idempotent (skip-if-exists),
        # so running them here is safe but optional. We don't run them so tests
        # start empty and can assert exact counts.
    return app


def auth_session(client, username="planner"):
    """Set `username` in the session so auth-requiring routes resolve."""
    with client.session_transaction() as sess:
        sess["username"] = username


class ApsTestCase(unittest.TestCase):
    """Base class with app-context + client + fresh DB per test."""

    def setUp(self):
        self.app = make_app()
        self.appctx = self.app.app_context()
        self.appctx.push()
        self.client = self.app.test_client()
        from app import db
        self.db = db
        db.create_all()

    def tearDown(self):
        from app import db
        db.session.remove()
        db.drop_all()
        self.appctx.pop()

    # ── helpers ─────────────────────────────────────────────────────────
    def _seed_master(self):
        """Seed lines, machines, stations, dies, billets, one customer order."""
        from app.models import Line, Machine, Station, Die, Billet, CustomerOrder
        line = Line(id=1, name="Extrusion Line 1", status="Running")
        self.db.session.add(line)
        self.db.session.flush()
        m1 = Machine(id=1, line_id=line.id, name="Press-01", status="Available")
        m2 = Machine(id=2, line_id=line.id, name="Press-02", status="Idle")
        m3 = Machine(id=3, line_id=line.id, name="Press-03", status="Running")
        self.db.session.add_all([m1, m2, m3])
        self.db.session.flush()
        self.db.session.add(Station(name="Press", code="PRESS"))
        self.db.session.flush()
        d1 = Die(id=str(uuid.uuid4()), die_code="DIE-6061-A", alloy="6061",
                 profile_code="P100", status="Available")
        d2 = Die(id=str(uuid.uuid4()), die_code="DIE-6063-A", alloy="6063",
                 profile_code="P101", status="Available")
        self.db.session.add_all([d1, d2])
        b1 = Billet(id=str(uuid.uuid4()), billet_code="BIL-6061-1", alloy="6061",
                    status="AVAILABLE")
        b2 = Billet(id=str(uuid.uuid4()), billet_code="BIL-6063-1", alloy="6063",
                    status="AVAILABLE")
        self.db.session.add_all([b1, b2])
        co = CustomerOrder(
            id=str(uuid.uuid4()), order_number="CO-0001",
            customer_name="TestCustomer", product_profile="P100", alloy="6061",
            quantity_tons=5.0, due_date=date.today() + timedelta(days=10),
            status="CONFIRMED",
        )
        self.db.session.add(co)
        self.db.session.commit()
        return {"line": line, "machines": [m1, m2, m3],
                "dies": [d1, d2], "billets": [b1, b2], "co": co}

    def _seed_wo(self, **overrides):
        from app.models import WorkOrder
        defaults = dict(
            id=str(uuid.uuid4()),
            order_number=f"WO-TEST-{uuid.uuid4().hex[:4].upper()}",
            part_number="P100",
            description="Test WO",
            quantity=3,
            priority="Medium",
            status="DRAFT",
            due_date=datetime.utcnow() + timedelta(days=7),
        )
        defaults.update(overrides)
        wo = WorkOrder(**defaults)
        self.db.session.add(wo)
        self.db.session.commit()
        return wo
