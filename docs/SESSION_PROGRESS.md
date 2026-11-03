# Session progress — feat/results-dashboard-mobile

Branch: `feat/results-dashboard-mobile` (from `origin/main` @ `9f11a10`, v1.78.0). **Never merge it to `main` directly: a merge auto-deploys to production** (CI → Build → Deploy, no database backup in the pipeline). Finish with a PR and stop. The server is not touched in this session.

Previous branch (`feat/ui-qa-real-exams`, merged as #117) is described in the git history; its open items are carried in `docs/QA_REPORT.md`.

## Decision taken with the owner
- Section 1 inventory found 21 files on dead Tailwind classes (> 15). Owner chose: migrate what users see; delete the unreachable legacy English exam screen; leave teacher pages (`TeacherFinanceDashboard`, `TeacherVocabGenerator`, `JoinGroup`, `ReferralRedirect`) listed as open in `DESIGN_AUDIT.md`.

## Section 1 — unstyled components: done (user-facing part)
`styles/ui.css` (tokens only) now styles: toasts (were rendered inline at the page bottom), referral card (full + compact), score-card modal, public feedback list/empty state, "join with code" card, bottom sheet, buttons/inputs. Onboarding modal had a hard-coded dark background with `var(--ink)` text (dark on dark in light mode) → tokens. `EnglishExamInterface.tsx` (1 800 lines, unreachable, with placeholder questions) → 80-line loader; `CefrExamComponents.tsx` deleted.

## Section 2 — result page: backend + UI done, browser check pending
- `Question.evidence`, `Question.explanation_status` (AddField, migration `tests.0019`); `question_review.py` (hints, source text, AI explain), `explanation_drafts.py` + `manage.py draft_explanations`.
- Result detail now returns per question: `status`, option letters, `hint`, `explanation`/`evidence`/`explanation_status`, part/group info, `can_ai_explain`; CD gap-fill keys come from `GapBlank`.
- `POST /api/tests/results/<id>/questions/<qid>/explain/` — paid tiers only, `ai_quota` + daily cap `AI_EXPLAIN_DAILY_LIMIT`, cached per question and answer.
- Legacy `explain-mistake` returned the key to any signed-in user → now needs a finished attempt of the caller.
- `SHOW_ESTIMATE_NOTICE` (default off) controls the old banner; the word "taxminiy" is gone from UI strings.
- `TestAddictiveResults` rewritten (i18n, no invented XP/topic analysis); BMB submit redirects to `/results/<id>`.

## Section 6 — feedback `question_issue`: backend + UI done
`UserFeedback.question/reason`, `Question.needs_review` (AddField, `notifications.0014`, `tests.0020`; the `category` choices change is a no-op in SQL). Endpoint `POST /api/v1/feedback/question-issue/`, grouping `GET /api/v1/panel/feedback/questions/`, Celery `notify_admin_question_needs_review` (one message at 3 active reports).

## Next
Section 3 (dashboard), Section 4 (mobile exam), admin inbox UI for grouped question issues, final checks, docs, PR.
