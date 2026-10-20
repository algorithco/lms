"""
Fast Mock Test Service — Ustoz uchun 1 soniyada kalitlar orqali Mock sessiya yaratish
va o'quvchilarning #MOCK-XXX kodi orqali testga ulanishi.
"""

from __future__ import annotations

import logging
import random
import re
from typing import Any

from django.db import transaction
from django.utils.text import slugify

from apps.courses.models import Course
from apps.tests.bmb_grading import calculate_bmb_grade
from apps.tests.models import Choice, Question, Test

logger = logging.getLogger(__name__)


def parse_mock_keys(key_string: str) -> dict[int, str]:
    """
    Turli formatdagi kalit matnini tahlil qiladi:
      - "1a2b3c4d5a...40b"
      - "1:a, 2:b, 3:c, 4:d"
      - "1.A 2.B 3.C"
      - "A B C D A B C D..."
      - "ABCDABCD..."
    Qaytadi: {1: 'A', 2: 'B', 3: 'C', ...}
    """
    raw = (key_string or "").strip()
    if not raw:
        return {}

    parsed: dict[int, str] = {}

    # 1. Format: 1a2b3c yoki 1:a, 2.b, 1-c
    pairs = re.findall(r"(\d+)\s*[:.\-)?]?\s*([a-eA-E])", raw)
    if pairs:
        for num_str, letter in pairs:
            num = int(num_str)
            parsed[num] = letter.upper()
        return dict(sorted(parsed.items()))

    # 2. Format: harflar ajratilgan: "A B C D" yoki "a, b, c, d"
    cleaned = re.sub(r"[,\s;]+", " ", raw).strip()
    parts = cleaned.split()
    if all(len(p) == 1 and p.upper() in "ABCDE" for p in parts):
        for idx, letter in enumerate(parts, start=1):
            parsed[idx] = letter.upper()
        return parsed

    # 3. Format: Bitta qatordagi toza harflar: "ABCDABCD..."
    only_letters = re.sub(r"[^a-eA-E]", "", raw)
    if only_letters:
        for idx, letter in enumerate(only_letters, start=1):
            parsed[idx] = letter.upper()
        return parsed

    return {}


def _get_or_create_mock_course(teacher) -> Course:
    """Mock testlar uchun o'qituvchining maxsus kursini olish yoki yaratish."""
    course = Course.objects.filter(teacher=teacher, title__icontains="Mock").first()
    if not course:
        base_slug = f"mock-tests-{teacher.id}"
        slug = base_slug
        count = 1
        while Course.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{count}"
            count += 1

        course = Course.objects.create(
            teacher=teacher,
            title="Milliy Sertifikat — Mock Testlar",
            slug=slug,
            description="Ona tili va adabiyotidan tezkor mock imtihonlar to'plami.",
            status=Course.Status.PUBLISHED,
        )
    return course


def generate_unique_mock_code() -> str:
    """Noyob #MOCK-XXX kodi yaratish."""
    for _ in range(50):
        num = random.randint(101, 999)
        code = f"#MOCK-{num}"
        if not Test.objects.filter(mock_code=code).exists():
            return code
    # Fallback agar barcha 3 xonali band bo'lsa
    rand_suffix = random.randint(1000, 9999)
    return f"#MOCK-{rand_suffix}"


