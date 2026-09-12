# LMS Platform — Complete Project Audit

**Audit date:** 2026-09-12  
**Scope:** Entire repository at `lms_platform`, including 213 Python files, 72 templates, static JavaScript, Django/Channels/Celery configuration, models and migrations, deployment files, dependency manifests, tests, and detached/untracked modules.  
**Method:** Static review, route and feature-flow tracing, Django checks, migration checks, template compilation, rendered JavaScript syntax validation, lint/type analysis, dependency advisory scan, an isolated 240-test run, focused in-memory reproductions, and read-only SQLite integrity checks. No application source or database data was changed.

## Executive conclusion

The project is a substantial Django LMS for Uzbek language and literature. It covers courses, tests, essay grading through external LLM providers, Telegram authentication and bot workflows, certificates, payments, games, and real-time Arena duels. The core domain is recognizable and the codebase has meaningful tests, service layers, indexes, deployment assets, and production security settings.

It is **not production-ready**. Two identity/authorization chains can give an untrusted user teacher-level academic and payment powers or let a Telegram username be mapped to the wrong account. Several main flows are confirmed broken: the Telegram Mini App JavaScript does not parse and calls the wrong routes; its test API contains invalid imports and incorrect service calls; group editing and bulk test import crash; timed attempts are not safely finalized; certificate integrity is not activated; and the production dependency constraints select known-vulnerable releases. Concurrency behavior has not been validated on PostgreSQL/Redis and contains source-visible races.

The most useful positive signal is that **240 labeled tests pass** in isolation and all current Django migrations match the models. The main negative signal is that the tests do not cover the privilege boundaries, production settings, real routing, browser JavaScript, PostgreSQL locking, Redis/Celery timing, or the broken default test-discovery path.

## A. Project summary

### Architecture and request flow

The active application entry points are `manage.py`, `config/wsgi.py`, `config/asgi.py`, and `config/urls.py`. Django templates provide the primary web UI. Django REST Framework and SimpleJWT serve API clients; the Telegram Mini App uses JWTs. Channels drives Arena WebSockets. Celery handles essay grading, result notifications, certificate generation, and periodic cleanup. SQLite is configured for development and PostgreSQL plus Redis for production.

The main active packages are:

- `apps/accounts`: custom email user, roles, profiles, parent links, API registration/login, Google auth.
- `apps/courses`: courses, enrollment, groups, assignments.
- `apps/tests`: test/question/choice/attempt/answer models and attempt/grading services.
- `apps/results` and `apps/certificates`: results, PDFs, public verification, checksums.
- `apps/essays`: submissions, LLM grading, caching, teacher review and appeals.
- `apps/notifications`: Telegram bot, Telegram login, push/email, Celery tasks.
- `apps/telegram_app`: Telegram Mini App endpoints.
- `apps/games` and `apps/arena`: single-player games and real-time duels.
- `apps/payments`: plans, subscriptions, manual payment requests.
- `apps/web` and `apps/panel`: server-rendered user and administrator interfaces.

There are also detached root packages (`quiz/`, `essays/`, and `project/`) that are not integrated into the active `config` application. They overlap active functionality and already break default test discovery.

### Main end-to-end flows

1. A user registers or authenticates through the web/API, Google, Telegram bot, or Telegram Mini App.
2. Teachers create courses, tests, essay topics, groups, and assignments.
3. Students start attempts, save answers, submit, and receive a denormalized `Result`; background tasks generate certificates and notifications.
4. Essay submissions are queued for external AI grading, cached, persisted as criteria, and may be reviewed by a teacher.
5. Telegram provides a parallel UI and manual subscription approval workflow.
6. Arena uses authenticated WebSockets and shared database state for matchmaking, timers, scoring, and rewards.

## B. Overall assessment

| Area | Score | Assessment |
|---|---:|---|
| Architecture | 5/10 | Useful domain separation, but duplicate implementations and oversized modules create divergent behavior. |
| Code quality | 4/10 | Readable intent and documentation, but lint/type failures include real undefined names and bad imports. |
| Security | 3/10 | Production flags exist, but identity binding and authorization boundaries have critical defects. |
| Performance | 5/10 | Some indexes/select-related usage; grading, dashboards, matchmaking, and external tasks have scaling hazards. |
| Maintainability | 4/10 | Business rules are duplicated across web, bot, TMA, services, and templates. |
| Frontend quality | 4/10 | Broad responsive UI, but inline scripts are very large and the TMA cannot execute. |
| Backend quality | 4/10 | Service abstractions exist; several service contracts and routes do not match their callers. |
| Database design | 5/10 | Migrations and basic integrity are sound; important state constraints, history snapshots, and delete policies are absent. |
| Testing | 6/10 | 240 tests pass, including many core flows; major security, JS, production, and concurrency paths are missing. |
| Production readiness | 3/10 | Blocked by critical auth issues, broken TMA/operations, vulnerable dependency pins, and unverified production concurrency. |

