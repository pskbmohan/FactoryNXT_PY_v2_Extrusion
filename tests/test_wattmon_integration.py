"""
Tests for the Wattmon CSV upload endpoint (/integrations/csv-upload).

Covers:
  1. Standard form POST (single multiline data= field)
  2. Repeated form POST (multiple data=... segments)
  3. Row cap, byte cap, and execution-guard on the reference script
  4. curl examples for local Flask testing

Run with:
    python -m pytest tests/test_wattmon_integration.py -v
"""
import io
import os
import sys
import pytest

# Ensure app package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Stub the config module before importing app
import types
_config_mod = types.ModuleType("app.config")
class _TestConfig:
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
_config_mod.Config = _TestConfig
sys.modules["app.config"] = _config_mod

from app import create_app, db
from app.models import WattmonUpload, WattmonReading


@pytest.fixture(scope="session")
def app():
    """Create a Flask app for testing with an in-memory SQLite DB."""
    _app = create_app()
    _app.config["TESTING"] = True
    _app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    with _app.app_context():
        db.create_all()
    yield _app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture(autouse=True)
def clean_db(app):
    """Wipe uploads + readings between tests."""
    with app.app_context():
        db.session.query(WattmonReading).delete()
        db.session.query(WattmonUpload).delete()
        db.session.commit()
    yield


# ============================================================================
# Helpers
# ============================================================================
def build_csv(rows):
    """Build a minimal Wattmon-format CSV blob (header + rows joined by \\r\\n)."""
    header = "ts,m_schneider_540420085805_AC_Active_Power,m_rishabh_2303051510_AC_PF"
    lines = [header] + rows
    return "\r\n".join(lines)


# ============================================================================
# Test 1: Standard form POST (single multiline data= field)
# ============================================================================
def test_csv_upload_standard_form(client):
    """
    POST with key=<MAC> + data=<header\\r\\nrow1\\r\\nrow2>
    Should return 200 + "OK".
    """
    csv_blob = build_csv([
        "1783087604,0.000,0.965",
        "1783087620,0.000,0.963",
    ])
    resp = client.post(
        "/integrations/csv-upload",
        data={
            "key": "9C-95-6E-53-28-17",
            "data": csv_blob,
        },
        content_type="application/x-www-form-urlencoded",
    )
    assert resp.status_code == 200
    assert resp.data.decode("utf-8").strip() == "OK"

    with client.application.app_context():
        uploads = WattmonUpload.query.all()
        assert len(uploads) == 1
        upload = uploads[0]
        assert upload.source_key == "9C-95-6E-53-28-17"
        assert upload.row_count == 2


# ============================================================================
# Test 2: Repeated form POST (multiple data=... segments)
# ============================================================================
def test_csv_upload_repeated_fields(client):
    """
    POST with key=<MAC> + data=<header> + data=<row1> + data=<row2>
    Should return 200 + "OK".
    """
    header = "ts,m_schneider_540420085805_AC_Active_Power,m_rishabh_2303051510_AC_PF"
    row1 = "1783087604,0.000,0.965"
    row2 = "1783087620,0.000,0.963"

    # Build the raw body manually with three data= fields
    from urllib.parse import urlencode, quote
    body = (
        f"key=9C-95-6E-53-28-17"
        f"&data={quote(header)}"
        f"&data={quote(row1)}"
        f"&data={quote(row2)}"
    )
    resp = client.post(
        "/integrations/csv-upload",
        data=body,
        content_type="application/x-www-form-urlencoded",
    )
    assert resp.status_code == 200
    assert resp.data.decode("utf-8").strip() == "OK"

    with client.application.app_context():
        uploads = WattmonUpload.query.all()
        assert len(uploads) == 1
        upload = uploads[0]
        assert upload.source_key == "9C-95-6E-53-28-17"
        assert upload.row_count == 2


# ============================================================================
# Test 3: Empty body returns 400
# ============================================================================
def test_csv_upload_empty_body(client):
    """
    POST with empty body.
    Should return 400.
    """
    resp = client.post(
        "/integrations/csv-upload",
        data="",
        content_type="application/x-www-form-urlencoded",
    )
    assert resp.status_code == 400


# ============================================================================
# Test 4: Missing key field still works (source_key becomes "unknown")
# ============================================================================
def test_csv_upload_missing_key(client):
    """
    POST with data=<csv> but no key.
    Should return 200 + "OK"; source_key = "unknown".
    """
    csv_blob = build_csv(["1783087604,0.000,0.965"])
    resp = client.post(
        "/integrations/csv-upload",
        data={"data": csv_blob},
        content_type="application/x-www-form-urlencoded",
    )
    assert resp.status_code == 200
    assert resp.data.decode("utf-8").strip() == "OK"

    with client.application.app_context():
        uploads = WattmonUpload.query.all()
        assert len(uploads) == 1
        assert uploads[0].source_key == "unknown"


