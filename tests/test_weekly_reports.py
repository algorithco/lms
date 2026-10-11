"""Weekly academic report regressions.

The report is a *persisted record* of a closed week, so these tests pin the
things a wrong implementation would quietly get wrong:

* the period is Monday 00:00 → Sunday 23:59:59.999999 in Asia/Tashkent, and an
  unfinished week can never be published as final;
* counts come from FINALIZED registers only, and an unmarked student is never
  turned into an absence;
* a pending essay is not a graded zero-score essay;
* a practice percentage is labelled practice;
* a teacher never sees another group's data, nor tuition figures they have no
  permission for;
* the same week is generated once and delivered once.
"""
from __future__ import annotations

import datetime as dt
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import ParentStudentLink, User
from apps.attendance import services as attendance_services
from apps.attendance.models import (
    AttendanceRecord,
    AttendanceSession,
    NotificationPreference,
)
from apps.courses.models import Course, Enrollment, StudentGroup
from apps.essays.models import EssayAssignment, EssaySubmission, EssayTopic
from apps.results.models import Result
from apps.tests.models import Test, TestAttempt
from apps.tuition.models import CourseBillingPolicy, CourseInvoice
from apps.weekly_reports import delivery, services
from apps.weekly_reports.models import (
    WeeklyGroupReport,
    WeeklyReportDelivery,
    WeeklyReportSettings,
)

#: The report under test always covers the completed previous week.
PERIOD_START, PERIOD_END = services.previous_week_bounds()
PERIOD_FIRST_DAY, PERIOD_LAST_DAY = services.period_dates(PERIOD_START, PERIOD_END)


def touch(model, pk: int, field: str, when):
    model.objects.filter(pk=pk).update(**{field: when})


class _ReportFixture(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="wr-admin@example.test", password="testpass123", role="admin",
            telegram_chat_id=900001,
        )
        self.teacher = User.objects.create_user(
            email="wr-teacher@example.test", password="testpass123", role="teacher",
            first_name="Oqituvchi", telegram_chat_id=900002,
        )
        self.other_teacher = User.objects.create_user(
            email="wr-teacher2@example.test", password="testpass123", role="teacher",
            telegram_chat_id=900003,
        )
        self.ali = User.objects.create_user(
            email="wr-ali@example.test", password="testpass123", role="student",
            first_name="Ali", last_name="Valiyev",
        )
        self.zuhra = User.objects.create_user(
            email="wr-zuhra@example.test", password="testpass123", role="student",
            first_name="Zuhra", last_name="Karimova",
        )
        self.gulnora = User.objects.create_user(
            email="wr-gulnora@example.test", password="testpass123", role="student",
            first_name="Gulnora", last_name="Yusupova",
        )
        self.outsider = User.objects.create_user(
            email="wr-outsider@example.test", password="testpass123", role="student",
            first_name="Begona", last_name="Oquvchi",
        )
        self.group = StudentGroup.objects.create(teacher=self.teacher, name="9-A")
        self.group.students.add(self.ali, self.zuhra, self.gulnora)
        self.other_group = StudentGroup.objects.create(
            teacher=self.other_teacher, name="10-B",
        )
        self.other_group.students.add(self.outsider)

    # -- helpers ----------------------------------------------------------
    def _finalized_session(self, lesson_day=PERIOD_FIRST_DAY):
        session, _created = attendance_services.create_session(
            group=self.group, teacher=self.teacher, actor=self.teacher,
            lesson_date=lesson_day,
        )
        return session

    def _mark(self, session, student, status, *, late_minutes=0):
        return attendance_services.mark(
            session, student, status, actor=self.teacher,
            late_minutes=late_minutes,
        )

    def _essay_setup(self):
        topic = EssayTopic.objects.create(title="Kitobxonlik", description="")
        assignment = EssayAssignment.objects.create(
            topic=topic, group=self.group, assigned_by=self.teacher,
        )
        return topic, assignment

    def _submission(self, *, student, topic, assignment=None, status, score=None,
                    submitted_on=None, source=EssaySubmission.Source.WEB,
                    max_score=24):
        submission = EssaySubmission.objects.create(
            student=student, topic=topic, essay_text="esse matni",
            # ``total_score`` is NOT NULL: an ungraded essay stores 0 and is
            # excluded from the average by its *status*, never by its score.
            status=status,
            total_score=Decimal(score) if score is not None else Decimal("0"),
            max_score=max_score, source=source, assignment=assignment,
            submitted_at=submitted_on or (PERIOD_START + timedelta(days=1)),
        )
        return submission


