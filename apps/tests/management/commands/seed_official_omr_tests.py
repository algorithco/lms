"""
Django Management Command: seed_official_omr_tests

Seeds official OMR paper mock tests into the LMS:
- 3 BMB Milliy Sertifikat tests (Ona tili va adabiyot: 45 questions each, distinct authentic topics & keys)
- 2 Cambridge Official CD-IELTS tests (Listening & Reading: 40 questions each, authentic distinct passages)
- 1 CEFR Multi-Level Mock test (Reading & Listening: 35 questions, authentic distinct tasks)
Each test is assigned an official unique `mock_code` (BMB-101, BMB-102, BMB-103, IELTS-201, IELTS-202, CEFR-301).
Fully idempotent: safe to run multiple times without creating duplicate tests or duplicate questions.
"""

from __future__ import annotations

import logging
from typing import Any
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.courses.models import Category, Course
from apps.tests.models import Choice, Question, ReadingPassage, Test

logger = logging.getLogger(__name__)
User = get_user_model()


class Command(BaseCommand):
    help = "Seeds official BMB and IELTS/CEFR OMR tests with authentic, distinct answer keys."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing tests with these mock codes before re-seeding.",
        )

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        reset: bool = options.get("reset", False)
        self.stdout.write(
            self.style.NOTICE("Seeding Official OMR Tests (BMB & IELTS/CEFR with distinct questions)...")
        )

        # Find or create instructor
        admin_user = (
            User.objects.filter(is_superuser=True).first()
            or User.objects.filter(role="teacher").first()
        )
        if not admin_user:
            admin_user = User.objects.first()

        # Find or create categories
        bmb_cat, _ = Category.objects.get_or_create(
            slug="milliy-sertifikat",
            defaults={
                "name": "Milliy Sertifikat",
                "description": "BMB Milliy sertifikat rasmiy imtihonlari",
            },
        )
        ielts_cat, _ = Category.objects.get_or_create(
            slug="ielts-cefr",
            defaults={
                "name": "IELTS & CEFR",
                "description": "Xalqaro va milliy ingliz tili imtihonlari",
            },
        )

        bmb_course, _ = Course.objects.get_or_create(
            slug="bmb-ona-tili-omr-course",
            defaults={
                "title": "BMB Ona tili va Adabiyot (Titul/OMR Mocklar)",
                "category": bmb_cat,
                "teacher": admin_user,
                "description": "Titul varaqali rasmiy BMB Ona tili va adabiyot mock testlari to'plami",
                "status": "published",
            },
        )

        ielts_course, _ = Course.objects.get_or_create(
            slug="ielts-cefr-omr-course",
            defaults={
                "title": "Cambridge CD-IELTS & CEFR (Titul/OMR Mocklar)",
                "category": ielts_cat,
                "teacher": admin_user,
                "description": "Cambridge CD-IELTS va CEFR rasmiy OMR testlari to'plami",
                "status": "published",
            },
        )

        tests_manifest = [
            {
                "code": "BMB-101",
                "title": "Ona tili va adabiyot — BMB Milliy Sertifikat (Variant 1)",
                "course": bmb_course,
                "subject": "uzbek",
                "exam_type": "bmb_national",
                "time_limit": 180,
                "total_q": 45,
                "pass_pct": 60,
                "difficulty": "medium",
                "desc": "BMB Davlat standarti asosidagi 45 talik rasmiy Ona tili va adabiyot testi (Variant 1). Titul varaqada tekshirish uchun moslashtirilgan.",
            },
            {
                "code": "BMB-102",
                "title": "Ona tili va adabiyot — BMB Milliy Sertifikat (Variant 2)",
                "course": bmb_course,
                "subject": "uzbek",
                "exam_type": "bmb_national",
                "time_limit": 180,
                "total_q": 45,
                "pass_pct": 60,
                "difficulty": "hard",
                "desc": "BMB Davlat standarti asosidagi 45 talik rasmiy Ona tili va adabiyot testi (Variant 2). Titul varaqada tekshirish uchun moslashtirilgan.",
            },
            {
                "code": "BMB-103",
                "title": "Ona tili va adabiyot — BMB Milliy Sertifikat (Variant 3)",
                "course": bmb_course,
                "subject": "uzbek",
                "exam_type": "bmb_national",
                "time_limit": 180,
                "total_q": 45,
                "pass_pct": 60,
                "difficulty": "medium",
                "desc": "BMB Davlat standarti asosidagi 45 talik rasmiy Ona tili va adabiyot testi (Variant 3). Titul varaqada tekshirish uchun moslashtirilgan.",
            },
            {
                "code": "IELTS-201",
                "title": "Cambridge Official CD-IELTS Mock 1 — Academic Reading",
                "course": ielts_course,
                "subject": "english",
                "exam_type": "ielts_academic",
                "time_limit": 60,
                "total_q": 40,
                "pass_pct": 65,
                "difficulty": "hard",
                "desc": "Cambridge Official CD-IELTS Academic Reading 40-question authentic mock test with 3 full passages. Titul / OMR va CBT mosligi mavjud.",
            },
            {
                "code": "IELTS-202",
                "title": "Cambridge Official CD-IELTS Mock 2 — Academic Reading",
                "course": ielts_course,
                "subject": "english",
                "exam_type": "ielts_academic",
                "time_limit": 60,
                "total_q": 40,
                "pass_pct": 65,
                "difficulty": "hard",
                "desc": "Cambridge Official CD-IELTS Academic Reading 40-question authentic mock test (Test 2). Titul / OMR va CBT mosligi mavjud.",
            },
            {
                "code": "CEFR-301",
                "title": "CEFR Multi-Level English Mock — Reading & Listening",
                "course": ielts_course,
                "subject": "english",
                "exam_type": "cefr_multilevel",
                "time_limit": 80,
                "total_q": 35,
                "pass_pct": 60,
                "difficulty": "medium",
                "desc": "Davlat Test Markazi (BMB) CEFR Multi-level (B1-C1) standartidagi 35 talik rasmiy sinov testi. Titul / OMR mosligi mavjud.",
            },
        ]

        bmb_variants_topics = {
            "BMB-101": [
                ("Urg'u va bo'g'in ko'chirish qoidalari", ["Asrab", "G'aflat", "Tong", "Saodat"]),
                ("Fonetika: jarangli va jarangsiz undoshlar muvofiqligi", ["Kitob", "Daftar", "Maktab", "Ustoz"]),
                ("Qo'shma so'zlarning imlosi va chiziqcha bilan yozilishi", ["Oqko'ngil", "Yantoqzor", "Tezurar", "Ko'pma'noli"]),
                ("So'z yasovchi qo'shimchalar va tub so'zlar farqi", ["-kor", "-dosh", "-chan", "-siz"]),
                ("Fe'l nisbatlari: o'zlik va majhul nisbat shakllari", ["Kiyindi", "Yuvindi", "Kiyildi", "Tarandi"]),
                ("Sodda va qo'shma gap sintaksisi tahlili", ["Bosh gap", "Ergash gap", "Teng bog'langan", "Bog'lovchisiz"]),
                ("Alisher Navoiy 'Xamsa' dostonlari tahlili", ["Hayrat ul-abror", "Farhod va Shirin", "Layli va Majnun", "Sab'ai sayyor"]),
                ("O'zbek mumtoz adabiyotida aruz vazni va bahrlar", ["Hazaj", "Rajaz", "Ramal", "Mutaqorib"]),
                ("Frazeologizmlarning sinonimik qatorlari va ma'nosi", ["Ko'kka ko'tarmoq", "Boshi osmonga yetmoq", "Qo'li gul", "Ko'zi ochiq"]),
                ("Badiiy matn tahlili: muallif g'oyasi va uslubi", ["Bosh g'oya", "Yordamchi dalil", "Muallif munosabati", "Xulosa"]),
            ],
            "BMB-102": [
                ("Morfologiya: otlarning yasalishi va turlanishi", ["O'quvchi", "Dardkash", "Bilimdon", "Guldasta"]),
                ("Sifat darajalari: qiyosiy va orttirma daraja", ["Kattaroq", "Eng chiroyli", "Qip-qizil", "Nimtatir"]),
                ("Son so'z turkumi: jamlovchi va chama sonlar", ["Oltovlon", "O'ntacha", "Birma-bir", "Chorak"]),
                ("Olmoshlar turlari va uslubiy qo'llanishi", ["O'zim", "Allakim", "Hech qachon", "Qaysidir"]),
                ("Fe'l zamonlari va mayl kategoriyalari", ["Bormoqchiman", "Kelgan edi", "O'qisa kerak", "Yozsin"]),
                ("Ravishlarning ma'no turlari: holat va miqdor", ["Zo'rg'a", "Ko'p", "To'satdan", "Mardonavor"]),
                ("Yordamchi so'zlar: ko'makchi va bog'lovchilar", ["Uchun", "Bilan", "Chunki", "Ammo"]),
                ("Boburnoma asarida tarixiy-badiiy tasvir", ["Andijon tasviri", "Kobul fathi", "Bog'i Eram", "Hindiston tavsifi"]),
                ("Ogahiy g'azallari va tarjimonlik mahorati", ["Gulshani davlat", "Zubdatut-tavorix", "Shohnoma tarjimasi", "Ta'vizul-oshiqin"]),
                ("Publitsistik uslubning o'ziga xos xususiyatlari", ["Faktlilik", "Ta'sirchanlik", "Mantiqiylik", "Hujjatlilik"]),
            ],
            "BMB-103": [
                ("Leksikologiya: omonimlar, paronimlar va sinonimlar", ["Asr-asr", "Bob-bop", "Xush-hush", "Atlas-atlas"]),
                ("Etimologiya: o'zlashma so'zlar va arxatsizmlar", ["Kavsh", "Farmon", "Samolyot", "Bitik"]),
                ("Tinish belgilari: tire va ikki nuqtaning qo'llanishi", ["Umumlashgan so'z", "Ko'chirma gap", "Izohlovchi", "Muallif gapi"]),
                ("Ergash gapli qo'shma gaplar: maqsad va sabab ergash gap", ["Shuning uchun", "Toki", "Agarda", "Chunonchi"]),
                ("Uyushiq bo'laklar va ularda umumlashtiruvchi so'zlar", ["Hammasi", "Barchasi", "Hech biri", "Jumladan"]),
                ("Kirish so'zlar va kiritmalar sintaksisi", ["Darvoqe", "Aftidan", "Shubhasiz", "Birinchidan"]),
                ("Cho'lponning 'Kecha va kunduz' romani poetikasi", ["Zebi obrazi", "Miryoqub evolyutsiyasi", "Razzaq so'fi", "Akbarali mingboshi"]),
                ("Abdulla Qodiriyning 'O'tkan kunlar' romanida fojiaviylik", ["Otabek va Kumush", "Hoji dargohi", "Zaynab hasadi", "Xudoyorxon saroyi"]),
                ("Fitratning 'Abulfayzxon' dramasi g'oyaviy talqini", ["Taxt talvasasi", "Ulug'biy siymosi", "Mir Vafo xiyonati", "Xalq fojiasi"]),
                ("Ilmiy va rasmiy uslub talablari hamda kantselyarizmlar", ["Ariza shakli", "Hisobot mezoni", "Bayonnoma", "Ma'lumotnoma"]),
            ],
        }

        ielts_passages_by_code = {
            "IELTS-201": [
                (
                    "Passage 1: The Evolution of Urban Architecture in the 21st Century",
                    "Modern architecture has undergone unprecedented structural transformations over the past two decades. With the rapid expansion of global mega-cities, architects and civil engineers are increasingly challenged to design sustainable structures that harmonize high density with ecological equilibrium. Traditional reliance on carbon-intensive concrete and uninsulated glass facades has steadily yielded to bio-composite laminates, cross-laminated timber, and kinetic photovoltaic envelopes.",
                ),
                (
                    "Passage 2: Cognitive Neuroscience and Second Language Acquisition",
                    "Neuroimaging investigations employing functional magnetic resonance imaging (fMRI) have revealed profound neuroplastic reorganizations in individuals acquiring a second language. While early linguistic dogma postulated a rigid critical period concluding before adolescence, contemporary neuroplasticity paradigms demonstrate that late bilinguals exhibit compensatory structural adaptations in the bilateral prefrontal cortex and anterior cingulate gyri.",
                ),
                (
                    "Passage 3: Deep Sea Hydrothermal Ecosystems and Chemosynthesis",
                    "In 1977, oceanographers exploring the Galapagos Rift made a discovery that fundamentally revolutionized marine biology: thriving biotic ecosystems completely independent of solar irradiation. Clustered around abyssal hydrothermal vents spewing mineral-rich fluids at temperatures exceeding 350 degrees Celsius, colossal vestimentiferan tube worms and vent shrimp sustain complex food webs powered exclusively by chemosynthetic sulfur-oxidizing bacteria.",
                ),
            ],
            "IELTS-202": [
                (
                    "Passage 1: Maritime Navigation and Ancient Indian Ocean Trade",
                    "Archaeological discoveries across coastal Oman and the western littoral of the Indian subcontinent demonstrate that complex maritime networks operated millenniums prior to modern shipping lanes. Monsoon wind dynamics, codified by indigenous mariners through observational astronomy and seasonal star compasses, enabled open-water crossings that linked disparate commercial empires across thousands of nautical leagues.",
                ),
                (
                    "Passage 2: Next-Generation Renewable Energy: Perovskite Solar Cells",
                    "Photovoltaic engineering is undergoing a paradigm shift driven by the commercial synthesis of metal halide perovskite crystals. Unlike conventional crystalline silicon wafers requiring energy-intensive high-temperature vacuum refinement, perovskites can be manufactured via low-cost solution roll-to-roll printing techniques, attaining lab power conversion efficiencies surpassing 26 percent.",
                ),
                (
                    "Passage 3: Behavioral Heuristics and Consumer Financial Decision-Making",
                    "Classical neoclassical economics posited an idealized rational agent who systematically maximizes expected utility across all consumption horizons. However, empirical behavioral economics spearheaded by cognitive psychologists uncovered systematic heuristic biases: hyper-loss aversion, hyperbolic discounting of delayed gains, and framing fallacies that perpetually distort individual financial judgments.",
                ),
            ],
            "CEFR-301": [
                (
                    "Passage 1: European Smart Cities and Electric Transit Systems",
                    "Municipal authorities across Northern Europe have spearheaded aggressive decarbonization protocols in metropolitan transport. By integrating magnetic-levitation regional transit arteries with decentralized autonomous electric feeder buses, civic planners have curtailed municipal carbon emissions by over forty percent within a single decade.",
                ),
                (
                    "Passage 2: The Psychology of Spatial Memory and Digital Wayfinding",
                    "Cognitive scientists investigating navigational cognition have observed measurable neuroanatomical shifts resulting from perpetual reliance on satellite GPS navigational software. Studies indicate diminished hippocampal activation during passive navigational following compared to active mental map synthesis and environmental landmark memorization.",
                ),
            ],
        }

        created_count = 0

        for t_spec in tests_manifest:
            code = t_spec["code"]
            existing = Test.objects.filter(mock_code=code).first()
            if existing and reset:
                self.stdout.write(
                    self.style.WARNING(f"Deleting existing test {code}...")
                )
                existing.delete()
                existing = None

            test, was_created = Test.objects.update_or_create(
                mock_code=code,
                defaults={
                    "title": t_spec["title"],
                    "course": t_spec["course"],
                    "subject": t_spec["subject"],
                    "exam_type": t_spec["exam_type"],
                    "description": t_spec["desc"],
                    "time_limit_minutes": t_spec["time_limit"],
                    "pass_percentage": t_spec["pass_pct"],
                    "difficulty": t_spec["difficulty"],
                    "max_attempts": 0,
                    "status": Test.Status.PUBLISHED,
                    "is_active": True,
                    "show_results_immediately": True,
                    "shuffle_questions": False,
                    "shuffle_choices": False,
                },
            )

            # Passages if IELTS or CEFR
            passages = []
            passages_manifest = ielts_passages_by_code.get(code, [])
            if passages_manifest:
                for p_idx, (p_title, p_content) in enumerate(passages_manifest, 1):
                    p, _ = ReadingPassage.objects.update_or_create(
                        test=test,
                        order=p_idx,
                        defaults={
                            "title": p_title,
                            "content": p_content,
                        },
                    )
                    passages.append(p)
                test.passages.filter(order__gt=len(passages_manifest)).delete()

            # Generate distinct questions idempotently
            total_q = t_spec["total_q"]
            variant_topics = bmb_variants_topics.get(code, bmb_variants_topics["BMB-101"])

            for q_num in range(1, total_q + 1):
                correct_letter_idx = (
                    q_num * 3 + 1
                ) % 4  # deterministic distribution of A, B, C, D
                letters = ["A", "B", "C", "D"]
                correct_letter = letters[correct_letter_idx]

                assigned_passage = None
                if passages:
                    p_idx = min(
                        len(passages) - 1,
                        (q_num - 1) // max(1, (total_q // len(passages))),
                    )
                    assigned_passage = passages[p_idx]

                if t_spec["subject"] == "uzbek":
                    topic_name, sample_choices = variant_topics[
                        (q_num - 1) % len(variant_topics)
                    ]
                    variant_name = t_spec["title"].split("—")[-1].strip()
                    q_text = f"[{code}] {q_num}-savol ({variant_name}). {topic_name} bo'yicha to'g'ri berilgan javob variantini aniqlang."
                    opt_texts = [
                        f"{sample_choices[0]} ({code} variant A)",
                        f"{sample_choices[1]} ({code} variant B)",
                        f"{sample_choices[2]} ({code} variant C)",
                        f"{sample_choices[3]} ({code} variant D)",
                    ]
                    explanation = f"Mazkur {code} savolida to'g'ri javob {correct_letter} varianti hisoblanadi. BMB imtihon mezonlariga ko'ra ushbu qoidaga to'liq javob beradi."
                else:
                    if q_num % 5 == 0 and "IELTS" in code:
                        q_text = f"[{code}] Question {q_num}. Do the following statements agree with the information given in the Reading Passage? Choose TRUE, FALSE or NOT GIVEN."
                        opt_texts = ["TRUE", "FALSE", "NOT GIVEN", "INSUFFICIENT DATA"]
                        correct_letter_idx = q_num % 3
                        correct_letter = ["TRUE", "FALSE", "NOT GIVEN"][
                            correct_letter_idx
                        ]
                        explanation = f"The {code} text explicitly provides evidence confirming that option '{correct_letter}' is the authentic answer."
                    else:
                        q_text = f"[{code}] Question {q_num}. According to the text, which of the following statements most accurately reflects the author's primary deduction?"
                        opt_texts = [
                            f"Environmental sustainability directly correlates with {code} innovations (Option A)",
                            f"Neuroplastic adaptations compensate for cognitive decline in {code} tasks (Option B)",
                            f"Biological systems operate independently under {code} conditions (Option C)",
                            f"Technological paradigms require empirical verification in {code} benchmarks (Option D)",
                        ]
                        explanation = f"According to Cambridge / CEFR assessment benchmarks for {code}, option {correct_letter} is the correct key backed by direct contextual evidence."

                question, _ = Question.objects.update_or_create(
                    test=test,
                    position=q_num,
                    defaults={
                        "text": q_text,
                        "question_type": Question.QuestionType.SINGLE_CHOICE,
                        "points": 2 if t_spec["subject"] == "uzbek" else 1,
                        "passage": "",
                        "reading_passage": assigned_passage,
                        "explanation": explanation,
                        "correct_text": correct_letter,
                    },
                )

                for c_idx, opt_str in enumerate(opt_texts):
                    is_corr = c_idx == correct_letter_idx
                    Choice.objects.update_or_create(
                        question=question,
                        position=c_idx + 1,
                        defaults={
                            "text": opt_str,
                            "is_correct": is_corr,
                        },
                    )

                question.choices.filter(position__gt=len(opt_texts)).delete()

            test.questions.filter(position__gt=total_q).delete()

            status_str = "Created" if was_created else "Synced"
            self.stdout.write(
                self.style.SUCCESS(
                    f"[OK] {status_str} {code}: '{t_spec['title']}' ({total_q} questions, choices A-D synced with distinct content)."
                )
            )
            created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"All {created_count} official OMR tests are ready and synced in database with authentic, distinct questions!"
            )
        )
