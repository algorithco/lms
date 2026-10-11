"""Telegram Stars (XTR) purchases and the subscription lifecycle.

Access must only ever be activated by a verified ``successful_payment`` that
matches the order's opaque payload *and* the charged amount. Invoice creation
and pre-checkout must never grant entitlement, and Telegram's at-least-once
update delivery must not grant a second period.

Two source-level gaps found while writing these tests are documented as skipped
tests at the bottom of this file rather than being asserted as correct
behaviour.
"""

import unittest
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.payments.models import (
    EntitlementAuditLog,
    SubscriptionPlan,
    TelegramOrder,
    UserSubscription,
)
from apps.payments.stars import (
    activate_from_successful_payment,
    cancel_order,
    create_order,
    mark_invoice_sent,
    pending_orders_for,
    refund_order,
    validate_pre_checkout,
)
from apps.payments.subscriptions import (
    expire_overdue_subscriptions,
    grant_subscription,
    plan_rank,
    revoke_subscription,
)

STARS = 100


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


class _StarsFixture(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            email="stars-student@example.test",
            password="StrongPass123!",
            role="student",
        )
        self.plan = make_plan(
            "start",
            price_monthly=15000,
            telegram_stars_price=STARS,
            is_public=True,
            duration_days=30,
        )

    def _activate(self, order, *, charge_id="tg-charge-1", **overrides):
        payload = {
            "payload": order.payload,
            "currency": "XTR",
            "total_amount": order.amount_stars,
            "telegram_payment_charge_id": charge_id,
        }
        payload.update(overrides)
        return activate_from_successful_payment(**payload)


class OrderCreationTests(_StarsFixture):
    def test_order_requires_a_configured_stars_price(self):
        plan = make_plan("starter", telegram_stars_price=None, is_public=True)
        with self.assertRaises(ValueError) as ctx:
            create_order(self.student, plan)
        self.assertIn("Telegram Stars narxi", str(ctx.exception))
        self.assertEqual(TelegramOrder.objects.count(), 0)

    def test_sponsored_plan_cannot_be_purchased(self):
        plan = make_plan(
            "teacher_sponsored", telegram_stars_price=STARS, is_public=True,
        )
        with self.assertRaises(ValueError) as ctx:
            create_order(self.student, plan)
        self.assertIn("Homiylik", str(ctx.exception))

    def test_non_public_plan_cannot_be_purchased(self):
        plan = make_plan("premium", telegram_stars_price=STARS, is_public=False)
        with self.assertRaises(ValueError) as ctx:
            create_order(self.student, plan)
        self.assertIn("sotuvda emas", str(ctx.exception))

    def test_inactive_plan_cannot_be_purchased(self):
        plan = make_plan(
            "family", telegram_stars_price=STARS, is_public=True, is_active=False,
        )
        with self.assertRaises(ValueError):
            create_order(self.student, plan)

    def test_created_order_records_the_amount_and_starts_unpaid(self):
        order = create_order(self.student, self.plan)
        self.assertEqual(order.amount_stars, STARS)
        self.assertEqual(order.currency, "XTR")
        self.assertEqual(order.status, TelegramOrder.Status.CREATED)
        self.assertIsNone(order.paid_at)
        self.assertIsNone(order.telegram_payment_charge_id)
        self.assertEqual(order.user_id, self.student.pk)

    def test_payload_is_unguessable_unique_and_not_a_sequence(self):
        first = create_order(self.student, self.plan)
        second = create_order(self.student, self.plan)
        self.assertNotEqual(first.payload, second.payload)
        for order in (first, second):
            self.assertTrue(order.payload.startswith("grandec:"))
            token = order.payload.split(":", 1)[1]
            # 12 random bytes rendered as hex: long, opaque and not a sequence.
            self.assertEqual(len(token), 24)
            self.assertRegex(token, r"^[0-9a-f]{24}$")
            self.assertNotEqual(token, str(order.pk))

    def test_mark_invoice_sent_and_cancel_are_state_guarded(self):
        order = create_order(self.student, self.plan)
        mark_invoice_sent(order)
        order.refresh_from_db()
        self.assertEqual(order.status, TelegramOrder.Status.INVOICE_SENT)

        cancel_order(order)
        order.refresh_from_db()
        self.assertEqual(order.status, TelegramOrder.Status.CANCELLED)

        # Cancelling a paid order is a no-op.
        order.status = TelegramOrder.Status.PAID
        order.save(update_fields=["status"])
        cancel_order(order)
        order.refresh_from_db()
        self.assertEqual(order.status, TelegramOrder.Status.PAID)

    def test_pending_orders_only_lists_open_orders(self):
        open_order = create_order(self.student, self.plan)
        closed = create_order(self.student, self.plan)
        cancel_order(closed)
        pending = pending_orders_for(self.student)
        self.assertEqual([o.pk for o in pending], [open_order.pk])


