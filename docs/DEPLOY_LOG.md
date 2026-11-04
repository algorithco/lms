# Deploy log

Each entry: what changed, which commit/tag is live, backups, checks, open items.
Merging to `main` auto-deploys (CI → Build → Deploy, `deploy/remote-deploy.sh`); that pipeline takes **no** database backup, so a manual `pg_dump` must be taken before merging anything that migrates.

## 2026-11-04 — PR #118 result review, dashboard, mobile exam, question issues (`2eae701`, release `9b9f174` v1.79.0)

**Live tag:** `sha-2eae701` (web, bot, celery-worker, celery-beat). Previous tag / rollback point: `sha-b532bb0` (#117). Rollback = `Deploy` workflow `workflow_dispatch` with `tag=sha-b532bb0`; the three migrations only add columns, so the old image runs on the new schema.

**Backup (taken right before merge):** `~/backups/lms_predeploy_pr118_20261104_032728.sql.gz` — 166 136 bytes, `gzip -t` OK, 117 tables (lms database only; an earlier one at 03:04 is superseded).

**Migrations applied:** `tests.0019_question_evidence_explanation_status`, `tests.0020_question_needs_review`, `notifications.0014_userfeedback_question_userfeedback_reason_and_more` (AddField ×5 + a choices-only change on `category`, no SQL). Table sizes before: `tests_question` 158 rows / 280 kB, `notifications_userfeedback` 1 row / 112 kB.

**Verified on production (read only):**
- CI, Security, CodeQL, Build, Release, Deploy all `success`; web/bot/celery-worker/celery-beat on `sha-2eae701`, all `healthy`; nginx/db/redis unchanged.
- Bestway / education containers: same names and images before and after (uptime unchanged).
- 0 tracebacks in web/bot/worker/beat since the deploy; `https://grandec.uz/healthz/` → 200.
- `showmigrations`: the three migrations are `[X]`.
- `draft_explanations --test-id 14 --dry-run` (Record Mock, published): 14 drafts, 67 left without explanation, **nothing written**. Not run for real yet (waiting for the owner's review).

**Not yet verified (needs a test FREE account from the owner):** explain-mistake / result endpoint return no key during an exam or for another user's attempt; #116 checks (receipt upload stays pending, group join grants nothing).

## 2026-11-03 — PR #116 free→PRO leak hotfix (`a39529a`, release `ec34526` v1.77.0)

**Live tag:** `sha-a39529a` (web, bot, celery-worker, celery-beat). Previous tag / rollback point: `sha-73e2a1f` (#115). Rollback = `Deploy` workflow `workflow_dispatch` with `tag=sha-73e2a1f`; the two migrations are schema-neutral / data-only, so an image rollback is safe.

**Backup (taken before merge):** `~/backups/lms_predeploy_20261103_120236.sql.gz` — 161 658 bytes, `gzip -t` OK, 117 tables.

**Migrations applied:** `payments.0016_drop_pdf_certificate_claim` (data: clears `pdf_certificate`, rewrites the PREMIUM description only if unchanged), `payments.0017_audit_expire_cancel_actions` (choices only, no SQL). `tests.0017/0018` came with #115.

**Verified on production (read only):**
- Deploy workflow `success` 12:11 UTC; web/bot/celery-worker/celery-beat on `sha-a39529a`, all `healthy`; nginx/db/redis unchanged.
- Bestway containers untouched (uptime unchanged: 33 h – 2 days).
- 0 error/traceback lines in web/bot/worker/beat logs (15 min after deploy); `https://grandec.uz/healthz/` → 200.
- Migrations 0015–0018 (`payments`, `tests`) show `[X]`.
- Plan rows: `pdf_certificate=False` everywhere; PREMIUM description no longer mentions PDF.
- Subscriptions before the deploy: 1 active paid-plan subscription, **0 backed by a payment**: user id 2, PRO, `receipt_trial` (the removed 24 h trial), created 11-03 05:48 UTC, expires 11-04 05:48 UTC, 1 test / 0 essays / 0 speaking. 0 admin grants, 0 teacher sponsorships. It was **not** revoked; it expires on its own.

**PRO limit decision:** production PRO row is `test_limit=100` per 7 days (not 30 as in the local DB). Approved before deploy; 0 real payers were affected.

**Not yet verified (needs a test FREE account provided by the owner):**
- uploading a receipt image leaves the account FREE and the receipt `pending` in the admin queue;
- joining a teacher group does not grant PRO;
- `/my-subscription` and `/profile` show the same limits;
- admin account login after deploy.

**Found afterwards:** `audit_unpaid_subscriptions` crashed on production (`EssaySubmission` has `submitted_at`, not `created_at`). Read-only command, no data impact. Fixed with a regression test in `feat/ui-qa-real-exams`.
