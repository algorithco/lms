"""Panel JSON API — same queries/rules as apps/panel/views.py, JSON in/out."""
from __future__ import annotations

from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.accounts.models import Profile, User
from apps.essays.models import EssaySubmission, EssayTopic
from apps.payments.models import PaymentRequest, UserSubscription
from apps.tests.models import (
    Choice, ExamSection, GapBlank, MatchingOption, MatchingPair,
    MatchingPrompt, Question, ReadingPassage, Test, TestAttempt,
)

from .permissions import IsPanelAdmin, IsPanelAdminOrEssayCreator
from .serializers import (
    EssayTopicSerializer,
    QuestionAdminSerializer,
    TestAdminSerializer,
    UserAdminSerializer,
)


@api_view(["GET"])
@permission_classes([IsPanelAdmin])
def dashboard_view(request):
    tests = Test.objects.aggregate(
        total=Count("id"),
        published=Count("id", filter=Q(status=Test.Status.PUBLISHED)),
        draft=Count("id", filter=Q(status=Test.Status.DRAFT)),
        archived=Count("id", filter=Q(status=Test.Status.ARCHIVED)),
    )
    users = User.objects.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        blocked=Count("id", filter=Q(is_active=False)),
    )
    role_counts = dict(
        User.objects.filter(is_active=True)
        .values_list("role")
        .annotate(c=Count("id"))
        .values_list("role", "c")
    )
    today = timezone.localdate()
    now = timezone.now()
    attempts = TestAttempt.objects.aggregate(
        total=Count("id"),
        today=Count("id", filter=Q(started_at__date=today)),
    )
    essays = EssaySubmission.objects.aggregate(
        total=Count("id"),
        # Semantics split (v0.48.0): "pending_ai" = still being AI-graded
        # (worker queue health signal), "awaiting_review" = PENDING_TEACHER
        # only (matches the teacher queue definition — avoids the
        # "admin 21 pending vs empty teacher queue" confusion).
        pending_ai=Count("id", filter=Q(status=EssaySubmission.Status.PENDING)),
        awaiting_review=Count(
            "id",
            filter=Q(status=EssaySubmission.Status.PENDING_TEACHER),
        ),
    )
    payments = PaymentRequest.objects.aggregate(
        pending=Count("id", filter=Q(status=PaymentRequest.Status.PENDING)),
    )
    recent_tests = (
        Test.objects.select_related("course").order_by("-created_at")[:5]
    )
    recent_topics = EssayTopic.objects.order_by("-created_at")[:5]

    # -- Cohort & Audience Segmentation (Smart Onboarding analytics) -----------
    onboarded_qs = Profile.objects.filter(onboarding_completed=True)
    total_onboarded = onboarded_qs.count()

    nat_count = onboarded_qs.filter(exam_target="national_certificate").count()
    att_count = onboarded_qs.filter(exam_target="attestation").count()
    und_count = onboarded_qs.filter(exam_target="undecided").count()

    nat_pct = round((nat_count / max(total_onboarded, 1)) * 100, 1)
    att_pct = round((att_count / max(total_onboarded, 1)) * 100, 1)
    und_pct = round((und_count / max(total_onboarded, 1)) * 100, 1)

    avg_placement = onboarded_qs.filter(placement_score__isnull=False).aggregate(avg=Avg("placement_score"))["avg"]
    avg_score = round(float(avg_placement), 2) if avg_placement is not None else 0.0

    timeline_1m = onboarded_qs.filter(target_timeline_months=1).count()
    timeline_3m = onboarded_qs.filter(target_timeline_months=3).count()
    timeline_6m = onboarded_qs.filter(target_timeline_months=6).count()

    cohort_analytics = {
        "total_onboarded": total_onboarded,
        "segmentation": {
            "national_certificate": {"count": nat_count, "percentage": nat_pct, "label": "Milliy sertifikat"},
            "attestation": {"count": att_count, "percentage": att_pct, "label": "Attestatsiya 2026"},
            "undecided": {"count": und_count, "percentage": und_pct, "label": "Noma'lum"},
        },
        "avg_placement_score": avg_score,
        "timeline_breakdown": {
            "months_1": {"count": timeline_1m, "label": "1 oylik (shoshilinch)"},
            "months_3": {"count": timeline_3m, "label": "3 oylik (standart)"},
            "months_6": {"count": timeline_6m, "label": "6 oylik (uzoq muddatli)"},
        },
    }

    return Response({
        "tests": tests,
        "questions": Question.objects.count(),
        "essay_topics": EssayTopic.objects.count(),
        "users": users,
        "new_users_today": User.objects.filter(date_joined__date=today).count(),
        "attempts": attempts,
        "essays": essays,
        "pending_payments": payments["pending"],
        "active_subscriptions": UserSubscription.objects.filter(
            status=UserSubscription.Status.ACTIVE, expires_at__gt=now,
        ).count(),
        "role_breakdown": [
            {"key": key, "count": role_counts.get(key, 0)}
            for key in ("student", "teacher", "parent", "admin")
        ],
        "recent_tests": TestAdminSerializer(recent_tests, many=True).data,
        "recent_topics": EssayTopicSerializer(recent_topics, many=True).data,
        "cohort_analytics": cohort_analytics,
    })


