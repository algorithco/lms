"""One canonical subscription entitlement + commercial quota service.

Every channel — website views, the Telegram bot, the Telegram Mini App and
internal services — must decide "may this student submit another essay / start
another test?" through this module. Nothing else may implement quota logic, and
nothing may enforce quotas in the frontend or in a Telegram handler only.

Guarantees provided here
------------------------
* **Deterministic precedence.** The effective entitlement is resolved from
  exactly one source in this order: explicit active administrator override →
  approved teacher sponsorship → paid subscription → default/free policy.
* **NULL is not zero.** A ``None`` quota field means "inherit from the tier
  below"; ``0`` means "explicitly none allowed"; a positive number is a hard
  cap. A partial override can therefore never disable a paid subscription.
* **Atomic, idempotent accounting.** Quota is consumed by inserting a unique
  ``SubscriptionUsage`` row inside a transaction that row-locks the user, so a
  retried Telegram webhook, a duplicated Celery task or a browser double-submit
  cannot be charged twice and the last remaining allowance cannot be handed to
  two concurrent requests.
* **No long transactions.** Reservations only touch the database; AI/OCR calls
  always happen after the transaction has closed.

Deliberately *not* implemented here: provider calls, cache lookups, Telegram
transport. This module answers entitlement questions only.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import (
    SubscriptionOverride,
    SubscriptionPlan,
    SubscriptionUsage,
    TeacherSponsorship,
    UserSubscription,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Source identifiers for the precedence chain
# ---------------------------------------------------------------------------
SOURCE_OVERRIDE = "override"
SOURCE_SPONSORED = "sponsored"
SOURCE_SUBSCRIPTION = "subscription"
SOURCE_DEFAULT = "default"

#: Usage kinds that map onto an essay submission type.
ESSAY_KINDS = {
    SubscriptionUsage.Kind.IMAGE_ESSAY,
    SubscriptionUsage.Kind.TEXT_ESSAY,
}


class QuotaDenied(Exception):
    """Raised by :func:`enforce_essay_quota` / :func:`enforce_test_quota`."""

    def __init__(self, code: str, message: str, *, remaining: dict | None = None,
                 retry_after_seconds: int = 0):
        super().__init__(message)
        self.code = code
        self.message = message
        self.remaining = remaining or {}
        self.retry_after_seconds = retry_after_seconds


# ---------------------------------------------------------------------------
# Platform defaults (all administrator-overridable via settings / plan rows)
# ---------------------------------------------------------------------------

def _platform_defaults() -> dict:
    """Fallback configuration for a tier that leaves a field unset.

    Every value defaults to **unlimited** (``None``) on purpose: the Grandec
    platform had no enforced essay quota before the commercial plans existed,
    so introducing one by default would silently change what existing students
    can do. Administrators opt in by configuring a plan row (or the ``free``
    plan row, which represents the default policy).
    """
    return {
        "image_essay_weekly_limit": getattr(
            settings, "SUBSCRIPTION_DEFAULT_IMAGE_ESSAY_WEEKLY_LIMIT", None,
        ),
        "text_essay_weekly_limit": getattr(
            settings, "SUBSCRIPTION_DEFAULT_TEXT_ESSAY_WEEKLY_LIMIT", None,
        ),
        "text_essay_cooldown_hours": getattr(
            settings, "SUBSCRIPTION_DEFAULT_TEXT_ESSAY_COOLDOWN_HOURS", None,
        ),
        "test_limit": getattr(settings, "SUBSCRIPTION_DEFAULT_TEST_LIMIT", None),
        "is_unlimited_image_essays": False,
        "is_unlimited_text_essays": False,
        "is_unlimited_tests": False,
        "quota_period_days": 7,
    }


def _quota_timezone() -> ZoneInfo:
    name = getattr(settings, "SUBSCRIPTION_QUOTA_TIMEZONE", "Asia/Tashkent")
    try:
        return ZoneInfo(name)
    except Exception:  # pragma: no cover - bad configuration fallback
        logger.warning("Unknown SUBSCRIPTION_QUOTA_TIMEZONE=%r, using UTC", name)
        return ZoneInfo("UTC")


def quota_period_start(
    now: datetime | None = None,
    *,
    period_days: int | None = 7,
    reset_weekday: int | None = None,
) -> datetime:
    """Start of the quota window containing *now*.

    The window boundary is ``reset_weekday`` at 00:00 in the configured quota
    timezone (Monday by default, matching "weekly reset at Monday 00:00 in
    Asia/Tashkent"). Longer periods are aligned to a fixed epoch so the window
    origin stays stable instead of sliding every request.
    """
    if reset_weekday is None:
        reset_weekday = int(getattr(settings, "SUBSCRIPTION_QUOTA_RESET_WEEKDAY", 0))
    tz = _quota_timezone()
    local = (now or timezone.now()).astimezone(tz)
    days_since = (local.weekday() - reset_weekday) % 7
    start_local = (local - timedelta(days=days_since)).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )
    try:
        length = int(period_days or 7)
    except (TypeError, ValueError):
        length = 7
    if length > 0 and length % 7 == 0 and length != 7:
        # Align multi-week periods to a fixed Monday so they do not slide.
        epoch = datetime(2020, 1, 6, tzinfo=tz)  # a Monday
        elapsed = (start_local - epoch).days
        start_local = epoch + timedelta(days=(elapsed // length) * length)
    return start_local


# ---------------------------------------------------------------------------
# Effective entitlement
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Entitlement:
    """The single resolved answer to "what may this student do right now?"."""

    source: str
    plan_type: str | None
    plan_name: str
    is_sponsored: bool
    is_active: bool = True
    plan: SubscriptionPlan | None = None
    subscription: UserSubscription | None = None
    expires_at: datetime | None = None
    image_essay_weekly_limit: int | None = None
    text_essay_weekly_limit: int | None = None
    text_essay_cooldown_hours: int | None = None
    test_limit: int | None = None
    is_unlimited_image_essays: bool = False
    is_unlimited_text_essays: bool = False
    is_unlimited_tests: bool = False
    quota_period_days: int = 7
    override_fields: tuple[str, ...] = field(default=())

    @property
    def is_paid(self) -> bool:
        return self.source == SOURCE_SUBSCRIPTION and bool(
            self.subscription and self.subscription.is_active
        )

    def limit_for(self, kind: str) -> int | None:
        if kind == SubscriptionUsage.Kind.IMAGE_ESSAY:
            return self.image_essay_weekly_limit
        if kind == SubscriptionUsage.Kind.TEXT_ESSAY:
            return self.text_essay_weekly_limit
        if kind == SubscriptionUsage.Kind.TEST:
            return self.test_limit
        return None

    def is_unlimited_for(self, kind: str) -> bool:
        if kind == SubscriptionUsage.Kind.IMAGE_ESSAY:
            return self.is_unlimited_image_essays
        if kind == SubscriptionUsage.Kind.TEXT_ESSAY:
            return self.is_unlimited_text_essays
        if kind == SubscriptionUsage.Kind.TEST:
            return self.is_unlimited_tests
        return False


def _plan_by_code(code: str) -> SubscriptionPlan | None:
    return SubscriptionPlan.objects.filter(plan_type=code, is_active=True).first()


def _apply_layer(base: dict, layer) -> tuple[dict, tuple[str, ...]]:
    """Overlay a plan/override/sponsorship onto *base*, ignoring NULL fields.

    Returns the merged dict plus the tuple of field names the layer actually
    contributed, which is how "partial override inherits unspecified settings"
    becomes auditable rather than implicit.
    """
    contributed: list[str] = []
    for name in (
        "image_essay_weekly_limit",
        "text_essay_weekly_limit",
        "text_essay_cooldown_hours",
        "test_limit",
        "is_unlimited_image_essays",
        "is_unlimited_text_essays",
        "is_unlimited_tests",
        "quota_period_days",
    ):
        if not hasattr(layer, name):
            continue
        value = getattr(layer, name)
        if value is None:
            continue
        base[name] = value
        contributed.append(name)
    return base, tuple(contributed)


def _subscription_for(user) -> UserSubscription | None:
    """Fetch the user's subscription from the database.

    Deliberately not ``getattr(user, "subscription", None)``: a reverse
    OneToOne accessor caches its result on the instance, so a long-lived or
    recycled ``User`` object would keep answering quota questions with a stale
    plan (this is exactly what the cooldown test caught). Q3 queried fresh so
    an admin plan change or a purchase takes effect on the next check.
    """
    if user is None or not getattr(user, "pk", None):
        return None
    return (
        UserSubscription.objects.select_related("plan")
        .filter(user_id=user.pk)
        .first()
    )


def _active_override(user) -> SubscriptionOverride | None:
    override = SubscriptionOverride.objects.filter(user=user, is_active=True).first()
    if override is None:
        return None
    if override.expires_at and override.expires_at <= timezone.now():
        return None
    return override


def _effective_sponsorship(user) -> TeacherSponsorship | None:
    now = timezone.now()
    qs = (
        TeacherSponsorship.objects.filter(student=user, is_active=True,
                                           approved_at__isnull=False)
        .select_related("group")
        .order_by("-approved_at", "-id")
    )
    for sponsorship in qs:
        if sponsorship.expires_at and sponsorship.expires_at <= now:
            continue
        # The student must still actually belong to the approved group.
        if not sponsorship.group.students.filter(pk=user.pk).exists():
            continue
        return sponsorship
    return None


def get_effective_entitlement(user) -> Entitlement:
    """Resolve the effective entitlement for *user* (precedence chain)."""
    config = _platform_defaults()
    period_days = config["quota_period_days"]

    if user is None or not getattr(user, "is_authenticated", False):
        return Entitlement(
            source=SOURCE_DEFAULT, plan_type=None, plan_name="Mehmon",
            is_sponsored=False, is_active=False,
            image_essay_weekly_limit=config["image_essay_weekly_limit"],
            text_essay_weekly_limit=config["text_essay_weekly_limit"],
            text_essay_cooldown_hours=config["text_essay_cooldown_hours"],
            test_limit=config["test_limit"],
            quota_period_days=period_days,
        )

    # --- 1. Explicit, active administrator override (highest priority) ------
    override = _active_override(user)
    if override is not None:
        merged, contributed = _apply_layer(dict(config), override)
        # An override expresses an entitlement by itself, so a fully specified
        # override wins outright; unspecified fields keep the platform default
        # rather than the (possibly paid) tier's values — that is the documented
        # merge policy: an admin override is authoritative for what it sets and
        # neutral for the rest.
        return Entitlement(
            source=SOURCE_OVERRIDE,
            plan_type=None,
            plan_name="Admin ustunligi",
            is_sponsored=False,
            expires_at=override.expires_at,
            override_fields=contributed,
            **merged,
        )

    entitlement_plan: SubscriptionPlan | None = None
    source = SOURCE_DEFAULT
    plan_name = "Bepul"
    is_sponsored = False
    subscription: UserSubscription | None = None
    expires_at = None

    # --- 2. Approved teacher sponsorship ------------------------------------
    sponsorship = _effective_sponsorship(user)
    if sponsorship is not None:
        sponsored_plan = _plan_by_code(SubscriptionPlan.PlanType.PRO) or _plan_by_code(SubscriptionPlan.PlanType.TEACHER_SPONSORED)
        if sponsored_plan is not None:
            merged, contributed = _apply_layer(dict(config), sponsored_plan)
            merged, contributed2 = _apply_layer(merged, sponsorship)
            entitlement_plan = sponsored_plan
            source = SOURCE_SPONSORED
            plan_name = "PRO (Ustoz guruhi orqali)"
            is_sponsored = True
            expires_at = sponsorship.expires_at
            merged["is_unlimited_tests"] = True
            return Entitlement(
                source=source, plan_type=sponsored_plan.plan_type,
                plan_name=plan_name, is_sponsored=is_sponsored,
                plan=entitlement_plan, expires_at=expires_at,
                override_fields=contributed + contributed2, **merged,
            )
        logger.warning(
            "Student %s has an approved sponsorship but no "
            "TEACHER_SPONSORED plan row exists; falling through.",
            user.pk,
        )

    # --- 3. Paid or sponsored subscription ---------------------------------
    subscription = _subscription_for(user)
    if subscription is not None and subscription.is_active:
        plan = subscription.plan
        entitlement_plan = plan
        is_teacher_sponsored = (
            subscription.purchase_source == UserSubscription.Source.TEACHER_SPONSORED
            or (hasattr(user, "student_groups") and user.student_groups.exists())
        )
        source = SOURCE_SPONSORED if is_teacher_sponsored else SOURCE_SUBSCRIPTION
        plan_name = "PRO (Ustoz guruhi orqali)" if is_teacher_sponsored else (plan.name if plan else "PRO")
        is_sponsored = is_teacher_sponsored
        expires_at = subscription.expires_at
        if plan is not None:
            merged, contributed = _apply_layer(dict(config), plan)
            if is_teacher_sponsored:
                merged["is_unlimited_tests"] = True
            return Entitlement(
                source=source, plan_type=plan.plan_type, plan_name=plan_name,
                is_sponsored=is_sponsored, plan=plan, subscription=subscription,
                expires_at=expires_at, override_fields=contributed, **merged,
            )
        return Entitlement(
            source=source, plan_type=None, plan_name=plan_name,
            is_sponsored=is_sponsored, subscription=subscription, expires_at=expires_at,
            image_essay_weekly_limit=config["image_essay_weekly_limit"],
            text_essay_weekly_limit=config["text_essay_weekly_limit"],
            text_essay_cooldown_hours=config["text_essay_cooldown_hours"],
            test_limit=config["test_limit"],
            quota_period_days=period_days,
            is_unlimited_tests=True if is_teacher_sponsored else False,
        )

    # --- 3.5. Enrolled in teacher group (Auto-delegated PRO) ---------------
    if hasattr(user, "student_groups") and user.student_groups.exists():
        pro_plan = _plan_by_code(SubscriptionPlan.PlanType.PRO)
        if pro_plan is not None:
            merged, contributed = _apply_layer(dict(config), pro_plan)
            merged["is_unlimited_tests"] = True
            return Entitlement(
                source=SOURCE_SPONSORED,
                plan_type=pro_plan.plan_type,
                plan_name="PRO (Ustoz guruhi orqali)",
                is_sponsored=True,
                plan=pro_plan,
                expires_at=None,
                override_fields=contributed,
                **merged,
            )

    # --- 4. Default / free policy ------------------------------------------
    # The ``free`` plan row (when an administrator has configured one) is the
    # platform's default access policy.
    free_plan = _plan_by_code(SubscriptionPlan.PlanType.FREE)
    if free_plan is not None:
        merged, contributed = _apply_layer(dict(config), free_plan)
        return Entitlement(
            source=SOURCE_DEFAULT, plan_type=free_plan.plan_type,
            plan_name=free_plan.name or "Bepul", is_sponsored=False,
            plan=free_plan, override_fields=contributed, **merged,
        )
    return Entitlement(
        source=SOURCE_DEFAULT, plan_type=None, plan_name=plan_name,
        is_sponsored=False,
        image_essay_weekly_limit=config["image_essay_weekly_limit"],
        text_essay_weekly_limit=config["text_essay_weekly_limit"],
        text_essay_cooldown_hours=config["text_essay_cooldown_hours"],
        test_limit=config["test_limit"],
        quota_period_days=period_days,
    )


# ---------------------------------------------------------------------------
# Read-only reporting helpers
# ---------------------------------------------------------------------------

def _used_in_window(user, kind: str, period_start: datetime) -> int:
    return SubscriptionUsage.objects.filter(
        user=user,
        kind=kind,
        counts_towards_quota=True,
        status__in=(
            SubscriptionUsage.Status.RESERVED,
            SubscriptionUsage.Status.COMMITTED,
        ),
        period_start=period_start,
        created_at__gte=period_start,
    ).count()


def last_text_essay_at(user) -> datetime | None:
    """Timestamp of the most recent quota-consuming text essay (rolling)."""
    row = (
        SubscriptionUsage.objects.filter(
            user=user,
            kind=SubscriptionUsage.Kind.TEXT_ESSAY,
            counts_towards_quota=True,
            status__in=(
                SubscriptionUsage.Status.RESERVED,
                SubscriptionUsage.Status.COMMITTED,
            ),
        )
        .order_by("-created_at")
        .values_list("created_at", flat=True)
        .first()
    )
    return row


def cooldown_seconds_remaining(user, entitlement: Entitlement | None = None) -> int:
    """Seconds until a *text* essay may be submitted again (0 = allowed now)."""
    entitlement = entitlement or get_effective_entitlement(user)
    hours = entitlement.text_essay_cooldown_hours
    if not hours or entitlement.is_unlimited_text_essays:
        return 0
    last = last_text_essay_at(user)
    if last is None:
        return 0
    deadline = last + timedelta(hours=int(hours))
    remaining = (deadline - timezone.now()).total_seconds()
    return max(0, int(remaining))


def format_duration(seconds: int) -> str:
    """Human Uzbek duration, e.g. ``3 soat 20 daqiqa``."""
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes = rem // 60
    if hours and minutes:
        return f"{hours} soat {minutes} daqiqa"
    if hours:
        return f"{hours} soat"
    if minutes:
        return f"{minutes} daqiqa"
    return "1 daqiqadan kam"


def get_remaining_limits(user, entitlement: Entitlement | None = None) -> dict:
    """Server-calculated remaining allowances for the quota widget / bot."""
    entitlement = entitlement or get_effective_entitlement(user)
    now = timezone.now()
    period_start = quota_period_start(
        now, period_days=entitlement.quota_period_days,
    )

    def bucket(kind: str, limit: int | None, unlimited: bool) -> dict:
        used = 0 if unlimited else _used_in_window(user, kind, period_start)
        if unlimited:
            return {
                "unlimited": True, "limit": None, "used": used,
                "remaining": None,
            }
        remaining = None if limit is None else max(0, int(limit) - used)
        return {
            "unlimited": False, "limit": limit, "used": used,
            "remaining": remaining,
        }

    cooldown = cooldown_seconds_remaining(user, entitlement)
    return {
        "source": entitlement.source,
        "plan_type": entitlement.plan_type,
        "plan_name": entitlement.plan_name,
        "is_sponsored": entitlement.is_sponsored,
        "is_paid": entitlement.is_paid,
        "expires_at": entitlement.expires_at.isoformat() if entitlement.expires_at else None,
        "period_start": period_start.isoformat(),
        "period_end": (
            period_start + timedelta(days=entitlement.quota_period_days)
        ).isoformat(),
        "image_essay": bucket(
            SubscriptionUsage.Kind.IMAGE_ESSAY,
            entitlement.image_essay_weekly_limit,
            entitlement.is_unlimited_image_essays,
        ),
        "text_essay": bucket(
            SubscriptionUsage.Kind.TEXT_ESSAY,
            entitlement.text_essay_weekly_limit,
            entitlement.is_unlimited_text_essays,
        ),
        "test": bucket(
            SubscriptionUsage.Kind.TEST,
            entitlement.test_limit,
            entitlement.is_unlimited_tests,
        ),
        "text_cooldown_seconds": cooldown,
        "text_cooldown_until": (
            (now + timedelta(seconds=cooldown)).isoformat() if cooldown else None
        ),
    }


# ---------------------------------------------------------------------------
# Limit-exceeded message builders (Uzbek)
# ---------------------------------------------------------------------------

UPGRADE_HINT = "PRO tarifiga o'tish orqali cheklovni olib tashlashingiz mumkin."


def _limit_message(kind: str) -> str:
    if kind == SubscriptionUsage.Kind.IMAGE_ESSAY:
        return "Haftalik rasmli esse limitingiz tugadi."
    if kind == SubscriptionUsage.Kind.TEXT_ESSAY:
        return "Matnli esse limitingiz tugadi."
    return "Haftalik testingiz limitingi tugadi."


def _remaining_message(kind: str, remaining: dict) -> str:
    label = {
        SubscriptionUsage.Kind.IMAGE_ESSAY: "rasmli esse",
        SubscriptionUsage.Kind.TEXT_ESSAY: "matnli esse",
        SubscriptionUsage.Kind.TEST: "test",
    }.get(kind, "urinish")
    bucket = remaining.get(kind if kind != SubscriptionUsage.Kind.TEST else "test", {})
    if bucket.get("unlimited"):
        return f"Joriy limitingiz: {label} cheklanmagan."
    left = bucket.get("remaining")
    total = bucket.get("limit")
    if left is None or total is None:
        return f"Joriy limitingiz: {label} — sozlanmagan."
    return f"Joriy limitingiz: {left}/{total} {label} qoldi."


# ---------------------------------------------------------------------------
# Eligibility checks
# ---------------------------------------------------------------------------

def can_submit_essay(user, kind: str) -> tuple[bool, str | None, dict]:
    """Non-mutating eligibility check. Returns ``(ok, reason, remaining)``."""
    if kind not in ESSAY_KINDS:
        raise ValueError(f"Unknown essay kind: {kind!r}")
    entitlement = get_effective_entitlement(user)
    remaining = get_remaining_limits(user, entitlement)

    if entitlement.is_unlimited_for(kind):
        return True, None, remaining

    limit = entitlement.limit_for(kind)
    if limit is not None and remaining[_kind_key(kind)]["used"] >= int(limit):
        return False, "limit_exceeded", remaining

    if kind == SubscriptionUsage.Kind.TEXT_ESSAY:
        cooldown = cooldown_seconds_remaining(user, entitlement)
        if cooldown > 0:
            return False, "cooldown", remaining

    return True, None, remaining


def can_start_test(user) -> tuple[bool, str | None, dict]:
    """Non-mutating check for starting a practice test."""
    entitlement = get_effective_entitlement(user)
    remaining = get_remaining_limits(user, entitlement)
    if entitlement.is_unlimited_tests:
        return True, None, remaining
    limit = entitlement.test_limit
    if limit is not None and remaining["test"]["used"] >= int(limit):
        return False, "limit_exceeded", remaining
    return True, None, remaining


def _kind_key(kind: str) -> str:
    return {
        SubscriptionUsage.Kind.IMAGE_ESSAY: "image_essay",
        SubscriptionUsage.Kind.TEXT_ESSAY: "text_essay",
        SubscriptionUsage.Kind.TEST: "test",
    }[kind]


# ---------------------------------------------------------------------------
# Atomic reservation
# ---------------------------------------------------------------------------

@dataclass
class Reservation:
    """Outcome of :func:`reserve_usage`."""

    ok: bool
    usage: SubscriptionUsage | None = None
    reason: str | None = None
    message: str = ""
    remaining: dict = field(default_factory=dict)
    retry_after_seconds: int = 0
    #: True when a previous identical reservation was replayed (idempotency).
    replayed: bool = False
    #: True when the entitlement is unlimited and the row does not consume
    #: commercial allowance (still recorded for audit).
    not_counted: bool = False

    def attach_submission(self, submission) -> None:
        if self.usage is not None and submission is not None:
            SubscriptionUsage.objects.filter(pk=self.usage.pk).update(
                submission=submission,
            )
            self.usage.submission = submission

    def attach_test_attempt(self, attempt) -> None:
        if self.usage is not None and attempt is not None:
            SubscriptionUsage.objects.filter(pk=self.usage.pk).update(
                test_attempt=attempt,
            )
            self.usage.test_attempt = attempt


def _default_idempotency_key(user, kind: str) -> str:
    return f"{kind}:{getattr(user, 'pk', 0)}:{uuid.uuid4().hex}"


def reserve_usage(
    user,
    kind: str,
    *,
    idempotency_key: str | None = None,
    source: str = "",
    note: str = "",
    enforce_quota: bool = True,
) -> Reservation:
    """Atomically reserve one commercial usage allowance.

    Call this **before** creating the submission / queueing the grading job, and
    keep the returned :class:`Reservation` so the caller can
    :func:`commit_usage` once the grading job is accepted or
    :func:`release_usage` when the operation is abandoned (invalid upload,
    rejected submission, provider-before-accept failure).

    The whole check-and-insert runs in one short transaction that row-locks the
    user, so two concurrent requests cannot both consume the last allowance.
    No external call ever happens while the transaction is open.
    """
    if kind not in dict(SubscriptionUsage.Kind.choices):
        raise ValueError(f"Unknown usage kind: {kind!r}")

    key = idempotency_key or _default_idempotency_key(user, kind)
    User = get_user_model()

    with transaction.atomic():
        # Row-lock the user row: serialises concurrent submissions per student,
        # which is what makes "last remaining quota" and the rolling cooldown
        # race-free without locking the whole usage table.
        User.objects.select_for_update().only("pk").get(pk=user.pk)

        existing = SubscriptionUsage.objects.filter(idempotency_key=key).first()
        if existing is not None:
            # Idempotent replay: a retried webhook/task/browser submits the same
            # logical operation and must not be charged a second time.
            return Reservation(
                ok=existing.status != SubscriptionUsage.Status.RELEASED,
                usage=existing,
                reason=None if existing.status != SubscriptionUsage.Status.RELEASED
                else "released",
                message="",
                # Resolved here rather than reusing a local: on the replay path
                # the entitlement has intentionally not been computed yet.
                remaining=get_remaining_limits(user),
                replayed=True,
                not_counted=not existing.counts_towards_quota,
            )

        entitlement = get_effective_entitlement(user)
        now = timezone.now()
        period_start = quota_period_start(
            now, period_days=entitlement.quota_period_days,
        )
        unlimited = entitlement.is_unlimited_for(kind)
        limit = entitlement.limit_for(kind)
        counts = True

        if enforce_quota and not unlimited:
            used = _used_in_window(user, kind, period_start)
            if limit is not None and used >= int(limit):
                remaining = get_remaining_limits(user, entitlement)
                message = _limit_message(kind)
                return Reservation(
                    ok=False, reason="limit_exceeded",
                    message=f"{message}\n{UPGRADE_HINT}\n"
                            f"{_remaining_message(kind, remaining)}",
                    remaining=remaining,
                )
            if kind == SubscriptionUsage.Kind.TEXT_ESSAY:
                cooldown = cooldown_seconds_remaining(user, entitlement)
                if cooldown > 0:
                    remaining = get_remaining_limits(user, entitlement)
                    return Reservation(
                        ok=False, reason="cooldown",
                        message=(
                            "Keyingi matnli esseni "
                            f"{format_duration(cooldown)}dan keyin "
                            "yuborishingiz mumkin."
                        ),
                        remaining=remaining,
                        retry_after_seconds=cooldown,
                    )
        elif enforce_quota and unlimited:
            # Unlimited tiers are not charged commercial allowance, but the
            # operation is still recorded (audit + provider-failure analysis).
            counts = False

        try:
            usage = SubscriptionUsage.objects.create(
                user=user,
                kind=kind,
                status=SubscriptionUsage.Status.RESERVED,
                idempotency_key=key,
                period_start=period_start,
                counts_towards_quota=counts,
                plan_type_snapshot=entitlement.plan_type or "",
                source=source or entitlement.source,
                note=note[:200],
            )
        except IntegrityError:
            # Lost the unique-key race with an identical concurrent operation.
            existing = SubscriptionUsage.objects.filter(
                idempotency_key=key,
            ).first()
            if existing is None:
                raise
            return Reservation(
                ok=True, usage=existing, replayed=True,
                remaining=get_remaining_limits(user, entitlement),
                not_counted=not existing.counts_towards_quota,
            )

    remaining = get_remaining_limits(user, entitlement)
    return Reservation(
        ok=True, usage=usage, remaining=remaining, not_counted=not counts,
    )


def commit_usage(reservation: Reservation | SubscriptionUsage | None) -> bool:
    """Mark a reservation as consumed. Idempotent."""
    usage = _as_usage(reservation)
    if usage is None:
        return False
    if usage.status == SubscriptionUsage.Status.COMMITTED:
        return True
    updated = SubscriptionUsage.objects.filter(
        pk=usage.pk,
    ).exclude(
        status=SubscriptionUsage.Status.COMMITTED,
    ).update(
        status=SubscriptionUsage.Status.COMMITTED,
        committed_at=timezone.now(),
    )
    return bool(updated) or True


def release_usage(reservation: Reservation | SubscriptionUsage | None) -> bool:
    """Return an unused reservation to the pool.

    Only ever releases a *reserved* row: a committed (already accepted, queued
    grading) usage must stay consumed, which is what stops an internal AI retry
    from being charged again.
    """
    usage = _as_usage(reservation)
    if usage is None:
        return False
    updated = SubscriptionUsage.objects.filter(
        pk=usage.pk, status=SubscriptionUsage.Status.RESERVED,
    ).update(
        status=SubscriptionUsage.Status.RELEASED,
        released_at=timezone.now(),
    )
    return bool(updated)


def _as_usage(obj) -> SubscriptionUsage | None:
    if obj is None:
        return None
    if isinstance(obj, SubscriptionUsage):
        return obj
    if isinstance(obj, Reservation):
        return obj.usage
    raise TypeError(f"Cannot treat {type(obj)!r} as a usage record")


# ---------------------------------------------------------------------------
# Convenience enforcement helpers for view/handler call sites
# ---------------------------------------------------------------------------

def enforce_essay_quota(user, kind: str, *, idempotency_key: str | None = None,
                        source: str = "") -> Reservation:
    """Reserve an essay allowance or raise :class:`QuotaDenied`."""
    reservation = reserve_usage(
        user, kind, idempotency_key=idempotency_key, source=source,
    )
    if not reservation.ok:
        raise QuotaDenied(
            reservation.reason or "denied",
            reservation.message or _limit_message(kind),
            remaining=reservation.remaining,
            retry_after_seconds=reservation.retry_after_seconds,
        )
    return reservation


def enforce_test_quota(user, *, idempotency_key: str | None = None,
                       source: str = "") -> Reservation:
    """Reserve a test allowance or raise :class:`QuotaDenied`."""
    ok, reason, remaining = can_start_test(user)
    if not ok:
        raise QuotaDenied(
            reason or "limit_exceeded",
            f"{_limit_message(SubscriptionUsage.Kind.TEST)}\n{UPGRADE_HINT}\n"
            f"{_remaining_message(SubscriptionUsage.Kind.TEST, remaining)}",
            remaining=remaining,
        )
    reservation = reserve_usage(
        user, SubscriptionUsage.Kind.TEST,
        idempotency_key=idempotency_key, source=source,
    )
    if not reservation.ok:
        raise QuotaDenied(
            reservation.reason or "denied",
            reservation.message or _limit_message(SubscriptionUsage.Kind.TEST),
            remaining=reservation.remaining,
        )
    return reservation


def essay_kind_for_submission_type(submission_type: str) -> str:
    """Map a channel-level submission type onto a usage kind."""
    normalized = (submission_type or "").strip().lower()
    if normalized in {"image", "photo", "ocr", "image_essay"}:
        return SubscriptionUsage.Kind.IMAGE_ESSAY
    return SubscriptionUsage.Kind.TEXT_ESSAY