class PeriodMathTests(TestCase):
    def test_week_runs_monday_midnight_to_sunday_end_of_day(self):
        anchor = dt.datetime(2026, 10, 8, 15, 30, tzinfo=services.reporting_timezone())
        start, end = services.week_bounds(anchor)
        local_start, local_end = (
            start.astimezone(services.reporting_timezone()),
            end.astimezone(services.reporting_timezone()),
        )
        self.assertEqual(start.weekday(), 0)                       # Monday
        self.assertEqual((local_start.hour, local_start.minute), (0, 0))
        self.assertEqual(local_end.weekday(), 6)                   # Sunday
        self.assertEqual(
            (local_end.hour, local_end.minute, local_end.second), (23, 59, 59),
        )
        self.assertEqual(local_end.microsecond, 999999)
        self.assertEqual((local_end - local_start).days, 6)

    def test_previous_week_is_the_completed_week(self):
        now = dt.datetime(2026, 10, 12, 9, 0, tzinfo=services.reporting_timezone())
        start, end = services.previous_week_bounds(now)
        local_start = start.astimezone(services.reporting_timezone())
        local_end = end.astimezone(services.reporting_timezone())
        self.assertEqual(local_start.date(), dt.date(2026, 10, 5))
        self.assertEqual(local_end.date(), dt.date(2026, 10, 11))

    def test_an_unfinished_week_is_never_treated_as_final(self):
        now = timezone.now()
        start, end = services.week_bounds(now)
        self.assertFalse(services.is_period_complete(end, now=now))
        with self.assertRaises(ValueError):
            services.ensure_complete(end, now=now)

        _, last_week_end = services.previous_week_bounds(now)
        self.assertTrue(services.is_period_complete(last_week_end, now=now))
        services.ensure_complete(last_week_end, now=now)  # must not raise

    def test_next_run_follows_the_configured_schedule(self):
        config = WeeklyReportSettings.load()
        config.send_weekday = 0
        config.send_hour = 9
        config.send_minute = 0
        config.save()

        _start, last_end = services.previous_week_bounds(timezone.now())
        run_at = services.next_run_at(last_end)
        local = run_at.astimezone(services.reporting_timezone())
        self.assertEqual(local.weekday(), 0)
        self.assertEqual((local.hour, local.minute), (9, 0))
        self.assertGreater(run_at, last_end)

        # An administrator moving the send time changes the next run.
        config.send_hour = 14
        config.save()
        local = services.next_run_at(last_end).astimezone(services.reporting_timezone())
        self.assertEqual(local.hour, 14)

    def test_settings_row_is_a_singleton(self):
        first = WeeklyReportSettings.load()
        second = WeeklyReportSettings.load()
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(WeeklyReportSettings.objects.count(), 1)

    def test_schedule_task_uses_admin_time_and_claims_once(self):
        from apps.weekly_reports.tasks import generate_and_send_weekly_reports
        from unittest.mock import patch

        now = dt.datetime(2026, 10, 12, 9, 0, tzinfo=services.reporting_timezone())
        _start, latest_end = services.previous_week_bounds(now)
        latest_start, _end = services.week_bounds(now - timedelta(days=7))
        config = WeeklyReportSettings.load()
        config.send_weekday = 0
        config.send_hour = 9
        config.send_minute = 0
        config.save()
        with (
            patch("apps.weekly_reports.tasks.timezone.now", return_value=now),
            patch("apps.weekly_reports.tasks.services.week_bounds", return_value=(latest_start, latest_end)),
            patch("apps.weekly_reports.tasks.services.generate_all_reports", return_value={"groups_created": 0}) as generate,
            patch("apps.weekly_reports.tasks.delivery.send_reports", return_value={"sent": 0}) as send,
            patch.object(generate_and_send_weekly_reports, "apply_async"),
        ):
            first = generate_and_send_weekly_reports.apply().get()
            second = generate_and_send_weekly_reports.apply().get()
        self.assertEqual(first["status"], "completed")
        self.assertEqual(second["status"], "already_processed")
        generate.assert_called_once()
        send.assert_called_once()

    def test_schedule_task_does_not_send_before_configured_time(self):
        from apps.weekly_reports.tasks import generate_and_send_weekly_reports
        from unittest.mock import patch

        config = WeeklyReportSettings.load()
        config.send_weekday = 0
        config.send_hour = 9
        config.send_minute = 0
        config.save()
        now = dt.datetime(2026, 10, 12, 8, 59, tzinfo=services.reporting_timezone())
        with (
            patch("apps.weekly_reports.tasks.timezone.now", return_value=now),
            patch("apps.weekly_reports.tasks.services.generate_all_reports") as generate,
            patch.object(generate_and_send_weekly_reports, "apply_async"),
        ):
            result = generate_and_send_weekly_reports.apply().get()
        self.assertEqual(result["status"], "not_due")
        generate.assert_not_called()


