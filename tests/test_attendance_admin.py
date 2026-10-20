"""Django-admin regressions for the attendance, observation and routing console.

``manage.py check`` only proves the admin *configuration* is syntactically
valid. These tests prove the new screens actually RENDER with real data and that
their permission gates and bulk actions behave the way the operator console
claims:

1. Every screen renders for a platform admin; an unprivileged staff account is
   refused the sensitive ones.
2. ``AttendanceAuditLog`` is a genuinely append-only audit trail: no add, no
   change, no delete — not even for a superuser.
3. The session actions never invent absences: an unfinished register is reported
   as skipped instead of finalized, and recording the unmarked students as
   absent requires the explicitly-named opt-in action.
4. A Telegram destination a teacher typed is never a delivery target until an
   administrator approves it.
5. Confirming a classroom observation persists even when message delivery
   fails, so a transport outage can never lose a teacher's decision.
"""

import datetime as dt
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth.models import Permission
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.attendance.admin import can_manage_attendance
from apps.attendance.models import (
    AttendanceAuditLog,
    AttendanceRecord,
    AttendanceSession,
    ClassroomObservation,
    GroupNotificationDestination,
    NotificationPreference,
)
from apps.attendance.notifications import (
    CATEGORY_ATTENDANCE_SUMMARY,
    destinations_for,
    notify_parents_of_observation,
)
from apps.courses.models import StudentGroup
from apps.notifications.models import NotificationLog

MODELS = {
    "session": AttendanceSession,
    "record": AttendanceRecord,
    "audit": AttendanceAuditLog,
    "observation": ClassroomObservation,
    "destination": GroupNotificationDestination,
    "preference": NotificationPreference,
    "notification_log": NotificationLog,
}


def _admin_url(model: str, view: str, *args) -> str:
    """Reverse an admin URL from the model's own app_label/model_name."""
    opts = MODELS[model]._meta
    name = f"admin:{opts.app_label}_{opts.model_name}_{view}"
    return reverse(name, args=args) if args else reverse(name)


def _request(user, path="/admin/"):
    request = RequestFactory().get(path)
    request.user = user
    return request


def _registered(model):
    return admin.site._registry[model]


class _AdminFixture(TestCase):
    """One group, one register with one marking, and the operator accounts."""

    def setUp(self):
        self.admin = User.objects.create_superuser(
            email="att-admin@example.test",
            password="testpass123",
        )
        self.teacher = User.objects.create_user(
            email="att-teacher@example.test",
            password="testpass123",
            role="teacher",
            first_name="Dilnoza",
            last_name="Rahimova",
        )
        self.ali = User.objects.create_user(
            email="att-ali@example.test",
            password="testpass123",
            role="student",
            first_name="Ali",
            last_name="Valiyev",
        )
        self.zuhra = User.objects.create_user(
            email="att-zuhra@example.test",
            password="testpass123",
            role="student",
            first_name="Zuhra",
            last_name="Karimova",
        )
        self.group = StudentGroup.objects.create(teacher=self.teacher, name="9-A")
        self.group.students.add(self.ali, self.zuhra)

        self.session = AttendanceSession.objects.create(
            group=self.group,
            teacher=self.teacher,
            lesson_date=timezone.localdate(),
            start_time=dt.time(14, 30),
            end_time=dt.time(15, 15),
            title="1-dars",
            created_by=self.teacher,
        )
        # Ali is marked, Zuhra is deliberately left UNMARKED.
        self.record = AttendanceRecord.objects.create(
            session=self.session,
            student=self.ali,
            status=AttendanceRecord.Status.PRESENT,
            marked_by=self.teacher,
        )
        self.client.force_login(self.admin)


# ---------------------------------------------------------------------------
# 1. The screens render
# ---------------------------------------------------------------------------


