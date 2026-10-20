"""Attendance workflow regressions: sessions, marking, finalization, reports.

Everything is exercised through `apps.attendance.services`, which is the single
entry point the React panel, the JSON API and the Telegram bot all call. Testing
the service layer keeps these assertions independent of transport.
"""

import datetime as dt

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.attendance import services as att
from apps.attendance.models import (
    AttendanceAuditLog,
    AttendanceRecord,
    AttendanceSession,
)
from apps.courses.models import StudentGroup

TODAY = timezone.localdate()
PERIOD_START = TODAY - dt.timedelta(days=7)
PERIOD_END = TODAY + dt.timedelta(days=1)


class _AttendanceFixture(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            email="aw-teacher@example.test",
            password="testpass123",
            role="teacher",
        )
        self.ali = User.objects.create_user(
            email="aw-ali@example.test",
            password="testpass123",
            role="student",
            first_name="Ali",
            last_name="Valiyev",
        )
        self.zuhra = User.objects.create_user(
            email="aw-zuhra@example.test",
            password="testpass123",
            role="student",
            first_name="Zuhra",
            last_name="Karimova",
        )
        self.gulnora = User.objects.create_user(
            email="aw-gulnora@example.test",
            password="testpass123",
            role="student",
            first_name="Gulnora",
            last_name="Yusupova",
        )
        self.group = StudentGroup.objects.create(teacher=self.teacher, name="9-A")
        self.group.students.add(self.ali, self.zuhra, self.gulnora)

    def _session(self, **kwargs):
        session, created = att.create_session(
            group=self.group,
            teacher=self.teacher,
            **kwargs,
        )
        return session, created


class SessionCreationTests(_AttendanceFixture):
    """A register must never be duplicated by a repeated Telegram callback."""

    def test_create_returns_created_flag_then_resolves_same_row(self):
        session, created = att.create_session(
            group=self.group,
            teacher=self.teacher,
            idempotency_key="cb-1",
        )
        self.assertTrue(created)
        self.assertEqual(AttendanceSession.objects.count(), 1)

        again, created_again = att.create_session(
            group=self.group,
            teacher=self.teacher,
            idempotency_key="cb-1",
        )
        self.assertFalse(created_again)
        self.assertEqual(again.pk, session.pk)
        self.assertEqual(AttendanceSession.objects.count(), 1)

    def test_same_slot_without_idempotency_key_is_also_deduplicated(self):
        first, created = att.create_session(
            group=self.group,
            teacher=self.teacher,
            start_time=dt.time(9, 0),
        )
        second, created_second = att.create_session(
            group=self.group,
            teacher=self.teacher,
            start_time=dt.time(9, 0),
        )
        self.assertTrue(created)
        self.assertFalse(created_second)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(AttendanceSession.objects.count(), 1)

    def test_multiple_sessions_in_one_day_stay_distinct(self):
        morning, _ = self._session(start_time=dt.time(9, 0))
        evening, _ = self._session(start_time=dt.time(15, 0))
        self.assertNotEqual(morning.pk, evening.pk)
        self.assertEqual(AttendanceSession.objects.count(), 2)
        self.assertEqual(morning.local_time_label(), "09:00")
        self.assertEqual(evening.local_time_label(), "15:00")

    def test_idempotency_key_cannot_be_reused_for_another_group(self):
        other = StudentGroup.objects.create(teacher=self.teacher, name="10-B")
        other.students.add(self.ali)
        att.create_session(
            group=self.group,
            teacher=self.teacher,
            idempotency_key="shared",
        )
        with self.assertRaises(att.AttendanceError):
            att.create_session(
                group=other,
                teacher=self.teacher,
                idempotency_key="shared",
            )

    def test_today_session_ignores_cancelled(self):
        session, _ = self._session()
        self.assertEqual(att.today_session(self.group).pk, session.pk)
        session.status = AttendanceSession.Status.CANCELLED
        session.save(update_fields=["status", "updated_at"])
        self.assertIsNone(att.today_session(self.group))