class AttendanceAggregationTests(_ReportFixture):
    def test_finalized_counts_split_late_and_excused_from_unexcused(self):
        session = self._finalized_session()
        self._mark(session, self.ali, AttendanceRecord.Status.PRESENT)
        self._mark(session, self.zuhra, AttendanceRecord.Status.LATE, late_minutes=12)
        self._mark(
            session, self.gulnora, AttendanceRecord.Status.EXCUSED,
        )
        attendance_services.finalize(
            session, actor=self.teacher, mark_unmarked_as_absent=True,
        )

        block = services.attendance_summary(self.group, PERIOD_START, PERIOD_END)
        self.assertEqual(block["active_students"], 3)
        self.assertEqual(block["finalized_lessons"], 1)
        self.assertEqual(block["present"], 1)
        self.assertEqual(block["late"], 1)
        self.assertEqual(block["excused_absences"], 1)
        self.assertEqual(block["unexcused_absences"], 0)
        # 2 of 3 marked records were attended.
        self.assertEqual(block["attendance_percentage"], 66.7)

    def test_an_unfinished_register_cannot_create_absences(self):
        session = self._finalized_session()
        self._mark(session, self.ali, AttendanceRecord.Status.PRESENT)

        block = services.attendance_summary(self.group, PERIOD_START, PERIOD_END)
        self.assertEqual(block["finalized_lessons"], 0)
        self.assertEqual(block["unfinished_lessons"], 1)
        self.assertEqual(block["unexcused_absences"], 0)
        self.assertIsNone(block["attendance_percentage"])

    def test_students_needing_follow_up_are_listed_from_real_records(self):
        first = self._finalized_session(PERIOD_FIRST_DAY)
        second = self._finalized_session(PERIOD_FIRST_DAY + timedelta(days=1))
        for session in (first, second):
            self._mark(session, self.zuhra, AttendanceRecord.Status.ABSENT)
            self._mark(session, self.ali, AttendanceRecord.Status.PRESENT)
            attendance_services.finalize(
                session, actor=self.teacher, mark_unmarked_as_absent=True,
            )

        block = services.attendance_summary(self.group, PERIOD_START, PERIOD_END)
        follow_up = {row["student_id"]: row for row in block["students_requiring_follow_up"]}
        self.assertIn(self.zuhra.pk, follow_up)
        self.assertEqual(follow_up[self.zuhra.pk]["unexcused_absences"], 2)
        self.assertEqual(follow_up[self.zuhra.pk]["name"], "Zuhra")
        self.assertNotIn(self.ali.pk, follow_up)
        self.assertEqual(block["follow_up_count"], len(block["students_requiring_follow_up"]))


