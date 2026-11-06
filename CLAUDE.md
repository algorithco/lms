# Grand Education (grandec.uz) — loyiha konteksti

Bu fayl Claude Code uchun doimiy kontekst. Har sessiyada shu qoidalarga amal qil.

## Loyiha haqida
- **Nima:** Milliy Sertifikat, Pedagoglar Attestatsiyasi va ingliz tili (CEFR Multi-level B2/C1, IELTS Academic/General) imtihonlariga tayyorlovchi AI LMS.
- **Domen:** https://grandec.uz
- **Server:** Contabo VPS, loyiha `/opt/lms` katalogida, Docker konteynerlarda.
- **Lokal:** `C:\Users\user\Desktop\lms`
- **MUHIM:** Shu serverda `bestway` degan BOSHQA loyiha ham ishlaydi. Uning konteynerlari, tarmoqlari, volume'lari, nginx konfiguratsiyasi va portlariga HECH QACHON tegma.

## Texnologik stek
- **Backend:** Django + Django REST Framework
- **Baza:** PostgreSQL
- **Frontend:** React + TypeScript + Vite
- **Fon vazifalari:** Celery + Redis
- **PDF (vedomost):** ReportLab
- **Telegram bot:** Aiogram (`@uz_essaygrader_bot`, nomi `grandEducation`)

## Fanlar (subject)
1. Ona tili va Adabiyot — BMB Milliy Sertifikat, 12 mezonli esse baholash
2. Pedagoglar Attestatsiyasi 2026 — 50 talik sinov
3. Ingliz tili — CEFR Multi-level (B2/C1) va IELTS (Academic & General)

Har bir fanning natija tahlili, mavzu kategoriyalari, baholash shkalasi va yorliqlari (masalan "BMB", "Milliy Sertifikat bali") FAQAT o'sha fanga tegishli bo'lishi kerak. Fanlar logikasini hech qachon aralashtirma.

## Modullar
Dashboard, Testlar (CBT), AI Esse Studiyasi (12 mezon + IELTS Writing), 1v1 Arena (jonli duel), Natijalar va Tahlil, Titul (OMR) Skaner, AI Speaking, Ustoz kabineti (guruhlar, o'quvchilar, AI Vision Test Konvertor, Vedomost), Admin panel.

## Rollar
- **Student** — FREE yoki PRO tarif
- **Teacher (Ustoz)** — guruh, o'quvchi, test, vedomost
- **Admin** (`ADMIN_UNLIMITED`) — limitsiz; to'lov cheklarini tekshiradi, o'quvchilarga PRO beradi, ustozlarga limit qo'yadi. Adminga obuna sotish menyusi ko'rsatilmasligi kerak.

## Ish qoidalari
1. **Avval o'qi, keyin o'zgartir.** Har vazifadan oldin tegishli fayllarni o'qib, qisqa reja tuz.
2. **Hardcode qilma.** Test savollari, statistika, natijalar — hammasi bazadan/API'dan kelsin. Soxta (demo) ma'lumot qo'yma; ma'lumot bo'lmasa toza "empty state" ko'rsat.
3. **Ikki xil "til" bor, aralashtirma:** interfeys tili (i18n: UZ/EN) va o'quv fani (subject). Ular alohida state bo'lishi shart.
4. **Barcha UI matnlari i18n orqali.** Komponentlarga to'g'ridan-to'g'ri o'zbekcha/inglizcha matn yozma.
5. **Stil yondashuvini birxillashtir.** Loyihada mavjud dizayn tizimiga (index.css o'zgaruvchilari / tanlangan yondashuv) mos yoz; yangi komponent eskilaridan farqli ko'rinmasin. Kunduzgi va tungi rejimni doim tekshir.
6. **Migratsiyalar ehtiyotkor.** Mavjud ma'lumotni o'chiradigan yoki buzadigan migratsiya yozma. Har migratsiyadan oldin nima qilishini tushuntir.
7. **Sirlar.** `.env`, tokenlar, parollarni kodga yozma, commit qilma, chatga chiqarma.
8. **Har bosqichdan keyin tekshir:** frontend `npm run build` (va `tsc --noEmit`, lint bo'lsa), backend `python manage.py check` va testlar. Xato bilan commit qilma.
9. **Kichik commitlar,** tushunarli xabar bilan (masalan `fix(exam): hooks order causing React #310`).
10. **Production'ga deploy faqat foydalanuvchi aniq ruxsat bergandan keyin.** Serverda buyruq ishlatishdan oldin aniq nima qilishingni ayt.
11. **Mobil va desktop** ikkalasida ham ishlashini hisobga ol.

## Tuzatish rejasi
Batafsil reja va progress: `docs/FIX_PLAN.md`. Har sessiyada o'sha fayldagi keyingi bajarilmagan bosqichni bajar va checkboxlarni yangilab qo'y.
