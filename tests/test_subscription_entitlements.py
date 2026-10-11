"""Entitlement resolution: deterministic precedence and NULL-vs-zero semantics.

These tests exercise ``apps.payments.entitlements`` directly (not through a
view) so they stay stable while the channel-level integrations are built.

Design note worth reading before changing an expectation: a *partial*
administrator override layers on top of the **platform defaults**, not on top
of the paid plan. An override is authoritative for the fields it sets and
neutral for the rest. The tests below pin that behaviour down explicitly so it
cannot drift silently.
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.payments.entitlements import (
    SOURCE_DEFAULT,
    SOURCE_OVERRIDE,
    SOURCE_SUBSCRIPTION,
    can_submit_essay,
    can_start_test,
    format_duration,
    get_effective_entitlement,
    get_remaining_limits,
    quota_period_start,
)
from apps.payments.models import (
    SubscriptionOverride,
    SubscriptionPlan,
    SubscriptionUsage,
    UserSubscription,
)

#: Every key ``get_remaining_limits`` may expose to a client. Nothing identity
#: related is allowed in here (see the privacy test at the bottom).
EXPECTED_LIMIT_KEYS = {
    "source", "plan_type", "plan_name", "is_sponsored", "is_paid",
    "expires_at", "period_start", "period_end",
    "image_essay", "text_essay", "test",
    "text_cooldown_seconds", "text_cooldown_until",
}

EXPECTED_BUCKET_KEYS = {"unlimited", "limit", "used", "remaining"}


def make_plan(plan_type: str, **overrides) -> SubscriptionPlan:
    """Fetch or create a plan row and pin the fields this test depends on."""
    defaults = {
        "name": plan_type.upper(),
        "description": "",
        "price_monthly": 0,
        "price_yearly": 0,
        "image_essay_weekly_limit": None,
        "text_essay_weekly_limit": None,
        "text_essay_cooldown_hours": None,
        "test_limit": None,
        "is_unlimited_image_essays": False,
        "is_unlimited_text_essays": False,
        "is_unlimited_tests": False,
        "duration_days": 30,
        "quota_period_days": 7,
        "telegram_stars_price": None,
        "is_public": True,
        "is_active": True,
    }
    defaults.update(overrides)
    plan, _created = SubscriptionPlan.objects.get_or_create(
        plan_type=plan_type, defaults=defaults,
    )
    for field, value in defaults.items():
        setattr(plan, field, value)
    plan.save()
    return plan


class EntitlementPrecedenceTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            email="entitlement-student@example.test",
            password="StrongPass123!",
            role="student",
        )

    def _subscribe(self, plan, *, days: int = 30, status: str | None = None):
        return UserSubscription.objects.create(
            user=self.student,
            plan=plan,
            status=status or UserSubscription.Status.ACTIVE,
            started_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=days),
        )

    def test_user_without_subscription_resolves_to_default_policy(self):
        entitlement = get_effective_entitlement(self.student)
        self.assertEqual(entitlement.source, SOURCE_DEFAULT)
        self.assertFalse(entitlement.is_sponsored)
        self.assertFalse(entitlement.is_paid)
        self.assertIsNone(entitlement.subscription)
        # The platform default enforces nothing, so introducing the commercial
        # plans cannot silently restrict an account that already exists.
        self.assertIsNone(entitlement.image_essay_weekly_limit)
        self.assertIsNone(entitlement.text_essay_weekly_limit)
        self.assertFalse(entitlement.is_unlimited_image_essays)

    def test_active_start_subscription_exposes_limits_and_cooldown(self):
        plan = make_plan(
            "start",
            image_essay_weekly_limit=5,
            text_essay_weekly_limit=3,
            text_essay_cooldown_hours=5,
        )
        self._subscribe(plan)

        entitlement = get_effective_entitlement(self.student)
        self.assertEqual(entitlement.source, SOURCE_SUBSCRIPTION)
        self.assertTrue(entitlement.is_paid)
        self.assertEqual(entitlement.plan_type, "start")
        self.assertEqual(entitlement.image_essay_weekly_limit, 5)
        self.assertEqual(entitlement.text_essay_weekly_limit, 3)
        self.assertEqual(entitlement.text_essay_cooldown_hours, 5)
        self.assertFalse(entitlement.is_unlimited_text_essays)

    def test_active_pro_subscription_is_unlimited_without_cooldown(self):
        plan = make_plan(
            "pro",
            image_essay_weekly_limit=None,
            text_essay_weekly_limit=None,
            text_essay_cooldown_hours=0,
            is_unlimited_image_essays=True,
            is_unlimited_text_essays=True,
            is_unlimited_tests=True,
        )
        self._subscribe(plan)

        entitlement = get_effective_entitlement(self.student)
        self.assertEqual(entitlement.source, SOURCE_SUBSCRIPTION)
        self.assertTrue(entitlement.is_unlimited_image_essays)
        self.assertTrue(entitlement.is_unlimited_text_essays)
        self.assertTrue(entitlement.is_unlimited_tests)
        self.assertTrue(entitlement.is_unlimited_for(SubscriptionUsage.Kind.TEXT_ESSAY))
        self.assertEqual(entitlement.text_essay_cooldown_hours, 0)

        for _ in range(4):
            ok, reason, _remaining = can_submit_essay(
                self.student, SubscriptionUsage.Kind.TEXT_ESSAY,
            )
            self.assertTrue(ok)
            self.assertIsNone(reason)

    def test_expired_subscription_falls_back_to_default(self):
        plan = make_plan("start", image_essay_weekly_limit=5)
        UserSubscription.objects.create(
            user=self.student,
            plan=plan,
            status=UserSubscription.Status.ACTIVE,
            started_at=timezone.now() - timedelta(days=60),
            expires_at=timezone.now() - timedelta(days=30),
        )
        entitlement = get_effective_entitlement(self.student)
        self.assertEqual(entitlement.source, SOURCE_DEFAULT)
        self.assertFalse(entitlement.is_paid)

    def test_cancelled_subscription_falls_back_to_default(self):
        plan = make_plan("start", image_essay_weekly_limit=5)
        self._subscribe(plan, status=UserSubscription.Status.CANCELLED)
        entitlement = get_effective_entitlement(self.student)
        self.assertEqual(entitlement.source, SOURCE_DEFAULT)


class AdministratorOverrideTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            email="override-student@example.test",
            password="StrongPass123!",
            role="student",
        )

    def test_active_override_outranks_paid_subscription(self):
        plan = make_plan(
            "start",
            image_essay_weekly_limit=5,
            text_essay_weekly_limit=3,
            text_essay_cooldown_hours=5,
        )
        UserSubscription.objects.create(
            user=self.student, plan=plan,
            status=UserSubscription.Status.ACTIVE,
            started_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=30),
        )
        SubscriptionOverride.objects.create(
            user=self.student,
            is_active=True,
            image_essay_weekly_limit=10,
            text_essay_weekly_limit=15,
            text_essay_cooldown_hours=0,
        )

        entitlement = get_effective_entitlement(self.student)
        self.assertEqual(entitlement.source, SOURCE_OVERRIDE)
        self.assertEqual(entitlement.image_essay_weekly_limit, 10)
        self.assertEqual(entitlement.text_essay_weekly_limit, 15)
        self.assertEqual(entitlement.text_essay_cooldown_hours, 0)
        # The override is authoritative; the paid row is no longer the source.
        self.assertIsNone(entitlement.subscription)

    def test_partial_override_is_neutral_for_unspecified_fields(self):
        """A partial override must not zero the fields it does not mention.

        Documented merge policy: an override layers on the platform defaults.
        Unspecified fields therefore keep the default (``None`` = unenforced),
        which can never be read as "zero allowance" and so can never disable an
        entitlement the student already has.
        """
        plan = make_plan(
            "start", image_essay_weekly_limit=5, text_essay_weekly_limit=3,
        )
        UserSubscription.objects.create(
            user=self.student, plan=plan,
            status=UserSubscription.Status.ACTIVE,
            started_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=30),
        )
        SubscriptionOverride.objects.create(
            user=self.student, is_active=True, image_essay_weekly_limit=7,
        )

        entitlement = get_effective_entitlement(self.student)
        self.assertEqual(entitlement.source, SOURCE_OVERRIDE)
        self.assertEqual(entitlement.image_essay_weekly_limit, 7)
        self.assertEqual(entitlement.override_fields, ("image_essay_weekly_limit",))
        self.assertIsNone(entitlement.text_essay_weekly_limit)
        self.assertNotEqual(entitlement.text_essay_weekly_limit, 0)
        self.assertFalse(entitlement.is_unlimited_text_essays)

    def test_expired_override_is_ignored(self):
        plan = make_plan("start", image_essay_weekly_limit=5)
        UserSubscription.objects.create(
            user=self.student, plan=plan,
            status=UserSubscription.Status.ACTIVE,
            started_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=30),
        )
        SubscriptionOverride.objects.create(
            user=self.student,
            is_active=True,
            image_essay_weekly_limit=99,
            expires_at=timezone.now() - timedelta(hours=1),
        )

        entitlement = get_effective_entitlement(self.student)
        self.assertEqual(entitlement.source, SOURCE_SUBSCRIPTION)
        self.assertEqual(entitlement.image_essay_weekly_limit, 5)

    def test_inactive_override_is_ignored(self):
        SubscriptionOverride.objects.create(
            user=self.student, is_active=False, image_essay_weekly_limit=99,
        )
        entitlement = get_effective_entitlement(self.student)
        self.assertEqual(entitlement.source, SOURCE_DEFAULT)
        self.assertIsNone(entitlement.image_essay_weekly_limit)

    def test_override_unlimited_flag_is_applied(self):
        SubscriptionOverride.objects.create(
            user=self.student,
            is_active=True,
            is_unlimited_text_essays=True,
            is_unlimited_tests=True,
        )
        entitlement = get_effective_entitlement(self.student)
        self.assertTrue(entitlement.is_unlimited_text_essays)
        self.assertTrue(entitlement.is_unlimited_tests)
        self.assertFalse(entitlement.is_unlimited_image_essays)


class NullVersusZeroTests(TestCase):
    """NULL means "inherit"; 0 means "explicitly none allowed"."""

    def setUp(self):
        self.student = User.objects.create_user(
            email="nullzero-student@example.test",
            password="StrongPass123!",
            role="student",
        )

    def _subscribe(self, plan):
        return UserSubscription.objects.create(
            user=self.student, plan=plan,
            status=UserSubscription.Status.ACTIVE,
            started_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=30),
        )

    def test_null_limit_enforces_nothing(self):
        plan = make_plan(
            "start", image_essay_weekly_limit=None,
            is_unlimited_image_essays=False,
        )
        self._subscribe(plan)
        entitlement = get_effective_entitlement(self.student)
        self.assertIsNone(entitlement.image_essay_weekly_limit)
        self.assertFalse(entitlement.is_unlimited_for(
            SubscriptionUsage.Kind.IMAGE_ESSAY,
        ))

        ok, reason, _remaining = can_submit_essay(
            self.student, SubscriptionUsage.Kind.IMAGE_ESSAY,
        )
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_zero_limit_blocks_immediately(self):
        plan = make_plan(
            "start", image_essay_weekly_limit=0, text_essay_weekly_limit=0,
        )
        self._subscribe(plan)

        ok, reason, remaining = can_submit_essay(
            self.student, SubscriptionUsage.Kind.IMAGE_ESSAY,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "limit_exceeded")
        self.assertEqual(remaining["image_essay"]["limit"], 0)
        self.assertEqual(remaining["image_essay"]["remaining"], 0)

        ok, reason, _remaining = can_submit_essay(
            self.student, SubscriptionUsage.Kind.TEXT_ESSAY,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "limit_exceeded")

    def test_zero_limit_is_not_treated_as_unlimited(self):
        plan = make_plan("start", test_limit=0, is_unlimited_tests=False)
        self._subscribe(plan)
        entitlement = get_effective_entitlement(self.student)
        self.assertEqual(entitlement.test_limit, 0)
        self.assertFalse(entitlement.is_unlimited_tests)

        ok, reason, _remaining = can_start_test(self.student)
        self.assertFalse(ok)
        self.assertEqual(reason, "limit_exceeded")


class RemainingLimitsPayloadTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            email="payload-student@example.test",
            password="StrongPass123!",
            role="student",
            first_name="Private",
            last_name="Student",
        )

    def test_payload_has_a_fixed_allow_list_of_keys(self):
        remaining = get_remaining_limits(self.student)
        self.assertEqual(set(remaining), EXPECTED_LIMIT_KEYS)
        for bucket in ("image_essay", "text_essay", "test"):
            self.assertEqual(set(remaining[bucket]), EXPECTED_BUCKET_KEYS)

    def test_payload_never_leaks_identity_or_other_users(self):
        other = User.objects.create_user(
            email="other-leak@example.test",
            password="StrongPass123!",
            role="student",
            first_name="Secret",
            last_name="Person",
        )
        UserSubscription.objects.create(
            user=other,
            plan=make_plan("start", text_essay_weekly_limit=3),
            status=UserSubscription.Status.ACTIVE,
            started_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=30),
        )

        remaining = get_remaining_limits(self.student)
        blob = repr(remaining)
        self.assertNotIn("other-leak@example.test", blob)
        self.assertNotIn("Secret", blob)
        self.assertNotIn("Person", blob)
        self.assertNotIn("user_id", blob)
        self.assertNotIn("email", blob)
        self.assertNotIn("password", blob)
        # The other student's subscription must not affect this student.
        self.assertEqual(remaining["source"], SOURCE_DEFAULT)
        self.assertFalse(remaining["is_paid"])

    def test_used_counter_reflects_only_this_users_usage(self):
        plan = make_plan("start", text_essay_weekly_limit=3)
        UserSubscription.objects.create(
            user=self.student, plan=plan,
            status=UserSubscription.Status.ACTIVE,
            started_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=30),
        )
        window = quota_period_start()
        SubscriptionUsage.objects.create(
            user=self.student,
            kind=SubscriptionUsage.Kind.TEXT_ESSAY,
            status=SubscriptionUsage.Status.COMMITTED,
            idempotency_key="payload-self-1",
            period_start=window,
        )
        other = User.objects.create_user(
            email="usage-other@example.test", password="StrongPass123!",
            role="student",
        )
        SubscriptionUsage.objects.create(
            user=other,
            kind=SubscriptionUsage.Kind.TEXT_ESSAY,
            status=SubscriptionUsage.Status.COMMITTED,
            idempotency_key="payload-other-1",
            period_start=window,
        )

        remaining = get_remaining_limits(self.student)
        self.assertEqual(remaining["text_essay"]["used"], 1)
        self.assertEqual(remaining["text_essay"]["remaining"], 2)


class FormatDurationTests(TestCase):
    def test_formats_hours_and_minutes_in_uzbek(self):
        self.assertEqual(format_duration(12000), "3 soat 20 daqiqa")
        self.assertEqual(format_duration(3600), "1 soat")
        self.assertEqual(format_duration(600), "10 daqiqa")
        self.assertEqual(format_duration(30), "1 daqiqadan kam")


class QuotaPeriodStartTests(TestCase):
    def test_window_starts_on_monday_midnight_in_the_quota_timezone(self):
        now = timezone.now()
        start = quota_period_start(now)
        self.assertEqual(start.weekday(), 0)  # Monday
        self.assertEqual((start.hour, start.minute, start.second), (0, 0, 0))
        self.assertLessEqual(start, now.astimezone(start.tzinfo))
        # Seven days after the window start is the next window start.
        next_week = quota_period_start(now + timedelta(days=7))
        self.assertGreaterEqual(next_week, start + timedelta(days=7))

    def test_reset_weekday_is_configurable(self):
        now = timezone.now()
        monday = quota_period_start(now, reset_weekday=0)
        sunday = quota_period_start(now, reset_weekday=6)
        self.assertEqual(monday.weekday(), 0)
        self.assertEqual(sunday.weekday(), 6)
        self.assertNotEqual(monday, sunday)

    def test_period_start_is_stable_within_a_week(self):
        # Anchored to the window start so the assertion is date-independent
        # (adding a day to "now" could otherwise cross a window boundary).
        start = quota_period_start(timezone.now())
        for offset in (timedelta(minutes=1), timedelta(days=1),
                       timedelta(days=6, hours=23)):
            self.assertEqual(quota_period_start(start + offset), start)

    def test_period_start_rolls_over_at_the_boundary(self):
        start = quota_period_start(timezone.now())
        self.assertEqual(
            quota_period_start(start + timedelta(days=7)),
            start + timedelta(days=7),
        )
