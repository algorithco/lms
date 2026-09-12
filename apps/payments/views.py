"""
Payments views — subscription management, payment processing.
"""
from __future__ import annotations

import logging
import secrets
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import PaymentHistory, SubscriptionPlan, UserSubscription

logger = logging.getLogger(__name__)


@login_required
def subscription_plans_view(request: HttpRequest) -> HttpResponse:
    """Obuna rejalarini ko'rish sahifasi."""
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by("sort_order")

    # Foydalanuvchining joriy obunasi
    user_sub = getattr(request.user, "subscription", None)

    ctx = {
        "plans": plans,
        "user_subscription": user_sub,
    }
    return render(request, "payments/plans.html", ctx)


@login_required
def subscribe_view(request: HttpRequest, plan_id: int) -> HttpResponse:
    """Obuna sotib olish — Telegram manual to'lov ko'rsatmalari.

    To'lov kartaga o'tkazma orqali: foydalanuvchi kartaga pul o'tkazadi,
    chek screenshot'ini Telegram orqali admin(@rozievkomiljon)ga yuboradi,
    admin tekshirib obunani faollashtiradi.
    """
    plan = get_object_or_404(SubscriptionPlan, id=plan_id, is_active=True)

    if plan.price_monthly <= 0:
        # Bepul reja — to'lov talab qilinmaydi
        messages.info(request, "Bepul reja uchun to'lov talab qilinmaydi.")
        return redirect("payments:plans")

    from apps.core.translations import t as translate, get_user_language

    ctx = {
        "plan": plan,
        "payment_card": settings.PAYMENT_CARD_NUMBER,
        "payment_card_bank": settings.PAYMENT_CARD_BANK,
        "payment_card_holder": settings.PAYMENT_CARD_HOLDER,
        "payment_admin_username": settings.PAYMENT_ADMIN_USERNAME,
        "telegram_bot_name": settings.TELEGRAM_BOT_NAME,
        "copied_label": translate("pay_copied", get_user_language(request)),
    }
    return render(request, "payments/subscribe.html", ctx)


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
    """Mening obunam sahifasi."""
    user_sub = getattr(request.user, "subscription", None)
    payment_history = PaymentHistory.objects.filter(user=request.user)[:10]

    ctx = {
        "user_subscription": user_sub,
        "payment_history": payment_history,
    }
    return render(request, "payments/my_subscription.html", ctx)


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
