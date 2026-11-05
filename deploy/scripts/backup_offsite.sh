#!/usr/bin/env bash
# ============================================================================
# Grandec — copy the verified backups OFF the server.
#
#   OFFSITE_TARGET=user@host:/path/to/dir  deploy/scripts/backup_offsite.sh [BACKUP_DIR]
#
# Copies BACKUP_DIR/daily and BACKUP_DIR/weekly (the .sql.gz files and their
# .sha256) with rsync over SSH, then re-checks the checksums on the remote side.
# The destination is not decided yet: with OFFSITE_TARGET unset the script does
# nothing and exits 2, so it can sit in the repo without ever sending anything.
#
#   OFFSITE_SSH_KEY   private key file to use (default: the ssh agent / ~/.ssh)
#   OFFSITE_SSH_PORT  default 22
#   OFFSITE_DELETE=1  also delete remote files that were rotated out locally
#
# It never prints credentials and never copies .env files. Backups contain
# personal data: the destination must be encrypted storage you control.
# ============================================================================
set -euo pipefail

BACKUP_DIR="${1:-${BACKUP_DIR:-/opt/backups/lms}}"
TARGET="${OFFSITE_TARGET:-}"

if [ -z "$TARGET" ]; then
  echo "OFFSITE_TARGET is not set (user@host:/path). Nothing was copied." >&2
  exit 2
fi
[ -d "$BACKUP_DIR" ] || { echo "Backup directory $BACKUP_DIR not found" >&2; exit 1; }
command -v rsync >/dev/null || { echo "rsync is required" >&2; exit 1; }

HOST="${TARGET%%:*}"
RPATH="${TARGET#*:}"
SSH_CMD="ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -p ${OFFSITE_SSH_PORT:-22}"
[ -n "${OFFSITE_SSH_KEY:-}" ] && SSH_CMD="$SSH_CMD -i ${OFFSITE_SSH_KEY}"

DELETE=()
[ "${OFFSITE_DELETE:-0}" = "1" ] && DELETE=(--delete)

echo "[$(date '+%F %T')] Copying $BACKUP_DIR -> $TARGET"
rsync -a --chmod=F600,D700 "${DELETE[@]}" \
  --include='daily/' --include='weekly/' \
  --include='*.sql.gz' --include='*.sql.gz.sha256' --exclude='*' \
  -e "$SSH_CMD" "$BACKUP_DIR/" "$TARGET/"

echo "[$(date '+%F %T')] Verifying checksums on the remote side"
$SSH_CMD "$HOST" "cd '$RPATH' && for d in daily weekly; do [ -d \$d ] && (cd \$d && ls *.sha256 >/dev/null 2>&1 && sha256sum -c --quiet *.sha256); done; true" \
  || { echo "Remote checksum verification FAILED" >&2; exit 1; }

echo "[$(date '+%F %T')] Offsite copy verified."