class PreCheckoutTests(_StarsFixture):
    def setUp(self):
        super().setUp()
        self.order = create_order(self.student, self.plan)

    def test_unknown_payload_is_rejected(self):
        ok, error, order = validate_pre_checkout(
            payload="grandec:deadbeefdeadbeefdeadbeef",
            currency="XTR",
            total_amount=STARS,
        )
        self.assertFalse(ok)
        self.assertEqual(error, "Buyurtma topilmadi.")
        self.assertIsNone(order)

    def test_wrong_currency_is_rejected(self):
        ok, error, _order = validate_pre_checkout(
            payload=self.order.payload, currency="USD", total_amount=STARS,
        )
        self.assertFalse(ok)
        self.assertIn("valyuta", error)

    def test_mismatched_amount_is_rejected(self):
        ok, error, _order = validate_pre_checkout(
            payload=self.order.payload, currency="XTR", total_amount=STARS + 1,
        )
        self.assertFalse(ok)
        self.assertIn("summasi", error)

    def test_cancelled_order_is_rejected(self):
        cancel_order(self.order)
        ok, error, _order = validate_pre_checkout(
            payload=self.order.payload, currency="XTR", total_amount=STARS,
        )
        self.assertFalse(ok)
        self.assertIn("holati", error)

    def test_price_change_after_invoice_is_rejected(self):
        self.plan.telegram_stars_price = STARS + 50
        self.plan.save(update_fields=["telegram_stars_price", "updated_at"])
        ok, error, _order = validate_pre_checkout(
            payload=self.order.payload, currency="XTR", total_amount=STARS,
        )
        self.assertFalse(ok)
        self.assertIn("narxi", error)

    def test_valid_pre_checkout_activates_nothing(self):
        ok, error, order = validate_pre_checkout(
            payload=self.order.payload, currency="XTR", total_amount=STARS,
        )
        self.assertTrue(ok)
        self.assertIsNone(error)
        self.assertEqual(order.pk, self.order.pk)

        # Nothing may be granted at the pre-checkout stage.
        self.assertEqual(UserSubscription.objects.filter(user=self.student).count(), 0)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, TelegramOrder.Status.CREATED)
        self.assertEqual(EntitlementAuditLog.objects.count(), 0)


