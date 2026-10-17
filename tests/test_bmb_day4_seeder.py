from decimal import Decimal
import pytest
from django.core.management import call_command

from apps.tests.bmb_grading import calculate_bmb_grade
from apps.tests.models import Question, Test
from apps.essays.models import EssayTopic
from apps.tests.scoring import normalize_text


@pytest.mark.django_db
class TestBmbDay4SeederAndScoring:
    def test_seeder_execution_and_structure(self):
        # 1. Run seeder command
        call_command("seed_bmb_mock_day4")

        # 2. Verify Test
        test = Test.objects.filter(mock_code="#MOCK-BMB04").first()
        assert test is not None
        assert "Mock #4" in test.title
        assert test.time_limit_minutes == 180
        assert test.is_active is True
        assert test.status == Test.Status.PUBLISHED

        # 3. Verify Sections & Passages
        assert test.sections.count() == 4
        assert test.passages.count() == 3

        # 4. Verify Questions count: 44 + 1 = 45
        questions = list(test.questions.order_by("position"))
        assert len(questions) == 45
        assert questions[0].position == 1
        assert questions[-1].position == 45

        # 5. Verify Passages linkage
        # Questions 18..22 should belong to passage 1 ("Bakteriyalar")
        for q in questions[17:22]:
            assert q.reading_passage is not None
            assert "Bakteriyalar" in q.reading_passage.title

        # Questions 23..27 should belong to passage 2 ("Hushtak")
        for q in questions[22:27]:
            assert q.reading_passage is not None
            assert "Hushtak" in q.reading_passage.title

        # Questions 28..32 should belong to passage 3 (Navoiy Ghazal)
        for q in questions[27:32]:
            assert q.reading_passage is not None
            assert "Navoiy" in q.reading_passage.title

        # 6. Verify Matching items 33, 34, 35
        q33 = questions[32]
        assert q33.position == 33
        assert q33.choices.filter(is_correct=True).exists()

        q34 = questions[33]
        assert q34.position == 34
        assert q34.choices.filter(is_correct=True).exists()

        q35 = questions[34]
        assert q35.position == 35
        assert q35.choices.filter(is_correct=True).exists()

        # 7. Verify Open text questions (Q36..44)
        for q in questions[35:44]:
            assert q.question_type == Question.QuestionType.TEXT_MATCH
            assert len(q.correct_text.strip()) > 0
            assert len(q.explanation.strip()) > 0

        # 8. Verify Task 45 (Written / Essay)
        q45 = questions[44]
        assert q45.question_type == Question.QuestionType.WRITTEN
        assert q45.points == 25
        assert q45.config.get("min_words") == 200
        assert q45.config.get("max_words") == 500

        # 9. Verify EssayTopic was synchronized
        topic = EssayTopic.objects.filter(national_cert_scale=True).first()
        assert topic is not None
        assert "Mock #4" in topic.title

    def test_pipe_separated_text_match_evaluation(self):
        call_command("seed_bmb_mock_day4")
        test = Test.objects.get(mock_code="#MOCK-BMB04")
        q36 = test.questions.get(position=36)

        # q36 correct_text: "ora | orasi | orasidan | orasiga"
        raw_keys = (q36.correct_text or "").split("|")
        accepted_keys = [normalize_text(k) for k in raw_keys if k.strip()]

        for valid_response in ["ora", "  ORA ", "Orasi", "ORASIDAN"]:
            student_norm = normalize_text(valid_response)
            assert any(student_norm == k for k in accepted_keys)

        for invalid_response in ["boshqa", "noto'g'ri", ""]:
            student_norm = normalize_text(invalid_response)
            assert not any(student_norm == k for k in accepted_keys)

    def test_bmb_aggregate_rasch_grading(self):
        # 44 test questions (say 80/88) + 25 essay (say 22/25)
        # Total possible: 88 + 25 = 113. Earned: 80 + 22 = 102. Pct: 102/113 = 90.26% -> A+
        grade_info = calculate_bmb_grade(
            test_score=Decimal("80"),
            test_max=Decimal("88"),
            essay_score=Decimal("22"),
            essay_max=Decimal("25"),
        )
        assert grade_info["grade"] == "A+"
        assert grade_info["is_passed"] is True
        assert grade_info["percentage"] > 90.0

        # Lower score: 40/88 test + 10/25 essay = 50/113 = 44.25% -> Fail
        fail_grade = calculate_bmb_grade(
            test_score=Decimal("40"),
            test_max=Decimal("88"),
            essay_score=Decimal("10"),
            essay_max=Decimal("25"),
        )
        assert fail_grade["grade"] == "Fail"
        assert fail_grade["is_passed"] is False