class EssayAggregationTests(_ReportFixture):
    def test_pending_essays_are_not_counted_as_graded(self):
        topic, assignment = self._essay_setup()
        self._submission(
            student=self.ali, topic=topic, assignment=assignment,
            status=EssaySubmission.Status.GRADED, score=20,
        )
        self._submission(
            student=self.zuhra, topic=topic, assignment=assignment,
            status=EssaySubmission.Status.PENDING,
        )

        block = services.essays_summary(self.group, PERIOD_START, PERIOD_END)
        self.assertEqual(block["assigned_essays"], 1)
        self.assertEqual(block["expected_submissions"], 3)   # the live roster
        self.assertEqual(block["submitted"], 2)
        self.assertEqual(block["submitted_students"], 2)
        self.assertEqual(block["missing_submissions"], 1)
        self.assertEqual(block["graded"], 1)
        self.assertEqual(block["pending_ai"], 1)
        self.assertEqual(block["average_raw_score"], 20.0)
        self.assertEqual(block["max_score"], 24)
        self.assertEqual(block["score_distribution"]["70-90%"], 1)
        self.assertEqual(block["score_distribution"]["0-50%"], 0)

    def test_teacher_reviewed_is_counted_separately_from_ai_graded(self):
        topic, assignment = self._essay_setup()
        self._submission(
            student=self.ali, topic=topic, assignment=assignment,
            status=EssaySubmission.Status.TEACHER_REVIEWED, score=22,
        )
        block = services.essays_summary(self.group, PERIOD_START, PERIOD_END)
        self.assertEqual(block["graded"], 1)
        self.assertEqual(block["teacher_reviewed"], 1)

    def test_web_and_bot_submissions_land_in_the_same_report(self):
        topic, assignment = self._essay_setup()
        self._submission(
            student=self.ali, topic=topic, assignment=assignment,
            status=EssaySubmission.Status.GRADED, score=20,
            source=EssaySubmission.Source.WEB,
        )
        self._submission(
            student=self.zuhra, topic=topic, assignment=assignment,
            status=EssaySubmission.Status.GRADED, score=18,
            source=EssaySubmission.Source.TELEGRAM,
        )
        block = services.essays_summary(self.group, PERIOD_START, PERIOD_END)
        self.assertEqual(block["graded"], 2)
        self.assertEqual(block["submitted_students"], 2)
        self.assertEqual(block["average_raw_score"], 19.0)

    def test_another_groups_essay_never_appears(self):
        foreign_topic = EssayTopic.objects.create(title="Tabiat", description="")
        foreign_assignment = EssayAssignment.objects.create(
            topic=foreign_topic, group=self.other_group, assigned_by=self.other_teacher,
        )
        self._submission(
            student=self.outsider, topic=foreign_topic,
            assignment=foreign_assignment,
            status=EssaySubmission.Status.GRADED, score=18,
        )
        block = services.essays_summary(self.group, PERIOD_START, PERIOD_END)
        self.assertEqual(block["submitted"], 0)
        self.assertEqual(block["graded"], 0)
        self.assertIsNone(block["average_raw_score"])
        self.assertEqual(block["missing_submissions"], 0)  # no assignments here

    def test_a_private_essay_is_never_counted(self):
        topic, assignment = self._essay_setup()
        self._submission(
            student=self.ali, topic=topic, assignment=assignment,
            status=EssaySubmission.Status.GRADED, score=20,
        )
        EssaySubmission.objects.filter(student=self.ali).update(
            group_visibility=EssaySubmission.GroupVisibility.PRIVATE,
        )
        block = services.essays_summary(self.group, PERIOD_START, PERIOD_END)
        self.assertEqual(block["submitted"], 0)
        self.assertEqual(block["graded"], 0)

    def test_submissions_outside_the_period_are_excluded(self):
        topic, assignment = self._essay_setup()
        self._submission(
            student=self.ali, topic=topic, assignment=assignment,
            status=EssaySubmission.Status.GRADED, score=20,
            submitted_on=PERIOD_START - timedelta(days=2),
        )
        block = services.essays_summary(self.group, PERIOD_START, PERIOD_END)
        self.assertEqual(block["submitted"], 0)


