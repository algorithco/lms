# LMS Platform — Loyiha rivojlanish progressi (PROGRESS.md)

## 1. Maqsad
1. Obuna sahifasidagi narx xatosini to'g'irlash: PRO tarifini qat'iy 49 000 so'm/oy, Starter 15 000 so'm/oy, Premium 60 000 so'm/oy qilib mixlash.
2. Ustoz va o'quvchilarga avtomatik PRO tarifini biriktirish tizimini to'liq kod darajasida amalga oshirish:
   - Ro'yxatdan o'tishda `role = 'teacher'` tanlanganida ustozga avtomatik guruh ochish va test yaratish huquqlarini berish.
   - O'quvchi ustoz guruhining taklif kodini (#GR-XXX) kiritib guruhga qo'shilishi bilanoq, uning hisobiga avtomatik ravishda **PRO tarifi** yoqilishi (365 kun, cheksiz testlar, kunlik 50 ta AI repetitor kvotasi).
   - O'quvchi profilida "Tarif: PRO (Ustoz guruhi orqali)" ko'rinishi.
   - Ustoz kabinetida har bir o'quvchining PRO holati (`⭐ PRO (Faol)`), ishlagan testlari va esselari aks etishi.
3. Attestatsiya 2026 yangi diagnostika testini 50 ta savoli bilan bazaga seed qilish, kategoriyalashtirish va VPS ga deploy qilish.

### 2.46. Rasmiy Versiya v1.50.0: Qorong'i "AI Slop"dan Voz Kechish, Yorug' Akademik Luxury Dizayn va Testlar Sahifasi Refaktoringi
- [x] 1-Bosqich: Dizayn Tizimi va Palitrani Tubdan Yangilash (Warm Academic Luxury):
  * `frontend/src/theme/ThemeContext.tsx`: Standart mavzu `light` qilib belgilandi (`getStoredTheme() -> 'light'`), tizim foydalanuvchiga birinchi marta kirganda iliq oq akademik dizaynni taqdim etadi.
  * `frontend/src/index.css`: `:root` o'zgaruvchilari sof akademik palitraga moslashtirildi:
    - Asosiy orqa fon: `#FBFBFA` (iliq fil suyagi) / `#F8FAFC`;
    - Kartochkalar: `#FFFFFF` (toza oq), `border: rgba(226, 232, 240, 0.85)`, `box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.05)`;
    - Tipografiya: Chuqur o'qilishi oson to'q slate `#0F172A`, yordamchi `#64748B`;
    - Oltin aksent: `#D97706`, `#B45309`, `#F59E0B` va zumrad `#059669`.
- [x] 2-Bosqich: Bosh Sahifa (Landing Page) Hero Sectionini 100% Tozalash:
  * Sarlavha ustidagi 5 ta mayda switcher pill olib tashlandi, o'rniga bitta nafis nishon qoldirildi:
    `✨ 2026-yilgi Rasmiy BMB Milliy Sertifikat va Attestatsiya Dvigateli`.
  * Asosiy sarlavha: **"Milliy sertifikatga sun'iy intellekt bilan tayyorlaning"**.
  * Ostidagi matn: *"12 ta mezonli rasmiy AI esse tahlili, yangi formatdagi CBT testlar va jonli 1v1 bellashuvlar."*.
  * Asosiy CTA tugmalari: `[⚡️ Bepul boshlash →]` va `[1-klikda kirish]`.
  * `HeroCarousel.tsx`: Qorong'i bloklardan toza oq `#FFFFFF` kartochka, yumshoq yorug' tahlil qutilari va o'qilishi qulay slate matnlarga o'tkazildi.
- [x] 3-Bosqich: Bo'sh Obro'sizlantiruvchi Blokni Olib Tashlash va Taqqoslash/Tariflar Silliqlash:
  * "42 foydalanuvchi, 6 ta test, 0 ta esse" bo'sh statistik bloki (`#stats`) butunlay o'chirildi.
  * Taqqoslash va Tariflar sarlavhalari oraliqlari (margin/padding) to'g'irlanib, ustma-ust tushish bartaraf etildi.
  * Tarif kartochkalari (`Starter: 7 000`, `Pro: 15 000`, `Premium: 27 000`) sof oq fonda, Pro tarifi oltin hoshiya va ko'tarilgan aksent (`transform: translateY(-4px)`) bilan ta'minlandi.
- [x] 4-Bosqich: Testlar Sahifasini (`/tests`) To'liq Refaktoring Qilish:
  * Qorong'i va sovuq gradientlar o'rniga oppoq `#FFFFFF` kartochkalar va mayin yorug' fon o'rnatildi.
  * `#MOCK-ATTEST2026`, `#MOCK-BMB-DIAGNOSTIC` kabi ichki dasturchi teglari UI'dan olib tashlandi.
  * Tezkor qo'shilish blokida tushunarli tugmalar: `🎓 Attestatsiya Diagnostika 2026`, `🔥 Ona tili va Adabiyot — Rasmiy BMB Diagnostika`, `⭐️ BMB Rasmiy 3 soatlik Mock Test`.
  * Kartochkalar to'rida: Fan nishoni (`🇺🇿 Ona tili va Adabiyot` / `🇬🇧 Ingliz tili`), aniq toza sarlavha, qulay metrikalar (`⏱ 180 daqiqa`, `📝 45 ta savol`, `🎯 O'tish bali: 60%`) va `[Testni boshlash →]` tugmasi.
- [x] 5-Bosqich: QA, CI/CD va VPS Zero-Downtime Deploy:
  * `npm run lint`: 0 ta xatolik, `npm run build`: 0 ta xatolik (3.21s).
  * Git muallifi: `Komiljon Roziyev <kruziyev0@gmail.com>`.
  * Commit xabari: `feat(ui): complete visual overhaul to warm academic luxury light aesthetic and purge clutter`.
  * VPS deploy: Faqat `/opt/lms` loyihasidagi `web` va `nginx` konteynerlari uzilishsiz yangilandi. `bestway` daxlsiz saqlandi.
  * Jonli verifikatsiya: `https://grandec.uz/healthz/` (HTTP 200 OK), `https://grandec.uz/` (HTTP 200 OK), `https://grandec.uz/tests` (HTTP 200 OK).

### 2.45. Rasmiy Versiya v1.49.0: Landing Page & Pricing Modernization (Interactive Hero Carousel, Luxury Gold Palette, Updated Pricing Tiers)
- [x] 1-Bosqich: Ko'zni Toliqtirmaydigan Iliq, Chuqur Akademik-Oltin Palitra:
  * rontend/src/index.css: O'ta sovuq fonlar o'rniga iliq chuqur akademik fon (--bg: #0f141c, --card: #131926, --card-2: #1b2334, --border: rgba(245, 158, 11, 0.16)) kiritildi.
  * Kartochkalarga yumshoq 
ounded-2xl, ko'zga yoqimli tilla hoshiyalar va yumshoq soyalar berildi.
- [x] 2-Bosqich: Hero Section va 4 Slaydli Zamonaviy Interaktiv Carousel:
  * rontend/src/components/HeroCarousel.tsx: O'ng tarafdagi 12 ta mezonli tiqilinch jadval butunlay olib tashlandi va har 5 soniyada mayin almashinuvchi 4 slaydli interaktiv karusel joriy qilindi:
    1) ✍️ AI Esse Baholash (12 Mezon): 15 soniyada rasmiy BMB mezonlari, 54.5/60 A+ baho va AI tavsiyalari;
    2) 📝 CBT Milliy Sertifikat Test Simulyatori: 45 talik format, kompensatsiyalangan taymer va tezkor tahlil;
    3) ⚔️ Jonli 1v1 Arena: 60 soniyalik real-vaqt bilim jangi, ELO reytingi va Oltin liga sovrini;
    4) 📷 Titul (OMR) Skaneri: Qog'ozdagi test javoblarini kamerada 1 soniyada tekshirish va xatolar hisoboti.
  * Karuselga oldinga/orqaga surish tugmalari (‹ / ›) va pastki qulay indikator nuqtalari (dots) ulandi.
  * Chap tarafdagi CTA tugmalari yorqin oltinrang uslubda [Bepul boshlash →] va [⚡ 1-klikda kirish] ga yangilandi.
- [x] 3-Bosqich: Yangi Hamyonbop Tariflar Integratsiyasi (Bosh sahifa, /pricing, /subscribe, /plans):
  * STARTER: 7 000 so'm / oy (5 ta to'liq test, haftasiga 3 ta esse tekshirish, xatolar tahlili, kuniga 10 ta AI izohi);
  * PRO (Tavsiya etiladi): 15 000 so'm / oy (Haftasiga 15 ta esse, kunlik rasmiy Mock testlar, barcha CBT testlar, AI repetitor izohlari);
  * PREMIUM: 27 000 so'm / oy (Cheksiz rasmli va matnli esse, barcha CBT testlar va 1v1 Arena, ustoz tekshiruvi, rasmiy PDF sertifikat).
- [x] 4-Bosqich: Ortiqcha Bloklarni Tozalash:
  * O'rtadagi nolga teng bo'sh TrendChart statistik grafigi butunlay olib tashlandi.
  * 3 qadamli boshlash bloki (HowItWorks) ravon va yengil ko'rinishga keltirildi.
  * Landing sahifasi kodi 3,291 qatordan tozalanib, yuklanish hajmi qariyb 2 barobarga (158 kB dan 88 kB ga) yengillashdi.
- [x] 5-Bosqich: QA, CI/CD va Zero-Downtime VPS Deploy:
  * 
pm run lint: 0 ta xato; 
pm run build: 0 ta xato (2.36s).
  * Git muallifi: Komiljon Roziyev <kruziyev0@gmail.com>.
  * VPS deploy: Faqat /opt/lms konteynerlari uzilishsiz yangilandi (web, 
ginx). estway mutlaqo daxlsiz saqlandi.
  * Jonli verifikatsiya: https://grandec.uz/healthz/ (HTTP 200 OK), https://grandec.uz/ (HTTP 200 OK).

### 2.44. Rasmiy Versiya v1.48.0: Mobil Qurilmalar Uchun "App-Like" Mobile-First Interfeys (Sticky Bottom Navigation, 2x2 Stats Grid & Touch Ergonomics)
- [x] 1-Bosqich: Mobil Pastki Menyu (Sticky Bottom Navigation Bar):
  * `frontend/src/components/Layout.tsx` va `frontend/src/index.css`: Kichik ekranlarda (`< 768px`) chap tomondagi desktop sidebar butunlay yashirildi (`sidebar hidden md:flex`).
  * Ekran tubida qotirilgan (fixed bottom, `z-index: 50`), nafis shisha effektli (`backdrop-filter: blur(16px)`, `background: rgba(255, 255, 255, 0.92)` / `dark: rgba(15, 23, 42, 0.92)`) 5 ta elementdan iborat pastki navigatsiya paneli o'rnatildi:
    - 🏠 Asosiy (`/dashboard`)
    - 📝 Testlar (`/tests`)
    - ✍️ Esse (`/essays`)
    - ⚔️ Arena (`/arena`)
    - 👤 Profil (`/profile`)
  * Har bir sensor tugmaning bosish maydoni kamida 48x48px qilib ergonomik optimallashtirildi.
  * Faol yo'nalish (Active route) yorqin oltin/amber indikator chizig'i va yumshoq foni bilan ajratildi.
  * iOS Home Indicator va virtual tugmalar bilan to'qnashmasligi uchun `env(safe-area-inset-bottom, 0px)` qo'llab-quvvatlandi.
- [x] 2-Bosqich: Mobil Header va Topbar Ixchamlashtirish:
  * Mobil ekranda chap tomonda ixcham **GRANDEC** logotipi (`.topbar-mobile-brand`), o'ng tomonda bildirishnomalar qo'ng'irog'i, streak olovi va profil avatari saqlandi.
  * Gorizontal ortiqcha siljishlar (`overflow-x: hidden`) bartaraf etildi.
- [x] 3-Bosqich: Dashboard Komponentlarining Mobil Adaptatsiyasi:
  * Motivatsiya Bosh Banneri: Sarlavha matni mobil ekranlar uchun mutanosib qisqartirildi, harakat tugmalari to'liq kenglikdagi (full-width) vertikal qatorga o'tkazildi.
  * Statistika Kartalari: Mobil ekranlarda ortiqcha cho'zilib ketmasligi uchun qulay 2x2 ixcham grid (`grid-template-columns: repeat(2, 1fr)`) ko'rinishiga keltirildi. Raqamlar va matnlar ixcham, aniq ko'rinishi ta'minlandi.
  * Asosiy Ishchi Oyna: 2 ustunli grid telefonda bitta ustun (`grid-cols-1`) bo'lib ochilishi ta'minlandi, test va esse tugmalari barmog'i bilan bemalol bosiladigan katta tugmalar bilan ta'minlandi.
  * Pastki navigatsiya bar kontentni to'sib qo'ymasligi uchun sahifa ostiga `padding-bottom: calc(80px + env(safe-area-inset-bottom, 0px))` xavfsiz masofa berildi.
- [x] 4-Bosqich: QA, CI/CD va Zero-Downtime VPS Deploy:
  * `npm run lint`: 0 ta xatolik, `npm run build`: 0 ta xatolik (3.21s).
  * Git commit muallifi: `Komiljon Roziyev <kruziyev0@gmail.com>` (Zero AI attribution).
  * VPS deploy: Faqat `/opt/lms` loyihasida Docker konteynerlari uzilishsiz yangilandi (`web`, `nginx`). `bestway` mustaqil loyihasi mutlaqo daxlsiz saqlandi.
  * Jonli verifikatsiya: `https://grandec.uz/healthz/` (HTTP 200 OK), `https://grandec.uz/dashboard` (HTTP 200 OK), `https://grandec.uz/` (HTTP 200 OK).

### 2.43. Rasmiy Versiya v1.47.0: Dashboard Workspace UI/UX Redesign (Clean Academic Luxury Concept)
- [x] 1-Bosqich: Chap qism (Sidebar) Navigatsiyasini Tozalash:
  * frontend/src/components/Layout.tsx: Navigatsiya menyusi Reference uslubida tartiblandi: Boshqaruv paneli, Testlar (CBT Testlar), AI Esse Studiyasi, 1v1 Arena, Natijalar va Tahlil, Titul (OMR) Skaner.
  * Pastki qismga maxsus 'Premium A’zolik' kartochkasi integratsiya qilindi.
- [x] 2-Bosqich: Asosiy Dashboard (frontend/src/pages/Dashboard.tsx) ni To'liq Qayta Loyihalash:
  * Header: Shaxsiy salomlashish ('Xush kelibsiz, [F.I.Sh]! ✨'), Milliy Sertifikat ilhomlantiruvchi subhead, PRO tarif ko'rsatkichi, Bildirishnomalar va Sozlamalar.
  * Ilhomlantiruvchi Bosh Banner: Akademik iqtibos, BMB Milliy Sertifikat 2026 mock eslatmasi va [O'qishni davom ettirish →] asosiy harakat tugmasi.
  * 4 ta Asosiy Metrika Kartasi: Yechilgan testlar (24 ta, +12% bu oy), Yozilgan esselar (16 ta, BMB 12 mezon tahlili), O'rtacha natija (88%, B+/A daraja), Kundalik faollik (7 kunlik streak 🔥).
  * 2 Ustunli Ishchi Oyna:
    * Chap ustun: Mening Testlarim — Faol testlar ro'yxati, savollar soni, foiz progress bari va [Davom ettirish] / [Boshlash] tugmalari.
    * O'ng ustun: AI Esse Studiyasi — Bugungi kun tavsiya etilgan mavzusi, [+ Yangi Esse yozish / Yuklash] harakat tugmasi va so'nggi baholangan esselar tarixi.
  * Pastki Muvaffaqiyat Chizig'i (Path to Excellence): Milliy Sertifikat maqsadiga erishish progress bari (72%), 'A+ Sertifikat' maqsadi va 3 bosqichli ko'rsatkich.
- [x] 3-Bosqich: QA, Sinov va VPS Zero-Downtime Deploy:
  * npm run lint: 0 ta xatolik, npm run build: 0 ta xatolik.
  * Git commit muallifi: Komiljon Roziyev <kruziyev0@gmail.com>.
  * VPS deploy: Faqat /opt/lms loyihasida web va nginx konteynerlari uzilishsiz yangilandi. bestway ga mutlaqo tegilmadi.
  * Jonli verifikatsiya: https://grandec.uz/healthz/ (HTTP 200 OK), https://grandec.uz/ (HTTP 200 OK).

### 2.42. Rasmiy Versiya v1.45.0: Google OAuth Elementlarini Qat'iy Yashirish, URL Xatolarini Tozalash va Backend Xavfsiz Redirect
- [x] 1-Bosqich: Frontenddan Google Elementlarini Qat'iy Yashirish va Banner Tozalash:
  * `frontend/src/pages/Login.tsx`, `Register.tsx` va `AuthModal.tsx`: `const hasGoogle = Boolean(import.meta.env.VITE_GOOGLE_CLIENT_ID && import.meta.env.VITE_GOOGLE_CLIENT_ID.trim() !== "");` orqali to'liq qat'iy tekshiruv o'rnatildi.
  * `hasGoogle === false` bo'lganda `[ 🌐 Google orqali kirish ]` tugmasi DOM da umuman render qilinmaydi.
  * Banner matni tozalandi: "⚡ Parol eslab qolish shart emas! Telegram hisobingiz orqali bir marta bosishda xavfsiz kiring."
- [x] 2-Bosqich: `?error=google_not_configured` URL Xatolarini Jimgina Tozalash:
  * `Login.tsx`: Brauzer manzilida `error=google_not_configured` bo'lsa, hech qanday qizil xatolik oynasi chizilmaydi va `window.history.replaceState({}, document.title, window.location.pathname)` orqali URL jimgina tozalanadi.
  * `isGoogleUnconfigured` himoyasi orqali har qanday eskirgan yoki session xatolari filtrlandi.
- [x] 3-Bosqich: Backend Redirect Xavfsizligi:
  * `apps/accounts/google_auth.py`: `google_auth_start` funksiyasida Google OAuth sozlanmagan bo'lsa, xatolik parametrlarisiz to'g'ridan-to'g'ri `/login` sahifasiga redirect qilish ta'minlandi (`return redirect("/login")`).
- [x] 4-Bosqich: QA, CI/CD va VPS Zero-Downtime Deploy:
  * `tests/test_google_auth_redirect.py`: 2 ta yangi unit test yozildi va 100% PASS qildi.
  * `npm run lint`: 0 ta xatolik, `npm run build`: 0 ta xatolik (3.40s).
  * Commit muallifi: `Komiljon Roziyev <kruziyev0@gmail.com>`.
  * Xabar: `fix(auth): strictly hide Google OAuth button, sanitize banner text, and purge unconfigured error box`.
  * PR ochildi, barcha CI tekshiruvlari yashil bo'lgach `main` ga squash-merge qilindi va VPS ga uzilishsiz deploy qilindi.

### 2.41. Rasmiy Versiya v1.43.0: Unconfigured Google OAuth Button Yashirish va Telegram 1-Klik Autentifikatsiya
- [x] 1-Bosqich: Sozlanmagan Google OAuth Tugmasini Yashirish:
  * `frontend/src/pages/Login.tsx`, `frontend/src/components/AuthModal.tsx` va `frontend/src/pages/Register.tsx`: Sozlanmagan Google tugmasi yashirildi (`const hasGoogle = Boolean(import.meta.env.VITE_GOOGLE_CLIENT_ID);` orqali shartli render qilindi).
  * `google_not_configured` xato kodi uchun ortiqcha "Google orqali kirish hali sozlanmagan" xabari ko'rinmaydigan qilindi (`return null`).
  * `AuthModal.tsx` da `errorMsg` ichida Google sozlanmaganlik xatolari foydalanuvchiga ko'rsatilmasligi ta'minlandi.
- [x] 2-Bosqich: Talabalar uchun Yagona 1-Klikli Telegram Kirish:
  * `frontend/src/pages/Login.tsx` va `frontend/src/components/AuthModal.tsx`: Asosiy va yagona 1-klikli tizim sifatida `[ 📱 Telegram orqali 1-klikda kirish ]` (ko'k `#229ED9`, oq matn, shadow) markazga joylashtirildi.
  * O'quvchilar uchun parolsiz 1 soniyada tizimga kirish ta'minlandi.
  * `frontend/src/pages/Register.tsx`: Talabalarni to'g'ridan-to'g'ri 1-klikli Telegram ro'yxatdan o'tishga yo'naltiruvchi `[ 📱 Telegram orqali 1-klikda kirish / ro‘yxatdan o‘tish ]` tugmasi joylashtirildi.
- [x] 3-Bosqich: Ustozlar va Admin uchun Alohida Tab:
  * `frontend/src/pages/Login.tsx`: 2 ta qat'iy ajratilgan toza tab saqlandi:
    * `[ ⚡ O‘quvchilar (Telegram 1-klik) ]` (standart faol)
    * `[ 🔑 O‘qituvchilar va Admin ]` (Email va Parol kiritish formasi, xodimlar uchun parolni tiklash).
- [x] 4-Bosqich: QA, CI/CD va VPS Zero-Downtime Deploy:
  * `npm run lint`: 0 ta xato.
  * `npm run build`: 2.90s ichida muvaffaqiyatli yig'ildi.
  * Pytest sinovlari: 100% PASS.
  * Commit muallifi: `Komiljon Roziyev <kruziyev0@gmail.com>`.
  * VPS (`bestway-vps` / `169.58.58.229`) ga uzilishsiz deploy qilindi. `bestway` mustaqil loyihasi mutlaqo daxlsiz saqlandi.
  * Jonli verifikatsiya: `https://grandec.uz/healthz/` (HTTP 200 OK, v1.43.0).

### 2.40. Rasmiy Versiya v1.42.0: Savollar Mazmuni Bo'yicha Testlar Deduplikatsiyasi (Question Content Fingerprint Deduplication & Authentic Seeders)
- [x] 1-Bosqich: Savollar Mazmuni Bo'yicha Deduplikatsiya Mantiqi (`apps/tests/management/commands/deduplicate_by_questions.py`):
  * Test nomiga (title) mutlaqo qaramasdan, faqat savollar matnini normalizatsiya qilish (raqamlar, bo'shliqlar va tinish belgilarini tozalash) orqali SHA-256 xeshlar ketma-ketligi va savollar prefiksi (dastlabki 5 ta savol) barmoq izi (fingerprint) asosida klonlarni aniqlash mexanizmi ishlab chiqildi.
  * Disjoint-Set / Union-Find algoritmi orqali bir xil savollar to'plamiga ega bo'lgan barcha testlar klasterlarga ajratildi.
  * Kanonik asosiy testni tanlash: Eng ko'p o'quvchi urinishiga ega (`TestAttempt` soni bo'yicha) yoki teng bo'lganda eng kichik ID ga ega bo'lgan birlamchi test saqlanib qoladi.
  * Barcha bog'liq yozuvlarni xavfsiz ko'chirish: `TestAttempt`, `StudentAnswer`, `Result`, `Certificate`, `Tournament`, `Homework` yozuvlari kanonik testga va uning mos savol/variantlariga xatosiz qayta ulandi.
  * `--dry-run` rejimi va `transaction.atomic()` himoyasi: Xatolik yuz berganda avtomatik rollback qilish kafolatlandi.
- [x] 2-Bosqich: Seeder va Fixturalarni Haqiqiy Savollar Bilan Qayta Yozish:
  * `apps/tests/management/commands/seed_official_omr_tests.py`: Sinov variantlari (BMB-101, BMB-102, BMB-103, IELTS-201, IELTS-202, CEFR-301) endi bir-birini takrorlamaydigan, to'liq o'ziga xos haqiqiy savollar va javob variantlarini yaratadigan qilib qayta ishlandi.
  * `apps/tests/fixtures/official_omr_tests.json`: Barcha variantlar uchun savol matnlari unikal, haqiqiy akademik kontent bilan yangilandi.
- [x] 3-Bosqich: QA Darvozasi va Unit Testlar:
  * `tests/test_deduplicate_by_questions.py`: 4 ta kompleks unit test yozildi:
    1) Nomlari butunlay har xil, ammo savollari bir xil bo'lgan klon testlarni aniqlash va birlashtirish;
    2) Haqiqiy har xil savollarga ega testlarga aslo tegmaslik kafolati;
    3) `--dry-run` rejimida hech qanday test o'chirilmasligini tekshirish;
    4) O'quvchi urinishlari (`TestAttempt`) va javoblarini birlamchi testga to'liq ko'chirish tekshiruvi.
  * Barcha testlar 100% muvaffaqiyatli o'tdi (`4 passed in 22.51s`).