class RosterAndMarkingTests(_AttendanceFixture):
    """Unmarked students stay unmarked, and corrections update in place."""

    def test_roster_starts_unmarked_for_every_student(self):
        session, _ = self._session()
        rows = att.roster(session)
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row["status"] is None for row in rows))
        self.assertTrue(all(row["marked"] is False for row in rows))
        self.assertTrue(all(row["status_label"] == "Belgilanmagan" for row in rows))
        self.assertEqual(AttendanceRecord.objects.count(), 0)

    def test_mark_all_present_marks_exactly_the_unmarked(self):
        session, _ = self._session()
        att.mark(session, self.ali, AttendanceRecord.Status.ABSENT, actor=self.teacher)
        marked_count = att.mark_all_present(session, actor=self.teacher)
        self.assertEqual(marked_count, 2)
        self.assertEqual(AttendanceRecord.objects.count(), 3)
        # The explicit ABSENT is not overwritten.
        record = AttendanceRecord.objects.get(session=session, student=self.ali)
        self.assertEqual(record.status, AttendanceRecord.Status.ABSENT)
        self.assertEqual(
            att.summary(session)["present"],
            2,
        )

    def test_marking_twice_updates_one_row_and_appends_audit(self):
        session, _ = self._session()
        att.mark(
            session,
            self.ali,
            AttendanceRecord.Status.LATE,
            late_minutes=12,
            actor=self.teacher,
        )
        self.assertEqual(AttendanceRecord.objects.count(), 1)
        self.assertEqual(AttendanceAuditLog.objects.count(), 1)

        att.mark(
            session,
            self.ali,
            AttendanceRecord.Status.PRESENT,
            actor=self.teacher,
            reason="Xato tuzatildi",
        )
        self.assertEqual(AttendanceRecord.objects.count(), 1)

        record = AttendanceRecord.objects.get(session=session, student=self.ali)
        self.assertEqual(record.status, AttendanceRecord.Status.PRESENT)
        self.assertEqual(record.late_minutes, 0)
        audit = AttendanceAuditLog.objects.order_by("-created_at").first()
        self.assertEqual(audit.field, "status")
        self.assertEqual(audit.old_value, AttendanceRecord.Status.LATE)
        self.assertEqual(audit.new_value, AttendanceRecord.Status.PRESENT)
        self.assertEqual(audit.reason, "Xato tuzatildi")
        self.assertEqual(audit.actor_id, self.teacher.pk)

    def test_late_minutes_stored_only_for_late(self):
        session, _ = self._session()
        late = att.mark(
            session,
            self.ali,
            AttendanceRecord.Status.LATE,
            late_minutes=7,
            actor=self.teacher,
        )
        self.assertEqual(late.late_minutes, 7)

        att.mark(
            session,
            self.zuhra,
            AttendanceRecord.Status.PRESENT,
            late_minutes=9,
            actor=self.teacher,
        )
        record = AttendanceRecord.objects.get(session=session, student=self.zuhra)
        self.assertEqual(record.late_minutes, 0)

        excused = att.mark(
            session,
            self.gulnora,
            AttendanceRecord.Status.EXCUSED,
            actor=self.teacher,
            note="Shifokorda",
        )
        self.assertEqual(excused.late_minutes, 0)
        self.assertEqual(excused.note, "Shifokorda")

    def test_mark_many_applies_only_roster_members(self):
        session, _ = self._session()
        outsider = User.objects.create_user(
            email="aw-outsider@example.test",
            password="testpass123",
            role="student",
        )
        applied = att.mark_many(
            session,
            [
                {"student_id": self.ali.pk, "status": AttendanceRecord.Status.PRESENT},
                {
                    "student_id": self.zuhra.pk,
                    "status": AttendanceRecord.Status.LATE,
                    "late_minutes": 5,
                },
                {"student_id": outsider.pk, "status": AttendanceRecord.Status.PRESENT},
                {"student_id": 999999, "status": AttendanceRecord.Status.PRESENT},
            ],
            actor=self.teacher,
        )
        self.assertEqual(applied, 2)
        self.assertEqual(AttendanceRecord.objects.count(), 2)

    def test_summary_counts_are_exact(self):
        session, _ = self._session()
        att.mark(session, self.ali, AttendanceRecord.Status.PRESENT, actor=self.teacher)
        att.mark(
            session,
            self.zuhra,
            AttendanceRecord.Status.LATE,
            late_minutes=4,
            actor=self.teacher,
        )
        summary = att.summary(session)
        self.assertEqual(summary["roster_size"], 3)
        self.assertEqual(summary["marked"], 2)
        self.assertEqual(summary["unmarked"], 1)
        self.assertEqual(summary["present"], 1)
        self.assertEqual(summary["late"], 1)
        self.assertEqual(summary["absent"], 0)
        self.assertEqual(summary["excused"], 0)
        self.assertEqual(summary["attended"], 2)

    def test_unknown_status_is_rejected(self):
        session, _ = self._session()
        with self.assertRaises(att.AttendanceError):
            att.mark(session, self.ali, "maybe", actor=self.teacher)


