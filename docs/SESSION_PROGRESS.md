# Session progress — feat/results-dashboard-mobile

Branch: `feat/results-dashboard-mobile` (from `origin/main` @ `9f11a10`, v1.78.0). **Never merge it to `main` directly: a merge auto-deploys to production** (CI → Build → Deploy, no database backup in the pipeline). Finish with a PR and stop. The server is not touched in this session.

If this session is interrupted, continue from the first unchecked item below. Details of what was tested: `docs/QA_REPORT.md`; design inventory: `docs/DESIGN_AUDIT.md`.

## Decision taken with the owner
- Section 1 inventory found 21 files on dead Tailwind classes (> 15 → asked). Owner chose: migrate what users see; delete the unreachable legacy English exam screen; leave teacher pages (`TeacherFinanceDashboard`, `TeacherVocabGenerator`, `JoinGroup`, `ReferralRedirect`) listed as open.

## Checklist
- [x] 0. Branch from `origin/main`; docs read
- [x] 1. Unstyled components → tokens (`styles/ui.css`): toasts, referral, score card, landing feedback, code card, onboarding contrast, legacy English screen deleted
- [x] 2. Result page: per-question review (`QuestionReview`), hints, stored explanations + evidence (`Question.evidence`, `explanation_status`), `draft_explanations`, AI explain endpoint (paid, quota, daily cap, cache), key-leak closed in `explain-mistake`, estimate banner behind `SHOW_ESTIMATE_NOTICE`, BMB submit → `/results/<id>`
- [x] 3. Dashboard on `/api/v1/dashboard/` (real data, per subject), single plan source (`useTier`, `PlanBadge`), name helper, catalog without invented numbers, referral compact
- [x] 4. Exam on phones: CD screen rebuilt (header/timer, picker, text|questions, bottom bar, palette sheet, offline queue, leave guard, text size); BMB screen: leave/offline guard, readable timer
- [x] 6. Feedback: `question_issue` (one active report per user and question, flag at 3, one Telegram summary), admin grouping tab, phone filter sheet, bottom-sheet modals
- [x] 5. Checks: backend suite, `makemigrations --check`, ruff, tsc, build, oxlint — see QA report
- [x] Docs: QA report, design audit, this file
- [ ] PR opened by the session; **stop** (owner merges; take a `pg_dump` first, two migrations touch `tests_question` and `notifications_userfeedback`)

## After deploy (owner, not done here)
- `python manage.py draft_explanations --exam-type cefr_multilevel` (fills empty explanations with passage-based drafts, marked "AI-prepared"; safe to re-run, never overwrites staff text).
- Optional env: `SHOW_ESTIMATE_NOTICE=true` to bring the "estimate" banner back; `AI_EXPLAIN_DAILY_LIMIT` (default 20).