class TestAggregationTests(_ReportFixture):
    def setUp(self):
        super().setUp()
        self.course = Course.objects.create(
            teacher=self.teacher, title="Ona tili", description="kurs",
        )
        self.enrollment = Enrollment.objects.create(student=self.ali, course=self.course)
        self.test_model = Test.objects.create(
            title="1-nazorat", description="", course=self.course,
            status=Test.Status.PUBLISHED, is_active=True,
        )

    def _attempt(self, student, *, status, percentage=None):
        attempt = TestAttempt.objects.create(
            test=self.test_model, student=student, status=status,
        )
        touch(TestAttempt, attempt.pk, "started_at", PERIOD_START + timedelta(days=1))
        if percentage is not None:
            Result.objects.create(
                attempt=attempt, student=student, test=self.test_model,
                course=self.course, total_questions=10, correct_answers=6,
                wrong_answers=4, score=Decimal(percentage) / 10 * 10,
                max_score=Decimal("100"), percentage=Decimal(str(percentage)),
                is_passed=percentage >= 60,
            )
        return attempt

    def test_assigned_tests_come_from_the_enrolled_courses(self):
        block = services.tests_summary(self.group, PERIOD_START, PERIOD_END)
        self.assertEqual(block["assigned_tests"], 1)
        self.assertEqual(block["attempts"], 0)

    def test_completed_and_incomplete_attempts_are_distinguished(self):
        self._attempt(self.ali, status=TestAttempt.Status.COMPLETED, percentage=80)
        self._attempt(self.zuhra, status=TestAttempt.Status.IN_PROGRESS)
        block = services.tests_summary(self.group, PERIOD_START, PERIOD_END)
        self.assertEqual(block["completed_attempts"], 1)
        self.assertEqual(block["incomplete_attempts"], 1)
        self.assertEqual(block["attempts"], 2)

    def test_practice_score_is_explicitly_a_practice_score(self):
        self._attempt(self.ali, status=TestAttempt.Status.COMPLETED, percentage=55)
        block = services.tests_summary(self.group, PERIOD_START, PERIOD_END)
        self.assertEqual(block["average_practice_percentage"], 55.0)
        self.assertEqual(block["score_basis"], "practice")
        self.assertEqual(block["needs_support_count"], 1)
        self.assertEqual(block["needs_support"][0]["student_id"], self.ali.pk)

    def test_another_groups_attempts_are_not_counted(self):
        self._attempt(self.outsider, status=TestAttempt.Status.COMPLETED, percentage=90)
        block = services.tests_summary(self.group, PERIOD_START, PERIOD_END)
        self.assertEqual(block["attempts"], 0)


