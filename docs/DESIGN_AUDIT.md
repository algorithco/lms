# Design audit — most important problems, by priority

Evidence is what was actually seen or measured in the browser (375 px / 1366 px). "Reported" means the owner listed it and it was **not** re-inspected in this session.

| # | Problem | Where | Status |
|---|---|---|---|
| 1 | IELTS / plain CEFR exam screen unreadable: Tailwind-only layout, columns collapse to 1-px stripes (screenshot: title wrapping one word per line, panels as vertical bars) | `/english-exam/:id` | **Fixed** (runs on the CD screen) |
| 2 | Result shown under the still-visible exam; topic block with invented percentages | `/take/:id` | **Fixed** |
| 3 | Subject switcher used country flags (Windows shows "UZ"/"GB" letters) and sat where the interface language belongs | header, 12 files | **Fixed**: text labels, language switcher added beside it |
| 4 | Payment page promised instant activation | `/pricing` | **Fixed** |
| 5 | Landing: three "Fikr bildirish" buttons, invented numbers and guarantees | `/` | **Fixed** |
| 6 | Dead Tailwind utility classes in `SubjectSwitcher`, `EnglishExamInterface`, landing buttons (no Tailwind installed) | 8+ files | Open: one style system needed (decision: extend `index.css` tokens, do not add Tailwind) |
| 7 | Touch targets under 44 px: 12–28 controls per page measured at desktop width (tabs, icon buttons, chips) | all pages | Open: new components (feedback modal, inbox, paywall) meet 44 px; legacy pages do not |
| 8 | Hard-coded Uzbek/English strings outside i18n ("Loading session…", pricing plan names, several panel pages) | many | Open |
| 9 | Referral card: plain input, grey buttons, empty label box, "Friends Invited:0Bonuses" without spacing | dashboard, profile | Reported, not re-inspected |
| 10 | Onboarding modal text unreadable on the dark background | dashboard (new user) | Reported, not re-inspected (modal appeared in light mode) |
| 11 | Sticky header overlapping content | dashboard | Reported, not re-inspected |
| 12 | Subject-specific labels on English tests (BMB/Rasch/"Milliy Sertifikat") | results list/detail | **Fixed** (hidden for English / CEFR) |
| 13 | Administrator can open the plans/subscription page by URL | `/subscribe` | Open |
| 14 | A completed near-empty test awards XP | `/take/:id` | Open (product decision) |
| 15 | Display names such as "komiljon Roziyev" / initials "kR" | header, profile | Reported; `formatDisplayName` exists, not re-checked per page |

New components follow the existing tokens (`--card`, `--ink`, `--accent`, `--border`) so both themes work; they were visually checked in light mode; the feedback modal's dark colours were checked by computed values only.
