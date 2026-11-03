# Grand Education — tuzatish rejasi

> Claude Code har bosqichni alohida bajaradi, tugatgach checkboxlarni `[x]` qiladi va bosqich oxiriga qisqa hisobot yozadi.
> Har bosqich uchun tartib: **o'rganish → reja (foydalanuvchiga ko'rsat) → tuzatish → build/test → commit → hisobot.**
> Bosqich tugagach TO'XTA va foydalanuvchidan keyingisiga ruxsat kut.

---

## 0-bosqich — Razvedka (hech narsani o'zgartirma)
- [x] Repo tuzilmasini o'rgan: backend app'lar, frontend `src/` tuzilmasi, routing, state management, API client, i18n tizimi, stil tizimi.
- [x] `docker-compose` fayllarini o'qi; lokal ishga tushirish yo'lini aniqla.
- [x] Tailwind holatini aniqla: o'rnatilganmi, versiyasi (v3 yoki v4), config, `content` yo'llari, `index.css` da direktivalar (`@tailwind ...` yoki `@import "tailwindcss"`), Vite plagini.
- [x] Rollar va ruxsatlar qanday ishlashini aniqla (User modeli, role/plan maydonlari, DRF permission klasslari).
- [x] Test/imtihon modellarini o'rgan: Test, Question, Attempt, subject maydoni, natija tahlili qanday hisoblanadi.
- [x] Quyidagi barcha muammolar uchun ehtimoliy sababni va tegishli fayllarni toping.
- [x] **Natija:** `docs/AUDIT.md` faylida qisqa hisobot — arxitektura, har muammo uchun sabab + fayl + taklif etilgan yechim + taxminiy hajm. Hisobotda men sanab o'tmagan, lekin topgan boshqa jiddiy muammolarni ham yoz.

---

## 1-bosqich — Kritik xatolar (ishlamay qolgan funksiyalar)
- [ ] **React error #310** (`/english-exam/59`, oq ekran). Bu odatda "Rendered more hooks than during the previous render" — hook'lar shartli `return` dan keyin chaqirilgan. Imtihon sahifasi va uning komponentlaridagi barcha hook'lar tartibini tekshir va tuzat.
- [x] **`Failed to fetch`** — qaysi so'rov ekanini aniqla (API URL, CORS, HTTPS/mixed content, nginx proxy, backend xatosi). Sababini tuzat va frontendda tushunarli xato xabari + qayta urinish chiqar.
- [x] Imtihon sahifasiga **Error Boundary** qo'sh: oq ekran o'rniga tushunarli xabar.
- [x] **Login qilmagan mehmonda "KR" chiqishi** — localStorage/cache'da eski user qolganmi, mock/fallback user bormi, logout state to'g'ri tozalanadimi — tekshir va tuzat. Mehmonga faqat "Kirish" tugmasi ko'rinsin.

