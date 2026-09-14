"""School JSON API — groups, parent portal, teacher overview, analytics,
essay leaderboard and CSV imports. Mirrors apps/web/views.py queries.
"""
from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db.models import Avg, Case, Count, F, Max, Q, When
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.accounts.access import is_platform_admin
from apps.accounts.models import ParentStudentLink, User
from apps.courses.models import StudentGroup
from apps.essays.models import EssaySubmission, EssayTopic
from apps.results.models import Result
from apps.tests.models import Test

from .permissions import IsTeacherOrAdmin
from .serializers import GroupMemberSerializer, StudentGroupSerializer


def _teacher_groups(user):
    if is_platform_admin(user):
        return StudentGroup.objects.all()
    return StudentGroup.objects.filter(teacher=user)


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------
@api_view(["GET", "POST"])
@permission_classes([IsTeacherOrAdmin])
def groups_view(request):
    if request.method == "POST":
        name = str(request.data.get("name", "")).strip()
        if not name:
            return Response({"detail": "Name is required."}, status=400)
        teacher = request.user
        if _teacher_groups(request.user).filter(name=name).exists():
            return Response({"detail": "Group with this name exists."}, status=400)
        group = StudentGroup.objects.create(
            teacher=teacher,
            name=name,
            description=str(request.data.get("description", "")),
        )
        return Response(StudentGroupSerializer(group).data, status=201)
    qs = _teacher_groups(request.user).prefetch_related("students").order_by("name")
    return Response(StudentGroupSerializer(qs, many=True).data)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsTeacherOrAdmin])
def group_detail_view(request, group_id: int):
    group = get_object_or_404(_teacher_groups(request.user), id=group_id)
    if request.method == "DELETE":
        group.delete()
        return Response(status=204)
    if request.method == "PATCH":
        if "name" in request.data:
            group.name = str(request.data["name"]).strip() or group.name
        if "description" in request.data:
            group.description = str(request.data.get("description", ""))
        group.save()
    return Response(
        StudentGroupSerializer(
            _teacher_groups(request.user).prefetch_related("students").get(id=group.id)
        ).data
    )


@api_view(["POST"])
@permission_classes([IsTeacherOrAdmin])
def group_members_view(request, group_id: int):
    """{add: [user_ids], remove: [user_ids]} — students only."""
    group = get_object_or_404(_teacher_groups(request.user), id=group_id)
    add_ids = request.data.get("add", []) or []
    remove_ids = request.data.get("remove", []) or []
    if add_ids:
        students = User.objects.filter(id__in=add_ids, role="student", is_active=True)
        group.students.add(*students)
    if remove_ids:
        group.students.remove(*User.objects.filter(id__in=remove_ids))
    group.refresh_from_db()
    return Response(StudentGroupSerializer(group).data)


