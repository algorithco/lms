#!/usr/bin/env bash
# ============================================================================
# LMS Platform — cert renew + nginx reload (RETIRED for grandec.uz)
# Cloudflare Origin certificates (15y) do not renew — this cron is NOT
# needed. Kept only for Let's Encrypt domains (compose profile legacy-le).
#
# Host crontab (LE domains only):
#   0 3,15 * * * cd /opt/lms && ./deploy/renew-reload.sh >>/var/log/lms-renew.log 2>&1
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE="docker compose --env-file .env.prod -f docker-compose.prod.yml"
$COMPOSE run --rm --entrypoint certbot certbot renew --webroot -w /var/www/certbot --quiet
$COMPOSE exec -T nginx nginx -s reload
echo "renew-reload OK: $(date -u +%FT%TZ)"
$COMPOSE exec -T nginx ls -l /etc/letsencrypt/live/ || true
