#!/bin/sh
set -e

echo "Postgres is ready — starting setup..."

# ── Normalise DATABASE_URL ───────────────────────────────────────────────────
# DigitalOcean App Platform injects DATABASE_URL as postgres://...
# SQLAlchemy needs postgresql+psycopg2://  — normalise it once here so
# both flask db upgrade and the app itself use the correct driver string.
RAW_URL="${DATABASE_URL:-postgresql+psycopg2://postgres:postgres@localhost:5432/factorynxt}"
case "$RAW_URL" in
  postgres://)
    DB_URL="postgresql+psycopg2://${RAW_URL#postgres://}" ;;
  postgresql://)
    DB_URL="postgresql+psycopg2://${RAW_URL#postgresql://}" ;;
  *)
    DB_URL="$RAW_URL" ;;
esac
export DATABASE_URL="$DB_URL"
echo "Using DB: ${DATABASE_URL%%@*}@****"
# ─────────────────────────────────────────────────────────────────────────────

# Init migrations folder if it doesn't exist
if [ ! -d "migrations" ]; then
  echo "No migrations folder found — running flask db init..."
  flask db init
fi

# ── Nuclear alembic_version reset (direct SQL, not flask db stamp) ───────
# The migration graph accumulated overlapping branches that repeatedly
# tripped Alembic's overlap detection on deploy. All old migration files
# have been moved to migrations/_archived_versions/. The schema is already
# created by db.create_all() at startup (see app/__init__.py).
#
# The single base marker base_20260701.py in migrations/versions/ has
# down_revision=None.  We need alembic_version to point to it.
#
# `flask db stamp base_20260701` cannot be used because Alembic first
# validates the CURRENT revision against the graph; if it's a stale value
# like 'aps_add_notes_columns' (whose file is archived), Alembic errors
# out: "Can't locate revision identified by 'aps_add_notes_columns'".
#
# The fix: write directly to the alembic_version table with Python,
# bypassing Alembic's validation entirely.  We create the table if it
# doesn't exist (fresh DB).  Then flask db upgrade sees a valid head
# and no-ops (head == base_20260701 == what we just stamped).
# ─────────────────────────────────────────────────────────────────────────
echo "Forcing alembic_version to base_20260701 (direct SQL, bypassing Alembic)..."
python3 - <<'PYEOF'
import os
from sqlalchemy import create_engine, text

url = os.environ["DATABASE_URL"]
engine = create_engine(url)
target = "base_20260701"

with engine.begin() as conn:
    # The alembic_version table may have accumulated multiple rows
    # (one per branch in the old merge graph).  The table has a
    # unique constraint on version_num (alembic_version_pkc), so we
    # can't just UPDATE or INSERT.  Nuclear option: wipe every row
    # then insert exactly one pointing to our single base marker.
    conn.execute(text(
        "CREATE TABLE IF NOT EXISTS alembic_version "
        "(version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
    ))
    rows = conn.execute(text(
        "SELECT version_num FROM alembic_version"
    )).fetchall()
    current_first = rows[0][0] if rows else None
    extra_count = max(0, len(rows) - 1)

    # Delete every row (handles the multi-branch case)
    if rows:
        conn.execute(text("DELETE FROM alembic_version"))
        print(
            f"Cleared alembic_version: had {len(rows)} row(s) "
            f"(first={current_first}, {extra_count} extra branch row(s))"
        )

    # Insert exactly one row
    conn.execute(text(
        "INSERT INTO alembic_version (version_num) VALUES (:v)"
    ), {"v": target})
    print(f"Inserted alembic_version: {target}")

engine.dispose()
PYEOF

echo "Running flask db upgrade to apply any future migrations..."
flask db upgrade

# ── Auto-seed on fresh database ─────────────────────────────────────────────
# Check if the DB is empty (no Lines seeded yet). If so, run the full seed
# script. The seed functions are all idempotent so re-runs are safe.
NEEDS_SEED=$(python3 - <<'PYEOF'
import os, sys
try:
    from sqlalchemy import create_engine, text
    url = os.environ['DATABASE_URL']
    engine = create_engine(url)
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM lines")).scalar()
        print('yes' if count == 0 else 'no')
except Exception as e:
    print('no', file=sys.stderr)
    print(f'seed-check error: {e}', file=sys.stderr)
    print('no')
PYEOF
)

if [ "$NEEDS_SEED" = "yes" ]; then
  echo "Empty database detected — running seed_data.py..."
  python scripts/seed_data.py
  echo "Seed complete."
else
  echo "Database already seeded — skipping seed_data.py."
fi
# ─────────────────────────────────────────────────────────────────────────────

# ── Two ports, one Flask app ────────────────────────────────────────────────
# - Port 5555: web UI (browser + Cloudflare HTTPS)
# - Port 80:   Wattmon device upload (plain HTTP, direct to origin, no TLS)
#
# The Wattmon device only speaks HTTP, so any POST to :5555 (behind
# Cloudflare) gets a 301 → HTTPS and the device times out. Port 80 bypasses
# Cloudflare entirely so the device can POST directly to the origin.
#
# Device POSTs to:
#     http://<origin-host>/integrations/csv-upload
#
WEB_PORT="${WEB_PORT:-5555}"
echo "Starting Flask app on port ${WEB_PORT} (web UI) + port 80 (Wattmon device)..."
python3 -c "
from app import create_app
app = create_app()
app.run(host='0.0.0.0', port=${WEB_PORT}, debug=False, use_reloader=False)
" >> /var/log/wattmon-device.log 2>&1 &
WEB_PID=$!
echo "Web listener started (PID ${WEB_PID})"
# Foreground: port 80 (keeps container alive)
exec python3 -c "
from app import create_app
app = create_app()
app.run(host='0.0.0.0', port=80, debug=False, use_reloader=False)
"
