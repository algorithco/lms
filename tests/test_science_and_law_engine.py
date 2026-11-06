import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model
from apps.courses.models import Course, Category, Subject
from apps.tests.models import Test, Question, Choice, TestAttempt, StudentAnswer
from apps.tests.services import SaveAnswerService, SubmitAttemptService
from apps.tests.ai_tutor import _detect_question_topic

User = get_user_model()


@pytest.mark.django_db
class TestScienceAndLawEngine:
    def setup_method(self):
        self.student = User.objects.create_user(
            email="science_student@grandec.uz",
            password="Password123!",
            first_name="Science",
            last_name="Tester",
        )
        self.teacher = User.objects.create_user(
            email="science_teacher@grandec.uz",
            password="Password123!",
            first_name="Teacher",
            last_name="BioChem",
            role="teacher",
        )
        self.cat = Category.objects.create(name="Science", slug="science-test-cat")
        self.course = Course.objects.create(
            title="Science Course",
            slug="science-course",
            teacher=self.teacher,
            category=self.cat,
            subject="chemistry",
        )

    def test_multi_subject_models(self):
        """Verify biology, chemistry, and law subjects are accepted in models."""
        for subj in ("biology", "chemistry", "law"):
            test = Test.objects.create(
                course=self.course,
                title=f"{subj.capitalize()} Test",
                subject=subj,
                time_limit_minutes=60,
            )
            assert test.subject == subj
            self.student.profile.active_subject = subj
            self.student.profile.save()
            self.student.profile.refresh_from_db()
            assert self.student.profile.active_subject == subj

    def test_dual_open_calc_grading_both_correct(self):
        """Verify DUAL_OPEN_CALC awards full points when both part a and b are correct."""
        test = Test.objects.create(
            course=self.course,
            title="Chem Calculation Test",
            subject="chemistry",
            time_limit_minutes=60,
        )
        q = Question.objects.create(
            test=test,
            text="Stexiometrik masala:\na) massani toping\nb) hajmni toping",
            question_type=Question.QuestionType.DUAL_OPEN_CALC,
            points=4,
            correct_text="29.25;29,25|0.5;0,5",
            position=1,
        )

        attempt = TestAttempt.objects.create(
            test=test,
            student=self.student,
            status=TestAttempt.Status.IN_PROGRESS,
        )

        # Student provides exact or comma-separated answers
        ans = SaveAnswerService.execute(
            attempt_id=attempt.id,
            question_id=q.id,
            choice_ids=[],
            student=self.student,
            text_answer="29,25|0.5",
        )
        assert ans.text_answer == "29,25|0.5"

        result = SubmitAttemptService.execute(attempt.id, self.student)
        assert result.score == Decimal("4")
        assert result.is_passed is True

    def test_dual_open_calc_grading_partial_credit(self):
        """Verify DUAL_OPEN_CALC awards half points when only part a is correct."""
        test = Test.objects.create(
            course=self.course,
            title="Bio Genetics Calculation",
            subject="biology",
            time_limit_minutes=60,
        )
        q = Question.objects.create(
            test=test,
            text="Genetika masalasi: a) foizni toping; b) sinflar soni",
            question_type=Question.QuestionType.DUAL_OPEN_CALC,
            points=4,
            correct_text="6.25|4",
            position=1,
        )

        attempt = TestAttempt.objects.create(
            test=test,
            student=self.student,
            status=TestAttempt.Status.IN_PROGRESS,
        )

        # Student gets part a right, part b wrong
        SaveAnswerService.execute(
            attempt_id=attempt.id,
            question_id=q.id,
            choice_ids=[],
            student=self.student,
            text_answer="6.25|999",
        )

        result = SubmitAttemptService.execute(attempt.id, self.student)
        assert result.score == Decimal("2")

    def test_matching_matrix_grading(self):
        """Verify MATCHING_MATRIX evaluates row-to-column pairs."""
        test = Test.objects.create(
            course=self.course,
            title="Matching Matrix Test",
            subject="law",
            time_limit_minutes=60,
        )
        q = Question.objects.create(
            test=test,
            text="1-3 savollarni A-F variantlariga moslashtiring",
            question_type=Question.QuestionType.MATCHING_MATRIX,
            points=3,
            correct_text="1-A, 2-B, 3-C",
            position=1,
        )

        attempt = TestAttempt.objects.create(
            test=test,
            student=self.student,
            status=TestAttempt.Status.IN_PROGRESS,
        )

        # 2 out of 3 correct
        SaveAnswerService.execute(
            attempt_id=attempt.id,
            question_id=q.id,
            choice_ids=[],
            student=self.student,
            text_answer="1-A, 2-B, 3-D",
        )

        result = SubmitAttemptService.execute(attempt.id, self.student)
        # 2 / 3 * 3 = 2 points
        assert result.score == Decimal("2")

    def test_legal_case_study_grading(self):
        """Verify LEGAL_CASE_STUDY grades choices accurately."""
        test = Test.objects.create(
            course=self.course,
            title="Legal Case Study Test",
            subject="law",
            time_limit_minutes=60,
        )
        q = Question.objects.create(
            test=test,
            text="Kazus tahlili: Noutbuk oldi-sotdisi",
            question_type=Question.QuestionType.LEGAL_CASE_STUDY,
            points=3,
            position=1,
        )
        c1 = Choice.objects.create(question=q, text="Bitim bekor qilinadi", is_correct=True)
        Choice.objects.create(question=q, text="Bitim qonuniy", is_correct=False)

        attempt = TestAttempt.objects.create(
            test=test,
            student=self.student,
            status=TestAttempt.Status.IN_PROGRESS,
        )

        SaveAnswerService.execute(
            attempt_id=attempt.id,
            question_id=q.id,
            choice_ids=[c1.id],
            student=self.student,
        )

        result = SubmitAttemptService.execute(attempt.id, self.student)
        assert result.score == Decimal("3")
        assert result.correct_answers == 1

    def test_ai_tutor_topic_detection_for_new_subjects(self):
        """Verify AI Tutor correctly categorizes Biology, Chemistry, and Law topics."""
        # Biology
        topic_bio1 = _detect_question_topic(
            "Mitoz bo'linish va hujayra organoidlari mitoxondriya DNKsi",
            subject="biology",
        )
        assert topic_bio1 == "Sitologiya va hujayra"

        topic_bio2 = _detect_question_topic(
            "Yurak qon tomirlari va o'pka nafas olish fiziologiyasi",
            subject="biology",
        )
        assert topic_bio2 == "Odam anatomiyasi"

        # Chemistry
        topic_chem1 = _detect_question_topic(
            "Mendeleyev davriy jadvali va kislota asos atom tuzilishi",
            subject="chemistry",
        )
        assert topic_chem1 == "Umumiy va anorganik kimyo"

        topic_chem2 = _detect_question_topic(
            "Alkan alken va spirt organik kimyoviy birikmalar",
            subject="chemistry",
        )
        assert topic_chem2 == "Organik kimyo"

        # Law
        topic_law1 = _detect_question_topic(
            "O'zbekiston Respublikasi Konstitutsiyasi va inson huquqlari moddalari",
            subject="law",
        )
        assert topic_law1 == "Konstitutsiyaviy huquq"

        topic_law2 = _detect_question_topic(
            "Sud tergov jarayoni va jinoyat kodeksi jazo choralari",
            subject="law",
        )
        assert topic_law2 == "Jinoyat va ma'muriy huquq"
