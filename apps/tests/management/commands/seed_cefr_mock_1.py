"""
Django Management Command: seed_cefr_mock_1

Seeds the authentic CEFR Multi-Level & IELTS mock examination:
"Record Mock – Test 1 (Multi-Level CEFR & IELTS)"
Based on RECORD MOCK _ TEST 1 - Multi-Level Record.pdf:
- 35 Listening Questions (Parts 1 to 6)
- 35 Reading Questions (Parts 1 to 5)
- 3 Writing Tasks (Task 1.1 Informal, Task 1.2 Formal, Task 2 Blog Post)
- 4 Speaking Parts (Parts 1.1, 1.2, 2, 3)

100% idempotent: safe to execute multiple times.
"""

from __future__ import annotations

import logging
from typing import Any
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.courses.models import Category, Course
from apps.tests.models import (
    Choice,
    ExamSection,
    GapBlank,
    Question,
    ReadingPassage,
    Test,
)

logger = logging.getLogger(__name__)
User = get_user_model()


class Command(BaseCommand):
    help = "Seeds the authentic CEFR Multi-Level & IELTS Record Mock - Test 1 with complete 35L + 35R + 3W + 4S items."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing test with mock_code CEFR-RECORD-1 before re-seeding.",
        )

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        reset: bool = options.get("reset", False)
        self.stdout.write(self.style.NOTICE("Seeding CEFR Multi-Level Record Mock - Test 1..."))

        admin_user = (
            User.objects.filter(is_superuser=True).first()
            or User.objects.filter(role="teacher").first()
            or User.objects.first()
        )
        if not admin_user:
            admin_user = User.objects.create_user(
                email="exam_admin@grandec.uz",
                password="admin_secure_password_2026",
                role="teacher",
                first_name="Exam Admin",
                is_staff=True,
            )

        category, _ = Category.objects.get_or_create(
            slug="cefr-ielts-authentic",
            defaults={
                "name": "CEFR & IELTS Official Mocks",
                "description": "Authentic British Council & BMB Multi-Level Computer Delivered Exams",
            },
        )

        course, _ = Course.objects.get_or_create(
            slug="cefr-multilevel-record-course",
            defaults={
                "title": "CEFR Multi-Level & IELTS Authentic Exam Series",
                "category": category,
                "teacher": admin_user,
                "description": "Rasmiy BMB va British Council andozasidagi Multi-Level va CD-IELTS sinov imtihonlari to'plami.",
                "status": "published",
            },
        )

        mock_code = "CEFR-RECORD-1"
        if reset:
            Test.objects.filter(mock_code=mock_code).delete()
            self.stdout.write(self.style.WARNING(f"Deleted existing test with code {mock_code}"))

        test, created = Test.objects.get_or_create(
            mock_code=mock_code,
            defaults={
                "title": "Record Mock – Test 1 (Multi-Level CEFR & IELTS)",
                "description": (
                    "BMB va British Council CD-IELTS rasmiy kompyuter imtihoni nusxasi. "
                    "Listening (35 ta), Reading (35 ta), Writing (3 ta) va Speaking (4 qism)."
                ),
                "course": course,
                "subject": "english",
                "exam_type": Test.ExamType.CEFR_MULTILEVEL,
                "scoring_type": Test.ScoringType.RASCH_DYNAMIC,
                "time_limit_minutes": 140,
                "pass_percentage": 60,
                "difficulty": Test.Difficulty.MEDIUM,
                "status": Test.Status.PUBLISHED,
                "is_active": True,
                "show_results_immediately": True,
                "shuffle_questions": False,
                "shuffle_choices": False,
                "is_strict_mode": True,
                "strict_anti_cheat": True,
                "created_by": admin_user,
            },
        )

        if not created and not reset:
            self.stdout.write(self.style.SUCCESS(f"Test '{test.title}' already exists (ID: {test.id}). Updating contents..."))

        # Create or update sections
        sec_listening, _ = ExamSection.objects.update_or_create(
            test=test,
            code="LISTENING",
            defaults={
                "name": "Listening (35 Questions)",
                "order": 1,
                "duration_minutes": 40,
            },
        )
        sec_reading, _ = ExamSection.objects.update_or_create(
            test=test,
            code="READING",
            defaults={
                "name": "Reading (35 Questions)",
                "order": 2,
                "duration_minutes": 60,
            },
        )
        sec_writing, _ = ExamSection.objects.update_or_create(
            test=test,
            code="WRITING",
            defaults={
                "name": "Writing (3 Tasks)",
                "order": 3,
                "duration_minutes": 45,
            },
        )
        sec_speaking, _ = ExamSection.objects.update_or_create(
            test=test,
            code="SPEAKING",
            defaults={
                "name": "Speaking (4 Parts)",
                "order": 4,
                "duration_minutes": 15,
            },
        )

        # Remove existing questions to allow clean idempotent re-seed
        test.questions.all().delete()
        test.passages.all().delete()

        # =====================================================================
        # 1. LISTENING SECTION (35 Questions)
        # =====================================================================

        # --- Listening Part 1 (1–8) ---
        l_part1_questions = [
            (1, "1. Choose the correct reply to sentence 1:", ["Me too.", "Can you?", "Sure, you can."], "C"),
            (2, "2. Choose the correct reply to sentence 2:", ["Take bus 6.", "It starts at 9 a.m. tomorrow.", "It’s in the center."], "A"),
            (3, "3. Choose the correct reply to sentence 3:", ["OK, here it is.", "No, that doesn’t suit you.", "Sure, I’ll wait here."], "C"),
            (4, "4. Choose the correct reply to sentence 4:", ["In the school library.", "Since 1997.", "Before I was born."], "B"),
            (5, "5. Choose the correct reply to sentence 5:", ["You should take a short break.", "Let’s get to work right now!", "Don’t worry, they haven’t."], "A"),
            (6, "6. Choose the correct reply to sentence 6:", ["How about an ice-cream?", "You need to wear your sweater.", "Let’s eat some fresh pizza and chips."], "A"),
            (7, "7. Choose the correct reply to sentence 7:", ["When does it happen?", "Where did you see that?", "Who told you that?"], "C"),
            (8, "8. Choose the correct reply to sentence 8:", ["My hands are also firm.", "Sounds like a boring person.", "Can you expect anything?"], "B"),
        ]

        for pos, q_text, choices, correct_letter in l_part1_questions:
            q = Question.objects.create(
                test=test,
                section=sec_listening,
                position=pos,
                text=q_text,
                question_type=Question.QuestionType.MULTIPLE_CHOICE,
                points=1,
                config={"part": 1, "section": "listening", "subtype": "sentence_reply"},
            )
            for c_idx, c_text in enumerate(choices):
                letter = chr(65 + c_idx)
                Choice.objects.create(
                    question=q,
                    text=f"{letter}  {c_text}",
                    is_correct=(letter == correct_letter),
                    position=c_idx,
                )

        # --- Listening Part 2 (9–14) SCHOOL TRIP Gap-Fill ---
        p2_passage = ReadingPassage.objects.create(
            test=test,
            section=sec_listening,
            order=1,
            title="SCHOOL TRIP – NOTES",
            content=(
                "SCHOOL TRIP INFORMATION:\n"
                "• Teacher’s name: Turner\n"
                "• They will travel by (9) __________ .\n"
                "• First activity: they walk around the (10) __________ .\n"
                "• Students spend their free time in the (11) __________ .\n"
                "• Lunch will be a (12) __________ together.\n"
                "• They will visit a (13) __________ .\n"
                "• They should bring a (14) __________ ."
            ),
        )

        l_part2_questions = [
            (9, "They will travel by (9) __________ .", "coach"),
            (10, "First activity: they walk around the (10) __________ .", "lake"),
            (11, "Students spend their free time in the (11) __________ .", "park"),
            (12, "Lunch will be a (12) __________ together.", "picnic"),
            (13, "They will visit a (13) __________ .", "museum"),
            (14, "They should bring a (14) __________ .", "raincoat"),
        ]

        for pos, q_text, ans_key in l_part2_questions:
            q = Question.objects.create(
                test=test,
                section=sec_listening,
                reading_passage=p2_passage,
                position=pos,
                text=q_text,
                question_type=Question.QuestionType.INLINE_GAP_FILL,
                correct_text=ans_key,
                points=1,
                config={"part": 2, "section": "listening", "subtype": "inline_gap_fill", "gap_number": pos},
            )
            GapBlank.objects.create(question=q, position=0, answer_text=ans_key)

        # --- Listening Part 3 (15–18) Speaker Situation Matching ---
        speaker_options = [
            ("A", "In a swimming pool"),
            ("B", "At home"),
            ("C", "In a shopping centre"),
            ("D", "In a garden"),
            ("E", "In a restaurant"),
            ("F", "In a classroom"),
        ]
        l_part3_keys = {15: "A", 16: "F", 17: "B", 18: "D"}

        p3_passage = ReadingPassage.objects.create(
            test=test,
            section=sec_listening,
            order=2,
            title="SPEAKER SITUATIONS (A–F)",
            content=(
                "Match each speaker (15–18) to the place where they are (A–F).\n"
                "There are TWO extra options which you do not need to use.\n\n"
                "A   In a swimming pool\n"
                "B   At home\n"
                "C   In a shopping centre\n"
                "D   In a garden\n"
                "E   In a restaurant\n"
                "F   In a classroom"
            ),
        )

        for pos in range(15, 19):
            correct_letter = l_part3_keys[pos]
            q = Question.objects.create(
                test=test,
                section=sec_listening,
                reading_passage=p3_passage,
                position=pos,
                text=f"{pos}. Speaker {pos - 14} is in:",
                question_type=Question.QuestionType.MATCHING,
                points=1,
                config={"part": 3, "section": "listening", "subtype": "speaker_matching"},
            )
            for c_idx, (letter, label) in enumerate(speaker_options):
                Choice.objects.create(
                    question=q,
                    text=f"{letter}   {label}",
                    is_correct=(letter == correct_letter),
                    position=c_idx,
                )

        # --- Listening Part 4 (19–23) Interactive Map Labeling ---
        map_plan_content = (
            "COMMUNITY CENTRE PLAN\n"
            "Label the places (19–23) on the map (A–H).\n"
            "There are THREE extra options which you do not need to use.\n\n"
            "Map Facilities:\n"
            "• Medical Centre (Top left)\n"
            "• Computer room (Top middle)\n"
            "• Gym (Top right)\n"
            "• Baby Care room (Right middle)\n"
            "• Sports Hall (Right center)\n"
            "• Games room (Center left)\n"
            "• Library (Bottom left)\n"
            "• Reception (Bottom middle/entrance)\n"
            "Letter locations: A, B, C, D, E, F, G, H"
        )
        p4_passage = ReadingPassage.objects.create(
            test=test,
            section=sec_listening,
            order=3,
            title="COMMUNITY CENTRE PLAN (MAP)",
            content=map_plan_content,
        )

        map_places = [
            (19, "Bike racks", "D"),
            (20, "Kitchen room", "C"),
            (21, "Music room", "A"),
            (22, "Shower room", "E"),
            (23, "Restroom", "H"),
        ]
        map_letters = ["A", "B", "C", "D", "E", "F", "G", "H"]

        for pos, place_name, correct_letter in map_places:
            q = Question.objects.create(
                test=test,
                section=sec_listening,
                reading_passage=p4_passage,
                position=pos,
                text=f"{pos}. {place_name}",
                question_type=Question.QuestionType.MAP_LABELING,
                points=1,
                config={
                    "part": 4,
                    "section": "listening",
                    "subtype": "map_labeling",
                    "place_name": place_name,
                    "plan_name": "COMMUNITY CENTRE PLAN",
                },
            )
            for c_idx, letter in enumerate(map_letters):
                Choice.objects.create(
                    question=q,
                    text=f"Room {letter}",
                    is_correct=(letter == correct_letter),
                    position=c_idx,
                )

        # --- Listening Part 5 (24–29) Extracts MCQ ---
        l_part5 = [
            (24, "EXTRACT ONE: What is the main conversation about?", ["A new library and its features", "A recent community event", "Renovations at the local museum"], "A"),
            (25, "EXTRACT ONE: What is the woman concerned about?", ["The lack of seating", "There are too many people in the evenings", "The opening hours are too short"], "B"),
            (26, "EXTRACT TWO: What is the main conversation about?", ["The menu options at a café", "The location of a popular café", "The size and atmosphere of a new coffee shop"], "C"),
            (27, "EXTRACT TWO: What did the man say about the new coffee shop?", ["The service was slower", "The prices were higher", "The staff weren’t friendlier"], "A"),
            (28, "EXTRACT THREE: What is the main conversation about?", ["The difficulty of taking care of a pet animal", "Choosing the right breed for a family", "Training a dog to behave indoors"], "B"),
            (29, "EXTRACT THREE: What was the woman’s recommendation?", ["Going for a smaller one", "Buying a pet from a shelter", "Hiring a professional trainer"], "A"),
        ]

        for pos, q_text, choices, correct_letter in l_part5:
            q = Question.objects.create(
                test=test,
                section=sec_listening,
                position=pos,
                text=f"{pos}. {q_text}",
                question_type=Question.QuestionType.MULTIPLE_CHOICE,
                points=1,
                config={"part": 5, "section": "listening", "subtype": "extract_mcq"},
            )
            for c_idx, c_text in enumerate(choices):
                letter = chr(65 + c_idx)
                Choice.objects.create(
                    question=q,
                    text=f"{letter}  {c_text}",
                    is_correct=(letter == correct_letter),
                    position=c_idx,
                )

        # --- Listening Part 6 (30–35) Marketing and Branding Gap-Fill ---
        p6_passage = ReadingPassage.objects.create(
            test=test,
            section=sec_listening,
            order=4,
            title="MARKETING AND BRANDING",
            content=(
                "LECTURE NOTES:\n"
                "A strong brand can help a company dominate its (30) __________ .\n"
                "Apple products are considered more valuable because of their high (31) __________ .\n"
                "Many brands focus less on selling logic and more on selling (32) __________ .\n"
                "After drinking Coca-Cola, customers don’t notice the ingredients but experience a feeling of (33) __________ .\n"
                "Online businesses track customer preferences using (34) __________ history.\n"
                "This data helps improve both the customer experience and overall (35) __________ ."
            ),
        )

        l_part6 = [
            (30, "A strong brand can help a company dominate its (30) __________ .", "market"),
            (31, "Apple products are considered more valuable because of their high (31) __________ .", "quality"),
            (32, "Many brands focus less on selling logic and more on selling (32) __________ .", "feelings"),
            (33, "After drinking Coca-Cola, customers don’t notice the ingredients but experience a feeling of (33) __________ .", "happiness"),
            (34, "Online businesses track customer preferences using (34) __________ history.", "cookies"),
            (35, "This data helps improve both the customer experience and overall (35) __________ .", "sales"),
        ]

        for pos, q_text, ans_key in l_part6:
            q = Question.objects.create(
                test=test,
                section=sec_listening,
                reading_passage=p6_passage,
                position=pos,
                text=q_text,
                question_type=Question.QuestionType.INLINE_GAP_FILL,
                correct_text=ans_key,
                points=1,
                config={"part": 6, "section": "listening", "subtype": "inline_gap_fill", "gap_number": pos},
            )
            GapBlank.objects.create(question=q, position=0, answer_text=ans_key)

        # =====================================================================
        # 2. READING SECTION (35 Questions)
        # =====================================================================

        # --- Reading Part 1 (1–6) HONEY Inline Gap-Fill ---
        honey_passage = ReadingPassage.objects.create(
            test=test,
            section=sec_reading,
            order=5,
            title="HONEY",
            content=(
                "Honey is a sweet and natural food made by bees. (1) __________ collect nectar from flowers "
                "and bring it back to their hive. Inside the (2) __________ , the bees change the nectar into "
                "thick, golden honey. This process is fascinating, and many scientists study how bees work "
                "together. A group of (3) __________ recently discovered that each bee in the colony has a special "
                "job. Some bees fly out to find flowers, while others protect the hive or store the (4) __________ . "
                "To make a small jar of honey, thousands of bees must visit millions of (5) __________ . "
                "The (6) __________ they collect is carried in their tiny bodies. Once they return, they pass it from "
                "one bee to another, slowly turning it into honey."
            ),
        )

        r_part1 = [
            (1, "Honey is a sweet and natural food made by bees. (1) __________ collect nectar from flowers...", "bees"),
            (2, "Inside the (2) __________ , the bees change the nectar into thick, golden honey.", "hive"),
            (3, "A group of (3) __________ recently discovered that each bee in the colony has a special job.", "scientists"),
            (4, "Some bees fly out to find flowers, while others protect the hive or store the (4) __________ .", "honey"),
            (5, "To make a small jar of honey, thousands of bees must visit millions of (5) __________ .", "flowers"),
            (6, "The (6) __________ they collect is carried in their tiny bodies.", "nectar"),
        ]

        for pos, q_text, ans_key in r_part1:
            q = Question.objects.create(
                test=test,
                section=sec_reading,
                reading_passage=honey_passage,
                position=pos,
                text=q_text,
                question_type=Question.QuestionType.INLINE_GAP_FILL,
                correct_text=ans_key,
                points=1,
                config={"part": 1, "section": "reading", "subtype": "inline_gap_fill", "gap_number": pos},
            )
            GapBlank.objects.create(question=q, position=0, answer_text=ans_key)

        # --- Reading Part 2 (7–14) Picnic Spots Matching Statements (A–J) ---
        statements_desc = (
            "Statements A–J:\n"
            "A  A cozy spot near a fireplace, perfect for enjoying a warm drink and a good book.\n"
            "B  A unique dining experience with breathtaking city views, a cool breeze, and a touch of romance.\n"
            "C  A breathtaking experience with panoramic views, fresh mountain air, and a feeling of accomplishment.\n"
            "D  A bustling marketplace with vibrant stalls, delicious street food, and a lively atmosphere.\n"
            "E  A tranquil spot by a lake, perfect for a relaxing afternoon with loved ones.\n"
            "F  A peaceful escape surrounded by towering trees and lush greenery, offering a magical atmosphere.\n"
            "G  A casual and convenient option, ideal for a quick bite and people-watching in the city.\n"
            "H  A leisurely picnic with a scenic backdrop, featuring a flowing river and the sound of water.\n"
            "I  A tranquil escape surrounded by blooming flowers and fragrant herbs, perfect for a romantic date.\n"
            "J  A quintessential summer experience with the sound of waves crashing and the warmth of the sun."
        )

        picnic_passage = ReadingPassage.objects.create(
            test=test,
            section=sec_reading,
            order=6,
            title="PICNIC SPOTS & STATEMENTS (A–J)",
            content=statements_desc,
        )

        r_part2_items = [
            (7, "7. This picnic spot next to a quiet lake is peaceful and beautiful. You can lay out your blanket on soft grass, listen to calm waves, and enjoy the clean air. It’s the perfect place to relax and spend quality time with your loved ones.", "E"),
            (8, "8. This forest picnic area is calm and full of tall trees and greenery. Sunlight shines through the leaves, making it feel magical. You can enjoy nature’s beauty, hear birds singing, and have a quiet meal in a peaceful place.", "F"),
            (9, "9. If you want a simple and quick picnic, this park bench is perfect. Grab some snacks or a takeaway sandwich and enjoy your food while watching people and the park. It’s a nice spot in the middle of the city to rest and unwind.", "G"),
            (10, "10. A picnic on the beach gives you the full summer feeling. You can hear the waves, feel the warm sun, and smell the sea. Enjoy your food with a view of the ocean, build sandcastles, and relax under the sun.", "J"),
            (11, "11. Take your picnic to the top of a mountain for amazing views. After a good hike, enjoy the fresh mountain air and feel proud of reaching the top. It’s a perfect place for a picnic with a view you won’t forget.", "C"),
            (12, "12. Hidden in a quiet garden, this picnic spot is peaceful and surrounded by flowers and nice smells. It’s great for a calm afternoon with friends or a sweet date in a relaxing garden setting.", "I"),
            (13, "13. Have a picnic by a flowing river, sitting on soft grass. You can relax while listening to the water, watch boats pass by, and enjoy the lovely view. It’s perfect for a calm picnic in nature.", "H"),
            (14, "14. Try something different with a picnic on a rooftop. Enjoy amazing views of the city, feel the cool wind, and have a special meal. It’s great for a romantic night or celebrating a special event under the stars.", "B"),
        ]

        statements_labels = [
            ("A", "A cozy spot near a fireplace, perfect for enjoying a warm drink and a good book."),
            ("B", "A unique dining experience with breathtaking city views, a cool breeze, and a touch of romance."),
            ("C", "A breathtaking experience with panoramic views, fresh mountain air, and a feeling of accomplishment."),
            ("D", "A bustling marketplace with vibrant stalls, delicious street food, and a lively atmosphere."),
            ("E", "A tranquil spot by a lake, perfect for a relaxing afternoon with loved ones."),
            ("F", "A peaceful escape surrounded by towering trees and lush greenery, offering a magical atmosphere."),
            ("G", "A casual and convenient option, ideal for a quick bite and people-watching in the city."),
            ("H", "A leisurely picnic with a scenic backdrop, featuring a flowing river and the sound of water."),
            ("I", "A tranquil escape surrounded by blooming flowers and fragrant herbs, perfect for a romantic date."),
            ("J", "A quintessential summer experience with the sound of waves crashing and the warmth of the sun."),
        ]

        for pos, q_text, correct_letter in r_part2_items:
            q = Question.objects.create(
                test=test,
                section=sec_reading,
                reading_passage=picnic_passage,
                position=pos,
                text=q_text,
                question_type=Question.QuestionType.MATCHING,
                points=1,
                config={"part": 2, "section": "reading", "subtype": "matching_statements"},
            )
            for c_idx, (letter, desc) in enumerate(statements_labels):
                Choice.objects.create(
                    question=q,
                    text=f"{letter}   {desc}",
                    is_correct=(letter == correct_letter),
                    position=c_idx,
                )

        # --- Reading Part 3 (15–20) CANADA MUST-VISIT DESTINATIONS (Headings Matching) ---
        canada_content = (
            "15.  If you go to the Insular Mountain Range of Vancouver Island and face the open Pacific Ocean, "
            "be ready to experience the magnificent natural and cultural heritage of Canada’s west coast. If you "
            "decide to go deeper into the island, you will find a lush coastal rainforest that gives way to bountiful "
            "and diverse intertidal and subtidal areas. And to top it all off, there are breathtaking beaches that "
            "make this an island paradise.\n\n"
            "16.  The resort town of Whistler is about a two-hour drive from Vancouver. Whistler offers visitors "
            "fine food and spas, but mostly it is popular among tourists for the opportunities it offers for "
            "adventure. Whistler and Blackcomb Mountains make Whistler one of the best destinations in the "
            "world for first-class skiing. The passage between the two mountains creates a unique terrain one "
            "mile above the village, providing a year-round skiable territory.\n\n"
            "17.  A prized national treasure, Banff National Park is one of five national parks in the Canadian "
            "Rocky Mountains. It attracts millions of visitors each year for camping, hiking, biking, skiing, "
            "fishing or just relaxing. A full range of accommodation, restaurants and shops can be found in the "
            "resort. Two of the most famous and historic Canadian hotels, the Fairmont Banff Springs and the "
            "Chateau Lake Louise, are located in these towns as well.\n\n"
            "18.  Niagara Falls is maybe the most famous in the world, attracting millions of tourists each year. "
            "However, it has a certain reputation for being partly a small-scale Las Vegas and a theme park, "
            "because in addition to Niagara Falls the tourists can visit a casino resort with fine hotels and "
            "restaurants. Although this area is improving very quickly and everyone can easily find what they "
            "like, the Niagara region as a whole is worth deeper exploration.\n\n"
            "19.  Tourists are naturally drawn to tall buildings where they can get a bird’s eye view of a city. The "
            "CN Tower, located in downtown Toronto, is the tallest free-standing structure in the world. "
            "Unfortunately, elevated observation usually comes at an equally elevated price, and the CN Tower is "
            "no different. However, tourists love it, and the glass elevator takes them to the glass-floored outdoor "
            "observation deck, which is a real thrill for both kids and grown-ups.\n\n"
            "20.  The 300 km long Cabot Trail is famous for its panorama views of the Atlantic Ocean. The trail "
            "is especially popular in the fall when the views are the most spectacular. Even though the drive into "
            "this area usually takes a few hours, once there, tourists can spend a day or two stopping in at one or "
            "two of the towns along the trail, relaxing and enjoying the magnificent nature all around."
        )

        canada_passage = ReadingPassage.objects.create(
            test=test,
            section=sec_reading,
            order=7,
            title="CANADA’S MUST-VISIT TOURIST DESTINATIONS",
            content=canada_content,
        )

        headings_list = [
            ("A", "For adventurous skiers"),
            ("B", "Especially good in autumn"),
            ("C", "For the rich and lazy"),
            ("D", "Not just for gamblers"),
            ("E", "Like an island in heaven"),
            ("F", "Film-makers like it"),
            ("G", "Looking down from up there"),
            ("H", "Probably the best one of five"),
        ]

        r_part3_keys = {
            15: "E",  # Vancouver Island
            16: "A",  # Whistler
            17: "H",  # Banff
            18: "D",  # Niagara Falls
            19: "G",  # CN Tower
            20: "B",  # Cabot Trail
        }

        for pos in range(15, 21):
            correct_letter = r_part3_keys[pos]
            q = Question.objects.create(
                test=test,
                section=sec_reading,
                reading_passage=canada_passage,
                position=pos,
                text=f"Paragraph {pos}",
                question_type=Question.QuestionType.MATCHING,
                points=1,
                config={"part": 3, "section": "reading", "subtype": "headings_matching"},
            )
            for c_idx, (letter, heading_title) in enumerate(headings_list):
                Choice.objects.create(
                    question=q,
                    text=f"{letter}   {heading_title}",
                    is_correct=(letter == correct_letter),
                    position=c_idx,
                )

        # --- Reading Part 4 (21–29) A STRANGE MORNING (MCQ + True/False/No Info) ---
        strange_morning_content = (
            "Emily woke up before her alarm went off and knew instantly something wasn’t quite right in the "
            "house. Bailey, her chocolate-coloured pet Labrador, should have been there at the bedroom door "
            "demanding food, but there was no sound of him. She decided to get up and go and see where he was. "
            "It felt cold in the hall, but she knew she had left the heating on last night. As she walked down the "
            "stairs, she heard a noise in the kitchen; the strange feeling that something was wrong was getting "
            "stronger. What was going on? She got to the bottom of the stairs and opened the door to the living "
            "room, which led to the kitchen. Why was the door closed? She always left it open. Bailey was "
            "nowhere to be seen, and his toys, which were usually all over the living room floor, were in a neat "
            "pile in the corner next to his basket. Had they been there when she had gone to bed last night? She "
            "couldn’t remember.\n\n"
            "She walked into the kitchen and turned the light on; it didn’t work, nothing happened. She stood "
            "very still and listened: nothing. There wasn’t a sound. That was really strange; she lived in the "
            "middle of a busy city, and there were always people around. She woke up to the sound of traffic, car "
            "horns, police cars and her neighbours shouting in the house next door. How could there be silence at "
            "8 o’clock on a Friday morning? She went back into the living room and turned the TV on, but again "
            "nothing happened. She went back into the kitchen and looked out of the window; it was a bright, "
            "clear day. The back door was shut, but when she tried the handle, she realised it was unlocked. She "
            "walked out into the tiny back garden and opened the back gate; still nothing, not a sound and no sign "
            "of Bailey. She called him, but he didn’t come.\n\n"
            "She went back into the house and did what she realised she should have done as soon as she got up: "
            "she called her mother. But there was no answer. She called her boyfriend, but his mobile was "
            "switched off and she got the answerphone message. She tried a couple of other numbers, but with "
            "equal success. She sat down on the sofa and thought about what she could do. She couldn’t decide if "
            "she should stay at home or go out and find someone. Just as she decided the best thing would be to "
            "stay at home and wait, there was a loud banging on the front door. She jumped up and ran to the "
            "door. “Who is it?” she shouted through the door. “It’s me,” came the reply. But she had no idea who "
            "“me” was.\n\n"
            "She didn’t want to open the door until she was sure she knew who it was, not with all the other "
            "strange things that were happening this morning, and she didn’t want to shout through the thick front "
            "door, so she walked back into the living room and tried to look through the front window to see who "
            "was standing at the front door. It was a man, but she couldn’t make out who he was; he didn’t look "
            "familiar. He was tall and was wearing a big coat with a hood over his head. Just as she was thinking "
            "of running out of the back door, she saw that the man had Bailey with him, and Bailey seemed quite "
            "happy, which meant that the man had to be someone he knew and liked; he would have been barking "
            "otherwise.\n\n"
            "She still wasn’t taking any chances, though; she put the safety latch on the door and opened it just "
            "enough to see who was there. She was instantly relieved; it was her brother, who lived just a few "
            "streets away. She opened the door all the way and let him in. As he walked through the door, he was "
            "almost knocked over by Bailey jumping up and looking more pleased than ever to see her. “So, "
            "what’s going on?” she asked her brother. He looked at her as if she was stupid. “Haven’t you heard?”"
        )

        strange_passage = ReadingPassage.objects.create(
            test=test,
            section=sec_reading,
            order=8,
            title="A STRANGE MORNING",
            content=strange_morning_content,
        )

        r_part4_mcq = [
            (21, "21. What was the first thing Emily noticed that made her feel something was wrong that morning?", [
                ("A", "The living room door was wide open."),
                ("B", "Bailey wasn’t waiting outside her room asking for food."),
                ("C", "She heard loud music coming from the kitchen."),
                ("D", "The heating system wasn’t working."),
            ], "B"),
            (22, "22. Which part of the story shows that Emily was shocked by how quiet everything was?", [
                ("A", "She lives in a quiet place in the countryside."),
                ("B", "She expected it to be noisier since it was a busy Friday morning."),
                ("C", "That time of day is always quiet with no people or cars."),
                ("D", "She got up much earlier than she usually does."),
            ], "B"),
            (23, "23. How did Emily realise that the power might be out?", [
                ("A", "She tried to turn on the heat but it didn’t work."),
                ("B", "The kitchen lights wouldn’t come on."),
                ("C", "She switched on the TV but only saw static."),
                ("D", "The home phone had no signal."),
            ], "B"),
            (24, "24. What made Emily finally open the front door?", [
                ("A", "She clearly heard her brother calling her."),
                ("B", "She saw that Bailey was calmly standing beside the man."),
                ("C", "The man outside said he would break the door."),
                ("D", "She remembered someone was supposed to visit."),
            ], "B"),
        ]

        for pos, q_text, choices, correct_letter in r_part4_mcq:
            q = Question.objects.create(
                test=test,
                section=sec_reading,
                reading_passage=strange_passage,
                position=pos,
                text=q_text,
                question_type=Question.QuestionType.MULTIPLE_CHOICE,
                points=1,
                config={"part": 4, "section": "reading", "subtype": "text_mcq"},
            )
            for c_idx, (letter, label) in enumerate(choices):
                Choice.objects.create(
                    question=q,
                    text=f"{letter}   {label}",
                    is_correct=(letter == correct_letter),
                    position=c_idx,
                )

        # Questions 25–29 True / False / No Information
        tfng_questions = [
            (25, "25. Emily finds Bailey’s toys lying scattered around the living room floor.", "False"),
            (26, "26. Emily attempts several phone calls but cannot get through to anyone.", "True"),
            (27, "27. The text states that Emily’s mother left her a message on the voicemail.", "No Information"),
            (28, "28. The stranger at the door turns out to be Emily’s brother.", "True"),
            (29, "29. Emily had locked the back door before going to bed.", "No Information"),
        ]

        tfng_choices = ["True", "False", "No Information"]

        for pos, q_text, correct_tfng in tfng_questions:
            q = Question.objects.create(
                test=test,
                section=sec_reading,
                reading_passage=strange_passage,
                position=pos,
                text=q_text,
                question_type=Question.QuestionType.TRUE_FALSE_NOT_GIVEN,
                points=1,
                config={"part": 4, "section": "reading", "subtype": "tfng"},
            )
            for c_idx, choice_val in enumerate(tfng_choices):
                Choice.objects.create(
                    question=q,
                    text=choice_val,
                    is_correct=(choice_val == correct_tfng),
                    position=c_idx,
                )

        # --- Reading Part 5 (30–35) THE NOMADIC WAY OF LIFE ---
        nomad_content = (
            "Out of a world population of 7.5 billion, around 30 million people currently lead a migratory "
            "lifestyle. Every continent has nomadic groups, leading a life very different from the sedentary "
            "communities they come into contact with. Almost all migratory communities are in steady decline "
            "for a wide range of reasons: climate change, political unrest, forced resettlement and armed conflict "
            "have all impacted on these traditional communities, diminishing their numbers year on year.\n\n"
            "However, the lure of the travelling lifestyle is as strong as ever. The ‘gypsy lifestyle’ continues to "
            "inspire people – especially the young – who crave the freedom of unstructured movement. "
            "Backpacking has become almost a rite of passage for the young. ‘Gap years’ between school and "
            "university often stretch to two years, or even more, as young people become addicted to the culture "
            "of travelling light and moving on.\n\n"
            "Traditional nomads may be seen as ‘wanderers’, but their movement is not as unstructured as it may "
            "appear. Most nomadic communities are, or were, herdsmen, leading their animals across fixed "
            "routes based on pastures. Their societies were based on strong bonds of kinship. According to "
            "14th-century social historian Ibn Khaldun, the Bedouin community owed their success in battle to "
            "asabiyya or ‘group feeling’, which enhanced their ability to protect the group from outsiders. This, "
            "along with excellent horsemanship and the rigours of a harsh lifestyle, based around the constant "
            "alertness needed to protect livestock, made them formidable adversaries in war when compared to "
            "their more settled counterparts.\n\n"
            "Far from the desert-dwelling Bedouin live a different kind of nomad: the Moken, or sea gypsies, of "
            "the Mergui Archipelago between Myanmar and the islands of Thailand’s North Andaman coast. "
            "During the dry season, they live on traditional houseboats, and during the monsoon season they "
            "build temporary villages on sheltered stretches of beach. Theirs is a culture of sharing and giving, to "
            "the extent that their language contains no words for individual possessions. These indigenous people "
            "have a great understanding of and respect for their environment, making use of over 80 plant species "
            "for food and more than 100 for shelter, handicrafts and other purposes. However, the Moken’s "
            "lifestyle has more recently been affected by government restrictions on their hunter-gathering "
            "activities, and legal disputes over ownership of their traditional lands. Somewhat inevitably, they "
            "have become a focus for tourism in the area, which they have embraced to some extent as they try to "
            "adapt to the modern world.\n\n"
            "Nomadic communities exist in Europe too. In the tundras and taigas of northern Scandinavia live a "
            "reindeer-herding community, the Sami. Originally travelling freely across the areas which now "
            "belong to Norway, Sweden, Finland and Russia, this subculture has had its traditional lifestyle "
            "curtailed by the creation of national borders."
        )

        nomad_passage = ReadingPassage.objects.create(
            test=test,
            section=sec_reading,
            order=9,
            title="THE NOMADIC WAY OF LIFE",
            content=nomad_content,
        )

        r_part5_gaps = [
            (30, "Migratory lifestyles (30) __________ the youth who are eager to have unplanned travel.", "inspire"),
            (31, "Nomadic herders tend to choose their way taking (31) __________ into account.", "pastures"),
            (32, "The Bedouin community had to be cautious all the time to (32) __________ their farm animals.", "protect"),
            (33, "The Moken have no words for (33) __________ property.", "individual"),
        ]

        for pos, q_text, ans_key in r_part5_gaps:
            q = Question.objects.create(
                test=test,
                section=sec_reading,
                reading_passage=nomad_passage,
                position=pos,
                text=q_text,
                question_type=Question.QuestionType.INLINE_GAP_FILL,
                correct_text=ans_key,
                points=1,
                config={"part": 5, "section": "reading", "subtype": "inline_gap_fill", "gap_number": pos},
            )
            GapBlank.objects.create(question=q, position=0, answer_text=ans_key)

        r_part5_mcq = [
            (34, "34. According to the passage, the Moken …", [
                ("A", "hardly share their own possessions."),
                ("B", "live on the sea during the rainy season."),
                ("C", "changed their lifestyle because of restrictions."),
                ("D", "escaped to become accustomed to the modern world."),
            ], "C"),
            (35, "35. What is the writer’s purpose in the reading passage?", [
                ("A", "to explain the future of backpacking culture"),
                ("B", "to compare the success of different nomadic groups"),
                ("C", "to criticise the lack of tolerance for travelling communities"),
                ("D", "to highlight the current state of traditional travelling cultures"),
            ], "D"),
        ]

        for pos, q_text, choices, correct_letter in r_part5_mcq:
            q = Question.objects.create(
                test=test,
                section=sec_reading,
                reading_passage=nomad_passage,
                position=pos,
                text=q_text,
                question_type=Question.QuestionType.MULTIPLE_CHOICE,
                points=1,
                config={"part": 5, "section": "reading", "subtype": "text_mcq"},
            )
            for c_idx, (letter, label) in enumerate(choices):
                Choice.objects.create(
                    question=q,
                    text=f"{letter}   {label}",
                    is_correct=(letter == correct_letter),
                    position=c_idx,
                )

        # =====================================================================
        # 3. WRITING SECTION (3 Tasks)
        # =====================================================================

        # Task 1.1: Informal Email
        Question.objects.create(
            test=test,
            section=sec_writing,
            position=1,
            text=(
                "TASK 1.1 · INFORMAL EMAIL (Write about 50 words)\n\n"
                "You planned a school trip to the Science Centre to see robotic displays. "
                "However, the trip has been cancelled and rescheduled for next week.\n\n"
                "Write a short email to your friend:\n"
                "• Explain that the trip to the Science Centre has been cancelled.\n"
                "• Tell your friend that it will take place next week instead."
            ),
            question_type=Question.QuestionType.WRITTEN,
            points=5,
            config={
                "section": "writing",
                "subtype": "informal_email",
                "min_words": 40,
                "max_words": 75,
                "target_words": 50,
            },
        )

        # Task 1.2: Formal Email
        Question.objects.create(
            test=test,
            section=sec_writing,
            position=2,
            text=(
                "TASK 1.2 · FORMAL EMAIL (Write 120–150 words)\n\n"
                "Write an email to the students who registered for the trip:\n"
                "• Inform them that the trip has been cancelled for now.\n"
                "• Explain that it has been rescheduled for next week.\n"
                "• Ask them whether they want a refund or prefer to keep their place for the new date."
            ),
            question_type=Question.QuestionType.WRITTEN,
            points=10,
            config={
                "section": "writing",
                "subtype": "formal_email",
                "min_words": 110,
                "max_words": 170,
                "target_words": 140,
            },
        )

        # Task 2: Blog Post / Essay
        Question.objects.create(
            test=test,
            section=sec_writing,
            position=3,
            text=(
                "PART 2 · BLOG POST / ESSAY (Write 180–200 words)\n\n"
                "You are participating in an online discussion for language learners. The question is:\n"
                "“Some people say school trips are a waste of time, while others believe students learn more outside the classroom. "
                "What is your opinion?”\n\n"
                "Post your response, giving reasons and examples."
            ),
            question_type=Question.QuestionType.WRITTEN,
            points=15,
            config={
                "section": "writing",
                "subtype": "essay_blog",
                "min_words": 170,
                "max_words": 230,
                "target_words": 190,
            },
        )

        # =====================================================================
        # 4. SPEAKING SECTION (4 Parts)
        # =====================================================================

        speaking_parts = [
            (
                1,
                "PART 1.1 · Personal Questions (30 seconds each · No preparation)",
                (
                    "Answer the questions about yourself:\n"
                    "1. What is your favourite food?\n"
                    "2. Do you have any pets?\n"
                    "3. What do you like to do at the weekend?"
                ),
            ),
            (
                2,
                "PART 1.2 · Picture Discussion (Q1: 45 sec · Q2–Q3: 30 sec · No prep)",
                (
                    "Look at the sports pictures and answer:\n"
                    "1. What are the people in these photos doing?\n"
                    "2. What are the benefits of doing sport?\n"
                    "3. What sports are popular in your country?"
                ),
            ),
            (
                3,
                "PART 2 · Educational Experience (1 min prep · 2 min speaking)",
                (
                    "Talk about an educational experience:\n"
                    "1. Describe a significant educational experience you have had.\n"
                    "2. How has this experience shaped your career or personal development?\n"
                    "3. What do you believe are the key components of a good education?"
                ),
            ),
            (
                4,
                "PART 3 · Social Discussion & Debate (1 min prep · 2 min speaking)",
                (
                    "Discuss the statement: 'Social media has a negative impact on mental health.'\n\n"
                    "FOR:\n"
                    "• Contributes to anxiety, depression and addiction\n"
                    "• Promotes unrealistic standards and cyberbullying\n"
                    "• Distracts from real-life relationships and responsibilities\n\n"
                    "AGAINST:\n"
                    "• Increases social connectivity and awareness\n"
                    "• Provides platforms for self-expression and support\n"
                    "• Facilitates access to information and global communities"
                ),
            ),
        ]

        for pos, title, prompt_content in speaking_parts:
            Question.objects.create(
                test=test,
                section=sec_speaking,
                position=pos,
                text=f"{title}\n\n{prompt_content}",
                question_type=Question.QuestionType.SHORT_ANSWER,
                points=5,
                config={"section": "speaking", "subtype": "speaking_prompt", "part_index": pos},
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded CEFR Multi-Level Record Mock - Test 1!\n"
                f"  Test ID: {test.id}\n"
                f"  Listening: 35 questions\n"
                f"  Reading: 35 questions\n"
                f"  Writing: 3 tasks\n"
                f"  Speaking: 4 parts\n"
                f"  Total items: {test.questions.count()}"
            )
        )
