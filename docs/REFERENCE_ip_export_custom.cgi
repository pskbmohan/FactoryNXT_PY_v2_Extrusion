#!/usr/bin/env python3
"""
Reference device-side exporter for the Wattmon integration device.

This script is intended to be deployed on the device (typically at
/scripts/ip_export_custom.cgi on CGI-capable metering hardware). It reads
meter samples, builds a tiny bounded CSV blob, and POSTs it to the
FactoryNXT Flask server as a single form-field payload:

    key=<device MAC>&data=<csv blob with \\r\\n row separators>

The Flask route /integrations/csv-upload accepts this and returns the
plain-text body "OK" within a few milliseconds, so the device's 30-second
CGI hard limit is never threatened.

Configuration constants at the top:
  EXPORT_MAX_ROWS        = 10         # max data rows per POST (header aside)
  EXPORT_MAX_BYTES       = 15000      # max total body size in bytes
  EXPORT_CONNECT_TIMEOUT = 3          # TCP connect timeout (seconds)
  EXPORT_RESPONSE_TIMEOUT= 8          # HTTP response read timeout (seconds)
  EXPORT_EXECUTION_GUARD = 25         # hard stop at 25 seconds (leave 5s headroom)

The script caps the CSV size on three axes:
  1. Row count   — at most EXPORT_MAX_ROWS rows
  2. Byte size   — at most EXPORT_MAX_BYTES bytes
  3. Elapsed time — never exceeds EXPORT_EXECUTION_GUARD seconds

If any cap is hit, the excess rows are truncated and the truncation is logged.

Transport strategy:
  * Uses `curl` if available on PATH (simplest, well-tested).
  * Falls back to `urllib.request` (stdlib) if curl is missing.
  * Falls back to `socket` as a last-resort fallback on embedded devices.

Logging:
  * All decisions, successes, and failures are appended to
    /tmp/ip_export_custom.log (configurable via LOG_FILE constant).

No authentication is required — the Flask route trusts this device.
"""

import csv
import io
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# ============================================================================
# Configuration — tune these to your device's capabilities and server latency
# ============================================================================
EXPORT_MAX_ROWS         = 10       # rows beyond the header
EXPORT_MAX_BYTES        = 15000    # max encoded body size
EXPORT_CONNECT_TIMEOUT  = 3        # seconds
EXPORT_RESPONSE_TIMEOUT = 8        # seconds
EXPORT_EXECUTION_GUARD  = 25       # seconds — hard-stop row collection

# Target server (device config would typically override this via env / cmdline).
WATMON_ENDPOINT = os.environ.get(
    "WATMON_ENDPOINT",
    "http://ext-app.factorynxt.com/integrations/csv-upload",
)
DEVICE_KEY = os.environ.get("DEVICE_KEY", "9C-95-6E-53-28-17")

LOG_FILE = os.environ.get("WATMON_LOG", "/tmp/ip_export_custom.log")


# ============================================================================
# Minimal logger — always appends, never raises
# ============================================================================
def log(msg):
    try:
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        with open(LOG_FILE, "a") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        # If logging itself fails, print to stderr as last resort
        sys.stderr.write(f"[log-failed] {msg}\n")


# ============================================================================
# Helpers
# ============================================================================
def elapsed_since(start):
    """Return seconds elapsed since `start` (time.time() stamp)."""
    return time.time() - start


def under_guard(start, guard_s):
    """True if we still have time budget under the execution guard."""
    return (time.time() - start) < guard_s


