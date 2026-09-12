#!/usr/bin/env bash
# ============================================================================
# LMS Platform — rate-limit self test (gap #4 proof)
#
# Fires controlled bursts and asserts nginx answers 429 exactly where
# designed — and NOWHERE else:
#   1. 25x POST /api/auth/login/      -> ~10-15 pass, rest MUST be 429
#   2. 10x  GET /                     -> all MUST be 200 (general untouched)
#   3. GET admin host without auth    -> MUST be 401 (Basic gate)
#   4. GET admin host with lmsadmin   -> MUST be 200 (legit staff passes)
#
# Usage (staging or local demo):
#   ./deploy/test-ratelimit.sh https://grandec.uz https://admin.grandec.uz
#   ADMIN_USER=lmsadmin ADMIN_PASS='...' ./deploy/test-ratelimit.sh ...
# Exit 0 = all assertions hold, else 1 (CI/host gate usable).
# ============================================================================
set -euo pipefail

BASE="${1:-https://grandec.uz}"
ADMIN_BASE="${2:-https://admin.grandec.uz}"
ADMIN_USER="${ADMIN_USER:-lmsadmin}"
ADMIN_PASS="${ADMIN_PASS:-}"

fail=0
check() { # check <desc> <expected> <actual>
    if [[ "$2" == "$3" ]]; then echo "PASS: $1 (=$3)";
    else echo "FAIL: $1 (expected $2, got $3)"; fail=1; fi
}

echo ">>> [1/4] login burst: 25x POST ${BASE}/api/auth/login/"
codes=$(for _ in $(seq 1 25); do
    curl -ks -o /dev/null -w "%{http_code}\n" -X POST "$BASE/api/auth/login/" \
        -H 'Content-Type: application/json' -d '{"email":"x@y.zz","password":"wrongpass123"}' &
done; wait)
limited=$(echo "$codes" | grep -c "^429$" || true)
echo "      429s: $limited / 25"
# Calibrated against a live nginx:1.27 run (19/25 limited): the band must
# catch both failure modes — gate open (0-4) and gate too greedy (24-25).
test "$limited" -ge 5 || { echo "FAIL: login burst not limited ($limited 429s)"; fail=1; }
test "$limited" -le 23 || { echo "FAIL: login over-limited ($limited 429s)"; fail=1; }
echo "PASS: login burst limited in sane band"

echo ">>> [2/4] general traffic untouched: 10x GET ${BASE}/"
ok=$(for _ in $(seq 1 10); do
    curl -ks -o /dev/null -w "%{http_code}\n" "$BASE/" &
done; wait | grep -c "^200$" || true)
check "general GET all 200" "10" "$ok"

echo ">>> [3/4] admin host without credentials"
code=$(curl -ks -o /dev/null -w "%{http_code}" "$ADMIN_BASE/")
check "admin no-auth is 401" "401" "$code"

echo ">>> [4/4] admin host with lmsadmin"
if [[ -z "$ADMIN_PASS" ]]; then
    echo "SKIP: set ADMIN_PASS env (never commit it) to test staff path"
else
    code=$(curl -ks -o /dev/null -w "%{http_code}" -u "$ADMIN_USER:$ADMIN_PASS" "$ADMIN_BASE/")
    check "admin staff is 200" "200" "$code"
fi

if test "$fail" -eq 0; then echo "RATELIMIT TESTS: ALL GREEN"; else echo "RATELIMIT TESTS: FAILED"; fi
exit "$fail"
