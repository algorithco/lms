# LMS Platform — Loyiha rivojlanish progressi (PROGRESS.md)

## 1. Maqsad
1. Obuna sahifasidagi narx xatosini to'g'irlash: PRO tarifini qat'iy 49 000 so'm/oy, Starter 15 000 so'm/oy, Premium 60 000 so'm/oy qilib mixlash.
2. Ustoz va o'quvchilarga avtomatik PRO tarifini biriktirish tizimini to'liq kod darajasida amalga oshirish:
   - Ro'yxatdan o'tishda `role = 'teacher'` tanlanganida ustozga avtomatik guruh ochish va test yaratish huquqlarini berish.
   - O'quvchi ustoz guruhining taklif kodini (#GR-XXX) kiritib guruhga qo'shilishi bilanoq, uning hisobiga avtomatik ravishda **PRO tarifi** yoqilishi (365 kun, cheksiz testlar, kunlik 50 ta AI repetitor kvotasi).
   - O'quvchi profilida "Tarif: PRO (Ustoz guruhi orqali)" ko'rinishi.
   - Ustoz kabinetida har bir o'quvchining PRO holati (`⭐ PRO (Faol)`), ishlagan testlari va esselari aks etishi.
3. Attestatsiya 2026 yangi diagnostika testini 50 ta savoli bilan bazaga seed qilish, kategoriyalashtirish va VPS ga deploy qilish.

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

---

## 3. Jarayonda
- Barcha talablar to'liq bajarildi, testlar 100% muvaffaqiyatli o'tdi, VPS deployment bosqichi.

---

## 4. Keyingi qadamlar
- Production serverida test va esse natijalari monitoringini olib borish.
- O'quvchilarning real imtihon ko'rsatkichlarini tahlil qilish.
