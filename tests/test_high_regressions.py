"""Contract tests for the repaired High-severity test and grading paths."""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.certificates.services.anti_fraud import generate_and_store_checksum
from apps.courses.models import Category, Course, StudentGroup
from apps.essays.models import EssaySubmission, EssayTopic
from apps.essays.services import TeacherReviewService, _compute_text_hash, _validate_result
from apps.results.models import Certificate, CertificateNumberCounter, Result
from apps.tests.models import Choice, Question, StudentAnswer, Test, TestAttempt
from apps.tests.services import SaveAnswerService, SubmitAttemptService
from apps.tests.bulk_import import BulkTestImportService

User = get_user_model()


class TestSubmissionRegressionTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            email="flow-teacher@example.com", password="pass", role="teacher",
        )
        self.student = User.objects.create_user(
            email="flow-student@example.com", password="pass", role="student",
        )
        self.other_student = User.objects.create_user(
            email="other-student@example.com", password="pass", role="student",
        )
        category = Category.objects.create(name="High regression")
        self.course = Course.objects.create(
            teacher=self.teacher, category=category, title="Secure course", description="",
        )
        self.test = Test.objects.create(
            course=self.course, title="Secure test", time_limit_minutes=10,
            pass_percentage=60,
        )
        self.question = Question.objects.create(
            test=self.test, text="One plus one?", position=1,
        )
        self.correct = Choice.objects.create(question=self.question, text="Two", is_correct=True)
        self.wrong = Choice.objects.create(question=self.question, text="Three")
        self.second = Question.objects.create(
            test=self.test, text="Three plus one?", position=2,
        )
        self.second_choice = Choice.objects.create(
            question=self.second, text="Four", is_correct=True,
        )
        token = str(RefreshToken.for_user(self.student).access_token)
        self.header = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_tma_start_answer_submit_and_result_contract(self):
        start = self.client.post(
            f"/tma/api/tests/{self.test.pk}/start/", data="{}",
            content_type="application/json", **self.header,
        )
        self.assertEqual(start.status_code, 200)
        attempt_id = start.json()["attempt_id"]
        answer = self.client.post(
            f"/tma/api/tests/{self.test.pk}/answer/",
            data=f'{{"attempt_id":{attempt_id},"question_id":{self.question.pk},"choice_ids":[{self.correct.pk}]}}',
            content_type="application/json", **self.header,
        )
        self.assertEqual(answer.status_code, 200)
        submit = self.client.post(
            f"/tma/api/tests/{self.test.pk}/submit/",
            data=f'{{"attempt_id":{attempt_id},"answers":{{"{self.second.pk}":[{self.second_choice.pk}]}}}}',
            content_type="application/json", **self.header,
        )
        self.assertEqual(submit.status_code, 200)
        self.assertEqual(submit.json()["correct_answers"], 2)
        self.assertTrue(submit.json()["is_passed"])
        result = self.client.get(
            f"/tma/api/attempts/{attempt_id}/result/", **self.header,
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["result_id"], submit.json()["result_id"])

    def test_tma_rejects_cross_question_choice_and_rolls_back_batch(self):
        attempt = TestAttempt.objects.create(test=self.test, student=self.student)
        response = self.client.post(
            f"/tma/api/tests/{self.test.pk}/submit/",
            data=(
                f'{{"attempt_id":{attempt.pk},"answers":{{'
                f'"{self.question.pk}":[{self.correct.pk}],'
                f'"{self.second.pk}":[{self.wrong.pk}]}}}}'
            ),
            content_type="application/json", **self.header,
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(StudentAnswer.objects.filter(attempt=attempt).exists())
        self.assertFalse(Result.objects.filter(attempt=attempt).exists())

    def test_tma_cannot_read_another_students_result(self):
        attempt = TestAttempt.objects.create(test=self.test, student=self.other_student)
        response = self.client.get(
            f"/tma/api/attempts/{attempt.pk}/result/", **self.header,
        )
        self.assertEqual(response.status_code, 404)

    def test_group_edit_and_bulk_import_use_valid_backend_paths(self):
        group = StudentGroup.objects.create(teacher=self.teacher, name="Original")
        self.client.force_login(self.teacher)
        response = self.client.post(
            f"/groups/{group.pk}/edit/",
            {"name": "Updated", "description": "", "students": [self.student.pk]},
        )
        self.assertEqual(response.status_code, 302)
        group.refresh_from_db()
        self.assertEqual(group.name, "Updated")
        self.assertTrue(group.students.filter(pk=self.student.pk).exists())

        csv = "question,choice_a,choice_b,correct,points\nTwo plus two?,3,4,B,1\n"
        imported = BulkTestImportService.import_test(
            csv, "Imported", self.course.pk, created_by=self.teacher,
        )
        self.assertTrue(imported["success"], imported["errors"])
        question = Question.objects.get(test_id=imported["test_id"])
        self.assertEqual(question.question_type, Question.QuestionType.SINGLE_CHOICE)

    def test_bulk_import_rejects_unrelated_teacher_at_service_layer(self):
        outsider = User.objects.create_user(
            email="outsider@example.com", password="pass", role="teacher",
        )
        csv = "question,choice_a,choice_b,correct\nTwo plus two?,3,4,B\n"
        denied = BulkTestImportService.import_test(
            csv, "Unauthorized", self.course.pk, created_by=outsider,
        )
        self.assertFalse(denied["success"])
        self.assertFalse(Test.objects.filter(title="Unauthorized").exists())

    def test_timed_save_commits_timeout_and_result(self):
        attempt = TestAttempt.objects.create(test=self.test, student=self.student)
        TestAttempt.objects.filter(pk=attempt.pk).update(
            started_at=timezone.now() - timedelta(minutes=11),
        )
        with self.assertRaisesRegex(ValueError, "Vaqt tugadi"):
            SaveAnswerService.execute(
                attempt.pk, self.question.pk, [self.correct.pk], self.student,
            )
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, TestAttempt.Status.TIMEOUT)
        self.assertTrue(Result.objects.filter(attempt=attempt).exists())

    def test_tma_timeout_commits_even_when_batch_rolls_back(self):
        attempt = TestAttempt.objects.create(test=self.test, student=self.student)
        TestAttempt.objects.filter(pk=attempt.pk).update(
            started_at=timezone.now() - timedelta(minutes=11),
        )
        response = self.client.post(
            f"/tma/api/tests/{self.test.pk}/submit/",
            data=f'{{"attempt_id":{attempt.pk},"answers":{{"{self.question.pk}":[{self.correct.pk}]}}}}',
            content_type="application/json", **self.header,
        )
        self.assertEqual(response.status_code, 408)
        self.assertTrue(response.json()["time_expired"])
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, TestAttempt.Status.TIMEOUT)
        self.assertTrue(Result.objects.filter(attempt=attempt).exists())

    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    def test_result_task_is_dispatched_only_on_commit(self):
        attempt = TestAttempt.objects.create(test=self.test, student=self.student)
        from unittest.mock import patch
        with patch("apps.notifications.tasks.process_test_result_task.delay") as delay:
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                SubmitAttemptService.execute(attempt.pk, self.student)
                delay.assert_not_called()
            self.assertTrue(callbacks)
            delay.assert_called_once()

    def test_certificate_counter_does_not_reuse_deleted_number(self):
        attempt = TestAttempt.objects.create(test=self.test, student=self.student)
        result = Result.objects.create(
            attempt=attempt, student=self.student, test=self.test,
            course=self.course, total_questions=0, correct_answers=0,
            wrong_answers=0, score=0, max_score=0, percentage=0,
            is_passed=False, time_taken_seconds=0,
        )
        first = Certificate.objects.create(
            result=result, student=self.student, test=self.test, course=self.course,
        )
        first_number = first.certificate_number
        first.delete()
        second = Certificate.objects.create(
            result=result, student=self.student, test=self.test, course=self.course,
        )
        self.assertGreater(int(second.certificate_number[-6:]), int(first_number[-6:]))
        self.assertGreater(CertificateNumberCounter.objects.get(year=timezone.now().year).last_value, 1)

    def test_certificate_verification_reflects_checksum(self):
        attempt = TestAttempt.objects.create(test=self.test, student=self.student)
        result = Result.objects.create(
            attempt=attempt, student=self.student, test=self.test,
            course=self.course, total_questions=2, correct_answers=2,
            wrong_answers=0, score=2, max_score=2, percentage=100,
            is_passed=True, time_taken_seconds=1,
        )
        certificate = Certificate.objects.create(
            result=result, student=self.student, test=self.test,
            course=self.course, status=Certificate.Status.GENERATED,
        )
        url = f"/api/certificates/verify/{certificate.certificate_number}/"
        self.assertEqual(self.client.get(url).status_code, 422)
        generate_and_store_checksum(certificate)
        self.assertTrue(self.client.get(url).json()["valid"])
        result.percentage = Decimal("50")
        result.save(update_fields=["percentage"])
        invalid = self.client.get(url)
        self.assertEqual(invalid.status_code, 422)
        self.assertFalse(invalid.json()["valid"])
        self.assertEqual(self.client.get(url).status_code, 422)
        page = self.client.get(
            f"/certificates/verify/{certificate.certificate_number}/"
        )
        # Direct-backend QR landing renders inline HTML (no page templates).
        self.assertEqual(page.status_code, 200)
        self.assertIn("topilmadi", page.content.decode())

    def test_existing_certificate_checksum_backfill_matches_live_verifier(self):
        import importlib
        from types import SimpleNamespace
        from django.apps import apps
        from django.db import connection
        from apps.certificates.services.anti_fraud import verify_certificate_checksum

        attempt = TestAttempt.objects.create(test=self.test, student=self.student)
        result = Result.objects.create(
            attempt=attempt, student=self.student, test=self.test,
            course=self.course, total_questions=1, correct_answers=1,
            wrong_answers=0, score=1, max_score=1, percentage=100,
            is_passed=True, time_taken_seconds=1,
        )
        certificate = Certificate.objects.create(
            result=result, student=self.student, test=self.test,
            course=self.course, status=Certificate.Status.GENERATED,
        )
        migration = importlib.import_module(
            "apps.results.migrations.0004_certificate_sequence_and_checksums"
        )
        migration.prepare_certificates(apps, SimpleNamespace(connection=connection))
        certificate.refresh_from_db()
        self.assertTrue(verify_certificate_checksum(certificate)["valid"])