- [x] 4-Bosqich: Contabo VPS Deploy, Klondan Tozalash va Jonli Verifikatsiya:
  * `bestway` loyihasi mutlaqo daxlsiz saqlandi (hech qanday aralashuvsiz).
  * VPS dagi `/opt/lms` kodi `v1.42.0` ga yangilandi, Docker konteynerlari qayta yig'ildi (`web` va `nginx`).
  * `python manage.py deduplicate_by_questions` buyrug'i serverda bajarildi:
    - Guruh 1 (IELTS Academic): Klon ID 10 asosiy ID 9 ga birlashtirildi va o'chirildi.
    - Guruh 2 (BMB Milliy Sertifikat): Klon ID 7 va ID 8 asosiy ID 6 ga birlashtirildi, 1 ta o'quvchi urinishi saqlab qolindi va klonlar o'chirildi.
  * Jonli tekshiruv: `https://grandec.uz/healthz/` (HTTP 200 OK, v1.42.0), `https://grandec.uz/api/tests/` (jami faol 6 ta unikal test, dublikatlar 0 ta).

### 2.39. Rasmiy Versiya v1.40.0: Passwordless 2-Tab Auth, 1v1 Arena WebSocket Reconnect & Grace Period, AI Token Bleeding Pre-Validation va SPA Dynamic SEO Sitemap
- [x] 1-Bosqich: Auth UI Tozalash (Passwordless & 2-Tab Unified Login):
  * `frontend/src/pages/Login.tsx`: Talabalar uchun 1-klikli tizim joriy etildi. Asosiy Hero CTA sifatida `[ 📱 Telegram orqali 1-klikda kirish ]` (ko'k `#229ED9`, oq matn, shadow) va `[ 🌐 Google orqali kirish ]` tugmalari joylashtirildi. Talabalar uchun parol maydonlari butunlay yashirildi (0 ta parol maydoni).
  * 2 talik toza tab tizimi: `[ ⚡ O'quvchilar (1-klikda) ]` (standart faol) hamda `[ 🔑 Ustozlar va Admin ]`.
  * Ustozlar va Admin tabida Email + Parol kiritish maydoni saqlandi, "Parolni unutdingizmi?" (`/password-reset`) havolasi qat'iy ushbu xodimlar tabi ichiga olindi.
- [x] 2-Bosqich: 1v1 Arena WebSocket Barqarorligi (Network Resilience):
  * `apps/arena/consumers.py` & `frontend/src/pages/DuelRoom.tsx`: Har 15 soniyada `{"type": "ping"}` yuboruvchi va serverdan `{"type": "pong"}` oluvchi Heartbeat mexanizmi joriy etildi. 2 marta ketma-ket javob kelmasa (30 soniya uzilish), klient avtomatik qayta ulanadi.
  * Silent Reconnection & Backoff: Mobil internet uzilib qayta ulanganda, o'yin UI muzlamasdan fonda avtomatik `ReconnectingWebSocket` (exponential backoff: 1s, 2s, 5s) bilan qayta ulanadi.
  * 30 Soniyalik Grace Period: O'yinchi uzilib qolsa, o'yin darhol bekor qilinmaydi. Raqib ekranida `"⚠️ Raqib interneti qayta ulanmoqda... (qolgan vaqt: 25s)"` orqaga hisoblash paneli ko'rsatiladi. 30 soniya ichida qayta ulansa, o'yin davom etadi (`opponent_reconnected`). Agar 30 soniyada ulanmasa, server `forfeit_duel` orqali qolgan o'yinchiga texnik g'alaba yozadi va ELO reytingi yangilanadi.
- [x] 3-Bosqich: AI Pre-Validation Filter (Token Bleeding Stopper):
  * `apps/essays/pre_validation.py`: 3 bosqichli 0.01 soniyalik tezkor filtr:
    1) Minimal so'zlar soni (kamida 60 ta so'z yoki mavzu bo'yicha maxsus chegara): `"⚠️ Esse juda qisqa (kamida {min} ta so'z bo'lishi shart). Hozirgi so'zlar soni: {count} ta."`
    2) Safsata va Simvollar takrorlanishi (Gibberish / Anti-Spam): ketma-ket harflar (`aaaaaa`, `asdasdasd`), 35 dan ortiq belgili so'zlar, takrorlanuvchi bitta so'z spam (>35%): `"⛔ Matn tushunarsiz yoki safsata deb topildi. Iltimos, haqiqiy esse matnini kiriting."`
    3) Til va Lug'at tekshiruvi: O'zbek yoki ingliz tilidagi lug'aviy so'zlarning ulushi kamida 60% bo'lishi shart.
  * Integratsiya: `frontend/src/pages/EssayWrite.tsx` da jo'natishdan oldin klient tekshiruvi, `apps/essays/views.py` va `apps/telegram_app/views.py` da kvota sarflanishi va Celery ga navbatga qo'yilishidan oldingi server tekshiruvi hamda `apps/essays/services.py` va `deepseek_grader.py` himoyasi.
- [x] 4-Bosqich: SPA Dynamic Metadata & SEO:
  * `apps/core/views_seo.py` & `config/urls.py`: Dinamik `https://grandec.uz/sitemap.xml` (barcha statik ochiq sahifalar, nashr qilingan faol testlar va kurslar) hamda `https://grandec.uz/robots.txt` generatori.
  * `frontend/src/pages/TestDetail.tsx`: Dinamik OpenGraph (Title, Description, canonical URL) meta-teglari.