class AdminScreenRenderingTests(_AdminFixture):
    """Every new console screen renders for a platform admin."""

    def test_every_changelist_renders(self):
        for model in (
            "session",
            "record",
            "audit",
            "observation",
            "destination",
            "preference",
            "notification_log",
        ):
            with self.subTest(model=model):
                response = self.client.get(_admin_url(model, "changelist"))
                self.assertEqual(response.status_code, 200)

    def test_every_add_page_renders(self):
        """The owner must be able to CREATE the operational rows by hand."""
        for model in ("session", "record", "observation", "destination", "preference"):
            with self.subTest(model=model):
                response = self.client.get(_admin_url(model, "add"))
                self.assertEqual(response.status_code, 200)

    def test_every_change_page_renders(self):
        destination = GroupNotificationDestination.objects.create(
            group=self.group,
            chat_id=-1001111111111,
            title="Ota-onalar",
        )
        preference = NotificationPreference.for_user(self.teacher)
        observation = ClassroomObservation.objects.create(
            student=self.ali,
            teacher=self.teacher,
            observation_type=ClassroomObservation.ObservationType.POSITIVE,
            neutral_description="Darsda faol qatnashdi.",
        )
        rows = (
            ("session", self.session.pk),
            ("record", self.record.pk),
            ("observation", observation.pk),
            ("destination", destination.pk),
            ("preference", preference.pk),
        )
        for model, pk in rows:
            with self.subTest(model=model):
                response = self.client.get(_admin_url(model, "change", pk))
                self.assertEqual(response.status_code, 200)

    def test_session_changelist_shows_group_counts_and_local_time(self):
        body = self.client.get(_admin_url("session", "changelist")).content.decode()
        self.assertIn("9-A", body)
        # One of the two students is marked: the roster/marked column.
        self.assertIn("1 / 2", body)
        # The label is Uzbekistan local time, not a naive UTC instant.
        self.assertIn("14:30", body)

    def test_session_change_page_renders_the_register_context(self):
        response = self.client.get(_admin_url("session", "change", self.session.pk))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("1-dars", body)
        # The change page fetches through get_object() -> get_queryset(), so the
        # annotated counts are available there too: 1 of 2 students is marked.
        self.assertIn("1 / 2", body)

    def test_notification_log_lists_the_dedup_key(self):
        NotificationLog.objects.create(
            recipient=self.teacher,
            title="Davomat",
            message="Ali kelmadi",
            notification_type=NotificationLog.NotificationType.ATTENDANCE,
            dedup_key="attendance:9A:2026-01-01:ali",
        )
        body = self.client.get(
            _admin_url("notification_log", "changelist"),
        ).content.decode()
        # The idempotency guard must be inspectable by an operator.
        self.assertIn("attendance:9A:2026-01-01:ali", body)

    def test_list_display_methods_return_real_values(self):
        model_admin = _registered(AttendanceSession)
        self.assertEqual(model_admin.time_label(self.session), "14:30")
        # counts_display reads the changelist annotations, not a per-row query...
        annotated = model_admin.get_queryset(_request(self.admin)).get(
            pk=self.session.pk,
        )
        self.assertEqual(model_admin.counts_display(annotated), "1 / 2")
        # ...and degrades to a plain count outside the changelist.
        self.assertEqual(model_admin.counts_display(self.session), "1 yozuv")
        self.assertEqual(model_admin.time_label(None), "—")
        self.assertEqual(model_admin.counts_display(None), "—")

        record_admin = _registered(AttendanceRecord)
        self.assertEqual(record_admin.group_display(self.record), "9-A")
        self.assertEqual(
            record_admin.lesson_date(self.record),
            self.session.lesson_date,
        )

        destination = GroupNotificationDestination.objects.create(
            chat_id=-1002222222222,
            title="Umumiy",
        )
        destination_admin = _registered(GroupNotificationDestination)
        self.assertEqual(
            destination_admin.group_display(destination),
            "Barcha guruhlar",
        )
        self.assertFalse(destination_admin.is_usable_display(destination))

        observation_admin = _registered(ClassroomObservation)
        self.assertFalse(observation_admin.is_confirmed_display(None))


# ---------------------------------------------------------------------------
# 2. The audit trail is append-only
# ---------------------------------------------------------------------------


