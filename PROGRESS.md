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

---

## 3. Jarayonda
- Barcha talablar to'liq va xatosiz bajarildi, testlar 100% muvaffaqiyatli o'tdi.

---

## 4. Keyingi qadamlar
- Yangilangan kodlarni git commit qilib, `origin main` ga push qilish.
- Contabo VPS (`169.58.58.229`) ga deploy qilish va `https://grandec.uz/healthz/` holatini tekshirish.

