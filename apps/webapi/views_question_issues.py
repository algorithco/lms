"""Question issues: "Problem with this question?" reports from the result page.

- POST /api/v1/feedback/question-issue/    signed in; one active report per user and question
- GET  /api/v1/panel/feedback/questions/   admin: reports grouped by question

A question with REVIEW_THRESHOLD or more active reports is flagged ``needs_review``
and the admin gets ONE summary message in Telegram (not one per report). The
report context carries test, section, part and number — never the answer key.
"""

from __future__ import annotations

import logging

from django.db import connection, transaction
from django.db.models import Count, Max, Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.notifications.models import UserFeedback

from .permissions import IsPanelAdmin
from .views_feedback import MAX_MESSAGE, MIN_MESSAGE, clean_text

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = (UserFeedback.Status.NEW, UserFeedback.Status.SEEN, UserFeedback.Status.IN_PROGRESS)
REVIEW_THRESHOLD = 3
MAX_GIVEN = 200


def _can_report(user, question) -> bool:
    """Only people who sat the test (or staff) can say a question is wrong."""
    from apps.accounts.access import is_platform_admin
    from apps.tests.models import TestAttempt

    if is_platform_admin(user) or getattr(user, "role", "") == "teacher":
        return True
    return TestAttempt.objects.filter(student=user, test_id=question.test_id).exists()


def question_label(question) -> dict:
    """Test, section, part and number of a question. No answer key."""
    from apps.tests.numbering import number_map

    group = question.group
    numbered = number_map(question.test, question.test.questions.select_related("section")).get(question.pk)
    return {
        "test_id": question.test_id,
        "test": clean_text(question.test.title, 120),
        "question_id": question.pk,
        "number": numbered.key if numbered else "",
        "section": clean_text(question.section.name, 60) if question.section_id else "",
        "part": clean_text(group.part.number, 10) if group else "",
    }


class QuestionIssueView(APIView):
    """POST {question_id, reason, comment?, given?}"""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "question-issue"

    def post(self, request: Request) -> Response:
        from apps.tests.models import Question

        data = request.data or {}
        reason = str(data.get("reason") or "").strip()
        if reason not in {r.value for r in UserFeedback.IssueReason}:
            return Response({"error": "bad_reason", "field": "reason"}, status=status.HTTP_400_BAD_REQUEST)
        comment = clean_text(data.get("comment", ""), MAX_MESSAGE)
        if reason == UserFeedback.IssueReason.OTHER and len(comment) < MIN_MESSAGE:
            return Response({"error": "comment_required", "field": "comment"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            question_id = int(data.get("question_id"))
        except (TypeError, ValueError):
            return Response({"error": "bad_question", "field": "question_id"}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        with transaction.atomic():
            qs = Question.objects.select_related("test", "section", "group", "group__part").filter(pk=question_id)
            if connection.features.has_select_for_update:
                qs = qs.select_for_update(of=("self",))  # serialises concurrent reports of one question
            question = qs.first()
            if question is None or not _can_report(user, question):
                return Response({"error": "not_allowed"}, status=status.HTTP_403_FORBIDDEN)

            existing = UserFeedback.objects.filter(user=user, question=question, status__in=ACTIVE_STATUSES).first()
            if existing:
                return Response({"success": True, "duplicate": True, "id": existing.pk}, status=status.HTTP_200_OK)

            context = question_label(question)
            given = clean_text(data.get("given", ""), MAX_GIVEN)
            if given:
                context["given"] = given
            context["role"] = getattr(user, "role", "") or ""
            feedback = UserFeedback.objects.create(
                user=user,
                user_name=user.get_full_name() or "",
                rating=0,
                category=UserFeedback.Category.QUESTION_ISSUE,
                reason=reason,
                question=question,
                message=comment or dict(UserFeedback.IssueReason.choices)[reason],
                context=context,
            )
            flagged = False
            active = UserFeedback.objects.filter(question=question, status__in=ACTIVE_STATUSES).count()
            if active >= REVIEW_THRESHOLD:
                # Flips once; only the request that flips it sends the summary.
                flagged = bool(Question.objects.filter(pk=question.pk, needs_review=False).update(needs_review=True))

        if flagged:

            def _notify() -> None:
                try:
                    from apps.notifications.tasks import notify_admin_question_needs_review

                    notify_admin_question_needs_review.delay(question.pk)
                except Exception as exc:  # a broker outage must never fail the report
                    logger.warning("Could not queue review summary for question #%s: %s", question.pk, exc)

            transaction.on_commit(_notify)
        return Response({"success": True, "id": feedback.pk, "needs_review": flagged}, status=status.HTTP_201_CREATED)


class AdminQuestionIssueGroupsView(APIView):
    """Reports grouped by question, most complained-about first."""

    permission_classes = [IsPanelAdmin]

    def get(self, request: Request) -> Response:
        from apps.tests.models import Question

        base = UserFeedback.objects.filter(category=UserFeedback.Category.QUESTION_ISSUE, question__isnull=False)
        rows = list(
            base.values("question_id")
            .annotate(total=Count("id"), active=Count("id", filter=Q(status__in=ACTIVE_STATUSES)), latest=Max("created_at"))
            .order_by("-active", "-latest")[:100]
        )
        questions = {
            q.pk: q for q in Question.objects.filter(pk__in=[r["question_id"] for r in rows]).select_related("test")
        }
        reasons: dict[int, dict[str, int]] = {}
        for r in (
            base.filter(question_id__in=list(questions), status__in=ACTIVE_STATUSES)
            .values("question_id", "reason")
            .annotate(n=Count("id"))
        ):
            reasons.setdefault(r["question_id"], {})[r["reason"]] = r["n"]

        results = []
        for r in rows:
            q = questions.get(r["question_id"])
            if q is None:
                continue
            results.append(
                {
                    "question_id": q.pk,
                    "test_id": q.test_id,
                    "test": q.test.title,
                    "text": clean_text(q.text, 160),
                    "total": r["total"],
                    "active": r["active"],
                    "needs_review": q.needs_review,
                    "reasons": reasons.get(q.pk, {}),
                    "latest": r["latest"].isoformat() if r["latest"] else None,
                    "edit_path": f"/panel/tests/{q.test_id}/questions",
                }
            )
        return Response({"results": results, "threshold": REVIEW_THRESHOLD})