**Overall: 4.3/10.** The system is a capable pre-production build, but it needs a security and correctness stabilization release before real users or payments are entrusted to it.

## C. Critical problems

### C1. Public users can self-assign the teacher role and reach global academic/payment actions

**Severity:** Critical  
**Status:** Confirmed source vulnerability; the registration policy and downstream permissions are explicit.  
**Locations:** `apps/accounts/serializers.py:96-113`; `apps/accounts/views.py` API registration; `apps/essays/views.py:608-620, 644-678`; `apps/notifications/bot/handlers.py:1555-1556`.

`RegisterSerializer.validate_role()` explicitly permits both `student` and `teacher`. The public API registration view is available without authentication. A teacher can access the global essay review queue and review arbitrary submissions; the Telegram payment handler also treats `ADMIN` **or `TEACHER` as a payment approver**. This creates a complete privilege-escalation chain from anonymous registration to academic score manipulation and subscription approval.

**Fix:** Public registration must always create a student. Remove `role` from writable public fields or force `User.Role.STUDENT` in `create()`. Provision teachers only through an administrator-controlled invitation with a single-use, expiring token. Separately enforce object-level ownership in essay review and restrict payment approval to a dedicated payment/admin permission. Add an integration test that posts `role=teacher` anonymously and proves the stored role remains student.

### C2. Telegram Mini App authentication trusts mutable usernames

**Severity:** Critical  
**Status:** Confirmed and reproduced with two Telegram IDs.  
**Location:** `apps/telegram_app/views.py:69-126`; duplicated lookup behavior in `apps/notifications/bot/handlers.py:52-82` and bot quiz helpers.

After validating Telegram init data, the code first searches by numeric `telegram_chat_id`, then falls back to an email derived from `username` (`tg_<username>@telegram.tma`). Telegram usernames can change and be reassigned. When the fallback finds an existing account whose stored Telegram ID belongs to another person, the code still issues JWT and session credentials for that account. The focused audit mapped incoming Telegram ID `3333` to an account stored with ID `2222` by reusing its username.

**Fix:** Treat the signed numeric Telegram user ID as the only identity key. Never locate or link an account by username. Put a unique database constraint on `telegram_chat_id`, reject any collision, and use an opaque local email identifier based on the numeric ID only when email is required. Existing web accounts should link through a short-lived challenge that is confirmed in both the authenticated web session and the Telegram chat. Reconcile existing duplicate/mismatched records before enabling the new rule.

### C3. Telegram webhook authentication is optional

**Severity:** Critical when a webhook deployment leaves the secret empty; High as a configuration defect.  
**Status:** Confirmed conditional vulnerability.  
**Location:** `apps/notifications/views.py:62-96`; `config/settings/base.py` webhook-secret default.

The webhook is CSRF-exempt. It validates `X-Telegram-Bot-Api-Secret-Token` only when `TELEGRAM_WEBHOOK_SECRET` is non-empty, so an empty production value makes arbitrary POST bodies trusted Telegram updates. The bot application is initialized before authentication. Forged updates can drive any handler that relies on Telegram sender identity, amplifying the teacher/payment and account-mapping defects.

**Fix:** Fail closed: refuse to start or return 503 when the secret is absent, compare with `secrets.compare_digest`, authenticate before initializing/parsing the bot update, cap the request body, and rate-limit by proxy-aware client IP. The webhook setup command must always register the same secret. Add a production system check that rejects an empty secret whenever webhook mode is enabled.

## D. High-priority problems

### D1. Parent and unknown roles fall through to administrator result access

**Severity:** High  
**Status:** Confirmed authorization flaw.  
**Locations:** `apps/results/views.py:43-56, 74-80`; `apps/web/views.py:929-945, 1018-1030`; `apps/certificates/views.py:90-105`.

The result list/detail API grants all records to every role other than student or teacher. That includes the defined parent role and any future role. Several web and certificate views use the same negative check. This is an IDOR/data-privacy problem.

**Fix:** Use explicit allow-lists. Admin branches must require `is_staff`, `is_superuser`, or an explicit permission. Parents must be limited through `ParentStudentLink`. Unknown roles must receive 403 or an empty queryset. Centralize the policy in queryset helpers/DRF object permissions and test every role against another student's result and certificate.

### D2. Telegram account linking accepts an unproven chat ID

**Severity:** High  
**Status:** Confirmed design vulnerability.  
**Location:** `apps/accounts/serializers.py:245-274`.

An authenticated user can submit any positive, currently unclaimed `chat_id`, and the serializer stores it without proof that the caller controls that Telegram account. This permits account-link hijacking and sends future notifications to the wrong person.

**Fix:** Replace raw ID assignment with a server-generated one-time challenge, confirmed by the target Telegram account through the bot. Make binding atomic and unique, expire the challenge, and notify both channels when an existing link changes.

### D3. Inactive users still receive custom JWT access

