"""Parent and group notification privacy, consent and idempotency.

The privacy contract these tests pin down:

* A named child's attendance detail goes ONLY to an approved, Telegram-verified
  parent in a private chat — never into a group.
* A shared/group destination receives aggregate counts with no student names,
  and only when an administrator has approved it.
* A replayed event (Telegram redelivery, Celery retry) never sends twice.
* A classroom observation is not deliverable until the recording teacher
  confirms it.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import ParentStudentLink, User
from apps.attendance import notifications as att_notifications
from apps.attendance import services as att
from apps.attendance.models import (
    AttendanceRecord,
    ClassroomObservation,
    GroupNotificationDestination,
    NotificationPreference,
)
from apps.attendance.notifications import CATEGORY_ATTENDANCE_SUMMARY
from apps.courses.models import StudentGroup

TOKEN = "123456:TEST-TOKEN"
SEND_PATH = "apps.attendance.notifications.TelegramService._send_message"
OK = {"success": True, "message_id": 1, "error": None}


class _NotificationFixture(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            email="an-teacher@example.test", password="testpass123", role="teacher",
        )
        self.student = User.objects.create_user(
            email="an-student@example.test", password="testpass123", role="student",
            first_name="Ali", last_name="Valiyev",
        )
        self.other_student = User.objects.create_user(
            email="an-student2@example.test", password="testpass123", role="student",
            first_name="Zuhra", last_name="Karimova",
        )
        self.group = StudentGroup.objects.create(teacher=self.teacher, name="9-A")
        self.group.students.add(self.student, self.other_student)

    def _parent(self, email="an-parent@example.test", **kwargs):
        defaults = {
            "telegram_chat_id": 500001,
            "telegram_identity_verified_at": timezone.now(),
        }
        defaults.update(kwargs)
        return User.objects.create_user(
            email=email, password="testpass123", role="parent", **defaults,
        )

    def _approve(self, parent, student=None):
        return ParentStudentLink.objects.create(
            parent=parent, student=student or self.student, is_approved=True,
        )

    def _session_with(self, status=AttendanceRecord.Status.LATE, student=None,
                     late_minutes=12):
        session, _ = att.create_session(group=self.group, teacher=self.teacher)
        record = att.mark(
            session, student or self.student, status,
            late_minutes=late_minutes, actor=self.teacher,
        )
        return session, record


@override_settings(TELEGRAM_BOT_TOKEN=TOKEN)
class ParentNotificationTests(_NotificationFixture):
    @patch(SEND_PATH)
    def test_verified_approved_parent_gets_one_private_message(self, mock_send):
        mock_send.return_value = OK
        parent = self._parent()
        self._approve(parent)
        _session, record = self._session_with()

        result = att_notifications.notify_parents_of_record(record)
        self.assertEqual(result["sent"], 1)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(mock_send.call_count, 1)

        kwargs = mock_send.call_args.kwargs
        self.assertEqual(kwargs["chat_id"], parent.telegram_chat_id)
        self.assertIn("Kechikdi", kwargs["text"])
        self.assertIn("12 daqiqa", kwargs["text"])
        self.assertIn("9-A", kwargs["text"])

    @patch(SEND_PATH)
    def test_replayed_event_is_not_sent_twice(self, mock_send):
        mock_send.return_value = OK
        self._approve(self._parent())
        _session, record = self._session_with()

        att_notifications.notify_parents_of_record(record)
        second = att_notifications.notify_parents_of_record(record)

        self.assertEqual(second["sent"], 0)
        self.assertEqual(second["duplicates"], 1)
        self.assertEqual(mock_send.call_count, 1)

    @patch(SEND_PATH)
    def test_correction_notification_is_a_distinct_message(self, mock_send):
        mock_send.return_value = OK
        self._approve(self._parent())
        _session, record = self._session_with()

        att_notifications.notify_parents_of_record(record)
        att.mark(record.session, self.student, AttendanceRecord.Status.PRESENT,
                 actor=self.teacher)
        record.refresh_from_db()
        correction = att_notifications.notify_parents_of_record(
            record, is_correction=True,
        )
        self.assertEqual(correction["sent"], 1)
        self.assertEqual(mock_send.call_count, 2)
        self.assertIn("tuzatilgan", mock_send.call_args.kwargs["text"])
        self.assertIn("Keldi", mock_send.call_args.kwargs["text"])

    @patch(SEND_PATH)
    def test_unapproved_link_discloses_nothing(self, mock_send):
        mock_send.return_value = OK
        parent = self._parent()
        ParentStudentLink.objects.create(
            parent=parent, student=self.student, is_approved=False,
        )
        _session, record = self._session_with()

        result = att_notifications.notify_parents_of_record(record)
        self.assertEqual(result["sent"], 0)
        self.assertNotIn(parent, att_notifications._parents_for(self.student))
        mock_send.assert_not_called()

    @patch(SEND_PATH)
    def test_unverified_telegram_identity_receives_nothing(self, mock_send):
        """A legacy numeric link without verified provenance is not enough."""
        mock_send.return_value = OK
        parent = self._parent(telegram_chat_id=500009)
        self._approve(parent)
        User.objects.filter(pk=parent.pk).update(telegram_identity_verified_at=None)
        _session, record = self._session_with()

        result = att_notifications.notify_parents_of_record(record)
        self.assertEqual(result["sent"], 0)
        mock_send.assert_not_called()

    @patch(SEND_PATH)
    def test_parent_without_telegram_link_receives_nothing(self, mock_send):
        mock_send.return_value = OK
        parent = self._parent(telegram_chat_id=None)
        self._approve(parent)
        _session, record = self._session_with()
        result = att_notifications.notify_parents_of_record(record)
        self.assertEqual(result["sent"], 0)
        mock_send.assert_not_called()

    @patch(SEND_PATH)
    def test_unrelated_parent_never_receives_another_childs_data(self, mock_send):
        mock_send.return_value = OK
        stranger = self._parent(email="an-stranger@example.test",
                                telegram_chat_id=500777)
        self._approve(stranger, student=self.other_student)
        _session, record = self._session_with(student=self.student)

        result = att_notifications.notify_parents_of_record(record)
        self.assertEqual(result["sent"], 0)
        mock_send.assert_not_called()

    @patch(SEND_PATH)
    def test_preference_opt_out_suppresses_attendance_messages(self, mock_send):
        mock_send.return_value = OK
        parent = self._parent()
        self._approve(parent)
        NotificationPreference.objects.create(
            user=parent, attendance_alerts=False,
        )
        _session, record = self._session_with()
        result = att_notifications.notify_parents_of_record(record)
        self.assertEqual(result["sent"], 0)
        mock_send.assert_not_called()

    @patch(SEND_PATH)
    def test_global_telegram_opt_out_suppresses_everything(self, mock_send):
        mock_send.return_value = OK
        parent = self._parent()
        self._approve(parent)
        NotificationPreference.objects.create(user=parent, telegram_enabled=False)
        _session, record = self._session_with()
        self.assertEqual(att_notifications.notify_parents_of_record(record)["sent"], 0)
        mock_send.assert_not_called()

    @patch(SEND_PATH)
    def test_session_notification_reports_every_record(self, mock_send):
        mock_send.return_value = OK
        parent = self._parent()
        self._approve(parent)
        parent_two = self._parent(email="an-parent2@example.test",
                                  telegram_chat_id=500002)
        self._approve(parent_two, student=self.other_student)
        session, _record = self._session_with()
        att.mark(session, self.other_student, AttendanceRecord.Status.ABSENT,
                 actor=self.teacher)

        result = att_notifications.notify_parents_of_session(session)
        self.assertEqual(result["records"], 2)
        self.assertEqual(result["sent"], 2)
        self.assertEqual(mock_send.call_count, 2)


@override_settings(TELEGRAM_BOT_TOKEN=TOKEN)
class GroupDestinationTests(_NotificationFixture):
    def _approved_destination(self, *, chat_id=-100123, categories=None):
        return GroupNotificationDestination.objects.create(
            group=self.group,
            chat_id=chat_id,
            destination_type=GroupNotificationDestination.DestinationType.PARENT_PUBLIC,
            is_approved=True,
            approved_by=self.teacher,
            approved_at=timezone.now(),
            allowed_categories=categories or [CATEGORY_ATTENDANCE_SUMMARY],
        )

    def _finalize_both(self, session):
        """Mark the second student too, so the register can actually finalize."""
        att.mark(session, self.other_student, AttendanceRecord.Status.PRESENT,
                 actor=self.teacher)
        return att.finalize(session, actor=self.teacher)

    @patch(SEND_PATH)
    def test_unapproved_destination_receives_nothing(self, mock_send):
        mock_send.return_value = OK
        GroupNotificationDestination.objects.create(
            group=self.group, chat_id=-100999,
            destination_type=GroupNotificationDestination.DestinationType.PARENT_PUBLIC,
            is_approved=False,
            allowed_categories=[CATEGORY_ATTENDANCE_SUMMARY],
        )
        session, _ = self._session_with(
            status=AttendanceRecord.Status.ABSENT, late_minutes=0,
        )
        self._finalize_both(session)

        result = att_notifications.send_group_attendance_summary(session)
        self.assertEqual(result["sent"], 0)
        self.assertEqual(
            att_notifications.destinations_for(self.group, CATEGORY_ATTENDANCE_SUMMARY),
            [],
        )
        mock_send.assert_not_called()

    @patch(SEND_PATH)
    def test_disabled_destination_receives_nothing(self, mock_send):
        mock_send.return_value = OK
        destination = self._approved_destination()
        GroupNotificationDestination.objects.filter(pk=destination.pk).update(
            is_enabled=False,
        )
        session, _ = self._session_with(
            status=AttendanceRecord.Status.ABSENT, late_minutes=0,
        )
        self._finalize_both(session)
        self.assertEqual(
            att_notifications.send_group_attendance_summary(session)["sent"], 0,
        )
        mock_send.assert_not_called()

    @patch(SEND_PATH)
    def test_group_summary_is_aggregate_only_and_never_names_a_student(self, mock_send):
        mock_send.return_value = OK
        self._approved_destination()
        session, _ = self._session_with(
            status=AttendanceRecord.Status.ABSENT, late_minutes=0,
        )
        self._finalize_both(session)

        result = att_notifications.send_group_attendance_summary(session)
        self.assertEqual(result["sent"], 1)
        text = mock_send.call_args.kwargs["text"]
        self.assertNotIn("Ali", text)
        self.assertNotIn("Valiyev", text)
        self.assertNotIn(self.student.email, text)
        self.assertIn("9-A", text)
        self.assertIn("2 o'quvchidan", text)
        self.assertIn("1 nafari kelmadi", text)

    @patch(SEND_PATH)
    def test_group_summary_is_not_sent_twice(self, mock_send):
        mock_send.return_value = OK
        self._approved_destination()
        session, _ = self._session_with(
            status=AttendanceRecord.Status.ABSENT, late_minutes=0,
        )
        self._finalize_both(session)

        att_notifications.send_group_attendance_summary(session)
        second = att_notifications.send_group_attendance_summary(session)
        self.assertEqual(second["duplicates"], 1)
        self.assertEqual(mock_send.call_count, 1)

    @patch(SEND_PATH)
    def test_destination_category_subscription_is_respected(self, mock_send):
        mock_send.return_value = OK
        self._approved_destination(categories=["some_other_category"])
        session, _ = self._session_with(
            status=AttendanceRecord.Status.ABSENT, late_minutes=0,
        )
        self._finalize_both(session)
        self.assertEqual(
            att_notifications.send_group_attendance_summary(session)["sent"], 0,
        )
        mock_send.assert_not_called()

    @patch(SEND_PATH)
    def test_global_destination_applies_to_every_group(self, mock_send):
        mock_send.return_value = OK
        GroupNotificationDestination.objects.create(
            group=None, chat_id=-100555,
            destination_type=GroupNotificationDestination.DestinationType.STAFF,
            is_approved=True, allowed_categories=[CATEGORY_ATTENDANCE_SUMMARY],
        )
        session, _ = self._session_with(
            status=AttendanceRecord.Status.ABSENT, late_minutes=0,
        )
        self._finalize_both(session)
        self.assertEqual(
            att_notifications.send_group_attendance_summary(session)["sent"], 1,
        )


@override_settings(TELEGRAM_BOT_TOKEN=TOKEN)
class ObservationNotificationTests(_NotificationFixture):
    @patch(SEND_PATH)
    def test_unconfirmed_observation_cannot_be_delivered(self, mock_send):
        mock_send.return_value = OK
        self._approve(self._parent())
        observation = att.create_observation(
            student=self.student,
            teacher=self.teacher,
            observation_type=ClassroomObservation.ObservationType.PARTICIPATION,
            neutral_description="Darsda faollik yetarli emas edi.",
        )
        with self.assertRaises(ValueError):
            att_notifications.notify_parents_of_observation(observation)
        mock_send.assert_not_called()

    @patch(SEND_PATH)
    def test_confirmed_observation_notifies_parents_once(self, mock_send):
        mock_send.return_value = OK
        self._approve(self._parent())
        observation = att.create_observation(
            student=self.student,
            teacher=self.teacher,
            observation_type=ClassroomObservation.ObservationType.RULES,
            neutral_description="Sinf qoidalari eslatildi.",
        )
        att.confirm_observation(observation, actor=self.teacher, send=True)
        observation.refresh_from_db()

        first = att_notifications.notify_parents_of_observation(observation)
        self.assertEqual(first["sent"], 1)
        text = mock_send.call_args.kwargs["text"]
        self.assertIn("Sinf qoidalari eslatmasi", text)
        self.assertIn("Sinf qoidalari eslatildi.", text)

        observation.refresh_from_db()
        self.assertEqual(observation.notification_status,
                         ClassroomObservation.NotificationStatus.SENT)
        self.assertIsNotNone(observation.sent_at)

    @patch(SEND_PATH)
    def test_declining_to_send_marks_observation_skipped(self, mock_send):
        mock_send.return_value = OK
        self._approve(self._parent())
        observation = att.create_observation(
            student=self.student,
            teacher=self.teacher,
            observation_type=ClassroomObservation.ObservationType.NOTE,
            neutral_description="Umumiy kuzatuv izohi.",
        )
        att.confirm_observation(observation, actor=self.teacher, send=False)
        observation.refresh_from_db()
        self.assertEqual(
            observation.notification_status,
            ClassroomObservation.NotificationStatus.SKIPPED,
        )
        mock_send.assert_not_called()

    @patch(SEND_PATH)
    def test_observation_preference_opt_out_is_respected(self, mock_send):
        mock_send.return_value = OK
        parent = self._parent()
        self._approve(parent)
        NotificationPreference.objects.create(user=parent, observation_alerts=False)
        observation = att.create_observation(
            student=self.student,
            teacher=self.teacher,
            observation_type=ClassroomObservation.ObservationType.NOTE,
            neutral_description="Umumiy kuzatuv izohi.",
        )
        att.confirm_observation(observation, actor=self.teacher, send=True)
        result = att_notifications.notify_parents_of_observation(observation)
        self.assertEqual(result["sent"], 0)
        mock_send.assert_not_called()


@override_settings(TELEGRAM_BOT_TOKEN=TOKEN)
class TeacherAndEssayNotificationTests(_NotificationFixture):
    def _teacher_with_telegram(self):
        return User.objects.create_user(
            email="an-tg-teacher@example.test", password="testpass123",
            role="teacher", telegram_chat_id=600001,
            telegram_identity_verified_at=timezone.now(),
        )

    @patch(SEND_PATH)
    def test_notify_teacher_requires_a_linked_and_verified_account(self, mock_send):
        mock_send.return_value = OK
        unlinked = self.teacher
        result = att_notifications.notify_teacher(
            teacher=unlinked, text="Salom", dedup_key="t-1",
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "teacher not linked")
        mock_send.assert_not_called()

        linked = self._teacher_with_telegram()
        User.objects.filter(pk=linked.pk).update(telegram_identity_verified_at=None)
        linked.refresh_from_db()
        unverified = att_notifications.notify_teacher(
            teacher=linked, text="Salom", dedup_key="t-2",
        )
        self.assertFalse(unverified["success"])
        self.assertEqual(unverified["error"], "teacher unverified")
        mock_send.assert_not_called()

    @patch(SEND_PATH)
    def test_notify_teacher_is_deduplicated(self, mock_send):
        mock_send.return_value = OK
        teacher = self._teacher_with_telegram()
        att_notifications.notify_teacher(
            teacher=teacher, text="Xabar", dedup_key="dedup-teacher",
        )
        second = att_notifications.notify_teacher(
            teacher=teacher, text="Xabar", dedup_key="dedup-teacher",
        )
        self.assertTrue(second["duplicate"])
        self.assertEqual(mock_send.call_count, 1)

    @patch(SEND_PATH)
    def test_essay_submission_notification_reaches_only_the_owning_teacher(self, mock_send):
        from apps.essays.models import EssayAssignment, EssaySubmission, EssayTopic

        mock_send.return_value = OK
        teacher = self._teacher_with_telegram()
        self.group.teacher = teacher
        self.group.save(update_fields=["teacher", "updated_at"])
        topic = EssayTopic.objects.create(
            title="Kitobxonlik", description="d", created_by=teacher,
        )
        assignment = EssayAssignment.objects.create(
            topic=topic, group=self.group, assigned_by=teacher,
        )
        submission = EssaySubmission.objects.create(
            student=self.student, topic=topic, assignment=assignment,
            essay_text="Matn " * 60, status=EssaySubmission.Status.PENDING,
        )

        result = att_notifications.notify_teachers_of_submission(submission)
        self.assertEqual(result["sent"], 1)
        text = mock_send.call_args.kwargs["text"]
        self.assertIn("Yangi esse topshirildi", text)
        self.assertIn("9-A", text)

        second = att_notifications.notify_teachers_of_submission(submission)
        self.assertEqual(second["duplicates"], 1)
        self.assertEqual(mock_send.call_count, 1)

    @patch(SEND_PATH)
    def test_unassigned_essay_notifies_no_teacher(self, mock_send):
        from apps.essays.models import EssaySubmission

        mock_send.return_value = OK
        submission = EssaySubmission.objects.create(
            student=self.student, topic=None, essay_text="Matn " * 60,
            status=EssaySubmission.Status.PENDING,
        )
        result = att_notifications.notify_teachers_of_submission(submission)
        self.assertTrue(result["skipped"])
        mock_send.assert_not_called()

    @patch(SEND_PATH)
    def test_graded_essay_notifies_student_and_parent_privately(self, mock_send):
        from apps.essays.models import EssaySubmission, EssayTopic

        mock_send.return_value = OK
        student = User.objects.create_user(
            email="an-tg-student@example.test", password="testpass123",
            role="student", telegram_chat_id=700001,
            telegram_identity_verified_at=timezone.now(),
        )
        parent = self._parent(email="an-parent-g@example.test",
                              telegram_chat_id=700002)
        self._approve(parent, student=student)
        topic = EssayTopic.objects.create(
            title="Tabiat", description="d", created_by=self.teacher,
        )
        submission = EssaySubmission.objects.create(
            student=student, topic=topic, essay_text="Matn " * 60,
            status=EssaySubmission.Status.GRADED, total_score=18, max_score=24,
        )

        result = att_notifications.notify_student_essay_graded(submission)
        self.assertEqual(result["sent"], 2)
        self.assertEqual(mock_send.call_count, 2)
        chat_ids = {call.kwargs["chat_id"] for call in mock_send.call_args_list}
        self.assertEqual(chat_ids, {700001, 700002})

        again = att_notifications.notify_student_essay_graded(submission)
        self.assertEqual(again["sent"], 0)
        self.assertEqual(again["duplicates"], 2)
        self.assertEqual(mock_send.call_count, 2)

    @patch(SEND_PATH)
    def test_group_summary_text_contains_no_identity_fields(self, mock_send):
        mock_send.return_value = OK
        session, _ = self._session_with(
            status=AttendanceRecord.Status.ABSENT, late_minutes=0,
        )
        text = att_notifications.group_summary_text(session)
        self.assertNotIn("Ali", text)
        self.assertNotIn("Valiyev", text)
        self.assertNotIn("Ali Valiyev", text)
        self.assertIn("9-A", text)
