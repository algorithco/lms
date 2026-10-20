"""Course tuition regressions: invoicing, the payment lifecycle and isolation.

Course tuition is tested against the same service layer the admin, the REST API
and the Telegram bot call. The load-bearing properties are:

* an amount is never invented (a policy with no price bills nothing);
* one invoice per (student, period, scope) — a re-run cannot double-bill;
* money is not real until an authorized human confirms it;
* being overdue never touches enrollment or platform entitlements;
* course tuition and the platform subscription stay independent.
"""

from __future__ import annotations

import datetime as dt
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.courses.models import Course, Enrollment, StudentGroup
from apps.payments.entitlements import SOURCE_SPONSORED, get_effective_entitlement
from apps.payments.models import (
    SubscriptionPlan,
    TeacherSponsorship,
    UserSubscription,
)
from apps.tuition import services
from apps.tuition.models import (
    CourseBillingPolicy,
    CourseInvoice,
    CoursePayment,
    MidMonthPolicy,
    PaymentMethod,
    PaymentReminderLog,
    StudentTuitionAgreement,
    TuitionAuditLog,
)

TODAY = timezone.localdate()
MONTH_START, MONTH_END = services.month_bounds(TODAY)


def backdate(model, pk: int, field: str, when: date) -> None:
    """Pin an auto_now_add timestamp so period math is deterministic.

    ``Enrollment.enrolled_at``, ``StudentGroup.created_at`` and
    ``User.date_joined`` are all ``auto_now_add``, so a test that exercises
    proration has to write the date directly through ``update()``.
    """
    model.objects.filter(pk=pk).update(
        **{field: timezone.make_aware(dt.datetime.combine(when, dt.time(9, 0)))}
    )


def make_plan(plan_type: str, **overrides) -> SubscriptionPlan:
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
        "is_public": False,
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


class _TuitionFixture(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="tui-admin@example.test",
            password="testpass123",
            role="admin",
        )
        self.teacher = User.objects.create_user(
            email="tui-teacher@example.test",
            password="testpass123",
            role="teacher",
        )
        self.ali = User.objects.create_user(
            email="tui-ali@example.test",
            password="testpass123",
            role="student",
            first_name="Ali",
            last_name="Valiyev",
        )
        self.zuhra = User.objects.create_user(
            email="tui-zuhra@example.test",
            password="testpass123",
            role="student",
            first_name="Zuhra",
            last_name="Karimova",
        )
        self.outsider = User.objects.create_user(
            email="tui-outsider@example.test",
            password="testpass123",
            role="student",
        )
        self.group = StudentGroup.objects.create(teacher=self.teacher, name="9-A")
        self.group.students.add(self.ali, self.zuhra)
        self.course = Course.objects.create(
            teacher=self.teacher,
            title="Ona tili",
            description="Ona tili kursi",
        )
        self.other_course = Course.objects.create(
            teacher=self.teacher,
            title="Matematika",
            description="Matematika kursi",
        )
        self.enrollment = Enrollment.objects.create(
            student=self.ali, course=self.course
        )

        # The relationship provably existed before this month, so the current
        # period is a *full* period and no proration rule applies.
        long_ago = MONTH_START - timedelta(days=40)
        backdate(StudentGroup, self.group.pk, "created_at", long_ago)
        backdate(User, self.ali.pk, "date_joined", long_ago)
        backdate(User, self.zuhra.pk, "date_joined", long_ago)
        backdate(Enrollment, self.enrollment.pk, "enrolled_at", long_ago)

        self.policy = CourseBillingPolicy.objects.create(
            name="9-A oylik to'lov",
            group=self.group,
            amount_uzs=300_000,
            due_day=10,
            effective_from=MONTH_START - timedelta(days=60),
        )

    def _invoice(self, student=None, policy=None, when=None):
        invoice, created = services.ensure_invoice(
            student or self.ali,
            policy or self.policy,
            period_start=when or MONTH_START,
        )
        self.assertTrue(created)
        return invoice

    def _pay(
        self, invoice, amount, *, reference="", verify=False, method=PaymentMethod.CARD
    ):
        payment = services.register_payment(
            student=invoice.student,
            amount=amount,
            method=method,
            reference=reference,
            invoice=invoice,
            submitted_by=invoice.student,
        )
        if verify:
            services.verify_payment(payment, actor=self.admin, reason="test")
        return payment


