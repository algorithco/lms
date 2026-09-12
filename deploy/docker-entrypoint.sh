#!/usr/bin/env bash
# ============================================================================
# LMS Platform — Docker entrypoint
#
# Order: wait for PostgreSQL → apply migrations → collect static files →
#        exec the container command (daphne / celery / bot / etc.)
# ============================================================================
set -euo pipefail

echo "[entrypoint] Waiting for database at ${DB_HOST:-db}:${DB_PORT:-5432} ..."
python - <<'PY'
import os
import sys
import time

import psycopg2

host = os.environ.get("DB_HOST", "db")
port = int(os.environ.get("DB_PORT", "5432"))
name = os.environ.get("DB_NAME", "lms_platform")
user = os.environ.get("DB_USER", "lms_user")
password = os.environ.get("DB_PASSWORD", "")

for attempt in range(60):
    try:
        conn = psycopg2.connect(
            host=host, port=port, dbname=name, user=user, password=password,
            connect_timeout=3,
        )
        conn.close()
        print("[entrypoint] Database is ready.")
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        if attempt == 59:
            print(f"[entrypoint] Database never became ready: {exc}", file=sys.stderr)
            sys.exit(1)
        time.sleep(2)
PY

# Only one container should own migrations/collectstatic (the web service);
# set SKIP_DB_STARTUP=1 on celery/bot containers to avoid races.
if [[ "${SKIP_DB_STARTUP:-0}" == "1" ]]; then
    echo "[entrypoint] SKIP_DB_STARTUP=1 — skipping migrate/collectstatic"
else
    echo "[entrypoint] Applying migrations ..."
    python manage.py migrate --noinput

    echo "[entrypoint] Collecting static files ..."
    python manage.py collectstatic --noinput
fi

echo "[entrypoint] Executing: $*"
exec "$@"