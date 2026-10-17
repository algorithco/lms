import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

logger = logging.getLogger(__name__)

from apps.payments.entitlements import (
    can_start_test,
    can_submit_essay,
    get_remaining_limits,
)
from apps.payments.models import (
    PaymentHistory,
    PaymentReceipt,
    SubscriptionPlan,
    SubscriptionUsage,
    UserSubscription,
)

from .serializers import (
    PaymentHistorySerializer,
    PaymentReceiptSerializer,
    SubscriptionPlanSerializer,
    UserSubscriptionSerializer,
)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def plans_view(request):
    """Public plan catalogue.

    Only plans an administrator has published (``is_public``) are listed, so
    the non-purchasable sponsored tier and the default-policy row never appear
    in the store. ``my_plan_id`` is derived from the user's subscription rather
    than from the filtered list, so a subscriber whose plan was later made
    non-public still sees which plan they are on.
    """
    plans = SubscriptionPlan.objects.filter(
        is_active=True, is_public=True,
    ).order_by("sort_order")
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
    free = plan.price_monthly <= 0
    payment_configured = all((
        settings.PAYMENT_CARD_NUMBER,
        settings.PAYMENT_CARD_BANK,
        settings.PAYMENT_CARD_HOLDER,
        settings.PAYMENT_ADMIN_USERNAME,
    ))
    return Response({
        "plan": SubscriptionPlanSerializer(plan).data,
        "card_number": settings.PAYMENT_CARD_NUMBER if payment_configured else "",
        "card_bank": settings.PAYMENT_CARD_BANK if payment_configured else "",
        "card_holder": settings.PAYMENT_CARD_HOLDER if payment_configured else "",
        "admin_username": settings.PAYMENT_ADMIN_USERNAME if payment_configured else "",
        "bot_name": settings.TELEGRAM_BOT_NAME,
        "free": free,
        "payment_available": free or payment_configured,
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


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def entitlement_view(request):
    """GET /api/v1/billing/entitlement/ — the canonical entitlement read model.

    The website, the Telegram bot and the Telegram Mini App all describe a
    student's plan, remaining quotas and text-essay cooldown from this single
    shape. Every number here is calculated server-side by
    ``apps.payments.entitlements``; clients never infer or enforce a limit.
    """
    remaining = get_remaining_limits(request.user)
    can_image = can_submit_essay(
        request.user, SubscriptionUsage.Kind.IMAGE_ESSAY,
    )[0]
    can_text = can_submit_essay(
        request.user, SubscriptionUsage.Kind.TEXT_ESSAY,
    )[0]
    can_test = can_start_test(request.user)[0]
    return Response({
        **remaining,
        "can_submit_image_essay": can_image,
        "can_submit_text_essay": can_text,
        "can_start_test": can_test,
    })


@api_view(["GET"])
@permission_classes([AllowAny])
def card_info_view(request):
    """GET /api/v1/payments/card-info/ — Public card and plan price settings."""
    card_number = getattr(settings, "PAYMENT_CARD_NUMBER", "") or "9860 **** **** ****"
    card_holder = getattr(settings, "PAYMENT_CARD_HOLDER", "") or "KOMILJON R"
    starter_price = getattr(settings, "PLAN_STARTER_PRICE", 0) or 15000
    pro_price = getattr(settings, "PLAN_PRO_PRICE", 0) or 49000
    premium_price = getattr(settings, "PLAN_PREMIUM_PRICE", 0) or 60000
    return Response({
        "card_number": card_number,
        "card_holder": card_holder,
        "starter_price": starter_price,
        "pro_price": pro_price,
        "premium_price": premium_price,
        "plans": {
            "starter": {"name": "Starter", "price": starter_price, "label": f"{starter_price:,} so'm/oy".replace(",", " ")},
            "pro": {"name": "Pro", "price": pro_price, "label": f"{pro_price:,} so'm/oy".replace(",", " ")},
            "premium": {"name": "Premium", "price": premium_price, "label": f"{premium_price:,} so'm/oy".replace(",", " ")},
        },
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def payment_receipt_upload_view(request):
    """POST /api/v1/payments/receipts/ — Upload card payment screenshot/receipt."""
    plan = str(request.data.get("plan", "")).strip().lower()
    if plan not in ("starter", "pro", "premium"):
        return Response({"detail": "Tarif 'starter', 'pro' yoki 'premium' bo'lishi kerak."}, status=400)

    amount_val = request.data.get("amount")
    default_amounts = {
        "starter": getattr(settings, "PLAN_STARTER_PRICE", 15000),
        "pro": getattr(settings, "PLAN_PRO_PRICE", 49000),
        "premium": getattr(settings, "PLAN_PREMIUM_PRICE", 60000),
    }
    if amount_val:
        try:
            amount = Decimal(str(amount_val))
        except (InvalidOperation, ValueError):
            amount = Decimal(default_amounts.get(plan, 15000))
    else:
        amount = Decimal(default_amounts.get(plan, 15000))

    receipt_image = request.FILES.get("receipt_image")
    if not receipt_image:
        return Response({"detail": "To'lov cheki rasmi yuklanishi shart."}, status=400)

    from apps.payments.services import validate_and_hash_receipt_image, notify_admin_new_receipt

    try:
        image_hash, _raw_bytes = validate_and_hash_receipt_image(receipt_image)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=400)

    receipt = PaymentReceipt.objects.create(
        user=request.user,
        plan=plan,
        amount=amount,
        receipt_image=receipt_image,
        image_hash=image_hash,
        source=PaymentReceipt.Source.WEB,
        status=PaymentReceipt.Status.PENDING,
    )

    try:
        notify_admin_new_receipt(receipt)
    except Exception as exc:
        logger.warning("Failed to notify admin of receipt #%s: %s", receipt.id, exc)

    return Response(PaymentReceiptSerializer(receipt).data, status=201)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_payment_receipts_view(request):
    """GET /api/v1/payments/my-receipts/ — User's uploaded payment receipts."""
    receipts = PaymentReceipt.objects.filter(user=request.user).order_by("-created_at")
    return Response({
        "results": PaymentReceiptSerializer(receipts, many=True).data
    })

