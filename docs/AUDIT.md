# Grand Education — 0-bosqich audit hisoboti

> Sana: 2026-11-02 · Holat: faqat o'qish (kodga o'zgartirish kiritilmagan)
> Manba: lokal repo `C:\Users\user\Desktop\lms`, `main` branch (oxirgi commit `8c6637e`).
> Eslatma: production (`/opt/lms`) bilan solishtirilmadi — ba'zi muammolar serverdagi eski versiyadan bo'lishi mumkin (pastda belgilangan).

---

## 1. Arxitektura qisqacha

| Qatlam | Holat |
|---|---|
| Backend | Django + DRF, `config/settings/{base,development,production,test}.py`. 26 ta app `apps/` ichida. Asosiylari: `accounts` (User/Profile/rollar), `tests` (CBT, OMR, AI konvertor, scoring), `essays`, `results`, `payments` + `billing` + `subscriptions`, `arena` (Channels/WebSocket), `notifications` (Telegram bot + auth), `webapi` (SPA uchun JSON API), `panel` |
| Frontend | React 19 + TS 6 + Vite 8, `react-router-dom` 7. State: React Context (`auth/AuthContext`, `i18n/LangContext`, `theme/ThemeContext`, `context/ToastContext`). Redux/Zustand yo'q |
| API client | Bitta katta fayl `frontend/src/lib/api.ts` (2532 qator): JWT (localStorage) + Django session fallback, avtomatik refresh. `API_BASE = VITE_API_URL ?? ''` → prod'da same-origin |
| Routing | `frontend/src/App.tsx` — `ProtectedRoute` / `TeacherRoute` / `AdminRoute` / `ParentRoute` guardlari. `/english-exam/:attemptId` Layout'dan tashqarida (kiosk rejim) |
| i18n | O'zimizniki: `i18n/LangContext.tsx` + `i18n/translations.json` (5762 qator). **3 til: uz / ru / en** (CLAUDE.md'da UZ/EN deyilgan). `t('key', 'Fallback')` shakli 159 joyda — fallback'lar o'zbekcha hardcode |
| Stil | `index.css` (1925 qator) + `theme.css` — CSS o'zgaruvchilari, `html.light` / `html.dark`. Ko'p komponentlarda inline `style={{...}}` va qattiq ranglar (`#F1F5F9`, `#1E293B`) |
| Fon vazifalari | Celery worker + beat, Redis |
| Docker | `docker-compose.yml` (dev: web, db, redis, celery, celery-beat, bot, nginx:80) va `docker-compose.prod.yml` (image `ghcr.io/algorithco/lms`, nginx **80/443** + certbot) |
| Lokal ishga tushirish | Backend: `python manage.py runserver` (127.0.0.1:8000, lokal `db.sqlite3` bor). Frontend: `cd frontend && npm run dev` (5173, Vite proxy → 8000). Yoki `docker compose up` |

### Tekshiruv natijalari (0-bosqichda ishga tushirildi)
- `tsc --noEmit` — ✅ xatosiz
- `vite build` (scratch papkaga) — ✅ muvaffaqiyatli. Eng katta chunklar: `AnalyticsChart` 375 kB, `index` 366 kB, `LangContext` 302 kB (butun translations.json bitta chunkda)
- `oxlint` — ✅ 0 xato, ~80 ogohlantirish (asosan `set-state-in-effect`)
- `python manage.py check` — ✅ 0 muammo
- Backend testlar: ~84 ta `test_*.py` fayl (bu bosqichda ishga tushirilmadi)

---

## 2. Tailwind holati — MUHIM

- **Tailwind o'rnatilmagan:** `package.json`da yo'q, `tailwind.config.*` / `postcss.config.*` yo'q, `index.css`da `@tailwind` yoki `@import "tailwindcss"` yo'q, Vite plagini yo'q, CDN ham yo'q.
- **Lekin Tailwind klasslari ishlatilgan** (taxminiy utility-klass soni):

| Fayl | ~soni |
|---|---|
| `pages/tests/EnglishExamInterface.tsx` | 454 |
| `pages/TeacherFinanceDashboard.tsx` | 168 |
| `pages/Landing.tsx` | 133 |
| `pages/TeacherVocabGenerator.tsx` | 130 |
| `pages/tests/CefrExamComponents.tsx` | 117 |
| `components/FeedbackModal.tsx` | 104 |
| `pages/JoinGroup.tsx` | 94 |
| `components/ReferralCard.tsx` | 60 |
| `ScoreCardModal`, `ErrorBoundary`, `Dashboard`, `TakeTest`, `HowItWorks`, `Layout` … | 5–27 |