**Severity:** High  
**Status:** Confirmed source flaw.  
**Locations:** `apps/telegram_app/views.py:120-126`; `apps/telegram_app/test_api.py:26-38`; `apps/notifications/views.py:138-140`; related bot lookup helpers.

`RefreshToken.for_user()` does not itself enforce the project's active-user policy, and the custom `_jwt_auth` helpers retrieve users without checking `is_active`. A disabled account can continue through TMA and push/bot routes even if Django's normal authentication backend blocks it.

**Fix:** Refuse token issuance for inactive users, make every custom JWT adapter use one shared authentication class, and require `user.is_active`. Revoke outstanding refresh tokens when disabling a user (SimpleJWT blacklist or a token-version claim).

### D4. The Telegram Mini App is unusable

**Severity:** High  
**Status:** Confirmed by rendering the actual template and running Node syntax validation.  
**Locations:** `templates/tma/index.html:292, 238, 312, 325, 354, 387, 614, 693, 737, 826`; `config/urls.py`; `apps/telegram_app/urls.py`.

The string `confirm('Esse yozishni to'xtatmoqchimisiz?')` terminates early at `to'`, causing `SyntaxError: missing ) after argument list`; the containing script never runs. In addition, the frontend calls `/telegram/api/...`, while the active URL configuration mounts the Mini App under `/tma/`, so the API requests resolve to 404. The greeting expects `data.user.first_name`, while the backend returns a different profile shape.

**Fix:** Move JavaScript to a static module, pass URLs through Django's `{% url %}` or a JSON configuration object, use a double-quoted/JSON-encoded translated string, and define a versioned response schema. Add a browser smoke test that authenticates, lists tests, starts one, saves an answer, submits, and loads a result.

### D5. Mini App test submission cannot complete and bypasses shared validation

**Severity:** High  
**Status:** Confirmed source/runtime defects.  
**Location:** `apps/telegram_app/test_api.py:180-192, 203-265, 285`.

The endpoint imports `Result` from `apps.tests.models`, where it does not exist. It calls `SubmitAttemptService.execute(attempt_id=...)` without the required student argument, then treats the service's `AttemptResult` data object as an ORM `Result` (`result.id`, `result.is_passed`, etc.). Choice IDs are not scoped to the question. The endpoint writes submitted answers before checking attempt status or deadline and duplicates the main save service.

**Fix:** Delete the duplicated grading path. Authenticate with the standard DRF class, call `SaveAnswerService` for each answer, call the canonical submit service with its exact typed contract, and serialize the returned data class deliberately. Scope choices to `question.choices`, use one transaction, validate status/deadline before writes, and add API contract tests.

### D6. Timed attempt auto-submission rolls back

**Severity:** High  
**Status:** Confirmed in an in-memory reproduction.  
**Location:** `apps/tests/services.py:185-219`.

`SaveAnswerService` runs atomically, calls `_timeout_attempt()`, and then raises `ValueError`. The exception causes the timeout state and generated result to roll back. The caller sees “automatically completed,” but the attempt remains `IN_PROGRESS` and no result exists.

**Fix:** Do not raise from inside the transaction after committing the state transition. Return a typed timeout result, or perform the finalization in a separate atomic boundary and raise only after it commits. Lock the attempt row and make completion idempotent.

### D7. Celery dispatch occurs before the grading transaction commits

**Severity:** High  
**Status:** Confirmed race from transaction structure.  
**Location:** `apps/tests/services.py:552-587`.

The result task is queued immediately after `Result.objects.create()` while the surrounding transaction is still open. A fast worker can query before commit, fail to find the result, and return without retry. Eager development tests mask the race.

**Fix:** Dispatch with `transaction.on_commit(lambda: process_test_result_task.delay(result.id))`. Make the task retry a temporarily missing record and make certificate/notification work idempotent.

### D8. Celery Beat contains a missing task and an invalid schedule object

**Severity:** High  
**Status:** Confirmed configuration/runtime defect.  
**Location:** `config/settings/base.py:330-357`.

`notifications.check_timeout_attempts` is scheduled but no registered task exists. `daily-maintenance` uses a plain dictionary as its schedule; Celery expects a numeric interval or schedule object such as `crontab`. Instantiating the schedule produced `AttributeError: 'dict' object has no attribute 'app'`. Timed test completion therefore has no reliable periodic safety net.

**Fix:** Point to a real registered task, use `crontab(hour=3, minute=0)`, and add a startup test that loads every Beat entry and resolves every task name.

### D9. Certificate numbering can fail on first PostgreSQL use and collide on SQLite

**Severity:** High  
**Status:** PostgreSQL path is source-confirmed and needs integration verification; SQLite collision mechanism is confirmed by algorithm.  
**Location:** `apps/results/models.py:205-234`.

The PostgreSQL code catches a failed `nextval()` and then tries to create the sequence in the same transaction. PostgreSQL marks that transaction aborted, so the fallback DDL cannot recover. No migration creates `cert_number_seq`. The SQLite fallback uses `COUNT(*) + 1`, which reuses numbers after deletion and races under concurrency.

