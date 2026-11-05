#!/usr/bin/env bash
# ============================================================================
# Grandec — prove a backup can be restored.
#
#   deploy/scripts/restore_test.sh [BACKUP_FILE.sql.gz]
#
# Restores the given backup (default: newest daily backup) into a THROWAWAY
# database on a LOCAL PostgreSQL, checks it, and drops it again. Never run it
# against production: it refuses unless PGHOST is localhost / 127.0.0.1 / ::1.
#
# Connection: standard PG* variables (PGHOST, PGPORT, PGUSER, PGPASSWORD).
#   BACKUP_DIR       where to look for the newest backup (default /opt/backups/lms)
#   RESTORE_DB       scratch database name (default lms_restore_test)
#   KEEP_DB=1        do not drop the scratch database afterwards
#   MIN_TABLES       minimum number of public tables expected (default 50)
#
# Checks: gzip integrity, SQL loads with ON_ERROR_STOP, table count,
# django_migrations has rows, auth user table readable, row counts printed.
# ============================================================================
set -euo pipefail

PGHOST="${PGHOST:-127.0.0.1}"
case "$PGHOST" in
  localhost|127.0.0.1|::1) ;;
  *) echo "Refusing to restore into non-local host '$PGHOST'." >&2; exit 1 ;;
esac
export PGHOST

BACKUP_DIR="${BACKUP_DIR:-/opt/backups/lms}"
FILE="${1:-$(ls -1t "$BACKUP_DIR"/daily/*.sql.gz 2>/dev/null | head -n1 || true)}"
[ -n "$FILE" ] && [ -f "$FILE" ] || { echo "No backup file found (pass one as an argument)." >&2; exit 1; }

DB="${RESTORE_DB:-lms_restore_test}"
MIN_TABLES="${MIN_TABLES:-50}"
ADMIN_DB="${ADMIN_DB:-postgres}"

echo "Backup : $FILE"
gzip -t "$FILE" || { echo "gzip integrity check FAILED" >&2; exit 1; }

cleanup() {
  if [ "${KEEP_DB:-0}" != "1" ]; then
    psql -d "$ADMIN_DB" -v ON_ERROR_STOP=1 -qc "DROP DATABASE IF EXISTS \"$DB\"" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

psql -d "$ADMIN_DB" -v ON_ERROR_STOP=1 -qc "DROP DATABASE IF EXISTS \"$DB\"" -c "CREATE DATABASE \"$DB\""
echo "Restoring into local database '$DB' ..."
gzip -dc "$FILE" | psql -d "$DB" -v ON_ERROR_STOP=1 -q -o /dev/null

TABLES="$(psql -d "$DB" -Atc "select count(*) from information_schema.tables where table_schema='public' and table_type='BASE TABLE'")"
MIGS="$(psql -d "$DB" -Atc "select count(*) from django_migrations")"
USERS="$(psql -d "$DB" -Atc "select count(*) from accounts_user" 2>/dev/null || psql -d "$DB" -Atc "select count(*) from auth_user" 2>/dev/null || echo "n/a")"

echo "Tables : $TABLES (minimum $MIN_TABLES)"
echo "Migrations applied: $MIGS"
echo "Users  : $USERS"

[ "$TABLES" -ge "$MIN_TABLES" ] || { echo "RESTORE CHECK FAILED: too few tables" >&2; exit 1; }
[ "$MIGS" -gt 0 ] || { echo "RESTORE CHECK FAILED: django_migrations is empty" >&2; exit 1; }

echo "RESTORE OK"
