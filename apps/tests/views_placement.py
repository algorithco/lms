"""Placement quiz & Smart Onboarding API views."""
from __future__ import annotations

import random
from decimal import Decimal
from typing import Any

from django.db.models import Q
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.accounts.models import Profile
from apps.tests.models import Choice, Question, Test


def _resolve_placement_questions(target: str, count: int = 5) -> list[Question]:
    """Pick exactly `count` random single-choice questions tailored to the exam target."""
    target_clean = (target or "").strip().lower()

    base_qs = Question.objects.filter(
        question_type=Question.QuestionType.SINGLE_CHOICE,
        choices__isnull=False,
    ).distinct()

    if target_clean == "attestation":
        target_qs = base_qs.filter(
            Q(test__title__icontains="Attestat")
            | Q(test__mock_code__icontains="ATTEST")
            | Q(test__description__icontains="Attestat")
        )
    else:  # national_certificate default
        target_qs = base_qs.filter(
            Q(test__title__icontains="Milliy")
            | Q(test__title__icontains="BMB")
            | Q(test__mock_code__icontains="BMB")
            | Q(test__title__icontains="Mock")
        )

    questions = list(target_qs.order_by("?")[:count])

    if len(questions) < count:
        existing_ids = [q.id for q in questions]
        fallback_qs = (
            base_qs.filter(test__status=Test.Status.PUBLISHED)
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


def _build_daily_plan(target: str, timeline_months: int, target_grade: str, score: int) -> dict[str, Any]:
    """Generate personalized AI daily study plan based on user goals and placement score."""
    months = 3 if timeline_months not in (1, 3, 6) else timeline_months
    is_attestation = target == "attestation"

    if months == 1:
        tests_per_day = 2
        essays_per_week = 3
        daily_minutes = 90
        schedule_label = "Intensiv Sprint (1 oylik shoshilinch reja)"
        pace = "Har kuni 2 ta test yechish va haftasiga 3 ta esse yozish talab etiladi."
    elif months == 6:
        tests_per_day = 1
        essays_per_week = 1
        daily_minutes = 30
        schedule_label = "Keng qamrovli tayyorgarlik (6 oylik chuqurlashtirilgan)"
        pace = "Kun oralatib 1 ta test yechish va haftasiga 1 ta esse yozish yetarli."
    else:  # 3 months
        tests_per_day = 1
        essays_per_week = 2
        daily_minutes = 45
        schedule_label = "Optimal muvozanatli reja (3 oylik standart)"
        pace = "Kuniga 1 ta test yechish va haftasiga 2 ta esse yozish tavsiya etiladi."

    if is_attestation:
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
        "schedule_label": schedule_label,
        "tests_per_day": tests_per_day,
        "essays_per_week": essays_per_week,
        "daily_minutes": daily_minutes,
        "focus_areas": focus_areas,
        "recommended_actions": recommended_actions,
        "advice": advice,
    }


def _calculate_initial_level(target: str, score: int) -> str:
    """Return friendly initial placement level name."""
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
    """GET /api/v1/tests/placement-quiz/?target=national_certificate|attestation

    Returns exactly 5 random single-choice questions for 5-minute placement testing.
    """
    target = request.query_params.get("target", "national_certificate").strip()
    questions = _resolve_placement_questions(target, count=5)

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
        "target": target,
        "time_limit_seconds": 300,
        "total_questions": len(data),
        "questions": data,
    })


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def placement_quiz_submit_view(request):
    """POST /api/v1/tests/placement-quiz/submit/

    Payload:
    {
        "target": "national_certificate" | "attestation",
        "target_timeline_months": 3,
        "target_grade": "A+",
        "answers": [
            {"question_id": 101, "selected_choice_id": 202},
            ...
        ]
    }
    """
    data = request.data or {}
    target = (data.get("target") or "national_certificate").strip().lower()
    if target not in ("national_certificate", "attestation"):
        target = "national_certificate"

    try:
        timeline_months = int(data.get("target_timeline_months", 3))
    except (ValueError, TypeError):
        timeline_months = 3
    if timeline_months not in (1, 3, 6):
        timeline_months = 3

    target_grade = (data.get("target_grade") or ("Oliy toifa" if target == "attestation" else "A+")).strip()
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
    initial_level = _calculate_initial_level(target, correct_count)
    daily_plan = _build_daily_plan(target, timeline_months, target_grade, correct_count)

    # Persist to User Profile
    user = request.user
    profile, _ = Profile.objects.get_or_create(user=user)
    profile.exam_target = target
    profile.target_timeline_months = timeline_months
    profile.target_grade = target_grade
    profile.placement_score = Decimal(str(correct_count))
    profile.onboarding_completed = True
    profile.daily_plan_summary = daily_plan
    profile.save(update_fields=[
        "exam_target",
        "target_timeline_months",
        "target_grade",
        "placement_score",
        "onboarding_completed",
        "daily_plan_summary",
    ])

    return Response({
        "ok": True,
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