class BillingPolicyTests(_TuitionFixture):
    def test_due_day_is_clamped_to_the_last_day_of_the_month(self):
        policy = CourseBillingPolicy.objects.create(
            name="Oy oxiri",
            group=self.group,
            amount_uzs=1000,
            due_day=31,
            effective_from=MONTH_START - timedelta(days=60),
        )
        self.assertEqual(policy.due_date_for(2026, 2), date(2026, 2, 28))
        self.assertEqual(policy.due_date_for(2024, 2), date(2024, 2, 29))
        self.assertEqual(policy.due_date_for(2026, 4), date(2026, 4, 30))
        self.assertEqual(policy.due_date_for(2026, 1), date(2026, 1, 31))

    def test_policy_scope_must_reference_a_course_or_a_group(self):
        with self.assertRaises(IntegrityError):
            CourseBillingPolicy.objects.create(
                name="Qamrovsiz",
                amount_uzs=1000,
                due_day=5,
            )

    def test_group_policy_wins_over_course_policy(self):
        Enrollment.objects.create(student=self.zuhra, course=self.course)
        CourseBillingPolicy.objects.create(
            name="Kurs narxi",
            course=self.course,
            amount_uzs=500_000,
            due_day=10,
            effective_from=MONTH_START - timedelta(days=60),
        )
        resolved = services.resolve_policy(self.zuhra)
        self.assertEqual(resolved.pk, self.policy.pk)
        # A student of neither scope resolves to nothing at all.
        self.assertIsNone(services.resolve_policy(self.outsider))

    def test_inactive_and_future_policies_are_ignored(self):
        CourseBillingPolicy.objects.create(
            name="Kelasi oy",
            group=self.group,
            amount_uzs=900_000,
            due_day=10,
            is_active=True,
            effective_from=MONTH_END + timedelta(days=1),
        )
        resolved = services.resolve_policy(self.ali)
        self.assertEqual(resolved.pk, self.policy.pk)


