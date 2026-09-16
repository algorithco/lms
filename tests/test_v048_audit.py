"""
v0.48.0 audit regression tests — panel metrics semantics + Phase 9 permission matrix.

Qamrov:
  * /api/v1/panel/dashboard/ endi pending_ai (PENDING) va awaiting_review
    (PENDING_TEACHER) ni alohida hisoblaydi — "admin 21 pending, teacher
    queue bo'sh" adashuvining ildiz sababi (semantik chalkashlik).
  * Phase 9 (Flows G/H): admin flag boshqaruvi — authorized/unauthorized
    teacher va student rad etilishi.
  * Flow F: cross-group teacher faqat o'z guruhlarini ko'radi.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.courses.models import StudentGroup
from apps.essays.models import EssaySubmission, EssayTopic

User = get_user_model()


class _AuditFixtures(TestCase):
    """Umumiy fiksatura: admin, 2 xil o'qituvchi, o'quvchi."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.admin = User.objects.create_user(
            email="v048-admin@test.com", password="x", role="admin",
        )
        cls.teacher = User.objects.create_user(
            email="v048-teacher@test.com", password="x", role="teacher",
        )
        cls.flagged_teacher = User.objects.create_user(
            email="v048-flagged@test.com", password="x", role="teacher",
            can_create_essay_topic=True,
        )
        cls.other_teacher = User.objects.create_user(
            email="v048-other-teacher@test.com", password="x", role="teacher",
        )
        cls.student = User.objects.create_user(
            email="v048-student@test.com", password="x", role="student",
        )
        cls.topic = EssayTopic.objects.create(title="v048 mavzu", description="")


class PanelDashboardMetricsTests(_AuditFixtures):
    """Panel dashboard essay metrics — semantics split (PENDING vs PENDING_TEACHER)."""

    def test_dashboard_endpoint_returns_split_metrics(self) -> None:
        EssaySubmission.objects.create(
            student=self.student, topic=self.topic, essay_text="X",
            status=EssaySubmission.Status.PENDING,
        )
        EssaySubmission.objects.create(
            student=self.student, topic=self.topic, essay_text="X",
            status=EssaySubmission.Status.PENDING_TEACHER,
        )
        self.client.force_login(self.admin)
        response = self.client.get("/api/v1/panel/dashboard/")
        self.assertEqual(response.status_code, 200)
        essays = response.json()["essays"]
        self.assertIn("pending_ai", essays)
        self.assertIn("awaiting_review", essays)
        self.assertEqual(essays["pending_ai"], 1)
        self.assertEqual(essays["awaiting_review"], 1)

    def test_pending_is_not_counted_as_awaiting_review(self) -> None:
        # The exact outage confusion: 21 rows in PENDING must never make the
        # teacher queue (PENDING_TEACHER) look non-empty.
        for _ in range(21):
            EssaySubmission.objects.create(
                student=self.student, topic=self.topic, essay_text="X",
                status=EssaySubmission.Status.PENDING,
            )
        self.client.force_login(self.admin)
        essays = self.client.get("/api/v1/panel/dashboard/").json()["essays"]
        self.assertEqual(essays["pending_ai"], 21)
        self.assertEqual(essays["awaiting_review"], 0)


class TeacherCreationPermissionMatrixTests(_AuditFixtures):
    """Phase 9 / Flows G-H: can_create_essay_topic backend enforcement."""

    def _post_topic(self):
        return self.client.post(
            "/api/v1/panel/topics/",
            {"title": "Yangi mavzu", "description": "Tavsif"},
            content_type="application/json",
        )

    def test_authorized_teacher_can_create_topic_via_panel_api(self) -> None:
        self.client.force_login(self.flagged_teacher)
        response = self._post_topic()
        self.assertIn(response.status_code, (200, 201))
        self.assertTrue(
            EssayTopic.objects.filter(title="Yangi mavzu").exists(),
        )

    def test_unauthorized_teacher_cannot_create_topic(self) -> None:
        self.client.force_login(self.teacher)
        self.assertEqual(self._post_topic().status_code, 403)

    def test_student_cannot_create_topic(self) -> None:
        self.client.force_login(self.student)
        self.assertEqual(self._post_topic().status_code, 403)

    def test_admin_can_create_topic(self) -> None:
        self.client.force_login(self.admin)
        self.assertIn(self._post_topic().status_code, (200, 201))

    def test_flag_grant_is_admin_side_effect_free(self) -> None:
        """Flag grant must NOT leak staff/admin powers (no role escalation)."""
        self.flagged_teacher.refresh_from_db()
        self.assertFalse(self.flagged_teacher.is_staff)
        self.assertFalse(self.flagged_teacher.is_superuser)
        self.assertFalse(self.flagged_teacher.role == "admin")


class CrossGroupTeacherIsolationTests(_AuditFixtures):
    """Flow F: teacher with no assigned groups sees nothing."""

    def test_teacher_without_groups_sees_no_students_or_essays(self) -> None:
        EssaySubmission.objects.create(
            student=self.student, topic=self.topic, essay_text="X",
            status=EssaySubmission.Status.PENDING_TEACHER,
        )
        self.client.force_login(self.other_teacher)
        response = self.client.get("/api/v1/school/teacher/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["student_count"], 0)
        self.assertEqual(data["essay_pending"], 0)
        self.assertEqual(data["essay_graded"], 0)

    def test_teacher_with_group_is_scoped_to_own_students(self) -> None:
        group = StudentGroup.objects.create(teacher=self.other_teacher, name="5-B")
        group.students.add(self.student)
        EssaySubmission.objects.create(
            student=self.student, topic=self.topic, essay_text="X",
            status=EssaySubmission.Status.PENDING_TEACHER,
        )
        self.client.force_login(self.other_teacher)
        data = self.client.get("/api/v1/school/teacher/").json()
        self.assertEqual(data["student_count"], 1)
        self.assertEqual(data["essay_pending"], 1)