**Fix:** Create the sequence in a migration and use it directly, or use a dedicated counter row locked with `select_for_update`. Keep the unique constraint and retry collisions. Never create schema lazily from model code.

### D10. Certificate anti-fraud metadata is never generated and verification says valid anyway

**Severity:** High  
**Status:** Confirmed by call-site search.  
**Locations:** `apps/certificates/services/anti_fraud.py:114-141`; `apps/certificates/views.py:170-195, 239-272`; PDF generation services.

`generate_and_store_checksum()` has no production call site. The API computes `fraud_check` but returns `valid: True` for any existing certificate, including one with no checksum or a failed checksum. The HTML verification path does not perform the anti-fraud check. PDF/media access is public, so the checksum cannot be treated as an access control.

**Fix:** Generate and persist the checksum atomically when issuing a certificate, embed a verification URL containing a signed value or opaque public token, and return validity from the actual verification result. Define whether certificates are public documents; if not, serve them through an authorized view rather than public media.

### D11. Essay appeal/review state machine rejects the state produced by the UI flow

**Severity:** High  
**Status:** Confirmed and reproduced.  
**Locations:** `apps/essays/services.py:598-672`; `apps/essays/views.py:692-708`; `templates/essays/result.html`.

The review/appeal service accepts only `AI_EVALUATED`, while the current grading path produces `GRADED`; a request for teacher review therefore raises `ValueError`. The view then saves `final_score` outside the service transaction. Dashboards and leaderboards inconsistently include `TEACHER_REVIEWED` versus `GRADED`, so a reviewed result may disappear or show an outdated score.

**Fix:** Define one explicit state-transition table, enforce it in a domain service, and update the review record, final score, status, audit actor, and timestamp in one transaction. Use one `effective_score` property/query expression everywhere.

### D12. AI result validation accepts structurally corrupt scoring

**Severity:** High  
**Status:** Confirmed and reproduced.  
**Location:** `apps/essays/services.py:706-751, 1240-1310`.

Validation checks only that `criteria` is a list of length 12 plus limited field types. It does not require the canonical 12 unique IDs, maximum score bounds, a fixed total of 24, finite numbers, or consistency between totals and criteria. A payload containing twelve duplicate ID `1` entries, total `999`, and max `0` passed validation.

**Fix:** Validate against a strict schema: exact ID set, uniqueness, per-criterion bounds, finite numeric values, string length limits, and no unknown keys. Recalculate all totals server-side from canonical criteria; never accept model-supplied totals as authoritative. Validate before caching and persist all criteria atomically.

### D13. Essay grading cache mixes models, prompts, modes, and rubrics

**Severity:** High  
**Status:** Confirmed design bug.  
**Location:** `apps/essays/services.py:881-989`.

The cache key hashes only essay text and topic title. It omits provider, model, grading prompt/version, rubric settings, language, and mock mode. A mock response can be reused after real credentials are enabled; changed rubrics can return stale scores.

**Fix:** Version the cache key with a canonical hash of provider, model, prompt template, rubric configuration, language, and mock/real mode. Never persist mock outputs into the production cache namespace. Add an expiry and a migration/invalidation strategy when grading rules change.

### D14. Group editing and bulk test import crash

**Severity:** High  
**Status:** Confirmed by focused execution.  
**Locations:** `apps/web/views.py:1278-1313, 1605`; `apps/tests/services.py`; `apps/tests/services/bulk_import.py`.

Valid group-edit POST reaches a local `User` reference before the function's later import, producing `UnboundLocalError`. Bulk import imports `apps.tests.services.bulk_import`, but `services` is a module file as well as a directory without package initialization, producing `ModuleNotFoundError`.

**Fix:** Keep the user model import at module scope or call `get_user_model()` once. Resolve the module/package collision by moving the existing service module into a real `services/` package with `__init__.py` re-exports, or move the importer to a uniquely named module and update callers.

### D15. Arena custom-room locking is invalid and reconnects reset the question clock

**Severity:** High  
**Status:** Locking issue is source-confirmed for PostgreSQL; timer reset is confirmed by code path.  
**Locations:** `apps/arena/services.py:478-510, 574-615`; `apps/arena/consumers.py` join/reconnect flow.

`select_for_update()` is evaluated at line 492 before entering `transaction.atomic()` at line 503, which raises `TransactionManagementError` on PostgreSQL. The second locked fetch does not re-check that the room is still waiting, allowing concurrent joiners to overwrite `player2` or violate related state. `mark_question_sent()` resets `question_started_at` whenever a question is sent; reconnecting calls the send path again and extends the answer window.

**Fix:** Start the transaction before the first read, lock once, re-check status/player count under the lock, and enforce a database constraint for valid participants. Store an immutable per-question deadline and do not reset it on reconnect. A reconnect should receive the current deadline and remaining time from shared state.

### D16. Dependency constraints select vulnerable and unsupported versions