class InvoiceGenerationTests(_TuitionFixture):
    def test_policy_without_a_configured_price_creates_no_invoice(self):
        policy = CourseBillingPolicy.objects.create(
            name="Narx yo'q",
            group=self.group,
            amount_uzs=0,
            due_day=10,
            effective_from=MONTH_START - timedelta(days=60),
        )
        with self.assertRaises(services.TuitionError):
            services.ensure_invoice(self.ali, policy, period_start=MONTH_START)
        self.assertEqual(CourseInvoice.objects.count(), 0)

    def test_monthly_generation_is_idempotent(self):
        first = services.generate_period_invoices(MONTH_START, actor=self.admin)
        self.assertEqual(first["created"], 2)
        self.assertEqual(CourseInvoice.objects.count(), 2)

        second = services.generate_period_invoices(MONTH_START, actor=self.admin)
        self.assertEqual(second["created"], 0)
        self.assertEqual(CourseInvoice.objects.count(), 2)

        invoice = CourseInvoice.objects.get(student=self.ali)
        self.assertEqual(invoice.amount_due_uzs, Decimal("300000.00"))
        self.assertEqual(
            invoice.due_date, self.policy.due_date_for(TODAY.year, TODAY.month)
        )
        self.assertEqual(invoice.status, CourseInvoice.Status.UNPAID)
        self.assertEqual(invoice.balance_uzs, Decimal("300000.00"))

    def test_quarterly_policies_bill_once_per_calendar_quarter(self):
        policy = CourseBillingPolicy.objects.create(
            name="Choraklik",
            group=self.group,
            amount_uzs=900_000,
            due_day=10,
            billing_frequency=CourseBillingPolicy.Frequency.QUARTERLY,
            effective_from=date(MONTH_START.year, 1, 1),
            mid_month_policy=MidMonthPolicy.FULL,
        )
        first = services.generate_period_invoices(MONTH_START, policy=policy)
        self.assertEqual(first["created"], 2)
        invoice = CourseInvoice.objects.get(student=self.ali, policy=policy)
        self.assertEqual(invoice.billing_period_start, date(MONTH_START.year, 10, 1))
        self.assertEqual(invoice.billing_period_end, date(MONTH_START.year, 12, 31))
        self.assertEqual(
            invoice.period_label, f"{MONTH_START.year}-10-01 — {MONTH_START.year}-12-31"
        )
        self.assertEqual(invoice.amount_due_uzs, Decimal("900000.00"))

        # A replay in another month of the same quarter does not bill again.
        replay = services.generate_period_invoices(
            date(MONTH_START.year, 11, 1),
            policy=policy,
        )
        self.assertEqual(replay["created"], 0)
        self.assertEqual(CourseInvoice.objects.filter(policy=policy).count(), 2)

    def test_annual_policies_are_generated_in_january_only(self):
        policy = CourseBillingPolicy.objects.create(
            name="Yillik",
            group=self.group,
            amount_uzs=1_200_000,
            due_day=10,
            billing_frequency=CourseBillingPolicy.Frequency.ANNUAL,
            effective_from=date(MONTH_START.year, 1, 1),
            mid_month_policy=MidMonthPolicy.FULL,
        )
        self.assertEqual(
            services.generate_period_invoices(MONTH_START, policy=policy)["created"],
            0,
        )
        result = services.generate_period_invoices(
            date(MONTH_START.year, 1, 1),
            policy=policy,
        )
        self.assertEqual(result["created"], 2)
        invoice = CourseInvoice.objects.get(student=self.ali, policy=policy)
        self.assertEqual(invoice.billing_period_start, date(MONTH_START.year, 1, 1))
        self.assertEqual(invoice.billing_period_end, date(MONTH_START.year, 12, 31))
        self.assertEqual(
            invoice.period_label, f"{MONTH_START.year}-01-01 — {MONTH_START.year}-12-31"
        )

    def test_one_time_policies_are_generated_in_the_effective_month_once(self):
        effective = date(MONTH_START.year, MONTH_START.month, 5)
        policy = CourseBillingPolicy.objects.create(
            name="Bir martalik",
            group=self.group,
            amount_uzs=75_000,
            due_day=10,
            billing_frequency=CourseBillingPolicy.Frequency.ONE_TIME,
            effective_from=effective,
        )
        result = services.generate_period_invoices(MONTH_START, policy=policy)
        self.assertEqual(result["created"], 2)
        invoice = CourseInvoice.objects.get(student=self.ali, policy=policy)
        self.assertEqual(invoice.billing_period_start, effective)
        self.assertEqual(invoice.billing_period_end, effective)
        self.assertEqual(
            invoice.due_date, policy.due_date_for(effective.year, effective.month)
        )
        next_month = services.generate_period_invoices(
            services.add_months(MONTH_START, 1),
            policy=policy,
        )
        self.assertEqual(next_month["created"], 0)
        self.assertEqual(CourseInvoice.objects.filter(policy=policy).count(), 2)

    def test_unenrolled_student_is_never_invoiced(self):
        # The outsider is in no group on this policy and has no enrollment.
        services.generate_period_invoices(MONTH_START, actor=self.admin)
        self.assertFalse(CourseInvoice.objects.filter(student=self.outsider).exists())

    def test_course_policy_invoices_only_enrolled_students(self):
        policy = CourseBillingPolicy.objects.create(
            name="Kurs",
            course=self.course,
            amount_uzs=200_000,
            due_day=10,
            effective_from=MONTH_START - timedelta(days=60),
        )
        services.generate_period_invoices(MONTH_START, actor=self.admin, policy=policy)
        self.assertEqual(
            list(CourseInvoice.objects.values_list("student_id", flat=True)),
            [self.ali.pk],
        )

    def test_eligibility_uses_persisted_group_membership_not_stale_relation_cache(self):
        stale_student = User.objects.get(pk=self.ali.pk)
        self.group.students.remove(self.ali)
        self.assertIsNone(services.eligibility_date(stale_student, self.policy))
        with self.assertRaises(services.TuitionError):
            services.ensure_invoice(
                stale_student, self.policy, period_start=MONTH_START
            )
        self.assertFalse(CourseInvoice.objects.filter(student=self.ali).exists())

    def test_mid_month_enrollment_skips_the_partial_period(self):
        newcomer = User.objects.create_user(
            email="tui-new@example.test",
            password="testpass123",
            role="student",
        )
        self.group.students.add(newcomer)
        # Joined well after this period started.
        backdate(User, newcomer.pk, "date_joined", MONTH_START + timedelta(days=5))

        services.generate_period_invoices(MONTH_START, actor=self.admin)
        self.assertFalse(CourseInvoice.objects.filter(student=newcomer).exists())

        # Next period is a full one and is billed normally.
        next_month = services.add_months(MONTH_START, 1)
        services.generate_period_invoices(next_month, actor=self.admin)
        invoice = CourseInvoice.objects.get(
            student=newcomer,
            billing_period_start=next_month,
        )
        self.assertEqual(invoice.amount_due_uzs, Decimal("300000.00"))

    def test_proration_is_applied_when_the_policy_asks_for_it(self):
        policy = CourseBillingPolicy.objects.create(
            name="Mutanosib",
            group=self.group,
            amount_uzs=300_000,
            due_day=10,
            mid_month_policy=MidMonthPolicy.PRORATED,
            effective_from=MONTH_START - timedelta(days=60),
        )
        newcomer = User.objects.create_user(
            email="tui-pro@example.test",
            password="testpass123",
            role="student",
        )
        self.group.students.add(newcomer)
        eligibility = MONTH_START + timedelta(days=20)
        backdate(User, newcomer.pk, "date_joined", eligibility)

        services.generate_period_invoices(MONTH_START, actor=self.admin, policy=policy)
        invoice = CourseInvoice.objects.get(
            student=newcomer,
            billing_period_start=MONTH_START,
        )
        total_days = monthrange(MONTH_START.year, MONTH_START.month)[1]
        remaining = total_days - 20
        expected = round(300_000 * remaining / total_days)
        self.assertEqual(invoice.amount_due_uzs, Decimal(expected))

    def test_different_courses_carry_different_prices(self):
        other_enrollment = Enrollment.objects.create(
            student=self.zuhra,
            course=self.other_course,
        )
        backdate(
            Enrollment,
            other_enrollment.pk,
            "enrolled_at",
            MONTH_START - timedelta(days=40),
        )
        CourseBillingPolicy.objects.create(
            name="Matematika",
            course=self.other_course,
            amount_uzs=450_000,
            due_day=15,
            effective_from=MONTH_START - timedelta(days=60),
        )
        services.generate_period_invoices(MONTH_START, actor=self.admin)
        # Each policy produces its own invoice, so a student who belongs to
        # both the group and the course is billed once per scope.
        by_scope = {
            (row["student_id"], row["scope_key"]): row["amount_due_uzs"]
            for row in CourseInvoice.objects.values(
                "student_id",
                "scope_key",
                "amount_due_uzs",
            )
        }
        self.assertEqual(
            by_scope[(self.ali.pk, f"group:{self.group.pk}")],
            Decimal("300000.00"),
        )
        self.assertEqual(
            by_scope[(self.zuhra.pk, f"course:{self.other_course.pk}")],
            Decimal("450000.00"),
        )

    def test_discount_scholarship_and_exemption_are_snapshotted(self):
        StudentTuitionAgreement.objects.create(
            student=self.ali,
            billing_policy=self.policy,
            discount_kind=StudentTuitionAgreement.DiscountKind.PERCENT,
            discount_percent=Decimal("10"),
            created_by=self.admin,
        )
        waived = StudentTuitionAgreement.objects.create(
            student=self.zuhra,
            billing_policy=self.policy,
            discount_kind=StudentTuitionAgreement.DiscountKind.FULL_WAIVER,
            scholarship_note="To'liq stipendiya",
            created_by=self.admin,
        )
        services.generate_period_invoices(MONTH_START, actor=self.admin)

        ali_invoice = CourseInvoice.objects.get(student=self.ali)
        self.assertEqual(ali_invoice.base_amount_uzs, Decimal("300000.00"))
        self.assertEqual(ali_invoice.discount_amount_uzs, Decimal("30000.00"))
        self.assertEqual(ali_invoice.amount_due_uzs, Decimal("270000.00"))

        zuhra_invoice = CourseInvoice.objects.get(student=self.zuhra)
        self.assertEqual(zuhra_invoice.amount_due_uzs, Decimal("0.00"))
        self.assertEqual(zuhra_invoice.status, CourseInvoice.Status.WAIVED)
        self.assertEqual(zuhra_invoice.agreement_id, waived.pk)

    def test_negotiated_amount_overrides_the_policy_price(self):
        StudentTuitionAgreement.objects.create(
            student=self.ali,
            billing_policy=self.policy,
            negotiated_amount_uzs=150_000,
            created_by=self.admin,
        )
        invoice = self._invoice()
        self.assertEqual(invoice.base_amount_uzs, Decimal("150000.00"))
        self.assertEqual(invoice.amount_due_uzs, Decimal("150000.00"))

    def test_installments_split_the_period_into_separate_invoices(self):
        policy = CourseBillingPolicy.objects.create(
            name="Bo'lib to'lash",
            group=self.group,
            amount_uzs=300_000,
            due_day=10,
            installment_allowed=True,
            installments=3,
            effective_from=MONTH_START - timedelta(days=60),
        )
        services.generate_period_invoices(MONTH_START, actor=self.admin, policy=policy)
        invoices = list(
            CourseInvoice.objects.filter(student=self.ali).order_by(
                "installment_number"
            )
        )
        self.assertEqual(len(invoices), 3)
        self.assertEqual([i.installment_number for i in invoices], [1, 2, 3])
        self.assertEqual(
            sum(i.amount_due_uzs for i in invoices),
            Decimal("300000.00"),
        )
        # Each installment is due in its own consecutive month.
        due_dates = [i.due_date for i in invoices]
        self.assertEqual(
            sorted(due_dates),
            due_dates,
            "Installment due dates must be ordered",
        )
        self.assertEqual(len({i.due_date for i in invoices}), 3)


