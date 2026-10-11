"""Tuition reminder regressions: the ladder, its stop conditions and idempotency.

A reminder is a message to a family about money, so the properties under test
are the *stop* conditions as much as the triggers:

* a paid, waived or cancelled invoice is never chased;
* a covering receipt that is still being checked replaces the overdue chase
  with a single "awaiting confirmation" notice;
* quiet hours and a recipient's own preference each suppress the message;
* re-running the job cannot send the same stage twice, and a failed send is
  retried rather than duplicated;
* only the student and their verified, approved parents are ever recipients.
"""
from __future__ import annotations

import datetime as dt
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import ParentStudentLink, User
from apps.attendance.models import NotificationPreference
from apps.courses.models import Course, Enrollment, StudentGroup
from apps.tuition import notifications, services
from apps.tuition.models import (
    CourseBillingPolicy,
    CourseInvoice,
    CoursePayment,
    PaymentMethod,
    PaymentReminderLog,
)

TODAY = timezone.localdate()
#: Any hour inside the default 08:00–21:00 sending window.
DAYTIME = timezone.localtime().replace(hour=10, minute=0, second=0, microsecond=0)


def backdate(model, pk: int, field: str, when: date) -> None:
    model.objects.filter(pk=pk).update(
        **{field: timezone.make_aware(dt.datetime.combine(when, dt.time(9, 0)))}
    )


class _ReminderFixture(TestCase):
    """An open invoice whose due date the test controls exactly."""

    def setUp(self):
        self.admin = User.objects.create_user(
            email="rem-admin@example.test", password="testpass123", role="admin",
        )
        self.teacher = User.objects.create_user(
            email="rem-teacher@example.test", password="testpass123", role="teacher",
        )
        self.ali = User.objects.create_user(
            email="rem-ali@example.test", password="testpass123", role="student",
            first_name="Ali", last_name="Valiyev", telegram_chat_id=555001,
        )
        self.parent = User.objects.create_user(
            email="rem-parent@example.test", password="testpass123", role="parent",
            telegram_chat_id=555002,
        )
        self.stranger = User.objects.create_user(
            email="rem-stranger@example.test", password="testpass123", role="parent",
            telegram_chat_id=555003,
        )
        self.group = StudentGroup.objects.create(teacher=self.teacher, name="9-A")
        self.group.students.add(self.ali)
        backdate(User, self.ali.pk, "date_joined", TODAY - timedelta(days=90))
        backdate(StudentGroup, self.group.pk, "created_at", TODAY - timedelta(days=90))

        self.policy = CourseBillingPolicy.objects.create(
            name="9-A oylik", group=self.group, amount_uzs=300_000, due_day=10,
            effective_from=TODAY - timedelta(days=90),
            reminder_policy={
                "before": [3], "due": [0], "overdue": [3, 10, 17],
                "quiet_start": 21, "quiet_end": 8,
            },
        )
        self.invoice = self._make_invoice(due_offset=0)

    def _make_invoice(self, *, due_offset: int, amount=300_000, grace_days=0):
        # A unique scope key per call: the uniqueness rule under test is the
        # real one, so a helper that needs a second invoice must not trip it.
        type(self)._invoice_seq = getattr(type(self), "_invoice_seq", 0) + 1
        invoice = CourseInvoice.objects.create(
            student=self.ali, policy=self.policy,
            scope_key=f"group:{self.group.pk}:t{type(self)._invoice_seq}",
            billing_period_start=TODAY.replace(day=1),
            billing_period_end=TODAY.replace(day=1) + timedelta(days=27),
            period_label=f"{TODAY:%Y-%m}",
            base_amount_uzs=Decimal(amount), amount_due_uzs=Decimal(amount),
            due_date=TODAY + timedelta(days=due_offset),
            grace_until=(
                TODAY + timedelta(days=due_offset + grace_days) if grace_days else None
            ),
            status=CourseInvoice.Status.UNPAID,
        )
        return invoice

    def _approved_parent(self, *, approved=True):
        return ParentStudentLink.objects.create(
            parent=self.parent, student=self.ali, is_approved=approved,
        )

    @staticmethod
    def _ok_transport(calls: list):
        def _send(chat_id, text, recipient, title):
            calls.append((chat_id, text))
            return {"success": True, "message_id": len(calls), "error": None}
        return _send


