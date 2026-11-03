"""Canonical subscription lifecycle: activation, upgrade, expiry, revocation.

Every activation path funnels through :func:`grant_subscription`, and only
these kinds are accepted (anything else raises :class:`SubscriptionGrantDenied`):

- ``approved_payment`` — a card receipt / payment request approved by an admin;
- ``provider_payment`` — a verified payment provider callback (Telegram Stars);
- ``admin`` — a platform administrator's manual grant;
- ``teacher_quota`` — a teacher spending one unit of their PRO/PREMIUM quota.

There is no automatic, reward, trial or self-service path. Every grant writes
an :class:`EntitlementAuditLog` row: who, what, when, why.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import (
    EntitlementAuditLog,
    SubscriptionPlan,
    UserSubscription,
)

logger = logging.getLogger(__name__)


class SubscriptionGrantDenied(PermissionError):
    """A subscription grant that does not come from an allowed source."""


GRANT_KINDS = ("approved_payment", "provider_payment", "admin", "teacher_quota")


def _check_grant(kind: str, actor, payment_reference: str, reason: str) -> None:
    from apps.accounts.access import is_platform_admin

    if kind not in GRANT_KINDS:
        raise SubscriptionGrantDenied(f"Unknown subscription grant kind: {kind!r}")
    if not (reason or "").strip():
        raise SubscriptionGrantDenied("A subscription grant needs a reason.")
    if kind in ("admin", "approved_payment") and not is_platform_admin(actor):
        raise SubscriptionGrantDenied(f"{kind} grants need a platform admin actor.")
    if kind in ("approved_payment", "provider_payment") and not payment_reference:
        raise SubscriptionGrantDenied(f"{kind} grants need a payment reference.")
    if kind == "teacher_quota" and not (
        is_platform_admin(actor) or getattr(actor, "role", "") == "teacher"
    ):
        raise SubscriptionGrantDenied("teacher_quota grants need a teacher actor.")

#: Ordering used to decide whether a purchase is an upgrade or a renewal.
#: A renewal of a cheaper plan must never silently downgrade a richer one.
PLAN_RANK: dict[str, int] = {
    SubscriptionPlan.PlanType.FREE: 0,
    SubscriptionPlan.PlanType.TEACHER_SPONSORED: 0,
    SubscriptionPlan.PlanType.START: 10,
    SubscriptionPlan.PlanType.STARTER: 10,
    SubscriptionPlan.PlanType.PRO: 30,
    SubscriptionPlan.PlanType.PREMIUM: 30,
    SubscriptionPlan.PlanType.FAMILY: 40,
}


def plan_rank(plan: SubscriptionPlan | None) -> int:
    if plan is None:
        return 0
    return PLAN_RANK.get(plan.plan_type, 0)


@transaction.atomic
def grant_subscription(
    user,
    plan: SubscriptionPlan,
    *,
    kind: str,
    source: str = UserSubscription.Source.ADMIN,
    payment_method: str = "",
    payment_reference: str = "",
    grant_source: str = "",
    days: int | None = None,
    hours: int | None = None,
    is_trial: bool = False,
    actor=None,
    reason: str = "",
    log_action: str | None = EntitlementAuditLog.Action.ACTIVATE_SUBSCRIPTION,
) -> UserSubscription:
    """Activate or extend *plan* for *user*. Deterministic and repeatable.

    Rules
    -----
    * No active subscription → create one starting now.
    * Active subscription of the **same or lower** rank → upgrade/replace the
      plan and extend from ``max(now, expires_at)``.
    * Active subscription of **higher** rank → keep the richer plan and extend
      its expiry (a START renewal can never downgrade an active PRO).
    * The plan configuration and the effective entitlement are snapshotted onto
      the row, so a later plan edit cannot retroactively change what was bought.
    """
    _check_grant(kind, actor, payment_reference, reason)
    if hours is not None:
        duration = timedelta(hours=int(hours))
    else:
        duration = timedelta(days=int(days or plan.duration_days or 30))
    now = timezone.now()

    existing = UserSubscription.objects.select_for_update().filter(user=user).first()

    if existing is None:
        subscription = UserSubscription.objects.create(
            user=user,
            plan=plan,
            status=UserSubscription.Status.ACTIVE,
            started_at=now,
            expires_at=now + duration,
            payment_method=payment_method,
            payment_reference=payment_reference,
            purchase_source=source,
            grant_source=grant_source,
            is_trial=is_trial,
            trial_days=max(1, (hours // 24) if hours else (days or 1)),
            # Freeze the plan configuration and the effective entitlement at
            # activation time so a later plan edit cannot retroactively change
            # what this student bought.
            plan_snapshot=plan.quota_snapshot(),
            entitlement_snapshot=plan.quota_snapshot(),
        )
        outcome = "created"
    else:
        base = (
            existing.expires_at
            if (existing.expires_at and existing.expires_at > now)
            else now
        )
        current_rank = plan_rank(existing.plan)
        new_rank = plan_rank(plan)
        downgrade_blocked = current_rank > new_rank

        if not downgrade_blocked:
            existing.plan = plan
            existing.plan_snapshot = plan.quota_snapshot()

        existing.status = UserSubscription.Status.ACTIVE
        existing.is_trial = is_trial
        existing.expires_at = base + duration
        existing.purchase_source = source
        existing.grant_source = grant_source or existing.grant_source
        if payment_method:
            existing.payment_method = payment_method
        if payment_reference:
            existing.payment_reference = payment_reference
        if not existing.plan_snapshot:
            existing.plan_snapshot = existing.plan.quota_snapshot()
        existing.entitlement_snapshot = dict(existing.plan_snapshot)
        existing.save()
        subscription = existing
        outcome = "downgrade_blocked" if downgrade_blocked else "extended"

    # Always audited — there is no silent grant.
    EntitlementAuditLog.objects.create(
        actor=actor,
        student=user,
        action=log_action or EntitlementAuditLog.Action.ACTIVATE_SUBSCRIPTION,
        details={
            "kind": kind,
            "plan": plan.plan_type,
            "source": source,
            "grant_source": grant_source,
            "payment_method": payment_method,
            "payment_reference": payment_reference,
            "actor_id": getattr(actor, "pk", None),
            "is_trial": is_trial,
            "outcome": outcome,
            "expires_at": subscription.expires_at.isoformat()
            if subscription.expires_at
            else None,
            "reason": reason,
        },
    )
    logger.info(
        "Subscription %s for user=%s plan=%s source=%s expires=%s",
        outcome,
        user.pk,
        plan.plan_type,
        source,
        subscription.expires_at,
    )
    return subscription


@transaction.atomic
def revoke_subscription(
    user, *, actor=None, reason: str = "", status: str = UserSubscription.Status.REVOKED
) -> bool:
    """Administratively revoke the active subscription (history preserved)."""
    subscription = (
        UserSubscription.objects.select_for_update().filter(user=user).first()
    )
    if subscription is None:
        return False
    subscription.status = status
    subscription.cancelled_at = timezone.now()
    subscription.save(update_fields=["status", "cancelled_at", "updated_at"])
    EntitlementAuditLog.objects.create(
        actor=actor,
        student=user,
        action=EntitlementAuditLog.Action.REVOKE_SUBSCRIPTION,
        details={
            "status": status,
            "reason": reason,
            "plan": subscription.plan.plan_type,
        },
    )
    return True


@transaction.atomic
def expire_overdue_subscriptions() -> int:
    """Flip ACTIVE subscriptions whose expiry has passed to EXPIRED (audited)."""
    now = timezone.now()
    overdue = list(
        UserSubscription.objects.select_for_update()
        .filter(
            status=UserSubscription.Status.ACTIVE,
            expires_at__isnull=False,
            expires_at__lte=now,
        )
        .select_related("plan")
    )
    if not overdue:
        return 0
    UserSubscription.objects.filter(pk__in=[s.pk for s in overdue]).update(
        status=UserSubscription.Status.EXPIRED, updated_at=now
    )
    EntitlementAuditLog.objects.bulk_create(
        [
            EntitlementAuditLog(
                actor=None,
                student_id=s.user_id,
                action=EntitlementAuditLog.Action.EXPIRE_SUBSCRIPTION,
                details={
                    "plan": s.plan.plan_type if s.plan else None,
                    "expires_at": s.expires_at.isoformat(),
                    "reason": "expiry job",
                },
            )
            for s in overdue
        ]
    )
    return len(overdue)


def cancel_subscription(subscription: UserSubscription, *, actor=None) -> None:
    """User-initiated cancellation (access stays until expiry), audited."""
    subscription.status = UserSubscription.Status.CANCELLED
    subscription.cancelled_at = timezone.now()
    subscription.save(update_fields=["status", "cancelled_at", "updated_at"])
    EntitlementAuditLog.objects.create(
        actor=actor,
        student_id=subscription.user_id,
        action=EntitlementAuditLog.Action.CANCEL_SUBSCRIPTION,
        details={
            "plan": subscription.plan.plan_type if subscription.plan else None,
            "expires_at": subscription.expires_at.isoformat() if subscription.expires_at else None,
            "reason": "cancelled by user",
        },
    )


def subscription_expiring_between(delta: timedelta) -> list[UserSubscription]:
    """Active subscriptions expiring within *delta* (for reminder notifications)."""
    now = timezone.now()
    return list(
        UserSubscription.objects.filter(
            status=UserSubscription.Status.ACTIVE,
            expires_at__gt=now,
            expires_at__lte=now + delta,
        ).select_related("user", "plan")
    )