class PaymentLifecycleTests(_TuitionFixture):
    def test_partial_payment_then_settlement(self):
        invoice = self._invoice()
        self._pay(invoice, 100_000, reference="R-1", verify=True)

        invoice.refresh_from_db()
        self.assertEqual(invoice.paid_amount_uzs, Decimal("100000.00"))
        self.assertEqual(invoice.balance_uzs, Decimal("200000.00"))
        self.assertEqual(invoice.status, CourseInvoice.Status.PARTIALLY_PAID)

        self._pay(invoice, 200_000, reference="R-2", verify=True)
        invoice.refresh_from_db()
        self.assertEqual(invoice.balance_uzs, Decimal("0.00"))
        self.assertEqual(invoice.status, CourseInvoice.Status.PAID)

    def test_a_submitted_payment_is_not_money_until_confirmed(self):
        invoice = self._invoice()
        self._pay(invoice, 300_000, reference="R-3", verify=False)

        invoice.refresh_from_db()
        self.assertEqual(invoice.paid_amount_uzs, Decimal("0.00"))
        self.assertEqual(invoice.pending_amount_uzs, Decimal("300000.00"))
        self.assertEqual(invoice.status, CourseInvoice.Status.PENDING_VERIFICATION)
        self.assertTrue(invoice.awaiting_confirmation)

    def test_unauthorized_actor_cannot_confirm_a_payment(self):
        invoice = self._invoice()
        payment = self._pay(invoice, 300_000, reference="R-4", verify=False)
        with self.assertRaises(PermissionDenied):
            services.verify_payment(payment, actor=self.teacher)
        payment.refresh_from_db()
        invoice.refresh_from_db()
        self.assertEqual(payment.status, CoursePayment.Status.PENDING_VERIFICATION)
        self.assertIsNone(payment.verified_by)
        self.assertEqual(invoice.paid_amount_uzs, Decimal("0.00"))

    def test_student_cannot_confirm_their_own_receipt(self):
        invoice = self._invoice()
        payment = self._pay(invoice, 300_000, reference="R-5", verify=False)
        with self.assertRaises(PermissionDenied):
            services.verify_payment(payment, actor=self.ali)

    def test_duplicate_payment_reference_is_rejected(self):
        invoice = self._invoice()
        self._pay(invoice, 100_000, reference="SAME-REF", verify=False)
        with self.assertRaises(IntegrityError):
            self._pay(invoice, 100_000, reference="SAME-REF", verify=False)

    def test_zero_or_negative_amounts_are_rejected(self):
        invoice = self._invoice()
        with self.assertRaises(services.TuitionError):
            self._pay(invoice, 0, verify=False)

    def test_rejection_and_refund_recompute_the_balance(self):
        invoice = self._invoice()
        rejected = self._pay(invoice, 50_000, reference="R-6", verify=False)
        services.reject_payment(rejected, actor=self.admin, reason="Chek yo'q")
        invoice.refresh_from_db()
        self.assertEqual(invoice.paid_amount_uzs, Decimal("0.00"))
        self.assertEqual(invoice.pending_amount_uzs, Decimal("0.00"))

        confirmed = self._pay(invoice, 120_000, reference="R-7", verify=True)
        invoice.refresh_from_db()
        self.assertEqual(invoice.paid_amount_uzs, Decimal("120000.00"))

        services.refund_payment(confirmed, actor=self.admin, reason="Xato to'lov")
        invoice.refresh_from_db()
        self.assertEqual(invoice.paid_amount_uzs, Decimal("0.00"))
        self.assertEqual(invoice.status, CourseInvoice.Status.UNPAID)

    def test_refund_requires_a_confirmed_payment(self):
        invoice = self._invoice()
        pending = self._pay(invoice, 10_000, reference="R-8", verify=False)
        with self.assertRaises(services.TuitionError):
            services.refund_payment(pending, actor=self.admin)

    def test_adjustment_records_the_old_and_new_amount(self):
        invoice = self._invoice()
        services.adjust_invoice(
            invoice,
            actor=self.admin,
            new_amount=250_000,
            reason="Chegirma",
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.amount_due_uzs, Decimal("250000.00"))
        log = TuitionAuditLog.objects.filter(
            invoice=invoice,
            action=TuitionAuditLog.Action.INVOICE_ADJUSTED,
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.old_value, "300000.00")
        self.assertEqual(log.new_value, "250000.00")
        self.assertEqual(log.actor_id, self.admin.pk)

    def test_verification_is_recorded_in_the_audit_trail(self):
        invoice = self._invoice()
        payment = self._pay(invoice, 300_000, reference="R-9", verify=True)
        log = TuitionAuditLog.objects.filter(
            payment=payment,
            action=TuitionAuditLog.Action.PAYMENT_VERIFIED,
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.actor_id, self.admin.pk)
        self.assertEqual(log.new_value, CoursePayment.Status.VERIFIED)

    def test_overdue_marking_respects_due_date_and_grace(self):
        invoice = self._invoice()
        services.adjust_invoice(  # move the period into the past
            invoice,
            actor=self.admin,
            new_amount=300_000,
            reason="test",
        )
        CourseInvoice.objects.filter(pk=invoice.pk).update(
            due_date=TODAY - timedelta(days=30),
            grace_until=TODAY + timedelta(days=5),
        )
        result = services.mark_overdue_invoices(as_of=TODAY, actor=self.admin)
        self.assertEqual(result["marked"], 0)
        invoice.refresh_from_db()
        self.assertNotEqual(invoice.status, CourseInvoice.Status.OVERDUE)

        CourseInvoice.objects.filter(pk=invoice.pk).update(
            grace_until=TODAY - timedelta(days=1),
        )
        result = services.mark_overdue_invoices(as_of=TODAY, actor=self.admin)
        self.assertEqual(result["marked"], 1)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, CourseInvoice.Status.OVERDUE)

    def test_recompute_never_invents_overdue_and_keeps_an_explicit_overdue_sticky(self):
        """The calendar must not relabel an invoice; only the job marks overdue."""
        invoice = self._invoice()
        CourseInvoice.objects.filter(pk=invoice.pk).update(
            due_date=TODAY - timedelta(days=30),
            grace_until=None,
        )
        invoice.refresh_from_db()
        services.recompute_invoice(invoice)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, CourseInvoice.Status.UNPAID)

        services.mark_overdue_invoices(as_of=TODAY, actor=self.admin)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, CourseInvoice.Status.OVERDUE)

        # A partial payment does not erase the fact that the invoice is overdue.
        self._pay(invoice, 100_000, reference="OD-1", verify=True)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, CourseInvoice.Status.OVERDUE)
        self.assertEqual(invoice.balance_uzs, Decimal("200000.00"))

        # Settling it does.
        self._pay(invoice, 200_000, reference="OD-2", verify=True)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, CourseInvoice.Status.PAID)

    def test_a_pending_receipt_on_a_past_due_invoice_awaits_verification(self):
        """An unconfirmed receipt replaces the debt chase; it is not money yet."""
        invoice = self._invoice()
        CourseInvoice.objects.filter(pk=invoice.pk).update(
            due_date=TODAY - timedelta(days=30),
            grace_until=None,
        )
        services.mark_overdue_invoices(as_of=TODAY, actor=self.admin)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, CourseInvoice.Status.OVERDUE)

        self._pay(invoice, 300_000, reference="OD-PENDING", verify=False)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, CourseInvoice.Status.PENDING_VERIFICATION)
        self.assertTrue(invoice.awaiting_confirmation)
        self.assertEqual(invoice.paid_amount_uzs, Decimal("0.00"))
        self.assertEqual(
            services.reminder_stage_for(invoice, as_of=TODAY),
            PaymentReminderLog.Stage.AWAITING_CONFIRMATION,
        )

    def test_overdue_never_removes_the_student_from_the_course(self):
        invoice = self._invoice()
        CourseInvoice.objects.filter(pk=invoice.pk).update(
            due_date=TODAY - timedelta(days=30),
            grace_until=None,
        )
        services.mark_overdue_invoices(as_of=TODAY, actor=self.admin)
        self.assertTrue(
            Enrollment.objects.filter(student=self.ali, course=self.course).exists()
        )
        self.assertTrue(self.group.students.filter(pk=self.ali.pk).exists())
        self.assertTrue(CourseInvoice.objects.filter(pk=invoice.pk).exists())


