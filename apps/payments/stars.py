"""Telegram Stars (XTR) purchase orders.

Grandec sells digital access inside the bot, so Telegram's digital-goods rules
require Telegram Stars. Order lifecycle::

    CREATED ──invoice sent──▶ INVOICE_SENT ──successful_payment──▶ PAID
       │                            │
       └──── cancelled/failed ◀─────┘

Access is activated **only** from a verified ``successful_payment`` update that
matches this order's opaque payload *and* the charged amount. An invoice
creation, a pre-checkout query, or any client-supplied flag must never activate
a subscription.

This module is deliberately transport-free: it takes plain values (never a
Telegram ``Update`` object) so it can be unit-tested without the Telegram
library or a network connection.
"""

from __future__ import annotations

import logging
import secrets

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import (
    EntitlementAuditLog,
    SubscriptionPlan,
    TelegramOrder,
    UserSubscription,
)
from .subscriptions import grant_subscription

logger = logging.getLogger(__name__)

STARS_CURRENCY = "XTR"


def _new_payload() -> str:
    """Opaque, unguessable order payload (never a sequential id)."""
    return f"grandec:{secrets.token_hex(12)}"


def create_order(user, plan: SubscriptionPlan) -> TelegramOrder:
    """Create a pending order for *plan*.

    Raises:
        ValueError: when the plan is not sellable through Telegram.
    """
    if not plan.is_active or not plan.is_public:
        raise ValueError("Bu reja sotuvda emas.")
    if plan.plan_type == SubscriptionPlan.PlanType.TEACHER_SPONSORED:
        raise ValueError("Homiylik tarifi sotilmaydi.")
    amount = plan.telegram_stars_price
    if not amount or amount <= 0:
        raise ValueError(
            "Bu reja uchun Telegram Stars narxi sozlanmagan. "
            "Administrator narxni kiritishi kerak."
        )
    return TelegramOrder.objects.create(
        user=user,
        plan=plan,
        payload=_new_payload(),
        amount_stars=int(amount),
        currency=STARS_CURRENCY,
        status=TelegramOrder.Status.CREATED,
    )


def mark_invoice_sent(order: TelegramOrder) -> TelegramOrder:
    if order.status == TelegramOrder.Status.CREATED:
        order.status = TelegramOrder.Status.INVOICE_SENT
        order.save(update_fields=["status", "updated_at"])
    return order


def cancel_order(order: TelegramOrder) -> TelegramOrder:
    if order.status in {TelegramOrder.Status.CREATED, TelegramOrder.Status.INVOICE_SENT}:
        order.status = TelegramOrder.Status.CANCELLED
        order.save(update_fields=["status", "updated_at"])
    return order


# ---------------------------------------------------------------------------
# Pre-checkout
# ---------------------------------------------------------------------------

def validate_pre_checkout(
    *,
    payload: str,
    currency: str,
    total_amount: int,
) -> tuple[bool, str | None, TelegramOrder | None]:
    """Validate a ``pre_checkout_query``.

    Returns ``(ok, error_message, order)``. The pre-checkout stage never
    activates anything; it only rejects orders that could never be honoured.
    """
    order = TelegramOrder.objects.filter(payload=payload).select_related("plan").first()
    if order is None:
        return False, "Buyurtma topilmadi.", None
    if order.status not in {
        TelegramOrder.Status.CREATED, TelegramOrder.Status.INVOICE_SENT,
    }:
        return False, "Buyurtma holati to'lovga mos emas.", order
    if currency != STARS_CURRENCY:
        return False, "To'lov valyutasi noto'g'ri.", order
    if int(total_amount) != int(order.amount_stars):
        logger.warning(
            "Stars amount mismatch for order %s: expected %s got %s",
            order.payload, order.amount_stars, total_amount,
        )
        return False, "To'lov summasi buyurtmaga mos kelmadi.", order
    plan = order.plan
    if not plan.is_active or not plan.is_public:
        return False, "Reja hozircha mavjud emas.", order
    if int(plan.telegram_stars_price or 0) != int(order.amount_stars):
        # An administrator changed the price after the invoice was issued.
        return False, "Reja narxi o'zgargan. Iltimos, qaytadan urinib ko'ring.", order
    return True, None, order


# ---------------------------------------------------------------------------
# Payment confirmation
# ---------------------------------------------------------------------------