**Severity:** High  
**Status:** Confirmed by `pip-audit` against `requirements/production.txt` on 2026-09-12.  
**Locations:** `requirements/base.txt:6, 33, 40`; `requirements/production.txt:10`.

The audit selected Django 5.1.15, Pillow 10.4.0, and WeasyPrint 62.3 and reported 45 advisory records across those three packages (some records duplicate the same CVE through multiple advisory sources). The current upper bounds prevent selecting fixed releases: Django fixes require a supported 5.2 patch or 6.0 line, Pillow findings require 12.3.0, and important WeasyPrint URL-fetcher fixes require 68/70. The current local environment also runs Django 5.2.14 and OpenAI 2.34.0, which violate the declared `<5.2` and `<2.0` constraints, proving environment drift.

**Fix:** Choose a supported dependency baseline, test it, then update constraints deliberately. At minimum use a currently patched Django 5.2 LTS patch, Pillow >=12.3.0, and WeasyPrint >=70.0 after reviewing its changelog. Decide whether OpenAI 1.x or 2.x is supported and pin accordingly. Generate a hash-locked deployment file and run `pip-audit` in CI. Add missing direct dependencies actually imported by the project (`djangorestframework-simplejwt`, `qrcode`, and `pywebpush`) to the correct manifest.

## E. Medium and low-priority improvements

### Confirmed medium issues

1. **Games hub can fail for anonymous users:** decorator order at `apps/games/views.py:226-227` lets the conditional/ETag function query with `AnonymousUser` before `login_required`; reproduced as a `TypeError`. Put authentication outermost or make the ETag function anonymous-safe.
2. **Imlo endpoint uses a Flask-style API:** `request.POST.get("word_index", type=int)` at `apps/games/views.py:304` is invalid for Django `QueryDict`. Parse explicitly in a `try/except` and validate the range.
3. **Teacher analytics is not database-portable:** `apps/web/views.py:680` injects `EXTRACT(HOUR FROM completed_at)`, which produced an SQLite syntax error. Use Django's `ExtractHour` and test both configured databases.
4. **Expired essay autosave crashes:** `apps/essays/views.py:294-304` calls `messages` without importing it. It also reaches persistence before all expiry rules and lacks a firm text-size limit. Import correctly and centralize deadline/size checks in the service.
5. **Topic password becomes invalid after editing:** the model's prefix test does not recognize all encoded hash algorithms, so saving an already-hashed password can hash it again. This was reproduced: the password matched before `save()` and failed afterward. Use `identify_hasher()`/`is_password_usable()` or store access secrets through a dedicated setter; never infer hash state by a partial prefix list.
6. **Google identity linking is weaker than it should be:** `apps/accounts/google_auth.py:150-169` links existing users by email without requiring the provider's verified-email claim. Require verified email, issuer/audience/nonce checks, and an explicit logged-in linking flow for an existing local account.
7. **WebSocket origin validation is absent:** `config/asgi.py:25-28` wraps WebSockets in `AuthMiddlewareStack` directly. Use `AllowedHostsOriginValidator` or a strict origin validator around it and test allowed/denied origins.
8. **CSRF is disabled on session-capable JSON endpoints:** `apps/notifications/views.py:108,177` uses `csrf_exempt` while accepting browser credentials. Use DRF authentication/permissions consistently; exempt only endpoints authenticated by an independent signed secret.
9. **Telegram login tokens are reusable:** `apps/notifications/telegram_auth.py:191-221` logs in through GET and never consumes the long token; the status response at line 179 also emits an unmounted `/api/...` login URL. Make login POST-only, bind it to the initiating browser session, atomically mark the token used, and return a reversed route.
10. **Short login codes can collide/replay:** generation is not protected by a database uniqueness rule over active codes, consumption is not row-locked, and `apps/notifications/bot/handlers.py:375-376` logs the full six-digit code. Add a hashed challenge record, unique active constraint, atomic consumption, attempt limits, and redact logs.
11. **Development settings are dangerous when tunneled:** `config/settings/development.py` enables wildcard hosts/CORS, insecure cookies, MD5 password hashing, and no API throttles while documenting public ngrok/Cloudflare endpoints. Keep a separate test settings module for speed and require secure hashers/throttles for any externally reachable development server.
12. **Production static storage setting is obsolete:** `config/settings/base.py:149` uses `STATICFILES_STORAGE`, which the running Django 5.2 ignores in favor of `STORAGES`. The observed backend was plain `StaticFilesStorage`. Configure the `staticfiles` backend under `STORAGES` and make `collectstatic` a required deployment check.
13. **Subscription limits are display-only:** `max_tests_per_day` and `max_essays_per_week` appear in plan models/setup/UI but are not enforced at attempt/submission entry points. Add one quota service called by web, API, bot, and TMA paths.
14. **Cancellation contradicts its confirmation message:** `apps/payments/views.py:104-108` immediately marks the subscription `CANCELLED`; `UserSubscription.is_active` at `apps/payments/models.py:179-186` then returns false, although the UI promises access until expiry. Store `cancel_at_period_end` separately or define cancellation as active until `expires_at`.
15. **Expired subscription renewal can violate one-to-one uniqueness:** `apps/notifications/bot/handlers.py:1587-1605` creates a new subscription whenever the existing one is inactive, even though the relation is one-to-one. Update the existing row regardless of prior status.
16. **Course/test deletion can erase academic history:** teacher/course/test/question/result/certificate relations use `CASCADE`. Panel views permit editing/deleting live questions. Use `PROTECT` for historical ownership, archive domain objects, and snapshot question/choice/rubric text on an attempt/result.
17. **No database guarantee prevents concurrent active attempts:** the prior unique-together rule was removed and `StartAttemptService` does not lock an attempt/quota key. Add a conditional unique constraint for `IN_PROGRESS` per student/test and lock/retry around start.
18. **Essay grading holds database state across network work:** worker code can keep a submission lock while LLM calls and fallback retries run. Claim work in a short transaction, release the lock, call the provider, then conditionally finalize with a job/version token.
19. **AI retry duration can exceed task limits:** nested SDK retries, provider fallbacks, and explicit delays can overrun Celery's hard time limit. Define an end-to-end deadline, pass bounded connect/read timeouts, disable layered retries, and record retryable versus permanent failures.
20. **Arena question sourcing uses a non-existent type:** `apps/arena/services.py:153` filters `question_type="multiple_choice"`, while the model choices are `single`, `multiple`, and `text`; it therefore falls back to a small built-in bank. Use the canonical enum and validate fallback facts.
21. **Arena state is process-fragile:** consumer-owned timers are canceled on disconnect and reconnect paths can create duplicate timers/broadcasts. Move authoritative deadlines/state transitions to the database plus scheduled tasks; consumers should render/broadcast current state.
22. **Matchmaking locks and scans the queue broadly:** `select_for_update()` over the ordered queue without `skip_locked` limits concurrency. Use a short transaction, indexed eligible filter, `skip_locked` on PostgreSQL, and a bounded cleanup policy.
23. **Result grading is query-heavy:** the loop fetches each answer and selected choices per question. Prefetch attempts, answers, and choices into maps before grading, then bulk-update answer correctness.
24. **Large server-rendered modules impede review:** `apps/notifications/bot/handlers.py` is about 76 KB, `apps/essays/services.py` 66 KB, `apps/web/views.py` 60 KB, and major templates carry tens of KB of inline behavior. Split by domain/flow while preserving one shared policy/service layer.