class IsolationAndEntitlementTests(_TuitionFixture):
    def test_student_sees_only_their_own_invoices(self):
        services.generate_period_invoices(MONTH_START, actor=self.admin)
        overview = services.student_tuition_overview(self.ali)
        self.assertEqual(overview["open_invoices"], 1)
        self.assertEqual(overview["outstanding_uzs"], 300_000.0)
        self.assertEqual(len(overview["invoices"]), 1)
        self.assertNotIn(
            self.zuhra.pk, [row.get("student_id") for row in overview["invoices"]]
        )

    def test_children_overview_returns_only_verified_children(self):
        from apps.accounts.models import ParentStudentLink

        parent = User.objects.create_user(
            email="tui-parent@example.test",
            password="testpass123",
            role="parent",
        )
        services.generate_period_invoices(MONTH_START, actor=self.admin)
        ParentStudentLink.objects.create(
            parent=parent,
            student=self.ali,
            is_approved=True,
        )
        ParentStudentLink.objects.create(
            parent=parent,
            student=self.zuhra,
            is_approved=False,
        )
        children = services.children_tuition_overview(parent)
        self.assertEqual([child["student_id"] for child in children], [self.ali.pk])

    def test_group_finance_summary_is_aggregate_only(self):
        services.generate_period_invoices(MONTH_START, actor=self.admin)
        invoice = CourseInvoice.objects.get(student=self.ali)
        self._pay(invoice, 300_000, reference="FIN-1", verify=True)

        summary = services.group_finance_summary(self.group, MONTH_START, MONTH_END)
        self.assertTrue(summary["policy_configured"])
        self.assertEqual(summary["paid_count"], 1)
        self.assertEqual(summary["unpaid_count"], 1)
        self.assertEqual(summary["billed_uzs"], 600_000.0)
        self.assertEqual(summary["confirmed_paid_uzs"], 300_000.0)
        self.assertEqual(summary["outstanding_uzs"], 300_000.0)
        # No names and no student identifiers leak into a report block.
        blob = repr(summary)
        for name in ("Ali", "Zuhra", "Valiyev", "Karimova"):
            self.assertNotIn(name, blob)
        # Aggregate only: no per-student rows, so a recipient cannot see who owes.
        self.assertNotIn("student", blob.replace("students_with_debt", ""))

    def test_tuition_does_not_touch_the_platform_subscription(self):
        make_plan(SubscriptionPlan.PlanType.TEACHER_SPONSORED)
        group_teacher = self.group.teacher
        TeacherSponsorship.objects.create(
            student=self.ali,
            group=self.group,
            is_active=True,
            approved_at=timezone.now(),
            approved_by=self.admin,
        )
        self.assertEqual(get_effective_entitlement(self.ali).source, SOURCE_SPONSORED)

        services.generate_period_invoices(MONTH_START, actor=self.admin)
        invoice = CourseInvoice.objects.get(student=self.ali)
        self._pay(invoice, 300_000, reference="SPON-1", verify=True)

        # Sponsored platform access is NOT a tuition waiver...
        self.assertEqual(invoice.amount_due_uzs, Decimal("300000.00"))
        self.assertEqual(invoice.status, CourseInvoice.Status.PAID)
        # ...and the entitlement is untouched by any tuition operation.
        self.assertEqual(get_effective_entitlement(self.ali).source, SOURCE_SPONSORED)
        self.assertFalse(UserSubscription.objects.filter(user=self.ali).exists())
        self.assertTrue(
            TeacherSponsorship.objects.filter(student=self.ali, is_active=True).exists()
        )
        self.assertEqual(group_teacher.pk, self.teacher.pk)

    def test_tuition_ops_never_grant_platform_quotas(self):
        from apps.payments.entitlements import get_remaining_limits

        before = get_remaining_limits(self.ali)
        services.generate_period_invoices(MONTH_START, actor=self.admin)
        invoice = CourseInvoice.objects.get(student=self.ali)
        self._pay(invoice, 10_000, reference="QUOTA-1", verify=True)
        after = get_remaining_limits(self.ali)
        self.assertEqual(before["source"], after["source"])
        self.assertEqual(before["image_essay"], after["image_essay"])
        self.assertEqual(before["text_essay"], after["text_essay"])
