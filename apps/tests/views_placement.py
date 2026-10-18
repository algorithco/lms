"""Placement quiz, Smart Onboarding & Subject Switcher API views."""
from __future__ import annotations

import random
from decimal import Decimal
from typing import Any

from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.accounts.models import Profile
from apps.courses.models import Course, Subject
from apps.essays.models import EssayTopic
from apps.tests.models import Choice, ExamSection, GapBlank, Question, ReadingPassage, Test

User = get_user_model()


def ensure_multi_subject_seed_data() -> None:
    """Idempotently seed Subject rows and default English (IELTS & Multi-level) content."""
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
            "description": "IELTS Academic/General Writing (Band 1.0–9.0), Listening & Reading CBT Simulator",
            "icon": "🇬🇧",
            "is_active": True,
            "position": 2,
        },
    )

    # Seed English Essay Topics if none exist
    if not EssayTopic.objects.filter(subject="english", is_active=True).exists():
        EssayTopic.objects.create(
            subject="english",
            rubric_type=EssayTopic.RubricType.IELTS_TASK2,
            category=EssayTopic.Category.IELTS_TASK2,
            title="IELTS Writing Task 2 — Artificial Intelligence in Modern Education",
            description=(
                "Some people believe that artificial intelligence and online learning platforms will "
                "completely replace traditional classroom teachers in the near future, while others "
                "argue that human teachers remain essential for student development.\n\n"
                "Discuss both these views and give your own opinion.\n"
                "Give reasons for your answer and include any relevant examples from your own knowledge or experience.\n"
                "Write at least 250 words."
            ),
            word_limit_min=250,
            word_limit_max=500,
            time_limit_minutes=40,
            sample_outline=(
                "1. Introduction: Paraphrase the prompt and state your thesis clearly.\n"
                "2. Body Paragraph 1: Why some believe AI/online platforms can replace teachers (scalability, instant feedback).\n"
                "3. Body Paragraph 2: Why human teachers are irreplaceable (empathy, mentorship, critical thinking).\n"
                "4. Conclusion: Summarize main points and restate your balanced opinion."
            ),
            is_active=True,
        )
        EssayTopic.objects.create(
            subject="english",
            rubric_type=EssayTopic.RubricType.IELTS_TASK1,
            category=EssayTopic.Category.IELTS_TASK1,
            title="IELTS Academic Writing Task 1 — Global Renewable Energy Production",
            description=(
                "The table and chart below show the percentage of total electricity generated from "
                "renewable energy sources (solar, wind, and hydro) across four countries between 2010 and 2025.\n\n"
                "Summarise the information by selecting and reporting the main features, and make comparisons where relevant.\n"
                "Write at least 150 words."
            ),
            word_limit_min=150,
            word_limit_max=350,
            time_limit_minutes=20,
            sample_outline=(
                "1. Introduction: Paraphrase what the chart/table illustrates.\n"
                "2. Overview: Identify the 2–3 most noticeable overall trends (highest growth, consistent leader).\n"
                "3. Specific Details 1: Compare countries with rapid increases from 2010 to 2025.\n"
                "4. Specific Details 2: Contrast remaining figures and key data points."
            ),
            is_active=True,
        )
        EssayTopic.objects.create(
            subject="english",
            rubric_type=EssayTopic.RubricType.IELTS_TASK2,
            category=EssayTopic.Category.MULTILEVEL,
            title="Multi-level (CEFR B2/C1) Essay — Remote Work and Urban Living",
            description=(
                "In many countries, a growing number of professionals are choosing to work remotely from home "
                "rather than commuting to city offices every day.\n\n"
                "Do the advantages of this development outweigh the disadvantages for individuals and society?\n"
                "Write at least 250 words."
            ),
            word_limit_min=250,
            word_limit_max=500,
            time_limit_minutes=40,
            is_active=True,
        )

    # Seed English CBT Test (Listening & Reading) if none exist
    if not Test.objects.filter(subject="english", status=Test.Status.PUBLISHED).exists():
        teacher = User.objects.filter(role__in=["teacher", "admin"]).first() or User.objects.first()
        if teacher:
            course, _ = Course.objects.get_or_create(
                slug="ielts-multilevel-cbt-mastery",
                defaults={
                    "teacher": teacher,
                    "subject": "english",
                    "title": "IELTS & Multi-level English Mastery",
                    "description": "Official IELTS Academic Reading, Listening & Writing CBT practice course.",
                    "status": Course.Status.PUBLISHED,
                },
            )
            test = Test.objects.create(
                subject="english",
                course=course,
                title="IELTS Academic Reading & Listening — Official CBT Mock Test",
                description=(
                    "Full IELTS Computer-Based Test (CBT) simulator featuring Listening audio playback "
                    "and split-screen Academic Reading (True/False/Not Given, Matching Headings, and Gap Fill)."
                ),
                time_limit_minutes=60,
                max_attempts=0,
                pass_percentage=60,
                difficulty=Test.Difficulty.MEDIUM,
                status=Test.Status.PUBLISHED,
                shuffle_questions=False,
                shuffle_choices=False,
                mock_code="IELTS-CBT-01",
                audio_url="https://actions.google.com/sounds/v1/ambiences/coffee_shop.ogg",
            )
            listening_sec = ExamSection.objects.create(
                test=test,
                name="Part 1: Listening Comprehension",
                code=ExamSection.LISTENING,
                audio_url="https://actions.google.com/sounds/v1/ambiences/coffee_shop.ogg",
                order=1,
                duration_minutes=20,
            )
            reading_sec = ExamSection.objects.create(
                test=test,
                name="Part 2: Academic Reading Passage",
                code=ExamSection.READING,
                order=2,
                duration_minutes=40,
            )
            passage = ReadingPassage.objects.create(
                test=test,
                section=reading_sec,
                title="The Rise of Sustainable Urban Architecture",
                content=(
                    "[Paragraph A]\n"
                    "Over the past two decades, urban planners and architects have increasingly turned to "
                    "biophilic design—an approach that integrates natural ecosystems directly into high-density "
                    "metropolitan buildings. Early pioneers in Singapore and Milan demonstrated that vertical "
                    "forests not only absorb significant amounts of carbon dioxide but also reduce ambient "
                    "building temperatures by up to 3.5 degrees Celsius during peak summer months.\n\n"
                    "[Paragraph B]\n"
                    "Despite initial skepticism regarding structural maintenance costs, long-term empirical studies "
                    "conducted by the European Urban Institute between 2018 and 2024 revealed that green-certified "
                    "commercial towers consumed 28% less energy for air conditioning than conventional glass skyscrapers. "
                    "However, the researchers noted that water irrigation efficiency remains a critical challenge in arid climates.\n\n"
                    "[Paragraph C]\n"
                    "Looking ahead, next-generation timber-hybrid structures and photovoltaic glass facades are expected "
                    "to transform city skylines from passive energy consumers into self-sustaining micro-power stations."
                ),
                source="IELTS Academic Reading Collection",
                order=1,
            )

            q1 = Question.objects.create(
                test=test,
                section=reading_sec,
                reading_passage=passage,
                text="[TRUE / FALSE / NOT GIVEN] Biophilic buildings in Singapore and Milan were able to lower surrounding building temperatures by up to 3.5°C in summer.",
                question_type=Question.QuestionType.SINGLE_CHOICE,
                points=1,
                explanation="Paragraph A explicitly states that vertical forests in Singapore and Milan reduce ambient building temperatures by up to 3.5 degrees Celsius during peak summer months.",
                position=1,
            )
            Choice.objects.create(question=q1, text="TRUE", is_correct=True, position=1)
            Choice.objects.create(question=q1, text="FALSE", is_correct=False, position=2)
            Choice.objects.create(question=q1, text="NOT GIVEN", is_correct=False, position=3)

            q2 = Question.objects.create(
                test=test,
                section=reading_sec,
                reading_passage=passage,
                text="[TRUE / FALSE / NOT GIVEN] The European Urban Institute found that green-certified towers are more expensive to insure than traditional glass skyscrapers.",
                question_type=Question.QuestionType.SINGLE_CHOICE,
                points=1,
                explanation="Paragraph B mentions maintenance costs and energy savings (28% less), but insurance costs are never mentioned in the passage (NOT GIVEN).",
                position=2,
            )
            Choice.objects.create(question=q2, text="TRUE", is_correct=False, position=1)
            Choice.objects.create(question=q2, text="FALSE", is_correct=False, position=2)
            Choice.objects.create(question=q2, text="NOT GIVEN", is_correct=True, position=3)

            q3 = Question.objects.create(
                test=test,
                section=reading_sec,
                reading_passage=passage,
                text="[Matching Headings] Choose the most suitable heading for Paragraph B:",
                question_type=Question.QuestionType.SINGLE_CHOICE,
                points=1,
                explanation="Paragraph B focuses on empirical data showing 28% energy savings alongside the ongoing challenge of water irrigation in dry regions.",
                position=3,
            )
            Choice.objects.create(question=q3, text="i. Historical origins of glass skyscrapers", is_correct=False, position=1)
            Choice.objects.create(question=q3, text="ii. Measured energy savings and climate-specific limitations", is_correct=True, position=2)
            Choice.objects.create(question=q3, text="iii. Government subsidies for residential housing", is_correct=False, position=3)
            Choice.objects.create(question=q3, text="iv. Complete elimination of urban carbon emissions", is_correct=False, position=4)

            q4 = Question.objects.create(
                test=test,
                section=reading_sec,
                reading_passage=passage,
                text="[Fill in the Gap] Complete the sentence using NO MORE THAN TWO WORDS from Paragraph C: Next-generation buildings will use timber-hybrid structures and ___ facades to generate power.",
                question_type=Question.QuestionType.GAP_FILL,
                correct_text="photovoltaic glass",
                points=1,
                explanation="Paragraph C states: 'next-generation timber-hybrid structures and photovoltaic glass facades are expected to transform city skylines...'",
                position=4,
            )
            GapBlank.objects.create(question=q4, position=0, answer_text="photovoltaic glass")

            q5 = Question.objects.create(
                test=test,
                section=listening_sec,
                reading_passage=passage,
                text="[Listening & Vocabulary] According to Paragraph B, by what percentage did green-certified commercial towers reduce air conditioning energy consumption?",
                question_type=Question.QuestionType.SINGLE_CHOICE,
                points=1,
                explanation="Paragraph B reports that green-certified commercial towers consumed 28% less energy for air conditioning.",
                position=5,
            )
            Choice.objects.create(question=q5, text="15%", is_correct=False, position=1)
            Choice.objects.create(question=q5, text="28%", is_correct=True, position=2)
            Choice.objects.create(question=q5, text="35%", is_correct=False, position=3)
            Choice.objects.create(question=q5, text="50%", is_correct=False, position=4)