### Low-priority issues

- API error shapes and status codes vary between DRF, plain `JsonResponse`, bot messages, and HTMX partials. Define a small stable error schema.
- Multiple broad `except Exception` blocks convert programming defects into generic user messages or silent fallbacks. Catch expected exceptions and log unexpected failures with correlation IDs.
- The API schema generator cannot infer serializers for numerous APIViews and TMA endpoints. Add explicit serializers/schema annotations so generated OpenAPI is usable.
- Email normalization is inconsistent: web login lowercases input, while the serializer can create mixed-case addresses. Normalize centrally in the user manager and enforce case-insensitive uniqueness at the database level.
- Templates depend on CDN Tailwind/Alpine/Chart.js with no build-time lock or Subresource Integrity. Pin and self-host critical browser dependencies for predictable/offline deployment.
- Accessibility needs a manual pass: large custom interactive templates need verified focus management, keyboard operation, labels, live regions, contrast, and reduced-motion behavior.

## F. Dead, duplicate, and unnecessary code

### Confirmed duplicate/detached trees

- Root `quiz/` duplicates the active `apps/tests` and Arena/WebSocket domain. It imports undefined `asyncio`/`sync_to_async`, is not installed, and makes default test discovery fail through `test_quiz_ws.py`.
- Root `essays/` duplicates active AI clients/prompts/views under `apps/essays` and follows a different settings/URL contract.
- Root `project/` contains partial `settings_additions.py`, URLs, and an ASGI file, but the active project is `config`. The fragment references undefined `BASE_DIR` when used alone.
- `test_grading.py`, `test_quiz_ws.py`, and `create_mock_test.py` are root scripts rather than isolated tests/management commands. The first two depend on detached modules; the mock script performs database setup at import/run time.
- `INTEGRATION_GUIDE.md` describes integrating the detached implementation rather than documenting the active architecture.

Choose one implementation for each domain. If the root trees are prototypes, move them to a clearly excluded archival branch or delete them after preserving anything still needed. Move safe data seeding into idempotent management commands or fixtures. Do not let prototype modules participate in test discovery or Docker build contexts.

### Generated/local artifacts

The workspace contains 911 files under `media/`, 166 under `staticfiles/`, a local `db.sqlite3`, and `.aider.input.history`. They are untracked/ignored, but `.dockerignore` does not exclude `.aider*`; local histories can enter Docker build contexts. Add `.aider*`, audit reports if desired, and other editor-agent histories to `.dockerignore`. Keep media/static/database data outside image builds and production source deployments.

