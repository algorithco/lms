"""HTTP contract and authorization regressions for the attendance/report API.

The React teacher panel talks to ``/api/v1/school/...`` and nothing else, so
these tests pin down three things the service-level tests cannot:

1. **The register flow over HTTP** — create, mark, mark-all-present, finalize,
   including the fact that an unfinished register is refused (409) instead of
   being silently recorded as a full absence.
2. **The 409 body is a client contract.** The panel parses ``reason`` and
   ``unmarked`` out of it; a top-level ``detail`` string would make the
   actionable list unreachable and degrade the UI to a generic message.
3. **Scoping.** Every response is filtered to the caller's own groups. A
   foreign id must be rejected *without* confirming that it exists, and the
   response body must not leak a group name, a roster size or a student name.

Status codes below are the ones the views actually return: ``_scoped_group()``
answers 400 for a group the caller does not own, the session helpers answer 403
for a foreign session id, and object lookups answer 404.
"""

import datetime as dt
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import ParentStudentLink, User
from apps.attendance.models import (
    AttendanceRecord,
    AttendanceSession,
    ClassroomObservation,
    GroupNotificationDestination,
    NotificationPreference,
)
from apps.courses.models import StudentGroup
from apps.essays.models import EssayAssignment, EssaySubmission, EssayTopic

TELEGRAM_TOKEN = "123456:TEST-TOKEN"


class _AttendanceApiFixture(TestCase):
    """Two teachers, one shared student, one foreign group, one verified parent."""

    def setUp(self):
        self.teacher = User.objects.create_user(
            email="api-teacher@example.test",
            password="testpass123",
            role="teacher",
            first_name="Oqituvchi",
            last_name="Birinchi",
        )
        self.other_teacher = User.objects.create_user(
            email="api-other@example.test",
            password="testpass123",
            role="teacher",
            first_name="Oqituvchi",
            last_name="Ikkinchi",
        )
        self.admin = User.objects.create_superuser(
            email="api-admin@example.test",
            password="testpass123",
            role="admin",
        )
        self.ali = User.objects.create_user(
            email="api-ali@example.test",
            password="testpass123",
            role="student",
            first_name="Ali",
            last_name="Valiyev",
        )
        self.zuhra = User.objects.create_user(
            email="api-zuhra@example.test",
            password="testpass123",
            role="student",
            first_name="Zuhra",
            last_name="Karimova",
        )
        self.outsider = User.objects.create_user(
            email="api-outsider@example.test",
            password="testpass123",
            role="student",
            first_name="Gulnora",
            last_name="Yusupova",
        )
        self.parent = User.objects.create_user(
            email="api-parent@example.test",
            password="testpass123",
            role="parent",
            first_name="Ota",
            last_name="Onaev",
            telegram_chat_id=555000111,
            telegram_identity_verified_at=timezone.now(),
        )
        self.other_parent = User.objects.create_user(
            email="api-other-parent@example.test",
            password="testpass123",
            role="parent",
            first_name="Begona",
            last_name="Otaeva",
        )

        self.group = StudentGroup.objects.create(teacher=self.teacher, name="9-A")
        self.group.students.add(self.ali, self.zuhra)
        self.foreign_group = StudentGroup.objects.create(
            teacher=self.other_teacher,
            name="10-B",
        )
        self.foreign_group.students.add(self.outsider)

        # An approved, Telegram-verified parent link for Ali only.
        ParentStudentLink.objects.create(
            parent=self.parent,
            student=self.ali,
            is_approved=True,
            relationship="father",
        )
        ParentStudentLink.objects.create(
            parent=self.other_parent,
            student=self.zuhra,
            is_approved=True,
            relationship="mother",
        )

        self.topic = EssayTopic.objects.create(
            title="Kitobxonlik",
            description="Tavsif",
            created_by=self.teacher,
        )
        self.assignment = EssayAssignment.objects.create(
            topic=self.topic,
            group=self.group,
            assigned_by=self.teacher,
        )
        self.foreign_topic = EssayTopic.objects.create(
            title="Begona mavzu",
            description="Tavsif",
            created_by=self.other_teacher,
        )
        self.foreign_assignment = EssayAssignment.objects.create(
            topic=self.foreign_topic,
            group=self.foreign_group,
            assigned_by=self.other_teacher,
        )

    # -- helpers ----------------------------------------------------------

    def url(self, name, **kwargs):
        return reverse(f"webapi:{name}", kwargs=kwargs or None)

    def _post(self, name, payload=None, **kwargs):
        return self.client.post(
            self.url(name, **kwargs),
            payload or {},
            content_type="application/json",
        )

    def _patch(self, name, payload=None, **kwargs):
        return self.client.patch(
            self.url(name, **kwargs),
            payload or {},
            content_type="application/json",
        )

    def _login(self, user):
        self.client.force_login(user)

    def _session(self, *, group=None, start_hour=9, teacher=None):
        """Create a register through the canonical service (setup only)."""
        from apps.attendance import services

        session, _ = services.create_session(
            group=group or self.group,
            teacher=teacher or self.teacher,
            lesson_date=timezone.localdate(),
            start_time=dt.time(start_hour, 0),
            actor=teacher or self.teacher,
        )
        return session

    def _mark(self, session, student, status, *, late_minutes=0):
        from apps.attendance import services

        return services.mark(
            session,
            student,
            status,
            late_minutes=late_minutes,
            actor=session.teacher,
        )

    def _submission(
        self,
        *,
        student=None,
        assignment=None,
        status=EssaySubmission.Status.GRADED,
        total_score=20,
        source=EssaySubmission.Source.WEB,
        final_score=None,
    ):
        assignment = assignment if assignment is not None else self.assignment
        return EssaySubmission.objects.create(
            student=student or self.ali,
            topic=assignment.topic if assignment else None,
            assignment=assignment,
            essay_text="Matn " * 60,
            status=status,
            total_score=total_score,
            max_score=24,
            final_score=final_score,
            source=source,
            group_visibility=EssaySubmission.GroupVisibility.ASSIGNMENT_ONLY,
            submitted_at=timezone.now(),
        )


