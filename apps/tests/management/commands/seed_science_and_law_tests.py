"""
Django Management Command: seed_science_and_law_tests

Seeds full authentic BMB/DTM-standard Mock tests for:
1. Biologiya (Milliy sertifikat & DTM) - #MOCK-BIO-01
   - Single Choice, Matching Matrix (1, 2, 3 -> A-F), and Dual Open Calculation (a & b)
2. Kimyo (Milliy sertifikat & DTM) - #MOCK-CHEM-01
   - Single Choice, Matching Matrix, and Dual Open Calculation
3. Huquqshunoslik (Yurisprudensiya & Konstitutsiya) - #MOCK-LAW-01
   - Single Choice, Legal Case Studies, and Legal Matching
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.courses.models import Category, Course, Subject
from apps.tests.models import Choice, ExamSection, Question, Test
from apps.tests.views_placement import ensure_multi_subject_seed_data

User = get_user_model()


class Command(BaseCommand):
    help = "Seeds authentic BMB/DTM Mock tests for Biology, Chemistry, and Law."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing science and law mock tests before recreating.",
        )

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        reset: bool = options.get("reset", False)
        self.stdout.write(self.style.NOTICE("Initializing Multi-Subject seed data..."))
        ensure_multi_subject_seed_data()

        # 1. Instructor
        instructor = (
            User.objects.filter(role="teacher").first()
            or User.objects.filter(is_superuser=True).first()
            or User.objects.filter(is_staff=True).first()
        )
        if not instructor:
            instructor = User.objects.create(
                email="teacher@grandec.uz",
                first_name="Grand",
                last_name="Education",
                role="teacher",
                is_active=True,
                is_staff=True,
            )
            instructor.set_password("GrandEducation2026!")
            instructor.save()

        # 2. Categories
        cat_bio, _ = Category.objects.get_or_create(
            slug="biologiya-milliy",
            defaults={
                "name": "Biologiya (Milliy sertifikat)",
                "description": "Biologiya fani bo'yicha BMB va DTM diagnostika testlari.",
            },
        )
        cat_chem, _ = Category.objects.get_or_create(
            slug="kimyo-milliy",
            defaults={
                "name": "Kimyo (Milliy sertifikat)",
                "description": "Kimyo fani bo'yicha BMB va DTM diagnostika testlari.",
            },
        )
        cat_law, _ = Category.objects.get_or_create(
            slug="huquq-yurisprudensiya",
            defaults={
                "name": "Huquqshunoslik (Yurisprudensiya)",
                "description": "Konstitutsiya va huquqshunoslik fanlari bo'yicha imtihonlar.",
            },
        )

        # 3. Courses
        course_bio, _ = Course.objects.get_or_create(
            slug="biologiya-milliy-sertifikat",
            defaults={
                "title": "Biologiya — Milliy Sertifikat va DTM Kursi",
                "description": "Sitologiya, genetika, odam anatomiyasi va ekologiya bo'yicha to'liq tayyorgarlik.",
                "teacher": instructor,
                "category": cat_bio,
                "subject": "biology",
                "status": Course.Status.PUBLISHED,
                "price": Decimal("0.00"),
            },
        )
        course_bio.subject = "biology"
        course_bio.save(update_fields=["subject"])

        course_chem, _ = Course.objects.get_or_create(
            slug="kimyo-milliy-sertifikat",
            defaults={
                "title": "Kimyo — Milliy Sertifikat va DTM Kursi",
                "description": "Mendeleyev davriy jadvali, stexiometriya, eritmalar va organik kimyo bo'yicha to'liq tayyorgarlik.",
                "teacher": instructor,
                "category": cat_chem,
                "subject": "chemistry",
                "status": Course.Status.PUBLISHED,
                "price": Decimal("0.00"),
            },
        )
        course_chem.subject = "chemistry"
        course_chem.save(update_fields=["subject"])

        course_law, _ = Course.objects.get_or_create(
            slug="huquqshunoslik-yurisprudensiya",
            defaults={
                "title": "Huquqshunoslik — Yurisprudensiya va Konstitutsiya",
                "description": "O'zbekiston Konstitutsiyasi, fuqarolik, mehnat va jinoyat huquqi kazuslari tahlili.",
                "teacher": instructor,
                "category": cat_law,
                "subject": "law",
                "status": Course.Status.PUBLISHED,
                "price": Decimal("0.00"),
            },
        )
        course_law.subject = "law"
        course_law.save(update_fields=["subject"])

        # =========================================================================
        # TEST 1: BIOLOGY (#MOCK-BIO-01)
        # =========================================================================
        self.stdout.write("Seeding Biology Mock Test (#MOCK-BIO-01)...")
        if reset:
            Test.objects.filter(mock_code="#MOCK-BIO-01").delete()

        bio_test, _ = Test.objects.get_or_create(
            mock_code="#MOCK-BIO-01",
            defaults={
                "title": "Biologiya — BMB Milliy Sertifikat & DTM Diagnostik Mock #1",
                "description": (
                    "BMB davlat standarti asosidagi to'liq biologiya diagnostik testi. "
                    "Sitologiya, anatomiya, botanika, genetika masalalari, 1-3 matritsali moslashtirish "
                    "hamda a/b ikki qismli ochiq masalalarni o'z ichiga oladi."
                ),
                "course": course_bio,
                "subject": "biology",
                "exam_type": Test.ExamType.NATIONAL_CERT,
                "time_limit_minutes": 120,
                "difficulty": Test.Difficulty.HARD,
                "status": Test.Status.PUBLISHED,
                "show_results_immediately": True,
            },
        )
        bio_test.subject = "biology"
        bio_test.save(update_fields=["subject"])

        # Create Questions for Biology if empty
        if bio_test.questions.count() == 0:
            bio_questions_data = [
                # Single Choice
                {
                    "text": "O'simlik hujayrasi qobig'ining asosiy tarkibiy qismini qaysi polisaxarid tashkil qiladi?",
                    "type": Question.QuestionType.SINGLE_CHOICE,
                    "points": 2,
                    "explanation": "O'simlik hujayrasi qobig'i sellyuloza (kletchatka) dan, zamburug'larniki xitindan, bakteriyalarniki esa mureindan iborat.",
                    "choices": [
                        ("Sellyuloza", True),
                        ("Xitin", False),
                        ("Murein", False),
                        ("Glikogen", False),
                    ],
                },
                {
                    "text": "Odam organizmida qon aylanishining katta doirasi qaysi yurak kamerasidan boshlanadi va qayerda tugaydi?",
                    "type": Question.QuestionType.SINGLE_CHOICE,
                    "points": 2,
                    "explanation": "Katta qon aylanish doirasi chap qorinchadan boshlanib, o'ng bo'lmachada tugaydi.",
                    "choices": [
                        ("Chap qorinchadan boshlanib, o'ng bo'lmachada tugaydi", True),
                        ("O'ng qorinchadan boshlanib, chap bo'lmachada tugaydi", False),
                        ("Chap bo'lmachadan boshlanib, o'ng qorinchada tugaydi", False),
                        ("O'ng bo'lmachadan boshlanib, chap qorinchada tugaydi", False),
                    ],
                },
                {
                    "text": "Hujayraning energetik stansiyasi hisoblangan va o'z DNKsiga ega bo'lgan organoid qaysi?",
                    "type": Question.QuestionType.SINGLE_CHOICE,
                    "points": 2,
                    "explanation": "Mitoxondriya ATF sintezlovchi energetik organoid bo'lib, o'zining halqasimon DNKsi va ribosomalariga ega.",
                    "choices": [
                        ("Mitoxondriya", True),
                        ("Golji majmuasi", False),
                        ("Ribosoma", False),
                        ("Lizosoma", False),
                    ],
                },
                {
                    "text": "Gulli o'simliklarda qo'sh urug'lanish hodisasini kim kashf etgan?",
                    "type": Question.QuestionType.SINGLE_CHOICE,
                    "points": 2,
                    "explanation": "1898-yilda rus botanigi S.G. Navashin gulli o'simliklarda qo'sh urug'lanish hodisasini kashf qilgan.",
                    "choices": [
                        ("S.G. Navashin", True),
                        ("G. Mendel", False),
                        ("R. Virxov", False),
                        ("K. Linney", False),
                    ],
                },
                {
                    "text": "DNK molekulasining bir zanjirida A-20%, T-30%, G-25%, S-25% bo'lsa, komplementar ikkinchi zanjirdagi adenin (A) ulushini (%) toping.",
                    "type": Question.QuestionType.SINGLE_CHOICE,
                    "points": 2,
                    "explanation": "Komplementarlik qoidasiga ko'ra (A=T, G=S), birinchi zanjirdagi timin (30%) ikkinchi zanjirdagi adeninga teng bo'ladi (30%).",
                    "choices": [
                        ("30%", True),
                        ("20%", False),
                        ("25%", False),
                        ("50%", False),
                    ],
                },
                # Matching Matrix (33-35)
                {
                    "text": (
                        "Organoidlar va ularning funksiyalari o'rtasidagi muvofiqlikni aniqlang:\n"
                        "1. Ribosoma\n"
                        "2. Lizosoma\n"
                        "3. Xloroplast\n\n"
                        "Variantlar:\n"
                        "A) Hujayra ichi hazmi va parchalanishi\n"
                        "B) Fotosintez va organik modda sintezi\n"
                        "C) Oqsil biosintezi\n"
                        "D) Yog' va uglevodlar to'planishi\n"
                        "E) Hujayra bo'linish dukini hosil qilish\n"
                        "F) ATF parchalanishi va harakat"
                    ),
                    "type": Question.QuestionType.MATCHING_MATRIX,
                    "points": 3,
                    "correct_text": "1-C, 2-A, 3-B",
                    "explanation": "1-Ribosoma oqsil biosintezini amalga oshiradi (C). 2-Lizosoma gidrolitik fermentlar orqali hazm qiladi (A). 3-Xloroplast fotosintez qiladi (B).",
                    "choices": [],
                },
                # Dual Open Calc (36-40)
                {
                    "text": (
                        "Genetika masalasi:\n"
                        "Pomidorda mevaning qizil rangi (A) sariq rang (a) ustidan, dumaloq shakli (B) noksimon shakli (b) ustidan dominantlik qiladi. "
                        "Digeterozigota (AaBb) o'simliklar o'zaro chatishtirildi.\n\n"
                        "a) F1 duragaylar orasida sariq noksimon mevali o'simliklarning nazariy ulushini (foizda) toping;\n"
                        "b) F1 duragaylar orasida necha xil fenotipik sinf hosil bo'ladi?"
                    ),
                    "type": Question.QuestionType.DUAL_OPEN_CALC,
                    "points": 4,
                    "correct_text": "6.25;6,25|4",
                    "explanation": "a) Sariq noksimon meva (aabb) nisbati 1/16 bo'lib, bu 6.25% ni tashkil qiladi. b) Digibrid chatishtirishda 4 xil fenotip (9:3:3:1) hosil bo'ladi.",
                    "choices": [],
                },
            ]

            for idx, qdata in enumerate(bio_questions_data, 1):
                q = Question.objects.create(
                    test=bio_test,
                    text=qdata["text"],
                    question_type=qdata["type"],
                    points=qdata["points"],
                    position=idx,
                    correct_text=qdata.get("correct_text", ""),
                    explanation=qdata.get("explanation", ""),
                )
                for c_text, is_corr in qdata.get("choices", []):
                    Choice.objects.create(
                        question=q,
                        text=c_text,
                        is_correct=is_corr,
                    )

        # =========================================================================
        # TEST 2: CHEMISTRY (#MOCK-CHEM-01)
        # =========================================================================
        self.stdout.write("Seeding Chemistry Mock Test (#MOCK-CHEM-01)...")
        if reset:
            Test.objects.filter(mock_code="#MOCK-CHEM-01").delete()

        chem_test, _ = Test.objects.get_or_create(
            mock_code="#MOCK-CHEM-01",
            defaults={
                "title": "Kimyo — BMB Milliy Sertifikat & DTM Diagnostik Mock #1",
                "description": (
                    "BMB davlat standarti asosidagi to'liq kimyo diagnostik imtihoni. "
                    "Mendeleyev davriy jadvali, eruvchanlik, oksidlanish darajasi, "
                    "stexiometriya, A-F matritsali moslashtirish va a/b ikki qismli hisoblash masalalarini o'z ichiga oladi."
                ),
                "course": course_chem,
                "subject": "chemistry",
                "exam_type": Test.ExamType.NATIONAL_CERT,
                "time_limit_minutes": 120,
                "difficulty": Test.Difficulty.HARD,
                "status": Test.Status.PUBLISHED,
                "show_results_immediately": True,
            },
        )
        chem_test.subject = "chemistry"
        chem_test.save(update_fields=["subject"])

        if chem_test.questions.count() == 0:
            chem_questions_data = [
                # Single Choice
                {
                    "text": "Kaliy dixromat (K2Cr2O7) dagi xromning oksidlanish darajasini toping.",
                    "type": Question.QuestionType.SINGLE_CHOICE,
                    "points": 2,
                    "explanation": "K(+1)*2 + Cr(x)*2 + O(-2)*7 = 0 => +2 + 2x - 14 = 0 => 2x = 12 => x = +6.",
                    "choices": [
                        ("+6", True),
                        ("+3", False),
                        ("+7", False),
                        ("+4", False),
                    ],
                },
                {
                    "text": "Quyidagi elektron konfiguratsiyalardan qaysi biri d-elementga tegishli?",
                    "type": Question.QuestionType.SINGLE_CHOICE,
                    "points": 2,
                    "explanation": "...3d⁶ 4s² konfiguratsiyasi temir (Fe) elementiga tegishli bo'lib, u o'tish d-elementidir.",
                    "choices": [
                        ("...3d⁶ 4s²", True),
                        ("...3s² 3p⁶", False),
                        ("...3s² 3p⁴", False),
                        ("...2s² 2p¹", False),
                    ],
                },
                {
                    "text": "Mis(II) sulfat (CuSO4) ning suvdagi eritmasi elektroliz qilinganda katodda va anodda qanday moddalar ajraladi?",
                    "type": Question.QuestionType.SINGLE_CHOICE,
                    "points": 2,
                    "explanation": "Cu²⁺ kationi vodoroddan o'ngda joylashganligi sababli katodda Cu ajraladi; kislorodli kislota qoldig'i (SO₄²⁻) bo'lgani uchun anodda suv oksidlanib O₂ ajraladi.",
                    "choices": [
                        ("Katodda Cu, anodda O2", True),
                        ("Katodda H2, anodda SO2", False),
                        ("Katodda Cu, anodda SO3", False),
                        ("Katodda H2, anodda O2", False),
                    ],
                },
                {
                    "text": "Quyidagi uglevodorodlarning qaysi biri bromli suvni rangsizlantiradi va sp² gibridlangan uglerod atomiga ega?",
                    "type": Question.QuestionType.SINGLE_CHOICE,
                    "points": 2,
                    "explanation": "Propen (CH3-CH=CH2) alken bo'lib, qo'shbog' hisobiga bromli suvni rangsizlantiradi va unda sp² gibridlangan uglerodlar mavjud.",
                    "choices": [
                        ("Propen", True),
                        ("Propan", False),
                        ("Metan", False),
                        ("Siklogeksan", False),
                    ],
                },
                # Matching Matrix
                {
                    "text": (
                        "Kristall panjara turlari va ularga mos moddalar o'rtasidagi muvofiqlikni aniqlang:\n"
                        "1. Atom kristall panjara\n"
                        "2. Ionli kristall panjara\n"
                        "3. Molekulyar kristall panjara\n\n"
                        "Variantlar:\n"
                        "A) Natriy xlorid (NaCl)\n"
                        "B) Olmos (C)\n"
                        "C) Quruq muz (CO2)\n"
                        "D) Mis (Cu)\n"
                        "E) Temir (Fe)\n"
                        "F) Kaliy gidroksid eritmasi"
                    ),
                    "type": Question.QuestionType.MATCHING_MATRIX,
                    "points": 3,
                    "correct_text": "1-B, 2-A, 3-C",
                    "explanation": "1-Olmos atom panjarali (B). 2-NaCl ionli panjarali (A). 3-CO2 molekulyar panjarali (C).",
                    "choices": [],
                },
                # Dual Open Calc
                {
                    "text": (
                        "Kimyoviy hisoblash masalasi:\n"
                        "Massasi 200 g bo'lgan 10% li natriy gidroksid (NaOH) eritmasiga yetarli miqdorda xlorid kislota (HCl) qo'shildi.\n\n"
                        "a) Hosil bo'lgan osh tuzi (NaCl) ning massasini (grammda) toping;\n"
                        "b) Reaksiyada qatnashgan NaOH ning miqdorini (mol) toping."
                    ),
                    "type": Question.QuestionType.DUAL_OPEN_CALC,
                    "points": 4,
                    "correct_text": "29.25;29,25|0.5;0,5",
                    "explanation": "a) m(NaOH) = 200 * 0.10 = 20 g. n(NaOH) = 20 / 40 = 0.5 mol. NaCl massasi = 0.5 * 58.5 = 29.25 g. b) n = 0.5 mol.",
                    "choices": [],
                },
            ]

            for idx, qdata in enumerate(chem_questions_data, 1):
                q = Question.objects.create(
                    test=chem_test,
                    text=qdata["text"],
                    question_type=qdata["type"],
                    points=qdata["points"],
                    position=idx,
                    correct_text=qdata.get("correct_text", ""),
                    explanation=qdata.get("explanation", ""),
                )
                for c_text, is_corr in qdata.get("choices", []):
                    Choice.objects.create(
                        question=q,
                        text=c_text,
                        is_correct=is_corr,
                    )

        # =========================================================================
        # TEST 3: LAW (#MOCK-LAW-01)
        # =========================================================================
        self.stdout.write("Seeding Law Mock Test (#MOCK-LAW-01)...")
        if reset:
            Test.objects.filter(mock_code="#MOCK-LAW-01").delete()

        law_test, _ = Test.objects.get_or_create(
            mock_code="#MOCK-LAW-01",
            defaults={
                "title": "Huquqshunoslik — Yurisprudensiya & Konstitutsiya Diagnostik Mock #1",
                "description": (
                    "O'zbekiston Respublikasi Konstitutsiyasi, davlat va huquq nazariyasi, "
                    "fuqarolik, mehnat va jinoyat huquqi bo'yicha situatsion kazuslar tahlili va diagnostik imtihon."
                ),
                "course": course_law,
                "subject": "law",
                "exam_type": Test.ExamType.NATIONAL_CERT,
                "time_limit_minutes": 100,
                "difficulty": Test.Difficulty.MEDIUM,
                "status": Test.Status.PUBLISHED,
                "show_results_immediately": True,
            },
        )
        law_test.subject = "law"
        law_test.save(update_fields=["subject"])

        if law_test.questions.count() == 0:
            law_questions_data = [
                # Single Choice Theory
                {
                    "text": "Yangi tahrirdagi O'zbekiston Respublikasi Konstitutsiyasining 1-moddasiga ko'ra, O'zbekiston qanday davlat deb e'lon qilingan?",
                    "type": Question.QuestionType.SINGLE_CHOICE,
                    "points": 2,
                    "explanation": "Konstitutsiyaning 1-moddasiga binoan O'zbekiston — boshqaruvning respublika shakliga ega bo'lgan suveren, demokratik, huquqiy, ijtimoiy va dunyoviy davlatdir.",
                    "choices": [
                        ("Suveren, demokratik, huquqiy, ijtimoiy va dunyoviy davlat", True),
                        ("Suveren, unitar, sotsialistik va diniy davlat", False),
                        ("Konstitutsiyaviy monarxiya va federal davlat", False),
                        ("Prezidentlik boshqaruvidagi parlamentar respublika", False),
                    ],
                },
                {
                    "text": "Huquqiy normaning mantiqiy tuzilishi qaysi uch elementdan iborat?",
                    "type": Question.QuestionType.SINGLE_CHOICE,
                    "points": 2,
                    "explanation": "Huquqiy normaning klassik tuzilishi: Gipoteza (shart), Dispozitsiya (xulq-atvor qoidasi) va Sanksiya (oqibat/jazo) dan iborat.",
                    "choices": [
                        ("Gipoteza, dispozitsiya, sanksiya", True),
                        ("Preambula, modda, band", False),
                        ("Kirish, asosiy qism, xulosa", False),
                        ("Huquq, majburiyat, javobgarlik", False),
                    ],
                },
                # Legal Case Study (Situatsion kazus)
                {
                    "text": (
                        "Fuqaro Aliyev 17 yoshli kollej bitiruvchisi bo'lib, o'ziga tegishli noutbukni ota-onasining roziligisiz "
                        "qo'shnisi Sobirovga 4 million so'mga sotdi. Ertasi kuni Aliyevning otasi bu bitimdan xabar topib, "
                        "o'g'lining voyaga yetmaganligini ro'kach qilib, bitimni bekor qilishni va noutbukni qaytarishni talab qildi.\n\n"
                        "Fuqarolik kodeksiga binoan, ushbu vaziyatda sud qanday qaror qabul qilishi kerak?"
                    ),
                    "type": Question.QuestionType.LEGAL_CASE_STUDY,
                    "points": 3,
                    "explanation": "O'zbekiston Respublikasi Fuqarolik kodeksiga ko'ra, 14 yoshdan 18 yoshgacha bo'lgan voyaga yetmaganlar o'z ish haqi yoki stipendiyalaridan tashqari yirik bitimlarni ota-onalarining yozma roziligi bilan tuzishlari shart. Rozilik bo'lmagani sababli bitim ota-onaning talabiga binoan haqiqiy emas deb topiladi.",
                    "choices": [
                        ("Bitim haqiqiy emas deb topiladi, chunki 14-18 yoshlilar bunday bitimlarni ota-onasi roziligi bilan tuzadi", True),
                        ("Bitim to'liq qonuniy, chunki 16 yoshdan fuqaro to'liq muomala layoqatiga ega", False),
                        ("Sobirov noutbukni qaytarmaslikka to'liq haqli, chunki pul to'langan", False),
                        ("Faqat Aliyev 18 yoshga to'lgandan keyingina bu masala ko'rib chiqiladi", False),
                    ],
                },
                # Another Legal Case Study
                {
                    "text": (
                        "Kompaniya rahbari xodim Karimovni hech qanday ogohlantirishsiz va kasaba uyushmasi roziligisiz, "
                        "faqatgina u bilan kelisha olmaganligi sababli ishdan bo'shatish to'g'risida buyruq chiqardi. "
                        "Karimov ishga tiklash va majburiy progul uchun ish haqi undirish da'vosi bilan fuqarolik sudiga murojaat qildi.\n\n"
                        "Mehnat qonunchiligi bo'yicha ushbu nizoning qonuniy yechimi qanday?"
                    ),
                    "type": Question.QuestionType.LEGAL_CASE_STUDY,
                    "points": 3,
                    "explanation": "Mehnat kodeksiga binoan ish beruvchi tashabbusi bilan mehnat shartnomasini bekor qilish qat'iy qonuniy asoslar va ogohlantirish muddatlariga rioya qilingan holda amalga oshirilishi shart. Asossiz bo'shatilgan xodim ishga tiklanadi va o'rtacha ish haqi to'liq undiriladi.",
                    "choices": [
                        ("Karimov ishga tiklanadi va majburiy progul vaqti uchun ish haqi to'liq undiriladi", True),
                        ("Rahbar xususiy korxona egasi bo'lgani uchun uning qarori o'zgarmaydi", False),
                        ("Karimovga faqat 2 haftalik nafaqa to'lanadi, lekin ishga tiklanmaydi", False),
                        ("Nizo faqat korxona ichki komissiyasi tomonidan hal qilinadi, sud aralashmaydi", False),
                    ],
                },
                # Matching Matrix
                {
                    "text": (
                        "Yuridik javobgarlik turlari va ularga qo'llaniladigan jazo choralari o'rtasidagi muvofiqlikni aniqlang:\n"
                        "1. Intizomiy javobgarlik\n"
                        "2. Ma'muriy javobgarlik\n"
                        "3. Jinoyat javobgarligi\n\n"
                        "Variantlar:\n"
                        "A) Hayfsan va ishdan bo'shatish\n"
                        "B) Ma'muriy qamoq va jarima\n"
                        "C) Ozodlikdan mahrum qilish\n"
                        "D) Yetkazilgan moddiy zararni qoplash\n"
                        "E) Diplomatik immunitet\n"
                        "F) Saylov huquqidan chetlatish"
                    ),
                    "type": Question.QuestionType.MATCHING_MATRIX,
                    "points": 3,
                    "correct_text": "1-A, 2-B, 3-C",
                    "explanation": "1-Intizomiy jazo: hayfsan, ishdan bo'shatish (A). 2-Ma'muriy jazo: ma'muriy qamoq, jarima (B). 3-Jinoiy jazo: ozodlikdan mahrum qilish (C).",
                    "choices": [],
                },
            ]

            for idx, qdata in enumerate(law_questions_data, 1):
                q = Question.objects.create(
                    test=law_test,
                    text=qdata["text"],
                    question_type=qdata["type"],
                    points=qdata["points"],
                    position=idx,
                    correct_text=qdata.get("correct_text", ""),
                    explanation=qdata.get("explanation", ""),
                )
                for c_text, is_corr in qdata.get("choices", []):
                    Choice.objects.create(
                        question=q,
                        text=c_text,
                        is_correct=is_corr,
                    )

        self.stdout.write(
            self.style.SUCCESS(
                "Successfully seeded authentic tests for Biology, Chemistry, and Law!"
            )
        )
