"""
Rich Content Seeder for GRAND EDUCATION LMS (`python manage.py seed_content`).

Idempotently seeds:
1. Courses & Subjects for Ona tili va Adabiyot (`uzbek`) and Ingliz tili (`english`).
2. Complete Ona tili va Adabiyot (BMB Milliy Sertifikat) diagnostic & mock tests (`subject="uzbek"`).
3. Complete Pedagoglar Attestatsiyasi 2026 diagnostic tests (`subject="uzbek"`).
4. Complete English CEFR Multi-level & IELTS practice tests (`subject="english"`) with Listening/Reading sections and question types.
5. Official EssayTopics (6+ each for `ielts_task1`, `ielts_task2`, `ona_tili`, `adabiyot`, `multilevel`).
6. Official SpeakingTopics (6+ each for `part1`, `part2`, `part3`, `multilevel`).
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import BaseCommand, call_command
from django.db import transaction

from apps.courses.models import Category, Course, Subject
from apps.essays.models import EssayTopic
from apps.speaking.models import SpeakingTopic
from apps.tests.models import (
    Choice,
    ExamPart,
    ExamSection,
    GapBlank,
    Question,
    QuestionGroup,
    ReadingPassage,
    Test,
)

User = get_user_model()


BMB_DIAGNOSTIC_TESTS = [
    {
        "mock_code": "#MOCK-BMB-DIAG-01",
        "title": "Ona tili va Adabiyot — BMB Milliy Sertifikat Diagnostika 1-variant",
        "description": (
            "Bilim va malakalarni baholash agentligi (BMB) standartlari asosida "
            "tuzilgan Milliy Sertifikat diagnostik testi. Grammatika, o'qish savodxonligi "
            "va badiiy-adabiy tahlil bo'limlarini o'z ichiga oladi."
        ),
        "exam_type": "milliy_sertifikat",
        "time_limit_minutes": 90,
        "sections": [
            {
                "code": "grammar",
                "name": "Ona tili (Grammatika)",
                "part_number": 1,
                "part_title": "1-qism: Imlo, fonetika va morfologiya",
                "questions": [
                    {
                        "text": "Qaysi qatordagi barcha so'zlar imlo qoidalariga ko'ra to'g'ri yozilgan?",
                        "options": [
                            ("ta'limot, ma'rifat, jur'at, mas'uliyat", True),
                            ("talimot, ma'rifat, jurat, masuliyat", False),
                            ("ta'limot, marifat, jur'at, mas'uliyat", False),
                            ("ta'limot, ma'rifat, jur'at, masuliyat", False),
                        ],
                        "explanation": "Tutuq belgisi arab tilidan o'zlashgan ta'limot, ma'rifat, jur'at va mas'uliyat so'zlarining barchasida yoziladi.",
                    },
                    {
                        "text": "Qaysi gapda ko'chma ma'noli (metafora usulidagi) so'z qo'llangan?",
                        "options": [
                            ("Ilmning oltin kaliti sabr va izlanishdir.", True),
                            ("Usta temirdan yangi kalit yasab berdi.", False),
                            ("Kitob javonida o'nta badiiy asar turibdi.", False),
                            ("Bahorda bog'dagi olma daraxtlari gulladi.", False),
                        ],
                        "explanation": "'Ilmning oltin kaliti' birikmasida 'oltin' va 'kalit' so'zlari o'xshashlik asosida ko'chma ma'noda (metafora) qo'llangan.",
                    },
                    {
                        "text": "Fe'lning vazifa shakllari qatnashgan gapni aniqlang.",
                        "options": [
                            ("Ko'p o'qigan inson har doim teran fikrlaydi.", True),
                            ("Kecha kutubxonadan yangi lug'at oldim.", False),
                            ("Biz ertaga viloyat olimpiadasiga boramiz.", False),
                            ("Quyosh chiqdi va atrof yorishdi.", False),
                        ],
                        "explanation": "'O'qigan' so'zi sifatdosh shakli bo'lib, fe'lning xoslangan (vazifa) shakliga kiradi.",
                    },
                    {
                        "text": "Qaysi javobda paronimlar juftligi keltirilgan?",
                        "options": [
                            ("abzal — afzal, asr — asir", True),
                            ("katta — ulkan, chiroyli — go'zal", False),
                            ("oq — qora, yaxshi — yomon", False),
                            ("yuz (inson a'zosi) — yuz (son)", False),
                        ],
                        "explanation": "Talaffuzi bir-biriga yaqin, ammo ma'nosi farqli bo'lgan so'zlar (abzal/afzal, asr/asir) paronimlar hisoblanadi.",
                    },
                    {
                        "text": "Ergashgan qo'shma gap berilgan qatorni toping.",
                        "options": [
                            ("Mehnat qilsang, baxt va muvaffaqiyat senga kulib boqadi.", True),
                            ("Bahor keldi va daraxtlar kurtak yozdi.", False),
                            ("Havo bulutli edi, lekin yomg'ir yog'madi.", False),
                            ("Tong otdi, qushlar sayray boshladi.", False),
                        ],
                        "explanation": "'-sa' shart mayli qo'shimchasi ergash gapni bosh gapga tobelantirib bog'lagan.",
                    },
                ],
            },
            {
                "code": "reading",
                "name": "O'qish savodxonligi",
                "part_number": 2,
                "part_title": "2-qism: Ilmiy-ommabop matn tahlili",
                "passage": (
                    "Sun'iy intellekt texnologiyalari bugungi kunda ta'lim, tibbiyot va sanoatning "
                    "barcha jabhalariga jadal kirib bormoqda. Biroq mutaxassislarning ta'kidlashicha, "
                    "texnologik vositalar insonning tanqidiy fikrlash va ijodiy yondashuv qobiliyatini "
                    "almashtira olmaydi, balki uni boyituvchi ko'makchi vosita bo'lib xizmat qiladi."
                ),
                "questions": [
                    {
                        "text": "Matn mazmuniga ko'ra sun'iy intellektning asosiy vazifasi nimadan iborat?",
                        "options": [
                            ("Inson qobiliyatlarini boyituvchi ko'makchi vosita bo'lish", True),
                            ("Insonning ijodiy fikrlashini butunlay almashtirish", False),
                            ("Faqat sanoat korxonalarida ishlash", False),
                            ("Ta'lim tizimida o'qituvchilar o'rnini to'liq egallash", False),
                        ],
                        "explanation": "Matnda texnologiya insonning tanqidiy va ijodiy qobiliyatini almashtira olmasligi, balki ko'makchi vosita ekani ta'kidlangan.",
                    },
                    {
                        "text": "Matnda qaysi sohalar bevosita sanab o'tilgan?",
                        "options": [
                            ("Ta'lim, tibbiyot va sanoat", True),
                            ("Qishloq xo'jaligi, sport va san'at", False),
                            ("Kosmonavtika va arxitektura", False),
                            ("Faqat bank-moliya tizimi", False),
                        ],
                        "explanation": "Birinchi gapda ta'lim, tibbiyot va sanoat sohalari aniq ko'rsatilgan.",
                    },
                    {
                        "text": "Matndan kelib chiqadigan asosiy xulosa qaysi?",
                        "options": [
                            ("Texnologiya rivojlansa ham tanqidiy va ijodiy fikrlash insonning ustuvor fazilati bo'lib qoladi", True),
                            ("Kelajakda kitob o'qishga ehtiyoj qolmaydi", False),
                            ("Sun'iy intellekt barcha kasblarni yo'q qiladi", False),
                            ("Tanqidiy fikrlash faqat dasturchilarga kerak", False),
                        ],
                        "explanation": "Muallif texnologiya inson tafakkurining o'rnini bosa olmasligini asosiy xulosa sifatida ilgari surgan.",
                    },
                ],
            },
            {
                "code": "literature",
                "name": "Adabiyot va G'azal tahlili",
                "part_number": 3,
                "part_title": "3-qism: Mumtoz va zamonaviy adabiyot",
                "questions": [
                    {
                        "text": "Alisher Navoiyning «Xamsa» asaridagi birinchi doston qaysi?",
                        "options": [
                            ("«Hayrat ul-abror»", True),
                            ("«Farhod va Shirin»", False),
                            ("«Layli va Majnun»", False),
                            ("«Saddi Iskandariy»", False),
                        ],
                        "explanation": "«Hayrat ul-abror» («Yaxshi kishilarning hayratlanishi») 1483-yilda yozilgan bo'lib, «Xamsa»ning birinchi dostonidir.",
                    },
                    {
                        "text": "Abdulla Qodiriyning «O'tkan kunlar» romanida Otabek qaysi shaharga savdo ishlari bilan borib, u yerda Kumushbibini uchratadi?",
                        "options": [
                            ("Marg'ilon", True),
                            ("Qo'qon", False),
                            ("Samarqand", False),
                            ("Buxoro", False),
                        ],
                        "explanation": "Otabek Toshkentdan Marg'ilonga savdo karvoni bilan borib, Mirzakarim qutidor xonadonida mehmon bo'ladi.",
                    },
                ],
            },
        ],
    },
    {
        "mock_code": "#MOCK-BMB-DIAG-02",
        "title": "Ona tili va Adabiyot — BMB Milliy Sertifikat Diagnostika 2-variant",
        "description": (
            "Milliy Sertifikat (BMB) imtihoniga tayyorgarlik ko'ruvchilar uchun "
            "2-diagnostika varianti. Sintaksis, uslubiyat, matn tahlili va adabiyotshunoslik savollari."
        ),
        "exam_type": "milliy_sertifikat",
        "time_limit_minutes": 90,
        "sections": [
            {
                "code": "grammar",
                "name": "Ona tili (Grammatika)",
                "part_number": 1,
                "part_title": "1-qism: Sintaksis va punktuatsiya",
                "questions": [
                    {
                        "text": "Qaysi gapda undalma ishtirok etgan?",
                        "options": [
                            ("Aziz yoshlar, vaqtning har bir daqiqasini qadrlang!", True),
                            ("Yoshlarimiz xalqaro fan olimpiadalarida g'olib bo'ldilar.", False),
                            ("Kitob insonning eng yaqin do'sti va maslahatchisidir.", False),
                            ("Bugun maktabimizda adabiy kecha tashkil etildi.", False),
                        ],
                        "explanation": "'Aziz yoshlar' so'zlovchining nutqi qaratilgan shaxsni bildiruvchi undalmadir.",
                    },
                    {
                        "text": "Qaysi qatorda ibora (frazeologizm) va uning ma'nosi to'g'ri moslashtirilgan?",
                        "options": [
                            ("Boshi osmonga yetmoq — juda xursand bo'lmoq", True),
                            ("Qo'li ochiq — dangasa, ishyoqmas", False),
                            ("Ko'z qorachig'idek asramoq — e'tiborsiz qoldirmoq", False),
                            ("Yerga urmoq — maqtamoq, ko'klarga ko'tarmoq", False),
                        ],
                        "explanation": "'Boshi osmonga yetmoq' iborasi behad sevinmoq, quvonmoq ma'nosini anglatadi.",
                    },
                    {
                        "text": "Uyushiq bo'lakli gap qaysi javobda berilgan?",
                        "options": [
                            ("Bog'imizda olma, anor, shaftoli va o'rik daraxtlari bor.", True),
                            ("Quyosh botdi va tevarak-atrofga oqshom cho'kdi.", False),
                            ("U ko'p o'qiydi, shuning uchun bilimi mustahkam.", False),
                            ("Agar ertaga havo ochiq bo'lsa, tog'ga chiqamiz.", False),
                        ],
                        "explanation": "'Olma, anor, shaftoli va o'rik' bir xil so'roqqa javob bo'lib, uyushiq aniqlovchi vazifasida kelgan.",
                    },
                    {
                        "text": "Rasmiy-idoraviy uslubga xos hujjat turlari qaysi qatorda berilgan?",
                        "options": [
                            ("Ariza, bayonnoma, ma'lumotnoma, shartnoma", True),
                            ("G'azal, ruboiy, doston, tuyuq", False),
                            ("Teorema, aksioma, formula, reaksiya", False),
                            ("Reportaj, feleton, ocherk, maqola", False),
                        ],
                        "explanation": "Ariza, bayonnoma, ma'lumotnoma va shartnoma rasmiy-idoraviy uslub janrlaridir.",
                    },
                ],
            },
            {
                "code": "reading",
                "name": "O'qish savodxonligi",
                "part_number": 2,
                "part_title": "2-qism: Badiiy va publitsistik matn tahlili",
                "passage": (
                    "Til — millatning ruhi va tarixiy xotirasidir. Har bir so'z zamirida xalqning "
                    "ming yillik hayotiy tajribasi, dunyoqarashi va qadriyatlari mujassam bo'ladi. "
                    "Ona tilini asrab-avaylash faqat tilshunoslarning emas, balki shu tilda so'zlashuvchi "
                    "har bir fuqaroning muqaddas burchidir."
                ),
                "questions": [
                    {
                        "text": "Matnda tilga qanday ta'rif berilgan?",
                        "options": [
                            ("Millatning ruhi va tarixiy xotirasi", True),
                            ("Faqat ilmiy tadqiqot obyekti", False),
                            ("O'zgaruvchan texnik belgilar tizimi", False),
                            ("Faqat yozuvchilar foydalanadigan qurol", False),
                        ],
                        "explanation": "Birinchi gapda 'Til — millatning ruhi va tarixiy xotirasidir' deb ta'riflangan.",
                    },
                    {
                        "text": "Muallifning fikricha, ona tilini asrab-avaylash kimning burchi?",
                        "options": [
                            ("Shu tilda so'zlashuvchi har bir fuqaroning", True),
                            ("Faqat tilshunos olimlarning", False),
                            ("Faqat jurnalist va shoirlarning", False),
                            ("Faqat boshlang'ich sinf o'qituvchilarining", False),
                        ],
                        "explanation": "Matn yakunida bu vazifa har bir fuqaroning muqaddas burchi ekanligi ta'kidlangan.",
                    },
                ],
            },
            {
                "code": "literature",
                "name": "Adabiyot va G'azal tahlili",
                "part_number": 3,
                "part_title": "3-qism: Mumtoz she'riyat va aruz vazni",
                "questions": [
                    {
                        "text": "Zahiriddin Muhammad Bobur qalamiga mansub memuar-tarixiy asar qaysi?",
                        "options": [
                            ("«Boburnoma»", True),
                            ("«Muhokamat ul-lug'atayn»", False),
                            ("«Qutadg'u bilig»", False),
                            ("«Devoni lug'otit-turk»", False),
                        ],
                        "explanation": "«Boburnoma» Boburning jahonga mashhur qomusiy-memuar asaridir.",
                    },
                    {
                        "text": "Cho'lponning «Kecha va kunduz» romanidagi bosh qahramon obrazini toping.",
                        "options": [
                            ("Zebi", True),
                            ("Kumushbibi", False),
                            ("Gulnor", False),
                            ("Saida", False),
                        ],
                        "explanation": "Zebi va Razzoq so'fi obrazlari Cho'lponning «Kecha va kunduz» romaniga mansub.",
                    },
                ],
            },
        ],
    },
]


ATTESTATSIYA_DIAGNOSTIC_TESTS = [
    {
        "mock_code": "#MOCK-ATTEST-DIAG-01",
        "title": "Pedagoglar Attestatsiyasi 2026 — Diagnostika 1-variant (Ona tili va Pedagogika)",
        "description": (
            "Oliy va birinchi malaka toifasiga talabgor pedagoglar uchun 2026-yilgi "
            "Attestatsiya diagnostika testi. Mutaxassislik fani, pedagogik mahorat va "
            "kasbiy standart savollarini qamrab oladi."
        ),
        "exam_type": "attestatsiya",
        "time_limit_minutes": 90,
        "sections": [
            {
                "code": "grammar",
                "name": "Mutaxassislik fani (Ona tili va adabiyot)",
                "part_number": 1,
                "part_title": "1-qism: Tilshunoslik va adabiyotshunoslik",
                "questions": [
                    {
                        "text": "O'zbek tilshunosligida so'z turkumlari necha katta guruhga bo'linadi?",
                        "options": [
                            ("Mustaqil so'zlar, yordamchi so'zlar va alohida guruhdagi so'zlar", True),
                            ("Faqat ot va fe'l guruhlariga", False),
                            ("Faqat sodda va qo'shma so'zlarga", False),
                            ("Bosh bo'laklar va ikkinchi darajali bo'laklarga", False),
                        ],
                        "explanation": "Morfologiyada so'zlar mustaqil, yordamchi va alohida guruhdagi (modal, undov, taqlid) so'zlarga ajratiladi.",
                    },
                    {
                        "text": "Aruz vaznida qisqa hijoni ifodalovchi shartli belgi nima deb ataladi?",
                        "options": [
                            ("V (ochiq va qisqa hijo)", True),
                            ("— (cho'ziq hijo)", False),
                            ("Turoq", False),
                            ("Qofiya", False),
                        ],
                        "explanation": "Aruzda qisqa unli bilan tugagan ochiq bo'g'in qisqa hijo hisoblanadi va 'V' belgisi bilan ko'rsatiladi.",
                    },
                    {
                        "text": "Mahmud Koshg'ariyning turkiy tillar qiyosiy lug'ati hisoblangan mashhur asari qaysi?",
                        "options": [
                            ("«Devoni lug'otit-turk»", True),
                            ("«Hibat ul-haqoyiq»", False),
                            ("«Qissasi Rabg'uziy»", False),
                            ("«Mahbub ul-qulub»", False),
                        ],
                        "explanation": "Mahmud Koshg'ariy XI asrda «Devoni lug'otit-turk» qomusiy lug'atini yaratgan.",
                    },
                ],
            },
            {
                "code": "reading",
                "name": "Pedagogik mahorat va Metodika",
                "part_number": 2,
                "part_title": "2-qism: Zamonaviy didaktika va baholash",
                "questions": [
                    {
                        "text": "Blum taksonomiyasining eng yuqori kognitiv darajasi qaysi javobda ko'rsatilgan?",
                        "options": [
                            ("Yaratish (Sintez) va Baholash", True),
                            ("Bilish va Eslab qolish", False),
                            ("Tushunish", False),
                            ("Qo'llash", False),
                        ],
                        "explanation": "Yangilangan Blum taksonomiyasida Tahlil, Baholash va Yaratish yuqori tartibli tafakkur ko'nikmalari sanaladi.",
                    },
                    {
                        "text": "Formatif (shakllantiruvchi) baholashning asosiy maqsadi nima?",
                        "options": [
                            ("O'quv jarayonida o'quvchining o'zlashtirishidagi bo'shliqlarni aniqlab, tezkor qayta aloqa berish", True),
                            ("O'quv yili yakunida attestat bahosini chiqarish", False),
                            ("O'quvchilarni reyting bo'yicha saralab guruhdan chiqarish", False),
                            ("Faqat nazorat ishlarini tekshirish", False),
                        ],
                        "explanation": "Formatif baholash o'qitish jarayonini yaxshilash va o'quvchiga muntazam qayta aloqa (feedback) berish uchun xizmat qiladi.",
                    },
                    {
                        "text": "PISA xalqaro baholash dasturi necha yoshli o'quvchilarning funksional savodxonligini baholaydi?",
                        "options": [
                            ("15 yoshli o'quvchilarning", True),
                            ("7 yoshli boshlang'ich sinf o'quvchilarining", False),
                            ("22 yoshli oliy ta'lim bitiruvchilarining", False),
                            ("Faqat maktabgacha ta'lim tarbiyalanuvchilarining", False),
                        ],
                        "explanation": "PISA (Programme for International Student Assessment) 15 yoshli o'quvchilarning o'qish, matematika va tabiiy fanlar savodxonligini tekshiradi.",
                    },
                ],
            },
        ],
    },
    {
        "mock_code": "#MOCK-ATTEST-DIAG-02",
        "title": "Pedagoglar Attestatsiyasi 2026 — Diagnostika 2-variant (Metodika va Kasbiy standart)",
        "description": (
            "Pedagog kadrlar attestatsiyasiga tayyorgarlik uchun 2-diagnostik test. "
            "Kompetensiyaviy yondashuv, dars loyihalash va mutaxassislik fani savollari."
        ),
        "exam_type": "attestatsiya",
        "time_limit_minutes": 90,
        "sections": [
            {
                "code": "grammar",
                "name": "Mutaxassislik fani",
                "part_number": 1,
                "part_title": "1-qism: Adabiy nazariya va til me'yorlari",
                "questions": [
                    {
                        "text": "She'riy baytda bir-biriga zid ma'noli so'zlarni yonma-yon qo'llash san'ati nima deb ataladi?",
                        "options": [
                            ("Tazod (antiteza)", True),
                            ("Talmeh", False),
                            ("Tashbeh", False),
                            ("Tajnis", False),
                        ],
                        "explanation": "Zid tushunchalarni qarama-qarshi qo'yish badiiy san'ati mumtoz poetikada tazod deb yuritiladi.",
                    },
                    {
                        "text": "O'zbek tilida nechta kelishik shakli mavjud?",
                        "options": [
                            ("6 ta", True),
                            ("4 ta", False),
                            ("5 ta", False),
                            ("8 ta", False),
                        ],
                        "explanation": "O'zbek tilida bosh, qaratqich, tushum, jo'nalish, o'rin-payt va chiqish kelishiklari (jami 6 ta) mavjud.",
                    },
                    {
                        "text": "Yusuf Xos Hojibning «Qutadg'u bilig» asarida adolat ramzi sifatida qaysi obraz tasvirlangan?",
                        "options": [
                            ("Kuntug'di (Elig)", True),
                            ("Oyto'ldi", False),
                            ("O'gdulmish", False),
                            ("O'zg'urmish", False),
                        ],
                        "explanation": "Hukmdor Kuntug'di — adolat va qonun ustuvorligi timsolidir.",
                    },
                ],
            },
            {
                "code": "reading",
                "name": "Pedagogik mahorat va Kasbiy standart",
                "part_number": 2,
                "part_title": "2-qism: Inklyuziv ta'lim va o'quvchi psixologiyasi",
                "questions": [
                    {
                        "text": "Differensial (tabaqalashtirilgan) ta'lim yondashuvining mohiyati nimadan iborat?",
                        "options": [
                            ("O'quvchilarning individual qobiliyati, qiziqishi va o'zlashtirish sur'atiga mos topshiriqlar berish", True),
                            ("Barcha o'quvchilarga faqat eng qiyin olimpiada masalalarini berish", False),
                            ("Darsda faqat ma'ruza usulidan foydalanish", False),
                            ("Uyga vazifalarni butunlay bekor qilish", False),
                        ],
                        "explanation": "Differensial yondashuv har bir o'quvchining ehtiyoji va darajasiga mos ta'lim muhitini yaratadi.",
                    },
                    {
                        "text": "Lev Vigotskiy tomonidan fanga kiritilgan «Yaqin rivojlanish zonasi» (ZPD) tushunchasi nimani anglatadi?",
                        "options": [
                            ("O'quvchi mustaqil bajara oladigan ish bilan ustoz ko'magida bajara oladigan vazifa o'rtasidagi masofa", True),
                            ("Maktab binosi atrofidagi sport maydonchasi", False),
                            ("Faqat imtihon topshirish xonasi", False),
                            ("Yozgi ta'til davridagi dam olish rejasi", False),
                        ],
                        "explanation": "Vigotskiy nazariyasiga ko'ra, Yaqin rivojlanish zonasi o'quvchining kattalar yoki ustoz ko'magi (scaffolding) orqali egallashi mumkin bo'lgan salohiyatidir.",
                    },
                ],
            },
        ],
    },
]


ENGLISH_PRACTICE_TESTS = [
    {
        "mock_code": "#MOCK-ENG-CBT-01",
        "title": "IELTS & CEFR English Diagnostic — Listening & Reading Practice 1",
        "description": (
            "Interactive English CBT practice test covering Listening Part 1-3 "
            "and Reading Matching, Gap Fill, Multiple Choice & True/False/Not Given."
        ),
        "exam_type": "cefr_multilevel",
        "time_limit_minutes": 60,
    },
    {
        "mock_code": "#MOCK-IELTS-ACAD-01",
        "title": "IELTS Academic Full Diagnostic — Reading & Listening Simulator",
        "description": (
            "Official-format IELTS Academic diagnostic simulator with Band 1.0-9.0 "
            "conversion, gap completion, heading matching, and multiple-choice questions."
        ),
        "exam_type": "ielts_academic",
        "time_limit_minutes": 60,
    },
]


ESSAY_TOPICS_SEED = {
    "ielts_task1": {
        "rubric_type": "ielts_task1",
        "subject": "english",
        "word_limit_min": 150,
        "word_limit_max": 250,
        "time_limit_minutes": 20,
        "topics": [
            (
                "Global Renewable Energy Share (2010–2025)",
                "The bar chart compares the percentage of electricity generated from solar, wind, and hydro sources across four countries between 2010 and 2025. Summarise the main features and make comparisons where relevant.",
            ),
            (
                "Urban Transport Modes in Three European Cities",
                "The table below gives information about the proportion of commuters using public transit, bicycles, and private cars in Amsterdam, Berlin, and Madrid in 2024. Summarise the information by selecting and reporting the main features.",
            ),
            (
                "Household Internet Access and Broadband Speed Trends",
                "The line graph illustrates household broadband penetration rates and average download speeds in urban and rural areas from 2015 to 2025. Summarise the key trends and make comparisons where relevant.",
            ),
            (
                "Plastic Recycling Process Diagram",
                "The diagram illustrates how post-consumer plastic bottles are collected, sorted, processed into pellets, and manufactured into new textile products. Summarise the stages shown in the process.",
            ),
            (
                "University Library Floor Plan Redevelopment",
                "The two maps below show the layout of a central university library in 2005 and how it looks today after digital transformation. Summarise the main changes and compare the facilities.",
            ),
            (
                "Age Distribution of Online Learners Worldwide",
                "The pie charts compare the age breakdown of students enrolled in professional online certification courses in 2018 and 2026. Summarise the main features and make comparisons where relevant.",
            ),
        ],
    },
    "ielts_task2": {
        "rubric_type": "ielts_task2",
        "subject": "english",
        "word_limit_min": 250,
        "word_limit_max": 400,
        "time_limit_minutes": 40,
        "topics": [
            (
                "Artificial Intelligence in Higher Education",
                "Some people believe that artificial intelligence tutors will eventually replace human university lecturers, while others argue that personal mentorship remains irreplaceable. Discuss both views and give your own opinion.",
            ),
            (
                "Remote Work and Urban Development",
                "In many countries, an increasing number of professionals work from home rather than commuting to city offices. Do the advantages of this trend for individuals and society outweigh the disadvantages?",
            ),
            (
                "Government Investment in Public Transport vs New Roads",
                "Some governments spend large sums of money expanding motorways, whereas others argue that funding high-speed rail and metro systems is a better solution to traffic congestion. To what extent do you agree or disagree?",
            ),
            (
                "Youth Financial Literacy in School Curricula",
                "Many young adults leave school without practical knowledge of managing personal finances, taxes, and savings. Why is this the case, and what measures can schools and parents take to address this issue?",
            ),
            (
                "Preserving Endangered Languages in a Globalised World",
                "Several languages die out every year as global communication relies on a few dominant languages. Some people think this makes life easier, while others view it as a cultural loss. Discuss both views and give your opinion.",
            ),
            (
                "Environmental Responsibility: Corporations vs Individuals",
                "Some people argue that environmental protection can only be achieved through strict government regulations on large corporations, while others believe individual lifestyle changes are equally important. Discuss both views and give your opinion.",
            ),
        ],
    },
    "ona_tili": {
        "rubric_type": "bmb_12",
        "subject": "uzbek",
        "word_limit_min": 200,
        "word_limit_max": 400,
        "time_limit_minutes": 60,
        "topics": [
            (
                "Sun'iy intellekt va inson tafakkuri: hamkorlikmi yoki raqobat?",
                "Ba'zilar sun'iy intellekt texnologiyalari yoshlarning mustaqil fikrlash qobiliyatini susaytiradi deb hisoblasa, boshqalar uni ilm-fan va ta'lim sifatini yangi bosqichga olib chiquvchi kuch deb biladi. Har ikki qarashni tahlil qilib, shaxsiy pozitsiyangizni asoslang.",
            ),
            (
                "Mutolaa madaniyati: bosma kitob afzalmi yoki elektron manbalar?",
                "Zamonaviy axborot asrida bir guruh insonlar an'anaviy bosma kitoblarni mutolaa qilish chuqur bilim beradi desa, boshqalar audiokitob va elektron darsliklarning tezkorligini ustun qo'yadi. Mavzu yuzasidan dalillarga tayangan holda esse yozing.",
            ),
            (
                "Ekologik madaniyat va suv resurslarini tejash mas'uliyati",
                "Mintaqamizda suv tanqisligi va ekologik muammolarning oldini olishda davlat dasturlari muhimroqmi yoki har bir fuqaroning kundalik ekologik mas'uliyati? Fikringizni hayotiy misollar bilan asoslang.",
            ),
            (
                "Kasb tanlashda qiziqish ustuvormi yoki jamiyat ehtiyoji?",
                "Yoshlar kelajak kasbini tanlashda o'z qiziqish va qobiliyatiga tayanishi kerakmi yoki mehnat bozoridagi yuqori daromadli yo'nalishlarni tanlashi ma'qulmi? Qarashlarni qiyoslab, xulosangizni bayon eting.",
            ),
            (
                "Ijtimoiy tarmoqlarning yoshlar nutqi va imlo savodxonligiga ta'siri",
                "Ijtimoiy tarmoqlardagi qisqartma so'zlar va erkin yozishmalar adabiy til me'yorlariga putur yetkazmoqdami yoki muloqot tezkorligini oshirmoqdami? Muammoni atroflicha tahlil qiling.",
            ),
            (
                "Milliy qadriyatlar va globallashuv jarayoni uyg'unligi",
                "Globallashuv davrida zamonaviy xorijiy tajribalarni o'zlashtirish bilan birga milliy o'zlik va urf-odatlarni asrab qolishning eng samarali yo'llari nimalardan iborat? Dalillar asosida esse yozing.",
            ),
        ],
    },
    "adabiyot": {
        "rubric_type": "bmb_12",
        "subject": "uzbek",
        "word_limit_min": 200,
        "word_limit_max": 400,
        "time_limit_minutes": 60,
        "topics": [
            (
                "Alisher Navoiy ijodida komil inson va ma'rifat talqini",
                "Hazrat Alisher Navoiyning «Xamsa» dostonlari va lirikasida ilgari surilgan komil inson, saxovat hamda ilm-ma'rifat g'oyalari bugungi yosh avlod tarbiyasida qanday ahamiyat kasb etadi?",
            ),
            (
                "Abdulla Qodiriyning «O'tkan kunlar» romanida oila va sadoqat masalasi",
                "«O'tkan kunlar» romanidagi Otabek, Kumush va Zaynab obrazlari misolida ota-ona orzusi hamda shaxsiy baxt o'rtasidagi murakkab ziddiyatlarni badiiy tahlil qiling.",
            ),
            (
                "Cho'lponning «Kecha va kunduz» asarida ma'rifatsizlik fojiasi",
                "Romanda Zebi va Razzoq so'fi taqdiri orqali jaholat hamda huquqsizlikning inson hayotiga ko'rsatgan salbiy ta'siri qanday badiiy mahorat bilan ochib berilgan?",
            ),
            (
                "Oybekning «Navoiy» romanida ilm-fan va davlat boshqaruvi",
                "Asarda mutafakkir shoir va davlat arbobi Alisher Navoiyning yurt obodligi hamda adolat o'rnatish yo'lidagi kurashi qanday tasvirlangan? Badiiy dalillar keltiring.",
            ),
            (
                "Said Ahmadning «Ufq» trilogiyasida inson matonati va mehr-oqibat",
                "Ikkinchi jahon urushi va undan keyingi mashaqqatli yillarda o'zbek oilasining sabr-bardoshi, ota va farzand munosabatlari asarda qanday ifodalangan?",
            ),
            (
                "O'tkir Hoshimovning «Dunyoning ishlari» qissasida Ona siymosi",
                "Adibning «Dunyoning ishlari» asaridagi hikoyalar misolida o'zbek onasining fidoyiligi, bag'rikengligi va farzand oldidagi burch tuyg'usini tahlil eting.",
            ),
        ],
    },
    "multilevel": {
        "rubric_type": "ielts_task2",
        "subject": "english",
        "word_limit_min": 180,
        "word_limit_max": 320,
        "time_limit_minutes": 40,
        "topics": [
            (
                "CEFR Multi-level Writing: Online Courses vs Classroom Learning",
                "More and more students are choosing online platforms to prepare for national and international exams instead of attending traditional classes. Write an essay discussing the pros and cons of online education and state your preference.",
            ),
            (
                "CEFR Multi-level Writing: Community Sports Facilities",
                "Your local council has received funding to build either a new public sports complex or a modern digital library. Write a formal argument essay explaining which project would benefit young people more.",
            ),
            (
                "CEFR Multi-level Writing: Gap Year Before University",
                "Some high school graduates prefer to work or travel for a year before starting university studies. Discuss the potential benefits and drawbacks of taking a gap year.",
            ),
            (
                "CEFR Multi-level Writing: Cashless Society",
                "Digital payments and mobile banking have almost replaced cash in daily transactions. Is moving towards a completely cashless society a positive or negative development?",
            ),
            (
                "CEFR Multi-level Writing:Extracurricular Activities for Teenagers",
                "Should secondary schools make volunteering and community service a compulsory part of the curriculum? Give reasons for your answer and include relevant examples.",
            ),
            (
                "CEFR Multi-level Writing: Sustainable Tourism",
                "International tourism brings economic growth to historic cities, but it can also damage local traditions and the environment. How can governments balance economic benefits with cultural preservation?",
            ),
        ],
    },
}


SPEAKING_TOPICS_SEED = {
    "part1": [
        (
            "Hometown & Neighbourhood",
            "Tell me about the town or city where you live. What do you like most about your neighbourhood, and how has it changed in recent years?",
            [],
            30,
        ),
        (
            "Work, Studies & Future Ambitions",
            "Are you currently working or studying? Why did you choose your main subject or profession, and how do you plan to use it in the future?",
            [],
            30,
        ),
        (
            "Daily Routine & Time Management",
            "What is your favourite part of the day for studying or working? How do you organize your daily schedule when you have important deadlines?",
            [],
            30,
        ),
        (
            "Reading Habits & Digital Media",
            "Do you prefer reading printed books or digital articles on your phone? What kind of topics do you enjoy reading about in your free time?",
            [],
            30,
        ),
        (
            "Technology & Mobile Applications",
            "Which mobile app do you use most frequently for learning or productivity? Could you imagine spending a whole week without your smartphone?",
            [],
            30,
        ),
        (
            "Health, Fitness & Outdoor Activities",
            "What do you usually do to stay healthy and active? Do people in your country prefer indoor gyms or outdoor parks for exercise?",
            [],
            30,
        ),
    ],
    "part2": [
        (
            "A Book or Article That Changed Your Perspective",
            "Describe a book or an article you read that had a strong positive influence on your thinking.",
            [
                "What the book or article was about",
                "When and why you decided to read it",
                "What key lesson or idea you learned from it",
                "And explain how it changed your perspective or daily habits",
            ],
            120,
        ),
        (
            "An Inspiring Teacher or Mentor",
            "Describe a teacher or mentor who helped you achieve an important academic or personal goal.",
            [
                "Who this person is and how you met them",
                "What subject or skill they taught you",
                "How they supported or motivated you during difficult moments",
                "And explain why you remember this person with gratitude",
            ],
            120,
        ),
        (
            "A Challenging Goal You Successfully Achieved",
            "Describe a difficult goal that you set for yourself and worked hard to accomplish.",
            [
                "What the goal was and when you set it",
                "What steps you took to prepare and stay disciplined",
                "What obstacles you faced along the way",
                "And explain how you felt when you finally succeeded",
            ],
            120,
        ),
        (
            "A Memorable Journey or Place You Visited",
            "Describe a historic city or scenic place you visited that left a lasting impression on you.",
            [
                "Where the place is located and when you went there",
                "Who accompanied you on the trip",
                "What sights, architecture, or cultural traditions you experienced",
                "And explain why you would recommend this place to others",
            ],
            120,
        ),
        (
            "A Useful Piece of Technology You Rely On",
            "Describe a piece of modern technology (other than a phone) that makes your study or work much easier.",
            [
                "What the device or software is",
                "How long you have been using it",
                "How frequently you use it in your daily routine",
                "And explain how it has improved your productivity",
            ],
            120,
        ),
        (
            "A Traditional Celebration in Your Country",
            "Describe an important national holiday or cultural festival celebrated in Uzbekistan.",
            [
                "What the celebration is called and when it takes place",
                "How families and communities prepare for it",
                "What special foods or customs are associated with it",
                "And explain why preserving this tradition is meaningful",
            ],
            120,
        ),
    ],
    "part3": [
        (
            "The Future of Education & Lifelong Learning",
            "Why has lifelong learning become essential in the modern job market? How should universities adapt their curricula to prepare graduates for rapidly changing careers?",
            [],
            60,
        ),
        (
            "Leadership Qualities & Teamwork in Society",
            "Do you think effective leaders are born with natural talent, or can leadership skills be trained? How can schools encourage collaborative problem-solving among students?",
            [],
            60,
        ),
        (
            "Environmental Policy & Sustainable Cities",
            "What are the most effective ways for growing cities to reduce air pollution and traffic congestion? Should governments penalize polluters or reward green innovation?",
            [],
            60,
        ),
        (
            "Artificial Intelligence & Human Creativity",
            "Can artificial intelligence ever produce genuine art and literature, or is creativity uniquely human? What ethical rules should govern AI tools in journalism and education?",
            [],
            60,
        ),
        (
            "Cultural Identity in a Globalised Era",
            "How does global media influence the lifestyle and values of young people? What role do museums, literature, and national languages play in keeping cultural heritage alive?",
            [],
            60,
        ),
        (
            "Work-Life Balance & Modern Productivity",
            "Why do many professionals feel busier today despite having time-saving technology? What policies can companies introduce to prevent burnout and support mental well-being?",
            [],
            60,
        ),
    ],
    "multilevel": [
        (
            "CEFR Multi-level Speaking: Digital Learning Platforms (B2–C1)",
            "Compare learning a foreign language through mobile apps with studying in a classroom with a teacher. Which approach leads to faster fluency, and why?",
            [
                "Flexibility and self-paced practice",
                "Live interaction and immediate error correction",
                "How to combine both methods effectively",
                "Your personal language learning experience",
            ],
            90,
        ),
        (
            "CEFR Multi-level Speaking: Career Choices for Young Graduates (B2–C1)",
            "Discuss the factors young people in Uzbekistan consider when choosing between working for a large organization and starting their own business.",
            [
                "Job security vs entrepreneurial freedom",
                "Skills required to launch a startup",
                "The role of government youth support programs",
                "Which career path appeals to you most",
            ],
            90,
        ),
        (
            "CEFR Multi-level Speaking: Healthy Lifestyle & Public Sports (B1–C1)",
            "Many people struggle to maintain healthy eating and exercise habits in busy cities. What practical steps can individuals and local communities take to promote active living?",
            [
                "Daily nutrition and sleep habits",
                "Accessible public parks and bicycle lanes",
                "Reducing screen time among teenagers",
                "Long-term benefits for society",
            ],
            90,
        ),
        (
            "CEFR Multi-level Speaking: Public Transport & Eco-friendly Travel (B2–C1)",
            "Evaluate how improving public transport networks can transform urban life and protect the environment in major cities.",
            [
                "Metro and electric bus expansion",
                "Reducing traffic congestion and emissions",
                "Making public transit affordable for students",
                "Future trends in urban mobility",
            ],
            90,
        ),
        (
            "CEFR Multi-level Speaking: Reading Literature vs Watching Films (B1–C1)",
            "When a famous novel is adapted into a movie, is it better to read the original book first or watch the film adaptation? Support your opinion with examples.",
            [
                "Imagination and depth of character development",
                "Visual storytelling and cinematic effects",
                "Time commitment in modern life",
                "An example of a book or film you enjoyed",
            ],
            90,
        ),
        (
            "CEFR Multi-level Speaking: Volunteering & Youth Community Service (B2–C1)",
            "Discuss how participating in charity projects and environmental volunteering helps young people develop responsibility and social skills.",
            [
                "Types of community projects available to youth",
                "Building empathy, teamwork, and leadership",
                "Impact on local neighbourhoods",
                "How schools can recognise student volunteers",
            ],
            90,
        ),
    ],
}


class Command(BaseCommand):
    help = "Idempotently seed rich courses, diagnostic tests, essay topics, and speaking topics."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Starting GRAND EDUCATION rich content seeder..."))

        teacher = self._ensure_author()
        uzbek_course, english_course = self._seed_subjects_and_courses(teacher)

        bmb_count = self._seed_structured_uzbek_tests(uzbek_course, BMB_DIAGNOSTIC_TESTS)
        attest_count = self._seed_structured_uzbek_tests(uzbek_course, ATTESTATSIYA_DIAGNOSTIC_TESTS)
        eng_count = self._seed_english_practice_tests(english_course)

        # Also invoke existing specialized mock seeders idempotently
        for cmd in (
            "seed_bmb_mock_day4",
            "seed_rash_mock_shukurov",
            "seed_attestatsiya_test_2026",
            "seed_cefr_mock_1",
        ):
            try:
                call_command(cmd, verbosity=0)
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"Note: optional seeder {cmd} skipped ({exc})"))

        essay_count = self._seed_essay_topics(teacher)
        speaking_count = self._seed_speaking_topics()

        self.stdout.write(
            self.style.SUCCESS(
                f"Done! Seeded {bmb_count} BMB tests, {attest_count} Attestatsiya tests, "
                f"{eng_count} English CBT tests, {essay_count} EssayTopics, and {speaking_count} SpeakingTopics."
            )
        )

    def _ensure_author(self):
        teacher = (
            User.objects.filter(role__in=["admin", "teacher"], is_active=True)
            .order_by("-is_superuser", "id")
            .first()
        )
        if not teacher:
            teacher, _ = User.objects.get_or_create(
                email="ustoz@grandec.uz",
                defaults={
                    "first_name": "Grand",
                    "last_name": "Education",
                    "role": "teacher",
                    "is_staff": True,
                    "is_active": True,
                },
            )
        return teacher

    @transaction.atomic
    def _seed_subjects_and_courses(self, teacher):
        Subject.objects.update_or_create(
            slug="uzbek",
            defaults={
                "name": "Ona tili va adabiyot",
                "description": "Milliy sertifikat (BMB), Attestatsiya va 12 mezonli esse tayyorgarligi",
                "icon": "🇺🇿",
                "is_active": True,
                "position": 1,
            },
        )
        Subject.objects.update_or_create(
            slug="english",
            defaults={
                "name": "English (IELTS & Multi-level)",
                "description": "IELTS Academic/General Writing, Speaking, Listening & Reading CBT Simulator",
                "icon": "🇬🇧",
                "is_active": True,
                "position": 2,
            },
        )

        uz_cat, _ = Category.objects.get_or_create(
            slug="ona-tili-va-adabiyot",
            defaults={
                "name": "Ona tili va Adabiyot",
                "description": "BMB Milliy Sertifikat va Pedagoglar Attestatsiyasi",
            },
        )
        en_cat, _ = Category.objects.get_or_create(
            slug="english-ielts-cefr",
            defaults={
                "name": "Ingliz tili (IELTS & CEFR)",
                "description": "IELTS Academic va Multi-level CEFR imtihonlariga tayyorgarlik",
            },
        )

        uzbek_course, _ = Course.objects.update_or_create(
            slug="ona-tili-milliy-sertifikat-va-attestatsiya",
            defaults={
                "title": "Ona tili va Adabiyot — Milliy Sertifikat & Attestatsiya",
                "description": "Ona tili va adabiyot fanidan BMB Milliy Sertifikat hamda Pedagoglar Attestatsiyasi kurslari.",
                "category": uz_cat,
                "subject": "uzbek",
                "teacher": teacher,
                "status": Course.Status.PUBLISHED,
            },
        )
        english_course, _ = Course.objects.update_or_create(
            slug="english-ielts-and-cefr-multilevel",
            defaults={
                "title": "Ingliz tili — IELTS Academic & CEFR Multi-level",
                "description": "IELTS Academic va CEFR Multi-level (B1-C1) Listening, Reading, Writing va Speaking kursi.",
                "category": en_cat,
                "subject": "english",
                "teacher": teacher,
                "status": Course.Status.PUBLISHED,
            },
        )
        return uzbek_course, english_course

    @transaction.atomic
    def _seed_structured_uzbek_tests(self, course: Course, test_defs: list[dict]) -> int:
        seeded = 0
        for tdef in test_defs:
            test, _ = Test.objects.update_or_create(
                mock_code=tdef["mock_code"],
                defaults={
                    "course": course,
                    "created_by": course.teacher,
                    "subject": "uzbek",
                    "exam_type": tdef["exam_type"],
                    "title": tdef["title"],
                    "description": tdef["description"],
                    "time_limit_minutes": tdef["time_limit_minutes"],
                    "pass_percentage": Decimal("60.00"),
                    "difficulty": Test.Difficulty.MEDIUM,
                    "status": Test.Status.PUBLISHED,
                    "is_active": True,
                    "access_type": Test.AccessType.PUBLIC,
                    "shuffle_questions": False,
                    "shuffle_choices": False,
                    "show_results_immediately": True,
                },
            )
            test.questions.all().delete()
            test.sections.all().delete()
            test.passages.all().delete()

            q_order = 1
            for s_idx, sec_def in enumerate(tdef["sections"], start=1):
                section = ExamSection.objects.create(
                    test=test,
                    code=sec_def["code"],
                    name=sec_def["name"],
                    duration_minutes=30,
                    order=s_idx,
                )
                part = ExamPart.objects.create(
                    section=section,
                    number=str(sec_def["part_number"]),
                    title=sec_def["part_title"],
                    instructions="To'g'ri javob variantini belgilang.",
                    order=sec_def["part_number"],
                )
                passage_obj = None
                if sec_def.get("passage"):
                    passage_obj = ReadingPassage.objects.create(
                        test=test,
                        section=section,
                        title=sec_def["part_title"],
                        content=sec_def["passage"],
                        order=s_idx,
                    )
                group = QuestionGroup.objects.create(
                    part=part,
                    title=sec_def["part_title"],
                    instructions="To'g'ri javob variantini belgilang.",
                    passage=passage_obj,
                    order=1,
                )
                for q_def in sec_def["questions"]:
                    q = Question.objects.create(
                        test=test,
                        section=section,
                        reading_passage=passage_obj,
                        passage=sec_def.get("passage", ""),
                        group=group,
                        question_type=Question.QuestionType.SINGLE_CHOICE,
                        text=q_def["text"],
                        explanation=q_def["explanation"],
                        points=2,
                        position=q_order,
                    )
                    for c_idx, (opt_text, is_corr) in enumerate(q_def["options"], start=1):
                        Choice.objects.create(
                            question=q,
                            text=opt_text,
                            is_correct=is_corr,
                            position=c_idx,
                        )
                    q_order += 1
            seeded += 1
        return seeded

    @transaction.atomic
    def _seed_english_practice_tests(self, course: Course) -> int:
        seeded = 0
        for tdef in ENGLISH_PRACTICE_TESTS:
            test, _ = Test.objects.update_or_create(
                mock_code=tdef["mock_code"],
                defaults={
                    "course": course,
                    "created_by": course.teacher,
                    "subject": "english",
                    "exam_type": tdef["exam_type"],
                    "title": tdef["title"],
                    "description": tdef["description"],
                    "time_limit_minutes": tdef["time_limit_minutes"],
                    "pass_percentage": Decimal("60.00"),
                    "difficulty": Test.Difficulty.MEDIUM,
                    "status": Test.Status.PUBLISHED,
                    "is_active": True,
                    "access_type": Test.AccessType.PUBLIC,
                    "shuffle_questions": False,
                    "shuffle_choices": False,
                    "show_results_immediately": True,
                },
            )
            test.questions.all().delete()
            test.sections.all().delete()
            test.passages.all().delete()

            # Section 1: Listening (Part 1 gap_fill, Part 3 single choice)
            listening_sec = ExamSection.objects.create(
                test=test,
                code="listening",
                name="Listening",
                duration_minutes=30,
                order=1,
            )
            l_passage1 = ReadingPassage.objects.create(
                test=test,
                section=listening_sec,
                title="Listening, Part 1 — Note Completion",
                content=(
                    "Receptionist: Welcome to the Cambridge Language Centre. "
                    "Our intensive evening course starts on 15th October and classes are held in Room 204. "
                    "The registration fee includes all digital textbooks and practice tests."
                ),
                order=1,
            )
            l_part1 = ExamPart.objects.create(
                section=listening_sec,
                number="1",
                title="Listening, Part 1 — Note Completion",
                instructions="Write ONE WORD AND/OR A NUMBER for each answer.",
                order=1,
            )
            l_group1 = QuestionGroup.objects.create(
                part=l_part1,
                title="Questions 1–3",
                instructions="Write ONE WORD AND/OR A NUMBER for each answer.",
                answer_rule="ONE WORD AND/OR A NUMBER",
                passage=l_passage1,
                order=1,
            )
            for idx, (q_text, ans, expl) in enumerate(
                [
                    (
                        "The intensive language course takes place in the ___ session.",
                        "evening",
                        "The receptionist states that the intensive evening course starts on 15th October.",
                    ),
                    (
                        "All lectures and workshops are held in Room ___.",
                        "204",
                        "Classes are held in Room 204.",
                    ),
                    (
                        "The course fee covers access to digital ___ and mock exams.",
                        "textbooks",
                        "The registration fee includes all digital textbooks and practice tests.",
                    ),
                ],
                start=1,
            ):
                q = Question.objects.create(
                    test=test,
                    section=listening_sec,
                    reading_passage=l_passage1,
                    group=l_group1,
                    question_type=Question.QuestionType.GAP_FILL,
                    text=q_text,
                    correct_text=ans,
                    explanation=expl,
                    points=1,
                    position=idx,
                )
                GapBlank.objects.create(
                    question=q,
                    position=0,
                    answer_text=ans,
                )

            l_passage3 = ReadingPassage.objects.create(
                test=test,
                section=listening_sec,
                title="Listening, Part 3 — Academic Discussion",
                content=(
                    "Tutor: So, Maya and Liam, how is your research project on urban vertical farming progressing?\n"
                    "Maya: We found that LED lighting efficiency has improved by 40%, reducing operating costs.\n"
                    "Liam: However, initial setup expenses remain the biggest barrier for small businesses."
                ),
                order=2,
            )
            l_part3 = ExamPart.objects.create(
                section=listening_sec,
                number="3",
                title="Listening, Part 3 — Academic Discussion",
                instructions="Choose the correct letter, A, B, C or D.",
                order=2,
            )
            l_group3 = QuestionGroup.objects.create(
                part=l_part3,
                title="Questions 4–6",
                instructions="Choose the correct letter, A, B, C or D.",
                passage=l_passage3,
                order=1,
            )
            for idx, (q_text, opts, expl) in enumerate(
                [
                    (
                        "What is the main topic of Maya and Liam's research project?",
                        [
                            ("Urban vertical farming", True),
                            ("Traditional rural agriculture", False),
                            ("Solar panel manufacturing", False),
                            ("Marine biology conservation", False),
                        ],
                        "The tutor asks about their research project on urban vertical farming.",
                    ),
                    (
                        "According to Maya, what has improved by 40%?",
                        [
                            ("LED lighting efficiency", True),
                            ("Water consumption rates", False),
                            ("Transport speed", False),
                            ("Seed germination time", False),
                        ],
                        "Maya explicitly notes that LED lighting efficiency has improved by 40%.",
                    ),
                    (
                        "What does Liam identify as the main challenge for small businesses?",
                        [
                            ("High initial setup costs", True),
                            ("Lack of qualified engineers", False),
                            ("Government export taxes", False),
                            ("Shortage of warehouse space", False),
                        ],
                        "Liam states that initial setup expenses remain the biggest barrier.",
                    ),
                ],
                start=4,
            ):
                q = Question.objects.create(
                    test=test,
                    section=listening_sec,
                    reading_passage=l_passage3,
                    group=l_group3,
                    question_type=Question.QuestionType.SINGLE_CHOICE,
                    text=q_text,
                    explanation=expl,
                    points=1,
                    position=idx,
                )
                for c_idx, (opt_text, is_corr) in enumerate(opts, start=1):
                    Choice.objects.create(question=q, text=opt_text, is_correct=is_corr, position=c_idx)

            # Section 2: Reading (Part 2 matching, Part 3 True/False/Not Given)
            reading_sec = ExamSection.objects.create(
                test=test,
                code="reading",
                name="Reading",
                duration_minutes=30,
                order=2,
            )
            passage_text = (
                "Paragraph A: The Rise of Autonomous Maritime Vessels\n"
                "Modern shipping companies are increasingly testing autonomous cargo ships equipped with radar, "
                "satellite navigation, and AI collision-avoidance systems to improve safety at sea.\n\n"
                "Paragraph B: Environmental Impact of Green Hydrogen Fuel\n"
                "By replacing heavy fuel oil with green hydrogen, maritime engineers aim to cut carbon emissions "
                "from international shipping by over 80 percent before 2040.\n\n"
                "Paragraph C: Training the Next Generation of Port Operators\n"
                "As ports become automated, maritime academies are redesigning their courses to focus on "
                "cybersecurity, remote vessel monitoring, and data analytics."
            )
            passage_obj = ReadingPassage.objects.create(
                test=test,
                section=reading_sec,
                title="Innovation in Global Maritime Transport",
                content=passage_text,
                order=3,
            )
            r_part2 = ExamPart.objects.create(
                section=reading_sec,
                number="2",
                title="Reading, Part 2 — Heading & Information Matching",
                instructions="Match each statement with the correct paragraph, A, B or C.",
                order=1,
            )
            r_group2 = QuestionGroup.objects.create(
                part=r_part2,
                title="Questions 7–9",
                instructions="Match each statement with the correct paragraph, A, B or C.",
                passage=passage_obj,
                order=1,
            )
            for idx, (q_text, corr_key, expl) in enumerate(
                [
                    (
                        "Which paragraph mentions using artificial intelligence to prevent accidents at sea?",
                        "A",
                        "Paragraph A describes AI collision-avoidance systems to improve safety at sea.",
                    ),
                    (
                        "Which paragraph discusses a clean fuel that could drastically reduce carbon emissions?",
                        "B",
                        "Paragraph B focuses on replacing heavy fuel oil with green hydrogen.",
                    ),
                    (
                        "Which paragraph explains how maritime education is adapting to automation?",
                        "C",
                        "Paragraph C explains that maritime academies are redesigning courses for remote monitoring.",
                    ),
                ],
                start=7,
            ):
                q = Question.objects.create(
                    test=test,
                    section=reading_sec,
                    reading_passage=passage_obj,
                    passage=passage_text,
                    group=r_group2,
                    question_type=Question.QuestionType.LEGACY_MATCHING,
                    text=q_text,
                    correct_text=corr_key,
                    explanation=expl,
                    points=1,
                    position=idx,
                )
                for c_idx, key in enumerate(["A", "B", "C"], start=1):
                    Choice.objects.create(
                        question=q,
                        text=key,
                        is_correct=(key == corr_key),
                        position=c_idx,
                    )

            r_group3 = QuestionGroup.objects.create(
                part=r_part2,
                title="Questions 10–12",
                instructions="Do the following statements agree with the information given in the Reading Passage?",
                passage=passage_obj,
                order=2,
            )
            for idx, (q_text, corr_val, expl) in enumerate(
                [
                    (
                        "Autonomous cargo ships use satellite navigation and radar to enhance maritime safety.",
                        "TRUE",
                        "Paragraph A explicitly states they are equipped with radar and satellite navigation.",
                    ),
                    (
                        "Green hydrogen has already completely replaced heavy fuel oil in all cargo ships.",
                        "FALSE",
                        "Paragraph B says engineers aim to cut emissions before 2040, not that it has already replaced all fuel.",
                    ),
                    (
                        "Maritime academies charge higher tuition fees for cybersecurity courses.",
                        "NOT GIVEN",
                        "Tuition fees are not mentioned anywhere in the passage.",
                    ),
                ],
                start=10,
            ):
                q = Question.objects.create(
                    test=test,
                    section=reading_sec,
                    reading_passage=passage_obj,
                    passage=passage_text,
                    group=r_group3,
                    question_type=Question.QuestionType.TRUE_FALSE_NOT_GIVEN,
                    text=q_text,
                    correct_text=corr_val,
                    explanation=expl,
                    points=1,
                    position=idx,
                )
                for c_idx, opt in enumerate(["TRUE", "FALSE", "NOT GIVEN"], start=1):
                    Choice.objects.create(
                        question=q,
                        text=opt,
                        is_correct=(opt == corr_val),
                        position=c_idx,
                    )

            seeded += 1
        return seeded

    @transaction.atomic
    def _seed_essay_topics(self, teacher) -> int:
        count = 0
        for category_code, cfg in ESSAY_TOPICS_SEED.items():
            for title, description in cfg["topics"]:
                EssayTopic.objects.update_or_create(
                    title=title,
                    category=category_code,
                    defaults={
                        "description": description,
                        "subject": cfg["subject"],
                        "rubric_type": cfg["rubric_type"],
                        "word_limit_min": cfg["word_limit_min"],
                        "word_limit_max": cfg["word_limit_max"],
                        "time_limit_minutes": cfg["time_limit_minutes"],
                        "is_active": True,
                        "created_by": teacher,
                    },
                )
                count += 1
        return count

    @transaction.atomic
    def _seed_speaking_topics(self) -> int:
        count = 0
        for part_code, items in SPEAKING_TOPICS_SEED.items():
            for title, prompt_text, bullets, duration in items:
                SpeakingTopic.objects.update_or_create(
                    part=part_code,
                    title=title,
                    defaults={
                        "subject": "english",
                        "prompt": prompt_text,
                        "bullet_points": bullets,
                        "prep_time_seconds": 60 if part_code in ("part2", "multilevel") else 15,
                        "speak_time_seconds": duration,
                        "is_active": True,
                    },
                )
                count += 1
        return count
