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

    # Subject seeding completed (user/teachers create their own tests and essays)
    return


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
    """GET /api/v1/tests/placement-quiz/?target=national_certificate|attestation|ielts|multilevel&subject=uzbek|english

    Returns exactly 5 random single-choice questions for 5-minute placement testing.
    """
    target = "national_certificate"
    subject = "uzbek"
    try:
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

            passage_text = getattr(q, "passage", "") or (q.reading_passage.content if getattr(q, "reading_passage", None) else "")
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
    except Exception:
        return Response({
            "ok": True,
            "subject": subject,
            "target": target,
            "time_limit_seconds": 300,
            "total_questions": 0,
            "questions": [],
        }, status=status.HTTP_200_OK)


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
    Payload: { "subject": "uzbek" | "english", "exam_target"?: str }
    """
    try:
        ensure_multi_subject_seed_data()
        data = request.data or {}
        subject = str(data.get("subject") or "").strip().lower()
        if subject not in ("uzbek", "english"):
            return Response(
                {"error": "Fan noto'g'ri tanlandi. Faqat 'uzbek' yoki 'english' bo'lishi mumkin."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile, _ = Profile.objects.get_or_create(user=request.user)
        profile.active_subject = subject

        # Resolve exam_target strictly based on subject
        requested_target = str(data.get("exam_target") or "").strip().lower()
        if subject == "english":
            if requested_target in ("ielts", "multilevel"):
                target = requested_target
            elif profile.exam_target in ("ielts", "multilevel"):
                target = profile.exam_target
            else:
                target = "ielts"
            default_grade = "Band 7.5"
        else:  # uzbek
            if requested_target in ("national_certificate", "attestation"):
                target = requested_target
            elif profile.exam_target in ("national_certificate", "attestation"):
                target = profile.exam_target
            else:
                target = "national_certificate"
            default_grade = "Oliy toifa" if target == "attestation" else "A+"

        profile.exam_target = target

        # Resolve target grade
        target_grade = profile.target_grade or default_grade
        if subject == "english" and target_grade in ("A+", "A", "B+", "Oliy toifa", "1-toifa"):
            target_grade = "Band 7.5"
        elif subject == "uzbek" and (target_grade.startswith("Band") or "daraja" in target_grade.lower()):
            target_grade = default_grade

        profile.target_grade = target_grade

        # Keep daily_plan_summary aligned with the selected subject & target
        score_int = int(profile.placement_score) if profile.placement_score is not None else 4
        profile.daily_plan_summary = _build_daily_plan(
            target=target,
            timeline_months=profile.target_timeline_months or 3,
            target_grade=target_grade,
            score=score_int,
            subject=subject,
        )
        profile.save(update_fields=["active_subject", "exam_target", "target_grade", "daily_plan_summary"])

        return Response({
            "ok": True,
            "active_subject": profile.active_subject,
            "exam_target": profile.exam_target,
            "target_grade": profile.target_grade,
            "daily_plan_summary": profile.daily_plan_summary,
            "message": (
                "Ingliz tili (IELTS & Multi-level) yo'nalishiga o'tildi!"
                if subject == "english"
                else "Ona tili va adabiyot yo'nalishiga o'tildi!"
            ),
        }, status=status.HTTP_200_OK)
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Error in switch_subject_view: %s", e)
        return Response({
            "ok": False,
            "error": "Fan yo'nalishini o'zgartirishda server xatoligi yuz berdi.",
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
