#!/usr/bin/env bash
# ============================================================================
# LMS Platform — provision admin Basic Auth (VPS ONLY, never committed)
#
# Creates deploy/secrets/htpasswd-admin with a single user `lmsadmin` and a
# strong random password. The password is printed ONCE to this terminal —
# save it in a password manager immediately. It is never written to the
# repo, logs, or CI output.
#
# Usage:
#   ./deploy/setup-admin-auth.sh            # create if missing (safe to re-run)
#   ./deploy/setup-admin-auth.sh --rotate   # force new password
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

AUTH_USER="lmsadmin"
SECRETS_DIR="deploy/secrets"
AUTH_FILE="${SECRETS_DIR}/htpasswd-admin"
ROTATE=0
if [[ "${1:-}" == "--rotate" ]]; then
    ROTATE=1
fi

mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"

if [[ -f "$AUTH_FILE" && "$ROTATE" -eq 0 ]]; then
    echo "exists: $AUTH_FILE (use --rotate to replace). Reloading nginx config check..."
else
    if ! command -v openssl >/dev/null; then
        echo "openssl topilmadi — Ubuntu'da: sudo apt install openssl" >&2
        exit 1
    fi
    PASSWORD="$(openssl rand -base64 24 | tr -d '\n')"
    # apr1 (Apache MD5) — nginx:alpine'ning openssl'i tushunadi, htpasswd shart emas
    HASH="$(openssl passwd -apr1 "$PASSWORD")"
    printf '%s:%s\n' "$AUTH_USER" "$HASH" > "$AUTH_FILE"
    chmod 600 "$AUTH_FILE"
    echo "created: $AUTH_FILE (600)"
    echo ""
    echo "================ ADMIN BASIC AUTH ================"
    echo "  host:     https://admin.grandec.uz"
    echo "  username: ${AUTH_USER}"
    echo "  password: ${PASSWORD}"
    echo "=================================================="
    echo "Parolni hozir saqlab oling — qayta ko'rsatib bo'lmaydi."
fi

if docker compose --env-file .env.prod -f docker-compose.prod.yml ps nginx >/dev/null 2>&1; then
    docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T nginx nginx -t
    docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T nginx nginx -s reload
    echo "nginx reloaded with admin gate."
else
    echo "(nginx ishlamayapti — keyingi 'up -d' da avtomatik ulanadi.)"
fi