@api_view(["GET"])
@permission_classes([IsPanelAdmin])
def cohort_analytics_view(request):
    """GET /api/v1/panel/analytics/cohorts/"""
    onboarded_qs = Profile.objects.filter(onboarding_completed=True)
    total_onboarded = onboarded_qs.count()

    nat_count = onboarded_qs.filter(exam_target="national_certificate").count()
    att_count = onboarded_qs.filter(exam_target="attestation").count()
    und_count = onboarded_qs.filter(exam_target="undecided").count()

    nat_pct = round((nat_count / max(total_onboarded, 1)) * 100, 1)
    att_pct = round((att_count / max(total_onboarded, 1)) * 100, 1)
    und_pct = round((und_count / max(total_onboarded, 1)) * 100, 1)

    avg_placement = onboarded_qs.filter(placement_score__isnull=False).aggregate(avg=Avg("placement_score"))["avg"]
    avg_score = round(float(avg_placement), 2) if avg_placement is not None else 0.0

    timeline_1m = onboarded_qs.filter(target_timeline_months=1).count()
    timeline_3m = onboarded_qs.filter(target_timeline_months=3).count()
    timeline_6m = onboarded_qs.filter(target_timeline_months=6).count()

    return Response({
        "total_onboarded": total_onboarded,
        "segmentation": {
            "national_certificate": {"count": nat_count, "percentage": nat_pct, "label": "Milliy sertifikat"},
            "attestation": {"count": att_count, "percentage": att_pct, "label": "Attestatsiya 2026"},
            "undecided": {"count": und_count, "percentage": und_pct, "label": "Noma'lum"},
        },
        "avg_placement_score": avg_score,
        "timeline_breakdown": {
            "months_1": {"count": timeline_1m, "label": "1 oylik (shoshilinch)"},
            "months_3": {"count": timeline_3m, "label": "3 oylik (standart)"},
            "months_6": {"count": timeline_6m, "label": "6 oylik (uzoq muddatli)"},
        },
    })


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
@api_view(["GET", "POST"])
@permission_classes([IsPanelAdmin])
def tests_view(request):
    if request.method == "POST":
        ser = TestAdminSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=400)
        ser.save()
        return Response(ser.data, status=201)
    qs = Test.objects.select_related("course").annotate(q_count=Count("questions"))
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    if q:
        qs = qs.filter(title__icontains=q)
    if status in {c[0] for c in Test.Status.choices}:
        qs = qs.filter(status=status)
    tests = qs.order_by("-created_at")[:100]
    return Response({
        "results": TestAdminSerializer(tests, many=True).data,
        "statuses": [{"value": v, "label": l} for v, l in Test.Status.choices],
    })


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsPanelAdmin])
def test_detail_view(request, test_id: int):
    test = get_object_or_404(Test, id=test_id)
    if request.method == "DELETE":
        test.delete()
        return Response(status=204)
    ser = TestAdminSerializer(
        test, data=request.data if request.method == "PATCH" else None,
        partial=(request.method == "PATCH"),
    )
    if request.method == "PATCH":
        if not ser.is_valid():
            return Response(ser.errors, status=400)
        ser.save()
    return Response(TestAdminSerializer(test).data if request.method == "GET" else ser.data)


@api_view(["POST"])
@permission_classes([IsPanelAdmin])
def test_status_view(request, test_id: int):
    test = get_object_or_404(Test, id=test_id)
    new_status = str(request.data.get("status", "")).strip()
    if new_status not in {c[0] for c in Test.Status.choices}:
        return Response({"detail": "Invalid status."}, status=400)
    test.status = new_status
    test.save()  # keeps is_active in sync (same as HTML view)
    return Response(TestAdminSerializer(test).data)


