# CD-format test modeli — loyiha (tasdiqlash uchun)

> Holat: **taklif**, kod yozilmagan. Tasdiqlangandan keyin migratsiya va seed yoziladi.

## 1. Hozir bazada nima bor

`Test → ExamSection (code, duration_minutes, audio_url) → Question (reading_passage, config.part, ...)`

Mavjud savol turlari: `MULTIPLE_CHOICE`, `INLINE_GAP_FILL` (+ `GapBlank`), `MATCHING` (+ `MatchingPrompt/Option/Pair`), `MAP_LABELING`, `TRUE_FALSE_NOT_GIVEN`, `written` (ExamWrittenBridge orqali AI baholash).

Yo'q narsalar:
- **Part** alohida obyekt emas, faqat `Question.config["part"]` raqami.
- **QuestionGroup** yo'q: umumiy instruksiya, so'z limiti ("ONE WORD and/or A NUMBER"), rasm va audio guruhga biriktirilmaydi.
- Rasm maydoni umuman yo'q (xarita, speaking rasmlari).
- Speaking savol turi yo'q (hozir `SHORT_ANSWER`, ya'ni kalitsiz obyektiv savol sifatida tekshiriladi).

## 2. Taklif: faqat qo'shimcha (additive) o'zgarishlar

```
Test
 └─ ExamSection        (mavjud)  LISTENING / READING / WRITING / SPEAKING, duration_minutes, audio
     └─ ExamPart       (YANGI)   number, title, instructions, audio (FileField), order
         └─ QuestionGroup (YANGI) instructions, answer_rule ("ONE WORD and/or A NUMBER"),
                                  passage (FK ReadingPassage, ixtiyoriy), image (ImageField),
                                  options_label ("Statements A–J"), each_option_once (bool), order
             └─ Question  (mavjud) + group (FK, NULL bo'lishi mumkin)
```

- `Question.group` — **nullable FK**: eski testlar (group=NULL) avvalgidek ishlaydi.
- Yangi savol turi `SPEAKING_PROMPT`: `config = {"prep_seconds": 60, "answer_seconds": 120}`; obyektiv tekshirilmaydi, Writing kabi "baholanmoqda" holatiga tushadi.
- Gap-fill: bitta bo'shliq uchun bir nechta `GapBlank` qatori = muqobil javoblar. Raqamlar uchun `config.number_words=true` bo'lsa, "6" ↔ "six" (0–100) teng hisoblanadi; katta-kichik harf va bo'shliqlar allaqachon normallashtiriladi (`scoring.normalize_text`).
- Fayllar: `media/exams/<mock_code>/listening/part-1.mp3 … part-6.mp3`, `media/exams/<mock_code>/images/…`.

**Migratsiya:** 2 ta yangi jadval, `Question` ga 1 ta nullable ustun, 1 ta yangi choice qiymati. Mavjud ma'lumot o'chirilmaydi va o'zgarmaydi.

## 3. Seed / import

- Test mazmuni Python kodda emas, `apps/tests/fixtures/mocks/record_mock_1.json` faylida turadi: bo'limlar → qismlar → guruhlar → savollar → kalitlar.
- `python manage.py import_cd_mock record_mock_1.json [--dry-run] [--replace]` — idempotent, `mock_code` bo'yicha.
- Test: JSON'dagi 70 ta L/R kalit PDF'dagi javoblar sahifasi (18-bet) bilan solishtiriladi; import qilingan bazadagi kalitlar ham JSON bilan solishtiriladi.

## 4. Imtihon dvigateli

- Savollar `section → part → group` tartibida render qilinadi; guruh instruksiyasi, rasmi va so'z limiti bir marta ko'rsatiladi.
- Bo'lim taymeri: Listening 45, Reading 60, Writing 60 daqiqa (`ExamSection.duration_minutes`).
- Audio yo'q bo'lsa: Listening "audio yuklanmagan" holatida ko'rsatiladi, savollarga javob berish mumkin.
- Javob kalitlari student API'ga hech qachon chiqmaydi (hozir ham chiqmaydi: tekshirildi).
- Preview (admin/ustoz): `TestAttempt.is_preview` (default False). Preview urinishlari statistika, reyting va vedomostga tushmaydi.
