"""In-app Admin Panel views (staff / role='admin' only).

Every view is wrapped in `@admin_required`; templates extend base.html so
they inherit the dual-theme shell, sidebar, and the {% t %} i18n system.
"""
from django.contrib import messages
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.core.translations import get_user_language, t
from apps.essays.models import EssayTopic
from apps.tests.models import Question, Test

from .decorators import admin_required, essay_topic_required
from .forms import ChoiceFormSet, EssayTopicForm, QuestionForm, TestForm


def _msg(request: HttpRequest, key: str, extra_tags: str = "") -> str:
    """Translated flash message (UZ/RU/EN aware)."""
    return t(key, get_user_language(request))


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@admin_required
def dashboard_view(request: HttpRequest) -> HttpResponse:
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
    lang = get_user_language(request)
    role_breakdown = [
        {"key": key, "label": t(label_key, lang), "count": role_counts.get(key, 0)}
        for key, label_key in [
            ("student", "role_student"),
            ("teacher", "role_teacher"),
            ("parent", "role_parent"),
            ("admin", "role_admin"),
        ]
    ]
    stats = {
        "tests": tests,
        "questions": Question.objects.count(),
        "essay_topics": EssayTopic.objects.count(),
        "users": users,
        "role_breakdown": role_breakdown,
        "recent_tests": Test.objects.select_related("course").order_by("-created_at")[:5],
        "recent_topics": EssayTopic.objects.order_by("-created_at")[:5],
    }
    return render(request, "panel/dashboard.html", {"stats": stats})


# ---------------------------------------------------------------------------
# Test CRUD + status
# ---------------------------------------------------------------------------
@admin_required
def test_list_view(request: HttpRequest) -> HttpResponse:
    qs = Test.objects.select_related("course").annotate(q_count=Count("questions"))
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    if q:
        qs = qs.filter(title__icontains=q)
    if status in {c[0] for c in Test.Status.choices}:
        qs = qs.filter(status=status)
    tests = qs.order_by("-created_at")[:100]
    return render(
        request,
        "panel/test_list.html",
        {"tests": tests, "q": q, "status": status, "statuses": Test.Status.choices},
    )


@admin_required
def test_create_view(request: HttpRequest) -> HttpResponse:
    form = TestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        test = form.save()
        messages.success(request, _msg(request, "panel_msg_test_created"))
        return redirect("panel:question-manage", test_id=test.id)
    return render(request, "panel/test_form.html", {"form": form, "test": None})


@admin_required
def test_edit_view(request: HttpRequest, test_id: int) -> HttpResponse:
    test = get_object_or_404(Test, id=test_id)
    form = TestForm(request.POST or None, instance=test)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _msg(request, "panel_msg_test_updated"))
        return redirect("panel:test-list")
    return render(request, "panel/test_form.html", {"form": form, "test": test})


@require_POST
@admin_required
def test_delete_view(request: HttpRequest, test_id: int) -> HttpResponse:
    test = get_object_or_404(Test, id=test_id)
    test.delete()
    messages.success(request, _msg(request, "panel_msg_test_deleted"))
    return redirect("panel:test-list")


@require_POST
@admin_required
def test_status_view(request: HttpRequest, test_id: int) -> HttpResponse:
    test = get_object_or_404(Test, id=test_id)
    new_status = request.POST.get("status", "").strip()
    if new_status in {c[0] for c in Test.Status.choices}:
        test.status = new_status
        test.save()  # save() keeps is_active in sync
        messages.success(request, _msg(request, "panel_msg_status_updated"))
    else:
        messages.error(request, _msg(request, "panel_msg_invalid_status"))
    return redirect("panel:test-list")


# ---------------------------------------------------------------------------
# Questions (per test) — with live preview on the form
# ---------------------------------------------------------------------------
@admin_required
def question_manage_view(request: HttpRequest, test_id: int) -> HttpResponse:
    test = get_object_or_404(Test, id=test_id)
    questions = test.questions.prefetch_related("choices").order_by("position")
    return render(request, "panel/question_manage.html", {"test": test, "questions": questions})


@admin_required
def question_add_view(request: HttpRequest, test_id: int) -> HttpResponse:
    test = get_object_or_404(Test, id=test_id)
    form = QuestionForm(request.POST or None)
    formset = ChoiceFormSet(request.POST or None, prefix="choices")
    if request.method == "POST":
        is_text = form.data.get("question_type") == Question.QuestionType.TEXT_MATCH
        # TEXT_MATCH questions carry no choices — skip formset validation
        if form.is_valid() and (is_text or formset.is_valid()):
            question = form.save(commit=False)
            question.test = test
            question.position = question.position or test.questions.count() + 1
            question.save()
            if not is_text:
                formset.instance = question
                formset.save()
            messages.success(request, _msg(request, "panel_msg_question_added"))
            return redirect("panel:question-manage", test_id=test.id)
    return render(
        request,
        "panel/question_form.html",
        {"test": test, "form": form, "formset": formset, "question": None},
    )