No real secret was found in tracked files by the pattern/history scan. Only placeholder values were found in tracked example files. Local `.env` files were intentionally not printed or copied; their presence alone is expected and they are ignored.

## G. Security findings

The critical and high findings above are the security priority: public teacher escalation, Telegram username account takeover, optional webhook authentication, unproven chat linking, inactive-user JWT access, parent IDOR, token replay, WebSocket origin checks, and weak public-development settings.

Additional controls needed before launch:

- Apply rate limits to web login/register/password reset, Telegram challenges, webhook failures, upload endpoints, Arena room/queue creation, and expensive AI operations. Production DRF throttles do not cover ordinary Django views.
- Validate upload MIME by content, filename/extension, decompressed dimensions, row/field limits, and total processing time. Store uploads with generated names outside public execution paths.
- Ensure Nginx accepts `X-Forwarded-Proto` only from the trusted proxy path and strips spoofed forwarding headers.
- Redact Telegram codes, auth-token prefixes where unnecessary, email/phone data, provider responses, and essay text from production logs. Define retention and access policies.
- Rotate any real credentials that may ever have been entered into `.aider.input.history` or copied into prior untracked artifacts; the audit did not expose their contents.
- Run authorization as a matrix: anonymous/student/parent/teacher/admin/inactive against every list, detail, update, download, review, payment, and WebSocket action.

No SQL injection or shell-command injection was confirmed in the active request paths reviewed. The raw analytics SQL is static, so its problem is portability rather than injection. Template autoescaping protects most rendered user text, but any future `safe`, raw HTML, or LLM-generated markup must receive a dedicated XSS review.

## H. Performance findings

The important performance work is operational rather than micro-optimization:

1. Shorten transactions around external AI calls and Celery dispatch; long row locks will dominate latency under load.
2. Prefetch grading data and bulk-update answers. Measure query counts for 20-, 100-, and 500-question tests.
3. Paginate global results, essay queues, users, payments, and leaderboards consistently. Avoid rendering full datasets in templates/bot keyboards.
4. Make Arena timers/deadlines authoritative and shared through PostgreSQL/Redis rather than per-consumer tasks. Load-test reconnects and concurrent matchmaking.
5. Bound LLM input/output tokens, provider timeouts, retries, and simultaneous jobs. Cache only with a complete versioned key.
6. Move certificate generation and notifications reliably after commit and monitor queue latency/failures.
7. Split the 143 KB translations Python module and very large inline templates into cacheable static resources/modules; compile/minify CSS/JS instead of relying on runtime CDN tooling.

Caching permission-sensitive pages/results must include identity and role in the key or be avoided. The certificate public cache should include checksum/version state and be invalidated on revocation.

## I. Recommended refactoring

Refactor around domain services and explicit policies rather than around transport:

```text
apps/<domain>/
  models.py
  policies.py          # role and object authorization
  selectors.py         # optimized, authorized querysets
  services/            # transactional commands/state transitions
  api/{serializers,views,urls}.py
  web/{forms,views,urls}.py
  tasks.py              # idempotent async adapters
  tests/
frontend/
  tma/                  # bundled JS/CSS, typed API client
config/settings/{base,test,development,production}.py
```

The first targets should be authentication/linking, attempt lifecycle, essay lifecycle, and subscription/payment approval. Each needs one policy and one service used by web, DRF, bot, and TMA. Transport adapters should parse input and serialize output; they should not duplicate scoring or authorization.

Introduce explicit state-transition methods for attempts, essays, payments, subscriptions, certificates, and Arena rooms. Back them with database constraints and audit records. Replace negative role fall-through with named capabilities such as `can_review_submission(user, submission)` and `can_view_result(user, result)`.

## J. Missing features and edge cases

- Safe migration/reconciliation for Telegram identities already linked by username.
- Teacher invitation, suspension, revocation, and audit history.
- Parent authorization for exactly linked children, including certificate/download boundaries.
- Idempotency keys for submit, payment approval, certificate issue, and notification tasks.
- Recovery for workers dying after claiming an essay or before publishing a result.
- Attempt/question snapshots so historical results remain meaningful after edits.
- Concurrent start/submit/save tests and duplicate request handling.
- Subscription quota enforcement and timezone-safe daily/weekly resets.
- Certificate revocation and verification of signed values, not merely record existence.
- Text-question support and answer persistence in the Telegram Mini App.
- Offline/reconnect behavior for the Mini App and Arena, including expired tokens and changed deadlines.
- Stable API/OpenAPI contracts and backward-compatible versioning.
- Database backup/restore drill, media backup, retention/deletion policy, and disaster recovery targets.
- Production observability: health checks for DB/Redis/Celery/AI, structured logs, queue metrics, error reporting, and alerts.

## K. Step-by-step fix plan

### 1. Immediate containment (before any public deployment)