## 2-bosqich — Rollar va admin huquqlari
- [ ] `ADMIN_UNLIMITED` adminga **"Tariflar va Obuna (PRO)"** menyusi ko'rinmasin. O'rniga admin bo'limlari: to'lov cheklarini tekshirish, o'quvchiga PRO berish, ustozlarga limit qo'yish (mavjud bo'lsa ulash, bo'lmasa AUDIT'da belgilab, alohida bosqichga qoldir).
- [ ] (kod tahlili 2026-11-03 da qilindi, prod bazani o'qish deploy bosqichida) Kompyuterda `komiljon Roziyev` profili `Student / FREE` bo'lib qolgan, mobilda esa `#ID-51 Administrator`. Bular bitta akkauntmi yoki ikki xil akkauntmi — aniqla. Agar bitta bo'lsa — rol sinxronizatsiyasini tuzat; ikki xil bo'lsa — foydalanuvchiga xabar ber, o'zing birlashtirma.
- [ ] Rolga asoslangan menyu/marshrutlar markazlashgan bo'lsin (bitta joyda aniqlansin).

## 3-bosqich — Imtihon dvigateli
- [x] **Urinishlar limiti:** `Record Mock – Test 1` da `Attempts left: 0`. Admin va ustozlar uchun limit qo'llanmasin. Ustoz/admin o'quvchiga qo'shimcha urinish bera olishi (yoki urinishni reset qilishi) mumkin bo'lsin.
- [x] **`Student access required.`** — admin va ustoz testni **"Preview / Sinov rejimi"** da ochib, to'liq o'tib ko'ra olsin. Preview natijalari o'quvchi statistikasi, reyting va vedomostga tushmasin.
- [x] **Ingliz tili natijasidagi soxta Band/CEFR qiymatlari** (`EnglishExamInterface.tsx:722-783`, AUDIT 6.13) — birinchi navbatda.
- [ ] **Fanga bog'liq natija tahlili:** ingliz tili testida "Grammatika va Morfologiya", "Mumtoz va Zamonaviy Adabiyot" kabi Ona tili mavzulari va `BMB: Fail`, `Milliy Sertifikatning rasmiy bali emas` yorliqlari chiqmoqda. Natija tahlili, mavzu kategoriyalari, ball shkalasi va yorliqlar testning `subject`/imtihon turiga qarab tanlansin:
  - Ingliz tili CEFR: Listening / Reading / (Writing / Speaking) bo'limlari va CEFR darajasi (B1/B2/C1).
  - IELTS: bo'limlar bo'yicha band score.
  - Ona tili: hozirgi BMB logikasi saqlansin.
  - Attestatsiya: o'z shkalasi.
- [ ] Hardcode qilingan mavzu ro'yxatlarini topib, fan/test konfiguratsiyasiga ko'chir.

## 4-bosqich — UI/CSS tuzatishlari
- [ ] **Stil tizimini hal qil.** 0-bosqich natijasiga ko'ra ikki yo'ldan birini tanla va foydalanuvchiga tushuntir:
  - (a) Tailwind'ni to'g'ri sozlash (versiyaga mos config/plagin/direktivalar, `content` yo'llari) — agar loyihada Tailwind ko'p ishlatilgan bo'lsa;
  - (b) yoki Tailwind klasslari ishlatilgan yangi komponentlarni mavjud dizayn tizimiga (index.css o'zgaruvchilari) ko'chirish — agar asosiy stil shu bo'lsa.
  Ikkala tizim aralash, chalkash qolmasin.
- [ ] **Referal karta** (Dashboard va Profile): chiroyli input-group — havola, "Nusxalash" (bosilganda "Nusxalandi ✓" feedback), "Ulashish" (Web Share API, bo'lmasa Telegram share link). Mobilda ham chiroyli.
- [ ] **FeedbackModal.tsx:** yulduzcha reyting (hover/active holatlar), kategoriya chiplari (tanlangani ajralib tursin), textarea, "Bekor qilish" (ikkinchi darajali) va "Yuborish" (asosiy) tugmalari. Kunduzgi/tungi rejimda.
- [ ] **Landing sahifadagi "Fikr bildirish" tugmasi** ikki marta takrorlangan — bittasini olib tashla, qolganini dizaynga moslashtir.
- [ ] **Dashboard header overlap:** sticky/fixed header kontentni yopmoqda. Header balandligini CSS o'zgaruvchisiga chiqar va kontentga to'g'ri `padding-top`/`scroll-margin` ber. Mobil va desktopda tekshir.
- [ ] **Smart Onboarding modali:** to'q fonda (`#0F172A`) qora matn ko'rinmayapti. Matn ranglarini tema tokenlaridan olsin; kontrast WCAG AA darajasida bo'lsin.
- [ ] **Mobil landing, tungi rejim:** "AI Esse — BMB rasmiy tahlil" sariq kartasida oq sarlavha ko'rinmayapti. Rangli kartalarda matn rangini fonga qarab belgilash.
- [ ] Butun loyiha bo'yicha "to'q fonda to'q matn / och fonda och matn" holatlarini qidirib, tema tokenlari bilan tuzat.

## 5-bosqich — i18n va fan (subject) ajratish
- [ ] Tepadagi `UZ Ona tili / GB English` tugmasini **ikkiga ajrat:**
  - Interfeys tili tanlagich (UZ / EN) — faqat i18n.
  - Fan tanlagich (Ona tili / Ingliz tili / Attestatsiya) — faqat kontent.
  Ikkalasi alohida saqlansin (user profile + localStorage).
- [ ] Qolib ketgan o'zbekcha matnlarni i18n'ga ko'chir va inglizcha tarjima qo'sh:
  - Landing: hero tavsifi, "O'quvchilarimiz va Ustozlar Fikrlari", "+ O'rnatish", "Yangi", pastki mobil menyu (Bosh, AI Esse, Testlar, Arena, Profil).
  - Hero sarlavhadagi ortiqcha "with" ("...[with AI Analysis] with") — tuzat.
  - Mobil profil: "Mening Profilim", "Xush kelibsiz!", "1-klikda kirish", "Ro'yxatdan o'tish", "Til:", "Rejim: Kunduzgi".
  - Profile: "Telegram Hisobini Bog'lash"; OMR Skaner: "Titul varaqa (Answer Sheet) avto-skaneri".
- [ ] Dashboard "My Tests" blokidagi "...for Native Language & Literature" matni tanlangan fanga qarab dinamik bo'lsin.
- [ ] Komponentlarda qolgan hardcoded UI matnlarni qidirib top (grep) va ro'yxatini AUDIT'ga yoz; asosiy sahifalardagilarni ko'chir.

## 6-bosqich — Soxta statistikani olib tashlash
- [ ] Dashboard'dagi "Tayyorgarlik darajasi: 72%", "Boshlang'ich Diagnostika Topshirildi (88% natija)", "Path to Excellence", "Keyingi Marra", "So'nggi baholangan esselar" (56/60 A+, Band 7.5) — barchasini haqiqiy API ma'lumotiga ula.
- [ ] Kerak bo'lsa backendda dashboard statistikasi uchun endpoint qo'sh/to'g'irla.
- [ ] Ma'lumot bo'lmasa — chiroyli empty state va keyingi qadamga chaqiruv ("Birinchi diagnostik testni topshiring").
- [ ] Butun frontend bo'yicha boshqa mock/demo ma'lumotlarni qidir.

## 7-bosqich — Telegram 1-klik login
- [ ] Hozir: bot kontakt + ism so'rab, 6 xonali kod beradi, saytga qo'lda kiritish kerak. Kerakli oqim (deep link):
  1. Saytda "Telegram orqali kirish" → backend bir martalik, qisqa muddatli `login_token` yaratadi.
  2. Foydalanuvchi `t.me/<bot>?start=<login_token>` ga yo'naltiriladi.
  3. Bot `/start <token>` ni oladi; yangi foydalanuvchi bo'lsa kontakt so'raydi (bir marta), so'ng backendda tokenni tasdiqlaydi.
  4. Sayt tokenni polling (yoki WebSocket) orqali kuzatadi va tasdiqlangach avtomatik kiradi.
- [ ] Token: bir martalik, 5 daqiqa amal qiladi, ishlatilgach o'chadi. Eski kodli usulni zaxira sifatida qoldirish yoki olib tashlash haqida foydalanuvchidan so'ra.

## 8-bosqich — CD-format test konstruktori (eng katta vazifa)
Maqsad: `RECORD MOCK – TEST 1` kabi testlar kodda statik emas, admin/ustoz panelidan kiritiladigan Computer-Delivered formatda bo'lsin.
- [x] Avval **ma'lumot modelini loyihalash** va foydalanuvchiga ko'rsatish (kod yozishdan oldin): Test → Section (Listening/Reading/...) → Part → QuestionGroup (umumiy instruksiya, audio, matn, rasm) → Question.
- [x] Qo'llab-quvvatlanadigan savol turlari:
  - Multiple Choice (bitta / bir nechta javob)
  - Inline Gap-fill (matn ichidagi bo'sh joylar, so'z limiti)
  - Map / Diagram Labeling (rasm + belgilar, masalan Community Centre xaritasi)
  - Heading Matching
  - Statements / Information Matching (A–J)
  - True / False / Not Given (va Yes / No / Not Given)
- [ ] Listening uchun audio yuklash va pleyer (imtihon rejimida bir marta eshitish sozlamasi).
- [ ] Ustoz/admin uchun konstruktor UI: qism qo'shish, savol turi tanlash, javob kalitlari, preview.
- [x] Imtihon dvigateli shu tuzilmadan dinamik render qilsin; avtomatik tekshirish (gap-fill'da katta-kichik harf va bo'sh joylarni normallashtirish, muqobil javoblar).
- [x] Mavjud statik testni yangi formatga ko'chirish uchun migratsiya/skript.
- [ ] Bu bosqichni kichik qismlarga bo'lib bajar, har qismdan keyin to'xtab ko'rsat.

## 9-bosqich — Deploy (faqat ruxsat bilan)
- [x] Deploydan oldin: build muvaffaqiyatli, migratsiyalar ro'yxati, bazaning zaxira nusxasi (`pg_dump`) olinishi.
- [x] Faqat `/opt/lms` konteynerlarini yangila. `bestway` ga tegma.
- [x] Deploydan keyin asosiy sahifalarni tekshirish ro'yxati: landing, login, dashboard, test boshlash/tugatish, esse, admin panel — mobil va desktop.

---

## Hisobotlar
(Har bosqich oxirida shu yerga 3–5 qatorlik hisobot yoziladi: nima qilindi, qaysi fayllar, ochiq qolgan masalalar.)

**0-bosqich (2026-11-02):** Razvedka bajarildi, kod o'zgartirilmadi. Natija: `docs/AUDIT.md`. Asosiy topilmalar: Tailwind o'rnatilmagan (8+ faylda klasslar ishlamaydi), "KR" `Landing.tsx:495` da hardcode, `TestDetail.tsx` admin/ustoz urinish limitini noto'g'ri ko'rsatadi, `TestAddictiveResults.tsx` soxta mavzu tahlili, Dashboard soxta statistikasi. Ochiq: #310 va `Failed to fetch` uchun prod loglari/reproduksiya kerak; `center_admin` huquqlari tasdiqlansin.

**1-bosqich, serversiz qism (2026-11-02):**
- Bajarildi: mehmonga "KR" o'rniga "Kirish" tugmasi (`Landing.tsx`); ErrorBoundary tema tokenlari va i18n bilan qayta yozildi, "Qayta yuklash" tugmasi qo'shildi; `lib/api.ts` tarmoq xatosi (`Failed to fetch`) va 502/503/504 javoblarida tushunarli xabar beradi, GET so'rovlar bir marta qayta yuboriladi; imtihon sahifasining xato ekraniga "Qayta urinish" qo'shildi; `TestDetail.tsx` ustoz va admin uchun urinishlar limitini endi bloklamaydi (bu 3-bosqichdan oldinroq bajarildi).
- #310: lokalda test 12 (77 savol) yuklandi, hamma savollar ko'rib chiqildi, javob berildi va test topshirildi — xato chiqmadi. Prod loglari va prod versiyasi kerak.
- Ochiq: `Failed to fetch` ning asl sababi (server), #310 (server). Yangi topilma: ingliz tili natijasida soxta Band/CEFR qiymatlari (AUDIT 6.13).

**Soxta Band/CEFR tuzatildi (2026-11-02):** ingliz tili natija sahifasi (`EnglishExamInterface.tsx`) endi qiymatlarni `certificate-card` API'dan oladi; natija kartasi faqat `is_valid` (B1+) bo'lsa chiqadi. Tasdiqlab bo'lmaydigan ID/QR havolasi olib tashlandi. Backend `score_converter.py` 40 ta savolni standart deb olmaydi, testdagi haqiqiy savollar sonidan foydalanadi (yangi test qo'shildi). Ochiq: natija kartasi bazada saqlanmaydi (`apps/certificates` bilan bog'lash kerak); IELTS va CEFR yorliqlarini fanga/imtihon turiga qarab ajratish 3-bosqichda.

**CEFR Multi-level ball hisoblash (2026-11-02, `feat/cefr-multilevel-mock`):** shkala `apps/tests/scales/cefr_multilevel.json` da, hisoblash `apps/tests/cefr_multilevel.py` da. Natija sahifasida IELTS band yo'q, "taxminiy natija" ogohlantirishi bor. `recalc_cefr_scores --dry-run` buyrug'i qo'shildi. Oldindan yiqilib turgan 12 ta backend testi `main` da ham yiqiladi (rollar va tarjimalar) — alohida tuzatish kerak.
**Record Mock – Test 1:** 70 ta L/R kalit PDF bilan mos. Farqlar: Speaking 4 ta kalitsiz `SHORT_ANSWER` (PDF bo'yicha 10 ta prompt), Listening vaqti 40 daq (45 bo'lishi kerak), Writing 45 daq (60 bo'lishi kerak), rasm va audio yo'q. Model loyihasi: `docs/CD_FORMAT_MODEL.md` — tasdiq kutilmoqda.

**CD-format va Record Mock (2026-11-02, `feat/cefr-multilevel-mock`):** `ExamPart`/`QuestionGroup` modellari (migratsiya 0016, faqat qo'shimcha), `import_cd_mock` buyrug'i va `fixtures/mocks/record_mock_1`. 70 kalit PDF bilan avtomatik solishtiriladi. Yangi `CdExamInterface`. Ustoz va admin urinishlari preview rejimida: statistika, vedomost va reytingga tushmaydi. Brauzerda 0/15/35 holatlari mobil+desktop va kunduzgi+tungi rejimda tekshirildi. Ochiq: audio fayllar, Speaking baholash (hozir CBT'da baholanmaydi), eski test #12 (CEFR-RECORD-1) ni o'chirmasdan arxivlash qarori.

**Deploy (2026-11-03):** `7ade8dc` production'da. Zaxira: `~/backups/lms_predeploy_20261103_021741.sql.gz`. Migratsiya 0016 qo'llandi, Record Mock = Test #14. `recalc_cefr_scores` dry-run: test #12 dagi 2 ta bo'sh urinish (#58, #59), qo'llanmadi.
**Failed to fetch sababi:** nginx'dagi 502'lar 18-oktabr 14:00 va 21-oktabr 15:00 dagi web uzilishlariga to'g'ri keladi (save-answer 78 marta). Hozir takrorlanmayapti; frontend endi tushunarli xabar beradi. Esse autosave 500 xatosi (shablon yo'q) topildi va tuzatildi — PR #114.

**Kritik guruh A1–A5 (2026-11-03, `fix/site-audit-critical`):**
- A1 OMR: `google-genai` o'rnatilmagani uchun har skan soxta "local CV" ga tushib, bir xil rasmda hamma javob "A" bo'lardi. Endi: rasm tekshiruvi (format, 8 MB, o'lcham, nisbat, qog'oz ulushi) + vision "javoblar varaqasi" tasdig'i, har savol aniq/bir nechta/bo'sh/o'qilmadi, >20% o'qilmasa natija yo'q, o'quvchi tasdiqlaydi, baholash onlayn pipeline orqali, XP yo'q, rate limit. Bot OMR'ni saytga yo'naltiradi. Ochiq: burchak markerli rasmiy varaq shabloni yo'q.
- A2 CEFR: 81 = 70 L/R + 3 Writing + 8 Speaking; 73 = 70 + 3 writing bali. Endi CEFR'da 70 savol, 0–75 shkala, "B1 uchun o'rtacha kamida 38/75", "Urinishlar: cheksiz", raqamlar L1–R35 (position 1001 emas), `/results/:id` da CefrResultSummary. backslash'li "O'tish bali" xatosi `Tests.tsx` dagi JSX matnidan edi.
- A3: admin `SUPERADMIN_TELEGRAM_IDS` dagi Telegram ID ga avtomatik beriladi; Google/email bilan kirish alohida student akkaunt yaratadi; botdagi "Men o'quvchiman" adminni ham student qiladi. Ustoz FREE kvotaga tushardi — tuzatildi. Preview urinishlarga XP berilmaydi. Prod bazani o'qish — deploy bosqichida.
- A4: modal fanga mos, Rasch/sertifikat va'dasi yo'q, narxlar `PLAN_*_PRICE` dan (7 000 / 15 000 / 27 000). Bepul sinov: Reading Part 1, bir marta, preview (migratsiya 0017).
- A5: test #12 arxivlandi (migratsiya 0018, natijalar saqlanadi), asossiz da'volar olib tashlandi; platformadagi qolgan da'volar ro'yxati PR tavsifida.
