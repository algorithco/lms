# QA report — branch `feat/results-dashboard-mobile`

Method: local database (sqlite), seeded QA accounts (guest, FREE, paid, teacher, admin), the dev servers in the in-app browser at 375 px, 360 px and 1366 px (light; dark only partly), plus the full backend suite. "Works" means it was run; everything else is listed as **not tested**.

## Checks
| Check | Result |
|---|---|
| `pytest tests` (full) | **1 478 passed, 2 skipped** (the 2 skips are PostgreSQL-only tests); 47 new tests (`test_result_review`, `test_question_issue`, `test_dashboard_api`) |
| `manage.py makemigrations --check` | no changes |
| `manage.py check` | no issues |
| `ruff check .` | all checks passed |
| `tsc -b` | clean |
| `npm run build` (vite) | built |
| `oxlint` | 0 errors, 77 warnings (all but 4 pre-existing; the new ones are `set-state-in-effect` in the exam, dashboard, inbox) |

## Modules
| Module | Role | Status | Evidence |
|---|---|---|---|
| Result page: per-question review | paid | works | Record Mock result at 375 px: summary by section and part ("Listening · Qism 1 5/8"), filter chips with counts, option letter + text ("B: Can you?"), "Sizning javobingiz" / "To'g'ri javob", status with icon and text |
| "Nega xato?" | paid | works | hint text (unanswered / near miss / not in text / word limit), stored explanation with "AI tayyorlagan, tekshirilmoqda" label, evidence quote |
| "Tushuntir" (AI) | paid, FREE | **partly** | gating, daily cap, cache, quota and prompt are unit-tested with the model mocked; with no provider key the button shows "Tushuntirish olinmadi" — **a real model answer was never obtained** |
| Draft explanations | — | works | `draft_explanations` on the local Record Mock: 14 drafts from the passage and key, Listening untouched (no transcript) |
| Free-trial result | FREE | works by test | one line + plans button + same review; **not clicked through in the browser** |
| Estimate banner | all | works | removed; `SHOW_ESTIMATE_NOTICE` turns it back on (test) |
| Dashboard (Ona tili, Ingliz tili) | paid | works | real indicators; English shows Listening/Reading best section scores (0–75), Ona tili shows average and best grade; subjects never mix (test) |
| Dashboard, no data | FREE | works | empty state, one main button, compact referral |
| Plan label | paid | works | header chip, sidebar card ("30 kun qoldi", "Testlar: 8/30") and drawer all read `/me` + the entitlement |
| Referral card | FREE | works | input-group, "Nusxalash"/"Nusxalandi ✓", share |
| CD exam on a phone | paid | works | 375 × 812 and 360 × 800: no horizontal scroll, every control ≥ 44 px, timer always visible, text | questions tabs, bottom bar (previous / palette / next, "Saqlandi ✓"), palette sheet with answered state, reload keeps position and timer |
| Offline answers | paid | works | `save-answer` blocked + `offline` event: banner "Aloqa yo'q, javoblar saqlanyapti", answer queued in localStorage, sent after `online` ("Aloqa tiklandi"), queue empty |
| CD exam on desktop | paid | works | two columns, passage sticky |
| BMB exam on a phone | paid | partly | finish/exit buttons and hotkey hint hidden on phones, leave confirmation, offline banner, readable timer; the rest of the screen is the old one |
| "Savolda xato bormi?" | paid | works | bottom sheet at 375 px, 2 steps, report stored with test/section/part/number, no answer in the context |
| Admin inbox | admin | works | question-issue filter, "Savollar bo'yicha" tab, filter bottom sheet at 375 px |
| Landing feedback block | guest | works | cards from approved + consented feedback; empty state with a centred button (code path; the list was non-empty locally) |
| Teacher / admin dashboards | teacher, admin | loads | no console errors from this branch's code |
| UZ / RU / EN | — | partly | every new key exists in the three languages (script-checked); screens were looked at in UZ only |
| Dark mode | — | partly | tokens only; the dashboard was seen with the dark class set by hand, the app's own toggle was not used |