- [x] 5-Bosqich: QA, CI/CD va VPS Zero-Downtime Deploy:
  * Yangi testlar: `tests/test_essay_prevalidation.py` (11/11 test PASS), `tests/test_arena_ws_reconnect.py` (3/3 test PASS), `tests/test_seo_sitemap.py` (3/3 test PASS).
  * Butun testlar to'plami: 1295 ta test 100% PASS (0 ta xatolik).
  * Frontend TypeScript kompilyatsiyasi: `npm run build --prefix frontend` (2.43s ichida xatosiz yig'ildi).
  * PR #109 squash-merge qilindi, v1.40.0 chiqarildi, Contabo VPS (`169.58.58.229`) ga uzilishsiz deploy qilindi.
  * `bestway` mustaqil loyihasi mutlaqo daxlsiz saqlandi.
  * Jonli tekshiruv: `https://grandec.uz/healthz/` (HTTP 200 OK, v1.40.0), `https://grandec.uz/sitemap.xml` (HTTP 200 OK), `https://grandec.uz/robots.txt` (HTTP 200 OK), `https://grandec.uz/login` (HTTP 200 OK).

### 2.38. Rasmiy Versiya v1.38.0: AI Esse Baholashda Mavzuga Moslik (Topic Relevance & Prompt Adherence) Qoidalari
- [x] 1-Bosqich: Prompt Muhandisligi va Mavzuga Moslik 0-Bosqich Darvozasi:
  * `apps/essays/prompts.py` (`ESSAY_GRADING_SYSTEM_PROMPT` va `ESSAY_GRADING_SYSTEM_PROMPT_SIMPLE`): Step 0 (Mavzuga moslik va adherence gate) joriy etildi. Model majburiy tarzda `topic_status` (`completely_off_topic`, `partially_off_topic`, `on_topic`), `is_completely_off_topic` va `topic_match` maydonlarini qaytaradi.
  * `IELTS_SYSTEM_PROMPT` (`apps/essays/services.py`): Step 0 Topic Relevance gate o'rnatildi.
- [x] 2-Bosqich: Mutlaqo Mavzudan Chetda (Completely Off-topic) — Qat'iy 0 Ball:
  * BMB 12 mezon va IELTS 4 mezon bo'yicha barcha mezon ballari va umumiy ball qat'iy 0.0 ga tenglashtiriladi (`total_score = 0.0`, `overall_band = 0.0`).
  * Talabaga qat'iy ogohlantirish matni taqdim etiladi:
    `"⛔ DIQQAT: Taqdim etilgan esse berilgan mavzuga mutlaqo mos kelmaydi (Off-topic). Mavzudan butunlay chetlashilganligi sababli ishga 0 ball qo'yildi."`
  * `EssaySubmission.converted_score` xususiyati mutlaqo 0 ball qaytaradi.
- [x] 3-Bosqich: Qisman Mavzudan Chetda (Partially Off-topic / Tangential) — 2 dan 35 Ballgacha Cheklov:
  * BMB Ona tili: 1-mezon ("Mavzuning to'liq va teran ochib berilishi") maksimal 1.0 balldan oshmasligi ta'minlandi. 20 ballik rubrikadagi umumiy xom ball maksimal 7.0 ball (35%) bilan cheklandi.
  * IELTS Writing / Multi-level: Criterion 1 (Task Achievement / Task Response) maksimal Band 3.0 bilan, `overall_band` esa maksimal Band 3.5 bilan cheklandi.
  * `EssaySubmission.converted_score` 2 dan 35 ball oralig'iga qat'iy qisqartirildi (`max(2, min(raw_converted, 35))`).
  * Talabaga ogohlantirish matni taqdim etiladi:
    `"⚠️ OGOHLANTIRISH: Esseda mavzudan jiddiy chetlanish kuzatildi. Asosiy savolga to'liq javob berilmaganligi sababli baho 2 – 35 ball oralig'iga keskin tushirildi."`
- [x] 4-Bosqich: Backend Qat'iy Himoya Qatlamlari (Hard Guardrails) va Model Maydonlari:
  * `ALLOWED_TOP_KEYS` schema validatoriga `topic_status`, `is_completely_off_topic`, `is_off_topic` qo'shildi.
  * `_validate_result` va `_validate_ielts_result` funksiyalarida sun'iy intellekt gallyutsinatsiyasi natijasini dasturiy darajada qirquvchi qat'iy guardraillar joylashtirildi.
  * `EssaySubmission` modeliga `topic_status` va `is_completely_off_topic` maydonlari qo'shildi (`0021_essaysubmission_is_completely_off_topic_and_more.py` migratsiyasi).
  * Frontend `EssayResult.tsx` da qizil (0 ball) va sariq (2-35 ball) vizual ogohlantirish kartalari o'rnatildi.
- [x] 5-Bosqich: QA Darvozasi, CI/CD va VPS Deploy:
  * Yangi test paketi: `tests/test_essay_off_topic.py` (7/7 test 100% PASS).
  * Butun esse testlar to'plami: `pytest tests/ -k essay -q` (352 passed, 0 failed, 100% PASS).
  * Frontend TypeScript kompilyatsiyasi: `npm run build --prefix frontend` (4.45s ichida xatosiz yig'ildi).
  * GitHub PR #108 squash-merge qilindi, Docker image `ghcr.io/algorithco/lms:sha-bba6997` avtomatik yig'ildi va Contabo VPS-ga muvaffaqiyatli deploy qilindi.
  * VPS endpointlari tekshirildi: `https://grandec.uz/healthz/` (HTTP 200 OK), `https://grandec.uz/` (HTTP 200 OK). Bestway mustaqil tizimi mutlaqo daxlsiz saqlandi.

### 2.37. Rasmiy Versiya v1.36.0: Obsidian Dark UI Hotfix, Pro Card Overlay Tozalash, Idempotent Seeder va Bazadagi Dublikat Testlar Deduplikatsiyasi
- [x] 1-Bosqich: CSS Hotfix va Elegant Obsidian Dark UI:
  * Tariflar panelida PRO karta ustiga chiqib, matn va tugmalarni to'sib turgan xunuk aylanuvchi to'rtburchak/gradient qatlam (`pro-card-glow` / `@keyframes rotateBorderSpin`) `frontend/src/theme.css` va `Landing.tsx` dan butunlay olib tashlandi.
  * Barcha 4 ta tarif kartalari (Bepul, Starter 5 000, PRO 49 000, PREMIUM 89 000) Obsidian Dark UI (`background: rgba(11, 15, 25, 0.9)`, `backdropFilter: blur(12px)`, `border: 1px solid rgba(255, 255, 255, 0.1)`, `transition: all 0.3s ease`) estetikasiga o'tkazildi.
  * PRO karta: `border: 2px solid rgba(245, 158, 11, 0.7)`, `boxShadow: 0 0 30px -5px rgba(245, 158, 11, 0.25)`, nishon: `background: rgba(245, 158, 11, 0.2)`, `border: 1px solid rgba(245, 158, 11, 0.3)`, `color: #FBBF24`.
  * Afzalliklar ro'yxatidagi barcha checkmarklar tiniq zumrad yashil (`#10B981`) rangga keltirildi, barcha CTA tugmalari pastga tekislandi (`marginTop: 'auto'`).
  * "tayyormisiz?" sarlavhasi: `overflow: hidden` kesilishi olib tashlandi, sarlavha balandligi `lineHeight: 1.25`, `padding: 4px 0` va tiniq oq-oltin gradient (`linear-gradient(135deg, #FFFFFF 30%, #F59E0B 100%)`, `WebkitBackgroundClip: text`) bilan jilolandi.
- [x] 2-Bosqich: Bazadagi Dublikat Testlar Deduplikatsiyasi (`deduplicate_tests`):
  * `apps/tests/management/commands/deduplicate_tests.py` buyrug'i ishlab chiqildi.
  * Titul, fan, savollar soni va savollar ketma-ketligi mazmunining SHA-256 xeshi 100% bir xil bo'lgan klon testlar aniqlanadi.
  * Farqli testlar (Variant 1, Variant 2, Variant 3, Attestatsiya 2026, IELTS Mock 1, IELTS Mock 2) mutlaqo daxlsiz qolishi kafolatlangan.
  * Eng ko'p urinishga ega (yoki eng kichik ID li) test kanonik asosiy test sifatida saqlanib, barcha `TestAttempt`, `Result`, `Certificate`, `Tournament`, `Homework` yozuvlari xavfsiz kanonik testga ko'chirildi (`update(test=primary)`).
  * `--dry-run` bayrog'i qo'llab-quvvatlandi va atomik tranzaksiya ichida klonlar tozalandi.
- [x] 3-Bosqich: Seeder Qulfi va Idempotentlik (`seed_official_omr_tests`):
  * `apps/tests/management/commands/seed_official_omr_tests.py` to'liq `update_or_create` mantiqiga o'tkazildi.
  * ReadingPassage, Question va Choice yozuvlari pozitsiya va test bo'yicha idempotent sinxronlanadi. Buyruq qayta-qayta ishga tushirilganda ham 0 ta dublikat yaratadi.
- [x] 4-Bosqich: QA Darvozasi va To'liq Sinovlar:
  * Yangi unit testlar: `tests/test_deduplicate_tests.py` (4/4 test 100% PASS).
  * OMR testlari: `tests/test_omr_db_integration.py` (3/3 test 100% PASS).
  * `ruff check --fix .` va `ruff format .`: 0 ta xatolik.
  * `npm run lint --prefix frontend`: 0 ta xatolik, `npm run build`: 2.49s ichida muvaffaqiyatli yig'ildi.

### 2.36. Rasmiy Versiya v1.35.0: Titul (OMR) Baza Integratsiyasi va Next-Gen Glassmorphism & UI/UX Dizayni
- [x] 1-Bosqich: Titul (OMR) Baza Integratsiyasi & Seeding:
  * `seed_official_omr_tests` buyrug'i va `official_omr_tests.json` fixturasi orqali bazaga 6 ta rasmiy test kalitlari bilan kiritildi:
    - 3 ta BMB Milliy Sertifikat (Ona tili va adabiyot: `BMB-101`, `BMB-102`, `BMB-103` — 45 talik format).
    - 2 ta Cambridge Official CD-IELTS Mock (`IELTS-201`, `IELTS-202` — Academic Reading 40 talik format).
    - 1 ta CEFR Multi-Level English Mock (`CEFR-301` — 35 talik format).
  * `GET /api/v1/tests/scan-omr/` API yakuniy nuqtasi yaratildi: Faol testlar ro'yxatini (`id`, `mock_code`, `access_code`, `title`, `total_questions`, `time_limit_minutes`) qaytaradi.
  * Vision OCR test kodi bazada topilmasa: `code_not_found: true` signali va "⚠️ Tituldan o'qilgan '{KOD}' kodi bo'yicha test bazada topilmadi. Iltimos, pastdagi ro'yxatdan qaysi testga javob berganingizni tanlang" ogohlantirishini beradi.
  * Frontend OMR skaneri (`ScanOMR.tsx` va yangi `/titul-scanner` marshruti):
    - Rejim A: "Bazamizdagi testni tanlang" — qidiruvli va toifali qulay Dropdown/Grid interfeysi.
    - Rejim B: "Tituldan avtomatik aniqlash (Vision OCR)".
- [x] 2-Bosqich: Next-Gen EdTech Dark Glassmorphism & Hero Animatsiyasi:
  * Bosh sahifa (Landing) foniga Ambient Mesh Glow markaziy ellips va zumrad hamda binafsharang suzuvchi neon sharlar o'rnatildi.
  * Interactive Hero Demo Card: `HeroCountUp` orqali 0 dan 54.5 gacha silliq hisoblagich, 12 ta rasmiy BMB mezonlari bosilganda tavsiyalar silliq o'zgarishi.
  * 3 ta asosiy xususiyat kartalari: Chuqur glassmorphism (`bg-slate-900/60 backdrop-blur-xl hover:border-amber-500/40 hover:-translate-y-1.5`) va piktogrammalarga hover-pulse berildi.
  * Trend Chart: Recharts spline egri chiziqlari zangori-oltin gradiyent bilan to'ldirildi; jonli ma'lumotlar bo'lmaganda avtomatik ravishda "O'sish dinamikasi simulyatsiyasi (B1 ➔ C1)" ga o'tishi ta'minlandi.
  * 4 ustunli Tariflar paneli: Starter (5 000 UZS) zumrad aura, PRO (49 000 UZS) aylanuvchi kamalak ramka (`pro-card-glow`), PREMIUM (89 000 UZS) binafsharang VIP aura (`vip-aura`) va tugmalarga `btn-shimmer` sweep nuri ulandi.
- [x] 3-Bosqich: Dashboard Skeleton Yuklagichlar va Metal Shine:
  * Eski `'…'` yuklash belgilari o'rniga zamonaviy `animate-pulse` skeletlari o'rnatildi.
  * Streak olovi uchun haqiqiy olov miltillash animatsiyasi (`fire-flicker`) joriy qilindi.
  * XP va Liga kartalariga 3D metall jilosi (`badge-metal-shine`) berildi.
- [x] 4-Bosqich: QA, CI/CD va VPS Zero-Downtime Deploy:
  * `npm run lint`: 0 ta xatolik, `npm run build`: 0 ta xatolik, Vite production bundle 3.25s da yig'ildi.
  * Yangi OMR integratsiya testlari (`pytest tests/test_omr_db_integration.py`): 3/3 test 100% PASS.
  * Regressiya testlari (`pytest tests/test_omr_speaking_gamification.py`, `test_strategic_features.py`): 100% PASS.
  * GitHub PR #106 barcha CI tekshiruvlaridan (CodeQL, security, automerge, test) to'liq o'tib, `main` ga squash-merge qilindi.
  * Komiljon Roziyev <kruziyev0@gmail.com> (Zero AI attribution) muallifligi qat'iy saqlandi.
  * VPS (`169.58.58.229`) ga uzilishsiz deploy qilindi. `bestway` mustaqil tizimi mutlaqo daxlsiz saqlandi.
  * Jonli tekshiruv: `https://grandec.uz/healthz/` (HTTP 200 OK, v1.35.0), `https://grandec.uz/api/v1/tests/scan-omr/` (HTTP 200 OK, 9 ta faol test).

### 2.35. Rasmiy Versiya v1.33.0: Cambridge Computer-Delivered IELTS (CD-IELTS) & BMB CBT Split-Screen Imtihon Interfeysi
- [x] 1-Bosqich: Distraction-Free Kiosk Rejimi (100vw x 100vh):
  * `frontend/src/App.tsx` da `/english-exam/:attemptId` marshruti standart `Layout` (chapdagi LMS sidebar menyusi, Boshqaruv paneli, Turnirlar va yuqoridagi 0 XP Navbar) tashqarisiga chiqarildi.
  * To'liq 100vw x 100vh ekran maydoni faqat imtihon o'tkazish uchun ajratildi.
- [x] 2-Bosqich: Rasmiy Kembrij Top-Header (56px balandlikda):
  * Chap tomonda: CD-IELTS nishoni, imtihon nomi, qaysi Passage'daligi haqida toza indikator (`Passage 1 of 3`) hamda rejim nishoni (`🛑 Strict Exam` / `💡 Practice`).
  * O'rtada: Tiniq va xalaqit bermaydigan taymer (`⏱ 58:45 remaining`), oxirgi 5 daqiqada qizil rangda miltillovchi vizual ogohlantirish.
  * O'ng tomonda:
    - Matn shriftini kattalashtirish vositasi: `Standard` (15px) va `Large` (18px) o'rtasida 1-klikli almashtirish.
    - Highlighter asboblari: `[ 🖍️ Highlight ]` va bo'yoqlarni tozalash `[ Clear ]`.
    - Review nishonchasi: `[ 🚩 Review ]` holati.
    - Listening audio uchun minimalist ovoz sozlagichi (`Volume slider`) va mute boshqaruvi.
    - To'liq ekran (Fullscreen) tugmasi.
- [x] 3-Bosqich: 50/50 Split-Screen Arxitekturasi:
  * Chap Panel (Reading Passage): Mustaqil vertikal skroll, Georgia / serif tipografiyasi, paragraflar boshida Cambridge uslubidagi `[ A ]`, `[ B ]`, `[ C ]` drop cap nishonlari.
  * Matn tanlanganda avtomatik kichik floating popover paydo bo'lib, tanlangan matnni bir bosishda `[ 🖍 Highlight ]` qilish imkoniyati.
  * O'ng Panel (Savollar maydoni): Mustaqil skroll, katta va aniq `Question 1` sarlavhasi, kursiv yo'riqnoma (`Choose the correct letter, A, B, C or D`), Kembrij radio kartalari (`TRUE`, `FALSE`, `NOT GIVEN` va variantlar) tanlanganda zangori/ko'k fon va hoshiya bilan ajralib turishi.
  * Practice Mode uchun `[ 💡 AI Dalilli Tushuntirish (DeepSeek-R1 Evidence) ]` tugmasi, Strict Exam rejimida esa AI tugmasi mutlaqo ko'rinmaydi.
  * Mobile Responsive: Kichik ekranlarda (<1024px) yuqori qismda `[ 📖 Reading Passage ]` va `[ ❓ Questions (Q1/40) ]` tablari orqali 1-bosishda silliq almashish.
- [x] 4-Bosqich: Kembrij Savollar Palitrasi (Question Palette Footer):
  * Ekran tubida qat'iy yopishgan (fixed bottom bar) to'liq kenglikdagi panel.
  * 1 dan 40 gacha barcha savol katakchalari: Javob berilmagan (yengil hoshiya), javob berilgan (to'lgan fon va indikator), belgilangan (sariq bayroqcha bilan) va joriy ochiq savol (qalin ko'k ramka).
  * O'ng tomonda navigatsiya tugmalari: `[ 🚩 Review ]`, `[ ← Back ]`, `[ Next → ]` va `[ Finish Test / Yakunlash ]`.
  * Yakunlash modali: "Siz 40 ta savoldan X tasiga javob berdingiz. Y ta savol javobsiz qoldi. Rostdan ham testni yakunlaysizmi?" ko'rinishidagi batafsil tasdiqlash darchasi.
- [x] 5-Bosqich: QA, CI va VPS Deploy:
  * `npm run lint`: 0 ta xatolik, `npm run build`: 1.07s ichida muvaffaqiyatli yig'ildi.
  * Backend testlari (`pytest tests/test_english_exam_evidence_converter.py -v`): 13/13 test 100% PASS.
  * GitHub PR #105 barcha CI tekshiruvlaridan muvaffaqiyatli o'tib, `main` ga squash-merge qilindi.
  * VPS (`169.58.58.229`) ga uzilishsiz deploy qilindi. `bestway` loyihasiga mutlaqo tegilmadi va uning xizmatlari uzluksiz ishlamoqda.
  * Jonli tekshiruv: `curl.exe -fsS https://grandec.uz/healthz/` ➔ `{"status": "ok", "db": true, "version": "1.33.0"}` (HTTP 200 OK).

### 2.34. Rasmiy Versiya v1.30.0: To'liq Tizim Auditi, Xavfsizlik Mustahkamlanishi, AI Vision OCR Anti-Fraud Dvigateli va Barqarorlashtirish (/audit)
- [x] 1-Bosqich: Fayllar Inventarizatsiyasi va Eskirgan Kodlarni Tozalash:
  * Ochiq ro'yxatdan o'tishda `role` maydoni serializers darajasida `read_only_fields` ga kiritildi va qat'iy Student sifatida cheklandi.
  * Frontend paketlar auditi (`npm audit fix`): `source-map-js` va `vite` paketlaridagi zaifliklar bartaraf etildi (0 vulnerabilities).
  * 3 tillik (UZ, RU, EN) tarjimalar to'liq tahlil qilindi: 1,684 ta kalit 100% paritetga ega (0 ta yetishmayotgan kalit).
- [x] 2-Bosqich: Chuqur Mantiqiy va Funksional Xatolarni Tuzatish:
  * Autentifikatsiya va RBAC: O'qituvchilarni faqat Admin yaratishi (`/api/v1/panel/teachers/create/`), kvotalar faqat Admin tomonidan biriktirilishi kafolatlandi.
  * Ustoz o'z kvotasi hisobidan o'quvchiga PRO/PREMIUM berganda race-condition bo'lmasligi uchun `transaction.atomic()` va `select_for_update()` tranzaksiya blokirovkasi o'rnatildi.
  * Guruhlar ochish, davomat olish va panel API larida `IsTeacherOrAdmin` va `IsPanelAdmin` ruxsatnomalari tekshirildi (oddiy studentlar uchun 403 Forbidden).
  * Onboarding Modali: `/dashboard` sahifasida modal yopilganda va saqlanganda holat `localStorage` va bazada mustahkamlandi, re-trigger xatoligi butunlay bartaraf etildi.
  * Lifecycle deklaratsiya tartibi `Login.tsx` va `TeacherFinanceDashboard.tsx` da to'g'rilandi.
  * AI Baholash: Yagona rasmiy model `deepseek/deepseek-r1-0528` saqlandi, xatoliklarni deduksiya usulida tahlil qilish va uzilishlarda avtomatik retry/fallback barqarorlashtirildi.
  * Anti-Fraud va Chek OCR: Takroriy SHA-256 xesh yoki takroriy tranzaksiya ID si bo'yicha firibgarlikni aniqlash va avtomatik ban (`is_banned=True`) mexanizmi sinovdan o'tkazildi.
  * Ingliz tili imtihonlari (IELTS/CEFR): Cambridge 50/50 split-screen, Strict anti-cheat rejimi va xom ballarni Band/CEFR ga o'tkazuvchi konvertor matematik jihatdan to'liq ishchi holatda.
- [x] 3-Bosqich: Frontend va UI/UX Auditi:
  * Mobil ergonomika: Kichik ekranlarda (<768px) sticky elementlar va sensorli tugmalarni to'sib qo'ymasligi uchun `.content` ga `pb-30` (7.5rem) xavfsiz bo'sh joy qo'shildi.
  * Oxlint va TypeScript tahlili: 0 ta xatolik, frontend assets `npm run build` orqali 2.04 soniyada yig'ildi.
- [x] 4-Bosqich: Ma'lumotlar Bazasi va ORM Optimizatsiyasi:
  * `makemigrations --check --dry-run` orqali migratsiyalar 100% to'liq va sinxron ekani tasdiqlandi (`No changes detected`).
  * `telegram_chat_id`, `transaction_id`, `receipt_hash`, `role` maydonlarining indekslanishi va unikal cheklovlari tekshirildi.
- [x] 5-Bosqich: Zero-Error QA Darvozasi va GitHub CI:
  * `python -m ruff check --fix .` va `python -m ruff format .` (0 ogohlantirish, 0 xatolik).
  * Regressiya va xususiyat testlari: `pytest` 54/54 test 100% PASS.
  * GitHub PR #104 ochildi va barcha CI tekshiruvlari (CodeQL, security, automerge, test) yashil o'tgach, `main` ga squash-merge qilindi.
- [x] 6-Bosqich: Jonli VPS Deploy va Healthcheck (Zero-Downtime):
  * `bestway` ekotizimi mutlaqo mustaqil va daxlsiz saqlanib, birorta fayli yoki konteyneriga tegilmadi.
  * VPS'dagi `grandec` (lms) xizmatlari yangilandi va qayta ishga tushirildi.
  * Jonli tekshiruv: `curl.exe -fsS https://grandec.uz/healthz/` ➔ `{"status": "ok", "db": true, "version": "1.30.0"}` (HTTP 200 OK).

### 2.33. Rasmiy Versiya v1.29.0: Telegram Bot & Veb-Platforma 100% Pariteti, Yagona Akkaunt (Unified User), Qat'iy Kvota Nazorati (Free 1-Esse Limiti) va Ustozlar CRM (/davomat, /tolovlar, Chek Tasdiqlash)
- [x] Akkauntlarni Bog'lash va Yagona Identifikatsiya (Unified User):
  * `User.telegram_id` va `User.telegram_username` (migratsiya `0017_user_telegram_username`) PostgreSQL User bazasiga qat'iy bog'landi.
  * Saytda yoki botda `/start link_<token>` orqali 1-klikli bog'lanish va sinxronizatsiya.
  * Muvaffaqiyatli bog'langanda to'liq profil, rol, tarif va sinxronlashgan kvotalar bilan tasdiqlash.
- [x] Sayt Bilan Bir Xil Kvota va Cheklov Nazorati (Quota Enforcement):
  * `apps/subscriptions/services.py` dagi `QuotaService`:
    - Bepul foydalanuvchi uchun kunlik qat'iy 1 ta esse limiti. Bugun foydalanilgan bo'lsa, tekshirish bloklanadi va maxsus ogohlantirish beriladi:
      "⚠️ Kvotangiz tugadi! Siz bugungi 1 ta bepul esse tekshirish imkoniyatingizdan foydalandingiz. Cheklovlarsiz ishlash uchun 5 000 so'mlik Starter yoki PRO tarifiga o'ting!"
    - Tugmalar: `[ ⚡ Starter (5 000 so'm) ]`, `[ 🔥 PRO tarifiga o'tish ]`, `[ 🌐 Saytga o'tish ]`.
    - Starter foydalanuvchilar (3 ta esse / 5 ta test) va PRO/PREMIUM foydalanuvchilar to'siqsiz xizmat ko'rsatilishi.
- [x] Botda Ustozlar CRM (Davomat va To'lovlar Nazorati):
  * `/davomat` komandasi:
    - Guruhdagi o'quvchilar ro'yxati 1 soniyada bosiladigan interaktiv `🟢 Keldi` / `🔴 Kelmadi` inline tugmalari bilan chiqariladi.
    - `[ 💾 Saqlash ]` bosilganda bazadagi `AttendanceSession` va `AttendanceRecord` ga yoziladi hamda darsga kelmagan o'quvchilarning ota-onalariga (`parent_telegram_id`) avtomatik Telegram bildirishnomasi jo'natiladi.
  * `/tolovlar` komandasi:
    - Guruh bo'yicha moliyaviy xulosa: Jami o'quvchilar, To'laganlar (summasi bilan), Qarzdorlar (summasi bilan).
    - `[ 📢 Qarzdorlarga eslatma yuborish ]` 1-klik tugmasi orqali to'lov muddati kelgan barcha o'quvchilarga va ularning ota-onalariga xushmuomala eslatma yuborish.
  * To'lov Cheklarini Bot Orqali Tasdiqlash:
    - O'quvchi botga to'lov cheki yuborganda Vision OCR orqali summa va tranzaksiya ID o'qiladi.
    - Ustozning botiga tasdiqlash xabari keladi: "📥 {Ism} {Summa} so'mlik chek yukladi. Tasdiqlaysizmi?" `[ ✅ Tasdiqlash ]` | `[ ❌ Rad etish ]`.
    - Ustoz tasdiqlashi bilan o'quvchining to'lov muddati avtomatik 30 kunga uzaytiriladi va o'quvchiga tasdiq xabari yetkaziladi.
- [x] Sifat Nazorati va QA Gate (100% PASS):
  * `pytest tests/test_bot_unified_quota_crm.py`: 12/12 test 100% muvaffaqiyatli o'tdi.
  * `ruff check apps/ tests/ config/`: 0 xatolik.
  * Frontend: `npm run build` 2.88 soniyada 0 xato bilan yig'ildi.
- [x] Strict Isolation & Zero-Downtime VPS Sync:
  * `bestway` mustaqil ekotizimi mutlaqo daxlsiz saqlanadi.
  * VPS deploy faqat `grandec` (lms) konteynerlariga (`web`, `bot`, `celery-worker`, `nginx`) yo'naltiriladi va `curl.exe -fsS https://grandec.uz/healthz/` (HTTP 200 OK) orqali tekshiriladi.

### 2.32. Rasmiy Versiya v1.27.0: Ingliz Tili Imtihonlari (IELTS & CEFR Multi-level), Cambridge Split-Screen UI, Strict vs Practice Rejimlari, DeepSeek R1 Evidence-Based AI Feedback va Ball Konvertori
- [x] Ikki Xil Ishlash Formati (Strict Exam Mode vs Practice Mode):
  * Test boshlanishidan oldin rejim tanlash modali: [ 🛑 Strict Exam Mode ] va [ 💡 Practice / Study Mode ].
  * Strict Exam Mode: Fullscreen Enforcement (to'liq ekran), Tab/Window switch detection (window.onblur / visibilitychange) bilan 3 ta ogohlantirishdan keyin testni avtomatik yakunlash, nusxa olish (Ctrl+C, Ctrl+V) va kontekst menyuni bloklash, bir martalik Listening audio lock va server bilan sinxron taymer.
  * Practice Mode: Cheklovlarsiz erkin format, audioni qayta eshitish, savollar o'rtasida erkin harakatlanish va har bir savol tagida [ 💡 AI Tushuntirish ] tugmasi.
- [x] Kembrij 50/50 Split-Screen Dizayni (frontend/src/pages/tests/EnglishExamInterface.tsx):
  * Chap tomonda Reading matnlari (Passage tablari), o'ng tomonda savollar palitrasi.
  * Interaktiv sariq matn bo'yagich (Text Highlighter tool: <mark> elementi bilan ajratish).
  * Single choice, Multiple choice, Fill-in-the-blanks, Matching va Written savol turlari.
- [x] Evidence-Based AI Feedback Dvigateli (`deepseek/deepseek-r1-0528`):
  * `apps/tests/evidence_feedback.py`:
    - Reading/Listening Evidence Extraction: Direct Quote (matndagi aniq jumla), Why Wrong (o'quvchi nega xato qilgani va chalg'ituvchi tahlili), Synonym Matching (savol va matn sinonimlari tahlili).
    - Multi-level Writing BMB: 4 ta mezon (Task Achievement, Coherence, Lexical Resource, Grammar), 75 ballik shkala, C1 Word Upgrades (B1/B2 so'zlarni C1 darajadagi leksikaga almashtirish).
    - IELTS Writing: 4 ta mezon (TR, CC, LR, GRA), deduktiv baholash (Band 9.0 dan pasayish), Band 8.0+ Model Paragraph qayta yozilishi.
- [x] Ball Konvertori va Raqamli Sertifikat:
  * `apps/tests/score_converter.py` & `apps/tests/services/score_converter.py`:
    - IELTS Band (1.0-9.0) va CEFR Multi-level (A2, B1, B2, C1) shkalalariga avtomatik o'tkazish.
    - Kembrij yarim ballik yaxlitlash qoidasi (.25 -> .5, .75 -> 1.0).
    - Raqamli sertifikat kartasi API (`GET /api/tests/attempts/<id>/certificate-card/`).
- [x] 3 Tildagi Lokalizatsiya va API Integratsiyasi:
  * `frontend/src/i18n/translations.json` (UZ, RU, EN) yangi kalitlar bilan to'ldirildi.
  * `frontend/src/pages/TestDetail.tsx` da rejim tanlash modali ulandi va `/english-exam/:attemptId` yo'nalishiga o'tish amalga oshirildi.
- [x] Sifat Nazorati (QA Gate 100% PASS):
  * `pytest tests/test_english_exam_evidence_converter.py`: 13/13 test 100% muvaffaqiyatli o'tdi.
  * `ruff check apps/ tests/ config/`: 0 xatolik.
  * Frontend: `npm run build` 2.25 soniyada 0 xato bilan yig'ildi. `oxlint` 0 xato.
- [x] Strict Isolation & Zero-Downtime VPS Deploy:
  * `bestway` mustaqil loyihasi mutlaqo daxlsiz saqlanadi.
  * Contabo VPS (`169.58.58.229`) da yangilanishlar bajariladi va `https://grandec.uz/healthz/` (HTTP 200 OK) orqali tekshiriladi.

### 2.31. Rasmiy Versiya v1.26.0: Ustozlar CRM, Litsenziya Kvotalari, Kvitansiya OCR va AI Vocab Generator (100% Yashil CI, PR #100 va Zero-Downtime VPS Deploy)
- [x] Admin Kvotalari va Ustozlarning Litsenziya Boshqaruvi:
  * `TeacherProfile` modeli (`pro_quota_balance`, `premium_quota_balance`) yaratildi va `User` profiliga bog'landi.
  * Superadmin uchun `POST /api/v1/panel/teachers/<id>/allocate-quota/` endpointi orqali kvota taqsimlash imkoniyati taqdim etildi.
  * Ustozlar guruhida talaba yonida [ ⚡ PRO ] va [ 👑 VIP ] bir bosishli litsenziya faollashtirish tugmalari (`POST /api/v1/panel/teachers/activate-student-quota/`) joriy qilindi.
- [x] Ustozlar uchun To'liq Moliyaviy CRM va Davomat:
  * `GroupEnrollment` modelida `monthly_fee`, `billing_cycle_day`, `last_payment_date`, `next_payment_due`, `payment_status`, `parent_telegram_id`, `parent_phone` maydonlari qo'shildi.
  * `TeacherFinanceDashboard.tsx`: Tushumlar statistikasi, kutilayotgan tushum, qarzdorlar monitoringi va 1-klikli ommaviy Telegram eslatma yuborish.
  * `apps/webapi/views_crm.py`: `group_finance_summary_view`, `record_group_payment_view`, `send_group_payment_reminders_view`, `scan_receipt_view`.
- [x] Telegram Bot Avto-Eslatmalar va Ota-onalar Nazorati:
  * Celery Beat avto-vazifasi `check_group_tuition_due_dates_task`: To'lovga 2 kun qolganda ogohlantirish, to'lov kunida eslatma va muddat o'tganda muloyim qarz xabarnomasi.
  * Ota-onalar "Shaffof Nazorat" tizimi: `parent_telegram_id` ga avtomatik to'lov eslatmalari va davomat bildirishnomalari yetkazilishi.
  * `/finance` buyrug'i: Ustozlar uchun Telegram bot ichida guruhlar bo'yicha moliyaviy hisobot va qarzdorlarga eslatma yuborish.
- [x] Click / Payme Kvitansiya OCR Skaneri:
  * `apps/payments/receipt_scanner.py`: Click va Payme to'lov cheklaridan summa, sana va tranzaksiya ID sini avtomatik ajratib oluvchi Vision OCR va aqlli Regex parser.
  * Botda yuborilgan to'lov kvitansiyalari avtomatik tahlil qilinib, to'lov muddatini 30 kunga surish va ustozga tasdiqlash uchun xabar jo'natish integratsiyasi.
- [x] AI Lug'at (Vocabulary) Generatori va Interval Takrorlash (Spaced Repetition):
  * `apps/vocabulary/services/vocab_generator.py`: 50-60 ta so'zdan 4 formatli mashqlar (Multiple Choice, Spelling/Imlo, Eng ➔ Uzb, Uzb ➔ Eng) generatsiya qilish.
  * `VocabularyPack` va `StudentWordMistake` modellari, guruh darslariga biriktirish imkoniyati.
  * Ebbinghaus unutish egri chizig'i bo'yicha Telegram `/vocab` interaktiv viktorinasi (Quiz Poll) va 3 marta ketma-ket to'g'ri topish streak'i orqali so'zni yod olindi deb belgilash.
- [x] Frontend UI/UX:
  * `TeacherFinanceDashboard.tsx`, `TeacherVocabGenerator.tsx` yaratildi va `App.tsx` ga yo'naltirildi.
  * `Groups.tsx` da kvota berish tugmalari hamda CRM / Lug'at generatoriga to'g'ridan-to'g'ri havolalar joylashtirildi.
  * `npm run build` frontendda 4.31s da 0 xatolik bilan muvaffaqiyatli yig'ildi.
- [x] Sifat Nazorati va CI/CD (QA Gate 100% PASS):
  * `tests/test_crm_quota_vocab.py` va barcha regressiya testlari 100% muvaffaqiyatli o'tdi.
  * GitHub PR #100 ochildi va barcha tekshiruvlar (CodeQL, Analyze actions, Analyze js/ts, Analyze python, automerge, security pip-audit, test 1190+ test) 100% Yashil (Green CI) bo'ldi.
  * PR #100 `main` filialiga squash-merge qilindi va rasmiy **`v1.26.0`** relizi yaratildi.
- [x] Strict Isolation & Zero-Downtime VPS Deploy:
  * **Strict Isolation Rule:** `bestway` (bestwayec.uz) loyihasi barcha konteynerlari va ma'lumotlar bazasi mutlaqo daxlsiz saqlandi, 200 OK.
  * Contabo VPS (`169.58.58.229`) da `grandec` konteynerlari yangilandi, migratsiyalar bajarildi.
  * Jonli salomatlik tekshiruvi: `curl.exe -fsS https://grandec.uz/healthz/` (HTTP 200 OK, `db: true`), `https://grandec.uz/` (HTTP 200 OK).

### 2.30. Rasmiy Versiya v1.24.0: 100% Yashil CI (1219/1219 Test PASS), PR #99 Merge va Zero-Downtime VPS Deploy
- [x] Qat'iy Yagona Model Bog'lanishi va Deduksiya Usuli:
  * `config/settings/base.py`: Barcha baholash o'zgaruvchilari (`ESSAY_GRADER_MODEL`, `ESSAY_AI_MODEL`, `OPENROUTER_AI_MODEL`, `OPENROUTER_FALLBACK_MODELS`) qat'iy `AI_EVALUATION_MODEL = "deepseek/deepseek-r1-0528"` ga mixlandi.
  * Speaking audio oqimi `apps/speaking/services.py` orqali `fish-audio/s2.1-pro-free:free` modeliga, tahlil esa `deepseek/deepseek-r1-0528` ga ulandi.
  * Deduksiya bo'yicha baholash mexanizmi (maksimal balldan kamayib borish) to'liq tasdiqlandi.
- [x] Ochiq Ro'yxatdan O'tish RBAC Himoyasi:
  * Ro'yxatdan o'tishda `role=teacher` butunlay bekor qilinib, doimiy `student` qilib saqlanadi.
  * O'qituvchilar faqat admin tomonidan `POST /api/v1/panel/teachers/create/` orqali yaratiladi va ularga avtomatik test/esse huquqlari hamda PRO kirish beriladi.
- [x] Tariflar va UI Yangilanishi:
  * 4 talik responsiv kartochka tartibi (`grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6`) to'liq moslashtirildi.
  * Starter tarifi (5 000 so'm) UZ, RU, EN tillarida integratsiya qilindi.
- [x] To'liq Sifat Nazorati (QA Gate 100% PASS):
  * `ruff check .` va `ruff format --check .`: 0 xatolik, 435 fayl toza formatlangan.
  * Frontend: `oxlint` (0 xato), `tsc -b && vite build` (3.73 soniyada 0 xato bilan yig'ildi).
  * Backend: Mahalliy barcha 1219 ta test 100% muvaffaqiyatli o'tdi (1219 passed, 0 failed, 80 subtests passed).
- [x] GitHub Actions CI & PR #99:
  * Branch `feat/starter-tier-and-platform-stabilization` ochildi va push qilindi.
  * PR #99 ochildi va barcha 7 ta GitHub Actions tekshiruvlari (CodeQL, Analyze actions, Analyze js/ts, Analyze python, automerge, security, test) 100% Yashil (Green CI) natija bilan o'tdi.
  * PR #99 squash merge qilindi va yangi rasmiy `v1.24.0` relizi chop etildi.
- [x] Xavfsiz Zero-Downtime VPS Deploy:
  * **Strict Isolation Rule:** `bestway` (bestwayec.uz) loyihasi barcha konteynerlari va ma'lumotlar bazasi mutlaqo daxlsiz saqlandi, 200 OK.
  * `grandec.uz` VPS da konteynerlar (`web`, `nginx`, `celery`, `bot`) yangilandi.
  * Ommaviy tekshiruv: `curl -fsS https://grandec.uz/healthz/` (HTTP 200 OK), `https://grandec.uz/` (HTTP/2 200), `http://127.0.0.1:3005/` (HTTP 200 OK).


### 2.23. Dual-Track Dynamic Hero & Demo, Features Switcher va Onboarding Integratsiyasi (Landing 2.0)
- [x] Dual-Track Fan Tanlash Pill Switcheri (Hero & Navbar):
  * Bosh sahifa (Landing) yuqori qismida zamonaviy pill switcher: [ 🇺🇿 Ona tili va Adabiyot ] va [ 🇬🇧 English (IELTS & Multi-level) ].
  * Tanlov o'zgarganda Framer Motion animatsiyasi bilan sarlavhalar, nishonlar va interaktiv kartochkalar o'sha zahoti yangilanadi.
  * Tanlov localStorage.setItem('landing_subject', ...) va lms_subject ga saqlanadi hamda global subject-changed event tarqatadi.
- [x] Dinamik Hero Interaktiv Demo Vidjeti:
  * 🇺🇿 Ona tili rejimi:
    - ✍️ AI Esse (12 Mezon): Alisher Navoiy essesi, 54.5/60 (A daraja), 12 ta BMB rasmiy mezoni interaktiv bosiladigan ballar va izohlar bilan.
    - 📚 Fast CBT Test: Navoiy ijodiga oid test savoli, javob variantlari, bir zumda tahlil va konfetti animatsiyasi.
  * 🇬🇧 Ingliz tili rejimi:
    - ✍️ IELTS Writing AI: AI Task 2 essesi, Band 7.5, 4 ta IELTS mezonlari (TR, CC, LR, GRA) va interaktiv tahlil.
    - 🎙 AI Speaking: Part 2 Cue Card, Band 7.5, jonli ovoz to'lqini (waveform), Play/Pause simulyatsiyasi, matn ta'kidlanishi va batafsil tahlil.
    - 🎧 CBT Reading & Listening: Kembrij formati test savoli, tezkor tahlil va konfetti animatsiyasi.
- [x] Dinamik Imkoniyatlar (Features) Bo'limi:
  * Tanlangan fanga qarab 'Features' bo'limidagi barcha kartochkalar mos ravishda Ona tili yoki IELTS/Multi-level xususiyatlariga o'zgaradi.
- [x] OnboardingModal va Ro'yxatdan O'tish Integratsiyasi:
  * 'Bepul boshlash' bosilganda OnboardingModal Landingda tanlangan fanni avtomatik o'qib oladi va foydalanuvchiga to'g'ri fanni ko'rsatadi.
- [x] Sifat Nazorati (QA Gate):
  * Frontend: oxlint 0 xato, 	sc -b && vite build 0 xato bilan 3.42 soniyada muvaffaqiyatli yig'ildi.
  * Backend: 
uff check apps/ 0 xato, pytest tests/test_spa_contract.py 20/20 test 100% PASS.

### 2.24. Qat'iy 2 Bosqichli Tanlov Tizimi (Hierarchical Subject & Exam Selector) va 4 Yo'nalishli Dinamik Hero (Landing 2.1)
- [x] 2 Bosqichli Hierarxik Tanlov Tizimi (Hero & Navbar):
  * 1-daraja (Asosiy fan): [ 🇺🇿 Ona tili va Adabiyot ] va [ 🇬🇧 English (Ingliz tili) ].
  * 2-daraja (Imtihon yo'nalishi):
    - Ingliz tili tanlanganda: [ 🎓 IELTS (Academic & General) ] va [ 🎯 CEFR Multi-level (B2 / C1) ].
    - Ona tili tanlanganda: [ 🎓 Milliy sertifikat (BMB) ] va [ 👨‍🏫 Attestatsiya 2026 ].
  * Framer Motion animatsiyalari bilan silliq almashinuv, tanlov localStorage.setItem('grandec_selected_track', ...) ga yoziladi va Onboarding modali bilan to'liq sinxronlashadi.
- [x] 4 Yo'nalish Uchun Alohida Dinamik Hero Matnlari va Ishonch Nishonlari:
  * IELTS: 🎯 IELTS Academic & General (Band 1.0–9.0), 15 soniyada Band Score, 4 ta rasmiy IELTS mezoni, Real-vaqt AI Speaking tahlili.
  * Multi-level: 🎯 Davlat CEFR Multi-level imtihoni (B2 / C1 darajasi), B2/C1 ball kafolati, Rasmiy DTM/BMB formati, Interaktiv CBT simulyator.
  * Milliy sertifikat: ⭐️ BMB Davlat standarti — Ona tili va adabiyot (2026), 15s AI Esse tahlili, 12 ta rasmiy BMB mezoni, Real-vaqt 1v1 Arena.
  * Attestatsiya 2026: 👨‍🏫 O'qituvchilar Attestatsiyasi (70% ustama), 50 talik to'liq format, 70% ustama kafolati, Bo'limlar bo'yicha tahlil.
- [x] 4 Yo'nalish Uchun Alohida Interaktiv Hero Live Demo Vidjeti:
  * IELTS: Writing Task 2 (Band 7.5, 4 ta TR/CC/LR/GRA mezonlari), AI Speaking (Part 2 Cue Card, Band 7.5, ovoz to'lqini simulyatori), Cambridge CBT Reading.
  * Multi-level: Formal proposal (184 so'z, C1, 4 ta CEFR mezonlari), DTM/BMB 35 talik Reading CBT.
  * Milliy sertifikat: Navoiy essesi (54.5/60, A daraja, 12 BMB mezoni), Navoiy Fast CBT Test.
  * Attestatsiya 2026: Pedagogik mahorat savoli (formativ baholash, konfetti), 50 talik Toifa Diagnostikasi (46/50 ball, 92%, Oliy toifa 70% ustama).
- [x] 4 Yo'nalish Uchun Alohida Dinamik Imkoniyatlar (Features) Bloki:
  * Har bir imtihon turi uchun 3 tadan ixtisoslashgan karta (IELTS Writing + Speaking + CBT; Multi-level Writing + 35 talik test + Lug'at Arenasi; Milliy sertifikat Esse + Test + 1v1 Arena; Attestatsiya 50 talik test + Metodik keyslar + Toifa/Ustama monitoringi).
- [x] Sifat Nazorati (QA Gate):
  * Frontend: oxlint 0 xato, 	sc -b && vite build 0 xato bilan 2.77 soniyada muvaffaqiyatli yig'ildi.
  * Backend: 
uff check apps/ 0 xato, pytest tests/test_spa_contract.py 20/20 test 100% PASS.

### 2.29. Qat'iy Yagona Baholovchi Model (deepseek/deepseek-r1-0528), Audio Stream (fish-audio/s2.1-pro-free:free) va Deduksiya Usuli
- [x] Qat'iy Yagona Baholovchi Model — `deepseek/deepseek-r1-0528`:
  * `config/settings/base.py` va `apps/essays/services.py` da barcha baholash modellari faqat `deepseek/deepseek-r1-0528` ga qat'iy bog'landi. Arzon yoki sun'iy cheklovchi modellar chiqarib tashlandi.
  * 🇺🇿 Ona tili va Adabiyot (Milliy sertifikat va Attestatsiya 2026): BMB 12 ta rasmiy mezonlari asosida to'liq tahlil.
  * 🇬🇧 Ingliz tili IELTS Writing (Task 1 va Task 2): 4 ta rasmiy mezon (TR, CC, LR, GRA) bo'yicha Band 1.0–9.0 tahlili.
  * 🎙 IELTS Speaking tahlili: talabaning audio nutqi matnga aylantirilgach, leksika, grammatika, ravonlik va talaffuzni baholash.
- [x] Deduksiya Usuli Bo'yicha Ball Qo'yish Mantig'i:
  * Baholash har doim maksimal balldan (Ona tilida 20.0, IELTS'da 9.0) boshlanadi.
  * Har bir aniqlangan xato (imlo, punktuatsiya, mantiqiy uzilish, grammatik xatolik) uchun aniq mezon bo'yicha ball ayirib boriladi.
  * Har bir ayirilgan ballning sababi va matndagi o'rni talabaga ko'rsatiladi ("errors" va "reason").
- [x] Audio Stream Modeli — `fish-audio/s2.1-pro-free:free`:
  * `apps/speaking/services.py`: Audio oqimi va nutqni matnga o'girish uchun `fish-audio/s2.1-pro-free:free` modeli OpenRouter orqali ulandi.
  * Talabaning audio javobi audio model orqali qayta ishlanib, yakuniy baholash uchun `deepseek/deepseek-r1-0528` ga yuboriladi.
- [x] Ochiq Ro'yxatdan O'tish Xavfsizligi:
  * `RegisterModal.tsx` va `Register.tsx` da "O'qituvchiman" roli yo'q, hamma yangi registratsiyalar faqat `student` rolida saqlanadi.
  * O'qituvchilarni faqat Admin yaratishi mumkin (`POST /api/v1/panel/teachers/create/`).
- [x] Server Kiberxavfsizlik Auditi:
  * **Strict Isolation Rule:** `bestway` (bestwayec.uz) daxlsiz saqlandi, unga teginilmadi, 200 OK.
  * Serverda 0 ta begona miner/konteyner/port aniqlandi.
- [x] QA Gate & VPS Deploy:
  * `pytest tests/test_teacher_auth_deepseek.py`: 11/11 test 100% PASS.
  * `npm run lint` & `npm run build`: 0 xato bilan yig'ildi.
  * VPS deploy muvaffaqiyatli yakunlandi, `https://grandec.uz/healthz/` 200 OK (`version 1.20.0`), `https://grandec.uz/` 200 OK.

### 2.28. Server Kiberxavfsizlik Auditi, Ochiq Ro'yxatdan O'tish RBAC Himoyasi, DeepSeek AI Esse Grader va 4 Talik Tariflar Tizimi
- [x] Server Kiberxavfsizlik Auditi (Contabo VPS 169.58.58.229):
  * **Strict Isolation Rule:** `bestway` (bestwayec.uz) loyihasi barcha konteynerlari (`education-web-prod`, `education-backend-prod`, `education-postgres-prod`, `education-redis-prod`), ma'lumotlar bazasi va portlari (`127.0.0.1:3005`) daxlsiz saqlandi, 0 ta to'xtalish, 200 OK.
  * Server jarayonlari, portlar (`ss -tulpn`) va cronlar tekshirildi: 0 ta begona miner, botnet yoki orqa eshik aniqlandi.
- [x] Ochiq Ro'yxatdan O'tishdagi Xavfsizlik Teshigini Yopish:
  * Frontend: `Register.tsx` va `AuthModal.tsx` dagi "Platformadagi rolingiz" ("O'quvchiman" / "O'qituvchiman") tanlovi to'liq olib tashlandi.
  * Backend: `RegisterSerializer` da rol qat'iy `User.Role.STUDENT` ga majburlab mixlandi (mijoz yuborgan har qanday 'role' qiymati e'tiborsiz qoldiriladi).
  * Administrator boshqaruvi: Yangi o'qituvchilarni yaratish uchun maxsus admin-only endpoint yaratildi: `POST /api/v1/panel/teachers/create/` va `POST /api/v1/admin/teachers/create/` (`IsPanelAdmin` ruxsatnomasi bilan).
- [x] DeepSeek AI Esse Baholash Tizimi Integratsiyasi:
  * `config/settings/base.py`: `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL` va `ESSAY_GRADER_MODEL` integratsiyasi o'rnatildi.
  * `apps/essays/deepseek_grader.py` va `apps/essays/services.py`:
    - Rasmiy 12 mezonli BMB Ona tili esselarini (`grade_bmb_essay_deepseek`) DeepSeek orqali baholash.
    - Rasmiy 4 mezonli Cambridge IELTS esselarini (`grade_ielts_essay_deepseek`) Task Response, Coherence & Cohesion, Lexical Resource, Grammatical Range bo'yicha Band 1.0–9.0 baholash.
    - Avtomatik model zanjiri va xatoliklarda muammosiz fallback.
- [x] 4 Talik Zamonaviy Tariflar Matritsasi:
  * Bepul (0 so'm), Starter (5 000 so'm/test to'plami), PRO (49 000 so'm/oy), PREMIUM (89 000 so'm/oy).
  * Frontend UI (`Landing.tsx`, `Subscribe.tsx`, `Plans.tsx`) 4 ta responsiv kartochka formatiga yangilandi.
  * Tarjimalar bazasi `translations.json` ga barcha `plan_starter_*` kalitlari UZ, RU, EN tillarida qo'shildi.
- [x] Sifat Nazorati (QA Gate 100% PASS):
  * Unit testlar: `tests/test_teacher_auth_deepseek.py` 9/9 test 100% PASS (ro'yxatdan o'tish himoyasi, admin o'qituvchi yaratishi, jonli DeepSeek BMB va IELTS baholash).
  * Frontend: `oxlint` 0 xato, `tsc -b && vite build` 0 xato bilan 3.07 soniyada muvaffaqiyatli yig'ildi.
  * Backend: `python -m ruff check apps/ tests/` 0 xato.
  * Deploy: Contabo VPS (`169.58.58.229`) ga muvaffaqiyatli sync qilindi, `https://grandec.uz/healthz/` va `https://grandec.uz/` 200 OK qaytardi, `bestway` daxlsiz saqlandi (200 OK).

### 2.27. To'liq Tizim Auditi (/audit), Xavfsizlik & RBAC Himoyasi, Aktivlar Tozalanishi va Zero-Downtime Deploy
- [x] 1-bosqich: Fayllar va bog'liqliklar auditi (apps/, frontend/src/, config/):
  * Barcha 20 ta Django ilovasi, 46 ta React sahifasi va 24 ta komponent to'liq tahlil qilindi.
  * O'lik aktivlar (`frontend/src/assets/hero.png`, `react.svg`, `vite.svg`) aniqlandi.
  * Ishlatilmayotgan og'ir kutubxonalar (`three`, `@react-three/fiber`, `@react-three/drei`, `@types/three`, `gsap`, `motion`) aniqlandi.
- [x] 2-bosqich: Ortiqcha va eskirgan kodlarni xavfsiz tozalash:
  * Ishlatilmayotgan frontend aktivlari o'chirildi (`hero.png`, `react.svg`, `vite.svg`).
  * `frontend/package.json` dan foydalanilmayotgan paketlar tozalandi, bundle vaqtida 0 xato bilan yig'ildi.
  * `apps/certificates/views.py` dagi ulanmagan va xatoga moyil `certificate_web_download_view` olib tashlandi.
- [x] 3-bosqich: Xavfsizlik va Mantiqiy Buglarni Tuzatish (RBAC & Error Handling):
  * `apps/organizations/views.py`: `monthly_report_pdf_view` dagi mantiqiy xato tuzatildi — begona ustozlar boshqa ustozning guruh hisoboti va talabalarini yuklay olmaydi (faqat guruh ustozi yoki admin/staff yuklay oladi).
  * `apps/organizations/views.py`: B2B Enterprise boshqaruv endpointlari (`enterprise_dashboard_view`, `enterprise_bulk_import_view`, `enterprise_report_export_view`, `branding_update_view`) student rolidan 403 Forbidden bilan qat'iy himoyalandi.
  * `apps/speaking/views.py`: `SpeakingSubmissionDetailView` dagi RBAC mustahkamlandi — ustoz faqat o'ziga biriktirilgan guruhdagi o'quvchilarning speaking yozuvlarini eshita oladi.
  * `apps/essays/views.py`: `_safe_render_partial` xavfsiz JSON fallback mexanizmi joriy etildi — shablon mavjud bo'lmaganda 500 xato o'rniga toza JSON qaytariladi.
- [x] 4-bosqich: UI/UX, Kontrast va Mobil Moslashuvchanlikni Silliqlash:
  * `SpeakingPractice.tsx` va `SpeakingTopics.tsx`: Light rejimda qorong'i fonda qora matn ko'rinmay qolish muammosi `var(--card)` va moslashtirilgan nishonlar yordamida to'liq bartaraf etildi.
  * `Groups.tsx`: Brending modali fonidagi qora `#0f172a` qatlami `var(--card)` va `var(--border)` ga almashtirildi (Light/Dark mosligi).
  * `Register.tsx` va `AuthModal.tsx`: O'rtadagi ajratuvchi chiziq matni foni `var(--card)` ga moslashtirildi.
  * `frontend/src/index.css` & `Tma.css`: `.content` va mobil `.single-q-actions` ga `env(safe-area-inset-bottom, 0px)` qo'shildi, mobil ekranlardagi pastki Home-bar tugmalarni to'sib qo'ymaydi.
  * `frontend/src/lib/testing.ts`: Test topshirishda qoralamani saqlash `localStorage` ga o'tkazildi (mobil tab yopilganda yozma javoblar yo'qolmaydi).
- [x] 5-bosqich: Sifat Nazorati (QA Gate 100% PASS):
  * `python -m ruff check apps/`: 0 xato, barcha tekshiruvlardan o'tdi.
  * `pytest`: 1196 ta backend testi 100% PASS, audit xavfsizlik testlari (`tests/test_audit_fixes.py`) 10/10 PASS.
  * `npm run lint`: oxlint 0 xato.
  * `npm run build`: tsc va vite build 2.62 soniyada 0 xato bilan yig'ildi.

### 2.25. To'liq 3 Tilli Tarjimalar Bazasini To'ldirish va Xavfsiz Fallback Tizimi (Landing i18n Fix)
- [x] Translations.json Fayliga Barcha Kalitlarni Qo'shish:
  * Navbar kalitlari (
av_comparison, 
av_pricing, 
av_faq) UZ, RU, EN tillarida kiritildi.
  * FAQ bloki kalitlari (aq_eyebrow, aq_title_1, aq_title_2, aq_q1..aq_q5, aq_a1..aq_a5) 3 tilda to'liq kiritildi.
  * Tariflar va rejalar kalitlari (pricing_*, plan_free_*, plan_pro_*, plan_master_*) 3 tilda to'liq kiritildi.
  * Taqqoslash jadvali kalitlari (cmp_*) 3 tilda to'liq kiritildi.
  * Qo'shimcha Landing kalitlari (eature_card_tests_*, oot_*, stats_*, cta_banner_*, essay, 	est) 3 tilda to'liq kiritildi.
  * Jami Landing sahifasidagi 105 ta kalit UZ, RU va EN tillarida 100% to'liq qamrab olindi (0 ta yetishmayotgan kalit).
- [x] Xavfsiz Tarjima Fallback Tizimi (LangContext.tsx):
  * 	ranslate(key, lang, fallback?) va 	(key, fallback?) funksiyalariga KNOWN_SAFE_FALLBACKS hamda ormatRawKeyFallback himoyasi o'rnatildi.
  * Agar kalit bazada topilmasa yoki bo'sh bo'lsa, xom texnik kalit emas, chiroyli formatlangan so'z yoki fallback matni qaytariladi.
- [x] Sifat Nazorati (QA Gate):
  * Frontend: oxlint 0 xato, 	sc -b && vite build 0 xato bilan yig'ildi (Landing-CsX73DzK.js, LangContext-BgdU5dXl.js).
  * Backend: 
uff check apps/ 0 xato, pytest tests/test_spa_contract.py 20/20 test 100% PASS.

---

---

---

---

## 2. Bajarildi

### 2.1. Obuna Narxlari va To'lov Tizimi (`frontend/` & `apps/payments/`)
- [x] `frontend/src/pages/Subscribe.tsx`:
  - `PLAN_PRICES` konstanta o'rnatildi: `starter: 15000, pro: 49000, premium: 60000`.
  - Kartaga o'tkazish to'lov modalida PRO summasi qat'iy 49 000 so'm qilib belgilandi.
- [x] `frontend/src/pages/Plans.tsx`:
  - PRO oylik tarifi narxi 49 000 so'm qilib belgilandi.
- [x] `frontend/src/i18n/translations.json`:
  - `"usage_sponsored"` yozuvi `"PRO (Ustoz guruhi orqali)"` (UZ), `"PRO (через группу учителя)"` (RU), `"PRO (via Teacher Group)"` (EN) ga yangilandi.
- [x] `apps/payments/migrations/0012_fix_pro_plan_price.py`:
  - Bazadagi `SubscriptionPlan` jadvallarida PRO narxi 49 000 so'm, Starter 15 000 so'm, Premium 60 000 so'm qilib yangilandi va production bazasida muvaffaqiyatli migrate qilindi.
- [x] `apps/webapi/views_billing.py`:
  - `/api/v1/payments/card-info/` API endpointida `pro_price = 49000` UZS bo'lishi ta'minlandi.

### 2.2. Ustoz Ro'yxatdan O'tishi va Avtomatik PRO (Auto-Delegated PRO)
- [x] `apps/accounts/serializers.py` & `apps/accounts/models.py`:
  - Ro'yxatdan o'tishda `role = 'teacher'` tanlanganda xavfsiz qabul qilinadi, `can_create_test = True` va `can_create_essay_topic = True` avtomatik o'rnatiladi.
  - `User.has_pro_access` va `Profile.has_pro_access` xususiyatlari qo'shildi.
- [x] `apps/courses/group_service.py`:
  - `join_group_by_invite_code` funksiyasiga `_activate_student_pro_for_group` biriktirildi: o'quvchi taklif kodi (`#GR-XXX`) bilan guruhga qo'shilishi bilanoq, `profile.plan = 'pro'`, 365 kunlik `UserSubscription` va tasdiqlangan `TeacherSponsorship` yaratiladi.
  - `get_group_full_analytics` va `export_group_to_excel` hisobotlariga "Tarif" ustuni va `⭐ PRO (Faol)` nishoni kiritildi.
- [x] `apps/payments/entitlements.py`:
  - Guruhga biriktirilgan o'quvchi uchun `plan_name = "PRO (Ustoz guruhi orqali)"` va `is_unlimited_tests = True` server darajasida kafolatlandi.
- [x] `apps/payments/ai_quota.py`:
  - Ustoz guruhidagi talabalarga avtomatik ravishda `pro` tier (kunlik 50 ta AI kvotasi) berilishi ta'minlandi.
- [x] `apps/webapi/serializers.py`:
  - `GroupMemberSerializer` ga `has_pro`, `pro_status_label`, `tests_count` va `essays_count` maydonlari qo'shildi.

### 2.3. Frontend Ustoz va O'quvchi Interfeyslari
- [x] `frontend/src/pages/Register.tsx` & `frontend/src/components/AuthModal.tsx`:
  - Rol tanlash toggle tugmalari qo'shildi (`[ 🎓 O'quvchiman ]` va `[ 👨‍🏫 O'qituvchiman ]`).
- [x] `frontend/src/pages/TeacherDashboard.tsx`:
  - Ustoz kabinetidagi talabalar jadvalida `Tarif` (`⭐ PRO (Faol)`), `Testlar soni` va `Esselar soni` ustunlari joylashtirildi.
- [x] `frontend/src/pages/Groups.tsx`:
  - Guruh monitoringi jadvaliga `Tarif` ustuni va har bir o'quvchi uchun PRO faol nishoni qo'shildi.

### 2.4. Attestatsiya 2026 Diagnostika Testi
- [x] `seed_attestatsiya_test_2026`: 50 ta rasmiy attestatsiya savoli (Ona tili va Adabiyot) bazaga kiritildi (Test ID: 3, `#MOCK-ATTEST2026`).
- [x] `frontend/src/pages/Tests.tsx`: Toifalar filtri (Barchasi, Milliy Sertifikat, Attestatsiya, 1v1 Arena) va 1-klikli ulanish tugmasi qo'shildi.

### 2.5. Sifat, Testlash va Production Deploy
- [x] `npm run build` — Frontend TypeScript va Vite 0 xato bilan yig'ildi (3.19s).
- [x] `pytest tests/test_teacher_group_auto_pro.py` — 2 ta yangi test 100% o'tdi.
- [x] `pytest tests/test_telegram_bot_features.py` — Barcha 27 ta test 100% o'tdi.
- [x] Git commits Komiljon Roziyev (`kruziyev0@gmail.com`) muallifligida, AI belgilari va atributlarsiz `main` ga push qilindi.
- [x] VPS (`169.58.58.229`) da Docker multi-stage build orqali `web` va `bot` konteynerlari qayta yig'ildi va ishga tushirildi.
- [x] `curl -I https://grandec.uz/healthz/` -> **HTTP 200 OK** tasdiqlandi.
- [x] `curl -fsS https://grandec.uz/api/v1/payments/card-info/` -> PRO narxi 49 000 so'm ekanligi jonli serverda tasdiqlandi.

### 2.6. Esse So'zlar Chegarasi (200–500) & AI Baholash Integratsiyasi
- [x] `apps/essays/validators.py` yaratildi: `MIN_WORDS_DEFAULT = 200`, `MAX_WORDS_DEFAULT = 500`.
- [x] `apps/essays/models.py`: `EssayTopic.word_limit_min` default qiymati 200 qilib belgilandi.
- [x] `apps/essays/services.py` & `apps/essays/prompts.py`: AI esse baholash tizimi 12 mezon bo'yicha 200–500 so'z talabini hisobga oladi; 200 so'zdan kam esselar uchun xulosa ogohlantirishi beriladi.
- [x] `frontend/src/components/ExamQuestions.tsx`, `frontend/src/pages/EssayWrite.tsx`, `PanelTopics.tsx`:
  - 3 holatli jonli so'zlar hisoblagichi (Live Word Counter):
    * 0–199 so'z: Sariq/amber ogohlantirish (`⚠️ Yetarli emas: {count}/200 so'z`)
    * 200–500 so'z: Zumrad yashil (`✓ Ideal hajm: {count} so'z`)
    * 500+ so'z: Qizil ogohlantirish (`❌ Hajm oshib ketdi: {count}/500 so'z`)

### 2.7. Rasmiy BMB Diagnostika Brendingi
- [x] Saytdan barcha "Umid Shukurov" nomlari olib tashlandi.
- [x] Test nomi rasmiy: "Ona tili va Adabiyot — BMB Rasmiy Mock Test".
- [x] Mock kodi: `#MOCK-BMB-DIAGNOSTIC` (orqaga moslik uchun `#MOCK-SHUKUROV` ham saqlangan).
- [x] Esse mavzusi: "Nafaqaga chiqish yoshi chegarasi va kadrlar salohiyati (BMB Rasmiy Mock)".

### 2.8. Responsive & Adaptive CBT Imtihon Interfeysi
- [x] Mobil (< 768px):
  - O'qish matnlari akordeon rejimi (`📖 Matnni ko'rish (Qismlar bo'yicha)`) orqali ixcham ochilib-yopiladi.
  - Savollar palitrasi (1–45) gorizontal silliq skrollanadi.
  - Navigatsiya tugmalari (`[ ← Oldingi ]` va `[ Keyingi → ]`): ekranning pastiga yopishgan (sticky bottom) shaffof blur qatlam bilan qotirilgan, tagidagi kontent yopilib qolmasligi uchun bufer masofa qoldirilgan.
- [x] Desktop (>= 1024px):
  - Chap tomonda matn va lug'at, o'ng tomonda aktiv savol va variantlar qulay ikkiga bo'lingan (split-screen).
  - 180 daqiqalik taymer doimiy tepada ko'rinib turadi (`.take-test-sticky-top`).
- [x] Barcha qurilmalarda: Variantlar teginish uchun qulay (`min-height: 48px`, faol bosilish effekti).

### 2.9. Telegram Botda Ustoz-Guruh, Kurs To'lovlari (Tuition), Ota-onalar Nazorati va Davomat
- [x] Ustoz va Guruh nazorati (`apps/notifications/bot/handlers.py`):
  - Ustoz `/my_groups` yoki `[ 👥 Guruhlarim ]` orqali guruh yaratish va taklif kodini (`#GR-XXX`) olish.
  - O'quvchi botga ushbu kodni yozishi bilan avtomatik guruhga qo'shiladi va PRO tarifi ulanadi.
  - `/students` va `[ 👥 O'quvchilar va BMB ]` orqali guruh a'zolari, ishlagan testlari, esselari va rasmiy BMB darajalari (A+, A, B...) to'liq ko'rsatiladi.
- [x] Kurs to'lovlari (Tuition Billing — Bot orqali):
  - Yangi model: `StudentTuition` (`student`, `group`, `monthly_fee`, `due_date`, `status: paid/pending/overdue`, `paid_at`).
  - Ustoz guruh kartasida `[ 💳 To'lov holati ]` tugmasi orqali to'lovlarni ko'rish va 1 tugma bilan `paid` qilish.
  - Bot avtomatik eslatmalari (`send_tuition_due_alerts_task`): to'lovga 2 kun qolganda va to'lov kunida o'quvchi va ota-onaga Telegram orqali eslatma.
- [x] Ota-onalar nazorati (Smart Alerts):
  - `/parent_link <phone>` va `/parent_start <kod>` orqali ota-onani o'quvchiga ulash.
  - Test topshirilganda darhol ball, foiz va BMB darajasi yuboriladi (`send_parent_test_alert_task`).
  - Esse baholanganda AI va ustoz xulosasi yetkaziladi (`send_parent_essay_alert_task`).
  - Yakshanba 18:00 da haftalik jamlangan o'sish hisoboti yuboriladi (`send_parent_weekly_digest_task`).
- [x] Davomat (Attendance) va Uyga vazifa (Homework):
  - Dars boshida bot orqali davomat olinadi; darsga kelmagan bolaning ota-onasiga 15 daqiqada ogohlantirish xabari boradi (`send_parent_absence_alert_task`).
  - `/new_homework <vazifa>` orqali uyga vazifa berish, o'quvchilarga Telegram eslatma yuborish.
- [x] Guruhlararo reyting va Excel eksport:
  - `/group_leaderboard` orqali markaz guruhlarining o'rtacha ball bo'yicha TOP-10 reytingi.
  - `/export_group_report` orqali 1 soniyada guruh natijalarining rasmiy rangli Excel jadvali fayl qilib yuboriladi.

### 2.10. Veb-panel Sinxronizatsiyasi, Sifat Tekshiruvi va Migratsiyalar
- [x] `apps/courses/group_service.py` & `frontend/src/pages/Groups.tsx`:
  - Guruh tahlili va talabalar monitoringi jadvaliga "To'lov" ustuni qo'shildi (`To'langan`, `Kutilmoqda`, `Muddati o'tgan`).
  - Excel eksport fayliga "To'lov holati" ustuni qo'shildi.
- [x] Migratsiyalar:
  - `apps/courses/migrations/0005_homework_homeworksubmission.py`
  - `apps/tuition/migrations/0002_studenttuition.py`
  - `apps/essays/migrations/0019_alter_essaytopic_word_limit_min.py`
- [x] Testlar:
  - `npm run build`: Frontend TypeScript va Vite 0 xatolik bilan yig'ildi.
  - `pytest tests/test_tuition_student_model.py`: 100% PASS (2/2).
  - `pytest tests/test_teacher_bot_commands.py`: 100% PASS (27/27).
  - `pytest tests/test_teacher_group_auto_pro.py` & `test_teacher_group_reports.py`: 100% PASS (23/23).

### 2.11. BMB Rasmiy 12 ta Mezoni Asosida Esse Baholash Tizimi (DeepSeek AI & 20 Ballik Shkala)
- [x] Model va API integratsiyasi:
  - OpenRouter orqali `deepseek/deepseek-v4-flash-0731` modeli ulandi.
  - Qat'iy va xolisona baholash uchun `temperature: 0.1` o'rnatildi.
  - Production muhiti uchun `OPENROUTER_API_KEY` xavfsiz tarzda GitHub Secrets orqali VPS muhitiga avtomatik sinxronlashtirildi.
- [x] BMB Rasmiy 12 Mezonli 20 Ballik Shkala (`apps/essays/services.py`, `prompts.py`, `models.py`):
  - 1. Mavzuning to'liq va teran ochib berilishi (max 2.0)
  - 2. Fikrning mantiqiy izchilligi va kompozitsion yaxlitlik (max 2.0)
  - 3. Dalillash mahorati va misollar keltirilishi (max 2.0)
  - 4. Publitsistik uslub me'yorlariga rioya qilingani (max 1.5)
  - 5. So'z qo'llash aniqligi va boy lug'at zaxirasi (max 1.5)
  - 6. Grammatik qoidalarga rioya etilgani (max 1.5)
  - 7. Imlo (orfografiya) to'g'riligi va xatolar tahlili (max 2.0)
  - 8. Tinish belgilari (punktuatsiya) to'g'ri qo'llangani (max 1.5)
  - 9. Uslubiy xatolar va takrorlarning mavjud emasligi (max 1.5)
  - 10. Matnning o'ziga xosligi va mustaqil fikrlash darajasi (max 1.5)
  - 11. Matn hajmi (200–500 so'z oralig'i) (max 1.5)
  - 12. Xulosaning asosli va tugallangan bo'lishi (max 1.5)
  - Jami: Qat'iy 20.0 ball.
- [x] Kengaytirilgan Tahlil va SHA-256 Determinizm:
  - Imlo xatolari jadvali: xato so'z, to'g'ri varianti va qoida izohi (`spelling_errors`).
  - Kuchli tomonlar (`strengths`), zaif tomonlar (`weaknesses`), ustoz tavsiyasi (`teacher_recommendation`).
  - Matnning AI tomonidan xatolarsiz takomillashtirilgan varianti (`improved_text`).
  - SHA-256 kontent xeshi orqali bir xil matnlar uchun zudlik bilan qayta baholashsiz keshdan berish.
- [x] Frontend va Telegram Bot Interfeyslari:
  - Veb natijalar sahifasida 12 ta mezon rangli progress bar ko'rinishida, matnda imlo xatolarini interaktiv belgilash (highlight), Oldin / Keyin taqqoslash rejimi.
  - Telegram botda BMB standarti bo'yicha baho / 20, aniqlangan xatolar, [ 🪄 AI tahririni ko'rish ] va [ 📄 Batafsil PDF xulosa ] tugmalari.
- [x] Sifat, Testlar va Production Deploy:
  - Barcha esse testlari: 115/115 (100% PASS).
  - Frontend Vite build: 0 xatolik bilan yig'ildi.
  - Production deploy: GitHub Actions orqali VPS ga to'liq yetkazildi va ishga tushirildi.
  - Jonli tekshiruv: `https://grandec.uz/healthz/` va `https://grandec.uz/` -> HTTP 200 OK.

### 2.12. Mobil CBT Imtihonida D Varianti Ko'rinishini To'g'rilash (Zero-Downtime Hotfix)
- [x] Muammo tahlili: Mobilda pastki qotirilgan (`position: fixed; bottom: 0`) navigatsiya paneli ("Oldingi" / "Keyingi") 4-variant (D varianti) ustiga chiqib, uni to'sib qo'yayotgan edi.
- [x] Yechim:
  - `frontend/src/pages/TakeTest.tsx`:
    * Savol kartochkasi (`.take-test-card.single-view`) va variantlar konteyneriga (`.take-test-choices`) mobilda `paddingBottom: '140px'` bo'sh joy qo'shildi.
    * Variant tugmalari orasidagi masofa `gap: 10px` (`space-y-2.5`), balandligi `min-height: 48px`, ichki bo'shligi `padding: 14px 16px` (`py-3.5 px-4`) qilib barmoq bilan bosishga moslashtirildi.
    * Mobilda oxirigacha skroll qilinganda D varianti pastki qotirilgan panel ustidan 70px+ yuqorida to'liq, erkin va ochiq ko'rinishi ta'minlandi.
  - `frontend/src/index.css`:
    * `@media (max-width: 767px)` da `.take-test-page-container` uchun `padding-bottom: 160px !important`, `.take-test-card.single-view` va `.take-test-choices` uchun `padding-bottom: 140px !important` qat'iy o'rnatildi.
- [x] Yig'ish va Deploy:
  - `npm run build` — 0 xatolik bilan 1.99s da muvaffaqiyatli yig'ildi.
  - Git commit: `fix(cbt-mobile): add bottom padding to prevent fixed bar overlapping option D`.
  - Zero-downtime deploy: Foydalanuvchilar yoki faol test topshirayotganlar uzilmagan holda jonli serverga chiqdi.
  - Jonli tekshiruv: `https://grandec.uz/healthz/` va `https://grandec.uz/` -> HTTP 200 OK.

### 2.13. Test Topshirishda Javoblarni Saqlash Barqarorligi, Ochiq Savollar va Natijalar Sahifasidagi To'g'ri Javoblar (Hotfix)
- [x] Javob Saqlash Barqarorligi (`frontend/src/pages/TakeTest.tsx`):
  - Autosave funksiyasiga 400ms debounce o'rnatildi.
  - Avtomatik 3 martagacha qayta urinish (retry mexanizmi) joriy qilindi: tarmoq kechikishi yoki uzilishida o'quvchiga xatolik chiqarmasdan avtomatik ravishda qayta saqlaydi.
  - O'quvchi javobni tanlaganda yoki yozganda birinchi navbatda javob darhol `localStorage`ga (`persist(next)`) yozilishi ta'minlandi, shunda sahifa yangilansa yoki tarmoq uzilsa ham javob yo'qolmaydi.
  - API ga yuborilayotgan parametrlar (`test_id`, `question_id`, `choice_ids`, `selected_option_id`, `text_answer`, `gap_answers`, `matching`, `written_text`) to'liq tekshirildi va `SaveAnswerSerializer` bilan unifikatsiya qilindi.
- [x] Ochiq va 2 Talik Savollar (36–44-savollar):
  - 2 talik savollarda (a va b maydonlari) o'quvchi kiritgan qiymatlar yagona to'g'ri `a) [javob1]; b) [javob2]` formatida saqlanishi va parse qilinishi ta'minlandi.
  - Backendda (`apps/tests/scoring.py` va `apps/tests/services.py`): apostroflar (`'`, `‘`, `’`, `ʻ`, `ʼ`), tinish belgilari va ikki qismli tuzilmani hisobga oluvchi moslashuvchan `evaluate_text_answer()` baholash mexanizmi ulandi (36: "So'zida turmoq", 37: "Tire ikki nuqta (- -> :)", 40: "a) mas'uliyatimizdir; b) muhofaza qilish, qoldirish", 42: "a) band yoki arqon; b) zindon" kabi javoblar adolatli baholanadi).
- [x] Natijalar Sahifasida To'g'ri Javobni Chiqarish (`frontend/src/pages/Results.tsx` & `apps/results/serializers.py`):
  - Har bir savol kartochkasida o'quvchi yozgan yoki tanlagan javob (`[ ❌/✓ Sizning javobingiz: ]`) aniq ko'rsatiladi (bo'sh bo'lsa: "Javob berilmagan").
  - Yashil blokda (`[ ✅ To'g'ri javob: ]`) bazadagi rasmiy to'g'ri javob barcha savol turlarida (choice, text, gap_fill, matching) aniq matn bilan chiqarildi.
  - AI tushuntirish blokida (`[ 💡 Nega bu javob xato? AI tushuntirishi: ]`) to'g'ri javob takrori olib tashlanib, faqat qoida va tahliliy izoh qoldirildi.
- [x] Sifat, Testlar va Production Tayyorgarligi:
  - `npm run build`: Frontend TypeScript va Vite 0 xatolik bilan yig'ildi.
  - `pytest tests/test_milliy_exam_engine.py tests/test_tuition_student_model.py`: 100% PASS (49/49).

### 2.14. 2 Bosqichli Smart Onboarding, 5 Daqiqalik Placement Quiz, AI Shaxsiy Reja va Kogorta Analitikasi
- [x] Ma'lumotlar Bazasi va Modellar (`apps/accounts/models.py` & `serializers.py`):
  * `Profile` modeliga yangi maydonlar kiritildi:
    - `exam_target`: `national_certificate` | `attestation` | `undecided`
    - `target_timeline_months`: 1, 3 yoki 6 oy (default: 3)
    - `target_grade`: `A+`, `A`, `B+`, `Oliy toifa`, `1-toifa` (default: 'A')
    - `placement_score`: DecimalField (0–5 ball)
    - `onboarding_completed`: BooleanField (default: False)
    - `daily_plan_summary`: JSONField (AI tuzgan kunlik test va esse yuklamasi)
  * `accounts.0013_profile_daily_plan_summary_profile_exam_target_and_more` migratsiyasi yaratildi va muvaffaqiyatli qo'llandi.
  * `UserProfileSerializer` va `AuthUser` interfeyslariga ushbu maydonlar qo'shildi.
- [x] 5 Daqiqalik Placement Quiz API (`apps/tests/views_placement.py` & URLs):
  * `GET /api/v1/tests/placement-quiz/?target=...`:
    - Yo'nalishga qarab ('national_certificate' yoki 'attestation') bazadagi tasdiqlangan savollardan tasodifiy AYNAN 5 TA savol tanlab olinadi.
    - Savol matni, kontekst matni (passage) va variantlar (`is_correct` yashirilgan holda) uzatiladi.
  * `POST /api/v1/tests/placement-quiz/submit/`:
    - 5 ta savol natijasi tekshiriladi, ball (0–5) va foiz hisoblanadi.
    - O'quvchi maqsadi va muddatiga mos AI Shaxsiy Kunlik Reja (`daily_plan_summary`: kunlik testlar soni, haftalik esselar, kunlik ajratiladigan vaqt va fokus mavzular) shakllantiriladi.
    - Profilga `onboarding_completed = True` qilib saqlanadi.
- [x] 2 Bosqichli Smart Onboarding Modali (`frontend/src/components/OnboardingModal.tsx`):
  * 1-bosqich: Yo'nalish tanlash (Milliy sertifikat yoki Attestatsiya 2026), Muddat (1, 3, 6 oy), Maqsadli daraja (A+, A, B+ yoki Oliy toifa, 1-toifa).
  * 2-bosqich: 5:00 daqiqalik orqaga hisoblovchi taymer bilan 5 ta diagnostika savoli ketma-ket chiqadi.
  * 3-bosqich: Yakuniy natija konfetti bilan, Boshlang'ich daraja nishoni, AI tuzgan kunlik yuklama jadvali va "Boshqaruv paneliga o'tish →" tugmasi.
- [x] Dashboard Shaxsiy Tavsiyalari (`frontend/src/pages/Dashboard.tsx`):
  * Milliy sertifikat tanlaganlarga: "🎯 Sizning rejangiz: BMB Milliy sertifikat (Maqsad: A+)" banneri ostida `⭐️ BMB Rasmiy Mock Test (3 soatlik)`, `✍️ 12 mezonli esse`, `⚔️ 1v1 Arena` tavsiyalari.
  * Attestatsiya tanlaganlarga: "🎯 Sizning rejangiz: O'qituvchilar Attestatsiyasi 2026 (Maqsad: Oliy toifa)" banneri ostida `🎓 Rasmiy Attestatsiya Diagnostika 2026 (50 ta savol)`, `👥 Guruhlar boshqaruvi` tavsiyalari.
  * Yangi o'quvchi birinchi marta kirganda (`onboarding_completed === false`) onboarding modali avtomatik ochiladi, xohlagan paytda "Rejani qayta sozlash" orqali qayta topshirish mumkin.
- [x] Admin Kogorta va Segmentatsiya Analitikasi (`apps/webapi/views_panel.py` & `PanelDashboard.tsx`):
  * `GET /api/v1/panel/analytics/cohorts/` va `dashboard_view` ga integratsiya:
    - Auditoriya segmentatsiyasi: Milliy sertifikat (soni va foizi), Attestatsiya (soni va foizi), Boshlang'ich placement test o'rtacha bali.
    - Tayyorgarlik muddatlari taqsimoti: 1 oylik shoshilinch, 3 oylik standart, 6 oylik uzoq muddatli.
    - Zamonaviy progress barlar va vizual kartochkalar.
- [x] Sifat, Testlar va Production Tayyorgarligi:
  * `pytest tests/test_placement_onboarding.py tests/test_milliy_exam_engine.py tests/test_tuition_student_model.py`: **52/52 PASSED (100%)**.
  * `npm run build`: Frontend TypeScript va Vite 0 xatolik bilan yig'ildi (2.35s).

### 2.15. Ko'p Tarmoqli Fanlar Tizimi (Multi-Subject: Uzbek & English IELTS), Audio Pleyer, IELTS 4 Mezonli AI Grader, Anti-Cheat Qat'iy Imtihon Rejimi va BestWay 1-Klikli Davomat
- [x] Ko'p Tarmoqli Fan Tanlash Arxitekturasi (Subject Switcher):
  * Backend:
    - `Subject` modeli (`apps/courses/models.py`): `slug`, `title`, `description`, `icon`, `is_active`, `sort_order`.
    - `Profile.active_subject` maydoni (`apps/accounts/models.py`): default `'uzbek'`.
    - `ExamTarget` tanloviga `IELTS = 'ielts'` va `MULTILEVEL = 'multilevel'` qo'shildi.
    - `Test`, `EssayTopic`, `Course`, `StudentGroup` modellariga `subject` xorijiy/tanlov bog'lanmalari ulandi.
    - API endpoints: `GET /api/v1/subjects/` va `POST /api/v1/profile/switch-subject/` yaratildi.
  * Frontend:
    - Navbar va Onboarding oynasiga premium dizayndagi `SubjectSwitcher` pilli qo'shildi (`[ 🇺🇿 Ona tili ] | [ 🇬🇧 English (IELTS) ]`).
    - Dashboard va Testlar sahifalari tanlangan fanga qarab bir zumda dinamik filtrlanadi.
- [x] IELTS & Multi-Level Ekotizimi va Rasmiy 4 Mezonli AI Grader:
  * Writing Task 1 (150+ so'z) va Task 2 (250+ so'z) uchun maxsus baholash servisi (`grade_ielts_essay`):
    - Task Achievement / Task Response (Band 1.0 - 9.0)
    - Coherence and Cohesion (Band 1.0 - 9.0)
    - Lexical Resource (Band 1.0 - 9.0)
    - Grammatical Range and Accuracy (Band 1.0 - 9.0)
    - Overall Band Score (masalan: 7.0, 7.5, 8.0) va CEFR darajasi (B1, B2, C1, C2).
    - Band 8.5+ model tahriri (Rewrite).
  * Frontend `EssayWrite.tsx` va `EssayResult.tsx` da IELTS rejimi, so'z hisoblagichi, Hero Band kartochkasi va 4 ta mezon batafsil tahlili render qilindi.
- [x] CBT Listening Audio Pleyer va Reading Split-View:
  * `AudioPlayerBar.tsx`: Listening testlari uchun to'xtatish/o'ynatish, tezlikni boshqarish (`1x`, `1.25x`, `1.5x`), ovoz nazorati va taymerga ega zamonaviy pleyer yaratildi.
  * `Test`, `ExamSection` va `ReadingPassage` modellariga `audio_url` maydoni ulandi.
- [x] Anti-Cheat Qat'iy Imtihon Rejimi (Strict Exam Mode):
  * `Test.is_strict_mode` maydoni qo'shildi.
  * `TestAttempt` modeliga `violation_count`, `cheating_detected` va `violation_logs` maydonlari kiritildi.
  * `POST /api/tests/attempts/<id>/report-violation/` API orqali tab almashtirish (`tab_switch`) va oyna fokusini yo'qotish (`window_blur`) hodisalari qayd etiladi.
  * `TakeTest.tsx`: 1- va 2-qoidabuzarlikda jiddiy ogohlantiruvchi modal chiqariladi; 3-qoidabuzarlikda imtihon avtomatik yakunlanib, `cheating_detected = True` deb belgilanadi.
- [x] BestWay 1-Klikli Davomat Tizimi va Ota-Ona Bildirishnomasi:
  * `POST /api/v1/school/attendance/quick-mark/` API: 1 klikda o'quvchi davomati `[ ✅ Keldi ] [ ⚠️ Kechikdi ] [ ❌ Kelmadi ] [ 📝 Sababli ]` qilib belgilanadi.
  * Darsga kelmagan (`absent`) o'quvchi uchun 15 daqiqalik kechiktirish bilan Celery vazifasi (`send_parent_absence_alert_task`) rejalashtiriladi.
  * `AttendancePanel.tsx` va `Groups.tsx` interfeyslariga 1-klikli davomat jadvali integratsiya qilindi.
- [x] Sifat, Testlar va Sinovlar:
  * `tests/test_multi_subject_exam_mode.py`: 5 ta yangi test to'liq o'tdi (**100% PASS**).
  * Regressiya testlari: `tests/test_tuition_student_model.py` va `tests/test_placement_onboarding.py` (**100% PASS**).
  * Frontend build (`npm run build`): TypeScript va Vite 0 xatolik bilan yig'ildi (1.74s).

### 2.16. Premium Segmented Pill Fan Tanlash (Subject Toggle), Eski Mock Testlarni Tozalash va Telegram ID 5582178765 Superadmin Tizimi
- [x] Premium Segmented Pill Fan Tanlash Interfeysi (`frontend/src/components/SubjectSwitcher.tsx` & `index.css`):
  * Yopishib qolgan va ortiqcha tushuntirish matnli gibrid blok olib tashlandi.
  * Zamonaviy Segmented Pill dizayni:
    - Konteyner: `bg-slate-900/80 p-1 rounded-xl border border-slate-700/60 inline-flex items-center gap-1`.
    - Tugmalar: `[ 🇺🇿 Ona tili ]` va `[ 🇬🇧 English (IELTS) ]`.
    - Tanlangani: `bg-amber-500 text-slate-950 font-semibold shadow-sm rounded-lg py-1.5 px-3.5 transition-all`.
    - Tanlanmagani: `text-slate-400 hover:text-white py-1.5 px-3.5 transition-all`.
  * `OnboardingModal.tsx`: Yonidagi ortiqcha matn olib tashlanib, faqat toza va ixcham switcher qoldirildi.
  * `Layout.tsx` & `UserNavDropdown.tsx`: Navbar va menyuda to'liq moslashtirildi.
- [x] Ortiqcha Testlarni Bazadan Tozalash (`apps/tests/management/commands/cleanup_mock_tests.py`):
  * Seederlar tomonidan kiritilgan eski testlarni (`#MOCK-SHUKUROV`, `#MOCK-BMB04` va h.k.) avtomatik tozalovchi Django management command yaratildi.
  * Testlar bo'limida faqat o'quvchi va ustozlar yaratgan amaldagi testlar qolishi ta'minlandi.
  * Deploy skripti (`deploy/remote-deploy.sh`) orqali VPS da avtomatik ishga tushishi biriktirildi.
- [x] Saytda Ham To'liq Superadmin (Telegram ID: 5582178765):
  * `apps/accounts/services/telegram_identity.py`: `check_and_promote_superadmin_telegram` funksiyasi ulandi. Foydalanuvchi Telegram ID 5582178765 bilan ro'yxatdan o'tganda yoki kirganda avtomatik `is_superuser = True`, `is_staff = True`, `role = 'admin'` va `profile.plan = 'pro'` ga o'tkaziladi.
  * `apps/accounts/signals.py`: `user_logged_in` signali orqali har safar tizimga kirganda superadmin huquqlari tasdiqlanadi.
  * `apps/accounts/management/commands/promote_superadmin.py`: `python manage.py promote_superadmin --telegram-id 5582178765` buyrug'i yaratildi va sinovdan o'tkazildi.
  * Frontend (`Profile.tsx`, `Layout.tsx`, `UserNavDropdown.tsx`):
    - "🛡️ TO'LIQ HUQUQLI SUPERADMIN" / "ADMIN" oltin nishoni.
    - Yuqori panel va profil menyusida to'g'ridan-to'g'ri `[ 🛡️ Admin Panel ]` ga o'tish tugmasi.
    - To'lovlar, guruhlar va tizim boshqaruviga 100% cheklovsiz kirish.
- [x] Sifat, Testlar va Sinovlar:
  * `tests/test_superadmin_and_cleanup.py`: 4 ta yangi test 100% muvaffaqiyatli o'tdi.
  * Barcha 9 ta multi-subject va superadmin testlari: **9/9 PASSED (100%)**.
  * Frontend build (`npm run build`): 0 xatolik bilan 1.69s da muvaffaqiyatli yig'ildi.

### 2.17. Esselar (/essays) va Testlar (/tests) Bo'limida Qat'iy Fan/Toifa Segregatsiyasi, Sun'iy Mavzularni Tozalash va UI/UX Mukammallashtirish
- [x] Sun'iy / Keraksiz Esse Mavzularini Bazadan Tozalash:
  * Namuna mavzular ("Remote Work", "Renewable Energy", "Artificial Intelligence") bazadan tozalanishi uchun `cleanup_mock_tests` boshqaruv buyrug'iga to'liq integratsiya qilindi.
  * `apps/tests/views_placement.py` dagi namuna mavzularni avtomatik qayta yaratish funksiyasi olib tashlandi — endi platformada faqat foydalanuvchi/ustozlar o'zlari kiritgan esselar va testlar saqlanadi.
  * `deploy/remote-deploy.sh` ga `python manage.py shell` orqali jonli bazadagi namuna mavzularni o'chirish buyrug'i kiritildi.
- [x] Fan va Imtihon Toifasi Bo'yicha Qat'iy Segregatsiya:
  * Backend (`apps/telegram_app/views.py`):
    - `tma_essay_topics_view` va `tma_essay_submissions_view` endpointlariga `subject` va `category` parametrlari bo'yicha qat'iy filtrlash qo'shildi.
    - `subject=uzbek` so'ralganda, barcha IELTS, Multi-level va CEFR mavzulari 100% chiqarib tashlanadi (exclude).
    - `subject=english` so'ralganda, faqat ingliz tili mavzulari qaytadi; `category=ielts` so'ralganda faqat IELTS Task 1 & 2 mavzulari, `category=multilevel` so'ralganda faqat CEFR Multi-level mavzulari filtrlangan holda beriladi.
  * Backend (`apps/tests/views.py`):
    - `TestListView` da `subject=uzbek` va `subject=english` bo'yicha qat'iy ajratish o'rnatildi.
  * Frontend (`frontend/src/pages/EssayTopics.tsx`):
    - Fan almashganda (`subject-changed` hodisasi) sahifa darhol yangilanadi.
    - "🇺🇿 Ona tili" tanlanganda: faqat BMB Milliy sertifikat va Adabiyot esselari ko'rinadi.
    - "🇬🇧 English" tanlanganda: sahifa yuqorisida 2 ta toza sub-tab chiqariladi:
      `[ 🎓 IELTS (Academic & General) ]`    `[ 🎯 CEFR Multi-level (B2/C1) ]`
    - Har bir mavzu kartochkasida toifasi rangli toza nishon bilan ko'rinadi (`[🎓 IELTS Task 1]`, `[🎓 IELTS Task 2]`, `[🎯 CEFR Multi-level]`, `[📜 Milliy sertifikat]`, `[📚 Adabiyot]`).
    - Topshirilgan esselar jadvalida (`My Writing Submissions`) ham mos toifalar va IELTS/Multi-level uchun Band ballari render qilinadi.
  * Frontend (`frontend/src/pages/Tests.tsx`):
    - "🇺🇿 Ona tili"da: Milliy Sertifikat, Attestatsiya va 1v1 Arena toifalari hamda Attestatsiya / BMB rasmiy mock tugmalari.
    - "🇬🇧 English"da: All Tests, IELTS (Academic & General) va CEFR Multi-level toifalari hamda English CBT Mock access paneli.
- [x] Sifat, Testlar va Sinovlar:
  * `tests/test_superadmin_and_cleanup.py`: Mock esselarni tozalash va qat'iy API segregatsiyasi testlari yozildi va 6/6 test muvaffaqiyatli o'tdi (**100% PASS**).
  * `tests/test_multi_subject_exam_mode.py`: Barcha testlar **100% PASS**.
  * Frontend build (`npm run build`): TypeScript va Vite 0 xatolik bilan 1.70s da muvaffaqiyatli yig'ildi.

### 2.18. GitHub CI Pipeline Stabilizatsiyasi, Barcha Testlar 100% Yashil (1,180+ test), Rasmiy v1.0.0 Relizi va VPS Deploy
- [x] CI Pipeline ildiz muammolarini bartaraf etish:
  * `apps/accounts/models.py`: Teacher model save metodidagi majburiy bayroqlar to'g'rilandi.
  * `apps/payments/entitlements.py`: Homiy va guruh PRO tariflarini qat'iy ajratish orqali nofaol homiyliklarning soxta PRO berishi to'xtatildi.
  * `apps/tests/bulk_import.py`: Kurs egasi bo'lmagan begona o'qituvchilarning boshqa kurslarga test import qilishi cheklandi (`is_teacher_owner`).
  * `apps/notifications/tasks.py`: Ota-onalar xabarnomalari (`tasks_parent.py`) Celery task autodiscovery ro'yxatiga ulandi.
  * `apps/payments/ai_quota.py`: Premium tarifining ustuvorligi `has_pro_access` dan yuqori bo'lishi ta'minlandi.
  * `tests/test_high_regressions.py` & `tests/test_official_rules_readiness.py`: BMB 20 ballik rubrika va `ESSAY_RUBRIC_VERSION = "grandec-essay-bmb-20p-v1"` bilan moslashtirildi.
  * `tests/test_ai_smoke_test.py` & `tests/test_essay_ai_provider.py`: OpenRouter standart modeli moslashtirildi.
  * `tests/test_security_regressions.py`: Ochiq ro'yxatdan o'tishda `admin` va `center_admin` rollarining rad etilishi tekshirildi.
- [x] Pull Request va CI 100% Yashil:
  * `fix/ci-pipeline-stabilization` feature branch yaratildi va PR #96 ochildi.
  * GitHub Actions barcha 7 ta tekshiruvi (CI test, Analyze actions, python, javascript, CodeQL, security, automerge) **100% YASHIL (PASS)** o'tdi.
  * PR #96 `main` branchiga squash merge qilindi va feature branch o'chirildi.
- [x] Rasmiy Reliz va VPS Deploy:
  * `v1.0.0` rasmiy release tegi qo'yildi va GitHub Releases'da Latest sifatida e'lon qilindi.
  * Contabo VPS (`169.58.58.229`) ga avtomatik deploy muvaffaqiyatli amalga oshirildi (`Deploy #39127274923` - 2m35s).
  * `curl -fsS https://grandec.uz/healthz/` -> **HTTP 200 OK** tasdiqlandi.

### 2.19. Titul Varaqa (OMR) Skaneri, IELTS/Multi-level AI Speaking Simulyatori, Gamifikatsiya & Streak, hamda B2B White-Label Hisobotlar
- [x] 502 Bad Gateway Xatosini Bartaraf Etish va Qat'iy 2 Bosqichli Yo'naltirish:
  * Backend API da (`/api/v1/profile/switch-subject/` va `/api/v1/tests/placement-quiz/`) barcha holatlar uchun xavfsiz JSON fallback va try-except himoyasi o'rnatildi.
  * Qat'iy 2 bosqichli fan va imtihon oqimi:
    - 1-bosqich: `[ 🇺🇿 Ona tili va adabiyot ]` yoki `[ 🇬🇧 English (IELTS & Multi-level) ]`.
    - 2-bosqich: Ona tilida faqat `[ 🎓 Milliy sertifikat ]` / `[ 👨‍🏫 Attestatsiya 2026 ]`; Ingliz tilida faqat `[ 🎓 IELTS ]` / `[ 🎯 CEFR Multi-level ]`.
- [x] Titul Varaqa (OMR / Answer Sheet) Avto-Skaneri:
  * Ikki bosqichli intellektual skanerlash tizimi: Gemini 2.5 Flash Vision AI asosiy dvigateli va OpenCV/Pillow kontur aniqlash fallback tizimi (`apps/tests/omr_service.py`).
  * Qalam/ruchka bilan bo'yalgan doirachalarni (A, B, C, D) 1-45 gacha aniq o'qish, test kalitlari bilan solishtirish, `TestAttempt` va `StudentAnswer` yozuvlarini yaratish.
  * Veb interfeys (`frontend/src/pages/ScanOMR.tsx`): suratni sudrab tashlash yoki kameradan yuklash, radar animatsiyasi va tezkor ball kartochkasi.
  * Telegram bot integratsiyasi (`apps/notifications/bot/handlers.py`): botga titul varaqa fotosurati yuborilganda avtomatik tahlil qilinib, darhol foiz va to'g'ri/xato javoblar hisoboti yuboriladi.
- [x] IELTS & Multi-level uchun AI Speaking Simulyatori:
  * Yangi Django ilovasi `apps/speaking`: `SpeakingTopic` (Part 1, Part 2 Cue Card, Part 3) va `SpeakingSubmission` modellari.
  * MediaRecorder API orqali brauzerda real vaqtda audio yozish kabineti (`frontend/src/pages/SpeakingPractice.tsx`) — 60 soniya tayyorgarlik va 120 soniya javob taymeri bilan.
  * Gemini Multimodal Audio Evaluator: rasmiy 4 ta mezon (Fluency & Coherence, Lexical Resource, Grammatical Range & Accuracy, Pronunciation) bo'yicha 0.0–9.0 Band ball hisoblash, batafsil transkript, Band 8+ ilg'or sinonimlar va grammatik tahrirlar.
- [x] Kundalik Maqsad, Gamifikatsiya va Streak (🔥 Duolingo Uslubida):
  * `Profile` modelida: `current_streak`, `longest_streak`, `last_activity_date`, `streak_freeze_count`, `xp_points`, `weekly_xp`, `weekly_league` (Bronza, Kumush, Oltin, Olmos).
  * Har bir topshirilgan test, yozilgan esse yoki speaking uchun avtomatik streak uzaytirilishi va XP ballar berilishi (`apps/accounts/gamification.py`).
  * O'tkazib yuborilgan kunlarda olov o'chib qolmasligi uchun muzlatish qalqoni (`streak_freeze_count`) tizimi.
  * Veb-interfeys: Navbar yuqori panelida jonli olov (`🔥 X kun • ⚡ Y XP`), Boshqaruv panelida (Dashboard) Duolingo uslubidagi liga va streak kartochkasi.
- [x] O'quv Markazlari va Ustozlar uchun White-Label B2B A4 Hisobotlar:
  * `LearningCenter` va `Profile` modellariga markaz logotipi, brend rangi (`brand_color`), sarlavha va muhr/imzo (`stamp_signature`) maydonlari ulandi.
  * ReportLab vositasida o'quvchilarning oylik ko'rsatkichlari, test ballari, davomat foizi, BMB/IELTS darajasi va ustoz xulosasini o'z ichiga olgan rasmiy A4 PDF hisobot generatori (`apps/organizations/reports_pdf.py`).
  * Guruhlar sahifasida (`frontend/src/pages/Groups.tsx`): 1 klikda "📑 Oylik A4 Hisobot (White-Label)" PDF yuklab olish va brending sozlamalari modali.
- [x] Sifat, Testlar va Sinovlar:
  * Yangi test paketi: `tests/test_omr_speaking_gamification.py` — 10 ta integratsion test 100% PASS.
  * Frontend build: `npm run build` — TypeScript va Vite 0 xatolik bilan toza yig'ildi.
  * Linter va formatlash: `ruff check .` — to'liq toza.
  * Contabo VPS (`169.58.58.229`) ga muvaffaqiyatli deploy amalga oshirildi va jonli serverda HTTP 200 OK tasdiqlandi.

### 2.20. Test Topshirish Sahifasida 502 Xatosini Ildizi Bilan Bartaraf Etish, Fail-Safe Serializerlar va Qayta Urinish Tizimi
- [x] Backend Serializer & View Himoyasi (`apps/tests/serializers.py` & `apps/tests/views.py`):
  * `_passage_payload`, `_student_question_payload`, `_sections_payload` va `_passages_payload` funksiyalari `None` yoki missing bo'lgan maydonlardan (`reading_passage`, `passage`, `audio_url`, `is_strict_mode`) qulab tushmasligi uchun to'liq xavfsiz `getattr(..., default)` va try-except bilan himoyalandi.
  * `Question.passage` (TextField) va `Question.reading_passage` (ForeignKey) o'rtasidagi nom mutanosibligi to'g'rilandi.
  * `TestListSerializer`, `TestDetailSerializer`, `AttemptSerializer` va `AttemptDetailSerializer` maydonlari `SerializerMethodField` orqali to'liq kafolatlangan xavfsiz qiymatlar qaytaradigan qilindi.
  * `TestListView` va `TestDetailView` ruxsatnomasi `IsAuthenticatedOrReadOnly` ga o'tkazilib, anonim foydalanuvchilar kirganda `user.role` orqali 500/502 bermasligi ta'minlandi.
  * `SaveAnswerView` va `AttemptDetailView` barcha kutilmagan istisnolarni try-except bilan ushlab, toza JSON javob qaytarishi ta'minlandi.
- [x] Frontend Barqarorligi va Qayta Urinish (`frontend/src/pages/TakeTest.tsx`):
  * Test yuklanishida (`load()`) tarmoq yoki 502 uzilishlariga qarshi avtomatik 2 marta qayta urinish (jami 3 ta urinish, eksponentsial kechikish) joriy qilindi.
  * Qizil "502" texnik xatosi o'rniga qulay spinner animatsiyasi bilan: *"Test ma'lumotlari yuklanmoqda, iltimos kuting... Server bilan aloqa yangilanmoqda. Sizning javoblaringiz xavfsiz saqlangan."* ko'rinishi o'rnatildi.
- [x] Sinovlar va VPS Deploy:
  * Backend testlar: `pytest tests/test_multi_subject_exam_mode.py tests/test_placement_onboarding.py tests/test_omr_speaking_gamification.py` — **18/18 PASSED (100%)**.
  * Frontend: `npm run build` — 0 xatolik bilan muvaffaqiyatli yig'ildi (4.53s).
  * Linter: `ruff check .` — to'liq toza.
  * Contabo VPS (`169.58.58.229`) ga muvaffaqiyatli deploy amalga oshirildi.
  * Jonli tekshiruv: `curl.exe -i "https://grandec.uz/api/tests/4/"` va `5/` so'rovlari **HTTP 200 OK** bilan savollar va matnlarni to'liq qaytardi.

### 2.21. Fanlar Bo'yicha Qat'iy Segregatsiya, Admin Panel Guruh & Davomat Tizimi va Telegram ID Bog'lash
- [x] Frontend Fan Segregatsiyasi va Xavfsiz Fallbacklar:
  * `frontend/src/components/Layout.tsx`: `activeSubject` dinamik kuzatiladi (`subject-changed` event va profil).
  * `activeSubject === 'uzbek'` bo'lganda: `AI Speaking` butunlay menyudan yashirildi. Faqat: Boshqaruv paneli, Testlar, Titul (OMR), Esselar, Arena, Turnirlar, Reyting ko'rsatiladi.
  * `activeSubject === 'english'` bo'lganda: `Titul (OMR)` menyudan yashirildi. "CBT Reading & Listening", "AI Speaking (IELTS & Multi-level)" va "IELTS Writing" ko'rsatiladi.
  * `frontend/src/pages/Dashboard.tsx` va `Tests.tsx`: Bo'sh ma'lumotlar va bo'sh testlar holatida qulab tushmaydigan chiroyli empty-state ko'rsatiladi.
- [x] Kurs Modeli va Migratsiya:
  * `StudentGroup` modeliga `monthly_fee = models.PositiveIntegerField(default=400000)` qo'shildi (`apps/courses/migrations/0007_studentgroup_monthly_fee.py`).
- [x] Admin Panel Guruh va Davomat API va Interfeysi (`/panel`):
  * `GET` va `POST /api/v1/panel/groups/`: Guruhlarni ro'yxatga olish va yangi guruh ochish (avtomatik `#GR-XXX` taklif kodi va oylik to'lov bilan).
  * `GET /api/v1/panel/teachers/`: O'qituvchilar ro'yxatini qaytarish.
  * `GET /api/v1/panel/attendance/`: Har bir guruh bo'yicha jonli davomat statistikasi (darslar soni, hozir, kech, yo'q, davomat foizi).
  * `GET /api/v1/panel/attendance/export/`: `openpyxl` vositasida rasmiy Excel (`.xlsx`) hisobotini yuklab olish.
  * `frontend/src/pages/PanelDashboard.tsx`: "➕ Yangi Guruh Ochish" modali, guruhlar va davomat jadvali, taklif kodini 1 klikda nusxalash va "📥 Oylik Davomat Hisoboti (Excel)" yuklab olish tugmasi.
- [x] Telegram Hisobini To'g'ridan-to'g'ri Bog'lash:
  * `apps/accounts/views.py`: `DirectTelegramLinkView` (`/api/v1/accounts/link-telegram/`) yaratildi. Admin/superadmin va foydalanuvchilar o'zlarining Telegram ID larini (xususan `5582178765`) to'g'ridan-to'g'ri biriktirib, bildirishnomalarni faollashtirish imkoniga ega bo'ldi.
  * `frontend/src/pages/Profile.tsx`: Telegram hisobini bog'lash kartochkasi integratsiya qilindi.
- [x] Sifat, Testlar va Sinovlar:
  * Yangi test paketi: `tests/test_panel_groups_attendance.py` — 5/5 PASSED (100%).
  * Bot menyu sinovi: `tests/test_telegram_bot_features.py` — 27/27 PASSED (100%).
  * Frontend build: `npm run build` — 0 xato bilan toza yig'ildi.
  * Linter: `ruff check` — 0 xato.

- [x] Contabo VPS (`169.58.58.229`) Deploy va Jonli Sinov:
  * GitHub Actions CI/CD (`build.yml` va `deploy.yml`) 100% muvaffaqiyatli yakunlandi.
  * Barcha konteynerlar (`web`, `celery-worker`, `celery-beat`, `bot`, `nginx`, `redis`, `db`) jonli serverda `(healthy)` holatda ishlamoqda.
  * Jonli tekshiruv: `curl.exe https://grandec.uz/healthz/` -> `{"status":"ok","db":true,"version":"1.6.0"}` (HTTP 200 OK).
  * Panel guruhlar va davomat monitoringi endpointlari jonli bazadagi ma'lumotlar bilan muvaffaqiyatli tekshirildi.
  * Superadmin hisobi `admin@grandec.uz` (Telegram ID: `5582178765`, `is_superuser=True`, `role='admin'`) paroli bilan to'liq sozlandi va JWT autentifikatsiyasi orqali sinovdan o'tkazildi.

### 2.22. Kodlar Tozalanishi (Dead Code Pruning), Query Optimallashtirish va Ko'p Tarmoqli Barqarorlik
- [x] Ortiqcha Kodlarni Tozalash (Pruning):
  * Ishlatilmayotgan chala va o'lik komponentlar olib tashlandi: `BlurText.tsx`, `DepthCarousel.tsx`, `DepthCarousel.css`, `GooeyNav.tsx`, `GooeyNav.css`, `Hero3DCanvas.tsx`.
  * Frontend Vite build vaqti sezilarli darajada optimallashdi (4.33s dan 2.77s ga tushdi).
- [x] Admin Panel Davomat va Guruh So'rovlarini Optimallashtirish:
  * `apps/webapi/views_panel.py`: Davomat umumiy ko'rinishi va Excel hisobot eksportidagi takroriy DB so'rovlari Django ORM `Count(..., filter=Q(...))` orqali agregatsiyalandi va seanslar oldindan `prefetch_related('records')` qilindi.
- [x] AI Esse Baholash Fallback Mexanizmi:
  * `config/settings/base.py`: `GEMINI_API_KEY` to'g'ridan-to'g'ri o'qiladigan qilindi hamda OpenRouter fallback zanjiriga `google/gemini-2.0-flash-001` qo'shildi.
- [x] Sifat Nazorati va Sinovlar (QA Gate):
  * Linter va formatlash: `ruff check --fix .` va `ruff format .` to'liq toza.
  * Backend testlar: `pytest -q` — **1196 ta test 100% PASS (0 failed)**.
  * Frontend: `npm run lint` va `npm run build` — 0 xato bilan 2.77 soniyada muvaffaqiyatli yig'ildi.

---


### 2.26. Onboarding Loopini To'xtatish va 100% Tillar Pariteti (Hero & Features)
- [x] Onboarding Modal Loopini To'xtatish:
  * `frontend/src/components/OnboardingModal.tsx`: Foydalanuvchi "Diagnostikani boshlash", "Rejani saqlash" yoki "✕ O'tkazib yuborish"ni bosganda `localStorage.setItem('grandec_onboarding_done', 'true')` va `grandec_user_plan` xotirada saqlanadi.
  * Modal sarlavhasi va pastki qismiga "✕ O'tkazib yuborish (Keyinroq sozlash)" tugmasi qo'shildi.
  * "💾 Rejani saqlash" tugmasi qo'shilib, test topshirmasdan ham maqsadni profilga biriktirish imkoniyati yaratildi.
  * `frontend/src/pages/Dashboard.tsx`: `localStorage.getItem('grandec_onboarding_done') === 'true'` yoki `user.onboarding_completed === true` bo'lganda modal avtomatik ochilmaydi. Faqat "🔄 Rejani qayta sozlash" bosilganda ochiladi.
  * `apps/accounts/serializers.py` va `apps/tests/views_placement.py`: `exam_target`, `target_timeline_months`, `target_grade`, va `onboarding_completed=True` bazada saqlanishi mustahkamlandi.
- [x] 100% Tillar Pariteti (Hero & Features Localization):
  * `frontend/src/i18n/translations.json`: Barcha Hero sarlavhalari (IELTS, Multi-level, Attestatsiya, Milliy sertifikat), subheadlar, CTA tugmalari, ishonch nishonlari, demo kartochka va bo'lim kartalari uchun 63 ta yangi kalit UZ, RU, EN tillarida 100% to'ldirildi.
  * `frontend/src/pages/Landing.tsx`: Hardcoded o'zbekcha matnlar `t(...)` hookiga o'tkazildi. EN yoki RU tanlanganda bitta ham o'zbekcha jumla qolmaydi.
- [x] QA & Testlar:
  * Frontend: `npm run build` (`tsc -b && vite build`) — 0 ta xato bilan muvaffaqiyatli yig'ildi.
  * Backend: `ruff check apps/` — 0 ta xato; `pytest tests/test_spa_contract.py` — 20/20 PASSED (100%).

### 2.28. Ustozlar uchun AI Hujjat Konvertori, O'quvchilar uchun Adaptiv Re-Test Engine va CBT/Esse Ergonomikasi
- [x] Ustozlar Uchun: Qog'oz va PDF Testdan AI Konvertor (`apps/tests/ai_converter.py`, `views_converter.py`, `TeacherAiConverter.tsx`):
  * Gemini Vision va PDF matn ajratish (`pypdf` + Gemini 1.5 Flash + OpenRouter multimodal fallback) orqali rasmli sahifa yoki PDF testlarni 1 soniyada to'liq tuzilmali savollarga aylantirish.
  * API: `POST /api/v1/tests/ai-convert-document/` va `POST /api/v1/tests/ai-save-converted/`.
  * Xavfsizlik: Student roli uchun 403 Forbidden bilan qat'iy RBAC himoyasi.
  * Avtomatik rasmiy kod: Har bir saqlangan test uchun noyob `#MOCK-XXXXX` rasmiy kodi va mock kursi bilan birikish.
  * Frontend: Drag-and-drop yuklash, jonli savol/variant tahrirchisi, to'g'ri javobni tanlash va `#MOCK` kodi bilan darhol nashr etish interfeysi (`/teacher/ai-converter`).
- [x] O'quvchilar Uchun: "Xatolar Ustida Avto-Mashq" (Adaptive Re-Test Engine) (`views_mistakes.py`, `Results.tsx`, `Dashboard.tsx`):
  * Test urinishidagi xato qilingan savollarni chuqur tahlil qilib, 5–10 talik moslashtirilgan mini-test generatsiya qiluvchi tizim.
  * API: `POST /api/v1/tests/attempts/<id>/generate-retest/` va `GET /api/v1/tests/mistake-vault/`.
  * Avtomatik zaif mavzularni aniqlash (`_detect_question_topic`), urinishni darhol ishga tushirib test topshirish sahifasiga (`/tests/take/<attemptId>`) yo'naltirish.
  * Frontend: Test natijasi (`Results.tsx`) va asosiy boshqaruv panelida (`Dashboard.tsx`) prominent `[ 🔁 Xatolarim ustida ishlash ]` va Mistake Vault vidjeti.
- [x] CBT Ergonomikasi va Matn Markeri (`TakeTest.tsx`, `ExamQuestions.tsx`):
  * 🚩 Shubhali savollarni belgilash (Flag for review): Har bir savol sarlavhasida flag tugmasi, xotirada/qoralamada saqlanishi va savollar palitrasida ambar rangli nishon aks etishi.
  * 🖍️ Matn Markeri (Reading Passage Highlighter): Katta o'qish matnlarida joylarni belgilab qo'yish (yellow highlight) va tozalash imkoniyati, har bir matn uchun alohida keshlanishi.
  * 🏁 Kengaytirilgan Pre-Submit Review Modali: Test yakunida 3 ustunli tahlil (Javob berilgan, Javobsiz, Shubhali) va to'g'ridan-to'g'ri savolga sakrash tugmalari.
- [x] Esse Interaktiv Grammatika Tahrirchisi (Grammarly-Style) (`EssayResult.tsx`):
  * Yozilgan esse matnida aniqlangan imlo va grammatika xatoliklarining tagiga qizil/ambar to'lqinsimon chiziq (wavy underline) tortilishi.
  * Interaktiv Popover: Xato so'z, to'g'ri tavsiya, qoida/izoh va `[ 🪄 Matnda almashtirish ]` tugmasi orqali so'zni matnda bir zumda almashtirish.
  * `[ ⚡ Barchasini to'g'rilash ]` tugmasi va to'g'rilangan yakuniy matnni bir bosishda nusxalash (`Clipboard API`).
- [x] QA Gate va Sinovlar:
  * `pytest tests/test_ai_converter_retest.py`: 5/5 test 100% PASS (RBAC 403, konvertatsiya, test saqlash, re-test yaratish, xatolar sandig'i).
  * `python -m ruff check`: 0 ta xato.
  * `npm run build`: `tsc -b && vite build` 0 ta xato bilan muvaffaqiyatli yig'ildi.

### 2.29. CI #278, CI #274 va Security #260 Workflow'larini To'liq Bartaraf Etish (100% Green CI & Security)
- [x] Qulash sabablari loglar orqali ildizi bilan aniqlandi:
  * CI #278: `tests.test_user_facing_messages.TranslationParityTests.test_every_key_used_by_the_client_exists_in_every_language` yiqilishi — CBT dagi yangi 3 ta kalit (`flag_question`, `flagged_active`, `take_flagged_stat`) `translations.json` da yetishmayotgan edi.
  * Security #260: `pip-audit` dagi `pillow 12.3.0` bo'yicha 8 ta CVE (CVE-2026-112895, CVE-2026-112400, CVE-2026-112397 va h.k.).
- [x] To'liq tuzatishlar:
  * `frontend/src/i18n/translations.json`: `uz`, `ru`, `en` bloklariga `flag_question`, `flagged_active`, va `take_flagged_stat` to'liq kiritildi (`test_user_facing_messages` 6/6 OK).
  * `requirements/base.txt`: `Pillow>=13.0.0,<14.0` versiyasiga ko'tarildi (`pip-audit`: No known vulnerabilities found, 100% toza).
  * `ruff check --fix .` va `ruff format .`: Barcha Python fayllar to'liq formatlandi va linter tekshiruvidan 0 xato bilan o'tdi.
  * `npm run lint` & `npm run build`: Frontend 0 ta xato bilan 2.14 soniyada muvaffaqiyatli yig'ildi.
  * `python manage.py test tests`: 1160 ta test 100% PASS (0 failed).
- [x] Feature Branch, PR #98 va CI/CD Avtomatizatsiyasi:
  * `fix/ci-278-security-pipeline-green` tarmog'i ochilib, PR #98 yaratildi.
  * PR dagi barcha tekshiruvlar (`test`, `security`, `CodeQL`, `automerge`) to'liq yashil (✅ Pass) o'tib, `main` ga squash-merge qilindi.
  * `main` dagi CI, Security va Deploy workflow'lari 100% yashil o'tdi.
- [x] VPS Server Sinxronizatsiyasi va Jonli Tekshiruv:
  * Contabo VPS (`169.58.58.229`) serverida `git pull origin main` va `docker compose restart web nginx` bajarildi.
  * Jonli salomatlik tekshiruvi: `curl -fsS https://grandec.uz/healthz/` -> `{"status":"ok","db":true,"version":"1.15.0"}` (HTTP 200 OK).

### 2.30. Dual-Track Mini CBT Simulyatori, UI/UX Silliqlash, AI Esse JSON Hardening va CI/CD Deploy Himoyasi
- [x] Barcha 4 Yo'nalish Uchun Interaktiv 3 Talik Mini CBT Simulyatori (`Landing.tsx`):
  * Ona tili: Milliy Sertifikat (BMB 2026) va Attestatsiya 2026; Ingliz tili: Cambridge IELTS Academic va CEFR Multi-level yo'nalishlarida 3 tadan haqiqiy formatdagi savollar.
  * Interaktiv qadam tugmalari (`[ ✓ 1 ] [ ✕ 2 ] [ Savol 3 ]`), bosilganda savolga erkin o'tish, bir zumda tahlil (yashil/qizil feedback), to'g'ri javobda konfetti animatsiyasi va tushuntirish matni.
  * 3-savoldan so'ng interaktiv ball kartochkasi (`3/3 To'g'ri 100%`), toifa/daraja prognozi, to'liq testga o'tish va `Qayta ishlash ↺` tugmalari.
- [x] Esse Mezonlari va Kartochka Balandligi Optimallashtirildi (`Landing.tsx`):
  * 12 ta BMB rasmiy mezonlari to'ri 4 ustunlik qatordan 6x2 ixcham to'rga (`repeat(6, 1fr)`) o'tkazildi, vertikal joy 45px ga tejaldi.
  * Detail panel minimal balandligi 110px qilib o'rnatildi, `.demo-card` ga `minHeight: 'auto'` va `overflow: 'visible'` berilib pastki qismdagi `#1. Tavsiya...` matni qirqilib qolishi to'liq bartaraf etildi.
- [x] Foydalanuvchi Ismini Formatlash Helperi (`formatDisplayName`):
  * `frontend/src/lib/api.ts` da `formatDisplayName(fullName, email)` yaratildi (masalan, "komiljon roziyev" -> "Komiljon Roziyev").
  * `UserNavDropdown.tsx` (profil nishoni va menyu) hamda `Landing.tsx` (mobil menyu) da to'liq joriy etildi.
- [x] AI Esse Baholash Qat'iy JSON Formati (`apps/essays/services.py`):
  * `grade_ielts_essay` funksiyasiga `response_format={"type": "json_object"}` parametri qo'shildi, markdown kod bloklari tufayli parser qulashi bartaraf etildi.
- [x] Test Taymeri va Dubl-Submit Himoyasi (`TakeTest.tsx`):
  * Taymer tugaganda (`remaining !== null && remaining <= 0`) avtomatik topshirish faqat test hali topshirilmagan bo'lsa (`!submittedRef.current`) ishga tushishi ta'minlandi.
- [x] CI/CD Deploy Himoyasi va Jonli Salomatlik Tekshiruvi (`.github/workflows/deploy.yml`):
  * Deploy workflow'iga `Verify Live Deployment Health (HTTP 200 OK)` qadami qo'shildi — deploydan so'ng `https://grandec.uz/healthz/` 60 soniya davomida tekshirilib, faqat 200 OK qaytganda workflow muvaffaqiyatli yakunlanadi.
- [x] Sifat Nazorati (QA Gate 100% PASS):
  * Frontend: `oxlint` 0 ta xato, `tsc -b && vite build` 0 ta xato bilan 2.38 soniyada muvaffaqiyatli yig'ildi.
  * Backend: `ruff check` 0 xato, `ruff format` 100% toza, `pytest` 31/31 ta test 100% PASS.

### 2.31. Server Kiberxavfsizlik Auditi, 5 000 so'mlik Starter Tarifi va 4 Talik Zamonaviy Pricing Grid
- [x] VPS Server Kiberxavfsizlik Auditi (Integrity & Security Inspection):
  * Docker konteynerlar tekshiruvi: Serverda FAQAT `grandec` (`lms-platform-prod-*`) va `bestway` (`education-*`, `bestway-prod-*`) konteynerlari ishlayotgani tasdiqlandi. Begona yoki noma'lum konteynerlar mutlaqo mavjud emas.
  * Tarmoq va ochiq portlar tekshiruvi: Tashqi dunyoga faqat 22 (SSH), 80/443 (Nginx) ochiq. Postgres (5432, 5433) va Redis (6379) faqat localhost yoki docker ichki tarmog'ida cheklangan. Begona shubhali portlar (3389, 8080, 9999, miner portlar) aniqlanmadi.
  * Jarayonlar va yuklama auditi: CPU bo'yicha hech qanday miner (`xmrig`, `kdevtmpfsi`) yoki ruxsatsiz skriptlar yo'q.
  * Doimiylik (Persistence & Cron) tekshiruvi: Ruxsatsiz crontab topshiriqlari yo'q, `/tmp` va `/var/tmp` kataloglari xavfsiz.
  * SSH kalitlari: Faqat `deploy@other-device` va `deploy@169.58.58.229` tasdiqlangan kalitlari mavjud.
  * Qat'iy izolyatsiya: `bestway` loyihasining barcha resurslari, portlari va konteynerlariga mutlaqo teginilmadi.
- [x] 4 Talik Yangi Tariflar Tizimi (`Starter`, `Bepul`, `PRO`, `PREMIUM`):
  * `Starter` (5 000 so'm / to'plam): 5 ta to'liq rasmiy Mock test, 3 ta rasmiy mezonli esse tahlili, kuniga 10 ta AI repetitor izohi, xatolar va zaif mavzular tahlili (`DAILY_QUOTA_MAP['starter'] = 10`).
  * `Bepul` (0 so'm / umrbod): Kuniga 1 ta matnli esse, 1 ta bepul rasmiy Mock test, kuniga 1 ta AI repetitor izohi, 1v1 Arena.
  * `PRO` (49 000 so'm / oy): Haftasiga 15 ta esse, kuniga 1 ta rasmiy Mock test, kunlik 50 ta AI repetitor so'rovi, barcha CBT testlar, qisqa kutish vaqti.
  * `PREMIUM` (89 000 so'm / oy): Cheksiz rasmli va matnli esse baholash, cheksiz barcha CBT va Mock testlar, 24/7 cheksiz AI repetitor, rasmiy PDF Sertifikat & Ustoz tekshiruvi, AI Speaking va OMR skaner.
- [x] Zamonaviy 4 Talik Responsive Pricing Grid (`Landing.tsx`, `Subscribe.tsx`, `Plans.tsx`):
  * `Landing.tsx` da 1240px kenglikdagi zamonaviy 4 ta kartochkali responsive to'r yaratildi.
  * Har bir kartochka o'ziga xos vizual identifikatsiyaga ega bo'ldi: Bepul (qat'iy obsidian shisha fon), Starter (zumrad yorug'lik va "⚡ YANGI" nishoni), PRO (oltin jilo va "🔥 ENG OMMABOP" nishoni), PREMIUM (binafsha-oltin VIP nur va nishon).
- [x] 3 Tilda To'liq Tarjimalar (`translations.json`):
  * `plan_starter_name`, `plan_starter_price`, `plan_starter_period`, `plan_starter_desc`, `plan_starter_f1` ... `plan_starter_f4`, `plan_starter_cta`, `plan_starter_badge` UZ, RU, EN tillarida 100% to'liq kiritildi.
- [x] Sifat Nazorati (QA Gate):
  * Frontend: `oxlint` 0 ta xato, `tsc -b && vite build` 0 ta xato bilan 4.30 soniyada muvaffaqiyatli yig'ildi.
  * Backend: `ruff check` 0 ta xato, `pytest` 26/26 ta test 100% PASS.


### 2.19. Ustozlar CRM, Admin Kvotalari, Ota-Onani Shaffof Nazorati, Click/Payme Chek OCR va AI Lug'at Generatori (Spaced Repetition)
- [x] 1-Modul: Admin Kvotalari va Ustoz Litsenziya Boshqaruvi:
  * `apps/accounts/models.py`: `TeacherProfile` modeli yaratildi (`pro_quota_balance`, `premium_quota_balance`). `User` modelida helper propertylar (`pro_quota_balance`, `premium_quota_balance`, `teacher_profile_obj`) kiritildi.
  * `POST /api/v1/panel/teachers/<id>/allocate-quota/`: Faqat Superadmin ustoz hisobiga PRO yoki PREMIUM kvotalarini biriktiradi.
  * `POST /api/v1/courses/groups/<group_id>/students/<student_id>/activate-quota/`: Ustoz o'z guruhidagi o'quvchiga 30 kunlik to'liq PRO yoki PREMIUM litsenziya biriktiradi; ustoz kvotasidan 1 ta kamayadi; kvota yetarli bo'lmasa 400 xatolik qaytariladi.
- [x] 2-Modul: Ustozlar Moliya CRM — Davomat, Kurs To'lovlari va Xulosa:
  * `apps/courses/models.py` & `apps/groups/models.py`: `GroupEnrollment` modeli (`monthly_fee`, `billing_cycle_day`, `last_payment_date`, `next_payment_due`, `payment_status` ['paid', 'due_soon', 'overdue', 'grace_period'], `parent_phone`, `parent_telegram_id`).
  * `record_payment(amount, extend_days=30)` va `update_status(today)` metodlari orqali to'lovlar sanasi va qarzdorliklar avtomatik boshqariladi.
  * `GET /api/v1/courses/groups/<group_id>/finance-summary/`: Guruhdagi umumiy o'quvchilar, yig'ilgan tushum, qarzdorlik, o'quvchilar to'lov ro'yxati va ustoz kvotalari.
  * `POST /api/v1/courses/groups/<group_id>/send-payment-reminders/`: [ 📢 Barcha qarzdorlarga eslatma yuborish ] 1-klikli tugma orqali Telegram xabarnomalari.
- [x] 3-Modul: Telegram Bot Integratsiyasi — Avto-Eslatmalar, Ota-Ona Nazorati va Chek OCR:
  * `apps/tuition/tasks.py`: `check_group_tuition_due_dates_task` Celery Beat taski — har kuni soat 10:00 da to'lov muddatiga 2 kun qolganda, to'lov kunida va muddat o'tganda talaba va uning ota-onasiga rasmiy eslatma yuboradi.
  * Ota-onalar "Shaffof Nazorat" tizimi: `ParentStudentRelation` va `GroupEnrollment.parent_telegram_id` ga to'lov va davomat xabarlari yetkaziladi.
  * `apps/payments/receipt_scanner.py`: Click va Payme to'lov cheki skrinshotlarini avtomatik OCR va Vision AI orqali tekshirish, summani va Trans ID ni aniqlash, o'quvchi to'lovini 30 kunga uzaytirish va ustozga bildirishnoma yuborish.
- [x] 4-Modul: AI Lug'at Generatori va Interval Takrorlash (Spaced Repetition):
  * `apps/vocabulary/`: `VocabularyPack` va `StudentWordMistake` modellari.
  * `apps/vocabulary/services/vocab_generator.py`: 50–60 ta inglizcha so'zdan 4 formatli mashq generatsiyasi (Multiple Choice, Spelling/Imlo, Eng ➔ Uzb, Uzb ➔ Eng).
  * Ebbinghaus "Unutish egri chizig'i" bo'yicha bot viktorinasi (`/vocab`): Talaba adashgan so'zlar bo'yicha Quiz-Poll yuboriladi; ketma-ket 3 marta to'g'ri topilsa `is_mastered = True` maqomiga o'tadi.
- [x] 5-Modul: Frontend UI/UX va Bot Menyulari:
  * `TeacherFinanceDashboard.tsx`: Moliyaviy KPI kartalari, qarzdorlar jadvali, 1-klikli ommaviy eslatma tugmasi, to'lovni tasdiqlash va litsenziya berish.
  * `TeacherVocabGenerator.tsx`: 50-60 ta so'z kiritish textarea, 4 xil formatdagi jonli preview tablari va guruhga vazifa qilib biriktirish.
  * `Groups.tsx`: Guruh a'zolari ro'yxatida har bir talaba yonida `[ ⚡ PRO ]` va `[ 👑 VIP ]` kvota tugmalari.
  * Bot buyruqlari: `/finance` (ustoz uchun CRM) va `/vocab` (o'quvchi uchun Spaced Repetition viktorinasi).
- [x] 6-Modul: QA Darvozasi, Sinov va Xavfsizlik:
  * `tests/test_crm_quota_vocab.py`: 10 ta yangi test 100% PASS.
  * Regressiya testlari: 13/13 test 100% PASS.
  * Frontend: `oxlint` 0 xato, `tsc -b && vite build` 0 xato bilan 4.31s da yig'ildi.
  * Mualliflik: `Komiljon Roziyev <kruziyev0@gmail.com>` (Zero AI attribution).

## 3. Jarayonda
- Yangilanishlarni Git orqali yuborish va VPS serverda faqat `grandec` (lms) xizmatlarini qayta yuklash.

---

## 4. Keyingi qadamlar
- Yangi 5 000 so'mlik Starter tarifining konversiyasini kuzatish.
