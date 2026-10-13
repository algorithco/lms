# Release v0.73.0 — Security Hardening, Channels JWT Auth & Production Stability

**Date:** 2026-10-13 · **Tag:** `v0.73.0` · **Base:** `v0.72.0`

## 🔐 Security & Authentication Hardening

- **Channels WebSocket JWT Authentication (`apps/arena/middleware.py`):**
  Added ASGI `JwtAuthMiddleware` supporting token extraction via query string (`?token=<jwt>`) and header (`Authorization: Bearer <jwt>`). WebSockets in Django Channels authenticate natively with SimpleJWT access tokens.
- **Frontend Password Cache & Session Purge:**
  Completely eliminated `cachedPassword` from memory and removed all `ensureSession` bridging across `AuthContext.tsx`, `Arena.tsx`, `DuelRoom.tsx`, `EssayResult.tsx`, `Login.tsx`, and `Register.tsx`.
- **DRF JWT API Migration for Essay Actions:**
  Added `@api_view(["POST"])` endpoints with SimpleJWT authentication:
  - `POST /api/v1/essays/<id>/improve/`
  - `POST /api/v1/essays/<id>/request-review/`
  Frontend now consumes these via standard JWT `api()`. Legacy views updated to safely return JSON without throwing `TemplateDoesNotExist`.
- **Nginx Admin Gate Hardening (`deploy/nginx/nginx-ssl.conf`):**
  On the main public domain `grandec.uz`, `/admin/` now returns HTTP 404. The Django Admin interface is exclusively accessible via `admin.grandec.uz`.
- **Multi-Tenant Course Boundary in Test Import:**
  Fixed course filtering in `apps/webapi/views_school.py:import_test_view` so non-admin teachers can only view and import tests into courses they own (`teacher=request.user`).

## 🛠️ Local Development & Bug Fixes

- **SPA Shell Redirect Loop Prevention (`apps/core/spa.py`):**
  Fixed infinite 302 redirect loops in `serve_spa_shell` when unbaked by checking `frontend/dist/index.html` fallback and returning an informative 200 dev page or 503 instead of self-redirecting.
- **TemplateDoesNotExist Elimination (`apps/web/views.py`, `apps/web/urls.py`):**
  Updated `RegisterView` and `SecurePasswordResetView` (along with `done`, `confirm`, and `complete` routes) to serve the SPA shell or JSON without referencing deleted legacy HTML templates.
- **Dependency & Config Modernization:**
  - Pinned Django requirement to `Django>=5.2,<5.3` in `requirements/base.txt`.
  - Removed unused `libpango*` system packages from `Dockerfile`.
  - Added `__test__ = False` on `Test` and `TestAttempt` models in `apps/tests/models.py` to eliminate all PytestCollectionWarnings.

## 🧪 Quality Assurance

| Check | Result |
|---|---|
| `pytest` | **1115 passed**, 2 skipped, 0 failed (100% pass) |
| `ruff check .` | **All checks passed** |
| `npm run build` | **Built cleanly in 1.85s** (`tsc -b && vite build`) |

---

# Release v1.2.0 — AI Improved Essay Generator & OpenRouter Resilience

**Date:** 2026-09-09 · **Tag:** `v1.2.0` · **Base:** `v1.1.1`

## ✨ New Feature: "Yaxshilangan versiya" (Improved Essay)

Students can now generate an AI-improved version of their graded essay directly
from the result page (`/essays/result/<id>/`):

- **Collapsible ✨ panel** below the 12-criteria evaluation — original vs
  improved essay **side-by-side** (stacked on mobile), with a copy-to-clipboard
  button ("Nusxalash") and a retry button on errors.
- **AJAX endpoint** `POST /essays/result/<id>/improve/` — owner-only,
  graded-only; clean JSON errors (400/404/502/503), never a raw 500.
- **Persisted result**: new `EssaySubmission.improved_content` / `improved_at`
  fields (migration `0011`, null-safe for existing rows) — generated essays are
  cached in the DB, so page reloads never re-generate or re-bill tokens.
- **Prompt engineering**: keeps the student's core ideas/arguments, upgrades
  vocabulary/cohesion/grammar to top rubric level (±20% length); output is
  wrapped in `<essay>…</essay>` and extracted, so reasoning-model
  chain-of-thought can never leak into student-visible text.

## 🔧 OpenRouter Resilience (from the same release cycle)

- `.env` generic aliases now map through: `AI_API_KEY` / `AI_BASE_URL` /
  `AI_MODEL` → OpenRouter settings (explicit `OPENROUTER_*` names still win).