@transaction.atomic
def create_quick_mock(
    teacher,
    key_string: str,
    *,
    title: str = "",
    time_limit_minutes: int = 120,
    course_id: int | None = None,
    custom_code: str | None = None,
    is_strict_mode: bool = False,
    subject: str = "uzbek",
) -> dict[str, Any]:
    """
    Bitta qatorli kalitlar orqali 1 soniyada Mock Test sessiya yaratadi.
    Masalan: "1a2b3c4d5a...40b" -> 40 ta savolli Test va #MOCK-401 kodi.
    """
    keys = parse_mock_keys(key_string)
    if not keys:
        raise ValueError(
            "Kalitlar formati noto'g'ri yoki bo'sh. Masalan: 1a2b3c4d... yoki ABCD..."
        )

    if custom_code:
        norm_code = custom_code.strip()
        if not norm_code.startswith("#"):
            norm_code = f"#{norm_code}"
        norm_code = norm_code.upper()
        if Test.objects.filter(mock_code=norm_code).exists():
            raise ValueError(
                f"'{norm_code}' kodi allaqachon mavjud. Boshqa kod tanlang."
            )
        mock_code = norm_code
    else:
        mock_code = generate_unique_mock_code()

    # Kursni aniqlash
    if course_id:
        course = Course.objects.filter(id=course_id, teacher=teacher).first()
        if not course:
            course = _get_or_create_mock_course(teacher)
    else:
        course = _get_or_create_mock_course(teacher)

    total_q = len(keys)
    test_title = (
        title.strip() if title.strip() else f"Milliy Sertifikat Mock Test ({mock_code})"
    )
    norm_subject = subject if subject in ("uzbek", "english") else "uzbek"

    test = Test.objects.create(
        course=course,
        subject=norm_subject,
        title=test_title,
        description=f"Tezkor kalitlar asosida yaratilgan {total_q} ta savolli Mock test. Kod: {mock_code}",
        mock_code=mock_code,
        time_limit_minutes=time_limit_minutes,
        pass_percentage=46,  # BMB minimal sertifikat bo'sag'asi
        max_attempts=1,
        difficulty=Test.Difficulty.MEDIUM,
        status=Test.Status.PUBLISHED,
        is_active=True,
        is_strict_mode=bool(is_strict_mode),
        show_results_immediately=True,
        shuffle_questions=False,
        shuffle_choices=False,
    )

    choice_labels = ["A", "B", "C", "D"]

    # Savollarni yaratish
    for pos, correct_letter in keys.items():
        q = Question.objects.create(
            test=test,
            text=f"{pos}-savol (Milliy Sertifikat Mock Test)",
            question_type=Question.QuestionType.SINGLE_CHOICE,
            points=1,
            position=pos,
            explanation=f"Ushbu savolning to'g'ri kaliti: {correct_letter} varianti.",
        )

        for c_pos, lbl in enumerate(choice_labels, start=1):
            Choice.objects.create(
                question=q,
                text=f"{lbl} varianti",
                is_correct=(lbl == correct_letter),
                position=c_pos,
            )

    logger.info(
        "Created quick mock test: id=%s, code=%s, questions=%s",
        test.id,
        mock_code,
        total_q,
    )

    return {
        "success": True,
        "test_id": test.id,
        "mock_code": mock_code,
        "title": test.title,
        "subject": test.subject,
        "is_strict_mode": test.is_strict_mode,
        "total_questions": total_q,
        "time_limit_minutes": test.time_limit_minutes,
        "course_id": course.id,
    }


def find_mock_by_code(code_str: str) -> Test | None:
    """Kod orqali Mock testni topish (masalan: '#MOCK-401' yoki 'MOCK-401')."""
    if not code_str:
        return None
    raw = code_str.strip().upper()
    if not raw.startswith("#"):
        raw_with_hash = f"#{raw}"
    else:
        raw_with_hash = raw

    found = (
        Test.objects.filter(mock_code__iexact=raw_with_hash, is_active=True).first()
        or Test.objects.filter(mock_code__iexact=raw, is_active=True).first()
    )
    if found:
        return found

    # Aliases backward compatibility
    if raw_with_hash in (
        "#MOCK-BMB-DIAGNOSTIC",
        "#MOCK-SHUKUROV",
        "MOCK-BMB-DIAGNOSTIC",
        "MOCK-SHUKUROV",
    ):
        return Test.objects.filter(
            mock_code__in=[
                "#MOCK-BMB-DIAGNOSTIC",
                "MOCK-BMB-DIAGNOSTIC",
                "#MOCK-SHUKUROV",
                "MOCK-SHUKUROV",
            ],
            is_active=True,
        ).first()

    return None


def get_mock_leaderboard(test_id: int) -> dict[str, Any]:
    """
    Mock test natijalari bo'yicha guruh reytingi va BMB darajalari tahlili.
    """
    from apps.results.models import Result

    test = Test.objects.filter(id=test_id).first()
    results = (
        Result.objects.filter(test_id=test_id)
        .select_related("student", "attempt")
        .order_by("-percentage", "time_taken_seconds")
    )

    ranking = []
    bmb_counts = {"A+": 0, "A": 0, "B+": 0, "B": 0, "C+": 0, "C": 0, "Fail": 0}

    for idx, r in enumerate(results, start=1):
        grade_info = calculate_bmb_grade(r.percentage)
        grade = grade_info["grade"]
        if grade in bmb_counts:
            bmb_counts[grade] += 1

        attempt = getattr(r, "attempt", None)
        cheating_detected = (
            bool(getattr(attempt, "cheating_detected", False)) if attempt else False
        )
        violation_count = (
            int(getattr(attempt, "violation_count", 0) or 0) if attempt else 0
        )

        ranking.append(
            {
                "rank": idx,
                "student_id": r.student_id,
                "student_name": r.student.get_full_name() or r.student.email,
                "score": float(r.score),
                "max_score": float(r.max_score),
                "percentage": float(r.percentage),
                "bmb_grade": grade,
                "bmb_title": grade_info["title"],
                "badge_class": grade_info["badge_class"],
                "time_taken_seconds": r.time_taken_seconds,
                "cheating_detected": cheating_detected,
                "violation_count": violation_count,
                "calculated_at": r.calculated_at.isoformat(),
            }
        )

    total_candidates = len(ranking)
    avg_score = (
        round(sum(r["percentage"] for r in ranking) / total_candidates, 1)
        if total_candidates > 0
        else 0.0
    )

    return {
        "test_id": test_id,
        "is_strict_mode": bool(test.is_strict_mode) if test else False,
        "total_participants": total_candidates,
        "average_percentage": avg_score,
        "bmb_distribution": bmb_counts,
        "ranking": ranking,
    }