class EssayAndScheduleRegressionTests(TestCase):
    def test_teacher_appeal_from_graded_state_is_atomic_and_owned(self):
        student = User.objects.create_user(email="appeal-student@example.com", password="pass")
        teacher = User.objects.create_user(email="appeal-teacher@example.com", password="pass", role="teacher")
        topic = EssayTopic.objects.create(title="Appeal", description="", created_by=teacher)
        submission = EssaySubmission.objects.create(
            student=student, topic=topic, essay_text="Essay text",
            status=EssaySubmission.Status.GRADED,
        )
        TeacherReviewService.request_teacher_review(submission, student, "Check rubric")
        submission.refresh_from_db()
        self.assertEqual(submission.status, EssaySubmission.Status.PENDING_TEACHER)
        self.assertTrue(submission.teacher_review_requested)
        self.assertEqual(submission.teacher_review_reason, "Check rubric")
        review = TeacherReviewService.submit_review(
            submission, teacher, {i: 1 for i in range(1, 13)},
        )
        submission.refresh_from_db()
        self.assertEqual(submission.status, EssaySubmission.Status.TEACHER_REVIEWED)
        self.assertEqual(submission.final_score, Decimal("12"))
        self.assertEqual(review.teacher_id, teacher.pk)

    def test_ai_scoring_rejects_duplicate_and_nonfinite_criteria(self):
        criteria = [
            {"id": i, "name": f"Criterion {i}", "score": 1, "reason": "OK"}
            for i in range(1, 13)
        ]
        payload = {"criteria": criteria, "total_score": 999, "max_score": 0, "summary": "OK"}
        _validate_result(payload)
        self.assertEqual(payload["total_score"], 12.0)
        self.assertEqual(payload["max_score"], 24)
        criteria[11]["id"] = 1
        with self.assertRaises(ValueError):
            _validate_result(payload)
        criteria[11]["id"] = 12
        criteria[0]["score"] = "NaN"
        with self.assertRaises(ValueError):
            _validate_result(payload)

    def test_cache_key_separates_model_prompt_rubric_and_mode(self):
        base = dict(provider="groq", model="model-a", mock_mode=False,
                    prompt_version="v1", rubric_digest="digest-a", language="uz")
        original = _compute_text_hash("Essay", "Topic", **base)
        for field, replacement in (
            ("provider", "openrouter"), ("model", "model-b"),
            ("mock_mode", True), ("prompt_version", "v2"),
            ("rubric_digest", "digest-b"), ("language", "ru"),
        ):
            changed = {**base, field: replacement}
            self.assertNotEqual(original, _compute_text_hash("Essay", "Topic", **changed))

    def test_every_beat_task_resolves_and_schedule_is_valid(self):
        from celery.schedules import crontab, schedule
        from config.celery import app
        app.autodiscover_tasks(force=True)
        for name, entry in settings.CELERY_BEAT_SCHEDULE.items():
            with self.subTest(entry=name):
                self.assertIn(entry["task"], app.tasks)
                self.assertTrue(isinstance(entry["schedule"], (int, float, schedule, crontab)))
