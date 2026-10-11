"""Attendance and group-report authorization (negative-path) regressions.

These tests exist to prove that nothing leaks across teacher-group boundaries:
a teacher must never read or write another teacher's register, annotate a
student they do not teach, or enumerate another group's essays — regardless of
what the caller asks for.
"""
import datetime as dt

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.attendance import services as att
from apps.attendance.models import (
    AttendanceRecord,
    AttendanceSession,
    ClassroomObservation,
)
from apps.courses.models import StudentGroup
from apps.essays import group_reports
from apps.essays.models import EssayAssignment, EssaySubmission, EssayTopic


class _AuthFixture(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email="az-admin@example.test", password="testpass123",
        )
        self.teacher = User.objects.create_user(
            email="az-teacher@example.test", password="testpass123", role="teacher",
        )
        self.other_teacher = User.objects.create_user(
            email="az-other@example.test", password="testpass123", role="teacher",
        )
        self.mine_student = User.objects.create_user(
            email="az-mine@example.test", password="testpass123", role="student",
            first_name="Ali", last_name="V",
        )
        self.shared_student = User.objects.create_user(
            email="az-shared@example.test", password="testpass123", role="student",
            first_name="Zuhra", last_name="K",
        )
        self.stranger_student = User.objects.create_user(
            email="az-stranger@example.test", password="testpass123", role="student",
        )

        self.group = StudentGroup.objects.create(teacher=self.teacher, name="9-A")
        self.group.students.add(self.mine_student, self.shared_student)

        self.other_group = StudentGroup.objects.create(
            teacher=self.other_teacher, name="10-B",
        )
        self.other_group.students.add(self.shared_student)

        self.topic = EssayTopic.objects.create(
            title="Kitobxonlik", description="d", created_by=self.teacher,
        )
        self.my_assignment = EssayAssignment.objects.create(
            topic=self.topic, group=self.group, assigned_by=self.teacher,
        )
        self.foreign_assignment = EssayAssignment.objects.create(
            topic=self.topic, group=self.other_group, assigned_by=self.other_teacher,
        )

    def _my_session(self):
        session, _ = att.create_session(group=self.group, teacher=self.teacher)
        return session

    def _foreign_session(self):
        session, _ = att.create_session(
            group=self.other_group, teacher=self.other_teacher,
        )
        return session


class GroupScopingTests(_AuthFixture):
    def test_teacher_groups_excludes_other_teachers_groups(self):
        self.assertIn(self.group, att.teacher_groups(self.teacher))
        self.assertNotIn(self.other_group, att.teacher_groups(self.teacher))
        self.assertEqual(att.teacher_groups(self.teacher).count(), 1)

    def test_admin_sees_every_group(self):
        self.assertEqual(att.teacher_groups(self.admin).count(), 2)
        self.assertEqual(group_reports.teacher_groups(self.admin).count(), 2)

    def test_anonymous_sees_no_groups(self):
        from django.contrib.auth.models import AnonymousUser

        self.assertEqual(att.teacher_groups(AnonymousUser()).count(), 0)
        self.assertEqual(att.teacher_groups(None).count(), 0)

    def test_can_manage_group_reflects_ownership(self):
        self.assertTrue(att.can_manage_group(self.teacher, self.group))
        self.assertFalse(att.can_manage_group(self.teacher, self.other_group))
        self.assertTrue(att.can_manage_group(self.admin, self.other_group))


class SessionAccessTests(_AuthFixture):
    def test_teacher_cannot_open_a_register_for_another_group(self):
        with self.assertRaises(PermissionDenied):
            att.create_session(group=self.other_group, teacher=self.teacher)

    def test_get_session_for_user_hides_foreign_registers(self):
        foreign = self._foreign_session()
        with self.assertRaises(PermissionDenied):
            att.get_session_for_user(self.teacher, foreign.pk)
        # The owner (and a platform admin) can open their own.
        self.assertEqual(
            att.get_session_for_user(self.other_teacher, foreign.pk).pk, foreign.pk,
        )
        self.assertEqual(
            att.get_session_for_user(self.admin, foreign.pk).pk, foreign.pk,
        )

    def test_get_session_for_user_raises_for_missing_session(self):
        with self.assertRaises(AttendanceSession.DoesNotExist):
            att.get_session_for_user(self.teacher, 987654)

    def test_student_can_only_read_a_session_they_have_a_record_in(self):
        session = self._my_session()
        att.mark(session, self.mine_student, AttendanceRecord.Status.PRESENT,
                 actor=self.teacher)
        self.assertEqual(
            att.session_for_student(self.mine_student, session.pk).pk, session.pk,
        )
        with self.assertRaises(AttendanceSession.DoesNotExist):
            att.session_for_student(self.stranger_student, session.pk)


class MarkingAuthorizationTests(_AuthFixture):
    def test_mark_rejects_a_student_outside_the_group(self):
        session = self._my_session()
        with self.assertRaises(att.AttendanceError):
            att.mark(session, self.stranger_student,
                     AttendanceRecord.Status.PRESENT, actor=self.teacher)

    def test_mark_rejects_a_cancelled_session(self):
        session = self._my_session()
        session.status = AttendanceSession.Status.CANCELLED
        session.save(update_fields=["status", "updated_at"])
        with self.assertRaises(att.AttendanceError):
            att.mark(session, self.mine_student,
                     AttendanceRecord.Status.PRESENT, actor=self.teacher)

    def test_teacher_cannot_take_attendance_for_a_student_in_another_group(self):
        foreign = self._foreign_session()
        with self.assertRaises(PermissionDenied):
            att.assert_can_manage_group(self.teacher, foreign.group)


