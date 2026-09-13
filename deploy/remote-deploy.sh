#!/usr/bin/env bash
# ============================================================================
# LMS Platform — remote deploy procedure. Runs ON THE VPS.
# Executed as: ssh deploy@VPS 'bash -s' < deploy/remote-deploy.sh
# (see .github/workflows/deploy.yml — native OpenSSH, no third-party action).
# Secrets arrive via /tmp/lms_deploy.env (scp'd 600, sourced, shredded).
# ============================================================================
set -euo pipefail
set +x # never echo secrets, even on error traces
cd /opt/lms

IMS_IMAGE_TAG="${IMS_IMAGE_TAG:-latest}"
REGISTRY="${REGISTRY:-ghcr.io}"
IMAGE_NAME="${IMAGE_NAME:-algorithco/lms}"

# --- Install synced versioned config (shipped to /tmp/lms_deploy.d by CI).
# VPS-only files (.env.prod, deploy/secrets/*, logs, volumes) are untouched.
if [ -d /tmp/lms_deploy.d ]; then
  install -m 755 /tmp/lms_deploy.d/preflight.sh deploy/preflight.sh
  install -m 644 /tmp/lms_deploy.d/nginx-main.conf deploy/nginx/nginx-main.conf
  install -m 644 /tmp/lms_deploy.d/nginx-http.conf deploy/nginx/nginx-http.conf
  install -m 644 /tmp/lms_deploy.d/nginx-ssl.conf deploy/nginx/nginx-ssl.conf
  rm -rf /tmp/lms_deploy.d
fi

# --- Secrets: source once, shred immediately after login ---
if [ -f /tmp/lms_deploy.env ]; then
  set -a
  # shellcheck disable=SC1091
  . /tmp/lms_deploy.env
  set +a
fi
rm -f /tmp/lms_deploy.env

# --- GHCR login: temp DOCKER_CONFIG only (nothing on disk) ---
export DOCKER_CONFIG="$(mktemp -d)"
cleanup() { docker logout "$REGISTRY" >/dev/null 2>&1 || true; rm -rf "$DOCKER_CONFIG"; }
trap cleanup EXIT
echo "$GHCR_READ_TOKEN" | docker login "$REGISTRY" -u "$GHCR_USER" --password-stdin

# --- Config sync: deploy ships versioned config (compose + preflight + nginx
# templates) via scp before ssh; VPS never drifts. Secrets (.env.prod,
# deploy/secrets/*) are NEVER synced — they live on the VPS only. ---
# --- Regenerate the live nginx.conf from template (same substitution as
# init-letsencrypt.sh) so template fixes actually reach the running nginx. ---
sed -e "s/__DOMAIN__/grandec.uz/g" deploy/nginx/nginx-ssl.conf > deploy/nginx/nginx.conf

./deploy/preflight.sh
docker compose --env-file .env.prod -f docker-compose.prod.yml pull web celery-worker celery-beat bot
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d

# --- Reload nginx AFTER up: picks up regenerated conf + fresh upstream IPs.
# (up -d never recreates nginx for bind-mounted content changes, and plain
# proxy_pass would pin the old web IP forever.) Zero-downtime by design. ---
docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T nginx nginx -s reload

echo "$IMS_IMAGE_TAG" > .last_good_tag.tmp && mv .last_good_tag.tmp .last_good_tag

for i in $(seq 1 30); do
  if docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T web curl -fsS http://127.0.0.1:8000/healthz/ >/dev/null 2>&1; then break; fi
  sleep 4
  if [ "$i" = "30" ]; then docker compose --env-file .env.prod -f docker-compose.prod.yml logs --tail=100 web; exit 1; fi
done
docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T web python manage.py migrate --check
docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T web python manage.py check --deploy
docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T web python manage.py ai_smoke_test --validate-models || true
# Public health: main host must return 200; admin host sits behind
# Basic Auth by design, so 401 means nginx + auth gate are up
# (the app itself was already proven healthy via 127.0.0.1 above).
curl -fsS https://grandec.uz/healthz/; echo
admin_code=$(curl -sS -o /dev/null -w "%{http_code}" https://admin.grandec.uz/healthz/); echo "admin /healthz -> $admin_code"
case "$admin_code" in 200|401) ;; *) echo "ERROR: admin host unexpected status $admin_code"; exit 1 ;; esac
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
# NOTE: rollback = workflow_dispatch with tag=<previous sha from .last_good_tag>