class FinalizationTests(_AttendanceFixture):
    """An unfinished register must never be silently treated as full absence."""

    def test_finalize_refuses_while_students_are_unmarked(self):
        session, _ = self._session()
        att.mark(session, self.ali, AttendanceRecord.Status.PRESENT, actor=self.teacher)

        result = att.finalize(session, actor=self.teacher)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "unmarked_students")
        self.assertEqual(result["session_id"], session.pk)
        self.assertEqual(
            {row["student_id"] for row in result["unmarked"]},
            {self.zuhra.pk, self.gulnora.pk},
        )
        session.refresh_from_db()
        self.assertEqual(session.status, AttendanceSession.Status.DRAFT)
        self.assertIsNone(session.finalized_at)

    def test_finalize_with_explicit_confirmation_marks_only_unmarked_absent(self):
        session, _ = self._session()
        att.mark(session, self.ali, AttendanceRecord.Status.PRESENT, actor=self.teacher)
        att.mark(
            session, self.zuhra, AttendanceRecord.Status.EXCUSED, actor=self.teacher
        )

        result = att.finalize(session, actor=self.teacher, mark_unmarked_as_absent=True)
        self.assertTrue(result["ok"])
        self.assertEqual(result["present"], 1)
        self.assertEqual(result["excused"], 1)
        self.assertEqual(result["absent"], 1)
        self.assertEqual(result["unmarked"], 0)

        session.refresh_from_db()
        self.assertEqual(session.status, AttendanceSession.Status.FINALIZED)
        self.assertEqual(session.finalized_by_id, self.teacher.pk)
        self.assertIsNotNone(session.finalized_at)

    def test_finalize_succeeds_when_everyone_is_marked(self):
        session, _ = self._session()
        att.mark_all_present(session, actor=self.teacher)
        result = att.finalize(session, actor=self.teacher)
        self.assertTrue(result["ok"])
        self.assertEqual(result["present"], 3)
        self.assertEqual(result["unmarked"], 0)


