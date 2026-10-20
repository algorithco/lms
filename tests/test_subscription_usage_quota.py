"""Atomic commercial quota accounting.

Covers the durable usage ledger: weekly limits, the rolling text cooldown,
idempotent billing across retries, reservation release, and the "last remaining
allowance" race.

Contrast with the true race: ``test_simultaneous_reservations_...`` is skipped
unless the suite runs against PostgreSQL (``config.settings.postgres_test``).
SQLite cannot prove PostgreSQL race safety, so the deterministic tests around it
prove the invariant while clearly not claiming to prove the race.
"""

import unittest
from datetime import timedelta
from threading import Thread

from django.db import connection, connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.payments.entitlements import (
    can_submit_essay,
    cooldown_seconds_remaining,
    get_remaining_limits,
    quota_period_start,
    release_usage,
    reserve_usage,
    commit_usage,
)
from apps.payments.models import (
    SubscriptionPlan,
    SubscriptionUsage,
    UserSubscription,
)

IS_POSTGRESQL = connection.vendor == "postgresql"

TEXT = SubscriptionUsage.Kind.TEXT_ESSAY
IMAGE = SubscriptionUsage.Kind.IMAGE_ESSAY


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
        plan_type=plan_type,
        defaults=defaults,
    )
    for field, value in defaults.items():
        setattr(plan, field, value)
    plan.save()
    return plan


class _QuotaTestCase(TestCase):
    """Shared fixture: one student on a fully specified START plan."""

    plan_kwargs: dict = {}

    def setUp(self):
        self.student = User.objects.create_user(
            email="quota-student@example.test",
            password="StrongPass123!",
            role="student",
        )
        defaults = {
            "image_essay_weekly_limit": 5,
            "text_essay_weekly_limit": 3,
            "text_essay_cooldown_hours": 0,
        }
        defaults.update(self.plan_kwargs)
        self.plan = make_plan("start", **defaults)
        UserSubscription.objects.create(
            user=self.student,
            plan=self.plan,
            status=UserSubscription.Status.ACTIVE,
            started_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=30),
        )

    def reserve(self, kind, key):
        return reserve_usage(self.student, kind, idempotency_key=key)


class QuotaLimitTests(_QuotaTestCase):
    def test_three_text_essays_accepted_then_fourth_rejected(self):
        for index in range(3):
            result = self.reserve(TEXT, f"text-{index}")
            self.assertTrue(result.ok, result.message)
            self.assertFalse(result.not_counted)

        fourth = self.reserve(TEXT, "text-3")
        self.assertFalse(fourth.ok)
        self.assertEqual(fourth.reason, "limit_exceeded")
        self.assertIn("Matnli esse limitingiz tugadi", fourth.message)
        self.assertIn("PRO tarifiga o'tish", fourth.message)
        self.assertIn("0/3 matnli esse qoldi", fourth.message)
        self.assertEqual(fourth.remaining["text_essay"]["remaining"], 0)

        self.assertEqual(
            SubscriptionUsage.objects.filter(
                user=self.student,
                kind=TEXT,
            ).count(),
            3,
        )

    def test_five_image_essays_accepted_then_sixth_rejected(self):
        for index in range(5):
            result = self.reserve(IMAGE, f"image-{index}")
            self.assertTrue(result.ok, result.message)

        sixth = self.reserve(IMAGE, "image-5")
        self.assertFalse(sixth.ok)
        self.assertEqual(sixth.reason, "limit_exceeded")
        self.assertIn("Haftalik rasmli esse limitingiz tugadi", sixth.message)
        self.assertEqual(
            SubscriptionUsage.objects.filter(
                user=self.student,
                kind=IMAGE,
            ).count(),
            5,
        )

    def test_image_and_text_quotas_are_independent(self):
        for index in range(5):
            self.assertTrue(self.reserve(IMAGE, f"ind-img-{index}").ok)
        self.assertFalse(self.reserve(IMAGE, "ind-img-5").ok)
        # The text quota is untouched by the exhausted image quota.
        self.assertTrue(self.reserve(TEXT, "ind-txt-0").ok)

    def test_weekly_window_reset_frees_a_new_allowance(self):
        self.plan.text_essay_weekly_limit = 1
        self.plan.save(update_fields=["text_essay_weekly_limit", "updated_at"])

        first = self.reserve(TEXT, "reset-1")
        self.assertTrue(first.ok)
        self.assertFalse(self.reserve(TEXT, "reset-2").ok)

        now = timezone.now()
        previous_window = quota_period_start(now) - timedelta(days=7)
        self.assertNotEqual(
            quota_period_start(previous_window), quota_period_start(now)
        )

        # Move the existing usage into the previous window. ``created_at`` is
        # auto_now_add, so it has to be rewritten through an UPDATE.
        SubscriptionUsage.objects.filter(pk=first.usage.pk).update(
            created_at=previous_window,
            period_start=previous_window,
        )

        third = self.reserve(TEXT, "reset-3")
        self.assertTrue(third.ok, third.message)
        self.assertEqual(get_remaining_limits(self.student)["text_essay"]["used"], 1)


class UnenforcedQuotaTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            email="unenforced-student@example.test",
            password="StrongPass123!",
            role="student",
        )

    def test_plan_with_all_fields_null_and_no_unlimited_flags_enforces_nothing(self):
        plan = make_plan(
            "start",
            image_essay_weekly_limit=None,
            text_essay_weekly_limit=None,
            text_essay_cooldown_hours=None,
            test_limit=None,
            is_unlimited_image_essays=False,
            is_unlimited_text_essays=False,
            is_unlimited_tests=False,
        )
        UserSubscription.objects.create(
            user=self.student,
            plan=plan,
            status=UserSubscription.Status.ACTIVE,
            started_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=30),
        )

        for index in range(10):
            result = reserve_usage(
                self.student,
                TEXT,
                idempotency_key=f"unenforced-{index}",
            )
            self.assertTrue(result.ok, result.message)
        self.assertEqual(cooldown_seconds_remaining(self.student), 0)
        self.assertIsNone(
            get_remaining_limits(self.student)["text_essay"]["limit"],
        )


class CooldownTests(_QuotaTestCase):
    plan_kwargs = {"text_essay_weekly_limit": 10, "text_essay_cooldown_hours": 5}

    def test_second_text_essay_is_blocked_by_the_five_hour_cooldown(self):
        first = self.reserve(TEXT, "cool-1")
        self.assertTrue(first.ok)
        self.assertTrue(commit_usage(first))

        seconds = cooldown_seconds_remaining(self.student)
        self.assertGreater(seconds, 4 * 3600)
        self.assertLessEqual(seconds, 5 * 3600)

        ok, reason, _remaining = can_submit_essay(self.student, TEXT)
        self.assertFalse(ok)
        self.assertEqual(reason, "cooldown")

        second = self.reserve(TEXT, "cool-2")
        self.assertFalse(second.ok)
        self.assertEqual(second.reason, "cooldown")
        self.assertGreater(second.retry_after_seconds, 0)
        self.assertIn("Keyingi matnli esseni", second.message)
        self.assertNotEqual(
            get_remaining_limits(self.student)["text_cooldown_until"], None
        )

    def test_cooldown_does_not_block_image_essays(self):
        self.assertTrue(commit_usage(self.reserve(TEXT, "cool-img-1")))
        self.assertGreater(cooldown_seconds_remaining(self.student), 0)

        ok, reason, _remaining = can_submit_essay(self.student, IMAGE)
        self.assertTrue(ok)
        self.assertIsNone(reason)
        self.assertTrue(self.reserve(IMAGE, "cool-img-2").ok)

    def test_unlimited_text_plan_has_no_cooldown(self):
        plan = make_plan(
            "pro",
            text_essay_weekly_limit=None,
            text_essay_cooldown_hours=5,
            is_unlimited_text_essays=True,
        )
        UserSubscription.objects.filter(user=self.student).update(plan=plan)
        self.assertTrue(commit_usage(self.reserve(TEXT, "cool-unlim-1")))
        # An unlimited tier is not subject to the rolling cooldown.
        self.assertEqual(cooldown_seconds_remaining(self.student), 0)
        self.assertTrue(self.reserve(TEXT, "cool-unlim-2").ok)

    def test_zero_cooldown_never_blocks(self):
        self.plan.text_essay_cooldown_hours = 0
        self.plan.save(update_fields=["text_essay_cooldown_hours", "updated_at"])
        self.assertTrue(commit_usage(self.reserve(TEXT, "cool-zero-1")))
        self.assertEqual(cooldown_seconds_remaining(self.student), 0)
        self.assertTrue(self.reserve(TEXT, "cool-zero-2").ok)