def build_csv_blob(rows, max_rows, max_bytes, guard_s):
    """Build a CSV blob with header + bounded rows.

    Returns (csv_text, meta_dict). ``meta_dict`` includes counts and any
    truncation reason.
    """
    start = time.time()
    meta = {"row_cap_hit": False, "byte_cap_hit": False, "time_cap_hit": False}

    # Build the canonical header — must match the Flask server's _WATMON_COLUMNS.
    # For the reference implementation we use the same schema as the device
    # actually emits (281 columns: ts + 9 Schneider × 29 + 1 Rishabh × 19).
    headers = [
        "ts",
    ]
    for sid in [
        "540420085805", "540420080451", "540420075852", "540420085806",
        "540420085810", "540420085804", "540420082234", "540420085811",
        "540420080682",
    ]:
        for field in [
            "AC_Active_Power", "AC_Reactive_Power", "AC_Apparent_Power",
            "kWh_Total_Active", "kVARh_Total_Active", "kVAh_Total_Active",
            "AC_Current_A", "AC_Current_B", "AC_Current_C",
            "AC_Voltage_AB", "AC_Voltage_BC", "AC_Voltage_CA",
            "AC_Voltage_AN", "AC_Voltage_BN", "AC_Voltage_CN",
            "AC_Active_Power_A", "AC_Active_Power_B", "AC_Active_Power_C",
            "AC_Reactive_Power_A", "AC_Reactive_Power_B", "AC_Reactive_Power_C",
            "AC_Apparent_Power_A", "AC_Apparent_Power_B", "AC_Apparent_Power_C",
            "AC_PF_A", "AC_PF_B", "AC_PF_C",
            "AC_PF", "AC_Frequency",
        ]:
            headers.append(f"m_schneider_{sid}_{field}")

    for field in [
        "AC_Active_Power", "AC_Reactive_Power", "AC_Apparent_Power",
        "kWh_Total_Import", "kWh_Total_Export",
        "AC_Voltage_AN", "AC_Voltage_BN", "AC_Voltage_CN",
        "AC_Current_A", "AC_Current_B", "AC_Current_C",
        "AC_Active_Power_A", "AC_Active_Power_B", "AC_Active_Power_C",
        "AC_PF", "AC_Frequency",
        "kVARh_Lead", "kVARh_Lag", "kVAh_Total_Active",
    ]:
        headers.append(f"m_rishabh_2303051510_{field}")

    # Cap rows by the time-guard too — stop generating rows if we run low.
    collected_rows = []
    for i, row in enumerate(rows):
        if i >= max_rows:
            meta["row_cap_hit"] = True
            log(f"BUILD: row cap reached at {max_rows} rows")
            break
        if not under_guard(start, guard_s):
            meta["time_cap_hit"] = True
            log(f"BUILD: time-guard reached at row {i}; stopping collection")
            break
        collected_rows.append(row)

    # Build the CSV blob with \r\n separators (server-agnostic).
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(headers)
    for row in collected_rows:
        # Pad/truncate each row to exactly the header length (be defensive).
        if len(row) < len(headers):
            row = list(row) + [""] * (len(headers) - len(row))
        elif len(row) > len(headers):
            row = row[: len(headers)]
        writer.writerow(row)

    csv_text = buf.getvalue()
    csv_bytes = csv_text.encode("utf-8")

    # Trim rows off the tail until we fit within max_bytes.
    while len(csv_bytes) > max_bytes and len(collected_rows) > 0:
        collected_rows.pop()
        meta["byte_cap_hit"] = True
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\r\n")
        writer.writerow(headers)
        for row in collected_rows:
            if len(row) < len(headers):
                row = list(row) + [""] * (len(headers) - len(row))
            elif len(row) > len(headers):
                row = row[: len(headers)]
            writer.writerow(row)
        csv_text = buf.getvalue()
        csv_bytes = csv_text.encode("utf-8")
    if meta["byte_cap_hit"]:
        log(f"BUILD: byte cap hit, trimmed to {len(collected_rows)} rows "
            f"(payload={len(csv_bytes)} bytes)")

    meta["final_rows"] = len(collected_rows)
    meta["final_bytes"] = len(csv_bytes)
    return csv_text, meta


def sample_rows(n):
    """Produce `n` realistic meter rows for the demo.

    In the real device, this is replaced by the live sample-reading loop.
    """
    import random
    now = int(time.time())
    rows = []
    for i in range(n):
        # ts first, then 280 columns of random 3-decimal floats
        row = [str(now + i)]
        for _ in range(280):
            row.append(f"{random.uniform(-100.0, 1000.0):.3f}")
        rows.append(row)
    return rows


# ============================================================================
# HTTP transport — curl, urllib, or socket
# ============================================================================
def post_with_curl(url, form_body, connect_t, read_t):
    if shutil.which("curl") is None:
        return None
    try:
        result = subprocess.run(
            [
                "curl", "-sS", "-X", "POST", url,
                "-H", "Content-Type: application/x-www-form-urlencoded",
                "--connect-timeout", str(connect_t),
                "--max-time", str(read_t),
                "-d", form_body,
                "-w", "HTTP_STATUS:%{http_code}",
                "-o", "/dev/stdout",
            ],
            capture_output=True, timeout=read_t + 2, text=True,
        )
        status_match = None
        body = result.stdout
        if "HTTP_STATUS:" in body:
            parts = body.rsplit("HTTP_STATUS:", 1)
            body = parts[0]
            status_match = parts[1].strip()
        return {"status": int(status_match) if status_match else 0, "body": body}
    except Exception as e:
        log(f"CURL: failed — {type(e).__name__}: {e}")
        return None