# ---------------------------------------------------------------------------
# Questions (nested choices, mirrors question_add/edit views)
# ---------------------------------------------------------------------------
def _save_choices(question: Question, choices: list | None) -> None:
    if choices is None:
        return
    question.choices.all().delete()
    for i, c in enumerate(choices):
        Choice.objects.create(
            question=question,
            text=str(c.get("text", "")).strip(),
            is_correct=bool(c.get("is_correct", False)),
            position=int(c.get("position", i) or 0),
        )


def _save_gaps(question: Question, gaps: list | None) -> None:
    """Replace gap blanks. Shape: [{position: int, answers: [str, ...]}]."""
    if gaps is None:
        return
    question.gap_blanks.all().delete()
    for g in gaps:
        try:
            pos = int(g.get("position", 0))
        except (TypeError, ValueError):
            continue
        for answer in g.get("answers", []) or []:
            text = str(answer or "").strip()[:200]
            if text:
                GapBlank.objects.create(
                    question=question, position=pos, answer_text=text,
                )


def _save_matching(question: Question, payload: dict | None) -> None:
    """Replace matching data. Prompts/options by position; pairs link them.

    Shape: {prompts: [{text, position}], options: [{text, position}],
            pairs: [{prompt_position, option_position}]}.
    """
    if payload is None:
        return
    MatchingPair.objects.filter(prompt__question=question).delete()
    question.matching_prompts.all().delete()
    question.matching_options.all().delete()
    prompts = {}
    for i, p in enumerate(payload.get("prompts", []) or []):
        text = str(p.get("text", "")).strip()
        if not text:
            continue
        try:
            pos = int(p.get("position", i))
        except (TypeError, ValueError):
            pos = i
        prompts[pos] = MatchingPrompt.objects.create(
            question=question, text=text, position=pos,
        )
    options = {}
    for i, o in enumerate(payload.get("options", []) or []):
        text = str(o.get("text", "")).strip()
        if not text:
            continue
        try:
            pos = int(o.get("position", i))
        except (TypeError, ValueError):
            pos = i
        options[pos] = MatchingOption.objects.create(
            question=question, text=text, position=pos,
        )
    for pair in payload.get("pairs", []) or []:
        try:
            prompt = prompts[int(pair.get("prompt_position"))]
            option = options[int(pair.get("option_position"))]
        except (TypeError, ValueError, KeyError):
            continue
        MatchingPair.objects.create(prompt=prompt, correct_option=option)


@api_view(["GET", "POST"])
@permission_classes([IsPanelAdmin])
def questions_view(request, test_id: int):
    test = get_object_or_404(Test, id=test_id)
    if request.method == "POST":
        ser = QuestionAdminSerializer(data={**request.data, "test": test.id})
        if not ser.is_valid():
            return Response(ser.errors, status=400)
        is_text = ser.validated_data.get("question_type") == Question.QuestionType.TEXT_MATCH
        question = ser.save()
        if question.position == 0:
            question.position = test.questions.count()
            question.save(update_fields=["position"])
        if is_text:
            question.choices.all().delete()
        else:
            _save_choices(question, request.data.get("choices"))
        _save_gaps(question, request.data.get("gaps"))
        if isinstance(request.data.get("matching"), dict):
            _save_matching(question, request.data.get("matching"))
        return Response(QuestionAdminSerializer(question).data, status=201)
    questions = test.questions.prefetch_related("choices").order_by("position")
    return Response({
        "test": TestAdminSerializer(test).data,
        "results": QuestionAdminSerializer(questions, many=True).data,
    })


@api_view(["PATCH", "DELETE"])
@permission_classes([IsPanelAdmin])
def question_detail_view(request, test_id: int, question_id: int):
    question = get_object_or_404(Question, id=question_id, test_id=test_id)
    if request.method == "DELETE":
        question.delete()
        return Response(status=204)
    ser = QuestionAdminSerializer(question, data=request.data, partial=True)
    if not ser.is_valid():
        return Response(ser.errors, status=400)
    saved = ser.save()
    if saved.question_type == Question.QuestionType.TEXT_MATCH:
        saved.choices.all().delete()
    elif "choices" in request.data:
        _save_choices(saved, request.data.get("choices"))
    if "gaps" in request.data:
        _save_gaps(saved, request.data.get("gaps"))
    if isinstance(request.data.get("matching"), dict):
        _save_matching(saved, request.data.get("matching"))
    return Response(QuestionAdminSerializer(saved).data)


