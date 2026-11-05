# QA report — branch `hotfix/integrity-audit` (integrity and security, no new features)

Base: `main` at `ae4e93c` (v1.81.0). **#118, #119 (`feat/mobile-pro-ui`) and #120 are all in `main`**; production runs image `sha-e061702` (#120), 0 unapplied migrations, `/healthz/` 200 (read-only checks, 2026-11-05). `grant_subscription` and the plan rules were not touched.

## 1. Production, read only (nothing was changed on the server)
| Check | Result |
|---|---|
| Accounts created by the old fixed-password `seed_accounts` command (git history `ec15c2e`) | **Two exist on production** (an admin and a teacher), created before the fix `b877c6a`. Details (ids, dates) were given to the owner outside the repository; the owner rotates the passwords. No personal data was read out |
| `.env.prod` key names | `PAYMENT_CARD_NUMBER`, `PAYMENT_CARD_HOLDER`, `PAYMENT_CARD_BANK`, `PAYMENT_ADMIN_USERNAME`: **not set**. `OPENROUTER_API_KEY`: set. `GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`: not set. `ESSAY_AI_PROVIDER=openrouter`, `ESSAY_AI_MOCK_MODE=False`. `TELEGRAM_BOT_TOKEN`: set. **So production has been showing the card number that was written in the code as a default** (see §5) |
| `audit_unpaid_subscriptions` | 0 unpaid active paid-plan subscriptions, 0 teacher sponsorships (nothing to break down by day or tier) |
| "official / guarantee" wording (`rasmiy`, `official`, `British Council`, `Cambridge`, `kafolat`, `guarantee`) | `essays.EssayTopic` id 2 `title` (rasmiy) and `description` (kafolat); `payments.SubscriptionPlan` id 3 `description` (rasmiy). `tests.Test`, `Question`, `Subject`: no matches |
| Migrations, health | all applied; web/bot/worker/beat healthy; image `sha-e061702` |
| CEFR writing | 2 essay topics exist, none "multilevel"; Record Mock (test 14) holds the three `written` tasks (1.1, 1.2, Part 2) |

Texts in the database were **not** changed: `manage.py fix_official_claims` (dry run by default) lists them and what it would write.

## 2. Honest grading: no invented score
Found and removed (all returned a score, band, transcript, questions or an explanation when the AI failed):
| Where | Was | Now |
|---|---|---|
| `grade_ielts_essay` (IELTS, CEFR Multi-level) | any provider error, timeout or broken JSON → `_mock_ielts_response` (an invented band) saved as GRADED | `AIUnavailable`: Celery retries, then the essay is ERROR (not graded), the allowance is refunded, the failure is counted |
| `DeepSeekGrader` (BMB, IELTS) | fell back to `_mock_12_criteria_response` | raises |
| `apply_ai_result` | accepted any `_mock_mode` result | refuses a mock grade unless the platform is knowingly in mock mode (no key and the flag) |
| AI Speaking | fixed fake transcript and a 6.5–7.0 band when audio/AI failed; missing scores defaulted to 6.5/7.0 | `AIUnavailable`: nothing saved, no XP; scores must be present and 0–9 |
| Vocabulary generator | built-in word list with invented translations and distractors | 503, nothing saved |
| Test converter | dummy "IELTS Reading" / "Navoiy" template; a guessed correct answer "A"; "Variant A…" choices | no questions → 422; unknown answer stays empty and flagged; saving refuses incomplete questions |
| Explain mistake (`ai_tutor`) | "your variant contradicts morphological rules" for any wrong answer, cached 7 days | only the answer key and the stored explanation; not cached |
Every failure path: status ERROR / `not_graded`, the allowance is returned (essays: `refund_usage_for_submission`; speaking, OCR, OMR, vocab, converter: the daily call), and `record_ai_failure` sends **one** Telegram message to the admin after 3 failures in a row per feature (30 min cooldown). Mocked: timeout, provider error, broken JSON, missing/out-of-range scores, missing key.

