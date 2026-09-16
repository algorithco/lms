"""Panel JSON API — same queries/rules as apps/panel/views.py, JSON in/out."""
from __future__ import annotations

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.accounts.models import User
from apps.essays.models import EssaySubmission, EssayTopic
from apps.payments.models import PaymentRequest, UserSubscription
from apps.tests.models import Choice, Question, Test, TestAttempt

from .permissions import IsPanelAdmin
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
        awaiting_review=Count(
            "id",
            filter=Q(
                status__in=[
                    EssaySubmission.Status.PENDING,
                    EssaySubmission.Status.PENDING_TEACHER,
                ]
            ),
        ),
    )
    payments = PaymentRequest.objects.aggregate(
        pending=Count("id", filter=Q(status=PaymentRequest.Status.PENDING)),
    )
    recent_tests = (
        Test.objects.select_related("course").order_by("-created_at")[:5]
    )
    recent_topics = EssayTopic.objects.order_by("-created_at")[:5]
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
    return Response(QuestionAdminSerializer(saved).data)


# ---------------------------------------------------------------------------
# Essay topics
# ---------------------------------------------------------------------------
@api_view(["GET", "POST"])
@permission_classes([IsPanelAdmin])
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
@permission_classes([IsPanelAdmin])
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
    target.is_active = not target.is_active
    target.save(update_fields=["is_active"])
    return Response(UserAdminSerializer(target).data)