def _resolve_placement_questions(target: str, count: int = 5, subject: str = "uzbek") -> list[Question]:
    """Pick exactly `count` random single-choice questions tailored to the exam target and subject."""
    ensure_multi_subject_seed_data()
    target_clean = (target or "").strip().lower()
    subject_clean = (subject or "uzbek").strip().lower()
    if target_clean in ("ielts", "multilevel"):
        subject_clean = "english"

    base_qs = Question.objects.filter(
        question_type=Question.QuestionType.SINGLE_CHOICE,
        choices__isnull=False,
    ).distinct()

    if subject_clean == "english":
        target_qs = base_qs.filter(test__subject="english")
    elif target_clean == "attestation":
        target_qs = base_qs.filter(
            test__subject="uzbek",
        ).filter(
            Q(test__title__icontains="Attestat")
            | Q(test__mock_code__icontains="ATTEST")
            | Q(test__description__icontains="Attestat")
        )
    else:  # national_certificate default
        target_qs = base_qs.filter(
            test__subject="uzbek",
        ).filter(
            Q(test__title__icontains="Milliy")
            | Q(test__title__icontains="BMB")
            | Q(test__mock_code__icontains="BMB")
            | Q(test__title__icontains="Mock")
        )

    questions = list(target_qs.order_by("?")[:count])

    if len(questions) < count:
        existing_ids = [q.id for q in questions]
        fallback_qs = (
            base_qs.filter(test__subject=subject_clean, test__status=Test.Status.PUBLISHED)
            .exclude(id__in=existing_ids)
            .order_by("?")[: count - len(questions)]
        )
        questions.extend(list(fallback_qs))

    if len(questions) < count:
        existing_ids = [q.id for q in questions]
        any_qs = (
            base_qs.exclude(id__in=existing_ids)
            .order_by("?")[: count - len(questions)]
        )
        questions.extend(list(any_qs))

    return questions[:count]