@admin_required
def question_edit_view(
    request: HttpRequest, test_id: int, question_id: int
) -> HttpResponse:
    test = get_object_or_404(Test, id=test_id)
    question = get_object_or_404(Question, id=question_id, test=test)
    form = QuestionForm(request.POST or None, instance=question)
    formset = ChoiceFormSet(request.POST or None, instance=question, prefix="choices")
    if request.method == "POST":
        is_text = form.data.get("question_type") == Question.QuestionType.TEXT_MATCH
        # TEXT_MATCH questions carry no choices — skip formset validation
        if form.is_valid() and (is_text or formset.is_valid()):
            saved = form.save()
            if saved.question_type != Question.QuestionType.TEXT_MATCH:
                formset.save()
            else:
                saved.choices.all().delete()
            messages.success(request, _msg(request, "panel_msg_question_updated"))
            return redirect("panel:question-manage", test_id=test.id)
    return render(
        request,
        "panel/question_form.html",
        {"test": test, "form": form, "formset": formset, "question": question},
    )


@require_POST
@admin_required
def question_delete_view(
    request: HttpRequest, test_id: int, question_id: int
) -> HttpResponse:
    question = get_object_or_404(Question, id=question_id, test_id=test_id)
    question.delete()
    messages.success(request, _msg(request, "panel_msg_question_deleted"))
    return redirect("panel:question-manage", test_id=test_id)


# ---------------------------------------------------------------------------
# Essay topics CRUD
# ---------------------------------------------------------------------------
@essay_topic_required
def essay_topic_list_view(request: HttpRequest) -> HttpResponse:
    qs = EssayTopic.objects.select_related("created_by")
    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    if q:
        qs = qs.filter(title__icontains=q)
    if category in {c[0] for c in EssayTopic.Category.choices}:
        qs = qs.filter(category=category)
    topics = qs.order_by("-created_at")[:100]
    return render(
        request,
        "panel/essay_topic_list.html",
        {
            "topics": topics,
            "q": q,
            "category": category,
            "categories": EssayTopic.Category.choices,
        },
    )


@essay_topic_required
def essay_topic_create_view(request: HttpRequest) -> HttpResponse:
    form = EssayTopicForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        topic = form.save(commit=False)
        topic.created_by = request.user
        topic.save()
        messages.success(request, _msg(request, "panel_msg_topic_created"))
        return redirect("panel:essay-topic-list")
    return render(request, "panel/essay_topic_form.html", {"form": form, "topic": None})


@essay_topic_required
def essay_topic_edit_view(request: HttpRequest, topic_id: int) -> HttpResponse:
    topic = get_object_or_404(EssayTopic, id=topic_id)
    form = EssayTopicForm(request.POST or None, instance=topic)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _msg(request, "panel_msg_topic_updated"))
        return redirect("panel:essay-topic-list")
    return render(request, "panel/essay_topic_form.html", {"form": form, "topic": topic})


@require_POST
@essay_topic_required
def essay_topic_delete_view(request: HttpRequest, topic_id: int) -> HttpResponse:
    topic = get_object_or_404(EssayTopic, id=topic_id)
    topic.delete()
    messages.success(request, _msg(request, "panel_msg_topic_deleted"))
    return redirect("panel:essay-topic-list")


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------
@admin_required
def user_list_view(request: HttpRequest) -> HttpResponse:
    qs = User.objects.all()
    q = request.GET.get("q", "").strip()
    role = request.GET.get("role", "").strip()
    status = request.GET.get("status", "").strip()  # active | blocked
    joined = request.GET.get("joined", "").strip()  # today | 7d | 30d

    if q:
        qs = qs.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q))
    if role in {c[0] for c in User.Role.choices}:
        qs = qs.filter(role=role)
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "blocked":
        qs = qs.filter(is_active=False)

    from django.utils import timezone

    if joined == "today":
        qs = qs.filter(date_joined__date=timezone.localdate())
    elif joined == "7d":
        qs = qs.filter(date_joined__gte=timezone.now() - timezone.timedelta(days=7))
    elif joined == "30d":
        qs = qs.filter(date_joined__gte=timezone.now() - timezone.timedelta(days=30))

    users = qs.order_by("-date_joined")[:100]
    return render(
        request,
        "panel/user_list.html",
        {
            "users": users,
            "q": q,
            "role": role,
            "status": status,
            "joined": joined,
            "roles": User.Role.choices,
        },
    )


@require_POST
@admin_required
def user_role_view(request: HttpRequest, user_id: int) -> HttpResponse:
    target = get_object_or_404(User, id=user_id)
    new_role = request.POST.get("role", "").strip()
    if new_role not in {c[0] for c in User.Role.choices}:
        messages.error(request, _msg(request, "panel_msg_invalid_role"))
        return redirect("panel:user-list")

    # Never allow the last admin to demote themselves out of access
    if target == request.user and new_role != User.Role.ADMIN:
        messages.error(request, _msg(request, "panel_msg_cannot_demote_self"))
        return redirect("panel:user-list")

    target.role = new_role
    target.save(update_fields=["role"])
    messages.success(request, _msg(request, "panel_msg_role_changed"))
    return redirect("panel:user-list")


@require_POST
@admin_required
def user_block_view(request: HttpRequest, user_id: int) -> HttpResponse:
    target = get_object_or_404(User, id=user_id)
    if target == request.user:
        messages.error(request, _msg(request, "panel_msg_cannot_block_self"))
        return redirect("panel:user-list")
    target.is_active = not target.is_active
    target.save(update_fields=["is_active"])
    key = "panel_msg_user_blocked" if not target.is_active else "panel_msg_user_unblocked"
    messages.success(request, _msg(request, key))
    return redirect("panel:user-list")