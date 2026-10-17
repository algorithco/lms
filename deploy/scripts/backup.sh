#!/usr/bin/env bash
# ============================================================================
# GRAND EDUCATION (grandec.uz) — PostgreSQL Auto-Backup & Retention Script
#
# Schedule via cron on the host VPS (runs daily at 03:00):
#   0 3 * * * cd /opt/lms && ./deploy/scripts/backup.sh >> /var/log/grandec-backup.log 2>&1
#
# Features:
#   1. pg_dump compressed to .sql.gz with timestamp
#   2. Local 7-day retention: automatically deletes backups older than 7 days
#   3. Offsite backup: sends .sql.gz directly to Telegram if configured
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_DIR"

BACKUP_DIR="${1:-/opt/backups}"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

DATE_STR=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/grandec_db_${DATE_STR}.sql.gz"

# Source environment if available
if [ -f .env.prod ]; then
    # Export only valid shell assignments
    set -a
    # shellcheck disable=SC1091
    source <(grep -E '^[A-Za-z0-9_]+=' .env.prod || true)
    set +a
fi

DB_USER="${DB_USER:-lms_user}"
DB_NAME="${DB_NAME:-lms_platform}"
COMPOSE="docker compose --env-file .env.prod -f docker-compose.prod.yml"

echo "=== [$(date '+%Y-%m-%d %H:%M:%S')] Starting PostgreSQL Database Backup ==="
echo "Target file: $BACKUP_FILE"

# 1. Execute pg_dump inside db container and compress with gzip
$COMPOSE exec -T db pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_FILE"

if [ ! -s "$BACKUP_FILE" ]; then
    echo "ERROR: Backup file $BACKUP_FILE is empty or failed to generate!" >&2
    exit 1
fi

FILE_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "✅ Database backup created successfully. Size: $FILE_SIZE"

# 2. Retention policy: Remove backups older than 7 days
echo ">>> Enforcing 7-day retention policy in $BACKUP_DIR..."
find "$BACKUP_DIR" -type f \( -name "grandec_db_*.sql.gz" -o -name "lms_*.sql.gz" -o -name "media_*.tar.gz" \) -mtime +7 -exec rm -vf {} \;
echo "✅ Retention enforcement complete."

# 3. Offsite Telegram dispatch if token & chat_id provided
TG_TOKEN="${BACKUP_TELEGRAM_BOT_TOKEN:-${TELEGRAM_BOT_TOKEN:-}}"
TG_CHAT="${BACKUP_TELEGRAM_CHAT_ID:-${ADMIN_TELEGRAM_ID:-5582178765}}"

if [ -n "$TG_TOKEN" ] && [ -n "$TG_CHAT" ]; then
    echo ">>> Sending offsite backup to Telegram chat: $TG_CHAT..."
    FILE_BYTES=$(wc -c < "$BACKUP_FILE" 2>/dev/null || stat -c%s "$BACKUP_FILE" 2>/dev/null || echo 0)
    # Telegram Bot API max file upload is 50MB
    if [ "$FILE_BYTES" -gt 0 ] && [ "$FILE_BYTES" -lt 52428800 ]; then
        curl -fsS -X POST "https://api.telegram.org/bot${TG_TOKEN}/sendDocument" \
            -F "chat_id=${TG_CHAT}" \
            -F "caption=📦 <b>Grandec DB Auto-Backup</b>%0A📅 Sana: $(date '+%Y-%m-%d %H:%M:%S')%0A💾 Hajm: ${FILE_SIZE}%0A🛡 Saqlanish: 7 kun" \
            -F "parse_mode=HTML" \
            -F "document=@${BACKUP_FILE}" >/dev/null 2>&1 && echo "✅ Offsite Telegram backup sent successfully." || echo "⚠️ Telegram offsite upload failed (non-fatal)."
    else
        echo "⚠️ Backup size (${FILE_SIZE}) exceeds Telegram 50MB limit or is invalid; skipping Telegram upload."
    fi
else
    echo "ℹ️ Telegram backup credentials not set (BACKUP_TELEGRAM_BOT_TOKEN / BACKUP_TELEGRAM_CHAT_ID); skipping offsite upload."
fi

echo "=== [$(date '+%Y-%m-%d %H:%M:%S')] Backup Complete ==="