class GenerationAndVersioningTests(_ReportFixture):
    def test_generate_is_idempotent_for_a_closed_week(self):
        first = services.generate_group_report(
            self.group, PERIOD_START, PERIOD_END, actor=self.teacher,
        )
        second = services.generate_group_report(
            self.group, PERIOD_START, PERIOD_END, actor=self.teacher,
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(WeeklyGroupReport.objects.count(), 1)
        self.assertEqual(first.version, 1)
        self.assertTrue(first.is_current)

    def test_regeneration_is_explicit_and_versioned(self):
        original = services.generate_group_report(
            self.group, PERIOD_START, PERIOD_END, actor=self.teacher,
        )
        replacement = services.regenerate(
            original, actor=self.admin, reason="Davomat tuzatildi",
        )
        self.assertEqual(replacement.version, 2)
        self.assertTrue(replacement.is_current)
        self.assertEqual(replacement.supersedes_id, original.pk)
        self.assertEqual(replacement.generation_reason, "Davomat tuzatildi")

        original.refresh_from_db()
        self.assertFalse(original.is_current)
        # Both versions survive: the audit trail is the point.
        self.assertEqual(WeeklyGroupReport.objects.count(), 2)
        self.assertEqual(
            WeeklyGroupReport.objects.filter(is_current=True).count(), 1,
        )

    def test_generate_all_reports_is_recoverable(self):
        first = services.generate_all_reports(PERIOD_START, PERIOD_END)
        self.assertEqual(first["groups_created"], 2)
        second = services.generate_all_reports(PERIOD_START, PERIOD_END)
        self.assertEqual(second["groups_created"], 0)
        self.assertEqual(second["groups_reused"], 2)
        self.assertEqual(WeeklyGroupReport.objects.count(), 2)

    def test_summary_is_scoped_to_one_group(self):
        report = services.generate_group_report(
            self.group, PERIOD_START, PERIOD_END, actor=self.teacher,
        )
        self.assertEqual(report.summary["group_id"], self.group.pk)
        self.assertEqual(report.summary["group_name"], "9-A")
        self.assertEqual(report.summary["period"]["label"],
                         services.period_label(PERIOD_START, PERIOD_END))


class _DeliveryTransport:
    """A fake transport that records what was sent and can be told to fail."""

    def __init__(self, *, fail=False):
        self.calls: list = []
        self.fail = fail

    def __call__(self, chat_id, text, buttons, recipient, title):
        self.calls.append({"chat_id": chat_id, "text": text, "buttons": buttons})
        if self.fail:
            return {"success": False, "message_id": None, "error": "Telegram down"}
        return {"success": True, "message_id": len(self.calls), "error": None}

    @property
    def last_text(self) -> str:
        return self.calls[-1]["text"] if self.calls else ""


class DeliveryAndPrivacyTests(_ReportFixture):
    def setUp(self):
        super().setUp()
        self.report = services.generate_group_report(
            self.group, PERIOD_START, PERIOD_END, actor=self.teacher,
        )

    def _finance_invoice(self):
        policy = CourseBillingPolicy.objects.create(
            name="9-A oylik", group=self.group, amount_uzs=300_000, due_day=10,
        )
        return CourseInvoice.objects.create(
            student=self.ali, policy=policy, scope_key=f"group:{self.group.pk}:wr",
            billing_period_start=PERIOD_FIRST_DAY, billing_period_end=PERIOD_LAST_DAY,
            period_label="test", base_amount_uzs=Decimal("300000"),
            amount_due_uzs=Decimal("300000"), paid_amount_uzs=Decimal("300000"),
            due_date=PERIOD_LAST_DAY, status=CourseInvoice.Status.PAID,
        )

    def test_teacher_receives_a_private_report_from_real_counts(self):
        session = self._finalized_session()
        self._mark(session, self.ali, AttendanceRecord.Status.PRESENT)
        attendance_services.finalize(
            session, actor=self.teacher, mark_unmarked_as_absent=True,
        )
        transport = _DeliveryTransport()
        result = delivery.send_reports(PERIOD_START, PERIOD_END, transport=transport)

        self.assertEqual(result["sent"], 1)
        self.assertEqual(result["deferred"], 0)
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(transport.calls[0]["chat_id"], self.teacher.telegram_chat_id)
        text = transport.last_text
        self.assertIn("9-A", text)
        self.assertIn("Davomat", text)
        self.assertIn("Sababsiz", text)
        # No tuition permission, so no payment block at all.
        self.assertNotIn("Kurs to'lovlari", text)

    def test_the_same_week_is_never_delivered_twice(self):
        transport = _DeliveryTransport()
        first = delivery.send_reports(PERIOD_START, PERIOD_END, transport=transport)
        second = delivery.send_reports(PERIOD_START, PERIOD_END, transport=transport)
        self.assertEqual(first["sent"], 1)
        self.assertEqual(second["sent"], 0)
        self.assertEqual(second["duplicates"], 1)
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(WeeklyReportDelivery.objects.count(), 1)

    def test_correcting_the_week_resends_as_a_new_version(self):
        transport = _DeliveryTransport()
        delivery.send_reports(PERIOD_START, PERIOD_END, transport=transport)
        replacement = services.regenerate(
            self.report, actor=self.admin, reason="Esse bahosi tuzatildi",
        )
        result = delivery.send_reports(PERIOD_START, PERIOD_END, transport=transport)
        self.assertEqual(result["sent"], 1)
        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(replacement.version, 2)
        self.assertEqual(WeeklyReportDelivery.objects.count(), 2)

    def test_a_stale_pending_delivery_can_be_recovered(self):
        from datetime import timedelta

        from django.utils import timezone

        row = WeeklyReportDelivery.objects.create(
            report=self.report, recipient=self.teacher,
            dedup_key=delivery.group_dedup_key(
                self.report, self.teacher, WeeklyReportDelivery.Channel.TELEGRAM,
            ),
            channel=WeeklyReportDelivery.Channel.TELEGRAM,
            status=WeeklyReportDelivery.Status.PENDING,
            retry_count=1,
        )
        WeeklyReportDelivery.objects.filter(pk=row.pk).update(
            last_attempt_at=timezone.now() - timedelta(minutes=15),
        )
        calls = _DeliveryTransport()
        recovered = delivery.deliver_group_report(self.report, self.teacher, transport=calls)
        self.assertTrue(recovered.attempted)
        self.assertEqual(recovered.status, WeeklyReportDelivery.Status.SENT)
        self.assertEqual(len(calls.calls), 1)

    def test_a_missing_telegram_link_defers_but_keeps_the_report(self):
        User.objects.filter(pk=self.teacher.pk).update(telegram_chat_id=None)
        transport = _DeliveryTransport()
        result = delivery.send_reports(PERIOD_START, PERIOD_END, transport=transport)
        self.assertEqual(result["deferred"], 1)
        self.assertEqual(len(transport.calls), 0)
        row = WeeklyReportDelivery.objects.get()
        self.assertEqual(row.status, WeeklyReportDelivery.Status.DEFERRED)
        # The report itself is still there, and still readable in the dashboard.
        self.assertTrue(WeeklyGroupReport.objects.filter(pk=self.report.pk).exists())
        payload = delivery.group_report_text(self.report)
        self.assertIn("9-A", payload)

    def test_a_transport_failure_is_recorded_then_retried(self):
        broken = _DeliveryTransport(fail=True)
        result = delivery.send_reports(PERIOD_START, PERIOD_END, transport=broken)
        self.assertEqual(result["failed"], 1)
        row = WeeklyReportDelivery.objects.get()
        self.assertEqual(row.status, WeeklyReportDelivery.Status.FAILED)
        self.assertIn("Telegram down", row.last_error)
        self.assertEqual(row.retry_count, 1)

        healthy = _DeliveryTransport()
        retry = delivery.retry_failed_deliveries(transport=healthy)
        self.assertEqual(retry["sent"], 1)
        self.assertEqual(len(healthy.calls), 1)
        row.refresh_from_db()
        self.assertEqual(row.status, WeeklyReportDelivery.Status.SENT)
        self.assertEqual(row.retry_count, 2)

    def test_retries_stop_at_the_configured_attempt_limit(self):
        config = WeeklyReportSettings.load()
        config.max_delivery_attempts = 1
        config.save()
        broken = _DeliveryTransport(fail=True)
        delivery.send_reports(PERIOD_START, PERIOD_END, transport=broken)
        healthy = _DeliveryTransport()
        delivery.retry_failed_deliveries(transport=healthy)
        self.assertEqual(len(healthy.calls), 0)

    def test_a_recipient_can_switch_the_weekly_message_off(self):
        NotificationPreference.objects.create(
            user=self.teacher, teacher_weekly_report=False,
        )
        transport = _DeliveryTransport()
        result = delivery.send_reports(PERIOD_START, PERIOD_END, transport=transport)
        self.assertEqual(result["sent"], 0)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(WeeklyReportDelivery.objects.count(), 0)

    def test_teachers_never_receive_another_groups_report(self):
        services.generate_group_report(
            self.other_group, PERIOD_START, PERIOD_END, actor=self.other_teacher,
        )
        transport = _DeliveryTransport()
        delivery.send_reports(PERIOD_START, PERIOD_END, transport=transport)
        own = set(
            WeeklyReportDelivery.objects.filter(report__group=self.group)
            .values_list("recipient_id", flat=True)
        )
        foreign = set(
            WeeklyReportDelivery.objects.filter(report__group=self.other_group)
            .values_list("recipient_id", flat=True)
        )
        self.assertEqual(own, {self.teacher.pk})
        self.assertEqual(foreign, {self.other_teacher.pk})

    def test_only_subscribed_admins_receive_group_reports(self):
        config = WeeklyReportSettings.load()
        transport = _DeliveryTransport()
        delivery.send_reports(PERIOD_START, PERIOD_END, transport=transport)
        self.assertNotIn(
            self.admin.pk,
            {row.recipient_id for row in WeeklyReportDelivery.objects.all()},
        )

        config.admin_recipients.add(self.admin)
        config.save()
        delivery.send_reports(PERIOD_START, PERIOD_END, transport=transport)
        self.assertIn(
            self.admin.pk,
            {row.recipient_id for row in WeeklyReportDelivery.objects.all()},
        )

    def test_finance_block_is_visible_only_to_authorized_recipients(self):
        self._finance_invoice()
        # A report is a frozen record, so the newly configured tuition only
        # appears after an explicit, versioned regeneration.
        report = services.regenerate(
            self.report, actor=self.admin, reason="Kurs to'lovi sozlandi",
        )
        self.assertIsNotNone(report.summary["finance"])
        self.assertTrue(report.summary["finance"]["policy_configured"])

        # A plain teacher owns the group but has no tuition permission.
        teacher_text = delivery.group_report_text(
            report, include_finance=delivery._may_see_finance(self.teacher),
        )
        self.assertNotIn("Kurs to'lovlari", teacher_text)
        self.assertNotIn("so'm", teacher_text)

        # A platform administrator does.
        admin_text = delivery.group_report_text(
            report, include_finance=delivery._may_see_finance(self.admin),
        )
        self.assertIn("Kurs to'lovlari", admin_text)
        self.assertIn("To'langan", admin_text)

    def test_dashboard_payload_strips_finance_for_unauthorized_readers(self):
        self._finance_invoice()
        report = services.regenerate(
            self.report, actor=self.admin, reason="Kurs to'lovi sozlandi",
        )
        teacher_view = delivery.visible_summary(report, self.teacher)
        self.assertFalse(teacher_view["finance_visible"])
        self.assertNotIn("finance", teacher_view)
        admin_view = delivery.visible_summary(report, self.admin)
        self.assertTrue(admin_view["finance_visible"])
        self.assertIn("finance", admin_view)

    def test_group_report_buttons_include_finance_only_when_allowed(self):
        teacher_rows = delivery.report_buttons(self.report, include_finance=False)
        admin_rows = delivery.report_buttons(self.report, include_finance=True)
        self.assertEqual(len(teacher_rows), 2)
        self.assertEqual(len(admin_rows), 3)
        callbacks = [button["callback_data"] for row in admin_rows for button in row]
        self.assertIn(f"wr_fin_{self.report.pk}", callbacks)


class ParentReportTests(_ReportFixture):
    def setUp(self):
        super().setUp()
        self.parent = User.objects.create_user(
            email="wr-parent@example.test", password="testpass123", role="parent",
            telegram_chat_id=900010,
        )
        self.relative = User.objects.create_user(
            email="wr-relative@example.test", password="testpass123", role="parent",
            telegram_chat_id=900011,
        )
        ParentStudentLink.objects.create(
            parent=self.parent, student=self.ali, is_approved=True,
        )
        ParentStudentLink.objects.create(
            parent=self.relative, student=self.ali, is_approved=False,
        )

    def test_only_verified_approved_parents_are_recipients(self):
        self.assertEqual(
            [user.pk for user in delivery.recipients_for_student(self.ali)],
            [self.parent.pk],
        )

    def test_parent_report_contains_only_that_child(self):
        session = self._finalized_session()
        self._mark(session, self.ali, AttendanceRecord.Status.LATE, late_minutes=9)
        self._mark(session, self.zuhra, AttendanceRecord.Status.ABSENT)
        attendance_services.finalize(
            session, actor=self.teacher, mark_unmarked_as_absent=True,
        )

        report = services.generate_student_report(
            self.ali, PERIOD_START, PERIOD_END, actor=None,
        )
        self.assertEqual(report.summary["student_id"], self.ali.pk)
        text = delivery.student_report_text(report)
        self.assertIn("Ali", text)
        for other in ("Zuhra", "Gulnora", "Karimova", "Yusupova"):
            self.assertNotIn(other, text)
        self.assertEqual(report.summary["attendance"]["late"], 1)

    def test_parent_report_is_delivered_once(self):
        services.generate_all_reports(PERIOD_START, PERIOD_END)
        transport = _DeliveryTransport()
        delivery.send_reports(PERIOD_START, PERIOD_END, transport=transport)
        row = WeeklyReportDelivery.objects.get(student_report__student=self.ali)
        self.assertEqual(row.recipient_id, self.parent.pk)
        self.assertEqual(row.status, WeeklyReportDelivery.Status.SENT)

        delivery.send_reports(PERIOD_START, PERIOD_END, transport=transport)
        self.assertEqual(WeeklyReportDelivery.objects.filter(
            student_report__student=self.ali,
        ).count(), 1)

    def test_parent_can_switch_the_weekly_message_off(self):
        NotificationPreference.objects.create(
            user=self.parent, parent_weekly_report=False,
        )
        services.generate_student_report(self.ali, PERIOD_START, PERIOD_END)
        transport = _DeliveryTransport()
        delivery.send_reports(PERIOD_START, PERIOD_END, transport=transport)
        self.assertFalse(
            WeeklyReportDelivery.objects.filter(recipient=self.parent).exists()
        )


class TaskTests(_ReportFixture):
    def test_generate_only_task_is_idempotent_and_never_sends(self):
        from apps.weekly_reports import tasks

        first = tasks.generate_weekly_reports(
            PERIOD_START.isoformat(), PERIOD_END.isoformat(),
        )
        self.assertEqual(first["status"], "completed")
        self.assertEqual(first["groups_created"], 2)
        second = tasks.generate_weekly_reports(
            PERIOD_START.isoformat(), PERIOD_END.isoformat(),
        )
        self.assertEqual(second["groups_created"], 0)
        self.assertEqual(WeeklyReportDelivery.objects.count(), 0)

    def test_retry_task_reports_disabled_configuration(self):
        from apps.weekly_reports import tasks

        config = WeeklyReportSettings.load()
        config.retry_failed_deliveries = False
        config.save()
        result = tasks.retry_weekly_report_deliveries()
        self.assertTrue(result.get("disabled"))
        self.assertEqual(result["retried"], 0)