class ObservationAuthorizationTests(_AuthFixture):
    def test_observation_requires_a_shared_group(self):
        with self.assertRaises(PermissionDenied):
            att.create_observation(
                student=self.stranger_student,
                teacher=self.teacher,
                observation_type=ClassroomObservation.ObservationType.NOTE,
                neutral_description="Aloqasiz o'quvchi haqida izoh.",
            )

    def test_observation_for_own_group_student_is_allowed(self):
        observation = att.create_observation(
            student=self.mine_student,
            teacher=self.teacher,
            observation_type=ClassroomObservation.ObservationType.POSITIVE,
            neutral_description="Darsda faol qatnashdi.",
        )
        self.assertEqual(observation.teacher_id, self.teacher.pk)
        self.assertEqual(
            observation.notification_status,
            ClassroomObservation.NotificationStatus.NOT_SENT,
        )

    def test_only_the_recording_teacher_can_edit_or_confirm(self):
        observation = att.create_observation(
            student=self.mine_student,
            teacher=self.teacher,
            observation_type=ClassroomObservation.ObservationType.NOTE,
            neutral_description="Dars jarayonida izoh berildi.",
        )
        with self.assertRaises(PermissionDenied):
            att.update_observation(
                observation, actor=self.other_teacher,
                neutral_description="Boshqa o'qituvchi tahriri.",
            )
        with self.assertRaises(PermissionDenied):
            att.confirm_observation(observation, actor=self.other_teacher)

    def test_short_observation_text_is_rejected(self):
        with self.assertRaises(att.AttendanceError):
            att.create_observation(
                student=self.mine_student,
                teacher=self.teacher,
                observation_type=ClassroomObservation.ObservationType.NOTE,
                neutral_description="ok",
            )


class EssayReportScopingTests(_AuthFixture):
    def _submit(self, *, assignment, student, score=20):
        return EssaySubmission.objects.create(
            student=student,
            topic=self.topic,
            assignment=assignment,
            essay_text="Matn " * 60,
            status=EssaySubmission.Status.GRADED,
            total_score=score,
            max_score=24,
        )

    def test_group_report_excludes_another_groups_assignment_submissions(self):
        """A student in two groups must not surface in the wrong group.

        ``shared_student`` belongs to both groups, but this submission is linked
        to the OTHER group's assignment, so it belongs to that group's report
        only.
        """
        self._submit(assignment=self.foreign_assignment, student=self.shared_student)
        mine = self._submit(assignment=self.my_assignment, student=self.mine_student)

        report = group_reports.group_essay_results(self.group)
        self.assertEqual(report["total"], 1)
        self.assertEqual(
            [row["submission_id"] for row in report["results"]], [mine.pk],
        )
        self.assertNotIn("outside_roster", report["results"][0])

    def test_group_report_returns_nothing_for_an_unrelated_teacher(self):
        self._submit(assignment=self.my_assignment, student=self.mine_student)
        # The other teacher never sees the 9-A report rows.
        foreign_view = group_reports.group_essay_results(self.other_group)
        self.assertEqual(foreign_view["total"], 0)

    def test_assert_group_access_rejects_foreign_groups(self):
        with self.assertRaises(PermissionDenied):
            group_reports.assert_group_access(self.teacher, self.other_group)
        with self.assertRaises(PermissionDenied):
            group_reports.create_assignment(
                topic=self.topic, group=self.other_group, assigned_by=self.teacher,
            )

    def test_teacher_essay_overview_only_covers_owned_groups(self):
        self._submit(assignment=self.my_assignment, student=self.mine_student)
        self._submit(assignment=self.foreign_assignment, student=self.shared_student)
        overview = group_reports.teacher_essay_overview(self.teacher)
        self.assertEqual(
            [row["group_name"] for row in overview["groups"]], ["9-A"],
        )
        self.assertEqual(overview["groups"][0]["graded"], 1)

    def test_teacher_cannot_assign_a_topic_to_another_teachers_group(self):
        other_topic = EssayTopic.objects.create(
            title="Boshqa", description="d", created_by=self.other_teacher,
        )
        with self.assertRaises(PermissionDenied):
            group_reports.create_assignment(
                topic=other_topic, group=self.other_group,
                assigned_by=self.teacher,
            )


class ReportPeriodScopingTests(_AuthFixture):
    def test_student_report_can_be_limited_to_one_group(self):
        session, _ = att.create_session(group=self.group, teacher=self.teacher)
        att.mark(session, self.shared_student, AttendanceRecord.Status.PRESENT,
                 actor=self.teacher)
        foreign, _ = att.create_session(
            group=self.other_group, teacher=self.other_teacher,
        )
        # The student is marked in the foreign register as well; a report scoped
        # to this group must ignore it.
        att.mark(foreign, self.shared_student, AttendanceRecord.Status.ABSENT,
                 actor=self.other_teacher)

        today = timezone.localdate()
        scoped = att.student_attendance_report(
            self.shared_student, start=today - dt.timedelta(days=7),
            end=today + dt.timedelta(days=1), group=self.group,
        )
        self.assertEqual(scoped["present"], 1)
        self.assertEqual(scoped["absent"], 0)

        unscoped = att.student_attendance_report(
            self.shared_student, start=today - dt.timedelta(days=7),
            end=today + dt.timedelta(days=1),
        )
        self.assertEqual(unscoped["marked_records"], 2)