- **Fallback-model chain**: `_chat_with_fallback()` retries transient failures
  (429 / 5xx / timeouts / 404 model-unavailable / empty replies) and fails over
  between models — primary `google/gemma-4-31b-it:free`, fallback
  `nvidia/nemotron-3-super-120b-a12b:free` (both verified live; the old
  `gemini-2.0-flash-exp:free` / `llama-3.3-70b-instruct:free` were retired by
  OpenRouter).
- **Bounded latency**: per-attempt HTTP timeout parameter; the improve endpoint
  uses 45 s and no pause-retries so a web worker is never pinned for minutes.
- Grading prompt hardened to pin exactly 12 criteria (id 1–12).

## 🧪 Quality Assurance

| Check | Result |
|---|---|
| `manage.py check` | 0 issues |
| `check --deploy` (production settings) | 0 errors (only intentional warnings) |
| Full test suite | 188 tests — all green after fixes |
| New endpoint tests | 9/9 (`ImprovedEssayEndpointTests`) |
| Live E2E via real OpenRouter | AJAX 200, clean text, persisted, cached |
| `collectstatic` | new `static/js/essay_result.js` collected (STATICFILES_DIRS added) |

## 🚀 Production Update (zero-downtime)

```bash
cd /opt/lms && git pull origin main
docker compose --env-file .env.prod -f docker-compose.prod.yml build
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
# entrypoint runs migrate + collectstatic on the web container
docker compose --env-file .env.prod -f docker-compose.prod.yml exec web python manage.py check
curl -s https://YOUR-DOMAIN/healthz/
```

Rollback: `git checkout v1.1.1 && docker compose ... up -d --build`
(the new DB columns are additive and harmless to older code).

---

# v1.3.0 — Barqarorlik (stability) relizi (2026-09-12)

## 🤖 OpenRouter model zanjiri (asosiy o'zgarish)

- **400 "is not a valid model ID" xatosi bartaraf etildi.** Retire bo'lgan
  ID'lar olib tashlandi; yangi zanjir (hammasi OpenRouter katalogida
  `--validate-models` bilan tekshirilgan):
  1. `nvidia/nemotron-3.5-lightning:free` (asosiy)
  2. `liquid/lfm-2.5-2.6b:free` (fallback 1)
  3. `nvidia/nemotron-3-super-120b-a12b:free` (fallback 2)
- `_chat_with_fallback()` endi **400 Invalid Model ID** xatosini ham
  ushlaydi (`_is_invalid_model_error`): task o'lmaydi, warning log yozib
  zanjirdagi keyingi modelga o'tadi.
- `parse_llm_json` mustahkam: reasoning/prose ("Here's a thinking process:"),
  markdown qobig'i, `\'` escape va kesilgan JSON — hammasi tuzatiladi.
- Grading prompt'lariga qat'iy "JSON only, no thinking" ko'rsatmasi qo'shildi.
- Yangi management command: `python manage.py ai_smoke_test`
  (`--validate-models`, `--live`) — deploy'dan keyin zanjirni bir buyruqda
  tekshirish.

## 🐛 Tuzatishlar

- `.env`dagi API kalit oxiridagi tab/probel endi `api_key.strip()` bilan
  xavfsizlanadi (httpx "Illegal header value" xatosining oldi olinadi).
- Legacy 30-ballik `AIGradingService` o'chirildi — faqat BMB 12-mezon
  (24.0 ball) tizimi qoldi; o'lik importlar tozalandi.
- `essay_has_grade_result()` va resubmit guard'lar edge-case testlar bilan
  mustahkamlandi.

## ⚡ Test suite tezligi

- Development sozlamalariga tezkor password hasher qo'shildi va DRF
  throttling testlar uchun lokal pinlandi — to'liq suite **10+ daqiqadan
  ~20 soniyaga** tushdi (production ta'sir qilmaydi).

## 🧪 Quality Assurance

| Check | Result |
|---|---|
| `manage.py check` | 0 issues |
| Full test suite | **308 tests — all green** |
| `ai_smoke_test --validate-models` | 3/3 model katalogda MAVJUD |
| Live OpenRouter smoke test | OK (~5s) |

## 🚀 Production Update

```bash
cd /opt/lms && git pull origin main
docker compose --env-file .env.prod -f docker-compose.prod.yml build
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
docker compose --env-file .env.prod -f docker-compose.prod.yml exec web \
  python manage.py ai_smoke_test --validate-models
curl -s https://YOUR-DOMAIN/healthz/
```
