#!/usr/bin/env bash
# ============================================================================
# LMS Platform — backup (DB + media + .env.prod reference)
# Usage: ./deploy/backup.sh [/opt/backups]
# Cron (host, daily 04:00 — note escaped %):
#   0 4 * * * cd /opt/lms && ./deploy/backup.sh /opt/backups >>/var/log/lms-backup.log 2>&1
#   0 5 * * * find /opt/backups -name 'lms_*.sql.gz' -mtime +14 -delete
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

OUT="${1:-/opt/backups}"
COMPOSE="docker compose --env-file .env.prod -f docker-compose.prod.yml"
DATE=$(date +%F)
mkdir -p "$OUT"
chmod 700 "$OUT"

echo ">>> DB dump"
$COMPOSE exec -T db pg_dump -U "${DB_USER:-lms_user}" "${DB_NAME:-lms_platform}" \
  | gzip > "$OUT/lms_${DATE}.sql.gz"
ls -lh "$OUT/lms_${DATE}.sql.gz"
gunzip -c "$OUT/lms_${DATE}.sql.gz" | head -c 120; echo

echo ">>> Media volume"
MEDIA_VOL=$($COMPOSE config --volumes 2>/dev/null | grep media | head -1 || echo "lms-platform-prod_media_volume")
docker run --rm -v "${MEDIA_VOL}:/media:ro" -v "$OUT:/backup" alpine \
  tar czf "/backup/media_${DATE}.tar.gz" -C /media .
ls -lh "$OUT/media_${DATE}.tar.gz"

echo ">>> BACKUP OK: $OUT/lms_${DATE}.sql.gz + media_${DATE}.tar.gz"
echo "    Restore DB (STAGING ONLY): gunzip -c $OUT/lms_${DATE}.sql.gz | $COMPOSE exec -T db psql -U <user> -d <db>"
