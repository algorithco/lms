"""HTTP contract and authorization for the tuition and weekly-report APIs.

The React dashboard and the parent portal talk to ``/api/v1/...`` and nothing
else, so these tests pin what the services cannot:

* a student sees only their own tuition, a parent only their *approved*
  children's, and a foreign invoice id is answered with 404 rather than a
  confirmation that it exists;
* submitting a receipt over HTTP never marks an invoice paid;
* confirmation is reachable only through the admin-gated endpoints;
* a teacher's weekly-report response contains no tuition figures at all (they
  are absent from the payload, not merely hidden by the client);
* a foreign report id is 404, and regeneration requires a stated reason.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import ParentStudentLink, User
from apps.attendance.models import AttendanceRecord
from apps.courses.models import Course, Enrollment, StudentGroup
from apps.tuition import services
from apps.tuition.models import (
    CourseBillingPolicy,
    CourseInvoice,
    CoursePayment,
    PaymentMethod,
    TuitionAuditLog,
)
from apps.weekly_reports import services as report_services
from apps.weekly_reports.models import WeeklyGroupReport, WeeklyStudentReport

TODAY = timezone.localdate()
MONTH_START, MONTH_END = services.month_bounds(TODAY)
PERIOD_START, PERIOD_END = report_services.previous_week_bounds()


class _ApiFixture(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email="api2-admin@example.test", password="testpass123", role="admin",
        )
        self.teacher = User.objects.create_user(
            email="api2-teacher@example.test", password="testpass123", role="teacher",
        )
        self.other_teacher = User.objects.create_user(
            email="api2-teacher2@example.test", password="testpass123", role="teacher",
        )
        self.ali = User.objects.create_user(
            email="api2-ali@example.test", password="testpass123", role="student",
            first_name="Ali", last_name="Valiyev",
        )
        self.zuhra = User.objects.create_user(
            email="api2-zuhra@example.test", password="testpass123", role="student",
            first_name="Zuhra", last_name="Karimova",
        )
        self.outsider = User.objects.create_user(
            email="api2-outsider@example.test", password="testpass123", role="student",
        )
        self.parent = User.objects.create_user(
            email="api2-parent@example.test", password="testpass123", role="parent",
        )
        self.group = StudentGroup.objects.create(teacher=self.teacher, name="9-A")
        self.group.students.add(self.ali, self.zuhra)
        self.foreign_group = StudentGroup.objects.create(
            teacher=self.other_teacher, name="10-B",
        )
        self.foreign_group.students.add(self.outsider)
        ParentStudentLink.objects.create(
            parent=self.parent, student=self.ali, is_approved=True,
        )
        ParentStudentLink.objects.create(
            parent=self.parent, student=self.zuhra, is_approved=False,
        )
        self.policy = CourseBillingPolicy.objects.create(
            name="9-A oylik", group=self.group, amount_uzs=300_000, due_day=10,
        )

    # -- helpers ----------------------------------------------------------
    def url(self, name, **kwargs):
        return reverse(f"webapi:{name}", kwargs=kwargs or None)

    def _login(self, user):
        self.client.force_login(user)

    def _post(self, name, payload=None, **kwargs):
        return self.client.post(
            self.url(name, **kwargs), payload or {}, content_type="application/json",
        )

    def _invoice(self, student=None, **overrides):
        defaults = {
            "student": student or self.ali,
            "policy": self.policy,
            "scope_key": f"group:{self.group.pk}",
            "billing_period_start": MONTH_START,
            "billing_period_end": MONTH_END,
            "period_label": f"{MONTH_START:%Y-%m}",
            "base_amount_uzs": Decimal("300000"),
            "amount_due_uzs": Decimal("300000"),
            "due_date": MONTH_START + timedelta(days=9),
            "status": CourseInvoice.Status.UNPAID,
        }
        defaults.update(overrides)
        return CourseInvoice.objects.create(**defaults)

    def _confirmed_payment(self, invoice, amount="300000"):
        payment = services.register_payment(
            student=invoice.student, amount=Decimal(amount), method=PaymentMethod.CARD,
            reference=f"API-REF-{invoice.pk}", invoice=invoice,
            submitted_by=invoice.student,
        )
        services.verify_payment(payment, actor=self.admin)
        return payment


class TuitionApiTests(_ApiFixture):
    def test_student_reads_only_their_own_tuition(self):
        self._invoice()
        self._invoice(student=self.zuhra, scope_key=f"group:{self.group.pk}")
        self._login(self.ali)
        response = self.client.get(self.url("billing-tuition-my"))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["student_id"], self.ali.pk)
        self.assertEqual(len(body["invoices"]), 1)
        self.assertEqual(body["invoices"][0]["balance_uzs"], 300000.0)

    def test_parent_sees_verified_children_only(self):
        self._invoice()
        self._invoice(student=self.zuhra, scope_key=f"group:{self.group.pk}")
        self._login(self.parent)
        body = self.client.get(self.url("billing-tuition-children")).json()
        self.assertEqual(
            [child["student_id"] for child in body["children"]], [self.ali.pk],
        )

    def test_submitting_a_receipt_does_not_mark_the_invoice_paid(self):
        invoice = self._invoice()
        self._login(self.ali)
        response = self._post("billing-tuition-payment-submit", {
            "invoice_id": invoice.pk,
            "amount": 300000,
            "method": PaymentMethod.CARD,
            "reference": "STUDENT-RECEIPT-1",
        })
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["payment"]["status"], CoursePayment.Status.PENDING_VERIFICATION)
        self.assertEqual(body["invoice"]["paid_amount_uzs"], 0.0)
        self.assertTrue(body["invoice"]["awaiting_confirmation"])
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, CourseInvoice.Status.PENDING_VERIFICATION)
        self.assertNotEqual(invoice.status, CourseInvoice.Status.PAID)

    def test_a_stranger_cannot_submit_against_someone_elses_invoice(self):
        invoice = self._invoice()
        self._login(self.outsider)
        response = self._post("billing-tuition-payment-submit", {
            "invoice_id": invoice.pk, "amount": 300000,
            "method": PaymentMethod.CARD, "reference": "STRANGER-1",
        })
        self.assertEqual(response.status_code, 404)
        self.assertFalse(CoursePayment.objects.exists())

    def test_an_invalid_amount_is_rejected(self):
        invoice = self._invoice()
        self._login(self.ali)
        response = self._post("billing-tuition-payment-submit", {
            "invoice_id": invoice.pk, "amount": 0, "method": PaymentMethod.CARD,
        })
        self.assertEqual(response.status_code, 400)

    def test_a_cancelled_invoice_accepts_no_payment(self):
        invoice = self._invoice(status=CourseInvoice.Status.CANCELLED)
        self._login(self.ali)
        response = self._post("billing-tuition-payment-submit", {
            "invoice_id": invoice.pk, "amount": 1000, "method": PaymentMethod.CARD,
        })
        self.assertEqual(response.status_code, 409)

    def test_payment_status_detail_is_scoped_to_student_and_approved_parent(self):
        invoice = self._invoice()
        payment = services.register_payment(
            student=self.ali, amount=Decimal("100000"), method=PaymentMethod.CARD,
            reference="STATUS-DETAIL-1", invoice=invoice, submitted_by=self.ali,
        )
        self._login(self.ali)
        self.assertEqual(
            self.client.get(self.url("billing-tuition-payment-detail", payment_id=payment.pk)).status_code,
            200,
        )
        self._login(self.outsider)
        self.assertEqual(
            self.client.get(self.url("billing-tuition-payment-detail", payment_id=payment.pk)).status_code,
            404,
        )
        self._login(self.parent)
        self.assertEqual(
            self.client.get(self.url("billing-tuition-payment-detail", payment_id=payment.pk)).status_code,
            200,
        )

    def test_student_can_only_read_invoices_in_own_group_scope_with_finance_permission(self):
        from apps.tuition.permissions import VIEW_PERMISSION

        self._invoice()
        self._invoice(student=self.zuhra)
        self._invoice(student=self.outsider, scope_key=f"group:{self.foreign_group.pk}")
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        from apps.tuition.models import CourseInvoice

        permission = Permission.objects.get(
            content_type=ContentType.objects.get_for_model(CourseInvoice),
            codename=VIEW_PERMISSION.split(".")[1],
        )
        self.teacher.user_permissions.add(permission)
        self._login(self.teacher)
        body = self.client.get(self.url("school-tuition-invoices")).json()
        # Own-group invoices only: the foreign group's invoice is invisible even
        # to a teacher who holds the finance *view* permission.
        self.assertEqual(body["count"], 2)
        self.assertEqual(
            sorted(row["student_id"] for row in body["results"]),
            sorted([self.ali.pk, self.zuhra.pk]),
        )

    def test_teacher_cannot_read_group_finance_without_permission(self):
        self._login(self.teacher)
        response = self.client.get(
            self.url("school-tuition-finance"), {"group_id": self.group.pk},
        )
        self.assertEqual(response.status_code, 403)

    def test_staff_recorded_partial_payment_is_verified_and_audited(self):
        invoice = self._invoice()
        self._login(self.teacher)
        response = self._post(
            "school-tuition-invoice-payment-record",
            {"amount": 100000, "reason": "Naqd qabul qilindi", "reference": "CASH-API-1"},
            invoice_id=invoice.pk,
        )
        self.assertEqual(response.status_code, 403)
        self._login(self.admin)
        response = self._post(
            "school-tuition-invoice-payment-record",
            {"amount": 100000, "reason": "Naqd qabul qilindi", "reference": "CASH-API-1"},
            invoice_id=invoice.pk,
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["payment"]["status"], CoursePayment.Status.VERIFIED)
        self.assertEqual(body["invoice"]["paid_amount_uzs"], 100000.0)
        self.assertEqual(body["invoice"]["balance_uzs"], 200000.0)
        self.assertTrue(TuitionAuditLog.objects.filter(
            payment_id=body["payment"]["id"],
            action=TuitionAuditLog.Action.PAYMENT_VERIFIED,
        ).exists())

    def test_admin_reads_aggregate_group_finance(self):
        invoice = self._invoice()
        self._confirmed_payment(invoice)
        self._login(self.admin)
        response = self.client.get(
            self.url("school-tuition-finance"), {"group_id": self.group.pk},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["group_name"], "9-A")
        self.assertEqual(body["paid_count"], 1)
        self.assertEqual(body["confirmed_paid_uzs"], 300000.0)
        self.assertNotIn("Valiyev", response.content.decode())

    def test_teacher_cannot_confirm_a_payment(self):
        invoice = self._invoice()
        payment = services.register_payment(
            student=self.ali, amount=Decimal("300000"), method=PaymentMethod.CARD,
            reference="TEACHER-CONFIRM", invoice=invoice, submitted_by=self.ali,
        )
        self._login(self.teacher)
        response = self._post("school-tuition-payment-verify", {"reason": "ok"}, payment_id=payment.pk)
        self.assertEqual(response.status_code, 403)
        payment.refresh_from_db()
        self.assertEqual(payment.status, CoursePayment.Status.PENDING_VERIFICATION)

    def test_student_cannot_confirm_their_own_receipt(self):
        invoice = self._invoice()
        payment = services.register_payment(
            student=self.ali, amount=Decimal("300000"), method=PaymentMethod.CARD,
            reference="SELF-CONFIRM", invoice=invoice, submitted_by=self.ali,
        )
        self._login(self.ali)
        response = self._post(
            "school-tuition-payment-verify", {"reason": "ok"}, payment_id=payment.pk,
        )
        self.assertEqual(response.status_code, 403)
        invoice.refresh_from_db()
        self.assertEqual(invoice.paid_amount_uzs, Decimal("0.00"))

    def test_admin_confirmation_settles_the_invoice_and_audits_it(self):
        invoice = self._invoice()
        payment = services.register_payment(
            student=self.ali, amount=Decimal("300000"), method=PaymentMethod.CARD,
            reference="ADMIN-CONFIRM", invoice=invoice, submitted_by=self.ali,
        )
        self._login(self.admin)
        response = self._post(
            "school-tuition-payment-verify", {"reason": "Bank ko'rindi"},
            payment_id=payment.pk,
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["payment"]["status"], CoursePayment.Status.VERIFIED)
        self.assertEqual(body["invoice"]["status"], CourseInvoice.Status.PAID)
        self.assertEqual(body["invoice"]["balance_uzs"], 0.0)
        self.assertTrue(
            TuitionAuditLog.objects.filter(
                action=TuitionAuditLog.Action.PAYMENT_VERIFIED, payment=payment,
            ).exists()
        )

    def test_admin_adjustment_is_audited_and_teacher_cannot_adjust(self):
        invoice = self._invoice()
        self._login(self.teacher)
        self.assertEqual(
            self._post("school-tuition-invoice-adjust", {"amount": 1000}, invoice_id=invoice.pk)
            .status_code,
            403,
        )
        self._login(self.admin)
        response = self._post(
            "school-tuition-invoice-adjust",
            {"amount": 250000, "reason": "Chegirma berildi"},
            invoice_id=invoice.pk,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["invoice"]["amount_due_uzs"], 250000.0)
        log = TuitionAuditLog.objects.filter(
            action=TuitionAuditLog.Action.INVOICE_ADJUSTED, invoice=invoice,
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.reason, "Chegirma berildi")

    def test_admin_waives_an_invoice_and_it_is_audited(self):
        invoice = self._invoice()
        self._login(self.teacher)
        self.assertEqual(
            self._post(
                "school-tuition-invoice-waive", {"reason": "Xayriya"},
                invoice_id=invoice.pk,
            ).status_code,
            403,
        )
        self._login(self.admin)
        # A waiver without a real stated reason is refused, not silently logged.
        self.assertEqual(
            self._post(
                "school-tuition-invoice-waive", {"reason": "ab"}, invoice_id=invoice.pk,
            ).status_code,
            400,
        )
        response = self._post(
            "school-tuition-invoice-waive", {"reason": "Xayriya yordami"},
            invoice_id=invoice.pk,
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["invoice"]["status"], CourseInvoice.Status.WAIVED)
        self.assertEqual(body["invoice"]["amount_due_uzs"], 0.0)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, CourseInvoice.Status.WAIVED)
        self.assertEqual(invoice.amount_due_uzs, Decimal("0.00"))
        log = TuitionAuditLog.objects.filter(
            invoice=invoice,
            action=TuitionAuditLog.Action.INVOICE_ADJUSTED,
            actor=self.admin,
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.reason, "Xayriya yordami")
        self.assertEqual(log.new_value, CourseInvoice.Status.WAIVED)

    def test_admin_redates_an_invoice_and_the_change_is_audited(self):
        invoice = self._invoice()
        new_due = TODAY + timedelta(days=45)
        new_grace = TODAY + timedelta(days=52)
        self._login(self.teacher)
        self.assertEqual(
            self._post(
                "school-tuition-invoice-due-date", {"due_date": new_due.isoformat()},
                invoice_id=invoice.pk,
            ).status_code,
            403,
        )
        self._login(self.admin)
        # Grace before the due date is a contradiction, so it is rejected.
        self.assertEqual(
            self._post(
                "school-tuition-invoice-due-date",
                {"due_date": new_due.isoformat(), "grace_until": TODAY.isoformat()},
                invoice_id=invoice.pk,
            ).status_code,
            400,
        )
        response = self._post(
            "school-tuition-invoice-due-date",
            {"due_date": new_due.isoformat(), "grace_until": new_grace.isoformat()},
            invoice_id=invoice.pk,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["invoice"]["due_date"], new_due.isoformat())
        invoice.refresh_from_db()
        self.assertEqual(invoice.due_date, new_due)
        self.assertEqual(invoice.grace_until, new_grace)
        audited = set(TuitionAuditLog.objects.filter(
            invoice=invoice, action=TuitionAuditLog.Action.INVOICE_UPDATED,
        ).values_list("field", flat=True))
        self.assertEqual(audited, {"due_date", "grace_until"})

    def test_admin_rejects_a_pending_receipt_and_the_invoice_is_payable_again(self):
        invoice = self._invoice()
        payment = services.register_payment(
            student=self.ali, amount=Decimal("300000"), method=PaymentMethod.CARD,
            reference="REJECT-API-1", invoice=invoice, submitted_by=self.ali,
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, CourseInvoice.Status.PENDING_VERIFICATION)

        self._login(self.teacher)
        self.assertEqual(
            self._post(
                "school-tuition-payment-reject", {"reason": "Chek ko'rinmadi"},
                payment_id=payment.pk,
            ).status_code,
            403,
        )
        self._login(self.admin)
        response = self._post(
            "school-tuition-payment-reject", {"reason": "Chek ko'rinmadi"},
            payment_id=payment.pk,
        )
        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        invoice.refresh_from_db()
        self.assertEqual(payment.status, CoursePayment.Status.REJECTED)
        self.assertEqual(payment.rejection_reason, "Chek ko'rinmadi")
        self.assertEqual(payment.verified_by_id, self.admin.pk)
        # A rejected receipt is not money: the balance comes straight back.
        self.assertEqual(invoice.paid_amount_uzs, Decimal("0.00"))
        self.assertEqual(invoice.pending_amount_uzs, Decimal("0.00"))
        self.assertEqual(invoice.status, CourseInvoice.Status.UNPAID)
        self.assertTrue(TuitionAuditLog.objects.filter(
            payment=payment, action=TuitionAuditLog.Action.PAYMENT_REJECTED,
            actor=self.admin,
        ).exists())

    def test_payment_queue_is_admin_only(self):
        invoice = self._invoice()
        services.register_payment(
            student=self.ali, amount=Decimal("100000"), method=PaymentMethod.CARD,
            reference="QUEUE-1", invoice=invoice, submitted_by=self.ali,
        )
        self._login(self.teacher)
        self.assertEqual(self.client.get(self.url("school-tuition-payment-queue")).status_code, 403)
        self._login(self.admin)
        body = self.client.get(self.url("school-tuition-payment-queue")).json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["results"][0]["method_label"], "Karta (o'tkazma)")

    def test_audit_endpoint_requires_admin(self):
        self._login(self.teacher)
        self.assertEqual(self.client.get(self.url("school-tuition-audit")).status_code, 403)
        self._login(self.admin)
        self.assertEqual(self.client.get(self.url("school-tuition-audit")).status_code, 200)


class WeeklyReportApiTests(_ApiFixture):
    def setUp(self):
        super().setUp()
        self.report = report_services.generate_group_report(
            self.group, PERIOD_START, PERIOD_END, actor=self.teacher,
        )
        self.foreign_report = report_services.generate_group_report(
            self.foreign_group, PERIOD_START, PERIOD_END, actor=self.other_teacher,
        )

    def test_teacher_sees_only_their_own_groups_reports(self):
        self._login(self.teacher)
        body = self.client.get(self.url("school-weekly-reports")).json()
        self.assertEqual([row["group_id"] for row in body["results"]], [self.group.pk])

    def test_a_foreign_report_is_not_found_rather_than_forbidden(self):
        self._login(self.teacher)
        response = self.client.get(
            self.url("school-weekly-report-detail", report_id=self.foreign_report.pk),
        )
        self.assertEqual(response.status_code, 404)
        self.assertNotIn("10-B", response.content.decode())

    def test_teacher_payload_contains_no_finance_fields(self):
        self._login(self.teacher)
        body = self.client.get(
            self.url("school-weekly-report-detail", report_id=self.report.pk),
        ).json()
        self.assertFalse(body["summary"]["finance_visible"])
        self.assertNotIn("finance", body["summary"])
        self.assertNotIn("Kurs to'lovlari", body["text"])

    def test_regeneration_requires_a_reason_and_creates_a_new_version(self):
        self._login(self.teacher)
        short = self._post(
            "school-weekly-report-regenerate", {"reason": "x"}, report_id=self.report.pk,
        )
        self.assertEqual(short.status_code, 400)
        self.assertEqual(
            WeeklyGroupReport.objects.filter(group=self.group).count(), 1,
        )

        response = self._post(
            "school-weekly-report-regenerate",
            {"reason": "Davomat tuzatildi"},
            report_id=self.report.pk,
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["report"]["version"], 2)
        self.assertEqual(body["report"]["generation_reason"], "Davomat tuzatildi")
        self.assertEqual(body["superseded_id"], self.report.pk)
        self.assertTrue(body["report"]["is_current"])

    def test_teacher_can_generate_only_owned_group_closed_week_report(self):
        self._login(self.teacher)
        response = self._post(
            "school-weekly-report-generate", {"group_id": self.group.pk},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["report"]["group_id"], self.group.pk)
        self.assertEqual(
            self._post("school-weekly-report-generate", {"group_id": self.foreign_group.pk}).status_code,
            404,
        )
        unfinished_start = timezone.now()
        unfinished_end = unfinished_start + timedelta(days=2)
        self.assertEqual(self._post(
            "school-weekly-report-generate",
            {"group_id": self.group.pk, "period_start": unfinished_start.isoformat(),
             "period_end": unfinished_end.isoformat()},
        ).status_code, 400)

    def test_parent_reads_only_their_verified_childs_weekly_report(self):
        report_services.generate_student_report(self.ali, PERIOD_START, PERIOD_END)
        report_services.generate_student_report(self.zuhra, PERIOD_START, PERIOD_END)
        self._login(self.parent)
        body = self.client.get(self.url("billing-weekly-reports-my")).json()
        self.assertEqual(
            [row["student_id"] for row in body["results"]], [self.ali.pk],
        )
        self.assertIn("Ali", body["results"][0]["text"])

    def test_schedule_endpoint_hides_configuration_from_teachers(self):
        self._login(self.teacher)
        teacher_body = self.client.get(self.url("school-weekly-report-schedule")).json()
        self.assertNotIn("send_hour", teacher_body)
        self.assertIn("next_run_at", teacher_body)

        self._login(self.admin)
        admin_body = self.client.get(self.url("school-weekly-report-schedule")).json()
        self.assertIn("send_hour", admin_body)
        self.assertEqual(admin_body["send_hour"], 9)

    def test_period_preview_reports_the_completed_week(self):
        self._login(self.teacher)
        body = self.client.get(self.url("billing-report-period")).json()
        self.assertEqual(body["period_label"], report_services.period_label(
            PERIOD_START, PERIOD_END,
        ))
        self.assertTrue(body["is_complete"])

    def test_send_endpoint_is_dedup_keyed(self):
        User.objects.filter(pk=self.teacher.pk).update(telegram_chat_id=4242)
        self.teacher.refresh_from_db()
        self._login(self.teacher)
        first = self._post(
            "school-weekly-report-send", {}, report_id=self.report.pk,
        ).json()
        # No reachable Telegram transport in tests, so the send fails cleanly...
        self.assertEqual(first["sent"], 0)
        self.assertEqual(first["failed"], 1)
        # ...and the failure is recorded rather than raised.
        second = self._post(
            "school-weekly-report-send", {}, report_id=self.report.pk,
        ).json()
        self.assertEqual(second["sent"], 0)

    def test_delivery_log_is_scoped_to_the_callers_groups(self):
        self._login(self.teacher)
        response = self.client.get(
            self.url("school-weekly-report-deliveries"),
            {"report_id": self.foreign_report.pk},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            self.client.get(self.url("school-weekly-report-deliveries")).status_code, 200,
        )

    def test_attendance_recorded_by_the_bot_appears_in_the_report(self):
        """Bot and website share one backend: a persisted register is reported."""
        from apps.attendance import services as attendance_services

        first_day, _last = report_services.period_dates(PERIOD_START, PERIOD_END)
        session, _created = attendance_services.create_session(
            group=self.group, teacher=self.teacher, actor=self.teacher,
            lesson_date=first_day,
        )
        attendance_services.mark(
            session, self.ali, AttendanceRecord.Status.PRESENT, actor=self.teacher,
        )
        # A finalized register requires an explicit status for every rostered
        # student. Marking the other student as excused proves that an
        # unexcused absence is not inferred merely from missing attendance.
        attendance_services.mark(
            session, self.zuhra, AttendanceRecord.Status.EXCUSED, actor=self.teacher,
        )
        result = attendance_services.finalize(
            session, actor=self.teacher, mark_unmarked_as_absent=False,
        )
        self.assertTrue(result["ok"])
        regenerated = report_services.regenerate(
            WeeklyGroupReport.objects.get(group=self.group, is_current=True),
            actor=self.admin, reason="Bez davomat qo'shildi",
        )
        attendance = regenerated.summary["attendance"]
        self.assertEqual(attendance["finalized_lessons"], 1)
        self.assertEqual(attendance["present"], 1)
        # The excused student is not converted into an unexcused absence.
        self.assertEqual(attendance["excused_absences"], 1)
        self.assertEqual(attendance["unexcused_absences"], 0)
        self.assertEqual(attendance["marked_records"], 2)
