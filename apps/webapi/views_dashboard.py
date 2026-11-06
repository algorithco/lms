"""Student dashboard: one call, real data only, scoped to the chosen subject.

GET /api/v1/dashboard/?subject=uzbek|english

Nothing here is invented: with no attempts every list is empty and every
indicator is ``null``/0, and the client shows an empty state with the next
step. English and Uzbek content never mix: results, indicators, weak parts and
the goal are all filtered by the subject of the test they came from.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from django.db.models import Q
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.results.models import Result
from apps.tests import cefr_multilevel
from apps.tests.models import Question, StudentAnswer, Test, TestAttempt
from apps.tests.numbering import NOT_OBJECTIVE

SUBJECTS = ("uzbek", "english", "biology", "chemistry", "law")
FINISHED = (TestAttempt.Status.COMPLETED, TestAttempt.Status.PENDING_GRADING, TestAttempt.Status.TIMEOUT)
BMB_GRADE_ORDER = ["Fail", "C", "C+", "B", "B+", "A", "A+"]
CEFR_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]
GOAL_SUBJECT = {
    "national_certificate": "uzbek",
    "milliy_sertifikat": "uzbek",
    "ona_tili": "uzbek",
    "attestation": "uzbek",
    "attestatsiya": "uzbek",
    "ielts": "english",
    "multilevel": "english",
    "cefr": "english",
    "biology": "biology",
    "dtm_biology": "biology",
    "chemistry": "chemistry",
    "dtm_chemistry": "chemistry",
    "law": "law",
    "yurisprudensiya": "law",
}
RECENT = 3
WEAK_PARTS = 3
WEAK_MIN_TOTAL = 3
WEAK_ATTEMPTS = 10


def test_kind(test: Test) -> str:
    """cefr | ielts | attestation | bmb | general — decides which labels and scales apply."""
    if test.exam_type == Test.ExamType.CEFR_MULTILEVEL:
        return "cefr"
    if str(test.exam_type).startswith("ielts"):
        return "ielts"
    if (test.mock_code or "").lstrip("#").upper().startswith("MOCK-ATTEST"):
        return "attestation"
    return "bmb" if test.subject == "uzbek" else "general"


def _sections_of(result: Result, kind: str) -> list[dict[str, Any]]:
    """Per-section score for a result: 0–75 for CEFR, earned/max otherwise."""
    attempt = result.attempt
    if kind == "cefr" and not attempt.trial_part_id:
        summary = cefr_multilevel.to_json(cefr_multilevel.summarize(attempt.section_scores or {}))
        return [
            {"code": s["code"], "name": s["name"], "score": s["score"], "max": summary["scale_max"], "level": s["level"]}
            for s in summary["sections"]
            if s["status"] == "scored" and s["score"] is not None
        ]
    return [
        {"code": s.section_code, "name": s.section_name, "score": float(s.earned), "max": float(s.maximum), "level": None}
        for s in result.section_scores.all()
        if float(s.maximum) > 0
    ]


def _recent(results: list[Result]) -> list[dict[str, Any]]:
    out = []
    for r in results[:RECENT]:
        kind = test_kind(r.test)
        trial = bool(r.attempt.trial_part_id)
        out.append(
            {
                "result_id": r.id,
                "test_id": r.test_id,
                "title": r.test.title,
                "kind": kind,
                "trial": trial,
                "finished_at": r.calculated_at.isoformat() if r.calculated_at else None,
                "percentage": float(r.percentage),
                "correct": r.correct_answers,
                "total": r.total_questions,
                "grade": r.bmb_grade if kind == "bmb" else "",
                "sections": [] if trial else _sections_of(r, kind),
            }
        )
    return out


def _best_grade(results: list[Result]) -> str | None:
    grades = [r.bmb_grade for r in results if test_kind(r.test) == "bmb" and r.bmb_grade]
    grades = [g for g in grades if g in BMB_GRADE_ORDER]
    return max(grades, key=BMB_GRADE_ORDER.index) if grades else None


def _best_cefr(results: list[Result]) -> dict[str, Any]:
    best_sections: dict[str, int | float] = {}
    best_overall: dict[str, Any] | None = None
    for r in results:
        if test_kind(r.test) != "cefr" or r.attempt.trial_part_id:
            continue
        summary = cefr_multilevel.to_json(cefr_multilevel.summarize(r.attempt.section_scores or {}))
        for s in summary["sections"]:
            if s["status"] == "scored" and s["score"] is not None:
                best_sections[s["code"]] = max(best_sections.get(s["code"], 0), s["score"])
        overall = summary.get("overall")
        if overall and (best_overall is None or overall["score"] > best_overall["score"]):
            best_overall = overall
    return {"sections": best_sections, "overall": best_overall}


def _essays(user, subject: str) -> dict[str, Any]:
    from apps.essays.models import EssaySubmission

    GRADED = (
        EssaySubmission.Status.GRADED,
        EssaySubmission.Status.AI_EVALUATED,
        EssaySubmission.Status.TEACHER_REVIEWED,
    )
    graded = EssaySubmission.objects.filter(student=user, topic__subject=subject, status__in=GRADED).order_by("-id")
    last = graded.first()
    recent = (
        EssaySubmission.objects.filter(student=user)
        .filter(Q(topic__subject=subject) | Q(topic__isnull=True) if subject == "uzbek" else Q(topic__subject=subject))
        .select_related("topic")
        .order_by("-updated_at")[:2]
    )
    return {
        "count": graded.count(),
        "last_score": float(last.total_score) if last and last.total_score is not None else None,
        "last_max": last.max_score if last else None,
        "recent": [
            {
                "id": e.id,
                "topic_id": e.topic_id,
                "title": e.topic.title if e.topic else e.custom_title,
                "category": e.topic.category if e.topic else "",
                "rubric_type": e.topic.rubric_type if e.topic else "bmb_12",
                "status": e.status,
                "total_score": float(e.total_score) if e.total_score is not None and e.status in GRADED else None,
                "max_score": e.max_score if e.status in GRADED else None,
                "overall_band": (
                    float(e.total_score)
                    if e.topic and e.topic.subject == "english" and e.total_score is not None and e.status in GRADED
                    else None
                ),
                "updated_at": e.updated_at.isoformat() if e.updated_at else None,
            }
            for e in recent
        ],
    }


def weak_parts(user, subject: str) -> list[dict[str, Any]]:
    """
    Weakest section/part/question-type groups over the last finished attempts.

    Unanswered questions count as misses (an attempt contributes every question of
    its test). Needs at least two groups to say which is weaker.
    """
    attempts = list(
        TestAttempt.objects.filter(
            student=user, test__subject=subject, status__in=FINISHED, is_preview=False, trial_part__isnull=True
        )
        .order_by("-id")
        .values("id", "test_id")[:WEAK_ATTEMPTS]
    )
    if not attempts:
        return []
    test_ids = {a["test_id"] for a in attempts}
    questions: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for q in (
        Question.objects.filter(test_id__in=test_ids)
        .exclude(question_type__in=NOT_OBJECTIVE)
        .values("id", "test_id", "question_type", "section__code", "section__name", "group__part__number")
    ):
        questions[q["test_id"]].append(q)
    right = set(
        StudentAnswer.objects.filter(attempt_id__in=[a["id"] for a in attempts], is_correct=True).values_list(
            "attempt_id", "question_id"
        )
    )
    groups: dict[tuple, dict[str, Any]] = {}
    for a in attempts:
        for q in questions.get(a["test_id"], []):
            key = (q["section__code"] or "", q["group__part__number"] or "", q["question_type"])
            g = groups.setdefault(
                key,
                {
                    "section_code": key[0],
                    "section_name": q["section__name"] or "",
                    "part": key[1],
                    "question_type": key[2],
                    "correct": 0,
                    "total": 0,
                },
            )
            g["total"] += 1
            g["correct"] += (a["id"], q["id"]) in right
    usable = [g for g in groups.values() if g["total"] >= WEAK_MIN_TOTAL]
    if len(usable) < 2:
        return []
    usable.sort(key=lambda g: (g["correct"] / g["total"], -g["total"]))
    return [g for g in usable[:WEAK_PARTS] if g["correct"] < g["total"]]


def goal_for(profile, subject: str, results: list[Result]) -> dict[str, Any] | None:
    """The onboarding goal, only when the student set one for this subject, compared with real results."""
    target = getattr(profile, "exam_target", "")
    if not getattr(profile, "onboarding_completed", False) or GOAL_SUBJECT.get(target) != subject:
        return None
    current: str | None = None
    reached: bool | None = None
    wanted = profile.target_grade or ""
    if target in ("national_certificate", "milliy_sertifikat", "ona_tili"):
        current = _best_grade(results)
        if current and wanted in BMB_GRADE_ORDER:
            reached = BMB_GRADE_ORDER.index(current) >= BMB_GRADE_ORDER.index(wanted)
    elif target in ("multilevel", "cefr"):
        overall = _best_cefr(results)["overall"]
        current = overall["level"] if overall else None
        level = wanted.split()[0] if wanted else ""
        if current in CEFR_ORDER and level in CEFR_ORDER:
            reached = CEFR_ORDER.index(current) >= CEFR_ORDER.index(level)
    return {
        "exam_target": target,
        "target": wanted,
        "months": profile.target_timeline_months,
        "current": current,
        "reached": reached,
    }


def _today_study_minutes(user) -> int:
    from apps.essays.models import EssaySubmission
    from apps.speaking.models import SpeakingSubmission

    today = timezone.localdate()
    minutes = 0

    today_attempts = TestAttempt.objects.filter(
        student=user, status__in=FINISHED, is_preview=False, completed_at__date=today
    )
    for att in today_attempts:
        sec = getattr(att, "time_taken_seconds", None)
        if sec and sec > 0:
            minutes += max(1, int(sec) // 60)
        elif att.completed_at and att.started_at:
            diff = int((att.completed_at - att.started_at).total_seconds()) // 60
            minutes += diff if 1 <= diff <= 240 else 15
        else:
            minutes += 15

    essay_count = (
        EssaySubmission.objects.filter(student=user, updated_at__date=today)
        .exclude(status=EssaySubmission.Status.DRAFT)
        .count()
    )
    minutes += essay_count * 15

    speaking_subs = SpeakingSubmission.objects.filter(user=user, created_at__date=today)
    for sp in speaking_subs:
        dur = getattr(sp, "duration_seconds", 0) or 0
        minutes += max(5, int(dur) // 60) if dur > 0 else 5

    return minutes


def _recommended_practice(subject: str) -> list[dict[str, Any]]:
    if subject == "english":
        return [
            {
                "section_code": "listening",
                "section_name": "Listening",
                "part": 1,
                "question_type": "gap_fill",
                "label": "Listening, Qism 1 — Bo'sh joyni to'ldirish",
                "is_recommended": True,
            },
            {
                "section_code": "reading",
                "section_name": "Reading",
                "part": 2,
                "question_type": "matching",
                "label": "Reading, Qism 2 — Moslashtirish",
                "is_recommended": True,
            },
            {
                "section_code": "listening",
                "section_name": "Listening",
                "part": 3,
                "question_type": "single",
                "label": "Listening, Qism 3 — Variantli savol",
                "is_recommended": True,
            },
        ]
    if subject == "biology":
        return [
            {
                "section_code": "sitologiya",
                "section_name": "Sitologiya va hujayra",
                "part": 1,
                "question_type": "single",
                "label": "Hujayra tuzilishi va organoidlar",
                "is_recommended": True,
            },
            {
                "section_code": "genetika",
                "section_name": "Genetika va seleksiya",
                "part": 2,
                "question_type": "matching_matrix",
                "label": "Mendel qonunlari va duragaylash",
                "is_recommended": True,
            },
            {
                "section_code": "anatomiya",
                "section_name": "Odam anatomiyasi",
                "part": 3,
                "question_type": "dual_open_calc",
                "label": "Qon aylanish va asab tizimi masalalari",
                "is_recommended": True,
            },
        ]
    if subject == "chemistry":
        return [
            {
                "section_code": "umumiy_kimyo",
                "section_name": "Umumiy va anorganik kimyo",
                "part": 1,
                "question_type": "single",
                "label": "Davriy qonun va kimyoviy bog'lanish",
                "is_recommended": True,
            },
            {
                "section_code": "eritmalar",
                "section_name": "Stexiometriya va eritmalar",
                "part": 2,
                "question_type": "dual_open_calc",
                "label": "Massa ulush va konsentratsiya hisoblash",
                "is_recommended": True,
            },
            {
                "section_code": "organika",
                "section_name": "Organik kimyo",
                "part": 3,
                "question_type": "matching_matrix",
                "label": "Uglevodorodlar va polimerlar",
                "is_recommended": True,
            },
        ]
    if subject == "law":
        return [
            {
                "section_code": "konstitutsiya",
                "section_name": "Konstitutsiyaviy huquq",
                "part": 1,
                "question_type": "single",
                "label": "O'zbekiston Konstitutsiyasi va inson huquqlari",
                "is_recommended": True,
            },
            {
                "section_code": "nazariya",
                "section_name": "Davlat va huquq nazariyasi",
                "part": 2,
                "question_type": "single",
                "label": "Huquqiy normalar va yuridik javobgarlik",
                "is_recommended": True,
            },
            {
                "section_code": "kazus",
                "section_name": "Fuqarolik va jinoyat huquqi",
                "part": 3,
                "question_type": "legal_case_study",
                "label": "Amaliy huquqiy vaziyatlar (Kazus tahlili)",
                "is_recommended": True,
            },
        ]
    return [
        {
            "section_code": "grammar",
            "section_name": "Ona tili (Grammatika)",
            "part": 1,
            "question_type": "single",
            "label": "Imlo, fonetika va leksikologiya",
            "is_recommended": True,
        },
        {
            "section_code": "reading",
            "section_name": "O'qish savodxonligi",
            "part": 2,
            "question_type": "single",
            "label": "Ilmiy va badiiy matn tahlili",
            "is_recommended": True,
        },
        {
            "section_code": "literature",
            "section_name": "Adabiyot va G'azal tahlili",
            "part": 3,
            "question_type": "matching",
            "label": "Mumtoz adabiyot va vazn tahlili",
            "is_recommended": True,
        },
    ]


def _resume(user, subject: str) -> dict[str, Any] | None:
    attempt = (
        TestAttempt.objects.filter(student=user, status=TestAttempt.Status.IN_PROGRESS, test__subject=subject, is_preview=False)
        .select_related("test")
        .order_by("-started_at")
        .first()
    )
    if attempt is None or attempt.is_time_expired:
        return None
    english = attempt.test.subject == "english" or test_kind(attempt.test) in ("cefr", "ielts")
    return {
        "attempt_id": attempt.id,
        "test_id": attempt.test_id,
        "title": attempt.test.title,
        "route": f"/english-exam/{attempt.id}" if english else f"/take/{attempt.id}",
        "started_at": attempt.started_at.isoformat(),
    }


class StudentDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        from apps.payments.ai_quota import get_user_plan_tier

        user = request.user
        profile = getattr(user, "profile", None)
        subject = request.query_params.get("subject") or getattr(profile, "active_subject", "") or "uzbek"
        if subject not in SUBJECTS:
            subject = "uzbek"

        rows = list(
            Result.objects.filter(student=user, test__subject=subject, attempt__is_preview=False)
            .select_related("test", "attempt")
            .prefetch_related("section_scores")
            .order_by("-calculated_at", "-id")
        )
        real = [r for r in rows if not r.attempt.trial_part_id]
        percentages = [float(r.percentage) for r in real]
        cefr = _best_cefr(real)
        best_pct = max(percentages) if percentages else None
        today_minutes = _today_study_minutes(user)
        goal_minutes = getattr(profile, "daily_goal_minutes", 15) or 15
        weaks = weak_parts(user, subject)

        return Response(
            {
                "subject": subject,
                "tier": get_user_plan_tier(user),
                "server_time": timezone.now().isoformat(),
                "resume": _resume(user, subject),
                "indicators": {
                    "tests_taken": len(real),
                    "average_percentage": round(sum(percentages) / len(percentages), 1) if percentages else None,
                    "best_percentage": round(best_pct, 1) if best_pct is not None else None,
                    "best_grade": _best_grade(real),
                    "best_sections": cefr["sections"],
                    "best_overall": cefr["overall"],
                    "essays": _essays(user, subject),
                    "streak": getattr(profile, "current_streak", 0) or 0,
                },
                "daily_goal": {
                    "goal_minutes": goal_minutes,
                    "completed_minutes": today_minutes,
                    "progress_pct": min(100, int(round((today_minutes / max(1, goal_minutes)) * 100))),
                    "reminder_slot": getattr(profile, "reminder_slot", "evening") or "evening",
                    "level": getattr(profile, "level", "beginner") or "beginner",
                    "target_exam": getattr(profile, "target_exam", "") or getattr(profile, "exam_target", ""),
                    "daily_plan_summary": getattr(profile, "daily_plan_summary", ""),
                },
                "recent": _recent(rows),
                "weak_parts": weaks,
                "recommended_practice": _recommended_practice(subject) if not weaks else [],
                "goal": goal_for(profile, subject, real) if profile else None,
            }
        )