1. Force public registration to student; restrict payment approval to admins and essay review to assigned/own-course teachers.
2. Disable username-based Telegram identity lookup; require numeric-ID binding with a two-channel challenge.
3. Require a webhook secret and block inactive users in every token/custom-auth path.
4. Fix parent/unknown-role result and certificate querysets.
5. Rotate production secrets if any have been used in development histories; configure strict production environment checks.

### 2. Restore broken core flows

1. Fix and bundle TMA JavaScript; generate route URLs server-side and align response contracts.
2. Replace TMA's duplicated test submission with canonical services.
3. Repair group edit, bulk import, games decorator order, Imlo parsing, teacher analytics, essay autosave, and topic-password storage.
4. Correct essay review transitions and strict AI payload validation/cache versioning.
5. Fix timed-attempt commit behavior, `on_commit` task dispatch, Beat task names, and `crontab` schedule.
6. Add the certificate sequence migration and activate end-to-end checksum issue/verification.

### 3. Enforce data integrity and concurrency

1. Add conditional unique/state constraints for active attempts, Telegram IDs, active challenges, room participants, and idempotency records.
2. Replace destructive cascades on historical records with `PROTECT`/archival and add immutable snapshots.
3. Correct Arena transactions/deadlines and make timers recoverable across consumers/workers.
4. Run the full suite against PostgreSQL and Redis with concurrent workers; SQLite passing is insufficient for locking semantics.

### 4. Stabilize dependencies and delivery

1. Update the supported dependency baseline and add all direct imports to manifests.
2. Produce hash-locked development and production installs; make `pip-audit`, Ruff, tests, migration check, and collectstatic blocking CI steps.
3. Replace obsolete static settings and verify a production container from a clean checkout.
4. Remove/exclude detached root prototypes and local history/generated artifacts from tests and Docker contexts.

### 5. Add the tests that decide release readiness

Required gates:

- Full role/object authorization matrix, including inactive accounts.
- Telegram username reuse, conflicting numeric IDs, forged webhook, token replay, and link challenge tests.
- TMA browser flow and JavaScript build/syntax checks.
- Concurrent attempt start/save/timeout/submit and worker-before-commit tests.
- AI malformed/duplicate/NaN/over-limit payloads, cache separation, retry deadline, and worker-loss recovery.
- PostgreSQL certificate first-issue/concurrent-issue tests and checksum tamper/revocation tests.
- Arena simultaneous join, reconnect, deadline, duplicate answer, disconnect, and multi-worker tests.
- Subscription renewal/cancel/quota/payment authorization tests.

### 6. Production acceptance

Deploy only after a clean environment can install from the lock, pass all blocking checks, migrate a PostgreSQL copy, collect static assets, connect to Redis, run Celery/Beat, and complete the critical end-to-end flows. Perform backup/restore and rollback drills, load-test grading/Arena, review logs for personal data, and run a focused external penetration test on auth, authorization, Telegram, uploads, payments, and public certificates.

## Verification evidence and limits

### Checks completed

- `python -B manage.py check`: passed with no system-check issues.
- Python syntax: all 213 Python files parsed successfully.
- Template loading: all 72 templates compiled successfully.
- Migration drift: `manage.py makemigrations --check --dry-run` reported “No changes detected.”
- Isolated test run: 240 tests passed in 17.083 seconds with temporary media/static paths, in-memory broker/cache, locmem email, mock AI, and external socket connections blocked.
- Default discovery: built a 241-test suite containing `_FailedTest.test_quiz_ws`; therefore the repository-root test command is not clean.
- Rendered frontend syntax: Node 24 validated the rendered TMA scripts and confirmed the syntax error at template line 292.
- Ruff 0.16.7: 708 diagnostics. Many are formatting or Django class-attribute typing noise, but the set contains real undefined names/import defects (`messages`, `User`, `Avg`, `asyncio`, `sync_to_async`).
- Mypy 2.3.1: 141 errors across 14 files/177 checked modules. Django stubs/plugin are not configured, so the count is a baseline rather than 141 confirmed defects.
- Dependency audit: 45 advisory records across Django 5.1.15, Pillow 10.4.0, and WeasyPrint 62.3 selected from production requirements.
- Local SQLite: `PRAGMA integrity_check` returned `ok`; `foreign_key_check` returned zero violations across 57 tables.
- Secret review: tracked history/pattern scan found example placeholders only; `.env` values were not disclosed.

### What was not verified

No real Telegram, Google, SMTP, LLM, push, payment-provider, PostgreSQL, or Redis service was contacted. No browser/device accessibility or responsive visual test was run. Production images were not built or deployed. Advisory reachability varies by feature and input format, but vulnerable versions are still unacceptable as a production baseline. Concurrency conclusions marked as risks must be validated under PostgreSQL/Redis after the source defects are fixed.

The worktree was already modified and contained untracked prototype files before this audit. Those changes were preserved. This report is the only file added by the audit.