# ---------------------------------------------------------------------------
# Exam sections & reading passages (Milliy Sertifikat content)
# ---------------------------------------------------------------------------
@api_view(["GET", "POST"])
@permission_classes([IsPanelAdmin])
def sections_view(request, test_id: int):
    from .serializers import ExamSectionSerializer

    test = get_object_or_404(Test, id=test_id)
    if request.method == "POST":
        ser = ExamSectionSerializer(data={**request.data, "test": test.id})
        if not ser.is_valid():
            return Response(ser.errors, status=400)
        section = ser.save()
        return Response(ExamSectionSerializer(section).data, status=201)
    sections = test.sections.order_by("order")
    return Response({"results": ExamSectionSerializer(sections, many=True).data})


@api_view(["GET", "POST"])
@permission_classes([IsPanelAdmin])
def passages_view(request, test_id: int):
    from .serializers import ReadingPassageSerializer

    test = get_object_or_404(Test, id=test_id)
    if request.method == "POST":
        ser = ReadingPassageSerializer(data={**request.data, "test": test.id})
        if not ser.is_valid():
            return Response(ser.errors, status=400)
        passage = ser.save()
        return Response(ReadingPassageSerializer(passage).data, status=201)
    passages = test.passages.order_by("order")
    return Response({"results": ReadingPassageSerializer(passages, many=True).data})


# ---------------------------------------------------------------------------
# Essay topics
# ---------------------------------------------------------------------------
@api_view(["GET", "POST"])
@permission_classes([IsPanelAdminOrEssayCreator])
def topics_view(request):
    if request.method == "POST":
        ser = EssayTopicSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=400)
        ser.save(created_by=request.user)
        return Response(ser.data, status=201)
    qs = EssayTopic.objects.select_related("created_by")
    q = (request.GET.get("q") or "").strip()
    category = (request.GET.get("category") or "").strip()
    if q:
        qs = qs.filter(title__icontains=q)
    if category in {c[0] for c in EssayTopic.Category.choices}:
        qs = qs.filter(category=category)
    return Response({
        "results": EssayTopicSerializer(qs.order_by("-created_at")[:100], many=True).data,
        "categories": [{"value": v, "label": l} for v, l in EssayTopic.Category.choices],
    })


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsPanelAdminOrEssayCreator])
def topic_detail_view(request, topic_id: int):
    topic = get_object_or_404(EssayTopic, id=topic_id)
    if request.method == "DELETE":
        topic.delete()
        return Response(status=204)
    if request.method == "PATCH":
        ser = EssayTopicSerializer(topic, data=request.data, partial=True)
        if not ser.is_valid():
            return Response(ser.errors, status=400)
        ser.save()
        return Response(ser.data)
    return Response(EssayTopicSerializer(topic).data)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
@api_view(["GET"])
@permission_classes([IsPanelAdmin])
def users_view(request):
    qs = User.objects.all()
    q = (request.GET.get("q") or "").strip()
    role = (request.GET.get("role") or "").strip()
    status = (request.GET.get("status") or "").strip()
    joined = (request.GET.get("joined") or "").strip()
    if q:
        qs = qs.filter(
            Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q)
        )
    if role in {c[0] for c in User.Role.choices}:
        qs = qs.filter(role=role)
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "blocked":
        qs = qs.filter(is_active=False)
    if joined == "today":
        qs = qs.filter(date_joined__date=timezone.localdate())
    elif joined == "7d":
        qs = qs.filter(date_joined__gte=timezone.now() - timezone.timedelta(days=7))
    elif joined == "30d":
        qs = qs.filter(date_joined__gte=timezone.now() - timezone.timedelta(days=30))
    return Response({
        "results": UserAdminSerializer(qs.order_by("-date_joined")[:100], many=True).data,
        "roles": [{"value": v, "label": l} for v, l in User.Role.choices],
    })


@api_view(["POST"])
@permission_classes([IsPanelAdmin])
def user_role_view(request, user_id: int):
    target = get_object_or_404(User, id=user_id)
    new_role = str(request.data.get("role", "")).strip()
    if new_role not in {c[0] for c in User.Role.choices}:
        return Response({"detail": "Invalid role."}, status=400)
    if target == request.user and new_role != User.Role.ADMIN:
        return Response({"detail": "You cannot demote yourself."}, status=400)
    target.role = new_role
    target.save(update_fields=["role"])
    return Response(UserAdminSerializer(target).data)