Not changed: BMB (`grade_essay`) already raised on failure; OMR already refuses unreadable marks. CEFR Writing topics (Record Mock 1.1, 1.2, Part 2) come from `manage.py publish_cefr_writing_topics` (dry run by default, reads the exam's own task text, idempotent); with them present the Essay studio lists them. **Not run on production.**

## 3. Abuse and cost control
| AI endpoint | Auth | Plan | Daily cap (FREE / STARTER / PRO / PREMIUM) | Rate limit | Size / type |
|---|---|---|---|---|---|
| OCR `/essays/ocr/` | yes | plan must include photo essays (FREE, STARTER refused; staff exempt) | **new** 0 / 5 / 5 / 20 | 20/h | 10 MB per page, ≤ 10 pages, `image/*` |
| Essay submit (text, image, custom) | yes | weekly quota (unchanged) | quota | 5/min | 50k chars |
| IELTS grade `/essays/ielts/grade/` | yes | **was none: any account, unlimited** → now text-essay quota | quota | **new** 5/min | 50k chars |
| Speaking submit | yes | – | **new** 1 / 3 / 10 / 30 | **new** 10/h | audio only, 25 MB, 5 s–15 min |
| OMR scan | yes | visible tests only | **new** 3 / 10 / 20 / 40 | 10/h | 8 MB, sheet checks |
| OMR confirm | yes | test quota (unchanged) | quota | 10/h | – |
| Test converter | teacher/admin | – | **new** 0 / 0 / 0 / 20 (teachers) | **new** 30/h | 15 MB, PDF/image |
| Vocabulary generator | **was any account** → teacher/admin, own groups | – | **new** same as converter | **new** 30/h | – |
| Essay autosave | owner only | – | – | **new** 60/min | 50k chars |
Admins are exempt from the caps; teachers count as PREMIUM. All numbers are in `FEATURE_DAILY_CAPS` and can be overridden with `settings.AI_FEATURE_DAILY_CAPS`. The caps use the cache (Redis in production): a Redis flush resets the day.
Also closed: the vocabulary "assign homework" accepted any pack and group (now pack owner and group teacher only); OMR listed and read tests of other teachers' private groups and PIN tests (now only tests the student can open).
XP (`apps/tests/xp_rules.py`): none under 30 % answered, none when finished faster than 3 s per question (never under 20 s), at most 40 XP per test per day. Staff previews and trials were already excluded. OMR gives no XP (`xp_earned: 0`, no XP code in the service).

## 4. OMR: what was proved
| Claim | Evidence |
|---|---|
| Non-sheet images rejected | dark screenshot, uniform frame, non-image, oversize, aspect ratio, and a vision answer "not a sheet" each refused (`test_omr_db_integration`), before any AI call for the image checks |
| Unread / unclear / blank mark never becomes "A" | `test_blank_multiple_and_unread_never_become_a`; a letter the question does not have becomes "unread" |
| Confidence threshold | per sheet: more than `OMR_MAX_UNREAD_RATIO` (0.2) unread rows → refused (`test_omr_scan_grades_nothing…`). The reader returns no per-mark confidence; "unsure" is its `null`. **Real-photo accuracy was not measured** (no phone photos / no reader key locally) |
| Student confirms before grading | the scan creates no attempt, result or XP; grading is a separate call with the student's reviewed answers |
| No XP via OMR | test + source check |
| Rate limit and file limits | 10/h scan and confirm; **new** daily scan cap; 8 MB; JPG/PNG/WEBP verified by content |
| Questions shown by sequence number | `number` and `key` per item (`test_cefr_numbering_has_70_objective_questions`) |
Not verifiable here: confirm can be called without a scan (it grades whatever the student submits, with the test quota and access checks): left as is.

## 5. Payment card
The card number was a code default in settings, in two bot handlers and in `card_info_view`, and in both `.env*.example` files. Removed everywhere. Without `PAYMENT_CARD_NUMBER` **and** `PAYMENT_CARD_HOLDER` the endpoints answer 503 `payment_unavailable` ("To'lov ma'lumoti hozircha mavjud emas."), the bot says the same, and the admin gets one Telegram message every 6 hours. **Production has none of these variables: set `PAYMENT_CARD_NUMBER`, `PAYMENT_CARD_HOLDER` (and `PAYMENT_CARD_BANK`) in `.env.prod` before merging, or students will see "not available" instead of the card.**

## 6. Plan display with a manual limit
`display_plan` / `get_display_tier`: with an admin limit override the plan name comes from the student's subscription (FREE when none) and the override is reported apart (`custom_limit`, `/me.has_custom_limit`, a "Custom limit" mark in the plan badge). Limits themselves still come from the override; `get_user_plan_tier` (used for AI daily quotas) is unchanged.

## 7. Backups
`backup_db.sh`, `backup_offsite.sh`, `restore_test.sh`, `docs/BACKUP.md`. Verified locally on PostgreSQL 17.11 with a freshly migrated database (117 tables): dump + gzip + checks, weekly copy, rotation, refusal of a too-small dump (old backups kept), corrupted gzip rejected, restore into a scratch database (162 migrations, users present), remote host refused, offsite does nothing without a target. **No cron job or service on the server. `backup_offsite.sh` has not run against a real host. A production dump has not been restored.**

## Checks
| Check | Result |
|---|---|
| `pytest` (full) | **1 561 passed, 2 skipped** (both PostgreSQL-only); 65 new tests in `test_integrity_*` (honest grading 21, abuse controls 29, billing/tier/commands/backup scripts 15, plus updated old tests) |
| `manage.py check` | no issues |
| `manage.py makemigrations --check` | no changes. **This branch adds no migration** |
| `ruff check .` | all checks passed |
| `tsc -b` | clean |
| `vite build` | built |
| `oxlint` | 0 errors, 79 warnings (same as `main`) |
| `npm test` | 13 passed |
| Backup scripts | run for real on local PostgreSQL 17.11 (see section 7) |

## Not tested / open
- Real AI answers: nothing was run against the live provider (mocks only). Real OCR, real OMR photos, real phone keyboards: not tested.
- Production data fixes (`fix_official_claims`, `publish_cefr_writing_topics`) are written and tested but **not run**; they need the owner's approval.
- `docs/ROADMAP_REMAINING.md` named in the task is not in the repository or on disk, so it was not added.
- Pre-existing and left: `tma_essay_topics_view` calls `ensure_multi_subject_seed_data()` on every GET (writes data from a read); the spaced-repetition quiz has a built-in sample word list; the bot text still describes plan limits that differ from the plan rows; legacy pages (speaking, converter, vocabulary) have hard-coded Uzbek text and show the server's message.
- An AI-suggested answer key in the converter (the prompt asks the model to fill a missing key) still goes to the teacher for review; it is not marked as AI-chosen.

---

# QA report — branch `fix/responsive-audit`

Method: live grandec.uz (guest pages) and the local dev servers with the seeded QA accounts (paid student, teacher, admin), in the in-app browser. Each page was loaded in an iframe of the given width and **measured**: document `scrollWidth` vs `clientWidth`, visible elements past the viewport edge (outside scroll containers), interactive elements under 44 px on phones, overlapping controls. Screenshots at 768, 1366 and 390 px; dark mode on the plans page. Bestway was not in scope.

## Found (before this branch)
| Page | Width | Problem |
|---|---|---|
| every signed-in page (student, teacher, admin) | 768 | top bar wider than the screen: the user menu ran 120 px (admin: 250 px) past the right edge and could not be reached |
| `/tests/create` (teacher) | 360, 390 | the "raw test text" column had a 420 px minimum and was cut off |
| grids with 320–360 px minimum columns (profile, groups, speaking, tournaments, landing, panel) | 360 | would overflow a 360 px phone (no overflow at 390) |
| `/plans`, `/subscribe` | all | prices and limits written in the page, disagreeing with the plan rows and between languages; debug line "Subscription Status (session): pro"; Uzbek banner on EN/RU screens; emoji icons |
| sidebar and drawer plan badge | all | **FREE shown next to an active PRO plan** for users restored from the Django session cookie (Telegram / Google): the session payload had no plan, subject or onboarding state and `/me` was never read |
| landing footer | all | Terms / Privacy / Public offer links lead to routes that do not exist (open the home page) |
| sidebar | all | "Tests" lit together with "OMR scanner" and "Create test" |
| phones | 360, 390 | `.btn.sm` 32 px, `.ui-btn--sm` 36 px, inputs 38–41 px, sidebar links 35 px, landing "Kirish" 32 px and menu 34 px, FAQ rows 38 px, footer links 16 px, login "back" link 16 px, "see all" links 16–21 px, test-creator time chips 24 px |
| guest pages `/`, `/login`, `/register` | 1920, 1366, 768, 390 | no horizontal scroll (live site) |

## Fixed and re-measured
| Check | Result |
|---|---|
| paid: dashboard, tests, essays, results, profile, subscribe, my-subscription, arena, checkout, OMR | 768, 390, 360: no overflow, no element past the edge |
| teacher: dashboard, groups, finance, analytics, create test | 768, 390, 360: no overflow |
| admin: panel, users, tests, tuition | 1366, 768, 390: no overflow |
| guest: `/`, `/login`, `/register` (local) | 390, 360: no overflow; header buttons, FAQ rows, footer links ≥ 44 px |
| cookie-restored PRO user (session cookie, no JWT) | sidebar shows "Tarif: PRO, 29 kun qoldi"; backend test `test_session_status_plan` |
| plans page | cards from the plan rows (Starter 5 tests / 3 text / no photo essays a week, Pro 30 / 15 / 15, Premium unlimited), cheapest first, light and dark |
| `manage.py check`, `ruff`, `makemigrations --check`, `tsc -b`, `vite build`, `npm test` (13), `oxlint` (0 errors, 79 warnings as on `main`) | pass |

## Still open
- Phones, legacy pages: segmented controls are 38–40 px inside a 44 px track (as in the design spec); native checkboxes 13 px; the test creator's template chips (25 px), its inline colours and hard-coded Uzbek text; admin table title links 34 px; the landing logo link 32 px.
- Legal pages (terms, privacy, public offer) need real texts from the owner before the footer links come back.
- `Pricing.tsx` / `Subscribe.tsx` (checkout) still have fixed prices and Uzbek strings; the cards there were not rebuilt.
- An active admin `SubscriptionOverride` reports tier FREE (`plan_type` is empty) even when the user also has a paid subscription; not changed here, needs a decision on what an override should show.
- Real devices (iOS Safari, Android Chrome, Telegram in-app browser): not tested; widths were emulated.

---

# QA report — branch `feat/mobile-pro-ui`

Method: local database (sqlite) with the seeded QA accounts (guest, FREE, paid, teacher, admin); both dev servers; the in-app browser. Each page was loaded in an iframe of the given width and **measured** (document `scrollWidth` vs `clientWidth`, leftover raw i18n keys, Uzbek words left on EN/RU screens, buttons under 32 px, whether the dark class is applied), plus screenshots at 375 px. "Works" means it was run; everything else is **sinalmadi** (not tested).

## Checks
| Check | Result |
|---|---|
| `pytest` (full) | **1 492 passed, 2 skipped** (both PostgreSQL-only); new: `test_essay_studio` (10), `test_tests_list_status` (3), dashboard recent essays (1) |
| `manage.py makemigrations --check` | no changes; one new migration on this branch: `essays.0022_essaysubmission_custom_title` (AddField, blank default; no data touched) |
| `manage.py check` | no issues |
| `ruff check .` | all checks passed |
| `tsc -b` | clean |
| `vite build` | built |
| `oxlint` | 0 errors, 79 warnings (pre-existing kinds: `set-state-in-effect`, `only-export-components`) |
| `npm test` (new, Node built-in runner) | **11 passed**: tests-page state (error / empty / no-match / list, never "(0)" on failure), word counter (letter tokens only, same rule as the server), word zones, the five essay states, essay kind per subject, score label, "My essays" filter, topic filter, every `t('key')` in `src` exists in uz/ru/en, the three languages have the same keys. Added to CI (lint job, Node 24) |

## Width sweep (no horizontal scroll, no raw keys)
| Role | Pages | Widths | Language / theme | Result |
|---|---|---|---|---|
| guest | `/`, `/login`, `/register`, `/join/<bad>`, `/r/<code>` | 360, 375, 390, 412, 768 | UZ light | 25 / 25 clean; `/r/<code>` goes to `/register?ref=…` as designed |
| FREE | dashboard, tests, essays, new essay, photo essay, results, profile, plans | 360, 390, 412, 768 | UZ light | 32 / 32 clean |
| paid | dashboard, tests, essays, photo essay, results, profile | 360, 375, 412 | UZ light | 18 / 18 clean |
| teacher | dashboard, tests, groups, finance, vocab generator, profile | 360, 390, 768 | UZ light | 18 / 18 clean |
| FREE | dashboard, tests, essays, profile, photo essay | 360, 412 | **EN dark** | 10 / 10: no overflow, dark applied (`body` `#0B0F17`); Uzbek left only in the **onboarding modal** (open item) |
| FREE | dashboard, tests, essays, new essay, profile | 360, 390 | **RU light** | 10 / 10 clean after the profile Telegram block was moved to i18n |
| admin | panel, profile, `/subscribe`, `/plans` | 375 | UZ light | plans and checkout routes now redirect to `/panel`; drawers show no plans link |

Screens looked at (375 px): teacher finance (dark): KPI cards in two columns, student cards with status chip, facts and actions, no table scroll. Group invite (light, guest): group card, 44 px "Kirish va qo'shilish" + "Yangi hisob yaratish", no scroll in either direction. Earlier sections: tests page, essay studio and write screen, dashboard, drawers (see the commits).

## Modules
| Module | Role | Status | Evidence |
|---|---|---|---|
| Top bar, subject switcher, bottom nav | all | works | 52 px bar (logo + page title, XP, avatar), segmented subject switch under it, 5 items with one active colour; no overflow at 360–412 |
| Interface language | all | works | text picker (O'zbekcha / English / Русский) in the profile drawer; subject is a separate state |
| Tests page | FREE, paid | works | skeleton → list; error state with retry when the API fails (no "(0)"); empty and no-match states; resume card; one code field; status per card from `my_status` |
| Essay studio | FREE, paid | works | type chips + search; "My essays" with filters; CEFR shown as a note pointing to the mock writing section (its grader has no real AI locally) |
| Write screen | paid | works | collapsible task, sticky counter `words / min–max` with colour zone, "Saqlandi ✓" via the new JWT autosave, leave guard |
| Own-topic essay (Ona tili) | paid | works by test | charges TEXT quota once; too short / duplicate cost nothing |
| Photo essay | FREE, paid | works by test | OCR free, submit charges IMAGE once; FREE refused (tariff has 0 photo essays); **real OCR sinalmadi** (no OCR key) |
| Result page | paid | works | translated status, "AI tomonidan baholandi" chip, indeterminate progress while grading |
| Dashboard essay block | FREE, paid | works | two latest real essays per subject, empty row otherwise |
| Referral card | FREE | works | full-width link + 2 buttons, two stats |
| Landing | guest | works | tighter sections on phones; exam tracks as one card set; no "rasmiy" / "Cambridge" / "kafolat" claims |
| JoinGroup | guest, FREE | works | preview, login/register links keep `next`; the false "automatic 365-day PRO" banner is gone (#116: joining a group grants nothing) |
| ReferralRedirect | guest | works | spinner on tokens, i18n |
| Teacher finance | teacher | works | KPIs, reminders banner, student cards, actions call the same endpoints as before; the "400 000" fallback fee is gone |
| Vocab generator | teacher | loads | form + four format tabs; **AI generation sinalmadi** (no key); the pre-filled demo word list is gone |

## Bugs found and fixed here
1. JoinGroup promised "365 kunlik PRO tarifi avtomatik yoqiladi"; joining grants nothing (#116).
2. Essay autosave from the SPA never worked (session endpoint, JWT client); new JWT endpoint.
3. Test list was paginated without an order (pages could repeat or skip a test); now newest first when no order is given.
4. The "All sections" drawer had its own subject tabs that wrote only localStorage; the profile subject won, so they could silently do nothing. Removed (the segmented switcher is the one place).
5. Admins saw "Tariflar va obuna" in both drawers and could open the plans and checkout routes.
6. Profile pre-filled a fixed Telegram chat ID for every admin.
7. Profile drawer showed "#ID-2026" when the user id was missing.
8. Landing "Qaysi imtihon" cards squeezed by a stray `flex` class.
9. "Loading session…" was hard-coded English.

## Open / sinalmadi
- **Telegram** in-app browser: sinalmadi. **Real phone keyboards** (iOS Safari, Android Chrome): sinalmadi; the write screen uses `visualViewport` and 16 px inputs, exercised only in an emulated viewport. **AI answers** (essay grading, vocab generation, explain): sinalmadi, no provider key locally. **Real OCR**: sinalmadi.
- `OnboardingModal` (1 074 lines, ≈ 60 hard-coded Uzbek strings, inline styles; some values such as "Oliy toifa" are stored in the profile) still shows Uzbek on EN/RU screens; needs its own pass.
- Admin panel group list shows the raw subject code (`ona_tili`); panel pages were not part of this branch.
- Legacy pages still have controls under 44 px (panel tables, `#GR-…` group code chips, some profile buttons).
- CEFR essays: the multilevel grader returns invented scores when no AI is configured, so CEFR topics are not offered in the studio until that is fixed.

---

# Previous report — branch `feat/results-dashboard-mobile` (merged as #118)

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
