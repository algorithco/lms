"""
Unit and integration tests for deduplicate_tests command.
"""

from io import StringIO
import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.courses.models import Category, Course
from apps.tests.models import Choice, Question, Test, TestAttempt

User = get_user_model()


@pytest.mark.django_db
class TestDeduplicateTestsCommand:
    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.user = User.objects.create_user(
            email="dedup_user@example.com",
            password="testpassword123",
            role="student",
        )
        self.category = Category.objects.create(name="Test Cat", slug="test-cat")
        self.course = Course.objects.create(
            title="Dedup Course",
            slug="dedup-course",
            category=self.category,
            teacher=self.user,
        )

    def _create_test_with_questions(
        self, title: str, subject: str = "uzbek", mock_code: str | None = None
    ) -> Test:
        test = Test.objects.create(
            title=title,
            subject=subject,
            course=self.course,
            mock_code=mock_code,
            status=Test.Status.PUBLISHED,
        )
        for i in range(1, 4):
            q = Question.objects.create(
                test=test,
                text=f"Question text {i}",
                position=i,
                correct_text="A",
            )
            Choice.objects.create(
                question=q, text="Option A", position=1, is_correct=True
            )
            Choice.objects.create(
                question=q, text="Option B", position=2, is_correct=False
            )
        return test

    def test_distinct_tests_are_never_touched(self):
        t1 = self._create_test_with_questions("Variant 1", "uzbek")
        t2 = self._create_test_with_questions("Variant 2", "uzbek")
        t3 = self._create_test_with_questions(
            "Variant 1", "english"
        )  # different subject

        out = StringIO()
        call_command("deduplicate_tests", stdout=out)

        assert Test.objects.filter(id=t1.id).exists()
        assert Test.objects.filter(id=t2.id).exists()
        assert Test.objects.filter(id=t3.id).exists()
        assert "No duplicate cloned tests detected" in out.getvalue()

    def test_cloned_tests_dry_run_leaves_database_untouched(self):
        t1 = self._create_test_with_questions(
            "Clone Target", "uzbek", mock_code="CLONE-01"
        )
        t2 = self._create_test_with_questions("Clone Target", "uzbek")

        # Create attempt on t2
        TestAttempt.objects.create(
            test=t2, student=self.user, status=TestAttempt.Status.COMPLETED
        )

        out = StringIO()
        call_command("deduplicate_tests", "--dry-run", stdout=out)

        output = out.getvalue()
        assert "DRY-RUN mode" in output
        assert "Would delete 1 clone(s)" in output

        # Both tests should still exist
        assert Test.objects.filter(id=t1.id).exists()
        assert Test.objects.filter(id=t2.id).exists()
        assert TestAttempt.objects.filter(test=t2).count() == 1

    def test_cloned_tests_deduplicated_and_attempts_migrated(self):
        t1 = self._create_test_with_questions(
            "Identical Mock", "uzbek", mock_code="MOCK-PRIMARY"
        )
        t2 = self._create_test_with_questions("Identical Mock", "uzbek")

        # Create attempts on both
        att1 = TestAttempt.objects.create(
            test=t1, student=self.user, status=TestAttempt.Status.COMPLETED
        )
        att2 = TestAttempt.objects.create(
            test=t2, student=self.user, status=TestAttempt.Status.COMPLETED
        )

        out = StringIO()
        call_command("deduplicate_tests", stdout=out)

        output = out.getvalue()
        assert "Successfully eliminated 1 duplicate test(s)" in output

        # t1 should survive, t2 should be deleted
        assert Test.objects.filter(id=t1.id).exists()
        assert not Test.objects.filter(id=t2.id).exists()

        # Both attempts should now be attached to t1
        att1.refresh_from_db()
        att2.refresh_from_db()
        assert att1.test_id == t1.id
        assert att2.test_id == t1.id
        assert t1.attempts.count() == 2

    def test_clone_with_more_attempts_becomes_primary(self):
        # t_low has lower ID but 0 attempts
        t_low = self._create_test_with_questions("Same Exam", "english")
        # t_high has higher ID but 2 attempts
        t_high = self._create_test_with_questions("Same Exam", "english")

        TestAttempt.objects.create(
            test=t_high, student=self.user, status=TestAttempt.Status.COMPLETED
        )
        TestAttempt.objects.create(
            test=t_high, student=self.user, status=TestAttempt.Status.COMPLETED
        )

        out = StringIO()
        call_command("deduplicate_tests", stdout=out)

        # t_high should be the primary survivor because it has more attempts
        assert Test.objects.filter(id=t_high.id).exists()
        assert not Test.objects.filter(id=t_low.id).exists()
        assert t_high.attempts.count() == 2