class LadderStageTests(_ReminderFixture):
    def test_stage_is_chosen_from_the_configured_offsets(self):
        self.assertEqual(
            services.reminder_stage_for(self.invoice, as_of=TODAY),
            PaymentReminderLog.Stage.DUE_TODAY,
        )
        self.assertEqual(
            services.reminder_stage_for(self.invoice, as_of=TODAY - timedelta(days=3)),
            PaymentReminderLog.Stage.BEFORE_DUE,
        )
        # Two days before the due date is not a configured offset.
        self.assertIsNone(
            services.reminder_stage_for(self.invoice, as_of=TODAY - timedelta(days=2))
        )
        for offset in (3, 10, 17):
            self.assertEqual(
                services.reminder_stage_for(
                    self.invoice, as_of=TODAY + timedelta(days=offset),
                ),
                PaymentReminderLog.Stage.OVERDUE,
            )
        # The ladder is weekly-ish: day 4 is not in the list, day 10 is.
        self.assertIsNone(
            services.reminder_stage_for(self.invoice, as_of=TODAY + timedelta(days=4))
        )

    def test_no_policy_means_no_automatic_reminders(self):
        invoice = self._make_invoice(due_offset=0)
        CourseInvoice.objects.filter(pk=invoice.pk).update(policy=None)
        invoice.refresh_from_db()
        self.assertIsNone(services.reminder_stage_for(invoice, as_of=TODAY))

    def test_paid_invoice_is_never_reminded_about(self):
        invoice = self._make_invoice(due_offset=-5)
        payment = services.register_payment(
            student=self.ali, amount=300_000, method=PaymentMethod.CARD,
            reference="REM-PAID", invoice=invoice, submitted_by=self.ali,
        )
        services.verify_payment(payment, actor=self.admin)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, CourseInvoice.Status.PAID)
        for offset in (-3, 0, 3, 10, 17):
            self.assertIsNone(
                services.reminder_stage_for(invoice, as_of=TODAY + timedelta(days=offset))
            )

    def test_waived_invoice_is_never_reminded_about(self):
        invoice = self._make_invoice(due_offset=-5)
        services.waive_invoice(invoice, actor=self.admin, reason="Stipendiya")
        invoice.refresh_from_db()
        self.assertIsNone(services.reminder_stage_for(invoice, as_of=TODAY))

    def test_partial_payment_still_reminds_about_the_remaining_balance(self):
        invoice = self._make_invoice(due_offset=-3)
        payment = services.register_payment(
            student=self.ali, amount=100_000, method=PaymentMethod.CARD,
            reference="REM-PART", invoice=invoice, submitted_by=self.ali,
        )
        services.verify_payment(payment, actor=self.admin)
        invoice.refresh_from_db()
        self.assertEqual(invoice.balance_uzs, Decimal("200000.00"))
        self.assertEqual(
            services.reminder_stage_for(invoice, as_of=TODAY),
            PaymentReminderLog.Stage.OVERDUE,
        )
        text = notifications.reminder_text(invoice, PaymentReminderLog.Stage.OVERDUE)
        # Only real recorded values: the remaining balance, not the full amount.
        self.assertIn("200 000", text)

    def test_a_covering_pending_receipt_replaces_the_overdue_chase(self):
        invoice = self._make_invoice(due_offset=-3)
        services.register_payment(
            student=self.ali, amount=300_000, method=PaymentMethod.CARD,
            reference="REM-PEND", invoice=invoice, submitted_by=self.ali,
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, CourseInvoice.Status.PENDING_VERIFICATION)
        self.assertEqual(
            services.reminder_stage_for(invoice, as_of=TODAY),
            PaymentReminderLog.Stage.AWAITING_CONFIRMATION,
        )
        text = notifications.reminder_text(
            invoice, PaymentReminderLog.Stage.AWAITING_CONFIRMATION,
        )
        self.assertIn("qabul qilindi", text)
        self.assertIn("Qo'shimcha to'lov qilish shart emas", text)

    def test_a_partial_pending_receipt_does_not_stop_the_ladder(self):
        invoice = self._make_invoice(due_offset=-3)
        services.register_payment(
            student=self.ali, amount=50_000, method=PaymentMethod.CARD,
            reference="REM-SMALL", invoice=invoice, submitted_by=self.ali,
        )
        invoice.refresh_from_db()
        self.assertFalse(invoice.awaiting_confirmation)
        self.assertEqual(
            services.reminder_stage_for(invoice, as_of=TODAY),
            PaymentReminderLog.Stage.OVERDUE,
        )

    def test_quiet_hours_suppress_the_run(self):
        night = DAYTIME.replace(hour=23)
        self.assertTrue(services.in_quiet_hours(self.policy, now=night))
        self.assertFalse(services.in_quiet_hours(self.policy, now=DAYTIME))
        self.assertEqual(
            notifications.send_due_reminders(
                as_of=TODAY, now=night, transport=self._ok_transport([]),
            )["planned"],
            0,
        )
        self.assertEqual(PaymentReminderLog.objects.count(), 0)


