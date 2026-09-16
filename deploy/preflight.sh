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

say "1/8 .env.prod exists + perms"
test -f .env.prod || { err "missing .env.prod (cp .env.prod.example .env.prod)"; }
if test -f .env.prod; then
  ls -l .env.prod
  perms=$(stat -c %a .env.prod 2>/dev/null || stat -f %Lp .env.prod 2>/dev/null || echo "?")
  test "$perms" = "600" || err ".env.prod perms=$perms, want 600 (chmod 600 .env.prod)"
fi

say "2/8 no placeholders left (including AI keys)"
if grep -qE "example\.com|change-me|changeme|your-super-secret|your-openrouter|placeholder" .env.prod 2>/dev/null; then
  grep -nE "example\.com|change-me|changeme|your-super-secret|your-openrouter|placeholder" .env.prod || true
  err "replace placeholder values in .env.prod (example.com/change-me/your-)"
fi
# GROQ placeholder is allowed when ESSAY_AI_PROVIDER!=groq (auto with openrouter key).
if grep -q "ESSAY_AI_PROVIDER=groq" .env.prod 2>/dev/null && grep -q "gsk_your" .env.prod 2>/dev/null; then
  grep -n "gsk_your" .env.prod || true
  err "replace GROQ placeholder when ESSAY_AI_PROVIDER=groq"
fi
if grep -q "ESSAY_AI_MOCK_MODE=True" .env.prod 2>/dev/null; then
  err ".env.prod must not have ESSAY_AI_MOCK_MODE=True in production"
fi
if grep -q "CELERY_TASK_ALWAYS_EAGER=True" .env.prod 2>/dev/null; then
  err ".env.prod must not have CELERY_TASK_ALWAYS_EAGER=True in production"
fi

say "3/8 compose config validates (DB_PASSWORD interpolation, YAML)"
docker compose --env-file .env.prod -f docker-compose.prod.yml config >/dev/null \
  || err "docker compose config failed"

say "4/8 nginx templates present"
test -f deploy/nginx/nginx-main.conf || err "missing nginx-main.conf (http-level zones)"
test -f deploy/nginx/nginx-http.conf || err "missing nginx-http.conf"
test -f deploy/nginx/nginx-ssl.conf || err "missing nginx-ssl.conf"
grep -q "grandec.uz" deploy/nginx/nginx-ssl.conf || err "nginx-ssl.conf missing grandec.uz server names"
grep -q "limit_req_zone" deploy/nginx/nginx-main.conf || err "nginx-main.conf missing limit_req zones"
grep -q "origin.pem" deploy/nginx/nginx-ssl.conf || err "nginx-ssl.conf not wired to Origin cert"

say "5/8 required CLIs"
command -v docker >/dev/null || err "docker not installed"

say "6/8 admin Basic Auth credential (fail-closed)"
if test -f deploy/secrets/htpasswd-admin; then
  aperms=$(stat -c %a deploy/secrets/htpasswd-admin 2>/dev/null || stat -f %Lp deploy/secrets/htpasswd-admin 2>/dev/null || echo "?")
  test "$aperms" = "600" || err "htpasswd-admin perms=$aperms, want 600"
  if cmp -s deploy/secrets/htpasswd-admin deploy/secrets/htpasswd-admin.example; then
    err "htpasswd-admin is still the DISABLED example — run ./deploy/setup-admin-auth.sh on the VPS"
  fi
else
  err "missing deploy/secrets/htpasswd-admin — run ./deploy/setup-admin-auth.sh on the VPS"
fi

say "7/8 Origin TLS files present + 600 (fail-closed)"
for f in deploy/secrets/origin.pem deploy/secrets/origin.key; do
  if test -f "$f"; then
    operms=$(stat -c %a "$f" 2>/dev/null || stat -f %Lp "$f" 2>/dev/null || echo "?")
    test "$operms" = "600" || err "$f perms=$operms, want 600"
  else
    err "missing $f — place Cloudflare Origin files on the VPS (chmod 600)"
  fi
done

say "8/8 disk + ports"
df -h / | tail -1
(ss -tlnp 2>/dev/null | grep -E ':80|:443' || echo "(no 80/443 listener yet — ok pre-install)")

if test "$fail" -ne 0; then
  echo "PRE-FLIGHT FAILED" >&2
  exit 1
fi
echo "PRE-FLIGHT OK"
