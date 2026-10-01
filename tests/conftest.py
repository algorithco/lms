"""
Shared test fixtures for LMS Platform integration tests.

Provides factory helpers for creating:
    - Users (student, teacher, admin)
    - Categories, Courses
    - Tests with Questions and Choices
    - TestAttempts and Results
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.courses.models import Category, Course
from apps.games.models import Badge, Game
from apps.tests.models import Choice, Question, Test, TestAttempt
from apps.results.models import Result, Certificate

User = get_user_model()


def _ensure_arena_badges() -> None:
    """Ensure arena badges and the arena_duel game exist in the test database.
    
    The data migration 0005_arena_badges_and_game should create these, but in the
    test environment it doesn't always run correctly. This helper ensures they exist.
    """
    # Create arena_duel game if missing
    if not Game.objects.filter(slug="arena_duel").exists():
        Game.objects.create(
            name="Quiz Arena Dueli",
            slug="arena_duel",
            description="1v1 real-time quiz duel — ELO reyting, kombo va tezlik bonuslari.",
            icon_emoji="⚔️",
            xp_per_correct=10,
            coins_per_correct=5,
            is_active=False,
            sort_order=4,
        )

    # Create arena badges if missing
    badges = [
        {
            "badge_type": "duel_winner_10",
            "name": "10 G'alaba Streak",
            "description": "Arena'da 10 ta duel g'alabasi",
            "icon_emoji": "🏆",
            "required_value": 10,
            "xp_bonus": 300,
        },
        {
            "badge_type": "night_owl",
            "name": "Tungi Boyqush",
            "description": "Kechasi (00:00-05:59) duel g'alaba qozonish",
            "icon_emoji": "🦉",
            "required_value": 1,
            "xp_bonus": 100,
        },
        {
            "badge_type": "essay_master",
            "name": "Esse Ustasi",
            "description": "5 ta esse AI tomonidan baholanishi",
            "icon_emoji": "✍️",
            "required_value": 5,
            "xp_bonus": 200,
        },
        {
            "badge_type": "arena_elite",
            "name": "Arena Elitasi",
            "description": "1200+ ELO reytingga erishish",
            "icon_emoji": "👑",
            "required_value": 1200,
            "xp_bonus": 250,
        },
    ]

    for b in badges:
        Badge.objects.get_or_create(badge_type=b["badge_type"], defaults=b)


class LMSBaseTestCase(TestCase):
    """
    Base test case with pre-created fixtures.

    self.student, self.teacher, self.admin
    self.category, self.course
    self.test, self.questions, self.choices
    """

    def setUp(self) -> None:
        _ensure_arena_badges()
        # -- Users -----------------------------------------------------------
        self.student = User.objects.create_user(
            email="student@test.com",
            password="testpass123",
            first_name="Jasur",
            last_name="Karimov",
            role="student",
            telegram_chat_id=123456789,
        )
        self.teacher = User.objects.create_user(
            email="teacher@test.com",
            password="testpass123",
            first_name="Oqituvchi",
            last_name="Rahimov",
            role="teacher",
        )
        self.admin_user = User.objects.create_superuser(
            email="admin@test.com",
            password="testpass123",
            first_name="Admin",
            last_name="User",
        )

        # -- Course ----------------------------------------------------------
        self.category = Category.objects.create(
            name="Backend Development",
            slug="backend-dev",
        )
        self.course = Course.objects.create(
            title="Django Backend",
            slug="django-backend",
            description="Complete Django backend course",
            teacher=self.teacher,
            category=self.category,
        )

        # -- Test ------------------------------------------------------------
        self.test = Test.objects.create(
            title="Django Quiz 1",
            course=self.course,
            description="Test your Django knowledge",
            time_limit_minutes=30,
            pass_percentage=60,
            max_attempts=3,
            is_active=True,
            shuffle_questions=False,
            shuffle_choices=False,
        )

        # -- Questions -------------------------------------------------------
        self.q1 = Question.objects.create(
            test=self.test,
            text="What is Django?",
            question_type="single",
            points=Decimal("10.00"),
            position=1,
        )
        self.q2 = Question.objects.create(
            test=self.test,
            text="Which are Django apps?",
            question_type="multiple",
            points=Decimal("10.00"),
            position=2,
        )
        self.q3 = Question.objects.create(
            test=self.test,
            text="What does MVC stand for?",
            question_type="single",
            points=Decimal("10.00"),
            position=3,
        )

        # -- Choices for Q1 (single) -----------------------------------------
        self.q1_c1 = Choice.objects.create(
            question=self.q1, text="A web framework", is_correct=True, position=1,
        )
        self.q1_c2 = Choice.objects.create(
            question=self.q1, text="A database", is_correct=False, position=2,
        )
        self.q1_c3 = Choice.objects.create(
            question=self.q1, text="An OS", is_correct=False, position=3,
        )

        # -- Choices for Q2 (multiple) ---------------------------------------
        self.q2_c1 = Choice.objects.create(
            question=self.q2, text="Auth", is_correct=True, position=1,
        )
        self.q2_c2 = Choice.objects.create(
            question=self.q2, text="ORM", is_correct=True, position=2,
        )
        self.q2_c3 = Choice.objects.create(
            question=self.q2, text="Excel", is_correct=False, position=3,
        )

        # -- Choices for Q3 (single) -----------------------------------------
        self.q3_c1 = Choice.objects.create(
            question=self.q3, text="Model View Controller", is_correct=True, position=1,
        )
        self.q3_c2 = Choice.objects.create(
            question=self.q3, text="My Very Cool", is_correct=False, position=2,
        )

    # -- Helper methods ------------------------------------------------------

    def get_jwt_tokens(self, email: str = "student@test.com", password: str = "testpass123") -> dict:
        """JWT token olish."""
        from rest_framework.test import APIClient
        client = APIClient()
        response = client.post(
            "/api/auth/login/",
            {"email": email, "password": password},
            format="json",
        )
        return response.data.get("tokens", {})

    def get_authenticated_client(self, email: str = "student@test.com") -> Any:
        """Authenticated API client yaratish."""
        from rest_framework.test import APIClient
        tokens = self.get_jwt_tokens(email=email)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.get('access', '')}")
        return client
