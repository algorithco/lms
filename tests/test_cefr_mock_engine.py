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

    def test_start_attempt_returns_existing_active_attempt_idempotently(self):
        """When an unexpired attempt is in progress, starting again safely returns the same attempt."""
        from apps.tests.services import StartAttemptService

        call_command("seed_cefr_mock_1")
        test = Test.objects.get(mock_code="CEFR-RECORD-1")
        student = User.objects.create_user(
            email="reentrant_student@example.com",
            password="pass",
            role="student",
        )

        att1 = StartAttemptService.execute(test_id=test.id, student=student)
        assert att1 is not None
        assert att1.status == TestAttempt.Status.IN_PROGRESS

        # Re-start without error
        att2 = StartAttemptService.execute(test_id=test.id, student=student)
        assert att2.id == att1.id

    def test_result_stats_includes_essays_and_zero_state(self):
        """Result stats view must return 0-state safely including total_essays_submitted."""
        from rest_framework.test import APIRequestFactory, force_authenticate
        from apps.results.views import ResultStatsView

        student = User.objects.create_user(
            email="new_stats_user@example.com",
            password="pass",
            role="student",
        )

        factory = APIRequestFactory()
        request = factory.get("/api/results/stats/")
        force_authenticate(request, user=student)

        view = ResultStatsView.as_view()
        response = view(request)

        assert response.status_code == 200
        data = response.data
        assert data["total_tests_taken"] == 0
        assert data["total_essays_submitted"] == 0
        assert data["average_percentage"] == 0.0

    def test_admin_and_teacher_can_start_and_preview_attempt(self):
        """Admin and Teacher must be permitted to start, preview, and submit attempts."""
        from rest_framework.test import APIRequestFactory, force_authenticate
        from apps.tests.views import StartAttemptView, AttemptDetailView, SaveAnswerView, SubmitAttemptView

        call_command("seed_cefr_mock_1")
        test = Test.objects.filter(mock_code="CEFR-RECORD-1").first()
        assert test is not None

        admin = User.objects.create_user(
            email="preview_admin@example.com",
            password="pass",
            role="admin",
            is_staff=True,
            is_superuser=True,
        )
        teacher = User.objects.create_user(
            email="preview_teacher@example.com",
            password="pass",
            role="teacher",
        )

        factory = APIRequestFactory()

        # 1. Admin can start attempt (no 403 Student access required)
        req_admin = factory.post(f"/api/tests/{test.id}/start/", {}, format="json")
        force_authenticate(req_admin, user=admin)
        res_admin = StartAttemptView.as_view()(req_admin, test_id=test.id)
        assert res_admin.status_code == 201
        admin_attempt_id = res_admin.data["id"]

        # 2. Teacher can start attempt
        req_teacher = factory.post(f"/api/tests/{test.id}/start/", {}, format="json")
        force_authenticate(req_teacher, user=teacher)
        res_teacher = StartAttemptView.as_view()(req_teacher, test_id=test.id)
        assert res_teacher.status_code == 201
        teacher_attempt_id = res_teacher.data["id"]

        # 3. Teacher can view detail/timer
        req_detail = factory.get(f"/api/tests/attempts/{teacher_attempt_id}/")
        force_authenticate(req_detail, user=teacher)
        res_detail = AttemptDetailView.as_view()(req_detail, pk=teacher_attempt_id)
        assert res_detail.status_code == 200

        # 4. Teacher can save answer
        question = test.questions.filter(question_type=Question.QuestionType.MULTIPLE_CHOICE).first()
        choice = question.choices.first()
        req_ans = factory.post(
            f"/api/tests/attempts/{teacher_attempt_id}/save-answer/",
            {"question_id": question.id, "choice_ids": [choice.id]},
            format="json",
        )
        force_authenticate(req_ans, user=teacher)
        res_ans = SaveAnswerView.as_view()(req_ans, attempt_id=teacher_attempt_id)
        assert res_ans.status_code == 200

        # 5. Teacher can submit
        req_sub = factory.post(f"/api/tests/attempts/{teacher_attempt_id}/submit/", {}, format="json")
        force_authenticate(req_sub, user=teacher)
        res_sub = SubmitAttemptView.as_view()(req_sub, attempt_id=teacher_attempt_id)
        assert res_sub.status_code == 200
        assert TestAttempt.objects.get(id=teacher_attempt_id).status in [TestAttempt.Status.COMPLETED, TestAttempt.Status.PENDING_GRADING]
