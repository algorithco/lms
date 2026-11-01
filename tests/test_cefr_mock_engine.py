import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from apps.tests.models import (
    Test,
    Question,
    Choice,
    TestAttempt,
    StudentAnswer,
)
from apps.tests.services import SaveAnswerService, SubmitAttemptService
from apps.tests.serializers import AttemptDetailSerializer

User = get_user_model()


@pytest.mark.django_db
class TestCefrMockEngine:
    def test_seed_cefr_mock_1_populates_all_sections_and_questions(self):
        """Verify seed_cefr_mock_1 seeds all 35L + 35R + 3W + 4S items with exact keys."""
        call_command("seed_cefr_mock_1", reset=True)

        test = Test.objects.filter(mock_code="CEFR-RECORD-1").first()
        assert test is not None
        assert test.title == "Record Mock – Test 1 (Multi-Level CEFR & IELTS)"
        assert test.subject == "english"
        assert test.exam_type == Test.ExamType.CEFR_MULTILEVEL

        sections = {s.code: s for s in test.sections.all()}
        assert "LISTENING" in sections
        assert "READING" in sections
        assert "WRITING" in sections
        assert "SPEAKING" in sections

        listening_qs = test.questions.filter(section=sections["LISTENING"]).order_by("position")
        assert listening_qs.count() == 35

        reading_qs = test.questions.filter(section=sections["READING"]).order_by("position")
        assert reading_qs.count() == 35

        writing_qs = test.questions.filter(section=sections["WRITING"]).order_by("position")
        assert writing_qs.count() == 3

        speaking_qs = test.questions.filter(section=sections["SPEAKING"]).order_by("position")
        assert speaking_qs.count() == 4

        assert test.questions.count() == 77

    def test_listening_part4_map_labeling_keys(self):
        """Verify Map Labeling questions 19-23 have correct room keys D, C, A, E, H."""
        call_command("seed_cefr_mock_1")
        test = Test.objects.get(mock_code="CEFR-RECORD-1")
        sec_l = test.sections.get(code="LISTENING")

        expected_map = {
            19: ("Bike racks", "Room D"),
            20: ("Kitchen room", "Room C"),
            21: ("Music room", "Room A"),
            22: ("Shower room", "Room E"),
            23: ("Restroom", "Room H"),
        }

        for pos, (place, expected_choice) in expected_map.items():
            q = test.questions.get(section=sec_l, position=pos)
            assert q.config.get("subtype") == "map_labeling"
            correct_choice = q.choices.get(is_correct=True)
            assert correct_choice.text == expected_choice

    def test_reading_part4_tfng_keys(self):
        """Verify True / False / No Information questions 25-29."""
        call_command("seed_cefr_mock_1")
        test = Test.objects.get(mock_code="CEFR-RECORD-1")
        sec_r = test.sections.get(code="READING")

        expected_tfng = {
            25: "False",
            26: "True",
            27: "No Information",
            28: "True",
            29: "No Information",
        }

        for pos, expected_val in expected_tfng.items():
            q = test.questions.get(section=sec_r, position=pos)
            assert q.config.get("subtype") == "tfng"
            correct_choice = q.choices.get(is_correct=True)
            assert correct_choice.text == expected_val

    def test_student_serializer_hides_correct_answers_but_includes_config(self):
        """Student payload must include config and passage, but never reveal is_correct."""
        call_command("seed_cefr_mock_1")
        test = Test.objects.get(mock_code="CEFR-RECORD-1")
        student = User.objects.create_user(
            email="candidate_cefr@example.com",
            password="pass",
            first_name="Candidate",
            role="student",
        )

        attempt = TestAttempt.objects.create(
            test=test,
            student=student,
            status=TestAttempt.Status.IN_PROGRESS,
        )

        serializer = AttemptDetailSerializer(attempt)
        data = serializer.data
        assert "questions" in data
        assert len(data["questions"]) == 77

        for q_payload in data["questions"]:
            assert "config" in q_payload
            for choice in q_payload.get("choices", []):
                assert "is_correct" not in choice

    def test_attempt_save_and_submit_flow(self):
        """Simulate student taking exam and auto-grading responses."""
        call_command("seed_cefr_mock_1")
        test = Test.objects.get(mock_code="CEFR-RECORD-1")
        sec_r = test.sections.get(code="READING")
        student = User.objects.create_user(
            email="tester_grade@example.com",
            password="pass",
            first_name="Tester",
            role="student",
        )

        attempt = TestAttempt.objects.create(
            test=test,
            student=student,
            status=TestAttempt.Status.IN_PROGRESS,
        )

        # Answer Q25 correctly (False)
        q25 = test.questions.get(section=sec_r, position=25)
        c_false = q25.choices.get(text="False")
        SaveAnswerService.execute(
            attempt_id=attempt.id,
            student=student,
            question_id=q25.id,
            choice_ids=[c_false.id],
        )

        ans25 = StudentAnswer.objects.get(attempt=attempt, question=q25)
        assert c_false in ans25.selected_choices.all()

        # Submit attempt
        result = SubmitAttemptService.execute(
            attempt_id=attempt.id,
            student=student,
        )

        attempt.refresh_from_db()
        assert attempt.status == TestAttempt.Status.COMPLETED
        ans25.refresh_from_db()
        assert ans25.is_correct is True