class AttendanceAuditAppendOnlyTests(_AdminFixture):
    """The correction audit is evidence: nobody may rewrite or delete it."""

    def setUp(self):
        super().setUp()
        self.audit = AttendanceAuditLog.objects.create(
            session=self.session,
            record=self.record,
            student=self.ali,
            actor=self.teacher,
            field="status",
            old_value="absent",
            new_value="late",
            reason="Tuzatish: darsga kechikdi",
        )

    def test_registered_model_admin_refuses_every_mutation(self):
        model_admin = _registered(AttendanceAuditLog)
        for user in (self.admin, self.teacher):
            request = _request(user)
            with self.subTest(user=user.email):
                self.assertFalse(model_admin.has_add_permission(request))
                self.assertFalse(model_admin.has_change_permission(request))
                self.assertFalse(model_admin.has_delete_permission(request))

    def test_add_and_delete_urls_are_refused_for_an_admin(self):
        self.assertEqual(self.client.get(_admin_url("audit", "add")).status_code, 403)
        self.assertEqual(
            self.client.get(
                _admin_url("audit", "delete", self.audit.pk),
            ).status_code,
            403,
        )

    def test_a_post_to_the_change_url_cannot_rewrite_a_row(self):
        response = self.client.post(
            _admin_url("audit", "change", self.audit.pk),
            {"field": "status", "old_value": "present", "new_value": "present"},
        )
        # No change permission -> Django refuses the write before any form runs.
        self.assertEqual(response.status_code, 403)
        self.audit.refresh_from_db()
        self.assertEqual(self.audit.old_value, "absent")
        self.assertEqual(self.audit.new_value, "late")

    def test_the_trail_is_still_readable(self):
        response = self.client.get(_admin_url("audit", "change", self.audit.pk))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("Tuzatish: darsga kechikdi", body)
        # The readonly cells render the recorded transition verbatim.
        self.assertIn(">absent<", body)
        self.assertIn(">late<", body)

    def test_audit_changelist_renders_the_transition(self):
        body = self.client.get(_admin_url("audit", "changelist")).content.decode()
        self.assertIn("Tuzatish: darsga kechikdi", body)


# ---------------------------------------------------------------------------
# 3. Permission gates
# ---------------------------------------------------------------------------


class UnprivilegedStaffGateTests(_AdminFixture):
    """Django staff is not a platform administrator.

    ``is_staff`` opens the admin site; it must not open the attendance console,
    the observation notes, the notification routing or the preference switches.
    """

    def setUp(self):
        super().setUp()
        self.staff = User.objects.create_user(
            email="att-staff@example.test",
            password="testpass123",
            role="teacher",
        )
        self.staff.is_staff = True
        self.staff.save(update_fields=["is_staff"])
        self.client.force_login(self.staff)

    def test_staff_cannot_open_the_sensitive_screens(self):
        for model in (
            "session",
            "record",
            "audit",
            "observation",
            "destination",
            "preference",
        ):
            with self.subTest(model=model):
                self.assertEqual(
                    self.client.get(_admin_url(model, "changelist")).status_code,
                    403,
                )
                self.assertEqual(
                    self.client.get(_admin_url(model, "add")).status_code,
                    403,
                )

    def test_gate_helper_refuses_staff_without_the_permission(self):
        self.assertFalse(can_manage_attendance(self.staff))
        self.assertFalse(can_manage_attendance(self.teacher))
        self.assertFalse(can_manage_attendance(None))
        self.assertTrue(can_manage_attendance(self.admin))

    def test_a_delegated_permission_opens_the_console(self):
        """The documented policy: an explicitly granted permission is enough."""
        self.staff.user_permissions.add(
            Permission.objects.get(
                codename="change_attendancesession",
                content_type__app_label="attendance",
            )
        )
        self.staff = User.objects.get(pk=self.staff.pk)
        self.assertTrue(can_manage_attendance(self.staff))
        self.assertEqual(
            self.client.get(_admin_url("session", "changelist")).status_code,
            200,
        )


