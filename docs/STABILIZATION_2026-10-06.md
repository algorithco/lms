# Stabilization — 2026-10-06 (follow-up to hardening pass)

## What changed since `docs/HARDENING_2026-10-06.md`

1. Frontend build fixed: `Layout.tsx` drops unused `lang/setLang` (canonical
   `LanguageSwitcher` owns language state; EN/UZ/RU behavior unchanged);
   `tma/Essays.tsx StatusBadge` receives `t` via props instead of calling
   module-level `translate(key)` without `lang`. `tsc --noEmit`, `npm run lint`
   (warnings only, none in touched files), and `npm run build` pass.
2. Group-edit regression fixed without restoring deleted HTML: the retired
   `/groups/<pk>/edit/` HTML route now serves the SPA shell by design.
   Persistence is covered by the canonical school API —
   `PATCH /api/v1/school/groups/<id>/` + `POST .../members/` with
   `IsTeacherOrAdmin` ownership scope (`apps/webapi/views_school.py`).
   `tests/test_high_regressions.py` updated to that contract (+ outsider 404).
3. Legacy roots deleted (`git rm`, worktree only, no commit):
   `quiz/`, `project/`, root `essays/`, `test_quiz_ws.py`, `test_grading.py`,
   `create_mock_test.py`. Canonical `apps/essays`, `apps/arena`, `apps/tests`
   untouched. `ruff.toml` per-file ignores and `.dockerignore` prototype
   entries removed.

## Architecture truth (current)

- Active frontend: React 19 + TS + Vite SPA (`frontend/src`, `npm run build`;
  `frontend/dist` gitignored, baked to `/app/spa` in Docker).
- Canonical Arena WS: `/ws/arena/` → `apps/arena/consumers.py`.
- Canonical essay app: `apps/essays`; canonical tests app: `apps/tests`.
- TMA API base: `/tma/api/` (auth/profile/arena/tests/essays); stale
  `/telegram/api/*` paths are wrong.
- Group management: `/api/v1/school/groups/` (list/create/PATCH/delete/members).
- Deploy/build: `pip install -r requirements/development.txt`,
  `python manage.py migrate`, `npm run build` (frontend), Daphne + Celery
  (`-Q celery,essay_grading`) + Beat + nginx (see `DEPLOYMENT.md` for env).