def activate_from_successful_payment(
    *,
    payload: str,
    currency: str,
    total_amount: int,
    telegram_payment_charge_id: str,
    provider_payment_charge_id: str = "",
    raw: dict | None = None,
) -> tuple[bool, str, UserSubscription | None]:
    """Activate the subscription for a verified ``successful_payment``.

    Idempotent: Telegram delivers updates at least once, so a replayed
    ``telegram_payment_charge_id`` returns the already-activated subscription
    instead of granting a second period.
    """
    if not telegram_payment_charge_id:
        return False, "To'lov identifikatori yo'q.", None

    with transaction.atomic():
        order = (
            TelegramOrder.objects.select_for_update()
            .select_related("plan", "user")
            .filter(payload=payload)
            .first()
        )
        if order is None:
            # Unknown payload: could belong to another bot/secret. Never guess.
            logger.warning("successful_payment with unknown payload %r", payload)
            return False, "Buyurtma topilmadi.", None

        if order.status == TelegramOrder.Status.PAID:
            subscription = UserSubscription.objects.filter(user=order.user).first()
            return True, "To'lov allaqachon tasdiqlangan.", subscription

        if currency != STARS_CURRENCY:
            order.status = TelegramOrder.Status.FAILED
            order.raw_payload = raw or {}
            order.save(update_fields=["status", "raw_payload", "updated_at"])
            return False, "To'lov valyutasi noto'g'ri.", None

        if int(total_amount) != int(order.amount_stars):
            order.status = TelegramOrder.Status.FAILED
            order.raw_payload = raw or {}
            order.save(update_fields=["status", "raw_payload", "updated_at"])
            logger.warning(
                "Paid amount mismatch for order %s: expected %s got %s",
                order.payload, order.amount_stars, total_amount,
            )
            return False, "To'lov summasi mos kelmadi.", None

        if int(order.plan.telegram_stars_price or 0) != int(order.amount_stars):
            order.status = TelegramOrder.Status.FAILED
            order.raw_payload = raw or {}
            order.save(update_fields=["status", "raw_payload", "updated_at"])
            return False, "Reja narxi o'zgargan.", None

        if order.status not in {
            TelegramOrder.Status.CREATED, TelegramOrder.Status.INVOICE_SENT,
        }:
            return False, "Buyurtma holati to'lovni qabul qilmaydi.", None

        try:
            order.telegram_payment_charge_id = telegram_payment_charge_id
            order.provider_payment_charge_id = provider_payment_charge_id
            order.raw_payload = raw or {}
            order.status = TelegramOrder.Status.PAID
            order.paid_at = timezone.now()
            # The savepoint is load-bearing: without it the IntegrityError that
            # a concurrent duplicate charge id raises would mark the whole
            # outer transaction as needing rollback, and the follow-up read
            # below would fail with TransactionManagementError on every
            # backend. Same guard as apps/accounts/services/telegram_identity.
            with transaction.atomic():
                order.save(update_fields=[
                    "telegram_payment_charge_id", "provider_payment_charge_id",
                    "raw_payload", "status", "paid_at", "updated_at",
                ])
        except IntegrityError:
            # The same charge id was recorded concurrently — do not double-grant.
            order.refresh_from_db()
            subscription = UserSubscription.objects.filter(user=order.user).first()
            return True, "To'lov allaqachon tasdiqlangan.", subscription

        subscription = grant_subscription(
            order.user,
            order.plan,
            source=UserSubscription.Source.TELEGRAM_BOT,
            payment_method="stars",
            payment_reference=telegram_payment_charge_id,
            actor=None,
            log_action=EntitlementAuditLog.Action.ACTIVATE_SUBSCRIPTION,
        )

    return True, "Obuna faollashtirildi.", subscription


def refund_order(order: TelegramOrder, *, actor=None, reason: str = "") -> bool:
    """Record a Telegram refund and revoke the subscription it granted.

    A refund must never leave paid entitlement in place; the individual
    student's essays and history are untouched.
    """
    with transaction.atomic():
        order = TelegramOrder.objects.select_for_update().get(pk=order.pk)
        if order.status == TelegramOrder.Status.REFUNDED:
            return True
        order.status = TelegramOrder.Status.REFUNDED
        order.save(update_fields=["status", "updated_at"])
        subscription = (
            UserSubscription.objects.select_for_update()
            .filter(user=order.user)
            .first()
        )
        if subscription is not None:
            subscription.status = UserSubscription.Status.REFUNDED
            subscription.cancelled_at = timezone.now()
            subscription.save(update_fields=["status", "cancelled_at", "updated_at"])
        EntitlementAuditLog.objects.create(
            actor=actor,
            student=order.user,
            action=EntitlementAuditLog.Action.REFUND_SUBSCRIPTION,
            details={
                "plan": order.plan.plan_type,
                "payload": order.payload,
                "charge_id": order.telegram_payment_charge_id or "",
                "reason": reason,
            },
        )
    return True


def pending_orders_for(user) -> list[TelegramOrder]:
    return list(
        TelegramOrder.objects.filter(
            user=user,
            status__in=(TelegramOrder.Status.CREATED, TelegramOrder.Status.INVOICE_SENT),
        ).select_related("plan")
    )