class IdempotencyAndReleaseTests(_QuotaTestCase):
    def test_same_idempotency_key_is_charged_once(self):
        first = self.reserve(TEXT, "same-key")
        self.assertTrue(first.ok)
        self.assertFalse(first.replayed)

        second = self.reserve(TEXT, "same-key")
        self.assertTrue(second.ok)
        self.assertTrue(second.replayed)
        self.assertEqual(second.usage.pk, first.usage.pk)
        self.assertEqual(SubscriptionUsage.objects.count(), 1)
        self.assertEqual(get_remaining_limits(self.student)["text_essay"]["used"], 1)

    def test_commit_then_same_key_retry_does_not_charge_again(self):
        """An internal AI retry must not consume a second essay allowance."""
        reservation = self.reserve(TEXT, "retry-key")
        self.assertTrue(reservation.ok)
        self.assertTrue(commit_usage(reservation))

        retry = self.reserve(TEXT, "retry-key")
        self.assertTrue(retry.replayed)
        self.assertEqual(SubscriptionUsage.objects.count(), 1)
        self.assertEqual(
            SubscriptionUsage.objects.get().status,
            SubscriptionUsage.Status.COMMITTED,
        )
        self.assertEqual(get_remaining_limits(self.student)["text_essay"]["used"], 1)

    def test_release_frees_a_reserved_allowance(self):
        keys = ["rel-a", "rel-b", "rel-c"]
        for key in keys:
            self.assertTrue(self.reserve(TEXT, key).ok)
        self.assertFalse(self.reserve(TEXT, "rel-d").ok)

        released = SubscriptionUsage.objects.get(idempotency_key="rel-c")
        self.assertTrue(release_usage(released))

        after = self.reserve(TEXT, "rel-d")
        self.assertTrue(after.ok, after.message)
        self.assertEqual(
            SubscriptionUsage.objects.filter(
                status=SubscriptionUsage.Status.RELEASED,
            ).count(),
            1,
        )
        self.assertEqual(get_remaining_limits(self.student)["text_essay"]["used"], 3)

    def test_release_does_not_free_a_committed_allowance(self):
        keys = ["keep-a", "keep-b", "keep-c"]
        for key in keys:
            self.assertTrue(commit_usage(self.reserve(TEXT, key)))
        self.assertFalse(self.reserve(TEXT, "keep-d").ok)

        committed = SubscriptionUsage.objects.get(idempotency_key="keep-c")
        self.assertFalse(release_usage(committed))
        committed.refresh_from_db()
        self.assertEqual(committed.status, SubscriptionUsage.Status.COMMITTED)
        self.assertFalse(self.reserve(TEXT, "keep-d").ok)

    def test_duplicate_delivery_of_a_released_operation_is_reported_as_released(self):
        """A retried delivery of an *abandoned* operation is not silently
        re-charged; the caller is told the attempt was released."""
        reservation = self.reserve(TEXT, "abandoned")
        self.assertTrue(release_usage(reservation))

        replay = self.reserve(TEXT, "abandoned")
        self.assertFalse(replay.ok)
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.reason, "released")
        self.assertEqual(SubscriptionUsage.objects.count(), 1)

    def test_reservations_are_recorded_against_the_current_window(self):
        result = self.reserve(TEXT, "window-row")
        self.assertEqual(
            result.usage.period_start,
            quota_period_start(timezone.now()),
        )
        self.assertTrue(result.usage.counts_towards_quota)
        self.assertEqual(result.usage.plan_type_snapshot, "start")
        self.assertEqual(result.usage.user_id, self.student.pk)


class LastAllowanceTests(TransactionTestCase):
    """The last remaining allowance must be handed out exactly once."""

    reset_sequences = True

    def setUp(self):
        self.student = User.objects.create_user(
            email="last-allowance@example.test",
            password="StrongPass123!",
            role="student",
        )
        plan = make_plan(
            "start",
            image_essay_weekly_limit=0,
            text_essay_weekly_limit=1,
            text_essay_cooldown_hours=0,
        )
        UserSubscription.objects.create(
            user=self.student,
            plan=plan,
            status=UserSubscription.Status.ACTIVE,
            started_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=30),
        )

    def tearDown(self):
        connections.close_all()

    def test_sequential_last_allowance_cannot_be_double_spent(self):
        """Deterministic form of the race (runs on every backend)."""
        first = reserve_usage(self.student, TEXT, idempotency_key="last-1")
        self.assertTrue(first.ok)

        second = reserve_usage(self.student, TEXT, idempotency_key="last-2")
        self.assertFalse(second.ok)
        self.assertEqual(second.reason, "limit_exceeded")
        self.assertEqual(SubscriptionUsage.objects.count(), 1)

    @unittest.skipUnless(
        IS_POSTGRESQL,
        "PostgreSQL is the target for the true race; run with "
        "config.settings.postgres_test to execute it.",
    )
    def test_simultaneous_reservations_hand_out_one_allowance(self):
        """Four simultaneous submissions, one remaining allowance.

        Requires PostgreSQL: ``select_for_update`` actually locks the user row
        there. On SQLite the same test would prove nothing, which is why it is
        skipped instead of being reported as a pass.
        """
        results: list = []
        user_id = self.student.pk

        def attempt(key: str) -> None:
            try:
                user = User.objects.get(pk=user_id)
                reservation = reserve_usage(
                    user,
                    TEXT,
                    idempotency_key=key,
                    source="race-test",
                )
                results.append(reservation.ok)
            except Exception as exc:  # pragma: no cover - surfaced in the assert
                results.append(exc)
            finally:
                connections.close_all()

        threads = [
            Thread(target=attempt, args=(f"race-{index}",)) for index in range(4)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(
            sum(1 for result in results if result is True),
            1,
            f"exactly one reservation may win, got {results!r}",
        )
        self.assertEqual(SubscriptionUsage.objects.count(), 1)
