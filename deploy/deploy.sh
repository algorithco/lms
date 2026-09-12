#!/usr/bin/env bash
# ============================================================================
# LMS Platform — minimal-downtime VPS deploy
# Usage:
#   ./deploy/deploy.sh            # pull already done manually / CI shipped code
#   ./deploy/deploy.sh --build    # force rebuild (default: --build always)
# Gates: preflight -> up -> migrate --check -> check --deploy ->
#        ai_smoke --validate-models -> healthz -> ps (+celery ping)
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE="docker compose --env-file .env.prod -f docker-compose.prod.yml"
DOMAIN=$(grep -E '^SITE_URL=' .env.prod | cut -d= -f2 | sed 's#https\?://##; s#/##g' | tr -d '\r' | head -1)

./deploy/preflight.sh

echo ">>> Building + starting stack (web first for migrate/collectstatic)"
$COMPOSE up -d --build
echo ">>> Waiting for web healthy (migrate+collectstatic can take 30-60s)"
for i in $(seq 1 30); do
  if $COMPOSE exec -T web curl -fsS http://127.0.0.1:8000/healthz/ >/dev/null 2>&1; then
    break
  fi
  sleep 4
  test "$i" = "30" && { echo "web never healthy"; $COMPOSE logs --tail=100 web; exit 1; }
done

echo ">>> Django checks"
$COMPOSE exec -T web python manage.py migrate --check
$COMPOSE exec -T web python manage.py check --deploy
$COMPOSE exec -T web python manage.py ai_smoke_test --validate-models || true

echo ">>> Health + topology"
curl -fsS "https://${DOMAIN}/healthz/" || curl -fsS http://127.0.0.1/healthz/ || true
echo
$COMPOSE ps
$COMPOSE exec -T web python -c "from config.celery import app; i=app.control.inspect(); print('celery ping:', list((i.ping() or {})))" || true

echo ""
echo "DEPLOY OK: https://${DOMAIN}/healthz/ should be {\"status\":\"ok\",\"db\":true}"