# ---------------------------------------------------------------------------
# 4. Session bulk actions
# ---------------------------------------------------------------------------


class SessionAdminActionTests(_AdminFixture):
    """Actions never invent absences and never rewrite a finished register."""

    def _post_action(self, action, pks):
        return self.client.post(
            _admin_url("session", "changelist"),
            {"action": action, "_selected_action": pks},
            follow=True,
        )

    def test_finalize_skips_a_register_with_unmarked_students(self):
        response = self._post_action("finalize_selected", [self.session.pk])
        self.assertEqual(response.status_code, 200)

        self.session.refresh_from_db()
        # The unfinished register must stay a draft...
        self.assertEqual(self.session.status, AttendanceSession.Status.DRAFT)
        self.assertIsNone(self.session.finalized_at)
        # ...Zuhra must NOT have been invented as absent...
        self.assertFalse(
            AttendanceRecord.objects.filter(
                session=self.session,
                student=self.zuhra,
            ).exists()
        )
        # ...and the operator is told why.
        self.assertIn("belgilanmagan", response.content.decode())

    def test_the_explicit_opt_in_action_records_only_the_unmarked_as_absent(self):
        response = self._post_action(
            "finalize_selected_marking_unmarked_absent",
            [self.session.pk],
        )
        self.assertEqual(response.status_code, 200)

        self.session.refresh_from_db()
        self.assertEqual(self.session.status, AttendanceSession.Status.FINALIZED)
        self.assertIsNotNone(self.session.finalized_at)
        self.assertEqual(self.session.finalized_by, self.admin)
        # Ali keeps the marking he actually got; only Zuhra becomes ABSENT.
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, AttendanceRecord.Status.PRESENT)
        absent = AttendanceRecord.objects.get(session=self.session, student=self.zuhra)
        self.assertEqual(absent.status, AttendanceRecord.Status.ABSENT)

    def test_cancel_never_touches_a_finalized_register(self):
        draft = AttendanceSession.objects.create(
            group=self.group,
            teacher=self.teacher,
            lesson_date=timezone.localdate(),
            start_time=dt.time(16, 0),
            created_by=self.teacher,
        )
        finalized = AttendanceSession.objects.create(
            group=self.group,
            teacher=self.teacher,
            lesson_date=timezone.localdate(),
            start_time=dt.time(17, 0),
            status=AttendanceSession.Status.FINALIZED,
            finalized_at=timezone.now(),
            finalized_by=self.admin,
            created_by=self.teacher,
        )

        response = self._post_action("cancel_selected", [draft.pk, finalized.pk])
        self.assertEqual(response.status_code, 200)

        draft.refresh_from_db()
        finalized.refresh_from_db()
        self.assertEqual(draft.status, AttendanceSession.Status.CANCELLED)
        self.assertEqual(finalized.status, AttendanceSession.Status.FINALIZED)

    def test_an_already_finalized_register_is_left_alone(self):
        self.session.status = AttendanceSession.Status.FINALIZED
        self.session.finalized_at = timezone.now()
        self.session.save(update_fields=["status", "finalized_at"])

        response = self._post_action("finalize_selected", [self.session.pk])
        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, AttendanceSession.Status.FINALIZED)
        # Zuhra was unmarked before and must remain unmarked afterwards.
        self.assertFalse(
            AttendanceRecord.objects.filter(
                session=self.session,
                student=self.zuhra,
            ).exists()
        )

    def test_an_ordinary_teacher_cannot_run_the_actions(self):
        """No privilege escalation: the actions are gated on the change permission."""
        self.client.force_login(self.teacher)
        self.assertEqual(
            self.client.get(_admin_url("session", "changelist")).status_code,
            302,  # a non-staff teacher is redirected to the admin login
        )
        model_admin = _registered(AttendanceSession)
        self.assertEqual(model_admin.get_actions(_request(self.teacher)), {})
        self.assertIn(
            "finalize_selected",
            model_admin.get_actions(_request(self.admin)),
        )


# ---------------------------------------------------------------------------
# 5. Notification destination approval
# ---------------------------------------------------------------------------