def _build_daily_plan(
    target: str,
    timeline_months: int,
    target_grade: str,
    score: int,
    subject: str = "uzbek",
) -> dict[str, Any]:
    """Generate personalized AI daily study plan based on user goals, subject, and placement score."""
    months = 3 if timeline_months not in (1, 3, 6) else timeline_months
    subject_clean = "english" if (subject == "english" or target in ("ielts", "multilevel")) else "uzbek"
    is_attestation = target == "attestation"

    if months == 1:
        tests_per_day = 2
        essays_per_week = 3
        daily_minutes = 90
        schedule_label = "Intensiv Sprint (1 oylik shoshilinch reja)"
        pace = "Har kuni 2 ta test yechish va haftasiga 3 ta yozma ish (Writing/Esse) yozish talab etiladi."
    elif months == 6:
        tests_per_day = 1
        essays_per_week = 1
        daily_minutes = 30
        schedule_label = "Keng qamrovli tayyorgarlik (6 oylik chuqurlashtirilgan)"
        pace = "Kun oralatib 1 ta test yechish va haftasiga 1 ta yozma ish yozish yetarli."
    else:  # 3 months
        tests_per_day = 1
        essays_per_week = 2
        daily_minutes = 45
        schedule_label = "Optimal muvozanatli reja (3 oylik standart)"
        pace = "Kuniga 1 ta test yechish va haftasiga 2 ta yozma ish yozish tavsiya etiladi."

    if subject_clean == "english":
        focus_areas = [
            "IELTS Academic Reading (True/False/Not Given & Headings)",
            "Listening Comprehension & Audio Note-taking",
            "Writing Task 1 (150+ words) & Task 2 Essay (250+ words) — 4 Criteria",
        ]
        recommended_actions = [
            {"title": "IELTS Academic Reading & Listening CBT", "badge": "Full Simulator", "link": "/tests"},
            {"title": "IELTS Writing Task 1 & Task 2 AI Grader", "badge": "Band 1.0–9.0", "link": "/essays"},
            {"title": "1v1 English Vocabulary & Grammar Arena", "badge": "Live Duel", "link": "/arena"},
        ]
    elif is_attestation:
        focus_areas = [
            "Ona tili va adabiyot metodikasi",
            "Matn ustida ishlash va tahlil",
            "Attestatsiya test strategiyalari (50 ta savol)",
        ]
        recommended_actions = [
            {"title": "Rasmiy Attestatsiya Diagnostika 2026", "badge": "50 ta savol", "link": "/tests"},
            {"title": "Guruhlar va o'quvchilar nazorati", "badge": "Pedagogik kabinet", "link": "/groups"},
        ]
    else:
        focus_areas = [
            "Morfologiya va imlo qoidalari",
            "Badiiy matn tahlili va lug'at",
            "BMB 12 mezonli esse yozish mahorati",
        ]
        recommended_actions = [
            {"title": "BMB Rasmiy Mock Test", "badge": "3 soatlik to'liq CBT", "link": "/tests"},
            {"title": "12 mezonli BMB Esse amaliyoti", "badge": "20 ballik AI tahlil", "link": "/essays"},
            {"title": "1v1 Bilimlar Arenasi", "badge": "Tezkor duel", "link": "/arena"},
        ]

    advice = (
        f"Boshlang'ich ko'rsatkichingiz 5 tadan {score} ball. "
        f"{pace} Sizning {target_grade} maqsadiga yetishingiz uchun barcha materiallar shaxsiy profilingizga moslashtirildi."
    )

    return {
        "subject": subject_clean,
        "schedule_label": schedule_label,
        "tests_per_day": tests_per_day,
        "essays_per_week": essays_per_week,
        "daily_minutes": daily_minutes,
        "focus_areas": focus_areas,
        "recommended_actions": recommended_actions,
        "advice": advice,
    }


