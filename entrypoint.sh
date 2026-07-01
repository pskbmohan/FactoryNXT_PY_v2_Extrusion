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

# ── Brownfield stamp ────────────────────────────────────────────────────────
# db.create_all() inside create_app() materialises every SQLAlchemy model
# table WITHOUT recording any revision in alembic_version. When that
# happens, flask db upgrade tries to replay every migration from scratch
# and crashes on the very first CREATE TABLE.
#
# Fix: check if bom_items exists AND alembic_version is empty. If so,
# stamp to the current tip so Alembic skips already-applied migrations.
NEED_STAMP=$(python3 - <<'PYEOF'
import os, sys
try:
    from sqlalchemy import create_engine, text
    url = os.environ['DATABASE_URL']
    engine = create_engine(url)
    with engine.connect() as conn:
        tbl = conn.execute(text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name='bom_items' LIMIT 1"
        )).scalar()
        if not tbl:
            print('no')
            sys.exit(0)
        try:
            ver = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar()
        except Exception:
            ver = None
        print('yes' if not ver else 'no')
except Exception as e:
    print('no', file=sys.stderr)
    print(f'stamp-check error: {e}', file=sys.stderr)
    print('no')
PYEOF
)

if [ "$NEED_STAMP" = "yes" ]; then
  echo "Tables exist but alembic_version is empty — stamping to current head..."
  flask db stamp head
fi
# ───────────────────────────────────────────────────────────────────────────

echo "Running flask db upgrade to apply pending migrations..."
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

echo "Starting Flask app on port 5555..."
exec python -c "from app import create_app; app = create_app(); app.run(host='0.0.0.0', port=5555, debug=True)"
