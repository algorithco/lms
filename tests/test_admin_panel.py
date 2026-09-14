"""
Integration tests for the Admin Panel JSON API (apps/webapi, /api/v1/panel/).

The server-rendered panel pages (templates/panel/*) are retired — the React
SPA drives this JSON contract instead. Covers:
    1. Access control — anon 401, student/teacher/staff 403, admins OK
    2. Dashboard aggregates
    3. Test CRUD + status transitions (draft/published/archived)
    4. Question management — single/multiple choice + TEXT_MATCH
    5. Essay topic CRUD
    6. User management — role change, block/unblock, self-protection
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.essays.models import EssayTopic
from apps.tests.models import Choice, Question, Test

from .conftest import LMSBaseTestCase

User = get_user_model()

PANEL = "/api/v1/panel"


class PanelAccessTests(LMSBaseTestCase):
    """Who may (not) enter the panel API."""

    def api(self, email: str):
        return self.get_authenticated_client(email=email)

    def test_anonymous_unauthenticated(self):
        from rest_framework.test import APIClient
        response = APIClient().get(f"{PANEL}/dashboard/")
        self.assertIn(response.status_code, (401, 403))

    def test_student_forbidden(self):
        response = self.api("student@test.com").get(f"{PANEL}/dashboard/")
        self.assertEqual(response.status_code, 403)

    def test_teacher_forbidden(self):
        response = self.api("teacher@test.com").get(f"{PANEL}/dashboard/")
        self.assertEqual(response.status_code, 403)

    def test_role_admin_allowed(self):
        response = self.api("admin@test.com").get(f"{PANEL}/dashboard/")
        self.assertEqual(response.status_code, 200)

    def test_staff_nonadmin_forbidden(self):
        # Django staff is not a platform administrator.
        staff = User.objects.create_user(
            email="staff@test.com", password="testpass123",
            first_name="Staff", last_name="User", role="teacher",
        )
        staff.is_staff = True
        staff.save(update_fields=["is_staff"])
        response = self.api("staff@test.com").get(f"{PANEL}/dashboard/")
        self.assertEqual(response.status_code, 403)

    def test_role_admin_without_staff_allowed(self):
        User.objects.create_user(
            email="role-admin@test.com", password="testpass123", role="admin",
        )
        response = self.api("role-admin@test.com").get(f"{PANEL}/dashboard/")
        self.assertEqual(response.status_code, 200)

    def test_superuser_student_role_allowed(self):
        # Platform admin is superuser OR role==admin — role alone is not the rule.
        su = User.objects.create_superuser(
            email="su-student@test.com", password="testpass123",
            first_name="Super", last_name="Student",
        )
        su.role = "student"
        su.save(update_fields=["role"])
        response = self.api("su-student@test.com").get(f"{PANEL}/dashboard/")
        self.assertEqual(response.status_code, 200)

    def test_dashboard_aggregates(self):
        data = self.api("admin@test.com").get(f"{PANEL}/dashboard/").data
        self.assertGreaterEqual(data["tests"]["total"], 1)
        self.assertGreaterEqual(data["questions"], 3)
        titles = [t["title"] for t in data["recent_tests"]]
        self.assertIn(self.test.title, titles)


class PanelTestCrudTests(LMSBaseTestCase):
    """Test module CRUD + status toggling via JSON."""

    def setUp(self):
        super().setUp()
        self.client = self.get_authenticated_client(email="admin@test.com")

    def test_test_list(self):
        response = self.client.get(f"{PANEL}/tests/")
        self.assertEqual(response.status_code, 200)
        titles = [t["title"] for t in response.data["results"]]
        self.assertIn(self.test.title, titles)
        self.assertTrue(response.data["statuses"])

    def test_create_test(self):
        response = self.client.post(
            f"{PANEL}/tests/",
            {
                "title": "Yangi Test",
                "description": "Tavsif",
                "course": self.course.id,
                "time_limit_minutes": 20,
                "max_attempts": 2,
                "pass_percentage": 70,
                "difficulty": "medium",
                "status": "published",
                "shuffle_questions": True,
                "show_results_immediately": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        created = Test.objects.get(title="Yangi Test")
        self.assertEqual(created.status, Test.Status.PUBLISHED)
        self.assertTrue(created.is_active)

    def test_create_test_draft_is_inactive(self):
        self.client.post(
            f"{PANEL}/tests/",
            {
                "title": "Qoralama Test",
                "description": "",
                "course": self.course.id,
                "time_limit_minutes": 0,
                "max_attempts": 1,
                "pass_percentage": 60,
                "difficulty": "easy",
                "status": "draft",
            },
            format="json",
        )
        created = Test.objects.get(title="Qoralama Test")
        self.assertEqual(created.status, Test.Status.DRAFT)
        self.assertFalse(created.is_active)

    def test_update_test(self):
        response = self.client.patch(
            reverse("webapi:panel-test-detail", args=[self.test.id]),
            {"title": "Tahrirlangan", "status": "archived"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.test.refresh_from_db()
        self.assertEqual(self.test.title, "Tahrirlangan")
        self.assertEqual(self.test.status, Test.Status.ARCHIVED)

    def test_status_transition(self):
        # published -> archived
        response = self.client.post(
            reverse("webapi:panel-test-status", args=[self.test.id]),
            {"status": "archived"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.test.refresh_from_db()
        self.assertEqual(self.test.status, Test.Status.ARCHIVED)

        # archived -> published
        self.client.post(
            reverse("webapi:panel-test-status", args=[self.test.id]),
            {"status": "published"},
            format="json",
        )
        self.test.refresh_from_db()
        self.assertEqual(self.test.status, Test.Status.PUBLISHED)
        self.assertTrue(self.test.is_active)

    def test_status_invalid_rejected(self):
        response = self.client.post(
            reverse("webapi:panel-test-status", args=[self.test.id]),
            {"status": "bogus"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.test.refresh_from_db()
        self.assertEqual(self.test.status, Test.Status.PUBLISHED)

    def test_delete_test(self):
        response = self.client.delete(
            reverse("webapi:panel-test-detail", args=[self.test.id])
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Test.objects.filter(id=self.test.id).exists())


class PanelQuestionTests(LMSBaseTestCase):
    """Question management incl. passage + TEXT_MATCH via JSON."""

    def setUp(self):
        super().setUp()
        self.client = self.get_authenticated_client(email="admin@test.com")
        self.url = reverse("webapi:panel-questions", args=[self.test.id])

    def test_question_list(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        texts = [q["text"] for q in response.data["results"]]
        self.assertIn("What is Django?", texts)

    def test_add_single_choice_question(self):
        response = self.client.post(
            self.url,
            {
                "question_type": "single",
                "passage": "Uzoq matn...",
                "text": "Yangi savol?",
                "points": 2,
                "position": 4,
                "choices": [
                    {"text": "To'g'ri variant", "is_correct": True, "position": 1},
                    {"text": "Noto'g'ri", "is_correct": False, "position": 2},
                    {"text": "Noto'g'ri 2", "is_correct": False, "position": 3},
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        q = Question.objects.get(text="Yangi savol?")
        self.assertEqual(q.question_type, "single")
        self.assertEqual(q.passage, "Uzoq matn...")
        self.assertEqual(q.points, 2)
        self.assertEqual(q.choices.filter(is_correct=True).count(), 1)
        self.assertEqual(q.choices.count(), 3)

    def test_add_text_match_question(self):
        response = self.client.post(
            self.url,
            {
                "question_type": "text",
                "passage": "Alisher Navoiy haqida parcha",
                "text": "Navoiyning tug'ilgan yili?",
                "correct_text": "1441",
                "points": 3,
                "position": 4,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        q = Question.objects.get(text="Navoiyning tug'ilgan yili?")
        self.assertEqual(q.question_type, "text")
        self.assertEqual(q.correct_text, "1441")
        self.assertEqual(q.choices.count(), 0)

    def test_edit_question(self):
        response = self.client.patch(
            reverse("webapi:panel-question-detail", args=[self.test.id, self.q1.id]),
            {
                "text": "O'zgartirilgan savol?",
                "points": 5,
                "choices": [
                    {"text": "A web framework", "is_correct": True, "position": 1},
                    {"text": "A database", "is_correct": False, "position": 2},
                    {"text": "An OS", "is_correct": False, "position": 3},
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.q1.refresh_from_db()
        self.assertEqual(self.q1.text, "O'zgartirilgan savol?")
        self.assertEqual(self.q1.points, 5)

    def test_delete_question(self):
        response = self.client.delete(
            reverse("webapi:panel-question-detail", args=[self.test.id, self.q2.id])
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Question.objects.filter(id=self.q2.id).exists())


class PanelEssayTopicTests(LMSBaseTestCase):
    """Essay topic module CRUD via JSON."""

    def setUp(self):
        super().setUp()
        self.client = self.get_authenticated_client(email="admin@test.com")
        self.topic = EssayTopic.objects.create(
            title="Navoiy ijodi",
            description="Alisher Navoiy ijodi haqida esse",
            category="adabiyot",
            word_limit_min=150,
            word_limit_max=400,
            time_limit_minutes=45,
            created_by=self.admin_user,
        )

    def test_topic_list(self):
        response = self.client.get(f"{PANEL}/topics/")
        self.assertEqual(response.status_code, 200)
        titles = [t["title"] for t in response.data["results"]]
        self.assertIn("Navoiy ijodi", titles)
        self.assertTrue(response.data["categories"])

    def test_create_topic(self):
        response = self.client.post(
            f"{PANEL}/topics/",
            {
                "title": "Milliy sertifikat mavzusi",
                "description": "Sertifikat uchun esse",
                "category": "ona_tili",
                "word_limit_min": 200,
                "word_limit_max": 500,
                "time_limit_minutes": 60,
                "sample_outline": "1. Kirish 2. Asosiy qism 3. Xulosa",
                "grammar_strictness": 80,
                "national_cert_scale": True,
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        topic = EssayTopic.objects.get(title="Milliy sertifikat mavzusi")
        self.assertEqual(topic.category, "ona_tili")
        self.assertEqual(topic.grammar_strictness, 80)
        self.assertTrue(topic.national_cert_scale)
        self.assertIn("Kirish", topic.sample_outline)
        self.assertEqual(topic.created_by, self.admin_user)

    def test_invalid_category_rejected(self):
        response = self.client.post(
            f"{PANEL}/topics/",
            {
                "title": "Noto'g'ri kategoriya",
                "description": "",
                "category": "bogus",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(EssayTopic.objects.filter(title="Noto'g'ri kategoriya").exists())

    def test_edit_topic(self):
        response = self.client.patch(
            reverse("webapi:panel-topic-detail", args=[self.topic.id]),
            {"title": "Navoiy ijodi (tahrir)", "category": "tarix", "grammar_strictness": 60},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.topic.refresh_from_db()
        self.assertEqual(self.topic.category, "tarix")
        self.assertEqual(self.topic.grammar_strictness, 60)

    def test_delete_topic(self):
        response = self.client.delete(
            reverse("webapi:panel-topic-detail", args=[self.topic.id])
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(EssayTopic.objects.filter(id=self.topic.id).exists())


class PanelUserManagementTests(LMSBaseTestCase):
    """User list, role change, block/unblock, self-protection via JSON."""

    def setUp(self):
        super().setUp()
        self.client = self.get_authenticated_client(email="admin@test.com")
        self.extra = User.objects.create_user(
            email="extra@test.com", password="testpass123",
            first_name="Extra", last_name="User", role="student",
        )

    def _emails(self, data):
        return [u["email"] for u in data["results"]]

    def test_user_list(self):
        response = self.client.get(f"{PANEL}/users/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("student@test.com", self._emails(response.data))
        self.assertIn("extra@test.com", self._emails(response.data))
        self.assertTrue(response.data["roles"])

    def test_user_list_filters(self):
        response = self.client.get(f"{PANEL}/users/", {"role": "teacher"})
        self.assertIn("teacher@test.com", self._emails(response.data))
        self.assertNotIn("extra@test.com", self._emails(response.data))

        response = self.client.get(f"{PANEL}/users/", {"q": "extra"})
        self.assertIn("extra@test.com", self._emails(response.data))
        self.assertNotIn("teacher@test.com", self._emails(response.data))

    def test_change_role(self):
        response = self.client.post(
            reverse("webapi:panel-user-role", args=[self.extra.id]),
            {"role": "teacher"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.extra.refresh_from_db()
        self.assertEqual(self.extra.role, "teacher")

    def test_cannot_demote_self(self):
        response = self.client.post(
            reverse("webapi:panel-user-role", args=[self.admin_user.id]),
            {"role": "student"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.admin_user.refresh_from_db()
        self.assertEqual(self.admin_user.role, "admin")

    def test_block_and_unblock(self):
        response = self.client.post(reverse("webapi:panel-user-block", args=[self.extra.id]))
        self.assertEqual(response.status_code, 200)
        self.extra.refresh_from_db()
        self.assertFalse(self.extra.is_active)

        self.client.post(reverse("webapi:panel-user-block", args=[self.extra.id]))
        self.extra.refresh_from_db()
        self.assertTrue(self.extra.is_active)

    def test_cannot_block_self(self):
        response = self.client.post(
            reverse("webapi:panel-user-block", args=[self.admin_user.id])
        )
        self.assertEqual(response.status_code, 400)
        self.admin_user.refresh_from_db()
        self.assertTrue(self.admin_user.is_active)

    def test_blocked_user_locked_out(self):
        self.client.post(reverse("webapi:panel-user-block", args=[self.extra.id]))
        self.client.logout()
        self.client.force_login(self.extra)
        # force_login ignores is_active, so verify via auth backend semantics:
        # a blocked user must not be able to log in with credentials.
        self.client.logout()
        ok = self.client.login(email="extra@test.com", password="testpass123")
        self.assertFalse(ok)