- `index.css` ichida qo'lda yozilgan bir nechta "shim" bor (`.flex { display:flex !important }`, `.grid`, `.grid-cols-1`…), ya'ni klasslarning kichik qismi ishlaydi, qolgani (`bg-slate-950`, `px-4`, `rounded-3xl`, `md:*`, `dark:*`…) **umuman ishlamaydi**.
- **Xulosa:** FeedbackModal, ReferralCard, ingliz tili imtihon interfeysi, JoinGroup, TeacherFinance/Vocab sahifalarining "xunuk/buzuq" ko'rinishining asosiy sababi shu.
- **Tavsiya (4-bosqich uchun):** asosiy dizayn tizimi — `index.css` o'zgaruvchilari (60+ fayl shunda). Lekin `EnglishExamInterface` + `CefrExamComponents` (~570 klass) ni qo'lda ko'chirish katta ish. Variantlar:
  - (a) Tailwind v4 ni `@tailwindcss/vite` bilan o'rnatib, uning ranglarini `index.css` tokenlariga bog'lash (`@theme`), `preflight` o'chirilgan holda — tez, lekin ikki tizim yonma-yon qoladi.
  - (b) 8 ta faylni `index.css` klasslariga ko'chirish — toza, lekin ~2–3 kunlik ish.
  - Tavsiyam: **(a)** imtihon interfeysi uchun (8-bosqichda baribir qayta yoziladi), qolgan kichik komponentlar (FeedbackModal, ReferralCard, JoinGroup, ErrorBoundary) uchun **(b)**. Qaror foydalanuvchida.

---

## 3. Rollar va ruxsatlar

- `apps/accounts/models.py` — `User.role`: `student | teacher | admin | parent | center_admin`. Tarif (`plan`) va `active_subject` — `Profile` modelida.
- Backend admin qoidasi: `apps/accounts/access.py:8 is_platform_admin()` = `is_superuser OR is_staff OR role in (admin, center_admin)`.
- Frontend nusxasi: `lib/api.ts:231 isPlatformAdmin()` + `normalizeUser()` (`lib/api.ts:288`) adminlarga `plan='ADMIN_UNLIMITED'` ni **frontendda** beradi (shart 5 marta copy-paste qilingan).
- DRF permission klasslari: `accounts/permissions.py` (`IsStudent`, `IsStudentOrReadOnly`…), `webapi/permissions.py` (`IsPanelAdmin`, `IsTeacherOrAdmin`), `tests/permissions.py` (`IsAttemptOwner`, `CanStartAttempt`…).
- Menyu rolga qarab 4 joyda alohida hisoblanadi: `Layout.tsx`, `MobileNavDrawer.tsx`, `MobileProfileDrawer.tsx`, `UserNavDropdown.tsx` — markazlashmagan.

