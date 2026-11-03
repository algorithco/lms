"""Feedback API.

- POST /api/v1/feedback/            submit (guest or signed-in), 5 per hour
- GET  /api/v1/feedback/public/     admin-approved AND consented feedback only
- GET  /api/v1/feedback/mine/       the signed-in user's own feedback + admin replies
- GET  /api/v1/panel/feedback/      admin inbox (filters, search, stats)
- PATCH /api/v1/panel/feedback/<id>/  status / reply / publish (consent required)

Nothing here stores or forwards passwords, tokens, e-mail or phone numbers.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, time

from django.db import transaction
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.html import strip_tags
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.notifications.models import UserFeedback

from .permissions import IsPanelAdmin

logger = logging.getLogger(__name__)

MIN_MESSAGE = 3
MAX_MESSAGE = 2000
MAX_NAME = 80
PAGE_SIZE = 20

# Only these context keys are kept, each truncated; everything else is dropped.
CONTEXT_LIMITS = {
    "path": 200, "subject": 20, "lang": 5, "device": 20, "browser": 120, "source": 30, "last_error": 300,
}
_SECRET = re.compile(r"(eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-\.]+|(?i:bearer|token|password|passwd|secret|authorization|cookie)[=:\s]+\S+)")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_text(value: object, limit: int) -> str:
    """Plain text only: tags stripped, control chars removed, length capped."""
    text = strip_tags(str(value or ""))
    text = _CONTROL.sub("", text).strip()
    return text[:limit]


def clean_context(raw: object, user, request: Request) -> dict:
    ctx: dict = {}
    if isinstance(raw, dict):
        for key, limit in CONTEXT_LIMITS.items():
            if key in raw:
                text = _SECRET.sub("[hidden]", clean_text(raw[key], limit))
                if text:
                    ctx[key] = text
    # Role and plan come from the server, never from the client.
    if user is not None:
        from apps.payments.ai_quota import get_user_plan_tier

        ctx["role"] = getattr(user, "role", "") or ""
        ctx["plan"] = get_user_plan_tier(user)
    else:
        ctx["role"] = "guest"
    ctx.setdefault("browser", clean_text(request.META.get("HTTP_USER_AGENT", ""), 120))
    return ctx


def _client_ip(request: Request) -> str:
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (fwd.split(",")[0].strip() if fwd else request.META.get("REMOTE_ADDR", ""))[:45]


class FeedbackView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "feedback-submit"

    def post(self, request: Request) -> Response:
        data = request.data or {}

        # Honeypot: real users never fill the hidden field.
        if str(data.get("website", "")).strip():
            return Response({"success": True, "message": "ok"}, status=status.HTTP_201_CREATED)

        message = clean_text(data.get("message", ""), MAX_MESSAGE + 1)
        if len(message) < MIN_MESSAGE:
            return Response({"error": "message_too_short", "field": "message"}, status=status.HTTP_400_BAD_REQUEST)
        if len(message) > MAX_MESSAGE:
            return Response({"error": "message_too_long", "field": "message"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            rating = int(data.get("rating"))
        except (TypeError, ValueError):
            rating = 0
        if not 1 <= rating <= 5:
            return Response({"error": "rating_required", "field": "rating"}, status=status.HTTP_400_BAD_REQUEST)

        category = str(data.get("category") or UserFeedback.Category.FEEDBACK).strip().lower()
        if category not in {c.value for c in UserFeedback.Category}:
            return Response({"error": "bad_category", "field": "category"}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user if request.user and request.user.is_authenticated else None
        name = (user.get_full_name() or "") if user else clean_text(data.get("name", ""), MAX_NAME)

        # The same text from the same sender in the last 10 minutes is a double click.
        since = timezone.now() - timezone.timedelta(minutes=10)
        dupes = UserFeedback.objects.filter(message=message, created_at__gte=since)
        dupes = dupes.filter(user=user) if user else dupes.filter(user__isnull=True, user_name=name)
        if dupes.exists():
            return Response({"success": True, "duplicate": True, "id": dupes.first().pk}, status=status.HTTP_200_OK)

        feedback = UserFeedback.objects.create(
            user=user,
            user_name=name,
            rating=rating,
            category=category,
            message=message,
            consent_public=bool(data.get("consent_public")) and bool(name),
            context=clean_context(data.get("context"), user, request),
        )
        context_ip = _client_ip(request)
        logger.info("feedback #%s category=%s rating=%s ip=%s", feedback.pk, category, rating, context_ip)

        def _notify() -> None:
            try:
                from apps.notifications.tasks import notify_admin_new_feedback

                notify_admin_new_feedback.delay(feedback.pk)
            except Exception as exc:  # broker down must never fail the submission
                logger.warning("Could not queue admin notification for feedback #%s: %s", feedback.pk, exc)

        transaction.on_commit(_notify)
        return Response({"success": True, "id": feedback.pk}, status=status.HTTP_201_CREATED)


class PublicFeedbackListView(APIView):
    """Only feedback an admin published AND whose author agreed to be shown."""

    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        rows = (
            UserFeedback.objects.filter(is_published=True, consent_public=True)
            .select_related("user")
            .order_by("-created_at")[:30]
        )
        role_labels = {"student": "student", "teacher": "teacher"}
        results = [
            {
                "id": fb.pk,
                "name": fb.short_name,
                "role": role_labels.get(getattr(fb.user, "role", ""), "user"),
                "rating": fb.rating,
                "category": fb.category,
                "message": fb.message,
                "created_at": fb.created_at.strftime("%Y-%m-%d"),
            }
            for fb in rows
        ]
        return Response({"results": results, "count": len(results)})


class MyFeedbackView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        rows = UserFeedback.objects.filter(user=request.user).order_by("-created_at")[:50]
        return Response(
            {
                "results": [
                    {
                        "id": fb.pk,
                        "rating": fb.rating,
                        "category": fb.category,
                        "message": fb.message,
                        "status": fb.status,
                        "admin_reply": fb.admin_reply,
                        "replied_at": fb.replied_at.isoformat() if fb.replied_at else None,
                        "created_at": fb.created_at.isoformat(),
                    }
                    for fb in rows
                ]
            }
        )


def _admin_row(fb: UserFeedback) -> dict:
    return {
        "id": fb.pk,
        "user_id": fb.user_id,
        "name": fb.name,
        "rating": fb.rating,
        "category": fb.category,
        "message": fb.message,
        "status": fb.status,
        "context": fb.context or {},
        "consent_public": fb.consent_public,
        "is_published": fb.is_published,
        "admin_reply": fb.admin_reply,
        "replied_at": fb.replied_at.isoformat() if fb.replied_at else None,
        "created_at": fb.created_at.isoformat(),
    }


class AdminFeedbackListView(APIView):
    permission_classes = [IsPanelAdmin]

    def get(self, request: Request) -> Response:
        qs = UserFeedback.objects.select_related("user")
        p = request.query_params
        if p.get("category") in {c.value for c in UserFeedback.Category}:
            qs = qs.filter(category=p["category"])
        if p.get("status") in {c.value for c in UserFeedback.Status}:
            qs = qs.filter(status=p["status"])
        if p.get("rating", "").isdigit():
            qs = qs.filter(rating=int(p["rating"]))
        for key, op in (("date_from", "gte"), ("date_to", "lte")):
            try:
                day = datetime.strptime(p.get(key, ""), "%Y-%m-%d").date()
            except ValueError:
                continue
            bound = datetime.combine(day, time.min if op == "gte" else time.max)
            qs = qs.filter(**{f"created_at__{op}": timezone.make_aware(bound)})
        q = (p.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(message__icontains=q) | Q(user_name__icontains=q) | Q(admin_reply__icontains=q))

        total = qs.count()
        page = max(1, int(p["page"])) if p.get("page", "").isdigit() else 1
        rows = qs.order_by("-created_at")[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]
        all_rows = UserFeedback.objects
        stats = {
            "total": all_rows.count(),
            "average_rating": round(all_rows.aggregate(a=Avg("rating"))["a"] or 0, 2),
            "by_status": dict(all_rows.values_list("status").annotate(n=Count("id"))),
            "by_category": dict(all_rows.values_list("category").annotate(n=Count("id"))),
        }
        return Response({"count": total, "page": page, "page_size": PAGE_SIZE, "results": [_admin_row(f) for f in rows], "stats": stats})


class AdminFeedbackDetailView(APIView):
    permission_classes = [IsPanelAdmin]

    def get(self, request: Request, pk: int) -> Response:
        return Response(_admin_row(get_object_or_404(UserFeedback, pk=pk)))

    def patch(self, request: Request, pk: int) -> Response:
        fb = get_object_or_404(UserFeedback, pk=pk)
        data = request.data or {}
        fields: list[str] = []

        if "status" in data:
            if data["status"] not in {s.value for s in UserFeedback.Status}:
                return Response({"error": "bad_status"}, status=status.HTTP_400_BAD_REQUEST)
            fb.status = data["status"]
            fields.append("status")

        if "is_published" in data:
            publish = bool(data["is_published"])
            if publish and not fb.consent_public:
                return Response({"error": "no_consent"}, status=status.HTTP_400_BAD_REQUEST)
            fb.is_published = publish
            fields.append("is_published")

        reply_sent = False
        if "admin_reply" in data:
            reply = clean_text(data["admin_reply"], MAX_MESSAGE)
            if reply != fb.admin_reply:
                fb.admin_reply = reply
                fb.replied_at = timezone.now() if reply else None
                fb.replied_by = request.user if reply else None
                fields += ["admin_reply", "replied_at", "replied_by"]
                reply_sent = bool(reply)

        if fields:
            fb.save(update_fields=fields)
        if reply_sent:

            def _send() -> None:
                try:
                    from apps.notifications.tasks import send_feedback_reply

                    send_feedback_reply.delay(fb.pk)
                except Exception as exc:
                    logger.warning("Could not queue reply for feedback #%s: %s", fb.pk, exc)

            transaction.on_commit(_send)
        return Response(_admin_row(fb))
