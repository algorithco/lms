# Design audit

Evidence is what was seen or measured in the browser (375 px phone, 1366 px desktop, light and dark) unless marked "reported" or "not checked".

## Root cause of the "grey, unstyled" components
The code used Tailwind utility classes (`bg-white`, `rounded-xl`, `dark:…`, `flex-col` …) but **Tailwind is not installed** (no dependency, no config, no `@tailwind` in the CSS). Those classes were dead: the browser showed default buttons and inputs. Only a few utilities (`hidden`, `flex`, `md:flex`, `grid`, `gap-6`…) were ever hand-written in `index.css`. Decision (owner): do **not** add a library; move what users see to semantic classes on the existing tokens (`--card`, `--ink`, `--accent`, `--border`, …).

### Inventory (grep of `className` strings for undefined utility classes, before this branch)
| File | Dead classes (uses) | Now |
|---|---|---|
| `pages/tests/EnglishExamInterface.tsx` | 1 149 | **Deleted** (unreachable legacy exam screen with placeholder questions); 80-line loader |
| `pages/tests/CefrExamComponents.tsx` | 339 | **Deleted** (only used by the legacy screen) |
| `pages/Landing.tsx` | 305 | Feedback block rebuilt (`PublicFeedbackList`); the rest were duplicates of inline styles and were removed |
| `pages/TeacherFinanceDashboard.tsx` | 345 | **Rewritten** in `feat/mobile-pro-ui` (`tf-*`, cards instead of a wide table, i18n) |
| `pages/TeacherVocabGenerator.tsx` | 285 | **Rewritten** in `feat/mobile-pro-ui` (`tv-*`, chips for formats, no demo word list) |
| `pages/JoinGroup.tsx` | 270 | **Rewritten** in `feat/mobile-pro-ui` (`jg-*`; false PRO banner removed) |
| `components/ReferralCard.tsx` | 118 | **Rewritten** (`ref-*` classes, full + compact) |
| `components/ScoreCardModal.tsx` | 80 | **Rewritten** (`modal-*`, `scorecard-*`); fake QR code and "official result" line removed from the image |
| `pages/Dashboard.tsx` | 54 | **Rewritten** (`dsh-*`) |
| `pages/TakeTest.tsx` | 52 | Loading/error screens rebuilt; 3 dead tokens left in templates |
| `components/HowItWorks.tsx`, `HeroCarousel.tsx`, `Layout.tsx`, `MobileBottomBar.tsx`, `Plans.tsx`, `Subscribe.tsx`, `Tests.tsx`, `TeacherGradebook.tsx`, `TestAddictiveResults.tsx` | 1–33 each | Dead tokens removed (inline styles already covered them) / component rewritten |
| `context/ToastContext.tsx` | 15 | **Rewritten** — toasts had no position at all and rendered at the page bottom |
| `pages/ReferralRedirect.tsx` | 17 | **Rewritten** in `feat/mobile-pro-ui` (shared spinner, i18n) |

After `feat/mobile-pro-ui` no user-facing page from this inventory is left on dead classes. The next styling debt is inline styles with hard-coded colours (`OnboardingModal`, `Profile`, the drawers' inner rows, panel pages), which do not follow the tokens in dark mode.

## Problems
| # | Problem | Status |
|---|---|---|
| 1 | Referral card: plain input, grey buttons, empty label box, "Friends Invited:0Bonuses" | **Fixed** (input-group with copy / "Nusxalandi ✓" / share; stats line). Also fixed a false promise: it said "+5 tests, +2 essays", the backend gives +1 / +1 |
| 2 | Landing "Fikr bildirish" button grey; empty state | **Fixed** (`PublicFeedbackList`) |
| 3 | Onboarding modal unreadable: hard-coded dark background with `var(--ink)` text (dark on dark in light mode); `--ink-muted` undefined | **Fixed** (tokens; `--ink-muted` aliased) |
| 4 | Search / code inputs grey; hard-coded "English CBT Mock & Exam Access" | **Fixed** (`MockCodeCard`, i18n, `ui-input` 16 px). Hard-coded quick-join buttons for seeded codes (`#MOCK-BMB04` …) removed |
| 5 | Toasts unpositioned | **Fixed** |
| 6 | Exam timer and progress bar had hard-coded `#1c1c1c` with dark text in light mode | **Fixed** |
| 7 | Phone top bar clipped the menu button at 375 px (20 px overflow) | **Fixed** (streak chip hides under 460 px) |
| 8 | Header tagline flipped between two texts while loading | **Fixed** (rendered only once the profile's subject is known) |
| 9 | Name "komiljon Roziyev", initials "kR" | **Fixed**: one helper (`lib/displayName.ts`) used by header, drawer, sidebar, profile, landing, dashboard, share cards |
| 10 | "Tarif: BEPUL" at the top and "PRO" in the sidebar | **Fixed**: one source (`useTier` from `/me`), `/me` re-read after every login path; PRO card shows real days left and test usage instead of "unlimited" |
| 11 | Catalog numbers "1 642 ta savol", "850", "1 200", "70% Ustama" | **Removed** (no counts, no promises the database cannot back) |
| 12 | Sticky header overlapping content | **Not reproduced** in this session; the top bar background is opaque (`--topbar-bg` ≥ 0.92) with blur. Reported earlier, not confirmed |
| 13 | Touch targets under 44 px | New components (review, sheets, exam, dashboard, inbox) are 44 px+. Legacy pages (teacher pages, groups, panel tables) still have smaller controls |
| 14 | Hard-coded strings outside i18n | New and rewritten components use i18n (UZ/RU/EN); a test now checks that every `t('key')` exists in all three. `feat/mobile-pro-ui` moved the tests page, essay studio, both drawers, profile Telegram block, route loaders and teacher pages to i18n. Still hard-coded: `OnboardingModal` (≈ 60 strings), several panel pages |
| 15 | Administrator can open `/subscribe` | **Fixed** in `feat/mobile-pro-ui`: plans and checkout routes redirect admins to `/panel`; no plans link in either drawer |

## Mobile pass (`feat/mobile-pro-ui`)
Rules: `docs/MOBILE_DESIGN_SPEC.md` (spacing / radius / type scale, 44 px targets, one accent per screen, one primary action, states for loading / error / empty). Measured at 360, 375, 390, 412 and 768 px for guest, FREE, paid and teacher; no page in the sweep scrolls horizontally (`docs/QA_REPORT.md`).

| # | Problem | Status |
|---|---|---|
| 16 | Top bar crowded (logo, tagline, language flags, hamburger, avatar) | **Fixed**: logo + page title, XP chip, avatar; language moved to the profile drawer as text |
| 17 | Bottom nav: 6+ items, several active colours | **Fixed**: 5 items, one active colour (`--accent-dark`) |
| 18 | Tests page showed "Testlar (0)" when the request failed | **Fixed**: error state with retry; count only after a successful load |
| 19 | Grids widened by chip rows (page clipped at 360 px) | **Fixed**: `minmax(0, 1fr)` columns and `min-width: 0` children |
| 20 | Essay write screen: task pushed the editor below the fold, counter scrolled away | **Fixed**: collapsible task, sticky counter bar |
| 21 | Duplicate subject switch in the nav drawer (could silently do nothing) | **Removed** |
| 22 | Landing: large gaps on phones; exam cards squeezed | **Fixed** |

## Not checked
Real iOS Safari / Android keyboards (the keyboard handling uses `visualViewport` and was exercised only with an emulated viewport), Telegram in-app browser, screen readers.