⚠️ **Xavfsizlik e'tibori:** `center_admin` (o'quv markaz rahbari) ham `is_platform_admin` = to'liq platforma admini bo'lib qoladi (barcha foydalanuvchilar, to'lovlar, panel). Bu ataylabmi — foydalanuvchidan so'rash kerak.

---

## 4. Test/imtihon modellari

`apps/tests/models.py`: `Test` → `ExamSection` → `ReadingPassage` → `Question` → `Choice`; `TestAttempt`, `StudentAnswer`, `GapBlank/GapResponse`, `MatchingPrompt/Option/Pair/Response`, `ExamWrittenBridge`, `AttemptSectionProgress`, `ExamScoringProfile`.

- `Test.exam_type`: `general | ielts_academic | ielts_general | cefr_multilevel | national_cert`.
- `Test.subject`: **faqat `uzbek` | `english`** — Attestatsiya uchun alohida qiymat yo'q (attestatsiya testlari `uzbek` sifatida saqlanadi → fan logikasi aralashadi). `Profile.active_subject` ham faqat 2 qiymat.
- `max_attempts` (0 = cheksiz) — `apps/tests/services.py:227` da admin/ustoz uchun **backend allaqachon chetlab o'tadi**.
- Ball: `scoring.py`, `bmb_grading.py`, `rasch_engine.py`, `score_converter.py`. Natija tahlili (mavzular bo'yicha) esa **frontendda** soxta hisoblanadi (pastga qarang).
- CD-format uchun kerakli modellarning katta qismi (section, passage, gap, matching) **allaqachon mavjud** — 8-bosqich noldan emas, kengaytirish bo'ladi.

---

## 5. FIX_PLAN muammolari: sabab → fayl → yechim → hajm

Hajm: S = <2 soat, M = yarim kun, L = 1–2 kun, XL = 3+ kun.

### 1-bosqich (kritik)
| # | Muammo | Ehtimoliy sabab / fayl | Yechim | Hajm |
|---|---|---|---|---|
| 1.1 | React #310 `/english-exam/59` | Statik tahlilda `EnglishExamInterface.tsx` (1660 qator) va `CefrExamComponents.tsx`da shartli return'dan keyingi hook **topilmadi**. Ehtimol: (a) serverda eski bundle; (b) result-view (`if (resultData)` 689-qator) yoki ichki render-funksiyalar; (c) `ProtectedRoute` loading o'tishi. **Lokal reproduksiya kerak** (dev rejimda to'liq xabar chiqadi) | Dev'da attempt 59 ni ochib aniq komponentni topish; fayl juda katta — bo'laklarga ajratish | M |
| 1.2 | `Failed to fetch` | Frontend same-origin (`VITE_API_URL` bo'sh) → bu odatda nginx 502/timeout yoki backend crash (CORS emas). Lokal kodda aniqlab bo'lmaydi — **prod nginx/web loglari kerak** | Loglarni ko'rish (ruxsat bilan); `lib/api.ts`da tarmoq xatosini ushlab, tushunarli xabar + "Qayta urinish" | M |
| 1.3 | Error Boundary | `ErrorBoundary.tsx` **mavjud** va `/english-exam` + `/take` ga ulangan, lekin Tailwind klasslarida (ishlamaydi) va `fallbackTitle` hardcode o'zbekcha | Stilni tokenlarga o'tkazish, i18n, "Qayta yuklash" tugmasi | S |
| 1.4 | Mehmonda "KR" | **Topildi:** `pages/Landing.tsx:494-495` — `user` yo'q bo'lsa ham avatar tugmasi `'KR'` bilan chiziladi (hardcode fallback). Qo'shimcha: `AuthContext` token bo'lmasa `SessionAuth.status()` orqali Django sessiyasidan qayta kiritadi | Mehmonga avatar o'rniga "Kirish" tugmasi; `'KR'` ni olib tashlash | S |

### 2-bosqich (rollar)
| # | Muammo | Sabab / fayl | Yechim | Hajm |
|---|---|---|---|---|
| 2.1 | Adminga "Tariflar va Obuna (PRO)" | `MobileProfileDrawer.tsx:358-376` va `MobileNavDrawer.tsx:315` — `isAdmin` tekshiruvisiz, matn ham hardcode | `!isAdmin` sharti + admin bo'limlari. Backend'da chek tasdiqlash bor (`webapi/views_billing.py:354`, `payments/services.py:266 approve_payment_receipt`); "PRO berish" va "ustoz limiti" API'lari aniq topilmadi — 2-bosqichda tekshirish | M |
| 2.2 | Desktop `Student/FREE`, mobil `#ID-51 Administrator` | Ikki xil kirish usuli (Google / Telegram / email) alohida `User` yaratgan bo'lishi ehtimoli yuqori; yoki desktop'da eski JWT/sessiya. **Prod bazada tekshirish kerak** (email/telegram_chat_id/google_id bo'yicha) | Faqat aniqlash va foydalanuvchiga xabar; birlashtirmaslik | S |
| 2.3 | Menyu markazlashmagan | 4 ta komponent (yuqorida) | `lib/navigation.ts` — rol → menyu konfiguratsiyasi | M |

### 3-bosqich (imtihon dvigateli)
| # | Muammo | Sabab / fayl | Yechim | Hajm |
|---|---|---|---|---|
| 3.1 | `Attempts left: 0` admin/ustozda | **Topildi:** `pages/TestDetail.tsx:129-131` — frontend rolni hisobga olmay `max_attempts - myAttempts` hisoblaydi va tugmani bloklaydi; backend esa admin/ustozni o'tkazadi | Frontendda rolni hisobga olish; ustoz uchun "qo'shimcha urinish/reset" endpoint (yangi model maydoni yoki `AttemptGrant`) | M |
| 3.2 | `Student access required.` | Bu matn faqat `accounts/permissions.py:45,64` (`IsStudent`, `IsStudentOrReadOnly`). Lokalda faqat `certificates/views.py:56` (my-certificates) ishlatadi; `tests/views.py` va `results/views.py`da import qilingan, lekin ishlatilmagan → **prod kodi lokaldan farq qilishi mumkin** | Preview rejimi: `TestAttempt.is_preview` (yangi maydon, default False — ma'lumotga zarar yo'q), statistika/reyting/vedomost querylarida `is_preview=False` filtri | L |
| 3.3 | Ingliz testida Ona tili mavzulari / `BMB: Fail` | **Topildi:** `components/TestAddictiveResults.tsx:90-145` — savol `topic` bo'lmasa, **savol indeksiga qarab soxta mavzu** beriladi (`idx<15 → 'Grammatika va Morfologiya'`) va savollar bo'lmasa foiz bilan **to'qib chiqariladi** (0.4/0.3/0.3). `isEnglish` aniqlashi (`:63`) xato ishlasa — Ona tili ro'yxati chiqadi. BMB yorlig'i: `pages/Results.tsx:320` | Mavzular va shkala backenddan (`ExamScoringProfile` / `exam_type`) kelsin; soxta taqsimotni o'chirish | L |
| 3.4 | Attestatsiya fani yo'q | `Test.subject` va `Profile.active_subject` choices'da `attestatsiya` yo'q | Yangi choice qo'shish (faqat choices — ma'lumot o'zgarmaydi) + attestatsiya testlarini data-migratsiya bilan belgilash (oldin ro'yxatni ko'rsatib) | M |

### 4-bosqich (UI/CSS)
| # | Muammo | Sabab / fayl | Hajm |
|---|---|---|---|
| 4.1 | Stil tizimi | 2-bo'limga qarang (Tailwind yo'q) | L |
| 4.2 | Referal karta | `components/ReferralCard.tsx` — Tailwind klasslari (ishlamaydi) | S |
| 4.3 | FeedbackModal | `components/FeedbackModal.tsx` — 104 Tailwind klass, ishlamaydi | M |
| 4.4 | Landing "Fikr bildirish" takror | `pages/Landing.tsx:2208, 2320, 2334` — **3 ta** tugma `setLandingFeedbackOpen(true)` | S |
| 4.5 | Dashboard header overlap | `index.css:260` `position: sticky` header; balandlik o'zgaruvchisi yo'q. Runtime'da tekshirish kerak | S–M |
| 4.6 | Onboarding kontrast | `components/OnboardingModal.tsx` (1021 qator) — inline ranglar; tema tokenlaridan foydalanmaydi | M |
| 4.7 | Sariq kartada oq matn | `pages/Landing.tsx` inline ranglar | S |
| 4.8 | Umumiy kontrast | Ko'p komponentlarda `isDark ? '#F1F5F9' : '#1E293B'` kabi qo'lda ranglar (masalan `MobileProfileDrawer.tsx:368`) | L |

### 5-bosqich (i18n / fan)
- Til va fan **allaqachon alohida state**: til `lms_lang` (`LangContext`), fan `lms_subject` + `Profile.active_subject` (`SubjectSwitcher.tsx`). Muammo UI'da bitta tugmada ko'rsatilishida — tugmani ajratish kerak. Fan ro'yxatida Attestatsiya yo'q (3.4).
- Hardcode matnlar eng ko'p (JSX ichidagi literal qatorlar, taxminiy): `TeacherGradebook` 51, `EnglishExamInterface` 50, `Landing` 47, `EnterpriseDashboard` 29, `Pricing` 25, `Groups` 21, `ScanOMR` 18, `PassingScoresModal` 16, `MobileNavDrawer` 16, `TeacherFinanceDashboard` 15, `PanelDashboard` 14, `Tests` 12. Shuningdek `MobileProfileDrawer` ("Tariflar va Obuna (PRO)", "Mening Sertifikatlarim"), `App.tsx` ("Yuklanmoqda…", ErrorBoundary sarlavhalari), `ProtectedRoute` ("Loading session…").
- `t('key', 'O'zbekcha fallback')` — 159 joy; kalit lug'atda bo'lmasa EN rejimda o'zbekcha chiqadi.
- Hero'dagi ortiqcha "with": `translations.json` `hero_h1_*_grad: "with AI"` + `hero_title_2: "prepare with AI"` birga render bo'lishi — Landing'da tekshirish. Hajm: L.

### 6-bosqich (soxta statistika) — **tasdiqlandi**
- `pages/Dashboard.tsx:604-610` "Keyingi Marra", "Tayyorgarlik darajasi: 72%" — hardcode.
- `pages/Dashboard.tsx:1270-1300` "So'nggi baholangan esselar" — qattiq yozilgan massiv (Band 7.5 / 7.0, CEFR C1…).
- `pages/Dashboard.tsx:1361-1443` "Path to Excellence", 72%, "Topshirildi (88% natija)".
- `components/TestAddictiveResults.tsx:120-145` — soxta mavzu taqsimoti.
- Kerak: `/api/dashboard/stats/` (yoki mavjud `Results.stats` ni kengaytirish) + empty state. Hajm: L.

### 7-bosqich (Telegram 1-klik)
- **Deep-link oqimi allaqachon bor:** backend `apps/notifications/telegram_auth.py:102-149` (`start` → `t.me/uz_essaygrader_bot?start=auth_<token>`, `status`, `login`, `expires_in: 600`), frontend `AuthModal.tsx:162`, `Login.tsx:208`, `lib/api.ts:1139-1148` (polling). Eski 6 xonali kod usuli ham saqlangan (`/telegram/auth/code/login/`).
- Foydalanuvchi ko'rayotgan "kontakt + 6 xonali kod" oqimi → ehtimol prod'da eski versiya yoki bot `/start auth_*` ni to'g'ri qayta ishlamaydi. Kerak: prod versiyasini va bot handlerini tekshirish; token muddati 600s → 300s. Hajm: M (noldan emas).

### 8-bosqich (CD konstruktor)
- Modellarning katta qismi mavjud (4-bo'lim). Kerak: `QuestionGroup` (umumiy instruksiya/audio/rasm), map-labeling koordinatalari, konstruktor UI. Hajm: XL.

---

## 6. Ro'yxatda yo'q, lekin topilgan jiddiy muammolar

1. **Tailwind umuman yo'q** (2-bo'lim) — eng katta yashirin UI muammosi.
2. **`center_admin` = to'liq platforma admini** (`accounts/access.py:16`, `lib/api.ts:236`). Markaz rahbari barcha to'lov/foydalanuvchilarni boshqara oladi. Tasdiqlash kerak.
3. **JWT tokenlar URL'da:** `AuthContext.tsx` `?access=...&refresh=...` qabul qiladi (OAuth redirect). URL server loglari, Referer, brauzer tarixida qoladi. Tavsiya: bir martalik `code` → POST bilan almashtirish. Hajm: M.
4. **Tokenlar `sessionStorage`da** (`lib/api.ts:20`), `storage` hodisasi orqali tablar o'rtasida sinxronlanadi. XSS bo'lsa o'g'irlanishi mumkin; `refresh` ni httpOnly cookie'ga o'tkazishni ko'rib chiqish kerak.
5. **Nginx 80/443 port to'qnashuvi xavfi:** `docker-compose.prod.yml:208-210` nginx host'da 80/443 ni band qiladi. Serverda `bestway` ham bor — qaysi biri haqiqiy reverse-proxy ekanini deploydan oldin **aniq bilish shart** (bestway'ga tegmaslik uchun).
6. **Dev compose portlari:** `docker-compose.yml` Postgres `5432` va Redis `6379` ni host'ga ochadi. Agar serverda shu fayl ishlatilsa — internetga ochiq baza. Faqat dev uchun ekanini tasdiqlash.
7. **Ulkan fayllar:** `lib/api.ts` 2532, `Landing.tsx` 2572, `TakeTest.tsx` 1769, `EnglishExamInterface.tsx` 1660, `Dashboard.tsx` 1452, `essays/services.py` 4400+, `notifications/bot/handlers.py` 8800+ qator. Xatoni topish va #310 kabi muammolar shu sababdan qiyin.
8. **Admin huquqi frontendda copy-paste** — `normalizeUser` ichida bir xil shart 5 marta; `ADMIN_UNLIMITED` faqat frontend tushunchasi. Backend bilan bir manbaga keltirish kerak.
9. **i18n bundle** — butun `translations.json` (3 til) bitta 302 kB chunk; til bo'yicha lazy-load qilish mumkin.
10. **`set-state-in-effect`** — ~70 ta lint ogohlantirishi; keraksiz qayta renderlar.
11. **Hujjatlar tartibsiz:** root'da `AUDIT_REPORT.md`, `AUDIT_REPORT_2026-09-12.md`, `PROGRESS.md` (229 kB). `FIX_PLAN.md` root'da, `docs/` emas (rejaning o'zi `docs/FIX_PLAN.md` deydi). `CLAUDE.md` va `FIX_PLAN.md` hali git'ga qo'shilmagan.
13. **Ingliz tili natijasida soxta ballar (1-bosqichda topildi, KRITIK):** `pages/tests/EnglishExamInterface.tsx:722-783` — backend ball bermasa `'Band 6.5'`, `'B2'` fallback, bo'limlar (Listening 7.0 / Reading 6.5 / Writing 6.5 / Speaking 7.0) esa to'liq hardcode. Lokal sinovda 0/77 to'g'ri javobga "Band 6.5, B2" va "muvaffaqiyatli topshirdi" sertifikati chiqdi. 3-bosqichda (fanga bog'liq natija) birinchi navbatda tuzatilishi kerak.
14. **Rejim yorlig'i:** `practice` rejimda boshlangan attempt sarlavhada "Strict Exam" deb ko'rsatildi — 3-bosqichda tekshirish.
12. **Lokal vs prod farqi ehtimoli:** "Student access required" va 6 xonali Telegram kodi lokal kodga mos kelmaydi → serverda qaysi commit/image ishlayotganini tekshirish 1-bosqichning birinchi qadami bo'lishi kerak.

---

## 7. Keyingi bosqich uchun tavsiya

1. Avval prod'dagi versiyani aniqlash (faqat o'qish: `docker ps`, image tag, `VERSION`) — ruxsat bilan.
2. 1-bosqich: 1.4 (KR) va 1.3 (ErrorBoundary) — tez yutuq; 1.1 uchun lokal reproduksiya.
3. Tailwind qarorini (2-bo'lim) 4-bosqichdan oldin qabul qilish — FeedbackModal/ReferralCard ishlari shunga bog'liq.
4. Foydalanuvchidan so'raladigan savollar: `center_admin` huquqlari; Tailwind (a)/(b); eski Telegram kodli usul qolsinmi; 2.2 dagi akkauntlar.

---

## 8. Foydalanuvchi qarorlari (2026-11-02)

| Savol | Qaror | Qaysi bosqichga ta'sir qiladi |
|---|---|---|
| `center_admin` huquqlari | **Faqat o'z markazi.** U platforma admini bo'lmaydi: faqat o'z `learning_center`idagi ustoz va o'quvchilarni boshqaradi. To'lovlar va butun panel faqat platforma adminida qoladi | 2-bosqich: `accounts/access.py` `is_platform_admin` dan `center_admin` chiqariladi, frontend `isPlatformAdmin` ham shunga moslanadi, markaz darajasidagi alohida ruxsat qo'shiladi |
| Tailwind | **Aralash yo'l.** `EnglishExamInterface` va `CefrExamComponents` uchun Tailwind v4 (`@tailwindcss/vite`) o'rnatiladi: ranglari `index.css` tokenlariga bog'lanadi, preflight o'chiriladi. FeedbackModal, ReferralCard, JoinGroup, ErrorBoundary, ScoreCardModal, TeacherFinance va TeacherVocab `index.css` klasslariga ko'chiriladi | 4-bosqich |
| Telegram 6 xonali kod | **Olib tashlansin.** Faqat deep-link orqali 1-klik qoladi | 7-bosqich: `/telegram/auth/code/login/` endpointi, frontenddagi kod kiritish UI va botdagi kod yuborish qismi olib tashlanadi |
| Server | **Faqat o'qish uchun ruxsat** berildi (`docker ps`, `docker logs`, image tag, nginx konfiguratsiyasini o'qish). Har buyruqdan oldin nima qilinishi aytiladi; `bestway` ga tegilmaydi | 1-bosqich: #310, `Failed to fetch`, versiya farqi va 80/443 portlarini tekshirish |