class SessionRegisterFlowTests(_AttendanceApiFixture):
    """The teacher's register round trip, over the HTTP surface the panel uses."""

    def test_create_session_returns_an_unmarked_roster(self):
        self._login(self.teacher)
        response = self._post(
            "school-attendance-sessions",
            {"group_id": self.group.pk, "title": "1-dars"},
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertTrue(body["created"])
        self.assertEqual(body["summary"]["roster_size"], 2)
        self.assertEqual(body["summary"]["marked"], 0)
        self.assertEqual(body["summary"]["unmarked"], 2)

        detail = self.client.get(
            self.url(
                "school-attendance-session-detail",
                session_id=body["session"]["id"],
            )
        )
        self.assertEqual(detail.status_code, 200)
        roster = detail.json()["roster"]
        self.assertEqual(len(roster), 2)
        for row in roster:
            self.assertFalse(row["marked"])
            self.assertIsNone(row["status"])
            self.assertEqual(row["status_label"], "Belgilanmagan")
            self.assertIsNone(row["record_id"])
        # Nothing was recorded: the register is empty, not absent-by-default.
        self.assertEqual(AttendanceRecord.objects.count(), 0)

    def test_create_session_is_idempotent_for_the_same_key(self):
        self._login(self.teacher)
        payload = {
            "group_id": self.group.pk,
            "start_time": "09:00",
            "idempotency_key": "tatt:42:777",
        }
        first = self._post("school-attendance-sessions", payload)
        second = self._post("school-attendance-sessions", payload)
        self.assertEqual(first.status_code, 201)
        self.assertTrue(first.json()["created"])
        self.assertEqual(second.status_code, 200)
        self.assertFalse(second.json()["created"])
        self.assertEqual(first.json()["session"]["id"], second.json()["session"]["id"])
        self.assertEqual(AttendanceSession.objects.count(), 1)

    def test_two_periods_on_one_day_stay_distinct(self):
        self._login(self.teacher)
        first = self._post(
            "school-attendance-sessions",
            {"group_id": self.group.pk, "start_time": "09:00"},
        )
        second = self._post(
            "school-attendance-sessions",
            {"group_id": self.group.pk, "start_time": "10:00"},
        )
        self.assertEqual({first.status_code, second.status_code}, {201})
        self.assertNotEqual(
            first.json()["session"]["id"],
            second.json()["session"]["id"],
        )
        self.assertEqual(AttendanceSession.objects.count(), 2)

    def test_repeated_mark_updates_one_record_only(self):
        self._login(self.teacher)
        session = self._session()
        first = self._post(
            "school-attendance-session-mark",
            {"student_id": self.ali.pk, "status": "present"},
            session_id=session.pk,
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["applied"], 1)

        second = self._post(
            "school-attendance-session-mark",
            {
                "marks": [
                    {
                        "student_id": self.ali.pk,
                        "status": "late",
                        "late_minutes": 12,
                    }
                ]
            },
            session_id=session.pk,
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(AttendanceRecord.objects.filter(session=session).count(), 1)
        record = AttendanceRecord.objects.get(session=session, student=self.ali)
        self.assertEqual(record.status, AttendanceRecord.Status.LATE)
        self.assertEqual(record.late_minutes, 12)
        # The correction is audited, not silently overwritten.
        self.assertTrue(session.audit_logs.exists())

    def test_mark_all_present_leaves_an_explicit_absence_alone(self):
        self._login(self.teacher)
        session = self._session()
        self._mark(session, self.ali, AttendanceRecord.Status.ABSENT)

        response = self._post(
            "school-attendance-session-mark-all-present",
            session_id=session.pk,
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["marked"], 1)  # only the unmarked student
        self.assertEqual(body["summary"]["present"], 1)
        self.assertEqual(body["summary"]["absent"], 1)
        self.assertEqual(body["summary"]["unmarked"], 0)
        self.assertEqual(
            AttendanceRecord.objects.get(session=session, student=self.ali).status,
            AttendanceRecord.Status.ABSENT,
        )

    def test_mark_rejects_an_unknown_status(self):
        self._login(self.teacher)
        session = self._session()
        response = self._post(
            "school-attendance-session-mark",
            {"marks": [{"student_id": self.ali.pk, "status": "uchib_ketdi"}]},
            session_id=session.pk,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(AttendanceRecord.objects.filter(session=session).count(), 0)

    def test_mark_requires_a_marks_list_or_a_single_pair(self):
        self._login(self.teacher)
        session = self._session()
        response = self._post(
            "school-attendance-session-mark",
            {},
            session_id=session.pk,
        )
        self.assertEqual(response.status_code, 400)

    def test_mark_ignores_a_student_outside_the_group(self):
        self._login(self.teacher)
        session = self._session()
        response = self._post(
            "school-attendance-session-mark",
            {"marks": [{"student_id": self.outsider.pk, "status": "present"}]},
            session_id=session.pk,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["applied"], 0)
        self.assertFalse(
            AttendanceRecord.objects.filter(
                session=session, student=self.outsider
            ).exists()
        )

    def test_a_bad_date_is_a_400_not_a_500(self):
        self._login(self.teacher)
        bad = self.client.get(
            self.url("school-attendance-report"),
            {"group_id": self.group.pk, "start": "not-a-date"},
        )
        self.assertEqual(bad.status_code, 400)
        bad_post = self._post(
            "school-attendance-sessions",
            {"group_id": self.group.pk, "lesson_date": "32-13-2020"},
        )
        self.assertEqual(bad_post.status_code, 400)

    def test_a_bad_group_id_is_a_400(self):
        self._login(self.teacher)
        response = self.client.get(
            self.url("school-attendance-report"),
            {"group_id": "abc"},
        )
        self.assertEqual(response.status_code, 400)


class FinalizeConcurrencyAndConfirmationTests(_AttendanceApiFixture):
    """Finalization never invents an absence, and says so in a parseable body."""

    def test_finalize_refuses_while_students_are_unmarked(self):
        self._login(self.teacher)
        session = self._session()
        self._mark(session, self.ali, AttendanceRecord.Status.PRESENT)

        response = self._post(
            "school-attendance-session-finalize",
            {},
            session_id=session.pk,
        )
        self.assertEqual(response.status_code, 409)
        body = response.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["reason"], "unmarked_students")
        unmarked = body["unmarked"]
        self.assertEqual([row["student_id"] for row in unmarked], [self.zuhra.pk])
        self.assertEqual(unmarked[0]["name"], "Zuhra Karimova")
        # The React panel reads reason/unmarked off this exact body; a top-level
        # `detail` string would hide the actionable list behind a generic error.
        self.assertNotIn("detail", body)

        session.refresh_from_db()
        self.assertEqual(session.status, AttendanceSession.Status.DRAFT)
        self.assertIsNone(session.finalized_at)
        self.assertFalse(
            AttendanceRecord.objects.filter(
                session=session, student=self.zuhra
            ).exists()
        )

    def test_finalize_with_explicit_confirmation_marks_the_rest_absent(self):
        self._login(self.teacher)
        session = self._session()
        self._mark(session, self.ali, AttendanceRecord.Status.PRESENT)

        response = self._post(
            "school-attendance-session-finalize",
            {"mark_unmarked_as_absent": True},
            session_id=session.pk,
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["present"], 1)
        self.assertEqual(body["absent"], 1)
        self.assertEqual(body["unmarked"], 0)
        session.refresh_from_db()
        self.assertEqual(session.status, AttendanceSession.Status.FINALIZED)
        self.assertIsNotNone(session.finalized_at)

    def test_finalize_all_marked_needs_no_confirmation(self):
        self._login(self.teacher)
        session = self._session()
        self._mark(session, self.ali, AttendanceRecord.Status.PRESENT)
        self._mark(session, self.zuhra, AttendanceRecord.Status.LATE, late_minutes=5)

        response = self._post(
            "school-attendance-session-finalize",
            {},
            session_id=session.pk,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])


class AttendanceAuthorizationTests(_AttendanceApiFixture):
    """A teacher can never reach another teacher's group, session or student."""

    def setUp(self):
        super().setUp()
        self.foreign_session = self._session(
            group=self.foreign_group,
            teacher=self.other_teacher,
        )
        self._mark(self.foreign_session, self.outsider, AttendanceRecord.Status.ABSENT)

    def assert_no_foreign_disclosure(self, response):
        raw = response.content.decode()
        self.assertNotIn(self.foreign_group.name, raw)
        self.assertNotIn(self.outsider.get_full_name(), raw)
        self.assertNotIn(self.outsider.email, raw)

    def test_a_foreign_group_id_never_resolves(self):
        self._login(self.teacher)
        for name in (
            "school-attendance-report",
            "school-essay-results",
            "school-essay-summary",
        ):
            with self.subTest(endpoint=name):
                response = self.client.get(
                    self.url(name),
                    {"group_id": self.foreign_group.pk},
                )
                self.assertEqual(response.status_code, 400)
                self.assert_no_foreign_disclosure(response)

        created = self._post(
            "school-attendance-sessions",
            {"group_id": self.foreign_group.pk},
        )
        self.assertEqual(created.status_code, 400)
        self.assert_no_foreign_disclosure(created)
        self.assertEqual(
            AttendanceSession.objects.filter(group=self.foreign_group).count(), 1
        )

        listed = self.client.get(
            self.url("school-attendance-sessions"),
            {"group_id": self.foreign_group.pk},
        )
        self.assertEqual(listed.status_code, 400)
        self.assert_no_foreign_disclosure(listed)

    def test_foreign_session_endpoints_are_forbidden(self):
        self._login(self.teacher)
        for label, call in (
            (
                "detail",
                lambda: self.client.get(
                    self.url(
                        "school-attendance-session-detail",
                        session_id=self.foreign_session.pk,
                    )
                ),
            ),
            (
                "mark",
                lambda: self._post(
                    "school-attendance-session-mark",
                    {"student_id": self.outsider.pk, "status": "present"},
                    session_id=self.foreign_session.pk,
                ),
            ),
            (
                "mark-all-present",
                lambda: self._post(
                    "school-attendance-session-mark-all-present",
                    session_id=self.foreign_session.pk,
                ),
            ),
            (
                "finalize",
                lambda: self._post(
                    "school-attendance-session-finalize",
                    session_id=self.foreign_session.pk,
                ),
            ),
        ):
            with self.subTest(endpoint=label):
                response = call()
                self.assertEqual(response.status_code, 403)
                self.assert_no_foreign_disclosure(response)

        # Nothing about the foreign register changed: no whiteboard for another
        # teacher's class, and no silent finalization.
        self.foreign_session.refresh_from_db()
        self.assertEqual(self.foreign_session.status, AttendanceSession.Status.DRAFT)
        self.assertEqual(
            AttendanceRecord.objects.get(
                session=self.foreign_session,
                student=self.outsider,
            ).status,
            AttendanceRecord.Status.ABSENT,
        )

    def test_an_unknown_session_id_is_404(self):
        self._login(self.teacher)
        missing = self.client.get(
            self.url("school-attendance-session-detail", session_id=999999),
        )
        self.assertEqual(missing.status_code, 404)

    def test_the_session_list_only_ever_contains_own_groups(self):
        own = self._session()
        self._login(self.teacher)
        response = self.client.get(self.url("school-attendance-sessions"))
        self.assertEqual(response.status_code, 200)
        # The foreign session EXISTS in this fixture, so an exact set equality
        # proves the scoping rather than merely that the list is empty.
        ids = {row["id"] for row in response.json()["results"]}
        self.assertEqual(ids, {own.pk})
        self.assertNotIn(self.foreign_session.pk, ids)
        self.assert_no_foreign_disclosure(response)

    def test_students_and_parents_cannot_use_teacher_endpoints(self):
        for user in (self.ali, self.parent):
            self._login(user)
            with self.subTest(role=user.role):
                self.assertEqual(
                    self.client.get(
                        self.url("school-attendance-report"),
                        {"group_id": self.group.pk},
                    ).status_code,
                    403,
                )
                self.assertEqual(
                    self._post(
                        "school-attendance-sessions",
                        {"group_id": self.group.pk},
                    ).status_code,
                    403,
                )
                self.assertEqual(
                    self.client.get(self.url("school-essay-results")).status_code,
                    403,
                )

    def test_anonymous_requests_are_denied_without_any_payload(self):
        from rest_framework.test import APIClient

        anonymous = APIClient()
        # DRF answers NotAuthenticated when the first authentication class
        # supplies a WWW-Authenticate header, so the boundary is 401/403 —
        # the same range the existing SPA-contract test asserts.
        for url in (
            self.url("school-attendance-report"),
            self.url("school-essay-results"),
            self.url("school-notification-preferences"),
        ):
            with self.subTest(url=url):
                response = anonymous.get(url)
                self.assertIn(response.status_code, (401, 403))
                self.assertNotIn(self.group.name, response.content.decode())

    def test_student_history_is_membership_scoped(self):
        self._login(self.teacher)
        self._mark(self._session(), self.ali, AttendanceRecord.Status.PRESENT)

        mine = self.client.get(
            self.url("school-attendance-student", student_id=self.ali.pk),
        )
        self.assertEqual(mine.status_code, 200)
        self.assertEqual(mine.json()["student_id"], self.ali.pk)

        foreign = self.client.get(
            self.url("school-attendance-student", student_id=self.outsider.pk),
        )
        self.assertEqual(foreign.status_code, 404)
        self.assert_no_foreign_disclosure(foreign)

        # A non-student id is not a student record either.
        self.assertEqual(
            self.client.get(
                self.url("school-attendance-student", student_id=self.teacher.pk),
            ).status_code,
            404,
        )

    def test_foreign_assignment_completion_is_not_found(self):
        self._login(self.teacher)
        response = self.client.get(
            self.url(
                "school-assignment-completion",
                assignment_id=self.foreign_assignment.pk,
            ),
        )
        self.assertEqual(response.status_code, 404)
        self.assert_no_foreign_disclosure(response)

    def test_an_admin_sees_every_group(self):
        own = self._session()
        self._login(self.admin)
        response = self.client.get(self.url("school-attendance-sessions"))
        self.assertEqual(response.status_code, 200)
        ids = {row["id"] for row in response.json()["results"]}
        self.assertEqual(ids, {own.pk, self.foreign_session.pk})

        report = self.client.get(
            self.url("school-attendance-report"),
            {"group_id": self.foreign_group.pk},
        )
        self.assertEqual(report.status_code, 200)
        self.assertEqual(report.json()["group_id"], self.foreign_group.pk)


class AttendanceReportApiTests(_AttendanceApiFixture):
    """Aggregated statistics: exact numbers, and no absence for an open register."""

    def setUp(self):
        super().setUp()
        first = self._session(start_hour=9)
        self._mark(first, self.ali, AttendanceRecord.Status.PRESENT)
        self._mark(first, self.zuhra, AttendanceRecord.Status.LATE, late_minutes=8)
        from apps.attendance import services

        services.finalize(first, actor=self.teacher)

        second = self._session(start_hour=10)
        self._mark(second, self.ali, AttendanceRecord.Status.ABSENT)
        self._mark(second, self.zuhra, AttendanceRecord.Status.EXCUSED)
        services.finalize(second, actor=self.teacher)

        # An unfinished register: its ABSENT row must not enter the statistics.
        draft = self._session(start_hour=11)
        self._mark(draft, self.ali, AttendanceRecord.Status.ABSENT)

    def test_group_report_numbers_are_exact(self):
        self._login(self.teacher)
        response = self.client.get(
            self.url("school-attendance-report"),
            {"group_id": self.group.pk},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["group_id"], self.group.pk)
        self.assertEqual(body["roster_size"], 2)
        self.assertEqual(body["sessions_total"], 3)
        self.assertEqual(body["finalized_sessions"], 2)
        self.assertEqual(body["pending_sessions"], 1)
        self.assertEqual(body["present"], 1)
        self.assertEqual(body["late"], 1)
        self.assertEqual(body["absent"], 1)
        self.assertEqual(body["excused"], 1)
        self.assertEqual(body["attended"], 2)
        self.assertEqual(body["marked_records"], 4)
        self.assertEqual(body["unexcused_absent"], 1)
        self.assertEqual(body["attendance_percentage"], 50.0)

    def test_open_register_absent_is_not_counted_as_an_absence(self):
        """The draft register's ABSENT row is excluded, and reported as pending."""
        self.assertEqual(
            AttendanceRecord.objects.filter(
                session__group=self.group,
                student=self.ali,
                status=AttendanceRecord.Status.ABSENT,
            ).count(),
            2,
        )  # one in the finalized register, one in the draft

        self._login(self.teacher)
        body = self.client.get(
            self.url("school-attendance-report"),
            {"group_id": self.group.pk},
        ).json()
        self.assertEqual(body["absent"], 1)
        self.assertEqual(body["unexcused_absent"], 1)
        self.assertEqual(body["pending_sessions"], 1)

    def test_daily_breakdown_aggregates_one_row_per_date(self):
        self._login(self.teacher)
        response = self.client.get(
            self.url("school-attendance-report"),
            {"group_id": self.group.pk, "daily": "true"},
        )
        self.assertEqual(response.status_code, 200)
        daily = response.json()["daily"]
        self.assertEqual(len(daily), 1)
        row = daily[0]
        self.assertEqual(row["date"], timezone.localdate().isoformat())
        self.assertEqual(row["present"], 1)
        self.assertEqual(row["late"], 1)
        self.assertEqual(row["absent"], 1)
        self.assertEqual(row["excused"], 1)
        self.assertEqual(row["attendance_percentage"], 50.0)

    def test_overview_lists_only_own_groups(self):
        self._login(self.teacher)
        response = self.client.get(
            self.url("school-attendance-report"),
            {"overview": "true"},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            [row["group_id"] for row in body["groups"]],
            [self.group.pk],
        )
        self.assertEqual(body["groups"][0]["group_name"], "9-A")
        self.assertTrue({"groups", "start", "end"} <= set(body))

    def test_report_requires_a_group(self):
        self._login(self.teacher)
        response = self.client.get(self.url("school-attendance-report"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("group_id", response.json()["detail"])


class ClassroomObservationApiTests(_AttendanceApiFixture):
    """Observations are neutral notes: unconfirmed until the teacher says so."""

    def _create(self, **payload):
        data = {
            "student_id": self.ali.pk,
            "observation_type": ClassroomObservation.ObservationType.POSITIVE,
            "neutral_description": "Darsda faol qatnashdi.",
        }
        data.update(payload)
        return self._post("school-observation-create", data)

    def test_created_observation_is_not_confirmed_and_not_sent(self):
        self._login(self.teacher)
        response = self._create()
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(
            body["notification_status"],
            ClassroomObservation.NotificationStatus.NOT_SENT,
        )
        self.assertFalse(body["is_confirmed"])
        self.assertIsNone(body["confirmed_at"])
        observation = ClassroomObservation.objects.get(pk=body["id"])
        self.assertEqual(observation.teacher, self.teacher)
        self.assertIsNone(observation.sent_at)

    def test_observation_needs_a_meaningful_description(self):
        self._login(self.teacher)
        response = self._create(neutral_description="ok")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ClassroomObservation.objects.exists())

    def test_observation_rejects_an_unknown_type(self):
        self._login(self.teacher)
        response = self._create(observation_type="jazolanadi")
        self.assertEqual(response.status_code, 400)

    def test_observation_for_a_student_outside_the_groups_is_forbidden(self):
        self._login(self.teacher)
        response = self._create(student_id=self.outsider.pk)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ClassroomObservation.objects.exists())

    def test_observation_requires_a_student_id(self):
        self._login(self.teacher)
        response = self._post(
            "school-observation-create",
            {
                "observation_type": ClassroomObservation.ObservationType.NOTE,
                "neutral_description": "Umumiy izoh yozildi.",
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_patch_corrects_the_description(self):
        self._login(self.teacher)
        created = self._create()
        response = self._patch(
            "school-observation-detail",
            {"neutral_description": "Tuzatilgan neytral izoh."},
            observation_id=created.json()["id"],
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["neutral_description"],
            "Tuzatilgan neytral izoh.",
        )

    def test_confirm_sends_once_and_repeats_are_idempotent(self):
        self._login(self.teacher)
        observation_id = self._create().json()["id"]

        with override_settings(TELEGRAM_BOT_TOKEN=TELEGRAM_TOKEN):
            with patch(
                "apps.attendance.notifications.TelegramService._send_message",
                return_value={"success": True, "error": None},
            ) as send:
                first = self._post(
                    "school-observation-confirm",
                    {"send": True},
                    observation_id=observation_id,
                )
                self.assertEqual(first.status_code, 200)
                self.assertTrue(first.json()["is_confirmed"])
                self.assertEqual(send.call_count, 1)

                # A replayed confirmation must not message the parent again.
                second = self._post(
                    "school-observation-confirm",
                    {"send": True},
                    observation_id=observation_id,
                )
                self.assertEqual(second.status_code, 200)
                self.assertEqual(send.call_count, 1)

        observation = ClassroomObservation.objects.get(pk=observation_id)
        self.assertEqual(
            observation.notification_status,
            ClassroomObservation.NotificationStatus.SENT,
        )
        self.assertIsNotNone(observation.sent_at)

    def test_confirm_without_sending_marks_it_skipped(self):
        self._login(self.teacher)
        observation_id = self._create().json()["id"]
        response = self._post(
            "school-observation-confirm",
            {"send": False},
            observation_id=observation_id,
        )
        self.assertEqual(response.status_code, 200)
        observation = ClassroomObservation.objects.get(pk=observation_id)
        self.assertEqual(
            observation.notification_status,
            ClassroomObservation.NotificationStatus.SKIPPED,
        )
        self.assertIsNone(observation.sent_at)

    def test_another_teacher_cannot_confirm_or_edit_it(self):
        self._login(self.teacher)
        observation_id = self._create().json()["id"]

        self._login(self.other_teacher)
        self.assertEqual(
            self._post(
                "school-observation-confirm",
                {"send": True},
                observation_id=observation_id,
            ).status_code,
            404,
        )
        self.assertEqual(
            self._patch(
                "school-observation-detail",
                {"neutral_description": "Begona tahrir."},
                observation_id=observation_id,
            ).status_code,
            404,
        )
        observation = ClassroomObservation.objects.get(pk=observation_id)
        self.assertFalse(observation.is_confirmed)
        self.assertEqual(observation.neutral_description, "Darsda faol qatnashdi.")


class EssayResultsApiTests(_AttendanceApiFixture):
    """Group essay reporting over HTTP: filters, pagination and scoping."""

    def setUp(self):
        super().setUp()
        self.graded = self._submission(student=self.ali, total_score=20)
        self.pending = self._submission(
            student=self.zuhra,
            status=EssaySubmission.Status.PENDING,
            total_score=0,
        )
        self.foreign = self._submission(
            student=self.outsider,
            assignment=self.foreign_assignment,
            total_score=18,
        )

    def test_graded_and_pending_are_counted_separately(self):
        self._login(self.teacher)
        response = self.client.get(
            self.url("school-essay-results"),
            {"group_id": self.group.pk},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 2)
        self.assertEqual(body["graded"], 1)
        self.assertEqual(body["pending"], 1)
        self.assertEqual(body["group_name"], "9-A")

        rows = {row["submission_id"]: row for row in body["results"]}
        graded_row = rows[self.graded.pk]
        pending_row = rows[self.pending.pk]
        self.assertTrue(graded_row["is_graded"])
        self.assertFalse(graded_row["is_pending"])
        self.assertEqual(graded_row["ai_total_score"], 20.0)
        self.assertEqual(graded_row["max_score"], 24)
        # The converted value is explicitly a PRACTICE score, never an official
        # Rasch/Milliy result: 20/24 * 75 = 62.5 -> 62.
        self.assertEqual(graded_row["converted_practice_score"], 62)
        self.assertIsNone(graded_row["final_score"])
        self.assertFalse(pending_row["is_graded"])
        self.assertTrue(pending_row["is_pending"])
        self.assertTrue(pending_row["status_label"])

    def test_source_label_reflects_the_submission_channel(self):
        self._submission(
            student=self.ali,
            source=EssaySubmission.Source.TELEGRAM,
            total_score=19,
        )
        self._login(self.teacher)
        body = self.client.get(
            self.url("school-essay-results"),
            {"group_id": self.group.pk},
        ).json()
        labels = sorted(row["source_label"] for row in body["results"])
        self.assertEqual(labels, ["TELEGRAM", "WEB", "WEB"])

    def test_state_filter_and_pagination_are_accurate(self):
        self._login(self.teacher)
        pending_only = self.client.get(
            self.url("school-essay-results"),
            {"group_id": self.group.pk, "state": "pending"},
        ).json()
        self.assertEqual(pending_only["total"], 1)
        self.assertEqual(
            [row["submission_id"] for row in pending_only["results"]],
            [self.pending.pk],
        )
        self.assertEqual(pending_only["graded"], 0)

        page = self.client.get(
            self.url("school-essay-results"),
            {"group_id": self.group.pk, "limit": 1, "offset": 0},
        ).json()
        self.assertEqual(page["total"], 2)
        self.assertEqual(page["shown"], 1)
        self.assertEqual(page["limit"], 1)
        second = self.client.get(
            self.url("school-essay-results"),
            {"group_id": self.group.pk, "limit": 1, "offset": 1},
        ).json()
        self.assertEqual(second["shown"], 1)
        self.assertNotEqual(
            page["results"][0]["submission_id"],
            second["results"][0]["submission_id"],
        )

    def test_a_bad_pagination_value_is_a_400(self):
        self._login(self.teacher)
        response = self.client.get(
            self.url("school-essay-results"),
            {"group_id": self.group.pk, "limit": 0},
        )
        self.assertEqual(response.status_code, 400)

    def test_another_groups_rows_never_appear(self):
        self._login(self.teacher)
        response = self.client.get(
            self.url("school-essay-results"),
            {"group_id": self.group.pk},
        )
        raw = response.content.decode()
        self.assertNotIn(self.outsider.get_full_name(), raw)
        self.assertNotIn(self.foreign_topic.title, raw)
        # Structured, not a substring: a bare numeric pk like "3" also occurs
        # inside unrelated JSON numbers, so only the returned rows can prove
        # the foreign submission is absent. Both fixtures exist here.
        body = response.json()
        returned = {row["submission_id"] for row in body["results"]}
        self.assertNotIn(self.foreign.pk, returned)
        self.assertNotIn(
            self.outsider.pk,
            {row["student_id"] for row in body["results"]},
        )
        self.assertEqual(returned, {self.graded.pk, self.pending.pk})

    def test_student_filter_narrows_to_one_student(self):
        self._login(self.teacher)
        body = self.client.get(
            self.url("school-essay-results"),
            {"group_id": self.group.pk, "student_id": self.ali.pk},
        ).json()
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["results"][0]["student_id"], self.ali.pk)

    def test_summary_counts_the_students_who_did_not_submit(self):
        self._login(self.teacher)
        response = self.client.get(
            self.url("school-essay-summary"),
            {"group_id": self.group.pk},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["roster_size"], 2)
        self.assertEqual(body["graded"], 1)
        self.assertEqual(body["pending"], 1)
        self.assertEqual(body["not_submitted"], 0)
        self.assertEqual(body["average_ai_score"], 20.0)

        # A student who never handed anything in is counted as missing, and is
        # not inside the results list.
        self.pending.delete()
        body = self.client.get(
            self.url("school-essay-summary"),
            {"group_id": self.group.pk},
        ).json()
        self.assertEqual(body["not_submitted"], 1)

    def test_overview_lists_only_own_groups(self):
        self._login(self.teacher)
        body = self.client.get(
            self.url("school-essay-summary"),
            {"overview": "true"},
        ).json()
        self.assertEqual([row["group_id"] for row in body["groups"]], [self.group.pk])
        self.assertEqual(body["groups"][0]["graded"], 1)


class AssignmentCompletionApiTests(_AttendanceApiFixture):
    """An AI failure is never reported as a missing submission."""

    def test_completion_splits_failed_from_missing(self):
        failed = self._submission(
            student=self.ali,
            status=EssaySubmission.Status.ERROR,
            total_score=0,
        )
        self._login(self.teacher)
        response = self.client.get(
            self.url(
                "school-assignment-completion",
                assignment_id=self.assignment.pk,
            ),
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["expected"], 2)
        self.assertEqual(body["failed"], 1)
        self.assertEqual(body["graded"], 0)
        self.assertEqual(body["not_submitted"], 1)
        self.assertEqual(
            [row["student_id"] for row in body["missing"]], [self.zuhra.pk]
        )
        self.assertEqual(
            [row["submission_id"] for row in body["submitted"]],
            [failed.pk],
        )

    def test_graded_submission_is_not_missing(self):
        self._submission(student=self.ali, total_score=18)
        self._login(self.teacher)
        body = self.client.get(
            self.url(
                "school-assignment-completion",
                assignment_id=self.assignment.pk,
            ),
        ).json()
        self.assertEqual(body["graded"], 1)
        self.assertEqual(body["not_submitted"], 1)
        self.assertEqual(body["average_ai_score"], 18.0)

    def test_filtering_by_assignment_id_in_the_summary(self):
        self._submission(student=self.ali, total_score=18)
        self._login(self.teacher)
        body = self.client.get(
            self.url("school-essay-summary"),
            {"group_id": self.group.pk, "assignment_id": self.assignment.pk},
        ).json()
        self.assertEqual(body["assignment_id"], self.assignment.pk)
        self.assertEqual(body["graded"], 1)
        self.assertEqual(body["not_submitted"], 1)

        missing = self.client.get(
            self.url("school-essay-summary"),
            {"group_id": self.group.pk, "assignment_id": 999999},
        )
        self.assertEqual(missing.status_code, 404)

    def test_assignment_creation_requires_a_real_topic(self):
        self._login(self.teacher)
        unknown = self._post(
            "school-assignments",
            {"group_id": self.group.pk, "topic_id": 999999},
        )
        self.assertEqual(unknown.status_code, 404)

        twice = self._post(
            "school-assignments",
            {"group_id": self.group.pk, "topic_id": self.topic.pk},
        )
        # (topic, group) is already assigned in the fixture — the service
        # resolves the existing row instead of raising a duplicate/500.
        self.assertEqual(twice.status_code, 201)
        self.assertEqual(twice.json()["id"], self.assignment.pk)
        self.assertEqual(EssayAssignment.objects.filter(group=self.group).count(), 1)

    def test_assignment_creation_for_a_foreign_group_is_rejected(self):
        self._login(self.teacher)
        response = self._post(
            "school-assignments",
            {"group_id": self.foreign_group.pk, "topic_id": self.topic.pk},
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            EssayAssignment.objects.filter(
                group=self.foreign_group, topic=self.topic
            ).exists()
        )

    def test_assignment_list_only_contains_own_groups(self):
        self._login(self.teacher)
        response = self.client.get(self.url("school-assignments"))
        self.assertEqual(response.status_code, 200)
        group_ids = {row["group_id"] for row in response.json()["results"]}
        self.assertEqual(group_ids, {self.group.pk})


class NotificationPreferenceApiTests(_AttendanceApiFixture):
    """A user may only change their own switches, and only the known ones."""

    def test_get_returns_own_row_with_defaults(self):
        self._login(self.teacher)
        response = self.client.get(self.url("school-notification-preferences"))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["telegram_enabled"])
        self.assertTrue(body["attendance_alerts"])
        self.assertTrue(body["teacher_new_essay"])
        self.assertEqual(
            NotificationPreference.objects.filter(user=self.teacher).count(), 1
        )

    def test_patch_round_trips_a_known_switch(self):
        self._login(self.teacher)
        response = self._patch(
            "school-notification-preferences",
            {"attendance_alerts": False},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["attendance_alerts"])
        self.assertTrue(
            NotificationPreference.objects.get(user=self.teacher).attendance_alerts
            is False,
        )
        self.assertTrue(
            NotificationPreference.for_user(self.teacher).teacher_new_essay,
        )

    def test_patch_ignores_unknown_keys(self):
        self._login(self.teacher)
        before = self.teacher.is_superuser
        response = self._patch(
            "school-notification-preferences",
            {"is_superuser": True, "attendance_alerts": False},
        )
        self.assertEqual(response.status_code, 200)
        self.teacher.refresh_from_db()
        self.assertEqual(self.teacher.is_superuser, before)
        self.assertNotIn("is_superuser", response.json())

    def test_the_endpoint_is_self_scoped(self):
        NotificationPreference.for_user(self.zuhra)
        self._login(self.teacher)
        self._patch(
            "school-notification-preferences",
            {"user": self.zuhra.pk, "attendance_alerts": False},
        )
        # A different user's id in the body changes nothing: the row written is
        # always the caller's own, and a non-whitelisted key is ignored.
        self.assertFalse(
            NotificationPreference.objects.get(user=self.teacher).attendance_alerts,
        )
        self.assertTrue(
            NotificationPreference.objects.get(user=self.zuhra).attendance_alerts,
        )


class NotificationDestinationApiTests(_AttendanceApiFixture):
    """A typed chat id only becomes a delivery target after admin approval."""

    def test_destinations_are_admin_only(self):
        self._login(self.teacher)
        self.assertEqual(
            self.client.get(self.url("school-notification-destinations")).status_code,
            403,
        )
        self.assertEqual(
            self._post(
                "school-notification-destinations",
                {"chat_id": -1001555000111, "group_id": self.group.pk},
            ).status_code,
            403,
        )

    def test_a_new_destination_is_unapproved_and_unusable(self):
        self._login(self.admin)
        response = self._post(
            "school-notification-destinations",
            {
                "chat_id": -1001555000111,
                "group_id": self.group.pk,
                "title": "9-A ota-onalar",
                "destination_type": GroupNotificationDestination.DestinationType.PARENT_PUBLIC,
            },
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertFalse(body["is_approved"])
        self.assertFalse(body["is_usable"])
        self.assertIsNone(body["approved_by"])
        self.assertEqual(body["allowed_categories"], ["attendance_summary"])

    def test_approval_flips_usable_and_stamps_the_approver(self):
        self._login(self.admin)
        created = self._post(
            "school-notification-destinations",
            {"chat_id": -1001555000222, "group_id": self.group.pk},
        ).json()
        response = self._post(
            "school-notification-destination-approve",
            {"approve": True},
            destination_id=created["id"],
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["is_approved"])
        self.assertTrue(body["is_usable"])
        self.assertEqual(body["approved_by"], self.admin.pk)
        self.assertIsNotNone(body["approved_at"])

        destination = GroupNotificationDestination.objects.get(pk=created["id"])
        self.assertTrue(destination.is_usable)
        self.assertTrue(destination.accepts("attendance_summary"))

    def test_revoking_an_approval_makes_it_undeliverable_again(self):
        self._login(self.admin)
        destination = GroupNotificationDestination.objects.create(
            group=self.group,
            chat_id=-1001555000333,
            allowed_categories=["attendance_summary"],
            is_approved=True,
            approved_by=self.admin,
            approved_at=timezone.now(),
        )
        response = self._post(
            "school-notification-destination-approve",
            {"approve": False},
            destination_id=destination.pk,
        )
        self.assertEqual(response.status_code, 200)
        destination.refresh_from_db()
        self.assertFalse(destination.is_approved)
        self.assertFalse(destination.is_usable)
        self.assertIsNone(destination.approved_at)
        self.assertFalse(destination.accepts("attendance_summary"))

    def test_a_bad_chat_id_or_type_is_a_400(self):
        self._login(self.admin)
        self.assertEqual(
            self._post(
                "school-notification-destinations",
                {"chat_id": "not-a-chat", "group_id": self.group.pk},
            ).status_code,
            400,
        )
        self.assertEqual(
            self._post(
                "school-notification-destinations",
                {"chat_id": -1001555000444, "destination_type": "hammaga"},
            ).status_code,
            400,
        )
        self.assertEqual(
            self._post(
                "school-notification-destinations",
                {"chat_id": -1001555000555, "group_id": 999999},
            ).status_code,
            404,
        )

    def test_approve_rejects_a_non_list_category_payload(self):
        self._login(self.admin)
        destination = GroupNotificationDestination.objects.create(
            group=self.group,
            chat_id=-1001555000666,
            is_approved=True,
        )
        response = self._post(
            "school-notification-destination-approve",
            {"approve": True, "allowed_categories": "attendance_summary"},
            destination_id=destination.pk,
        )
        self.assertEqual(response.status_code, 400)
        # The rejected payload must not have been applied either.
        destination.refresh_from_db()
        self.assertEqual(destination.allowed_categories, [])

    def test_approve_of_an_unknown_destination_is_404(self):
        self._login(self.admin)
        self.assertEqual(
            self._post(
                "school-notification-destination-approve",
                {"approve": True},
                destination_id=999999,
            ).status_code,
            404,
        )

    def test_the_list_is_readable_by_an_admin(self):
        self._login(self.admin)
        GroupNotificationDestination.objects.create(
            group=self.group,
            chat_id=-1001555000777,
        )
        body = self.client.get(self.url("school-notification-destinations")).json()
        self.assertEqual(len(body["results"]), 1)
        self.assertEqual(body["results"][0]["group_name"], "9-A")


class ParentAttendanceApiTests(_AttendanceApiFixture):
    """A parent sees their verified child's attendance and nobody else's."""

    def setUp(self):
        super().setUp()
        session = self._session()
        self._mark(session, self.ali, AttendanceRecord.Status.LATE, late_minutes=12)
        from apps.attendance import services

        services.finalize(session, actor=self.teacher)

    def test_an_approved_parent_sees_their_child(self):
        self._login(self.parent)
        response = self.client.get(self.url("school-parent-attendance"))
        self.assertEqual(response.status_code, 200)
        children = response.json()["children"]
        self.assertEqual(len(children), 1)
        child = children[0]
        self.assertEqual(child["student_id"], self.ali.pk)
        self.assertEqual(child["late"], 1)
        self.assertEqual(child["attended"], 1)
        self.assertEqual(child["attendance_percentage"], 100.0)
        self.assertEqual(child["relationship"], "father")
        self.assertEqual(child["recent"][0]["late_minutes"], 12)
        self.assertEqual(child["recent"][0]["status_label"], "Kechikdi")
        # No sibling, no cousin: the other family's child is absent entirely.
        self.assertNotIn(self.zuhra.get_full_name(), response.content.decode())
        self.assertNotIn(self.zuhra.email, response.content.decode())

    def test_an_unapproved_link_discloses_nothing(self):
        ParentStudentLink.objects.filter(parent=self.parent).update(is_approved=False)
        self._login(self.parent)
        response = self.client.get(self.url("school-parent-attendance"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["children"], [])
        raw = response.content.decode()
        self.assertNotIn(self.ali.get_full_name(), raw)
        self.assertNotIn(self.ali.email, raw)

    def test_a_parent_cannot_ask_for_another_family_child(self):
        self._login(self.parent)
        response = self.client.get(
            self.url("school-parent-attendance"),
            {"student_id": self.zuhra.pk},
        )
        self.assertEqual(response.status_code, 200)
        children = response.json()["children"]
        self.assertEqual([child["student_id"] for child in children], [self.ali.pk])
        self.assertNotIn(self.zuhra.get_full_name(), response.content.decode())

    def test_a_parent_with_no_children_sees_an_empty_list(self):
        self._login(self.other_parent)
        ParentStudentLink.objects.filter(parent=self.other_parent).update(
            is_approved=False
        )
        response = self.client.get(self.url("school-parent-attendance"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["children"], [])

    def test_a_student_cannot_use_the_parent_endpoint_as_a_shortcut(self):
        self._login(self.ali)
        response = self.client.get(self.url("school-parent-attendance"))
        # The caller has no approved parent links, so the endpoint yields no
        # child data even for a logged-in student.
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["children"], [])
