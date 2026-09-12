#!/usr/bin/env bash
# ============================================================================
# LMS Platform — VPS pre-flight (run BEFORE first `up -d` and every deploy)
# Usage: ./deploy/preflight.sh
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

fail=0
say() { echo ">>> $*"; }
err() { echo "!!! $*" >&2; fail=1; }

say "1/6 .env.prod exists + perms"
test -f .env.prod || { err "missing .env.prod (cp .env.prod.example .env.prod)"; }
if test -f .env.prod; then
  ls -l .env.prod
  perms=$(stat -c %a .env.prod 2>/dev/null || stat -f %Lp .env.prod 2>/dev/null || echo "?")
  test "$perms" = "600" || err ".env.prod perms=$perms, want 600 (chmod 600 .env.prod)"
fi

say "2/6 no example.com placeholders left"
if grep -q "example.com\|change-me" .env.prod 2>/dev/null; then
  grep -n "example.com\|change-me" .env.prod || true
  err "replace all example.com/change-me placeholders in .env.prod"
fi

say "3/6 compose config validates (DB_PASSWORD interpolation, YAML)"
docker compose --env-file .env.prod -f docker-compose.prod.yml config >/dev/null \
  || err "docker compose config failed"

say "4/6 nginx templates present"
test -f deploy/nginx/nginx-http.conf || err "missing nginx-http.conf"
test -f deploy/nginx/nginx-ssl.conf || err "missing nginx-ssl.conf"
grep -q "__DOMAIN__" deploy/nginx/nginx-ssl.conf || err "nginx-ssl.conf missing __DOMAIN__ placeholder"

say "5/6 required CLIs"
command -v docker >/dev/null || err "docker not installed"

say "6/6 disk + ports"
df -h / | tail -1
(ss -tlnp 2>/dev/null | grep -E ':80|:443' || echo "(no 80/443 listener yet — ok pre-install)")

if test "$fail" -ne 0; then
  echo "PRE-FLIGHT FAILED" >&2
  exit 1
fi
echo "PRE-FLIGHT OK"
