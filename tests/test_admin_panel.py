"""
Integration tests for the in-app Admin Panel (apps/panel, mounted at /control-panel/).

Covers:
    1. Access control — anon redirect, student/teacher/staff 403, admins OK
    2. Dashboard render
    3. Test CRUD + status transitions (draft/published/archived)
    4. Question management — single/multiple choice + TEXT_MATCH (passage/correct_text)
    5. Essay topic CRUD — categories, word limits, AI metric config
    6. User management — role change, block/unblock, self-protection
"""
from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.courses.models import Category, Course
from apps.essays.models import EssayTopic
from apps.tests.models import Choice, Question, Test

from .conftest import LMSBaseTestCase

User = get_user_model()


class PanelAccessTests(LMSBaseTestCase):
    """Who may (not) enter the panel."""

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse("panel:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_student_forbidden(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("panel:dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_teacher_forbidden(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("panel:dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_role_admin_allowed(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("panel:dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_staff_nonadmin_forbidden(self):
        # Django staff is not a platform administrator.
        staff = User.objects.create_user(
            email="staff@test.com", password="testpass123",
            first_name="Staff", last_name="User", role="teacher",
        )
        staff.is_staff = True
        staff.save(update_fields=["is_staff"])
        self.client.force_login(staff)
        response = self.client.get(reverse("panel:dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_role_admin_without_staff_allowed(self):
        admin = User.objects.create_user(
            email="role-admin@test.com", password="testpass123", role="admin",
        )
        self.client.force_login(admin)
        self.assertEqual(self.client.get(reverse("panel:dashboard")).status_code, 200)

    def test_dashboard_renders_stats(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("panel:dashboard"))
        self.assertContains(response, self.test.title)
        self.assertContains(response, "Testlar")


class PanelTestCrudTests(LMSBaseTestCase):
    """Test module CRUD + status toggling."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin_user)

    def test_test_list(self):
        response = self.client.get(reverse("panel:test-list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.test.title)

    def test_create_test(self):
        response = self.client.post(
            reverse("panel:test-create"),
            {
                "title": "Yangi Test",
                "description": "Tavsif",
                "course": self.course.id,
                "time_limit_minutes": 20,
                "max_attempts": 2,
                "pass_percentage": 70,
                "difficulty": "medium",
                "status": "published",
                "shuffle_questions": "on",
                "show_results_immediately": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        created = Test.objects.get(title="Yangi Test")
        self.assertEqual(created.status, Test.Status.PUBLISHED)
        self.assertTrue(created.is_active)
        # redirects to question manager
        self.assertIn(f"/control-panel/tests/{created.id}/questions/", response.url)

    def test_create_test_draft_is_inactive(self):
        self.client.post(
            reverse("panel:test-create"),
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
        )
        created = Test.objects.get(title="Qoralama Test")
        self.assertEqual(created.status, Test.Status.DRAFT)
        self.assertFalse(created.is_active)

    def test_edit_test(self):
        response = self.client.post(
            reverse("panel:test-edit", args=[self.test.id]),
            {
                "title": "Tahrirlangan",
                "description": "Yangi tavsif",
                "course": self.course.id,
                "time_limit_minutes": 45,
                "max_attempts": 5,
                "pass_percentage": 75,
                "difficulty": "hard",
                "status": "archived",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.test.refresh_from_db()
        self.assertEqual(self.test.title, "Tahrirlangan")
        self.assertEqual(self.test.status, Test.Status.ARCHIVED)
        self.assertFalse(self.test.is_active)

    def test_status_transition(self):
        # published -> archived
        response = self.client.post(
            reverse("panel:test-status", args=[self.test.id]),
            {"status": "archived"},
        )
        self.assertEqual(response.status_code, 302)
        self.test.refresh_from_db()
        self.assertEqual(self.test.status, Test.Status.ARCHIVED)
        self.assertFalse(self.test.is_active)

        # archived -> published restores is_active
        self.client.post(
            reverse("panel:test-status", args=[self.test.id]),
            {"status": "published"},
        )
        self.test.refresh_from_db()
        self.assertEqual(self.test.status, Test.Status.PUBLISHED)
        self.assertTrue(self.test.is_active)

    def test_status_invalid_keeps_old(self):
        self.client.post(
            reverse("panel:test-status", args=[self.test.id]),
            {"status": "bogus"},
        )
        self.test.refresh_from_db()
        self.assertEqual(self.test.status, Test.Status.PUBLISHED)

    def test_delete_test(self):
        response = self.client.post(
            reverse("panel:test-delete", args=[self.test.id])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Test.objects.filter(id=self.test.id).exists())


class PanelQuestionTests(LMSBaseTestCase):
    """Question management incl. passage + TEXT_MATCH."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin_user)

    def test_question_manage_lists(self):
        response = self.client.get(
            reverse("panel:question-manage", args=[self.test.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "What is Django?")

    def test_add_single_choice_question(self):
        response = self.client.post(
            reverse("panel:question-add", args=[self.test.id]),
            {
                "question_type": "single",
                "passage": "Uzoq matn...",
                "text": "Yangi savol?",
                "points": "2",
                "position": "4",
                "choices-TOTAL_FORMS": "3",
                "choices-INITIAL_FORMS": "0",
                "choices-MIN_NUM_FORMS": "0",
                "choices-MAX_NUM_FORMS": "6",
                "choices-0-text": "To'g'ri variant",
                "choices-0-is_correct": "on",
                "choices-1-text": "Noto'g'ri",
                "choices-2-text": "Noto'g'ri 2",
            },
        )
        self.assertEqual(response.status_code, 302)
        q = Question.objects.get(text="Yangi savol?")
        self.assertEqual(q.question_type, "single")
        self.assertEqual(q.passage, "Uzoq matn...")
        self.assertEqual(q.points, 2)
        self.assertEqual(q.choices.filter(is_correct=True).count(), 1)
        self.assertEqual(q.choices.count(), 3)

    def test_add_text_match_question(self):
        response = self.client.post(
            reverse("panel:question-add", args=[self.test.id]),
            {
                "question_type": "text",
                "passage": "Alisher Navoiy haqida parcha",
                "text": "Navoiyning tug'ilgan yili?",
                "correct_text": "1441",
                "points": "3",
                "position": "4",
            },
        )
        self.assertEqual(response.status_code, 302)
        q = Question.objects.get(text="Navoiyning tug'ilgan yili?")
        self.assertEqual(q.question_type, "text")
        self.assertEqual(q.correct_text, "1441")
        self.assertEqual(q.choices.count(), 0)

    def test_text_match_requires_correct_text(self):
        response = self.client.post(
            reverse("panel:question-add", args=[self.test.id]),
            {
                "question_type": "text",
                "text": "Javob kutilmoqda",
                "points": "1",
                "position": "4",
            },
        )
        self.assertEqual(response.status_code, 200)  # re-render with errors
        self.assertFalse(
            Question.objects.filter(text="Javob kutilmoqda").exists()
        )

    def test_edit_question(self):
        response = self.client.post(
            reverse("panel:question-edit", args=[self.test.id, self.q1.id]),
            {
                "question_type": "single",
                "text": "O'zgartirilgan savol?",
                "points": "5",
                "position": "1",
                "choices-TOTAL_FORMS": "3",
                "choices-INITIAL_FORMS": "3",
                "choices-MIN_NUM_FORMS": "0",
                "choices-MAX_NUM_FORMS": "6",
                "choices-0-id": self.q1_c1.id,
                "choices-0-text": "A web framework",
                "choices-0-is_correct": "on",
                "choices-1-id": self.q1_c2.id,
                "choices-1-text": "A database",
                "choices-2-id": self.q1_c3.id,
                "choices-2-text": "An OS",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.q1.refresh_from_db()
        self.assertEqual(self.q1.text, "O'zgartirilgan savol?")
        self.assertEqual(self.q1.points, 5)

    def test_delete_question(self):
        response = self.client.post(
            reverse("panel:question-delete", args=[self.test.id, self.q2.id])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Question.objects.filter(id=self.q2.id).exists())


class PanelEssayTopicTests(LMSBaseTestCase):
    """Essay topic module CRUD + AI metric config."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin_user)
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
        response = self.client.get(reverse("panel:essay-topic-list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Navoiy ijodi")

    def test_create_topic_with_ai_config(self):
        response = self.client.post(
            reverse("panel:essay-topic-create"),
            {
                "title": "Milliy sertifikat mavzusi",
                "description": "Sertifikat uchun esse",
                "category": "ona_tili",
                "word_limit_min": 200,
                "word_limit_max": 500,
                "time_limit_minutes": 60,
                "sample_outline": "1. Kirish 2. Asosiy qism 3. Xulosa",
                "grammar_strictness": "80",
                "national_cert_scale": "on",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        topic = EssayTopic.objects.get(title="Milliy sertifikat mavzusi")
        self.assertEqual(topic.category, "ona_tili")
        self.assertEqual(topic.grammar_strictness, 80)
        self.assertTrue(topic.national_cert_scale)
        self.assertIn("Kirish", topic.sample_outline)

    def test_word_limit_validation(self):
        response = self.client.post(
            reverse("panel:essay-topic-create"),
            {
                "title": "Noto'g'ri limit",
                "description": "",
                "category": "umumiy",
                "word_limit_min": 500,
                "word_limit_max": 100,
                "time_limit_minutes": 30,
                "grammar_strictness": "50",
            },
        )
        self.assertEqual(response.status_code, 200)  # re-render with errors
        self.assertFalse(EssayTopic.objects.filter(title="Noto'g'ri limit").exists())

    def test_edit_topic(self):
        response = self.client.post(
            reverse("panel:essay-topic-edit", args=[self.topic.id]),
            {
                "title": "Navoiy ijodi (tahrir)",
                "description": "Yangi tavsif",
                "category": "tarix",
                "word_limit_min": 100,
                "word_limit_max": 300,
                "time_limit_minutes": 30,
                "sample_outline": "",
                "grammar_strictness": "60",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.topic.refresh_from_db()
        self.assertEqual(self.topic.category, "tarix")
        self.assertEqual(self.topic.grammar_strictness, 60)

    def test_delete_topic(self):
        response = self.client.post(
            reverse("panel:essay-topic-delete", args=[self.topic.id])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(EssayTopic.objects.filter(id=self.topic.id).exists())


class PanelUserManagementTests(LMSBaseTestCase):
    """User list, role change, block/unblock, self-protection."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin_user)
        self.extra = User.objects.create_user(
            email="extra@test.com", password="testpass123",
            first_name="Extra", last_name="User", role="student",
        )

    def test_user_list_renders(self):
        response = self.client.get(reverse("panel:user-list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "student@test.com")
        self.assertContains(response, "extra@test.com")

    def test_user_list_filters(self):
        response = self.client.get(reverse("panel:user-list"), {"role": "teacher"})
        self.assertContains(response, "teacher@test.com")
        self.assertNotContains(response, "extra@test.com")

        response = self.client.get(reverse("panel:user-list"), {"q": "extra"})
        self.assertContains(response, "extra@test.com")
        self.assertNotContains(response, "teacher@test.com")

    def test_change_role(self):
        response = self.client.post(
            reverse("panel:user-role", args=[self.extra.id]),
            {"role": "teacher"},
        )
        self.assertEqual(response.status_code, 302)
        self.extra.refresh_from_db()
        self.assertEqual(self.extra.role, "teacher")

    def test_cannot_demote_self(self):
        response = self.client.post(
            reverse("panel:user-role", args=[self.admin_user.id]),
            {"role": "student"},
        )
        self.assertEqual(response.status_code, 302)
        self.admin_user.refresh_from_db()
        self.assertEqual(self.admin_user.role, "admin")

    def test_block_and_unblock(self):
        response = self.client.post(
            reverse("panel:user-block", args=[self.extra.id])
        )
        self.assertEqual(response.status_code, 302)
        self.extra.refresh_from_db()
        self.assertFalse(self.extra.is_active)

        self.client.post(reverse("panel:user-block", args=[self.extra.id]))
        self.extra.refresh_from_db()
        self.assertTrue(self.extra.is_active)

    def test_cannot_block_self(self):
        response = self.client.post(
            reverse("panel:user-block", args=[self.admin_user.id])
        )
        self.assertEqual(response.status_code, 302)
        self.admin_user.refresh_from_db()
        self.assertTrue(self.admin_user.is_active)

    def test_blocked_user_locked_out(self):
        self.client.post(reverse("panel:user-block", args=[self.extra.id]))
        self.client.logout()
        self.client.force_login(self.extra)
        # force_login ignores is_active, so verify via auth backend semantics:
        # a blocked user must not be able to log in with credentials.
        self.client.logout()
        ok = self.client.login(email="extra@test.com", password="testpass123")
        self.assertFalse(ok)


class PanelLocalizationTests(LMSBaseTestCase):
    """New panel views must render localized strings (RU/EN)."""

    def _render_panel(self, lang: str):
        session = self.client.session
        session["language"] = lang
        session.save()
        self.client.force_login(self.admin_user)
        return self.client.get(reverse("panel:dashboard"))

    def test_russian_dashboard(self):
        response = self._render_panel("ru")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Панель администратора")

    def test_english_dashboard(self):
        response = self._render_panel("en")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Admin Dashboard")