def post_with_urllib(url, form_body, read_t):
    try:
        req = urllib.request.Request(
            url,
            data=form_body.encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=read_t) as resp:
            body = resp.read(512).decode("utf-8", errors="replace")
            return {"status": resp.status, "body": body}
    except urllib.error.HTTPError as e:
        try:
            body = e.read(512).decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return {"status": e.code, "body": body}
    except Exception as e:
        log(f"URLLIB: failed — {type(e).__name__}: {e}")
        return None


def post_with_socket(url, form_body, connect_t, read_t):
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        path = parsed.path or "/"

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(connect_t)
        s.connect((host, port))

        body_bytes = form_body.encode("utf-8")
        request_line = (
            f"POST {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            f"Content-Type: application/x-www-form-urlencoded\r\n"
            f"Content-Length: {len(body_bytes)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        ).encode("ascii") + body_bytes

        s.sendall(request_line)
        s.settimeout(read_t)

        response = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            response += chunk
            if len(response) > 4096:  # stop greedily reading
                break
        s.close()

        # Parse status line
        head, _, _ = response.partition(b"\r\n\r\n")
        status_line = head.split(b"\r\n", 1)[0].decode("ascii", errors="replace")
        parts = status_line.split(" ", 2)
        status = int(parts[1]) if len(parts) >= 2 else 0
        body = response.split(b"\r\n\r\n", 1)[1].decode("utf-8", errors="replace") \
               if b"\r\n\r\n" in response else ""
        return {"status": status, "body": body}
    except Exception as e:
        log(f"SOCKET: failed — {type(e).__name__}: {e}")
        return None


def http_post(url, form_body, connect_t, read_t):
    """Try curl → urllib → socket, return the first successful response."""
    result = post_with_curl(url, form_body, connect_t, read_t)
    if result is not None:
        return result
    result = post_with_urllib(url, form_body, read_t)
    if result is not None:
        return result
    return post_with_socket(url, form_body, connect_t, read_t)


# ============================================================================
# Entry point
# ============================================================================
def main():
    start = time.time()
    log(f"--- EXPORT START key={DEVICE_KEY} endpoint={WATMON_ENDPOINT}")

    if not under_guard(start, EXPORT_EXECUTION_GUARD):
        log("ABORT: execution-guard already exceeded at startup")
        return 1

    # 1. Gather meter samples (real device substitutes its own reading loop).
    log("STEP 1: collecting samples")
    rows = sample_rows(EXPORT_MAX_ROWS * 3)   # over-collect so caps are exercised
    log(f"  collected {len(rows)} candidate rows in {elapsed_since(start)*1000:.0f}ms")

    if not under_guard(start, EXPORT_EXECUTION_GUARD):
        log("ABORT: time-guard exceeded during sample collection")
        return 1

    # 2. Build a bounded CSV blob (header + capped rows).
    log(f"STEP 2: building CSV blob (max_rows={EXPORT_MAX_ROWS}, "
        f"max_bytes={EXPORT_MAX_BYTES}, guard_s={EXPORT_EXECUTION_GUARD})")
    csv_text, meta = build_csv_blob(
        rows, EXPORT_MAX_ROWS, EXPORT_MAX_BYTES, EXPORT_EXECUTION_GUARD,
    )
    log(f"  final: {meta['final_rows']} rows, {meta['final_bytes']} bytes "
        f"(row_cap={meta['row_cap_hit']}, byte_cap={meta['byte_cap_hit']}, "
        f"time_cap={meta['time_cap_hit']})")

    if not under_guard(start, EXPORT_EXECUTION_GUARD):
        log("ABORT: time-guard exceeded during CSV build")
        return 1

    # 3. Build the form body (URL-encode key + csv).
    form_body = urllib.parse.urlencode({
        "key": DEVICE_KEY,
        "data": csv_text,
    })
    log(f"STEP 3: POST {WATMON_ENDPOINT}  body={len(form_body)} bytes")

    # 4. Post and read the status line + tiny body sample.
    result = http_post(
        WATMON_ENDPOINT, form_body,
        EXPORT_CONNECT_TIMEOUT, EXPORT_RESPONSE_TIMEOUT,
    )

    elapsed_ms = elapsed_since(start) * 1000
    if result is None:
        log(f"FAIL: no transport worked; elapsed={elapsed_ms:.0f}ms")
        return 1

    status = result["status"]
    body = (result.get("body") or "").strip()
    ok = (status == 200) or ("OK" in body)
    log(f"RESULT: status={status}, body_sample={body[:120]!r}, "
        f"elapsed={elapsed_ms:.0f}ms, ok={ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log(f"FATAL: {type(e).__name__}: {e}")
        sys.exit(1)
