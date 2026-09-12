#!/usr/bin/env bash
# ============================================================================
# LMS Platform — Let's Encrypt bootstrap
#
# Usage:
#   ./deploy/init-letsencrypt.sh example.com admin@example.com [--staging]
#
# What it does:
#   1. Builds the images and starts nginx + web with the HTTP config
#      (ACME challenge is served from the certbot webroot volume).
#   2. Runs certbot certonly --webroot to issue certificates for the domain.
#   3. Swaps in the HTTPS nginx config (nginx-ssl.conf → nginx.conf).
#   4. Reloads nginx so HTTPS goes live immediately.
#
# Renewal afterwards is automatic: the certbot service in
# docker-compose.prod.yml re-runs `certbot renew` every 12 hours.
# ============================================================================
set -euo pipefail

DOMAIN="${1:-}"
EMAIL="${2:-}"
STAGING="${3:-}"

if [[ -z "${DOMAIN}" || -z "${EMAIL}" ]]; then
    echo "Usage: $0 <domain> <email> [--staging]" >&2
    exit 1
fi

# --env-file .env.prod so ${DB_NAME}, ${DB_PASSWORD} etc. interpolate for db/redis
COMPOSE="docker compose --env-file .env.prod -f docker-compose.prod.yml"
NGINX_CONF="deploy/nginx/nginx.conf"
HTTP_CONF="deploy/nginx/nginx-http.conf"
SSL_CONF="deploy/nginx/nginx-ssl.conf"

STAGING_ARGS=()
if [[ "${STAGING}" == "--staging" ]]; then
    echo ">>> STAGING mode — Let's Encrypt staging certs (not valid for browsers)"
    STAGING_ARGS=(--staging)
fi

# 1. Start with the HTTP (no-SSL) config so the ACME challenge is reachable
echo ">>> Installing HTTP nginx config (bootstrap)"
cp "${HTTP_CONF}" "${NGINX_CONF}"

echo ">>> Building images and starting stack"
${COMPOSE} up -d --build web nginx

# 2. Wait for nginx to accept connections (wget — alpine images ship wget, not curl)
echo ">>> Waiting for nginx..."
for i in $(seq 1 30); do
    if ${COMPOSE} exec -T nginx wget -q -O /dev/null http://localhost/ 2>/dev/null; then
        break
    fi
    sleep 2
done

# 3. Issue the certificate via the certbot image (webroot method)
echo ">>> Requesting Let's Encrypt certificate for ${DOMAIN}"
${COMPOSE} run --rm --entrypoint certbot certbot \
    certonly \
    --webroot -w /var/www/certbot \
    --email "${EMAIL}" \
    -d "${DOMAIN}" -d "www.${DOMAIN}" \
    --rsa-key-size 4096 \
    --agree-tos --no-eff-email \
    --keep-until-expiring \
    "${STAGING_ARGS[@]}"

# 4. Swap in the HTTPS config with the real domain substituted
echo ">>> Installing HTTPS nginx config for ${DOMAIN}"
sed -e "s/__DOMAIN__/${DOMAIN}/g" "${SSL_CONF}" > "${NGINX_CONF}"

echo ">>> Reloading nginx with HTTPS"
${COMPOSE} exec -T nginx nginx -s reload

# 5. Bring up the rest of the stack
echo ">>> Starting full production stack"
${COMPOSE} up -d

echo ""
echo "✅ HTTPS is live: https://${DOMAIN}"
echo "   (Certificates auto-renew via the certbot service every 12h.)"