def _calculate_initial_level(target: str, score: int, subject: str = "uzbek") -> str:
    """Return friendly initial placement level name."""
    if subject == "english" or target in ("ielts", "multilevel"):
        if score >= 5:
            return "Band 7.5–8.0 (C1 Advanced)"
        if score == 4:
            return "Band 6.5–7.0 (B2+ Upper-Intermediate)"
        if score == 3:
            return "Band 5.5–6.0 (B2 Intermediate)"
        if score == 2:
            return "Band 5.0 (B1 Pre-Intermediate)"
        return "Band 4.0–4.5 (A2 Foundation)"
    if target == "attestation":
        if score >= 5:
            return "Oliy toifa (Yetakchi pedagog)"
        if score == 4:
            return "1-toifa (Katta o'qituvchi)"
        if score == 3:
            return "2-toifa (Yetuk mutaxassis)"
        return "Mutaxassis (Boshlang'ich daraja)"
    # national_certificate
    if score >= 5:
        return "A+ (A'lo daraja)"
    if score == 4:
        return "A (Juda yaxshi daraja)"
    if score == 3:
        return "B+ (Yaxshi daraja)"
    if score == 2:
        return "B (Qoniqarli daraja)"
    return "C (Boshlang'ich daraja)"


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def placement_quiz_view(request):
    """GET /api/v1/tests/placement-quiz/?target=national_certificate|attestation|ielts&subject=uzbek|english

    Returns exactly 5 random single-choice questions for 5-minute placement testing.
    """
    target = request.query_params.get("target", "national_certificate").strip()
    subject = request.query_params.get("subject", "").strip().lower()
    if not subject and request.user and request.user.is_authenticated:
        profile, _ = Profile.objects.get_or_create(user=request.user)
        subject = profile.active_subject or "uzbek"
    if not subject:
        subject = "english" if target in ("ielts", "multilevel") else "uzbek"

    questions = _resolve_placement_questions(target, count=5, subject=subject)

    data = []
    for q in questions:
        choices = []
        for c in q.choices.all():
            choices.append({
                "id": c.id,
                "text": c.text,
            })
        random.shuffle(choices)

        passage_text = q.passage or (q.reading_passage.content if q.reading_passage else "")
        data.append({
            "id": q.id,
            "text": q.text,
            "passage": passage_text,
            "choices": choices,
        })

    return Response({
        "ok": True,
        "subject": subject,
        "target": target,
        "time_limit_seconds": 300,
        "total_questions": len(data),
        "questions": data,
    })


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def placement_quiz_submit_view(request):
    """POST /api/v1/tests/placement-quiz/submit/"""
    data = request.data or {}
    subject = (data.get("subject") or "").strip().lower()
    target = (data.get("target") or "national_certificate").strip().lower()
    if target not in ("national_certificate", "attestation", "ielts", "multilevel"):
        target = "ielts" if subject == "english" else "national_certificate"
    if subject not in ("uzbek", "english"):
        subject = "english" if target in ("ielts", "multilevel") else "uzbek"

    try:
        timeline_months = int(data.get("target_timeline_months", 3))
    except (ValueError, TypeError):
        timeline_months = 3
    if timeline_months not in (1, 3, 6):
        timeline_months = 3

    default_grade = "Band 7.5+" if subject == "english" else ("Oliy toifa" if target == "attestation" else "A+")
    target_grade = (data.get("target_grade") or default_grade).strip()
    answers = data.get("answers") or []

    correct_count = 0
    total_answered = 0

    for item in answers:
        if not isinstance(item, dict):
            continue
        qid = item.get("question_id")
        cid = item.get("selected_choice_id")
        if not qid:
            continue
        total_answered += 1
        if cid and Choice.objects.filter(id=cid, question_id=qid, is_correct=True).exists():
            correct_count += 1

    total_questions = max(len(answers), 5)
    percentage = round((correct_count / total_questions) * 100, 1)
    initial_level = _calculate_initial_level(target, correct_count, subject=subject)
    daily_plan = _build_daily_plan(target, timeline_months, target_grade, correct_count, subject=subject)

    # Persist to User Profile
    user = request.user
    profile, _ = Profile.objects.get_or_create(user=user)
    profile.active_subject = subject
    profile.exam_target = target
    profile.target_timeline_months = timeline_months
    profile.target_grade = target_grade
    profile.placement_score = Decimal(str(correct_count))
    profile.onboarding_completed = True
    profile.daily_plan_summary = daily_plan
    profile.save(update_fields=[
        "active_subject",
        "exam_target",
        "target_timeline_months",
        "target_grade",
        "placement_score",
        "onboarding_completed",
        "daily_plan_summary",
    ])

    return Response({
        "ok": True,
        "subject": subject,
        "score": correct_count,
        "total": total_questions,
        "percentage": percentage,
        "initial_level": initial_level,
        "target": target,
        "target_timeline_months": timeline_months,
        "target_grade": target_grade,
        "daily_plan": daily_plan,
        "onboarding_completed": True,
        "message": "Onboarding va placement test muvaffaqiyatli yakunlandi!",
    }, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def subjects_list_view(request):
    """GET /api/v1/subjects/ — list available subjects and active subject."""
    ensure_multi_subject_seed_data()
    subjects = Subject.objects.filter(is_active=True).order_by("position", "id")
    active_subject = "uzbek"
    if request.user and request.user.is_authenticated:
        profile, _ = Profile.objects.get_or_create(user=request.user)
        active_subject = profile.active_subject or "uzbek"
    return Response({
        "active_subject": active_subject,
        "subjects": [
            {
                "id": s.id,
                "slug": s.slug,
                "name": s.name,
                "description": s.description,
                "icon": s.icon,
            }
            for s in subjects
        ],
    })


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def switch_subject_view(request):
    """POST /api/v1/profile/switch-subject/
    Payload: { "subject": "uzbek" | "english" }
    """
    ensure_multi_subject_seed_data()
    subject = str((request.data or {}).get("subject") or "").strip().lower()
    if subject not in ("uzbek", "english"):
        return Response(
            {"error": "Fan noto'g'ri tanlandi. Faqat 'uzbek' yoki 'english' bo'lishi mumkin."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    profile, _ = Profile.objects.get_or_create(user=request.user)
    profile.active_subject = subject

    # Keep daily_plan_summary aligned with the selected subject
    score_int = int(profile.placement_score) if profile.placement_score is not None else 4
    target = "ielts" if subject == "english" else (
        profile.exam_target if profile.exam_target in ("national_certificate", "attestation") else "national_certificate"
    )
    target_grade = profile.target_grade or ("Band 7.5+" if subject == "english" else "A+")
    if subject == "english" and target_grade in ("A+", "A", "B+", "Oliy toifa", "1-toifa"):
        target_grade = "Band 7.5+"
    elif subject == "uzbek" and target_grade.startswith("Band"):
        target_grade = "A+"

    profile.daily_plan_summary = _build_daily_plan(
        target=target,
        timeline_months=profile.target_timeline_months or 3,
        target_grade=target_grade,
        score=score_int,
        subject=subject,
    )
    profile.save(update_fields=["active_subject", "daily_plan_summary"])

    return Response({
        "ok": True,
        "active_subject": profile.active_subject,
        "daily_plan_summary": profile.daily_plan_summary,
        "message": (
            "Ingliz tili (IELTS & Multi-level) yo'nalishiga o'tildi!"
            if subject == "english"
            else "Ona tili va adabiyot yo'nalishiga o'tildi!"
        ),
    })
