# v0.48.0 — Deployment & Rollback Runbook

Release branch: `release/v0.48.0` (PR #58). Base: v0.47.0 (`62a0e27`).
Target: fix the 2026-09-16 AI-grading outage (`essay_grading` queue starvation) and harden permissions/metrics.

## Pre-flight (operator, on VPS)

1. **Backup PostgreSQL** and verify it:
   ```bash
   docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T db \
     pg_dump -U lms_user lms_platform | gzip > backup_$(date +%F_%H%M).sql.gz
   gzip -t backup_*.sql.gz && echo "backup OK"
   ```
2. **Pre-migration data check** for `accounts.0008_email_lower_unique` (fails fast if duplicate lowercase emails exist):
   ```sql
   SELECT lower(email), count(*) FROM accounts_user GROUP BY lower(email) HAVING count(*) > 1;
   ```
   If rows are returned: resolve duplicates (rename/deactivate) BEFORE deploying. The migration will refuse to apply otherwise (safe, additive-first ordering).
3. Note the currently deployed image tag (`IMS_IMAGE_TAG` / running image digest) — this is the rollback target.

## Deploy

```bash
git fetch origin && git checkout release/v0.48.0   # or the v0.48.0 tag after release
./deploy/preflight.sh                              # now also fails if worker lacks -Q essay_grading
./deploy/deploy.sh                                 # build → migrate → check --deploy → ai_smoke → healthz → active_queues
```

`deploy.sh` prints **Celery active queues** at the end. MUST contain `essay_grading`:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml \
  exec -T celery-worker celery -A config inspect active_queues
```

No downtime required; migrations `accounts.0008/0009` are online-safe (constraint + additive columns). Daphne keeps serving during worker restart.

## Post-deploy: recover stuck submissions (idempotent)

The 21+ submissions stuck in PENDING at outage time are recovered in one of two ways:

1. **Automatic (preferred):** the orphaned Celery tasks still sitting in the `essay_grading` Redis list execute exactly once once the fixed worker connects. The task re-checks status under row lock; `apply_ai_result`'s FSM guard drops duplicates.
2. **Operator sweep (if anything remains PENDING >10 min after deploy):**
   ```bash
   docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T web \
     python manage.py recover_stale_essays --dry-run     # review first
   docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T web \
     python manage.py recover_stale_essays               # requeue (atomic claim, no double grading)
   ```

Do **NOT** flush Redis: it would discard the queued grading tasks; the recovery sweep would then re-grade every stuck essay from scratch.

## Smoke tests

- Student submits an essay → status `pending` ("AI baholamoqda") → `graded` with 12 criteria + Uzbek summary within minutes (free-model dependent).
- Teacher queue (`/teacher/essays`) counts ONLY `pending_teacher` rows; admin panel shows `pending_ai` and `awaiting_review` separately.
- `docker compose ... logs celery-worker | grep -i "essay grading"` shows activity.

## Rollback

Trigger criteria: grading smoke fails after 30 min, error rate spikes, migration failure, or data-integrity alert.

```bash
# 1. Redeploy previous image (migrations 0008/0009 are additive and
#    forward-compatible with the old code; no downgrade needed):
IMS_IMAGE_TAG=<previous-digest> docker compose --env-file .env.prod \
  -f docker-compose.prod.yml up -d web celery-worker celery-beat bot nginx

# 2. If 0008 must be reversed (only if duplicate-email errors appear):
docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T web \
  python manage.py migrate accounts 0007
```

Rollback restores the OLD broken worker command — stuck PENDING essays will re-accumulate. Run the recovery sweep AFTER re-deploying the fixed version, not before.

## Known limitations

- Frontend main JS chunk >500 kB (code-splitting backlog; cosmetic).
- Recovery sweep is intentionally NOT run from CI/automation — operator-only.