class PaymentActivationTests(_StarsFixture):
    def test_missing_charge_id_is_rejected(self):
        order = create_order(self.student, self.plan)
        ok, _message, subscription = self._activate(order, charge_id="")
        self.assertFalse(ok)
        self.assertIsNone(subscription)
        self.assertEqual(UserSubscription.objects.count(), 0)
        order.refresh_from_db()
        self.assertEqual(order.status, TelegramOrder.Status.CREATED)

    def test_unknown_payload_never_grants_access(self):
        ok, _message, subscription = activate_from_successful_payment(
            payload="grandec:unknownunknownunknown",
            currency="XTR",
            total_amount=STARS,
            telegram_payment_charge_id="tg-charge-unknown",
        )
        self.assertFalse(ok)
        self.assertIsNone(subscription)
        self.assertEqual(UserSubscription.objects.count(), 0)

    def test_wrong_currency_fails_the_order_without_activating(self):
        order = create_order(self.student, self.plan)
        ok, _message, subscription = self._activate(order, currency="USD")
        self.assertFalse(ok)
        self.assertIsNone(subscription)
        order.refresh_from_db()
        self.assertEqual(order.status, TelegramOrder.Status.FAILED)
        self.assertEqual(UserSubscription.objects.count(), 0)

    def test_amount_mismatch_fails_the_order_without_activating(self):
        order = create_order(self.student, self.plan)
        ok, _message, subscription = self._activate(
            order, total_amount=STARS - 1,
        )
        self.assertFalse(ok)
        self.assertIsNone(subscription)
        order.refresh_from_db()
        self.assertEqual(order.status, TelegramOrder.Status.FAILED)
        self.assertEqual(UserSubscription.objects.count(), 0)

    def test_successful_payment_activates_exactly_one_subscription(self):
        order = create_order(self.student, self.plan)
        before = timezone.now()
        ok, message, subscription = self._activate(order, charge_id="tg-charge-ok")

        self.assertTrue(ok)
        self.assertEqual(message, "Obuna faollashtirildi.")
        self.assertIsNotNone(subscription)
        self.assertEqual(subscription.status, UserSubscription.Status.ACTIVE)
        self.assertEqual(subscription.plan_id, self.plan.pk)
        self.assertEqual(
            subscription.purchase_source, UserSubscription.Source.TELEGRAM_BOT,
        )
        self.assertEqual(subscription.payment_method, "stars")
        self.assertEqual(subscription.payment_reference, "tg-charge-ok")
        self.assertGreaterEqual(subscription.expires_at, before + timedelta(days=29))
        self.assertLessEqual(subscription.expires_at, before + timedelta(days=31))

        order.refresh_from_db()
        self.assertEqual(order.status, TelegramOrder.Status.PAID)
        self.assertEqual(order.telegram_payment_charge_id, "tg-charge-ok")
        self.assertIsNotNone(order.paid_at)

        self.assertEqual(UserSubscription.objects.count(), 1)
        self.assertTrue(
            EntitlementAuditLog.objects.filter(
                student=self.student,
                action=EntitlementAuditLog.Action.ACTIVATE_SUBSCRIPTION,
            ).exists(),
        )

    def test_replayed_payment_update_is_idempotent(self):
        order = create_order(self.student, self.plan)
        ok, _message, subscription = self._activate(order, charge_id="tg-charge-dup")
        self.assertTrue(ok)
        first_expiry = subscription.expires_at

        again_ok, again_message, again_subscription = self._activate(
            order, charge_id="tg-charge-dup",
        )
        self.assertTrue(again_ok)
        self.assertEqual(again_message, "To'lov allaqachon tasdiqlangan.")
        self.assertEqual(UserSubscription.objects.count(), 1)

        again_subscription.refresh_from_db()
        self.assertEqual(again_subscription.expires_at, first_expiry)
        self.assertEqual(
            EntitlementAuditLog.objects.filter(
                action=EntitlementAuditLog.Action.ACTIVATE_SUBSCRIPTION,
            ).count(),
            1,
        )

    def test_refund_revokes_access_and_is_audited(self):
        order = create_order(self.student, self.plan)
        _ok, _message, subscription = self._activate(order, charge_id="tg-charge-refund")

        self.assertTrue(refund_order(order))
        order.refresh_from_db()
        self.assertEqual(order.status, TelegramOrder.Status.REFUNDED)
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, UserSubscription.Status.REFUNDED)
        self.assertTrue(
            EntitlementAuditLog.objects.filter(
                student=self.student,
                action=EntitlementAuditLog.Action.REFUND_SUBSCRIPTION,
            ).exists(),
        )
        # Refunding twice is a no-op, not a second revocation event.
        self.assertTrue(refund_order(order))
        self.assertEqual(
            EntitlementAuditLog.objects.filter(
                action=EntitlementAuditLog.Action.REFUND_SUBSCRIPTION,
            ).count(),
            1,
        )


class SubscriptionLifecycleTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            email="lifecycle-student@example.test",
            password="StrongPass123!",
            role="student",
        )
        self.start_plan = make_plan(
            "start", text_essay_weekly_limit=3, image_essay_weekly_limit=5,
            duration_days=30,
        )
        self.pro_plan = make_plan(
            "pro", is_unlimited_text_essays=True, is_unlimited_image_essays=True,
            is_unlimited_tests=True, duration_days=30,
        )

    def test_first_activation_starts_now_for_the_full_duration(self):
        before = timezone.now()
        subscription = grant_subscription(
            self.student, self.start_plan,
            source=UserSubscription.Source.WEBSITE,
            payment_method="card",
            payment_reference="receipt-1",
        )
        self.assertEqual(subscription.plan_id, self.start_plan.pk)
        self.assertEqual(subscription.status, UserSubscription.Status.ACTIVE)
        self.assertGreaterEqual(subscription.expires_at, before + timedelta(days=29))
        self.assertLessEqual(subscription.expires_at, before + timedelta(days=31))
        self.assertIsNotNone(subscription.started_at)

    def test_upgrading_to_pro_extends_from_the_later_expiry(self):
        basic = grant_subscription(self.student, self.start_plan)
        original_expiry = basic.expires_at

        upgraded = grant_subscription(self.student, self.pro_plan)
        self.assertEqual(upgraded.pk, basic.pk)
        self.assertEqual(upgraded.plan_id, self.pro_plan.pk)
        # Extended from the existing expiry, not restarted from now.
        self.assertEqual(
            upgraded.expires_at,
            original_expiry + timedelta(days=30),
        )
        self.assertEqual(UserSubscription.objects.count(), 1)

    def test_buying_start_while_pro_is_active_does_not_downgrade(self):
        pro = grant_subscription(self.student, self.pro_plan)
        original_expiry = pro.expires_at

        renewed = grant_subscription(self.student, self.start_plan)
        self.assertEqual(renewed.pk, pro.pk)
        self.assertEqual(renewed.plan_id, self.pro_plan.pk)
        renewed.refresh_from_db()
        self.assertEqual(renewed.plan.plan_type, "pro")
        self.assertEqual(renewed.expires_at, original_expiry + timedelta(days=30))
        # The richer plan and its snapshot are preserved.
        self.assertTrue(renewed.plan_snapshot.get("is_unlimited_text_essays"))

    def test_expired_subscription_is_restarted_not_extended(self):
        subscription = grant_subscription(self.student, self.start_plan)
        UserSubscription.objects.filter(pk=subscription.pk).update(
            expires_at=timezone.now() - timedelta(days=10),
        )
        before = timezone.now()
        renewed = grant_subscription(self.student, self.start_plan)
        self.assertGreaterEqual(renewed.expires_at, before + timedelta(days=29))

    def test_expire_overdue_flips_only_past_due_subscriptions(self):
        active = grant_subscription(self.student, self.start_plan)
        other = User.objects.create_user(
            email="lifecycle-other@example.test", password="StrongPass123!",
            role="student",
        )
        stale = grant_subscription(other, self.start_plan)
        UserSubscription.objects.filter(pk=stale.pk).update(
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        self.assertEqual(expire_overdue_subscriptions(), 1)
        active.refresh_from_db()
        stale.refresh_from_db()
        self.assertEqual(active.status, UserSubscription.Status.ACTIVE)
        self.assertEqual(stale.status, UserSubscription.Status.EXPIRED)

    def test_administrative_revocation_is_audited(self):
        grant_subscription(self.student, self.pro_plan)
        self.assertTrue(revoke_subscription(self.student, reason="chargeback"))
        subscription = UserSubscription.objects.get(user=self.student)
        self.assertEqual(subscription.status, UserSubscription.Status.REVOKED)
        self.assertIsNotNone(subscription.cancelled_at)
        self.assertTrue(
            EntitlementAuditLog.objects.filter(
                student=self.student,
                action=EntitlementAuditLog.Action.REVOKE_SUBSCRIPTION,
            ).exists(),
        )

    def test_plan_rank_orders_the_tiers(self):
        self.assertEqual(plan_rank(None), 0)
        self.assertEqual(plan_rank(make_plan("teacher_sponsored")), 0)
        self.assertEqual(plan_rank(make_plan("free")), 0)
        self.assertEqual(plan_rank(make_plan("start")), plan_rank(make_plan("starter")))
        self.assertEqual(plan_rank(make_plan("pro")), plan_rank(make_plan("premium")))
        self.assertGreater(plan_rank(make_plan("family")), plan_rank(make_plan("pro")))
        self.assertGreater(plan_rank(make_plan("pro")), plan_rank(make_plan("start")))

    def test_snapshot_is_refreshed_when_an_existing_subscription_is_renewed(self):
        """A later plan edit must not rewrite entitlements already held.

        On the renewal path the row's frozen snapshot is written from the plan
        as it stands at that moment, and it is never re-derived from a plan that
        an administrator edits afterwards.
        """
        subscription = grant_subscription(self.student, self.start_plan)
        renewed = grant_subscription(self.student, self.start_plan)
        self.assertEqual(
            renewed.plan_snapshot.get("text_essay_weekly_limit"), 3,
        )

        self.start_plan.text_essay_weekly_limit = 99
        self.start_plan.save(update_fields=["text_essay_weekly_limit", "updated_at"])
        renewed.refresh_from_db()
        self.assertEqual(
            renewed.plan_snapshot.get("text_essay_weekly_limit"), 3,
        )
        self.assertEqual(
            renewed.entitlement_snapshot.get("text_essay_weekly_limit"), 3,
        )
        self.assertNotEqual(subscription.pk, None)


class ActivationDurabilityTests(_StarsFixture):
    """Two defects found while writing these tests, now fixed and pinned.

    Both were real source bugs in ``apps/payments`` and are asserted here so a
    regression fails the suite instead of passing silently.
    """

    def test_duplicate_charge_id_from_a_second_order_activates_once(self):
        """A replayed charge id must resolve, not explode.

        The charge-id save runs inside a nested savepoint: without it the
        ``IntegrityError`` raised by the UNIQUE ``telegram_payment_charge_id``
        would mark the outer transaction as needing rollback and the
        follow-up read would raise ``TransactionManagementError``.
        """
        first = create_order(self.student, self.plan)
        second = create_order(self.student, self.plan)

        ok, _message, subscription = self._activate(first, charge_id="tg-charge-shared")
        self.assertTrue(ok)
        first_expiry = subscription.expires_at

        ok_again, message, again = self._activate(second, charge_id="tg-charge-shared")
        self.assertTrue(ok_again)
        self.assertEqual(message, "To'lov allaqachon tasdiqlangan.")
        self.assertEqual(UserSubscription.objects.count(), 1)
        self.assertEqual(again.expires_at, first_expiry)

    def test_snapshot_is_recorded_on_first_activation(self):
        """A brand-new activation freezes the plan and entitlement snapshots.

        They used to be written only on the renewal branch, so a first
        purchase recorded an empty snapshot and a later plan edit could be
        read as if it were the student's original entitlement.
        """
        self.plan.text_essay_weekly_limit = 3
        self.plan.image_essay_weekly_limit = 5
        self.plan.save(update_fields=[
            "text_essay_weekly_limit", "image_essay_weekly_limit", "updated_at",
        ])

        subscription = grant_subscription(self.student, self.plan)
        self.assertEqual(
            subscription.plan_snapshot.get("text_essay_weekly_limit"), 3,
        )
        self.assertEqual(
            subscription.entitlement_snapshot.get("text_essay_weekly_limit"), 3,
        )
        self.assertEqual(
            subscription.entitlement_snapshot.get("image_essay_weekly_limit"), 5,
        )

    def test_plan_edit_after_purchase_does_not_rewrite_the_snapshot(self):
        """Editing a plan must not retroactively change what was bought."""
        self.plan.text_essay_weekly_limit = 3
        self.plan.save(update_fields=["text_essay_weekly_limit", "updated_at"])
        grant_subscription(self.student, self.plan)

        self.plan.text_essay_weekly_limit = 99
        self.plan.save(update_fields=["text_essay_weekly_limit", "updated_at"])

        subscription = UserSubscription.objects.get(user=self.student)
        self.assertEqual(
            subscription.plan_snapshot.get("text_essay_weekly_limit"), 3,
        )
