# Mobile design spec

Short rules every screen follows. Phones first (360–412 px), then tablet (768) and desktop. Most visitors come through the Telegram or Chrome in-app browser, where the browser's own bar already takes the top of the screen: sticky elements at the top stay compact (one row, ≤ 56 px).

Tokens live in `frontend/src/index.css` (colours, theme) and `frontend/src/styles/ui.css` (scale, components). Never hard-code a colour in a component: use a token.

## Scale
| | Tokens | Values |
|---|---|---|
| Spacing (4/8 grid) | `--sp-1 … --sp-8` | 4, 8, 12, 16, 20, 24, 32, 40 px |
| Radius | `--r-sm`, `--r-md`, `--r-lg`, `--r-pill` | 8, 12, 16, 999 px |
| Shadow | `--shadow-1` (cards), `--shadow-2` (sheets, menus) | soft, one direction |
| Text | `--fs-xs` 12, `--fs-sm` 14, `--fs-md` 16, `--fs-lg` 18, `--fs-xl` 22, `--fs-2xl` 28 | body and **every input ≥ 16 px** (no iOS zoom) |
| Touch target | `--tap` | 44 px minimum, 48 px for primary actions |

## Colour roles
- **One primary colour** (`--accent`, amber) for primary buttons, the active tab, the active nav item. The same colour on every page.
- **Green** (`--emerald`) only for success ("Saqlandi", correct answer). **Red** (`--danger`) only for errors and wrong answers.
- Cards are plain surface (`--card`) with a thin border. Colour appears only as a small icon chip (`.ic-chip`), never as pastel card backgrounds.
- State is never colour alone: always an icon or text next to it.
- Contrast: text on surface ≥ 4.5:1 (WCAG AA) in light and dark; checked with the tokens, not with hand-picked hex values.

## Components (`styles/ui.css`)
| Component | Class | Rules |
|---|---|---|
| Card | `.ui-card` | surface, 1 px border, `--r-lg`, padding 16 |
| Icon chip | `.ic-chip` (+ `--accent`/`--success`/`--info`/`--muted`) | 32 px square, tinted background, SVG icon 18 px |
| Chip / filter | `.ui-chip` (`.is-on`) | pill, 44 px tall, horizontal scroll row `.ui-chip-row` (no wrapping) |
| Segmented control | `.ui-seg` | 2–3 equal options, 40 px tall inside a 44 px track |
| Button | `.ui-btn`, `--primary`, `--sm`, `--block` | one primary per screen |
| Input | `.ui-input`, `.ui-search` | 16 px, 44 px, icon inside the search field |
| Bottom sheet | `.sheet` | slides from the bottom on phones, centred dialog ≥ 640 px, keyboard-safe via `--vvh` |
| Sticky action bar | `.ui-actionbar` | bottom, safe-area padding, above the bottom nav when both exist |
| Skeleton | `.ui-skel` | shapes of the real content; no spinner and no grey page overlay while loading |
| Empty / error state | `.ui-state` (+ `--error`) | icon chip, one line of text, one button (retry or next step) |

## Layout rules
- `min-height: 100dvh`, never `100vh`; `env(safe-area-inset-*)` on fixed bars.
- No horizontal page scroll at 360, 375, 390, 412 px. Long rows scroll inside themselves (chip rows, pickers).
- Top bar: page title or logo left, avatar right, one compact XP/streak chip. Subject switcher (Ona tili | Ingliz tili) is a segmented control under the bar. Interface language lives in the profile / menu, as text ("O'zbekcha", "English", "Русский").
- Bottom nav: 5 items, ~56 px + safe area; every page reserves the same bottom padding so nothing hides under it.
- Text never wraps inside buttons, chips or the top bar; long titles are clamped to 2 lines in cards, 1 line in bars.
- Motion: short (≤ 200 ms) and disabled under `prefers-reduced-motion`.
- Icons are SVG (`lucide-react`); no emoji as icons.
