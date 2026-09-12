#!/usr/bin/env bash
# ============================================================================
# LMS Platform — cert renew + nginx reload (host cron)
# Why: the `certbot` container renews files every 12h but nginx only loads
# certs at startup/reload. Without this, renewed certs sit unused until the
# next reboot/redeploy (outage at ~90d).
#
# Host crontab (twice daily is the Let's Encrypt recommendation):
#   0 3,15 * * * cd /opt/lms && ./deploy/renew-reload.sh >>/var/log/lms-renew.log 2>&1
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE="docker compose --env-file .env.prod -f docker-compose.prod.yml"
$COMPOSE run --rm --entrypoint certbot certbot renew --webroot -w /var/www/certbot --quiet
$COMPOSE exec -T nginx nginx -s reload
echo "renew-reload OK: $(date -u +%FT%TZ)"
$COMPOSE exec -T nginx ls -l /etc/letsencrypt/live/ || true
