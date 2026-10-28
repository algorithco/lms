"""
Unit and integration tests for deduplicate_by_questions command.
Verifies that tests are deduplicated strictly by question content regardless of test titles.
"""

from io import StringIO
import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.courses.models import Category, Course
from apps.results.models import Certificate, Result
from apps.tests.models import Choice, Question, StudentAnswer, Test, TestAttempt

User = get_user_model()


@pytest.mark.django_db
class TestDeduplicateByQuestionsCommand:
    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.user = User.objects.create_user(
            email="dedup_q_user@example.com",
            password="testpassword123",
            role="student",
        )
        self.category = Category.objects.create(name="Q Cat", slug="q-cat")
        self.course = Course.objects.create(
            title="Q Course",
            slug="q-course",
            category=self.category,
            teacher=self.user,
        )

    def _create_test_with_specific_questions(
        self,
        title: str,
        question_texts: list[str],
        subject: str = "uzbek",
        mock_code: str | None = None,
    ) -> Test:
        test = Test.objects.create(
            title=title,
            subject=subject,
            course=self.course,
            mock_code=mock_code,
            status=Test.Status.PUBLISHED,
        )
        for i, text in enumerate(question_texts, 1):
            q = Question.objects.create(
                test=test,
                text=text,
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

    def test_tests_with_different_titles_but_identical_questions_are_deduplicated(self):
        identical_questions = [
            "1-savol. Urg'u va tovushlar mutanosibligi bo'yicha to'g'ri variantni toping.",
            "2-savol. Fonetika: jarangli undoshlar qatorini aniqlang.",
            "3-savol. Qo'shma so'zlarning to'g'ri yozilishi qoidasi.",
            "4-savol. Fe'l nisbatlari tahlili.",
            "5-savol. Navoiy dostonlari kompozitsiyasi.",
        ]

        t1 = self._create_test_with_specific_questions(
            "BMB Rasmiy Mock Test", identical_questions, "uzbek", mock_code="#MOCK-BMB-DIAGNOSTIC"
        )
        t2 = self._create_test_with_specific_questions(
            "BMB Milliy Sertifikat (Variant 1)", identical_questions, "uzbek", mock_code="BMB-101"
        )
        t3 = self._create_test_with_specific_questions(
            "BMB Milliy Sertifikat (Variant 2)", identical_questions, "uzbek", mock_code="BMB-102"
        )

        # Create 2 attempts on t1, 1 attempt on t2
        TestAttempt.objects.create(test=t1, student=self.user, status=TestAttempt.Status.COMPLETED)
        TestAttempt.objects.create(test=t1, student=self.user, status=TestAttempt.Status.COMPLETED)
        TestAttempt.objects.create(test=t2, student=self.user, status=TestAttempt.Status.COMPLETED)

        out = StringIO()
        call_command("deduplicate_by_questions", stdout=out)
        output = out.getvalue()

        assert "Found 1 test group(s) with duplicate cloned questions." in output
        assert f"PRIMARY CANONICAL] ID: {t1.id}" in output
        assert f"CLONE TO MERGE] ID: {t2.id}" in output
        assert f"CLONE TO MERGE] ID: {t3.id}" in output

        # t1 should remain as canonical primary
        assert Test.objects.filter(id=t1.id).exists()
        # t2 and t3 should be merged and deleted
        assert not Test.objects.filter(id=t2.id).exists()
        assert not Test.objects.filter(id=t3.id).exists()

        # All 3 attempts should now be under t1
        assert TestAttempt.objects.filter(test=t1).count() == 3

    def test_distinct_tests_with_different_questions_are_never_touched(self):
        questions_set_a = [
            "Savol A1. Matematik analiz asoslari.",
            "Savol A2. Integrallar turlari.",
            "Savol A3. Limitlar va hosilalar.",
        ]
        questions_set_b = [
            "Savol B1. Kimyoviy reaksiyalar kinetikasi.",
            "Savol B2. Mendeleyev davriy qonuni.",
            "Savol B3. Organik birikmalar tuzilishi.",
        ]

        t1 = self._create_test_with_specific_questions(
            "Matematika Testi", questions_set_a, "uzbek"
        )
        t2 = self._create_test_with_specific_questions(
            "Kimyo Testi", questions_set_b, "uzbek"
        )

        out = StringIO()
        call_command("deduplicate_by_questions", stdout=out)
        output = out.getvalue()

        assert "No duplicate cloned tests detected" in output
        assert Test.objects.filter(id=t1.id).exists()
        assert Test.objects.filter(id=t2.id).exists()

    def test_dry_run_leaves_all_records_intact(self):
        identical_questions = [
            "Q1. Reading passage analysis.",
            "Q2. Main idea of the paragraph.",
            "Q3. Vocabulary in context.",
            "Q4. Inference question.",
            "Q5. Author attitude.",
        ]

        t1 = self._create_test_with_specific_questions(
            "Cambridge Mock 1", identical_questions, "english", mock_code="IELTS-201"
        )
        t2 = self._create_test_with_specific_questions(
            "Cambridge Mock 2", identical_questions, "english", mock_code="IELTS-202"
        )

        out = StringIO()
        call_command("deduplicate_by_questions", "--dry-run", stdout=out)
        output = out.getvalue()

        assert "DRY-RUN mode" in output
        assert "Would delete 1 clone(s)" in output

        # Both tests must still exist
        assert Test.objects.filter(id=t1.id).exists()
        assert Test.objects.filter(id=t2.id).exists()

    def test_student_answers_and_results_preserved_on_primary(self):
        identical_questions = [
            "1-savol. Urg'u qoidasi.",
            "2-savol. Jarangsiz undoshlar.",
            "3-savol. Imlo qoidasi.",
        ]

        t1 = self._create_test_with_specific_questions("Test Alpha", identical_questions)
        t2 = self._create_test_with_specific_questions("Test Beta", identical_questions)

        # Give t1 2 attempts so t1 is canonical primary, and t2 1 attempt so t2 is merged
        TestAttempt.objects.create(test=t1, student=self.user, status=TestAttempt.Status.COMPLETED)
        TestAttempt.objects.create(test=t1, student=self.user, status=TestAttempt.Status.COMPLETED)

        # Create attempt and answer on t2
        att = TestAttempt.objects.create(test=t2, student=self.user, status=TestAttempt.Status.COMPLETED)
        t2_q1 = t2.questions.first()
        t2_c1 = t2_q1.choices.first()
        sa = StudentAnswer.objects.create(attempt=att, question=t2_q1, text_answer="A")
        sa.selected_choices.add(t2_c1)
        res = Result.objects.create(
            attempt=att,
            test=t2,
            student=self.user,
            course=self.course,
            total_questions=3,
            correct_answers=3,
            wrong_answers=0,
            score=3,
            max_score=3,
            percentage=100,
            is_passed=True,
        )
        cert = Certificate.objects.create(
            student=self.user,
            result=res,
            test=t2,
            course=self.course,
            certificate_number="CERT-1234",
        )

        call_command("deduplicate_by_questions")

        # t2 deleted
        assert not Test.objects.filter(id=t2.id).exists()
        assert Test.objects.filter(id=t1.id).exists()

        # Attempt, result, and certificate now point to t1
        att.refresh_from_db()
        assert att.test_id == t1.id

        res.refresh_from_db()
        assert res.test_id == t1.id

        cert.refresh_from_db()
        assert cert.test_id == t1.id

        # StudentAnswer now points to t1's corresponding question
        sa.refresh_from_db()
        assert sa.question.test_id == t1.id
        assert sa.question.position == t2_q1.position
