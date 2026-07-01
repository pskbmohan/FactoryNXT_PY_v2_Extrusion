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

# ── Nuclear alembic_version reset ─────────────────────────────────────────
# The migration graph accumulated overlapping branches that repeatedly
# tripped Alembic's overlap detection on deploy.  The schema is already
# created by db.create_all() at startup (see app/__init__.py), so the
# migrations serve only as a version marker going forward.
#
# We unconditionally stamp `base_20260701` (the single, clean base marker
# in migrations/versions/base_20260701.py).  This:
#   - Corrects any stale alembic_version (e.g. 20260702_die_ext) that
#     no longer exists in the file tree.
#   - Is a no-op when alembic_version already == base_20260701.
#   - Lets flask db upgrade below become a no-op too (already at head).
#
# The only way this could ever run an actual upgrade is if a FUTURE
# migration is added with down_revision='base_20260701' — in which
# case flask db upgrade will pick it up normally.
# ─────────────────────────────────────────────────────────────────────────
echo "Stamping alembic_version to base_20260701 (nuclear reset)..."
flask db stamp base_20260701

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

echo "Starting Flask app on port 5555..."
exec python -c "from app import create_app; app = create_app(); app.run(host='0.0.0.0', port=5555, debug=True)"