class ReportTests(_AttendanceFixture):
    """Only finalized registers feed report percentages."""

    def _finalized_day(self, day, statuses, start_time=None):
        """Create, mark and finalize one register.

        ``start_time`` matters: two registers for the same date are only
        distinct when they occupy different periods, because the slot
        uniqueness is on (group, lesson_date, start_time).
        """
        session, _ = att.create_session(
            group=self.group,
            teacher=self.teacher,
            lesson_date=day,
            start_time=start_time,
        )
        for student, status in zip(
            (self.ali, self.zuhra, self.gulnora),
            statuses,
        ):
            att.mark(session, student, status, actor=self.teacher)
        att.finalize(session, actor=self.teacher)
        return session

    def test_unfinished_session_is_never_counted_as_absence(self):
        self._finalized_day(
            TODAY,
            (
                AttendanceRecord.Status.PRESENT,
                AttendanceRecord.Status.EXCUSED,
                AttendanceRecord.Status.PRESENT,
            ),
        )
        draft, _ = att.create_session(
            group=self.group,
            teacher=self.teacher,
            lesson_date=TODAY - dt.timedelta(days=1),
        )
        att.mark(draft, self.ali, AttendanceRecord.Status.ABSENT, actor=self.teacher)

        report = att.group_attendance_report(
            self.group,
            start=PERIOD_START,
            end=PERIOD_END,
        )
        self.assertEqual(report["finalized_sessions"], 1)
        self.assertEqual(report["pending_sessions"], 1)
        self.assertEqual(report["present"], 2)
        self.assertEqual(report["excused"], 1)
        self.assertEqual(report["absent"], 0)
        self.assertEqual(report["unexcused_absent"], 0)
        self.assertEqual(report["attended"], 2)
        # 2 of 3 marked records attended.
        self.assertEqual(report["attendance_percentage"], 66.7)

    def test_excused_is_separate_from_unexcused(self):
        self._finalized_day(
            TODAY,
            (
                AttendanceRecord.Status.ABSENT,
                AttendanceRecord.Status.EXCUSED,
                AttendanceRecord.Status.LATE,
            ),
        )
        report = att.group_attendance_report(
            self.group,
            start=PERIOD_START,
            end=PERIOD_END,
        )
        self.assertEqual(report["absent"], 1)
        self.assertEqual(report["excused"], 1)
        self.assertEqual(report["unexcused_absent"], 1)
        self.assertEqual(report["late_arrivals"], 1)
        self.assertEqual(report["attended"], 1)
        self.assertEqual(report["marked_records"], 3)

    def test_percentage_math_for_a_known_case(self):
        self._finalized_day(
            TODAY,
            (
                AttendanceRecord.Status.PRESENT,
                AttendanceRecord.Status.PRESENT,
                AttendanceRecord.Status.LATE,
            ),
        )
        report = att.group_attendance_report(
            self.group,
            start=PERIOD_START,
            end=PERIOD_END,
        )
        self.assertEqual(report["attended"], 3)
        self.assertEqual(report["marked_records"], 3)
        self.assertEqual(report["attendance_percentage"], 100.0)

    def test_report_is_none_percentage_without_marked_records(self):
        att.create_session(group=self.group, teacher=self.teacher)
        report = att.group_attendance_report(
            self.group,
            start=PERIOD_START,
            end=PERIOD_END,
        )
        self.assertIsNone(report["attendance_percentage"])
        self.assertEqual(report["marked_records"], 0)

    def test_daily_breakdown_aggregates_one_row_per_date(self):
        self._finalized_day(
            TODAY,
            (
                AttendanceRecord.Status.PRESENT,
                AttendanceRecord.Status.ABSENT,
                AttendanceRecord.Status.PRESENT,
            ),
        )
        yesterday = TODAY - dt.timedelta(days=1)
        self._finalized_day(
            yesterday,
            (
                AttendanceRecord.Status.LATE,
                AttendanceRecord.Status.PRESENT,
                AttendanceRecord.Status.EXCUSED,
            ),
            start_time=dt.time(9, 0),
        )
        # A second register on the same day (a different period) rolls up into
        # the same daily row rather than being counted as a separate day.
        self._finalized_day(
            yesterday,
            (
                AttendanceRecord.Status.PRESENT,
                AttendanceRecord.Status.PRESENT,
                AttendanceRecord.Status.PRESENT,
            ),
            start_time=dt.time(11, 0),
        )

        rows = att.group_daily_breakdown(
            self.group,
            start=PERIOD_START,
            end=PERIOD_END,
        )
        self.assertEqual(len(rows), 2)
        by_date = {row["date"]: row for row in rows}
        today_row = by_date[TODAY.isoformat()]
        self.assertEqual(today_row["present"], 2)
        self.assertEqual(today_row["absent"], 1)
        yesterday_row = by_date[yesterday.isoformat()]
        self.assertEqual(yesterday_row["present"], 4)
        self.assertEqual(yesterday_row["late"], 1)
        self.assertEqual(yesterday_row["excused"], 1)
        self.assertEqual(yesterday_row["attendance_percentage"], 83.3)

    def test_student_report_is_scoped_to_one_student(self):
        session, _ = att.create_session(group=self.group, teacher=self.teacher)
        att.mark(session, self.ali, AttendanceRecord.Status.PRESENT, actor=self.teacher)
        att.mark(
            session, self.zuhra, AttendanceRecord.Status.ABSENT, actor=self.teacher
        )

        report = att.student_attendance_report(
            self.ali,
            start=PERIOD_START,
            end=PERIOD_END,
        )
        self.assertEqual(report["student_id"], self.ali.pk)
        self.assertEqual(report["present"], 1)
        self.assertEqual(report["absent"], 0)
        self.assertEqual(report["marked_records"], 1)
        self.assertEqual(report["attendance_percentage"], 100.0)
        self.assertEqual(len(report["recent"]), 1)
        self.assertEqual(report["recent"][0]["status"], AttendanceRecord.Status.PRESENT)
        self.assertEqual(report["recent"][0]["group"], "9-A")

        other = att.student_attendance_report(
            self.zuhra,
            start=PERIOD_START,
            end=PERIOD_END,
        )
        self.assertEqual(other["present"], 0)
        self.assertEqual(other["absent"], 1)

    def test_teacher_overview_lists_only_owned_groups(self):
        other_teacher = User.objects.create_user(
            email="aw-teacher2@example.test",
            password="testpass123",
            role="teacher",
        )
        StudentGroup.objects.create(teacher=other_teacher, name="11-C")
        overview = att.teacher_attendance_overview(self.teacher)
        self.assertEqual([row["group_name"] for row in overview["groups"]], ["9-A"])
