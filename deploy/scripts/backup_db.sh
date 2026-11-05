#!/usr/bin/env bash
# ============================================================================
# Grandec — daily PostgreSQL backup with rotation and verification.
#
#   deploy/scripts/backup_db.sh [BACKUP_DIR]          (default /opt/backups/lms)
#
# Layout:  BACKUP_DIR/daily/lms_YYYYmmdd_HHMMSS.sql.gz   keep the newest 7
#          BACKUP_DIR/weekly/lms_YYYYmmdd_HHMMSS.sql.gz  keep the newest 4
# A Sunday's daily backup is also copied into weekly/.
#
# A backup only counts when ALL of these hold; otherwise the file is deleted,
# older backups are NOT rotated away, the script exits non-zero and (when
# BACKUP_ALERT_TELEGRAM_* / TELEGRAM_BOT_TOKEN + ADMIN_TELEGRAM_ID are set) the
# admin gets a Telegram message:
#   1. pg_dump succeeded (pipefail),
#   2. `gzip -t` passes,
#   3. size >= BACKUP_MIN_BYTES and not under 50 % of the previous daily backup,
#   4. the dump contains at least BACKUP_MIN_TABLES CREATE TABLE statements.
#
# Modes (DUMP_MODE):
#   docker  (default) pg_dump inside the compose `db` container (production).
#   local   pg_dump on this machine; connection from PGHOST/PGPORT/PGUSER/
#           PGPASSWORD/PGDATABASE (used by the restore test).
#
# This script does NOT install a cron job or a service. See docs/BACKUP.md.
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

BACKUP_DIR="${1:-${BACKUP_DIR:-/opt/backups/lms}}"
DUMP_MODE="${DUMP_MODE:-docker}"
KEEP_DAILY="${KEEP_DAILY:-7}"
KEEP_WEEKLY="${KEEP_WEEKLY:-4}"
BACKUP_MIN_BYTES="${BACKUP_MIN_BYTES:-20000}"
BACKUP_MIN_TABLES="${BACKUP_MIN_TABLES:-50}"
PREFIX="${BACKUP_PREFIX:-lms}"

umask 077
mkdir -p "$BACKUP_DIR/daily" "$BACKUP_DIR/weekly"
chmod 700 "$BACKUP_DIR" "$BACKUP_DIR/daily" "$BACKUP_DIR/weekly"

STAMP="$(date +%Y%m%d_%H%M%S)"
FINAL="$BACKUP_DIR/daily/${PREFIX}_${STAMP}.sql.gz"
PARTIAL="$FINAL.partial"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

alert() {
  # Best effort; never hides the original failure.
  local token="${BACKUP_ALERT_TELEGRAM_TOKEN:-${TELEGRAM_BOT_TOKEN:-}}"
  local chat="${BACKUP_ALERT_TELEGRAM_CHAT:-${ADMIN_TELEGRAM_ID:-}}"
  [ -n "$token" ] && [ -n "$chat" ] || return 0
  curl -fsS -m 20 -X POST "https://api.telegram.org/bot${token}/sendMessage" \
    --data-urlencode "chat_id=${chat}" \
    --data-urlencode "text=⚠️ Grandec zaxira nusxasi MUVAFFAQIYATSIZ: $1" >/dev/null 2>&1 || true
}

fail() {
  log "ERROR: $*" >&2
  rm -f "$PARTIAL"
  alert "$*"
  exit 1
}

# --- environment (docker mode needs DB_USER / DB_NAME from .env.prod) ----------
if [ "$DUMP_MODE" = "docker" ]; then
  cd "$PROJECT_DIR"
  if [ -f .env.prod ]; then
    set -a
    # shellcheck disable=SC1091
    source <(grep -E '^(DB_USER|DB_NAME|TELEGRAM_BOT_TOKEN|ADMIN_TELEGRAM_ID)=' .env.prod || true)
    set +a
  fi
  DB_USER="${DB_USER:-lms_user}"
  DB_NAME="${DB_NAME:-lms_platform}"
  COMPOSE="${COMPOSE:-docker compose --env-file .env.prod -f docker-compose.prod.yml}"
fi

# --- 1. dump ------------------------------------------------------------------
log "Backup start ($DUMP_MODE) -> $FINAL"
if [ "$DUMP_MODE" = "docker" ]; then
  # shellcheck disable=SC2086
  $COMPOSE exec -T db pg_dump -U "$DB_USER" --no-owner --no-privileges "$DB_NAME" | gzip -6 > "$PARTIAL" \
    || fail "pg_dump or gzip failed"
elif [ "$DUMP_MODE" = "local" ]; then
  pg_dump --no-owner --no-privileges "${PGDATABASE:?PGDATABASE must be set in local mode}" | gzip -6 > "$PARTIAL" \
    || fail "pg_dump or gzip failed"
else
  fail "unknown DUMP_MODE '$DUMP_MODE' (docker|local)"
fi

# --- 2-4. verify ----------------------------------------------------------------
gzip -t "$PARTIAL" 2>/dev/null || fail "gzip integrity check failed"

SIZE="$(wc -c < "$PARTIAL" | tr -d ' ')"
[ "$SIZE" -ge "$BACKUP_MIN_BYTES" ] || fail "backup is only ${SIZE} bytes (minimum ${BACKUP_MIN_BYTES})"

PREV="$(ls -1t "$BACKUP_DIR"/daily/${PREFIX}_*.sql.gz 2>/dev/null | head -n1 || true)"
if [ -n "$PREV" ]; then
  PREV_SIZE="$(wc -c < "$PREV" | tr -d ' ')"
  if [ "$PREV_SIZE" -gt 0 ] && [ $((SIZE * 2)) -lt "$PREV_SIZE" ]; then
    fail "backup (${SIZE} B) is less than half the previous one (${PREV_SIZE} B); keeping the old backups"
  fi
fi

TABLES="$(gzip -dc "$PARTIAL" | grep -c '^CREATE TABLE ' || true)"
[ "$TABLES" -ge "$BACKUP_MIN_TABLES" ] || fail "dump has only ${TABLES} tables (minimum ${BACKUP_MIN_TABLES})"

mv "$PARTIAL" "$FINAL"
( cd "$BACKUP_DIR/daily" && sha256sum "$(basename "$FINAL")" > "$(basename "$FINAL").sha256" )
log "OK daily: $(basename "$FINAL")  ${SIZE} bytes, ${TABLES} tables, gzip verified"

# --- weekly copy on Sundays ------------------------------------------------------
if [ "$(date +%u)" = "${WEEKLY_DAY:-7}" ]; then
  cp "$FINAL" "$BACKUP_DIR/weekly/"
  cp "$FINAL.sha256" "$BACKUP_DIR/weekly/"
  log "OK weekly copy"
fi

# --- rotation (only reached after a verified backup) -------------------------------
rotate() {
  local dir="$1" keep="$2"
  ls -1t "$dir"/${PREFIX}_*.sql.gz 2>/dev/null | tail -n +"$((keep + 1))" | while read -r old; do
    rm -f -- "$old" "$old.sha256"
    log "rotated out $(basename "$old")"
  done
}
rotate "$BACKUP_DIR/daily" "$KEEP_DAILY"
rotate "$BACKUP_DIR/weekly" "$KEEP_WEEKLY"

log "Backup complete. daily=$(ls -1 "$BACKUP_DIR"/daily/${PREFIX}_*.sql.gz | wc -l) weekly=$(ls -1 "$BACKUP_DIR"/weekly/${PREFIX}_*.sql.gz 2>/dev/null | wc -l)"