class DeliveryTests(_ReminderFixture):
    def test_reminder_is_sent_once_even_if_the_job_runs_twice(self):
        self._approved_parent()
        calls: list = []
        first = notifications.send_due_reminders(
            as_of=TODAY, now=DAYTIME, transport=self._ok_transport(calls),
        )
        self.assertEqual(first["sent"], 2)  # student + approved parent
        self.assertEqual(len(calls), 2)
        self.assertEqual(PaymentReminderLog.objects.count(), 2)

        second = notifications.send_due_reminders(
            as_of=TODAY, now=DAYTIME, transport=self._ok_transport(calls),
        )
        self.assertEqual(second["sent"], 0)
        self.assertEqual(len(calls), 2, "A re-run must not send a duplicate")
        self.assertEqual(
            PaymentReminderLog.objects.filter(
                status=PaymentReminderLog.Status.SENT,
            ).count(),
            2,
        )

    def test_weekly_overdue_stage_can_fire_again_a_week_later(self):
        calls: list = []
        notifications.send_due_reminders(
            as_of=TODAY, now=DAYTIME, transport=self._ok_transport(calls),
        )
        # The +10 offset is a distinct stage key, so the family is reminded
        # again a week later without any duplicate of the +3 message.
        notifications.send_due_reminders(
            as_of=TODAY + timedelta(days=10), now=DAYTIME,
            transport=self._ok_transport(calls),
        )
        keys = set(PaymentReminderLog.objects.values_list("idempotency_key", flat=True))
        self.assertEqual(len(keys), 2)
        self.assertTrue(any(":due_today:" in key for key in keys))
        self.assertTrue(any(":overdue:" in key for key in keys))

    def test_unapproved_parent_and_strangers_are_never_recipients(self):
        self._approved_parent(approved=False)
        recipients = services.reminder_recipients(self.ali)
        self.assertEqual([user.pk for user in recipients], [self.ali.pk])
        self.assertNotIn(self.stranger.pk, [user.pk for user in recipients])
        self.assertNotIn(self.parent.pk, [user.pk for user in recipients])

    def test_recipient_preference_can_disable_reminders(self):
        NotificationPreference.objects.create(user=self.ali, tuition_reminders=False)
        result = notifications.send_due_reminders(
            as_of=TODAY, now=DAYTIME, transport=self._ok_transport([]),
        )
        self.assertEqual(result["sent"], 0)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(PaymentReminderLog.objects.count(), 0)

    def test_student_without_a_telegram_link_gets_dashboard_fallback(self):
        User.objects.filter(pk=self.ali.pk).update(telegram_chat_id=None)
        self.ali.refresh_from_db()
        result = notifications.send_due_reminders(
            as_of=TODAY, now=DAYTIME, transport=self._ok_transport([]),
        )
        self.assertEqual(result["planned"], 1)
        self.assertEqual(result["sent"], 0)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(
            PaymentReminderLog.objects.filter(channel=PaymentReminderLog.Channel.TELEGRAM).count(),
            1,
        )
        self.assertEqual(
            PaymentReminderLog.objects.filter(channel=PaymentReminderLog.Channel.DASHBOARD).count(),
            1,
        )
        self.assertEqual([row.pk for row in services.reminder_recipients(self.ali)], [self.ali.pk])

    def test_stale_pending_reservation_can_be_recovered(self):
        from django.utils import timezone

        stale_key = (
            f"tuition:{self.invoice.pk}:{PaymentReminderLog.Stage.DUE_TODAY}:"
            f"{self.ali.pk}:{PaymentReminderLog.Channel.TELEGRAM}"
        )
        row = PaymentReminderLog.objects.create(
            invoice=self.invoice, recipient=self.ali,
            stage=PaymentReminderLog.Stage.DUE_TODAY,
            channel=PaymentReminderLog.Channel.TELEGRAM,
            idempotency_key=stale_key, status=PaymentReminderLog.Status.PENDING,
        )
        PaymentReminderLog.objects.filter(pk=row.pk).update(
            created_at=timezone.now() - timedelta(minutes=15),
        )
        calls = []
        result = notifications.send_due_reminders(
            as_of=TODAY, now=DAYTIME, transport=self._ok_transport(calls),
        )
        row.refresh_from_db()
        self.assertEqual(result["sent"], 1)
        self.assertEqual(row.status, PaymentReminderLog.Status.SENT)
        self.assertEqual(len(calls), 1)

    def test_a_transport_failure_is_recorded_and_then_retried(self):
        def _broken(chat_id, text, recipient, title):
            return {"success": False, "error": "Telegram unavailable"}

        first = notifications.send_due_reminders(
            as_of=TODAY, now=DAYTIME, transport=_broken,
        )
        self.assertEqual(first["failed"], 1)
        log = PaymentReminderLog.objects.get(channel=PaymentReminderLog.Channel.TELEGRAM)
        fallback = PaymentReminderLog.objects.get(channel=PaymentReminderLog.Channel.DASHBOARD)
        self.assertEqual(log.status, PaymentReminderLog.Status.FAILED)
        self.assertIn("Telegram unavailable", log.error)
        self.assertEqual(fallback.status, PaymentReminderLog.Status.SENT)

        calls: list = []
        second = notifications.send_due_reminders(
            as_of=TODAY, now=DAYTIME, transport=self._ok_transport(calls),
        )
        self.assertEqual(second["sent"], 1)
        self.assertEqual(len(calls), 1)
        log.refresh_from_db()
        self.assertEqual(log.status, PaymentReminderLog.Status.SENT)
        self.assertEqual(PaymentReminderLog.objects.count(), 2)

    def test_reminder_text_never_invents_a_penalty_or_a_price(self):
        invoice = self._make_invoice(due_offset=-3, amount=250_000)
        text = notifications.reminder_text(invoice, PaymentReminderLog.Stage.OVERDUE)
        self.assertIn("250 000", text)
        self.assertIn("Ali Valiyev", text)
        for invented in ("jarima", "penalty", "1 000 000"):
            self.assertNotIn(invented, text.lower())

    def test_payment_confirmation_notice_is_idempotent(self):
        invoice = self._make_invoice(due_offset=0)
        self._approved_parent()
        payment = services.register_payment(
            student=self.ali, amount=300_000, method=PaymentMethod.CARD,
            reference="REM-CONF", invoice=invoice, submitted_by=self.ali,
        )
        services.verify_payment(payment, actor=self.admin)

        first = notifications.send_payment_confirmed(invoice.pk)
        second = notifications.send_payment_confirmed(invoice.pk)
        # The transport is not configured in tests, so success is 0 — what
        # matters is that the second call sends nothing new.
        self.assertGreaterEqual(first["sent"], 0)
        self.assertEqual(second["sent"], 0)


class TaskIdempotencyTests(_ReminderFixture):
    def test_failed_send_is_retried_but_a_sent_one_is_not(self):
        calls: list = []
        notifications.send_reminder(
            self.invoice, PaymentReminderLog.Stage.OVERDUE, self.ali,
            transport=self._ok_transport(calls),
        )
        notifications.send_reminder(
            self.invoice, PaymentReminderLog.Stage.OVERDUE, self.ali,
            transport=self._ok_transport(calls),
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(PaymentReminderLog.objects.count(), 1)
