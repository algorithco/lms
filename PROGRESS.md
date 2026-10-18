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

---

## 3. Jarayonda
- Barcha talablar to'liq va mukammal bajarildi.

---

## 4. Keyingi qadamlar
- Mobil qurilmalarda real imtihon topshirayotgan foydalanuvchilarning UX qulayligini doimiy kuzatib borish.
- Telegram orqali kirish (1-klikli login) funksiyasini keyingi bosqichda joriy qilish.