@api_view(["GET"])
@permission_classes([IsTeacherOrAdmin])
def student_search_view(request):
    """Find students to add to groups (email/name search)."""
    q = (request.GET.get("q") or "").strip()
    qs = User.objects.filter(role="student", is_active=True)
    if q:
        qs = qs.filter(
            Q(email__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
        )
    return Response(GroupMemberSerializer(qs.order_by("first_name")[:20], many=True).data)


# ---------------------------------------------------------------------------
# Parent portal
# ---------------------------------------------------------------------------
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def parent_overview_view(request):
    parent = request.user
    if request.GET.get("user_id") and is_platform_admin(request.user):
        parent = get_object_or_404(User, id=request.GET["user_id"])
    if parent.role != "parent" and not is_platform_admin(request.user):
        return Response({"detail": "Parent access required."}, status=403)
    links = (
        ParentStudentLink.objects.filter(parent=parent)
        .select_related("student")
        .order_by("-created_at")
    )
    children = []
    for link in links:
        s = link.student
        results = (
            Result.objects.filter(student=s)
            .select_related("test")
            .order_by("-calculated_at")[:10]
        )
        children.append({
            "id": s.id,
            "name": s.get_full_name(),
            "email": s.email,
            "relationship": link.relationship,
            "is_approved": link.is_approved,
            "results": [
                {
                    "test": r.test.title,
                    "percentage": float(r.percentage),
                    "is_passed": r.is_passed,
                    "date": r.calculated_at.isoformat(),
                }
                for r in results
            ],
        })
    return Response({"children": children})


# ---------------------------------------------------------------------------
# Teacher overview + analytics
# ---------------------------------------------------------------------------
@api_view(["GET"])
@permission_classes([IsTeacherOrAdmin])
def teacher_overview_view(request):
    user = request.user
    groups = _teacher_groups(user).prefetch_related("students")
    student_ids = set()
    for g in groups:
        student_ids.update(g.students.values_list("id", flat=True))
    if is_platform_admin(user):
        results_qs = Result.objects.all()
        tests_qs = Test.objects.filter(status=Test.Status.PUBLISHED)
    else:
        results_qs = Result.objects.filter(test__course__teacher=user)
        tests_qs = Test.objects.filter(
            course__teacher=user, status=Test.Status.PUBLISHED
        )
    recent = (
        results_qs.select_related("test", "student").order_by("-calculated_at")[:10]
    )
    return Response({
        "groups": StudentGroupSerializer(groups, many=True).data,
        "student_count": len(student_ids),
        "published_tests": tests_qs.count(),
        "active_topics": EssayTopic.objects.filter(is_active=True).count(),
        "recent_results": [
            {
                "student": r.student.get_full_name(),
                "test": r.test.title,
                "percentage": float(r.percentage),
                "is_passed": r.is_passed,
                "date": r.calculated_at.isoformat(),
            }
            for r in recent
        ],
    })


@api_view(["GET"])
@permission_classes([IsTeacherOrAdmin])
def analytics_view(request):
    try:
        days = min(max(int(request.GET.get("days", 14)), 1), 90)
    except (TypeError, ValueError):
        days = 14
    since = timezone.now() - timedelta(days=days)
    qs = Result.objects.filter(calculated_at__gte=since)
    if not is_platform_admin(request.user):
        qs = qs.filter(test__course__teacher=request.user)
    daily = (
        qs.annotate(day=TruncDate("calculated_at"))
        .values("day")
        .annotate(attempts=Count("id"), avg=Avg("percentage"))
        .order_by("day")
    )
    by_day = {str(row["day"]): row for row in daily}
    labels, attempts, avg = [], [], []
    for i in range(days - 1, -1, -1):
        day = (timezone.now() - timedelta(days=i)).date().isoformat()
        row = by_day.get(day, {})
        labels.append(day)
        attempts.append(row.get("attempts", 0))
        avg.append(round(float(row.get("avg") or 0), 1))
    return Response({
        "labels": labels,
        "attempts": attempts,
        "avg_percentage": avg,
        "totals": {
            "attempts": sum(attempts),
            "passed": qs.filter(is_passed=True).count(),
        },
    })


# ---------------------------------------------------------------------------
# Essay leaderboard (same queryset as web essay_leaderboard_view)
# ---------------------------------------------------------------------------
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def essay_leaderboard_view(request):
    stats = (
        EssaySubmission.objects.filter(status=EssaySubmission.Status.GRADED)
        .values("student__id", "student__first_name", "student__last_name")
        .annotate(
            best_score=Max("total_score"),
            best_converted=Max(
                Case(
                    When(final_score__isnull=False, then=F("final_score")),
                    default=F("total_score"),
                )
            ),
            essay_count=Count("id"),
            avg_score=Avg("total_score"),
        )
        .order_by("-best_score")[:20]
    )
    target = getattr(settings, "ESSAY_TARGET_SCALE", 75)
    board = []
    for i, s in enumerate(stats, 1):
        best = float(s["best_score"] or 0)
        board.append({
            "rank": i,
            "name": f"{s['student__first_name']} {s['student__last_name']}",
            "student_id": s["student__id"],
            "best_score": best,
            "converted_score": round(best / 24 * target) if best > 0 else 0,
            "essay_count": s["essay_count"],
            "avg_score": round(float(s["avg_score"] or 0), 1),
        })
    return Response({
        "podium": board[:3],
        "rest": board[3:],
        "total_essays": EssaySubmission.objects.filter(
            status=EssaySubmission.Status.GRADED
        ).count(),
        "total_students": len(board),
    })


# ---------------------------------------------------------------------------
# Public platform stats (landing page — aggregate only, no personal data)
# ---------------------------------------------------------------------------
@api_view(["GET"])
@permission_classes([AllowAny])
def public_stats_view(request):
    """Public totals + last-14-days activity for the landing Statistika band."""
    from apps.essays.models import EssaySubmission

    days = 30
    since = timezone.now() - timedelta(days=days)
    qs = Result.objects.filter(calculated_at__gte=since)
    daily = (
        qs.annotate(day=TruncDate("calculated_at"))
        .values("day")
        .annotate(attempts=Count("id"), avg=Avg("percentage"))
        .order_by("day")
    )
    by_day = {str(row["day"]): row for row in daily}
    labels, attempts, avg = [], [], []
    for i in range(days - 1, -1, -1):
        day = (timezone.now() - timedelta(days=i)).date().isoformat()
        row = by_day.get(day, {})
        labels.append(day)
        attempts.append(row.get("attempts", 0))
        avg.append(round(float(row.get("avg") or 0), 1))
    return Response({
        "totals": {
            "tests": Test.objects.filter(status=Test.Status.PUBLISHED).count(),
            "students": User.objects.filter(role="student", is_active=True).count(),
            "essays_graded": EssaySubmission.objects.filter(
                status=EssaySubmission.Status.GRADED
            ).count(),
        },
        "daily": {"labels": labels, "attempts": attempts, "avg": avg},
    })


# ---------------------------------------------------------------------------
# CSV imports (same services + guards as web views)
# ---------------------------------------------------------------------------
def _csv_guard(csv_file):
    if not csv_file:
        return "CSV faylni tanlang."
    if not csv_file.name.endswith(".csv"):
        return "Faqat CSV fayllar qabul qilinadi."
    if csv_file.size > 5 * 1024 * 1024:
        return "CSV fayl hajmi 5 MB dan oshmasligi kerak."
    try:
        csv_file.read().decode("utf-8-sig")
        csv_file.seek(0)
    except (UnicodeDecodeError, ValueError):
        return "CSV fayl UTF-8 kodlangan bo'lishi kerak."
    return None


@api_view(["POST"])
@permission_classes([IsTeacherOrAdmin])
def import_students_view(request):
    err = _csv_guard(request.FILES.get("csv_file"))
    if err:
        return Response({"detail": err}, status=400)
    from apps.accounts.services.csv_import import CSVImportService

    result = CSVImportService.import_students(
        csv_content=request.FILES["csv_file"].read(),
        created_by=request.user,
        send_welcome=True,
    )
    return Response({
        "created": result.get("created", 0),
        "skipped": result.get("skipped", 0),
        "errors": result.get("errors", []),
    })


@api_view(["GET", "POST"])
@permission_classes([IsTeacherOrAdmin])
def import_test_view(request):
    from apps.courses.models import Course

    courses = (
        Course.objects.all()
        if is_platform_admin(request.user)
        else Course.objects.filter(teacher=request.user)
    ).order_by("title")
    course_opts = [{"id": c.id, "title": c.title} for c in courses]
    if request.method == "GET":
        return Response({"courses": course_opts})
    err = _csv_guard(request.FILES.get("csv_file"))
    if err:
        return Response({"detail": err}, status=400)
    test_title = str(request.data.get("test_title", "")).strip()
    course_id = request.data.get("course_id")
    if not test_title:
        return Response({"detail": "Test nomini kiriting."}, status=400)
    if not course_id:
        return Response({"detail": "Kursni tanlang."}, status=400)
    try:
        time_limit = int(request.data.get("time_limit", 30) or 30)
        pass_pct = float(request.data.get("pass_percentage", 60) or 60)
    except (ValueError, TypeError):
        return Response({"detail": "Vaqt/foiz noto'g'ri."}, status=400)
    if not (1 <= time_limit <= 600) or not (0 <= pass_pct <= 100):
        return Response({"detail": "Vaqt (1-600) yoki foiz (0-100) xato."}, status=400)
    if not courses.filter(id=course_id).exists():
        return Response({"detail": "Kurs topilmadi."}, status=404)
    from apps.tests.bulk_import import BulkTestImportService

    result = BulkTestImportService.import_test(
        csv_content=request.FILES["csv_file"].read(),
        test_title=test_title,
        course_id=int(course_id),
        created_by=request.user,
        time_limit_minutes=time_limit,
        pass_percentage=pass_pct,
    )
    status = 201 if result.get("success") else 400
    return Response(result, status=status)
