#!/usr/bin/env bash
# Delegate to deploy/scripts/backup.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/scripts/backup.sh" "$@"
