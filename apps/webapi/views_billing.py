"""Billing JSON API — same data as apps/payments/views.py, JSON in/out."""
from __future__ import annotations

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.payments.models import PaymentHistory, SubscriptionPlan, UserSubscription

from .serializers import (
    PaymentHistorySerializer,
    SubscriptionPlanSerializer,
    UserSubscriptionSerializer,
)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def plans_view(request):
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by("sort_order")
    sub = getattr(request.user, "subscription", None)
    return Response({
        "results": SubscriptionPlanSerializer(plans, many=True).data,
        "my_plan_id": sub.plan_id if sub else None,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_view(request):
    sub = getattr(request.user, "subscription", None)
    history = PaymentHistory.objects.filter(user=request.user)[:10]
    return Response({
        "subscription": UserSubscriptionSerializer(sub).data if sub else None,
        "history": PaymentHistorySerializer(history, many=True).data,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def subscribe_info_view(request, plan_id: int):
    """Manual card-transfer instructions (same ctx as subscribe_view)."""
    plan = get_object_or_404(SubscriptionPlan, id=plan_id, is_active=True)
    return Response({
        "plan": SubscriptionPlanSerializer(plan).data,
        "card_number": settings.PAYMENT_CARD_NUMBER,
        "card_bank": settings.PAYMENT_CARD_BANK,
        "card_holder": settings.PAYMENT_CARD_HOLDER,
        "admin_username": settings.PAYMENT_ADMIN_USERNAME,
        "bot_name": settings.TELEGRAM_BOT_NAME,
        "free": plan.price_monthly <= 0,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cancel_view(request):
    sub = getattr(request.user, "subscription", None)
    if not sub or not sub.is_active:
        return Response({"detail": "No active subscription."}, status=400)
    sub.status = UserSubscription.Status.CANCELLED
    sub.cancelled_at = timezone.now()
    sub.save(update_fields=["status", "cancelled_at", "updated_at"])
    return Response(UserSubscriptionSerializer(sub).data)