@api_view(["POST"])
@permission_classes([IsPanelAdmin])
def user_block_view(request, user_id: int):
    target = get_object_or_404(User, id=user_id)
    if target == request.user:
        return Response({"detail": "You cannot block yourself."}, status=400)
    was_active = target.is_active
    target.is_active = not target.is_active
    target.save(update_fields=["is_active"])
    # Revoke all refresh tokens when deactivating — 7-day OutstandingToken would otherwise stay valid
    if was_active and not target.is_active:
        try:
            from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

            for tok in OutstandingToken.objects.filter(user=target):
                BlacklistedToken.objects.get_or_create(token=tok)
        except Exception:
            # token_blacklist must stay non-fatal for the admin action
            pass
    return Response(UserAdminSerializer(target).data)


# ---------------------------------------------------------------------------
# Panel: Groups & Teacher Assignment
# ---------------------------------------------------------------------------
@api_view(["GET", "POST"])
@permission_classes([IsPanelAdmin])
def panel_groups_view(request):
    """GET /api/v1/panel/groups/ — List groups for admin.
    POST /api/v1/panel/groups/ — Create group with teacher & auto invite_code.
    """
    from apps.courses.models import StudentGroup
    import secrets

    if request.method == "POST":
        data = request.data or {}
        name = str(data.get("name") or "").strip()
        if not name:
            return Response({"error": "Guruh nomi kiritilishi shart."}, status=400)

        subject = str(data.get("subject") or "uzbek").strip().lower()
        if subject not in ("uzbek", "english"):
            subject = "uzbek"

        teacher_id = data.get("teacher_id")
        if not teacher_id:
            return Response({"error": "Ustoz tanlanishi shart."}, status=400)

        teacher = get_object_or_404(User, id=teacher_id)
        monthly_fee_raw = data.get("monthly_fee", 400000)
        try:
            monthly_fee = max(0, int(monthly_fee_raw))
        except (ValueError, TypeError):
            monthly_fee = 400000

        invite_code = f"GR-{secrets.token_hex(3).upper()}"
        while StudentGroup.objects.filter(invite_code=invite_code).exists():
            invite_code = f"GR-{secrets.token_hex(3).upper()}"

        group = StudentGroup.objects.create(
            name=name,
            subject=subject,
            teacher=teacher,
            invite_code=invite_code,
            monthly_fee=monthly_fee,
        )

        return Response({
            "id": group.id,
            "name": group.name,
            "subject": group.subject,
            "subject_display": "Ingliz tili (IELTS & Multi-level)" if group.subject == "english" else "Ona tili va adabiyot",
            "teacher_id": teacher.id,
            "teacher_name": teacher.get_full_name() or teacher.email,
            "teacher_email": teacher.email,
            "student_count": 0,
            "invite_code": group.invite_code,
            "monthly_fee": group.monthly_fee,
            "created_at": group.created_at,
            "message": f"'{group.name}' guruhi muvaffaqiyatli ochildi! Taklif kodi: #{group.invite_code}",
        }, status=201)

    # GET
    groups = (
        StudentGroup.objects.select_related("teacher")
        .prefetch_related("students")
        .order_by("-created_at")
    )
    results = []
    for g in groups:
        results.append({
            "id": g.id,
            "name": g.name,
            "subject": g.subject,
            "subject_display": "Ingliz tili (IELTS & Multi-level)" if g.subject == "english" else "Ona tili va adabiyot",
            "teacher_id": g.teacher_id,
            "teacher_name": g.teacher.get_full_name() or g.teacher.email,
            "teacher_email": g.teacher.email,
            "student_count": g.students.count(),
            "invite_code": g.invite_code or f"GR-{g.id:03d}",
            "monthly_fee": getattr(g, "monthly_fee", 400000),
            "created_at": g.created_at,
        })
    return Response({"results": results})


@api_view(["GET"])
@permission_classes([IsPanelAdmin])
def panel_teachers_view(request):
    """GET /api/v1/panel/teachers/ — List active teachers for group assignment."""
    teachers = User.objects.filter(
        Q(role="teacher") | Q(role="admin") | Q(is_staff=True) | Q(is_superuser=True),
        is_active=True,
    ).order_by("first_name", "last_name", "email")
    return Response({
        "results": [
            {
                "id": u.id,
                "full_name": u.get_full_name() or u.email,
                "email": u.email,
                "role": u.role,
            }
            for u in teachers
        ]
    })


