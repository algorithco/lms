# QA report — branch `feat/ui-qa-real-exams`

Method: local database, 5 roles (guest, FREE student, paid student, teacher, admin; seeded by `seed_qa_accounts`), browser at 375 px and 1366 px, plus scripted sweeps. A row says **works** only if it was actually run. Things that could not be run are listed as **not tested** with the reason.

## Scripted sweeps
| Sweep | Result |
|---|---|
| Every no-argument GET route (189) × 5 roles | 0 server errors; no role reached another role's admin/teacher API. `/control-panel/*` returns only the SPA shell (HTML) to anyone. |
| Every frontend route (≈70) per role, desktop | No uncaught JS errors after the fixes below; role guards redirect correctly (guest → `/login`, student → `/dashboard`, admin `/dashboard` → `/panel`). |
| Answer-key leak scan on start / test detail / attempt detail for all 7 local tests | No `is_correct`, `correct_*`, `explanation` or gap answers in any response. Now a regression test (`test_exam_no_key_leak`). |

## Modules
| Module | Role | Status | Evidence |
|---|---|---|---|
| Landing | guest | fixed | 3 "Fikr bildirish" buttons → 1; "99.4% imtihon aniqligi", "Minglab …", "kafolat" removed; flag emoji removed |
| Login / register / password reset / verify | guest | works | pages load, no console errors |
| Telegram 1-click login | guest | **not tested** | needs the live bot |
| Dashboard | FREE, paid, teacher, admin | works | loads for all; onboarding modal appears for a new account |
| Test list and test detail | FREE, paid | works | 3 BMB tests listed; badges "70 savol", "0–75 ball", "B1 uchun o'rtacha kamida 38/75", "Urinishlar: cheksiz" |
| BMB take → result (45 single-choice) | paid | **fixed** | keyboard answers saved (`save-answer` 200), reload keeps answers and server timer, confirm dialog shows 2 answered / 43 unanswered; result page previously showed invented topic analysis and rendered *under* the exam |
| IELTS take → result (40 q, 3 passages) | paid | **fixed** | the legacy English screen was unstyled (no Tailwind) and unusable on desktop and mobile; now runs on the CD screen: passage split view, parts, 0/40 counter; result shows raw score + estimated band |
| CEFR CD Record Mock | paid, FREE trial, admin preview | works | verified in the previous PR (0 / 15 / 35 cases, trial part, preview) |
| CEFR-301 (35 "single" L/R, no sections) | paid | partly | now takeable; its result has no L/R split because the seed has no sections (content issue) |
| Results list / detail | paid | works | CEFR result shows 0–75 per section and no Band; English results no longer carry BMB/Rasch labels |
| Paywall modal, free trial | FREE | works | verified in the previous PR |
| `/pricing` receipt page | FREE | **fixed** | claimed "Vision AI activates the plan in 3 seconds" — false since #116 |
| `/my-subscription`, `/profile` limits | paid | works | both read the same entitlement |
| Receipt upload and admin approval | FREE, admin | partly | upload path covered by tests (`test_free_pro_leak`); admin approval click-through **not tested in the browser** |
| Referral card | FREE | **open** | styling issues listed in `DESIGN_AUDIT.md` |
| Teacher: groups | teacher | works | `/groups` lists the QA group |
| Teacher: finance, vocab generator | teacher | **fixed** | both called a non-existent `/api/v1/school/overview/` (HTML instead of JSON), group picker was empty |
| Teacher: AI test converter, essay queue, import | teacher | pages load; AI calls **not tested** (no key) |
| Admin panel (users, tests, topics, tuition) | admin | works | all pages load, no errors |
| Admin: `/subscribe` | admin | **open** | an administrator can open the plans page (nav hides it, the route is not blocked) |
| Feedback: submit, public list, inbox, reply, publish, my feedback, result prompt | guest / student / admin | works | submitted from the browser at 375 px, stored (HTML stripped, context, consent), published by admin, shown as "Komiljon R." |
| 1v1 Arena | — | **not tested** | needs two live sessions / websockets |
| AI Speaking, AI essay grading | — | **not tested** | need audio and an AI key |
| OMR scanner | — | covered in the previous PR; **not re-tested** here (instruction: do not touch) |
| Telegram bot flows (feedback alerts, replies) | — | **not tested** | no bot locally; the Celery tasks are unit-tested with Telegram mocked |
| Dark mode, mobile menu | all | partly | result and paywall pages checked in the previous PR; the new modal and inbox were checked in light mode only |

## Bugs found and fixed here
1. IELTS / plain CEFR attempts unusable (unstyled Tailwind-only layout).
2. Result page rendered the exam under the score; topic analysis was invented from question order and from fixed fractions of the correct count, followed by an "AI mentor prepared a 3-day plan" claim.
3. `/pricing` promised instant activation (contradicting #116).
4. Teacher finance and vocab pages: wrong endpoint, plus a hardcoded 400 000 fee fallback.
5. `SubjectSwitcher` used flag emoji and mixed subject with language; flags render as "UZ"/"GB" letters on Windows (23 places in 12 files).
6. Header tag "Milliy Sertifikat & AI Esse LMS" ignored the subject.
7. Unproven claims on landing, "Official IELTS …" labels on essay pages, a stray dotless "ı" in "Obuna rejalari".
8. `audit_unpaid_subscriptions` crashed on production (wrong essay date field).

## Open items (not fixed here)
- `/api/v1/billing/card-details/` is public: any visitor can read the card number and holder. Decision needed (require login?).
- `seed_accounts.py` contains fixed passwords (`GrandAdmin2026!`, `GrandUstoz2026!`); never run it on production. `seed_official_omr_tests` names local tests "Cambridge Official …".
- IELTS band table is one function for Listening and Reading and is labelled "Official IELTS scale" in code; per decision (b) it should move to a JSON scale labelled "taxminiy" and be split per section. Existing tests pin the current values, so it needs its own change.
- Legacy `EnglishExamInterface` (≈1 800 lines of Tailwind markup) is now unreachable for real attempts and should be removed.
- Every page still has controls smaller than 44 px on desktop; mobile spot checks only.
- `Loading session…` (English, hard-coded) shows while the session restores.
- Completing a test with almost no answers still gives XP (15 XP for 2 answers in 5 seconds).
- Dev: the browser log lists every request twice (probably React StrictMode double effects); not verified, and production builds do not do this.
- Screenshot attachment for bug reports and optional audio upload were not built.