class DestinationApprovalGateTests(_AdminFixture):
    """A chat id typed by a teacher is NEVER a delivery target until approved."""

    def setUp(self):
        super().setUp()
        self.destination = GroupNotificationDestination.objects.create(
            group=self.group,
            chat_id=-1009988776655,
            title="9-A ota-onalar",
            destination_type=GroupNotificationDestination.DestinationType.PARENT_PUBLIC,
            allowed_categories=[CATEGORY_ATTENDANCE_SUMMARY],
        )

    def test_an_unapproved_destination_is_not_usable_and_not_used(self):
        self.assertFalse(self.destination.is_usable)
        self.assertFalse(self.destination.accepts(CATEGORY_ATTENDANCE_SUMMARY))
        self.assertEqual(destinations_for(self.group, CATEGORY_ATTENDANCE_SUMMARY), [])

    def test_approve_action_makes_the_destination_usable(self):
        response = self.client.post(
            _admin_url("destination", "changelist"),
            {"action": "approve_selected", "_selected_action": [self.destination.pk]},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        self.destination.refresh_from_db()
        self.assertTrue(self.destination.is_approved)
        self.assertTrue(self.destination.is_usable)
        # An approval must always be attributable to a named administrator.
        self.assertEqual(self.destination.approved_by, self.admin)
        self.assertIsNotNone(self.destination.approved_at)
        self.assertTrue(self.destination.accepts(CATEGORY_ATTENDANCE_SUMMARY))
        self.assertIn(
            self.destination.pk,
            [d.pk for d in destinations_for(self.group, CATEGORY_ATTENDANCE_SUMMARY)],
        )

    def test_a_category_outside_the_allow_list_is_never_delivered(self):
        self.client.post(
            _admin_url("destination", "changelist"),
            {"action": "approve_selected", "_selected_action": [self.destination.pk]},
            follow=True,
        )
        self.destination.refresh_from_db()
        self.assertFalse(self.destination.accepts("student_observation"))
        self.assertEqual(destinations_for(self.group, "student_observation"), [])

    def test_revoke_action_stops_delivery(self):
        self.client.post(
            _admin_url("destination", "changelist"),
            {"action": "approve_selected", "_selected_action": [self.destination.pk]},
            follow=True,
        )
        response = self.client.post(
            _admin_url("destination", "changelist"),
            {"action": "revoke_selected", "_selected_action": [self.destination.pk]},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        self.destination.refresh_from_db()
        self.assertFalse(self.destination.is_approved)
        self.assertFalse(self.destination.is_usable)
        self.assertIsNone(self.destination.approved_by_id)
        self.assertIsNone(self.destination.approved_at)
        self.assertEqual(destinations_for(self.group, CATEGORY_ATTENDANCE_SUMMARY), [])

    def test_disabling_an_approved_destination_also_stops_delivery(self):
        self.destination.is_approved = True
        self.destination.approved_by = self.admin
        self.destination.approved_at = timezone.now()
        self.destination.is_enabled = False
        self.destination.save()
        self.assertFalse(self.destination.is_usable)
        self.assertEqual(destinations_for(self.group, CATEGORY_ATTENDANCE_SUMMARY), [])

    def test_saving_an_approval_through_the_form_stamps_the_approver(self):
        """The form's approver fields are read-only, so saving must stamp them."""
        model_admin = _registered(GroupNotificationDestination)
        obj = GroupNotificationDestination.objects.get(pk=self.destination.pk)
        obj.is_approved = True
        model_admin.save_model(_request(self.admin), obj, form=None, change=True)
        obj.refresh_from_db()
        self.assertEqual(obj.approved_by, self.admin)
        self.assertIsNotNone(obj.approved_at)

    def test_an_ordinary_teacher_cannot_approve_a_destination(self):
        model_admin = _registered(GroupNotificationDestination)
        self.assertFalse(model_admin.has_add_permission(_request(self.teacher)))
        self.assertFalse(model_admin.has_change_permission(_request(self.teacher)))
        self.assertEqual(model_admin.get_actions(_request(self.teacher)), {})


# ---------------------------------------------------------------------------
# 6. Observation confirmation
# ---------------------------------------------------------------------------


class ObservationConfirmationActionTests(_AdminFixture):
    """An observation is a neutral note; nothing reaches a parent unconfirmed."""

    def setUp(self):
        super().setUp()
        self.observation = ClassroomObservation.objects.create(
            student=self.ali,
            session=self.session,
            teacher=self.teacher,
            observation_type=ClassroomObservation.ObservationType.PARTICIPATION,
            neutral_description="Darsda faol qatnashmadi, qo'shimcha mashq kerak.",
        )

    def _post_action(self, action):
        return self.client.post(
            _admin_url("observation", "changelist"),
            {"action": action, "_selected_action": [self.observation.pk]},
            follow=True,
        )

    def test_an_unconfirmed_observation_is_never_delivered(self):
        """The delivery path re-checks confirmation, so a retry cannot leak."""
        self.observation.refresh_from_db()
        self.assertIsNone(self.observation.confirmed_at)
        with self.assertRaises(ValueError):
            notify_parents_of_observation(self.observation)

    def test_confirm_without_sending_marks_the_observation_skipped(self):
        response = self._post_action("confirm_without_sending_selected")
        self.assertEqual(response.status_code, 200)

        self.observation.refresh_from_db()
        self.assertIsNotNone(self.observation.confirmed_at)
        self.assertEqual(self.observation.confirmed_by, self.admin)
        self.assertEqual(
            self.observation.notification_status,
            ClassroomObservation.NotificationStatus.SKIPPED,
        )
        self.assertIsNone(self.observation.sent_at)

    def test_a_delivery_failure_never_rolls_back_the_confirmation(self):
        """A Telegram outage must not lose the teacher's confirmed decision."""
        with patch(
            "apps.attendance.notifications.notify_parents_of_observation",
            side_effect=RuntimeError("telegram transport is down"),
        ):
            response = self._post_action("confirm_and_send_selected")
        self.assertEqual(response.status_code, 200)

        self.observation.refresh_from_db()
        self.assertIsNotNone(self.observation.confirmed_at)
        self.assertEqual(self.observation.confirmed_by, self.admin)
        self.assertEqual(
            self.observation.notification_status,
            ClassroomObservation.NotificationStatus.PENDING_CONFIRMATION,
        )

    def test_confirming_a_second_time_is_idempotent(self):
        self._post_action("confirm_without_sending_selected")
        first_confirmed_at = ClassroomObservation.objects.get(
            pk=self.observation.pk,
        ).confirmed_at

        response = self._post_action("confirm_without_sending_selected")
        self.assertEqual(response.status_code, 200)
        self.observation.refresh_from_db()
        self.assertIsNotNone(self.observation.confirmed_at)
        self.assertGreaterEqual(self.observation.confirmed_at, first_confirmed_at)

    def test_confirmation_requires_more_than_the_attendance_permission(self):
        """A staffer delegated only attendance rights is not offered this action.

        The observation actions are gated on the observation model's own change
        permission, so delegating attendance can never delegate behavioural
        notes about students.
        """
        staff = User.objects.create_user(
            email="att-staff2@example.test",
            password="testpass123",
            role="teacher",
        )
        staff.is_staff = True
        staff.user_permissions.add(
            Permission.objects.get(
                codename="change_attendancesession",
                content_type__app_label="attendance",
            )
        )
        staff.save(update_fields=["is_staff"])
        staff = User.objects.get(pk=staff.pk)

        model_admin = _registered(ClassroomObservation)
        self.assertNotIn(
            "confirm_and_send_selected", model_admin.get_actions(_request(staff))
        )
        self.assertIn(
            "confirm_and_send_selected",
            model_admin.get_actions(_request(self.admin)),
        )
        self.assertFalse(model_admin.has_change_permission(_request(staff)))
        self.assertTrue(model_admin.has_change_permission(_request(self.admin)))
