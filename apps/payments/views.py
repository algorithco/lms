"""
Payments views — subscription management, payment processing.
"""
from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import SubscriptionPlan, UserSubscription
from apps.core.spa import serve_spa_shell

logger = logging.getLogger(__name__)


def subscription_plans_view(request: HttpRequest) -> HttpResponse:
    """GET /subscribe/ — SPA shell (React Router owns /subscribe/)."""
    return serve_spa_shell(request, fallback="/")


def subscribe_view(request: HttpRequest, plan_id: int) -> HttpResponse:
    """GET /subscribe/<id>/subscribe/ — SPA shell (manual card flow lives in React)."""
    get_object_or_404(SubscriptionPlan, id=plan_id, is_active=True)
    return serve_spa_shell(request, fallback=f"/subscribe/{plan_id}")


@login_required
def payment_success_view(request: HttpRequest) -> HttpResponse:
    """To'lov cheki yuborilgandan keyin (manual flow) — holat sahifasi."""
    messages.success(request, "Chek qabul qilindi! Admin tekshirgandan so'ng obuna faollashtiriladi.")
    return redirect("payments:my-subscription")


@login_required
def payment_cancel_view(request: HttpRequest) -> HttpResponse:
    """To'lov bekor qilinganda."""
    messages.info(request, "To'lov bekor qilindi.")
    return redirect("payments:plans")


@login_required
def my_subscription_view(request: HttpRequest) -> HttpResponse:
    """GET /subscribe/my/ — SPA shell (React Router owns /my-subscription)."""
    return serve_spa_shell(request, fallback="/my-subscription")


@require_POST
@login_required
def cancel_subscription_view(request: HttpRequest) -> HttpResponse:
    """Obunani bekor qilish."""
    user_sub = getattr(request.user, "subscription", None)

    if not user_sub or not user_sub.is_active:
        messages.error(request, "Faol obuna topilmadi.")
        return redirect("payments:my-subscription")

    user_sub.status = UserSubscription.Status.CANCELLED
    user_sub.cancelled_at = timezone.now()
    user_sub.save(update_fields=["status", "cancelled_at", "updated_at"])

    messages.success(request, "Obuna bekor qilindi. Muddati tugaguncha foydalanishingiz mumkin.")
    return redirect("payments:my-subscription")


@login_required
def subscription_api_view(request: HttpRequest) -> JsonResponse:
    """API — foydalanuvchining obuna holati (AJAX uchun)."""
    user_sub = getattr(request.user, "subscription", None)

    if not user_sub or not user_sub.is_active:
        return JsonResponse({
            "has_subscription": False,
            "plan": "free",
            "features": _get_free_features(),
        })

    return JsonResponse({
        "has_subscription": True,
        "plan": user_sub.plan.plan_type,
        "plan_name": user_sub.plan.name,
        "expires_at": user_sub.expires_at.isoformat() if user_sub.expires_at else None,
        "days_remaining": user_sub.days_remaining,
        "features": _get_plan_features(user_sub.plan),
    })


def _get_free_features() -> dict:
    """Bepul reja imkoniyatlari."""
    return {
        "max_tests_per_day": 5,
        "max_essays_per_week": 2,
        "detailed_analytics": False,
        "pdf_certificate": False,
        "priority_support": False,
        "unlimited_tests": False,
        "unlimited_essays": False,
    }


def _get_plan_features(plan: SubscriptionPlan) -> dict:
    """Reja imkoniyatlari."""
    return {
        "max_tests_per_day": plan.max_tests_per_day,
        "max_essays_per_week": plan.max_essays_per_week,
        "detailed_analytics": plan.detailed_analytics,
        "pdf_certificate": plan.pdf_certificate,
        "priority_support": plan.priority_support,
        "unlimited_tests": plan.unlimited_tests,
        "unlimited_essays": plan.unlimited_essays,
    }


# ---------------------------------------------------------------------------
# Manual payment activation — used by the bot screenshot-approval flow
# (apps/notifications/bot/handlers.py) and the Django admin.
# Automatic Click/Payme checkout was removed: subscriptions are now activated
# only after an admin verifies the Telegram receipt.
# ---------------------------------------------------------------------------
