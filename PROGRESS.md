# LMS Platform — Loyiha rivojlanish progressi (PROGRESS.md)

## 1. Maqsad
Platformaning Testlar bo‘limida yangi "ATTESTATSIYA" toifasini ochish, "Attestatsiya Diagnostika-2026 (19)" 50 talik rasmiy attestatsiya testini to‘liq kalitlari, matnlari va AI tushuntirishlari bilan Django bazasiga kiritish, frontendda zamonaviy foydalanuvchi tajribasini (kategoriya filtri, split passage ko‘rinishi, moslashtirish, bo‘limlar kesimidagi ball tahlili va xatolarni ko‘rsatish) ta'minlash hamda Contabo VPS serveriga (`169.58.58.229` / `grandec.uz`) muvaffaqiyatli deploy qilish.

---

## 2. Bajarildi

### 2.1. Backend va Baza Seederi (`apps/tests/`)
- [x] Yangi `seed_attestatsiya_test_2026` Django management buyrug‘i yaratildi (`apps/tests/management/commands/seed_attestatsiya_test_2026.py`).
- [x] "Attestatsiya" toifasi (`slug='attestatsiya'`), "Ona tili va Adabiyot (Attestatsiya 2026)" kursi va "Ona tili va Adabiyot — Rasmiy Attestatsiya Diagnostika 2026" (Mock code: `#MOCK-ATTEST2026`, 100 daqiqa, 50 ta savol, 60% o'tish bali) yaratildi.
- [x] 3 ta ixtisoslashgan bo‘lim shakllantirildi:
  - `MUTAXASSISLIK` (1–35-savollar): Mutaxassislik fani (Ona tili va adabiyot)
  - `KASB_STANDARTI` (36–40-savollar): Kasbiy standart (O'qituvchi kompetensiyalari)
  - `PEDAGOGIKA` (41–50-savollar): Pedagogik mahorat va metodika
- [x] 2 ta matn kiritildi va savollarga bog‘landi:
  - 1–5-savollar: "DUNYO TILLARI HAQIDA QIZIQARLI MA’LUMOTLAR" ilmiy matni
  - 21–25-savollar: Metin va uning ota-onasi haqidagi o'tkir satirik hikoya
- [x] 50 ta rasmiy test savoli, 4 tadan variantlari, rasmiy kalitlari va tushuntirishlari kiritildi.
- [x] `TestListSerializer` da `category_slug`, `category_name`, `mock_code` maydonlari integratsiya qilindi.
- [x] Attestatsiya ballash profili (`ExamScoringProfile`) yaratildi: `MUTAXASSISLIK`, `KASB_STANDARTI`, `PEDAGOGIKA` bo‘limlari bo‘yicha to‘liq hisob-kitob.

### 2.2. Frontend Integratsiyasi (`frontend/src/`)
- [x] `frontend/src/lib/testing.ts`: `TestListItem` interfeysi yangi toifa maydonlari bilan boyitildi.
- [x] `frontend/src/pages/Tests.tsx`:
  - Yangi toifalar filtri qo‘shildi: `[ Barchasi ] [ Milliy Sertifikat ] [ Attestatsiya (Ustozlar uchun) ] [ 1v1 Arena ]`.
  - Attestatsiya diagnostika testiga tezkor kirish tugmasi (`#MOCK-ATTEST2026`) va vizual badge qo‘shildi.
  - 1v1 Arena bo‘limi kartasi va to‘g‘ridan-to‘g‘ri navigatsiyasi qo‘shildi.
- [x] `frontend/src/pages/TakeTest.tsx`:
  - 41 va 42-savollardagi moslashtirish bandlari va mumtoz she'riy misralar uchun qator buzilmasligi (`whiteSpace: 'pre-line'`) ta'minlandi.
  - Desktopda matn va savol parallel (split view), mobilda esa qulay ochilib-yopiluvchi akkordeon ko‘rinishi ishlaydi.
- [x] `frontend/src/pages/Results.tsx`:
  - Test yakunida 3 ta bo‘lim (`Mutaxassislik`, `Kasbiy standart`, `Pedagogik mahorat`) bo‘yicha foiz va ballar alohida progress-barlar bilan vizuallashtirildi.
  - Xato ishlangan savollar tahlili:
    - ❌ Sizning javobingiz
    - ✅ To‘g‘ri javob
    - 💡 Nega bu javob xato? AI tushuntirishi (avtomatik ochiq turadi).

### 2.3. Sifat va Testlash (QA Gate)
- [x] `tests/test_attestatsiya_test_2026.py` test to‘plami yozildi:
  - 50 ta savol mavjudligi va toifalarga bo‘linganligi (35, 5, 10).
  - 100% rasmiy javob kalitlari muvofiqligi.
  - Matnlar bog‘lanishi va variantlar to‘liqligi.
- [x] `pytest tests/test_attestatsiya_test_2026.py` — **100% PASS (1 passed in 19.44s)**.
- [x] `npm run build` — **0 xato (Vite build 2.33s)**.

### 2.4. Production Deploy (`grandec.uz`)
- [x] O‘zgarishlar GitHub `main` tarmog‘iga push qilindi (`Komiljon Roziyev` profilida, no-AI attribution).
- [x] CI/CD avtomatik ravishda Docker prod konteynerlarini (`ghcr.io/algorithco/lms:sha-fce2375`) yig‘ib, VPS ga deploy qildi.
- [x] Production VPS serverida (`169.58.58.229`):
  - `docker compose exec web python manage.py seed_attestatsiya_test_2026` ishga tushirildi: 50 ta savol to‘liq PostgreSQL bazasiga kiritildi.
  - Public endpoint tekshirildi: `curl https://grandec.uz/healthz/` -> `HTTP 200 OK` (`{"status": "ok", "db": true, "version": "0.98.0"}`).

---

## 3. Jarayonda
- Barcha talablar to‘liq amalga oshirildi va production muhitida muvaffaqiyatli tekshirildi.

---

## 4. Keyingi qadamlar
- O'qituvchilar uchun attestatsiya natijalari asosida shaxsiy tahliliy PDF sertifikat yoki ma'lumotnoma generatsiya qilish imkoniyatini ko'rib chiqish.
- Foydalanuvchi va ustozlarning diagnostika testini yechish statistikasi hamda analitikasini kuzatib borish.

---

## 5. Muhim qarorlar
- **37-savoldagi nusxa xatosi to'g'rilandi**: Asl faylda D varianti "A) Hayot xavfsizligi asoslarini" deb xato belgilangan edi. Bu baza kiritilishida D varianti sifatida to'g'rilandi, rasmiy to'g'ri javob kaliti B saqlab qolindi.
- **Ko'p qatorli matn va moslashtirish savollari**: 41 va 42-savollar (moslashtirish) hamda 26–35-savollardagi she'riy parchalar formatini to'g'ri saqlash uchun frontendda `pre-line` uslubi qo'llandi.
- **Nol uzilishli deploy**: Persistent PostgreSQL va Redis hajmlari saqlangan holda faqat app konteynerlari yangilandi va production healthz 200 OK tasdiqlandi.