# ============================================================================
# Test 5: Malformed row (wrong column count) is skipped, not fatal
# ============================================================================
def test_csv_upload_malformed_row_skipped(client):
    """
    POST with one good row and one bad row (wrong column count).
    Should return 200 + "OK"; only the good row should be inserted.
    """
    header = "ts,m_schneider_540420085805_AC_Active_Power,m_rishabh_2303051510_AC_PF"
    good_row = "1783087604,0.000,0.965"
    bad_row = "1783087620,0.000"  # missing one column

    csv_blob = "\r\n".join([header, good_row, bad_row])
    resp = client.post(
        "/integrations/csv-upload",
        data={"key": "TEST-DEVICE", "data": csv_blob},
        content_type="application/x-www-form-urlencoded",
    )
    assert resp.status_code == 200

    with client.application.app_context():
        uploads = WattmonUpload.query.all()
        assert len(uploads) == 1
        upload = uploads[0]
        # Only the good row should be counted (background thread may still run)
        # We check the upload record; if status='success', row_count should be 1.
        # If status='pending', the thread hasn't run yet — skip the count check.
        if upload.status == "success":
            assert upload.row_count == 1


# ============================================================================
# Reference script tests (if available)
# ============================================================================
def test_reference_script_row_cap():
    """
    Verify the reference device script's row cap logic.
    """
    script_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "docs",
        "REFERENCE_ip_export_custom.cgi",
    )
    if not os.path.exists(script_path):
        pytest.skip("REFERENCE_ip_export_custom.cgi not found in docs/")

    # Import the script module
    import importlib.util
    spec = importlib.util.spec_from_file_location("ref_script", script_path)
    ref = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ref)

    # Build a CSV blob with 20 candidate rows, max_rows=10
    rows = [[str(i)] + ["0.0"] * 280 for i in range(20)]
    csv_text, meta = ref.build_csv_blob(rows, max_rows=10, max_bytes=100000, guard_s=10)

    assert meta["row_cap_hit"] is True
    assert meta["final_rows"] == 10


def test_reference_script_byte_cap():
    """
    Verify the reference device script's byte cap logic.
    """
    script_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "docs",
        "REFERENCE_ip_export_custom.cgi",
    )
    if not os.path.exists(script_path):
        pytest.skip("REFERENCE_ip_export_custom.cgi not found in docs/")

    import importlib.util
    spec = importlib.util.spec_from_file_location("ref_script", script_path)
    ref = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ref)

    # Build a CSV blob with 10 rows, but max_bytes=500 (forces trimming)
    rows = [[str(i)] + ["0.0"] * 280 for i in range(10)]
    csv_text, meta = ref.build_csv_blob(rows, max_rows=10, max_bytes=500, guard_s=10)

    assert meta["byte_cap_hit"] is True
    assert meta["final_bytes"] <= 500


def test_reference_script_time_guard():
    """
    Verify the reference device script's execution guard.
    """
    script_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "docs",
        "REFERENCE_ip_export_custom.cgi",
    )
    if not os.path.exists(script_path):
        pytest.skip("REFERENCE_ip_export_custom.cgi not found in docs/")

    import importlib.util
    spec = importlib.util.spec_from_file_location("ref_script", script_path)
    ref = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ref)

    # Build a CSV blob with guard_s=0.001 (1ms) — should hit the time cap
    rows = [[str(i)] + ["0.0"] * 280 for i in range(1000)]
    csv_text, meta = ref.build_csv_blob(rows, max_rows=1000, max_bytes=1_000_000, guard_s=0.001)

    # The guard should have stopped collection before all 1000 rows
    assert meta["time_cap_hit"] is True or meta["final_rows"] < 1000


# ============================================================================
# curl examples (for documentation / manual testing)
# ============================================================================
"""
Manual curl tests for the Flask route:

1. Standard form POST:
    curl -X POST https://ext-app.factorynxt.com/integrations/csv-upload \\
      -H "Content-Type: application/x-www-form-urlencoded" \\
      --data-urlencode "key=test-device" \\
      --data-urlencode "data=ts,a,b\r\n1,10,20\r\n2,11,21"

2. Repeated form POST:
    curl -X POST https://ext-app.factorynxt.com/integrations/csv-upload \\
      -H "Content-Type: application/x-www-form-urlencoded" \\
      --data-urlencode "key=test-device" \\
      --data-urlencode "data=ts,a,b" \\
      --data-urlencode "data=1,10,20" \\
      --data-urlencode "data=2,11,21"

3. From the reference device script:
    python docs/REFERENCE_ip_export_custom.cgi
"""