# ---------------------------------------------------------------------------
# Panel: Attendance Monitoring & Excel Export
# ---------------------------------------------------------------------------
@api_view(["GET"])
@permission_classes([IsPanelAdmin])
def panel_attendance_overview_view(request):
    """GET /api/v1/panel/attendance/ — Live attendance stats across all groups."""
    from apps.attendance.models import AttendanceRecord, AttendanceSession
    from apps.courses.models import StudentGroup

    groups = (
        StudentGroup.objects.select_related("teacher")
        .prefetch_related("students")
        .order_by("-created_at")
    )
    results = []
    for g in groups:
        sessions = AttendanceSession.objects.filter(group=g).order_by("-lesson_date", "-id")
        total_sessions = sessions.count()
        rec_qs = AttendanceRecord.objects.filter(session__group=g)
        present = rec_qs.filter(status="present").count()
        late = rec_qs.filter(status="late").count()
        absent = rec_qs.filter(status="absent").count()
        total_records = present + late + absent
        rate = round((present + late * 0.5) / max(total_records, 1) * 100, 1) if total_records > 0 else 100.0

        recent_sessions = []
        for s in sessions[:3]:
            s_recs = s.records.all()
            recent_sessions.append({
                "id": s.id,
                "lesson_date": s.lesson_date.strftime("%d.%m.%Y"),
                "status": s.status,
                "present": s_recs.filter(status="present").count(),
                "late": s_recs.filter(status="late").count(),
                "absent": s_recs.filter(status="absent").count(),
            })

        results.append({
            "group_id": g.id,
            "group_name": g.name,
            "subject": g.subject,
            "subject_display": "Ingliz tili (IELTS)" if g.subject == "english" else "Ona tili",
            "teacher_name": g.teacher.get_full_name() or g.teacher.email,
            "student_count": g.students.count(),
            "total_sessions": total_sessions,
            "present_count": present,
            "late_count": late,
            "absent_count": absent,
            "attendance_rate": rate,
            "recent_sessions": recent_sessions,
        })
    return Response({"results": results})


@api_view(["GET"])
@permission_classes([IsPanelAdmin])
def panel_attendance_export_view(request):
    """GET /api/v1/panel/attendance/export/ — Export monthly attendance report to Excel."""
    import io
    from django.http import HttpResponse
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    from apps.attendance.models import AttendanceRecord, AttendanceSession
    from apps.courses.models import StudentGroup

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Davomat Hisoboti"

    ws.merge_cells("A1:J1")
    today_str = timezone.localdate().strftime("%d.%m.%Y")
    ws["A1"] = f"GRAND EDUCATION — BARCHA GURUHLAR DAVOMAT HISOBOTI ({today_str})"
    ws["A1"].font = Font(name="Arial", size=13, bold=True, color="FFFFFF")
    ws["A1"].fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 36

    headers = [
        "№", "Guruh nomi", "Fan", "Ustoz", "O'quvchilar soni",
        "Darslar soni", "Kelganlar", "Kech qolganlar", "Kelmaganlar", "Davomat ko'rsatkichi"
    ]
    ws.append(headers)
    ws.row_dimensions[2].height = 24
    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=2, column=col_idx)
        cell.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center")

    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )

    groups = StudentGroup.objects.select_related("teacher").prefetch_related("students").order_by("name")
    for idx, g in enumerate(groups, 1):
        sessions = AttendanceSession.objects.filter(group=g)
        tot_s = sessions.count()
        recs = AttendanceRecord.objects.filter(session__group=g)
        p_cnt = recs.filter(status="present").count()
        l_cnt = recs.filter(status="late").count()
        a_cnt = recs.filter(status="absent").count()
        tot_r = p_cnt + l_cnt + a_cnt
        pct = round((p_cnt + l_cnt * 0.5) / max(tot_r, 1) * 100, 1) if tot_r > 0 else 100.0

        row = [
            idx,
            g.name,
            "Ingliz tili (IELTS)" if g.subject == "english" else "Ona tili va adabiyot",
            g.teacher.get_full_name() or g.teacher.email,
            g.students.count(),
            tot_s,
            p_cnt,
            l_cnt,
            a_cnt,
            f"{pct}%",
        ]
        ws.append(row)
        curr_row = ws.max_row
        ws.row_dimensions[curr_row].height = 20
        for c_idx in range(1, 11):
            c = ws.cell(row=curr_row, column=c_idx)
            c.border = thin_border
            c.alignment = Alignment(
                horizontal="left" if c_idx in (2, 4) else "center",
                vertical="center",
            )

    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    response = HttpResponse(
        buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    filename = f"grandec_davomat_{timezone.localdate().strftime('%Y_%m_%d')}.xlsx"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