## Bugs found and fixed here
1. `POST /api/tests/questions/<id>/explain-mistake/` returned the correct answer and explanation to **any signed-in user, during an exam** (no ownership or state check). Now it needs a finished attempt of the caller (or their course's teacher / an admin). An existing test had encoded the old behaviour and was changed.
2. CD gap-fill answers were never shown on the result page (their key is in `GapBlank`, the serializer read only `correct_text`).
3. Toasts rendered inline at the page bottom (no styles).
4. Referral card promised "+5 tests, +2 essays"; the backend gives +1 / +1.
5. Onboarding modal: dark background with dark text in light mode.
6. Score-card image carried a fake QR code and "official authenticated result" text.
7. Exam timer and progress bar used hard-coded dark colours.
8. Phone top bar clipped its menu button (20 px overflow).
9. After login the tier could be stale (login payload had no plan); `/me` is now re-read.
10. Names/initials: "komiljon Roziyev" / "kR" in the sidebar and landing.
11. Result list showed "O'tmadi" (failed) for IELTS results, which have no pass mark.
12. The unreachable `EnglishExamInterface` (1 800 lines, placeholder questions) is gone.

## Open / not tested
- **Telegram** (in-app browser, the admin summary message): not tested; the Celery task is unit-tested with Telegram mocked. The exam asks before leaving on browser back, but the Telegram back button cannot be intercepted by a web page.
- **Real devices** (iOS Safari, Android Chrome): not tested; the on-screen keyboard behaviour (`visualViewport`, hiding the bottom bar while typing, 16 px inputs) was written to the platforms' rules and exercised only in an emulated viewport.
- **AI**: no key locally, see above. **Audio**: no audio files; the player is the browser's native controls (the schema has no "play once" flag, so seeking is not restricted anywhere).
- Attestation has no content locally; its dashboard branch is covered by the `kind` logic only.
- Pre-existing, unchanged: card number default in `views_billing.card_info_view`, `seed_accounts` history (see the previous report below), `/subscribe` open to admins, XP for near-empty tests.
- BMB (`TakeTest`) is not rebuilt on the new exam shell: legacy question types (multiple answers, text, matching) are not supported by the CD screen.
- Teacher pages still on dead Tailwind classes (see `DESIGN_AUDIT.md`).

---

# Previous report — branch `feat/ui-qa-real-exams` (merged as #117)

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
| `/tests` when the API fails (429 / 500 / 502 / network) | FREE | **fixed** | showed the right error and a retry button, but the heading said "Testlar (0)" and 429/500 printed raw English text; now a friendly message, no count, retry recovers |
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
| Dark mode, mobile menu | all | partly | result and paywall pages checked visually in the previous PR; the new feedback modal was checked by computed colours in dark mode (card `#131B2E`, text `#F8FAFC`, selected chip dark-on-amber ≈ 8:1), not by screenshot; the inbox was seen in light mode only |

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
- Card details: now signed-in only (guests get 401; fixed). The server still has a hard-coded **default** card number/holder in `views_billing.card_info_view` (used when `PAYMENT_CARD_NUMBER` / `PAYMENT_CARD_HOLDER` are unset). Check those variables on the server, then remove the default.
- `seed_accounts.py` no longer contains passwords and refuses non-local databases (fixed). Whether it was ever run on production is **unknown**; if it was, the admin and teacher accounts it creates may carry the old fixed passwords (see the git history of that file) and should be checked and rotated. `seed_official_omr_tests` names local tests "Cambridge Official …".
- IELTS band table is one function for Listening and Reading and is labelled "Official IELTS scale" in code; per decision (b) it should move to a JSON scale labelled "taxminiy" and be split per section. Existing tests pin the current values, so it needs its own change.
- Legacy `EnglishExamInterface` (≈1 800 lines of Tailwind markup) is now unreachable for real attempts and should be removed.
- Every page still has controls smaller than 44 px on desktop; mobile spot checks only.
- `Loading session…` (English, hard-coded) shows while the session restores.
- Completing a test with almost no answers still gives XP (15 XP for 2 answers in 5 seconds).
- Dev: the browser log lists every request twice (probably React StrictMode double effects); not verified, and production builds do not do this.
- Screenshot attachment for bug reports and optional audio upload were not built.
