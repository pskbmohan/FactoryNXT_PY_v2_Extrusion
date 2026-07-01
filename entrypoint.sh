#!/bin/sh
set -e

echo "Postgres is ready — starting setup..."

# Init migrations folder if it doesn't exist
if [ ! -d "migrations" ]; then
  echo "No migrations folder found — running flask db init..."
  flask db init
fi

# ── Brownfield stamp ────────────────────────────────────────────────────────
# db.create_all() inside create_app() materialises every SQLAlchemy model
# table WITHOUT recording any revision in alembic_version. When that
# happens, flask db upgrade tries to replay every migration from scratch
# and crashes on the very first CREATE TABLE (bom_items already exists).
#
# Fix: use Python/SQLAlchemy (always available) to check if bom_items
# exists AND alembic_version is empty. If so, stamp to the current tip
# so Alembic skips every migration already applied by db.create_all().
#
# NOTE: psql is NOT installed in this Python image, which is why the
# previous version using psql silently failed.
NEED_STAMP=$(python3 - <<'PYEOF'
import os, sys
try:
    from sqlalchemy import create_engine, text
    url = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@db:5432/factorynxt')
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
  flask db stamp aps_add_notes_columns
fi
# ───────────────────────────────────────────────────────────────────────────

echo "Running flask db upgrade to apply pending migrations..."
flask db upgrade heads

echo "Starting Flask app on port 5555..."
exec python -c "from app import create_app; app = create_app(); app.run(host='0.0.0.0', port=5555, debug=True)"
