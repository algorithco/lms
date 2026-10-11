# Hardening Pass — 2026-10-06

Branch: `feat/react-spa-handoff` (no commit/push/deploy per task rules).

## 1. Current architecture (code truth)

- Django 5.2 + DRF + SimpleJWT (`config/settings/base.py`, `config/urls.py`).
- 15 canonical apps under `apps/`: accounts, courses, tests, results,
  certificates, essays, arena, games, notifications, telegram_app, payments,
  panel, web, webapi, core. `apps.web` serves the React SPA shell
  (`apps/core/spa.py`), not server-rendered pages.
- React 19 + TS + Vite SPA (`frontend/src`, `App.tsx`); built `frontend/dist`
  is NOT tracked (nginx serves `/app/spa`). `templates/` keeps email only.
- Postgres prod / SQLite dev; Redis broker/cache/channel; Celery + Beat;
  Daphne ASGI; nginx TLS + rate-limit + CSP.
- Detached roots `quiz/`, `project/`, root `essays/` are NOT in
  `INSTALLED_APPS`, `config/urls.py`, `config/asgi.py`, frontend, or Docker —
  only self-referenced + `test_quiz_ws.py`/`test_grading.py`/`INTEGRATION_GUIDE.md`
  (archived). No production repair performed on them.

## 2. Active websocket protocol/path

- Canonical: `/ws/arena/` → `apps/arena/routing.py` → `apps/arena/consumers.py`
  via `config/asgi.py` (`AllowedHostsOriginValidator(AuthMiddlewareStack(...))`).
- SPA: `arenaSocketUrl()` (`frontend/src/lib/api.ts`) + `Arena.tsx` queue socket
  (`join_queue` → `queue_update|match_found|error`) + `DuelRoom.tsx` duel
  (`join_room|submit_answer|leave_room` → `connected|room_joined|match_found|
  send_question|answer_result|live_score_update|game_over|error`). Session must
  exist before WS (JWT cannot auth WS); server timer authoritative; correct
  answer never sent in `send_question`.
- Legacy `ws/quiz/arena/` (`quiz/consumers.py`) is detached — SPA never uses it.

## 3. Authentication / RBAC overview

- Custom `accounts.User` (email login, roles student/teacher/admin/parent).
- JWT (60m/7d rotate+blacklist) + Session (`REST_FRAMEWORK` defaults).
  Default permission `IsAuthenticated`.
- Google OAuth (`google_auth.py`), Telegram login (bot deep-link + TMA HMAC).
- `is_platform_admin` (`apps/accounts/access.py`) gates panel/billing;
  `IsTeacherOrAdmin`, `IsPanelAdmin`, essay `can_review_submission` (group
  isolation) for scoped areas. Parents view children via `ParentStudentLink`.
- CSRF: session POSTs require CSRF (Arena `csrf_exempt` removed). JWT-only
  clients (TMA `test_api.py` manual JWT) stay exempt by necessity with HMAC/JWT
  as the auth factor. Telegram webhook uses `X-Telegram-Bot-Api-Secret-Token`
  HMAC, not CSRF. TMA `tma_auth_view` uses signed `init_data`, exempt on first
  contact by necessity.

## 4. TMA API contract (current, not `/telegram/api/*`)

Base `/tma/api/` (`apps/telegram_app/urls.py`):
- `POST auth/` (`init_data` → JWT + session; AllowAny + HMAC).
- `GET profile|arena|tests|results|essays...` (JWT `IsAuthenticated`).
- `POST essays/{topic}/start|essays/{sub}/submit` (JWT; throttled).
- Tests: `POST tests/{id}/start|answer|submit`, `GET attempts/{id}/result`
  (`apps/telegram_app/test_api.py`, manual JWT, CSRF-exempt by necessity).
- Stale `/telegram/api/*` paths in old docs are wrong.

## 5. Certificates

- One canonical service: `apps/certificates/services/generation.py::generate_certificate`
  (called by `results` task, `notifications` task, `tests` sync fallback).
  Format `LMS-YYYY-NNNNNN` (sequence/counter), ReportLab PDF, QR encodes SPA URL
  `{SITE_URL}/certificates/verify/<number>/` (Router renders via JSON API
  `/api/certificates/verify/`). HMAC-SHA256 (`anti_fraud.py`) with
  `CERTIFICATE_SECRET_KEY` (prod fail-closed). Idempotent via `get_or_create`
  + GENERATED+file reuse. No revocation model — FAILED status only marks
  generation failure, not post-issue revocation.

## 6. Essay grading rubric/version

- 12 criteria, 24 pts → 75 scale (`ESSAY_TARGET_SCALE`), off-topic 35
  (`ESSAY_OFF_TOPIC_SCORE`). Cache key includes provider/model/mock/version/
  digest/lang; poison cache deleted. `EssayGradingCache` + `EssayCriterionScore`
  rows. No rubric version migration policy yet — cache invalidation is by key.

## 7. Confirmed gaps (next milestone, NOT implemented)

`Milliy Sertifikat Exam Engine`: GAP_FILL, MATCHING, WRITTEN, READING question
types; exam→essay bridge; section scoring; aggregate certification result.
Current `Question` is single/multiple/text + free `passage`; written modeled as
MCQ in `create_mock_test.py` is ungradable.
