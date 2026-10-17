# LMS Platform — Loyiha rivojlanish progressi (PROGRESS.md)

## 1. Maqsad
"Rash test. Umid Shukurov jamoasi" (BMBA Namunaviy Milliy Sertifikat) 3 soatlik rasmiy diagnostika imtihonini barcha matnlari, 44 ta savoli, rasmiy javob kalitlari va 45-esse topshirig'i bilan birga Django bazasiga kiritish, moslashtirish va 2 talik ochiq savollar interfeysini qulay holatga keltirish, tezkor kirish chiplarini yaratish hamda Contabo VPS serveriga (`169.58.58.229` / `grandec.uz`) muvaffaqiyatli deploy qilish.

---

## 2. Bajarildi

### 2.1. Backend va Baza Seederi (`apps/tests/`)
- [x] Yangi `seed_rash_mock_shukurov` Django seeder buyrug‘i yaratildi (`apps/tests/management/commands/seed_rash_mock_shukurov.py`).
- [x] Test nomi: "Ona tili va Adabiyot — Rasmiy Mock Test (Umid Shukurov jamoasi)"
- [x] Mock kodi: `#MOCK-SHUKUROV`, davomiyligi: 180 daqiqa (3 soat), 45 ta topshiriq (44 test + 45-esse).
- [x] 4 ta rasmiy bo'lim integratsiya qilindi:
  - `LANGUAGE` (1–17-savollar): Grammatika, leksika, orfografiya, morfologiya
  - `READING` (18–27-savollar): "O'lik dengiz" (18–22) va "Ming marta shukur!" (23–27) matnlari tahlili
  - `LITERATURE` (28–35-savollar): Navoiy g'azali tahlili (28–32) va sintaktik tahlil moslashtirishlari (33–35)
  - `WRITING` (36–45-savollar): Ochiq savollar (36–44) va 45-rasmiy 12 mezonli publitsistik esse topshirig'i
- [x] Barcha 3 ta matn (passages) kiritildi va savollarga bog'landi.
- [x] 4-savoldagi PDF vektor glyph qiyinchiligi to'liq hal qilindi: rasmiy kalit (4b: `bo'sh, xom, puch`) va to'liq variantlar kiritildi.
- [x] 45-esse topshirig'i uchun alohida `EssayTopic` (ID 2) sinxron yaratildi (Kamida 150 ta so'z, 12 mezonli BMB baholash).

### 2.2. Frontend CBT Interfeysi & UX (`frontend/src/`)
- [x] `frontend/src/pages/TakeTest.tsx`:
  - 40, 41, 42, 43, 44-savollar uchun alohida `a)` va `b)` 2 talik kirish maydonlari integratsiya qilindi.
  - JSON parsing va string formatidagi ikki qismli javoblarni avtomatik o'qish va xatosiz saqlash ta'minlandi.
  - 33, 34, 35-savollar uchun tezkor variant tanlash pill paneli (`A-F`) qulay joylashtirildi.
  - Matnlar uchun desktopda parallel split-view, mobilda esa akkordeon rejim saqlandi.
  - Test yakunlashda esse yozilmagan bo'lsa ogohlantirish modal dialogi ishlaydi.
- [x] `frontend/src/pages/Tests.tsx`:
  - `#MOCK-SHUKUROV` tezkor kirish chipi va 1-klikli ulanish tugmasi qo'shildi.
  - Shukurov mock testi ro'yxatda yuqoriga pin qilindi va alohida amber rangli nishon (`🔥 Rasmiy Mock (Umid Shukurov)`) bilan ajratildi.
- [x] `frontend/src/i18n/translations.json`:
  - Rus va ingliz tili tarjimalaridagi barcha yozuvlar tiklandi va tozalandi.

### 2.3. Sifat va Testlash (QA Gate)
- [x] `ruff check .` — Barcha linter qoidalari muvaffaqiyatli o'tdi.
- [x] `npm run build` — TypeScript va Vite production yig'ish 0 xato bilan yakunlandi (3.67s).
- [x] `pytest -q` — 1161 ta test 100% muvaffaqiyatli o'tdi (0 failed).

### 2.4. Production Deploy (`grandec.uz`)
- [x] Git commits Komiljon Roziyev (`kruziyev0@gmail.com`) nomidan, hech qanday AI atributsisiz `main` ga push qilindi.
- [x] VPS serverida (`169.58.58.229`) git yangilandi:
  - `seed_rash_mock_shukurov` buyrug'i production bazasida ishga tushirildi: Test ID 2 (`#MOCK-SHUKUROV`) to'liq 45 ta savoli bilan yaratildi.
  - Yangi yig'ilgan SPA bundle `/var/lib/docker/volumes/lms-platform-prod_spa_volume/_data/` ga ko'chirildi va Nginx qayta yuklandi.
  - Public endpoint tekshirildi: `https://grandec.uz/` -> `HTTP 200 OK`.

---

## 3. Jarayonda
- Barcha talablar to‘liq amalga oshirildi va production muhitida muvaffaqiyatli tekshirildi.

---

## 4. Keyingi qadamlar
- O'quvchilar va abituriyentlarning imtihon topshirish statistikasi va AI esse baholash natijalarini kuzatib borish.
- Yangi diagnostika testlari kelganda ularni ham xuddi shu yuqori andozada platformaga integratsiya qilish.

---

## 5. Muhim qarorlar
- Savol 4 dagi matnlar PDF ichida vektor yo'nalishlar sifatida chizilganligi sababli, uning geometrik parametrlari tahlil qilinib, to'g'ri variantlar (`bo'sh, xom, puch`) kiritildi.
- 40–44-savollar ikki mustaqil qismdan (`a)` va `b)`) iborat bo'lganligi sababli bitta matn maydoni o'rniga strukturalangan ikkita alohida input orqali foydalanuvchiga taqdim etildi.
