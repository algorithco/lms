"""
tests/test_rasch_engine.py

Unit and integration tests for the continuous 1PL Rasch IRT scoring engine,
difficulty logit calibration, dynamic weights, and recalculation endpoint.
"""

from decimal import Decimal
import math
import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.courses.models import Course
from apps.results.models import Result
from apps.tests.models import Choice, Question, StudentAnswer, Test, TestAttempt
from apps.tests.rasch_engine import RaschEngine


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def teacher_user(db):
    return User.objects.create_user(
        email="teacher_rasch@grandec.uz",
        password="ValidPassword123!",
        role="teacher",
        first_name="Ustoz",
        last_name="Rasch",
    )


@pytest.fixture
def student_user(db):
    return User.objects.create_user(
        email="student_rasch@grandec.uz",
        password="ValidPassword123!",
        role="student",
        first_name="Talaba",
        last_name="Ali",
    )


@pytest.fixture
def student_user2(db):
    return User.objects.create_user(
        email="student2_rasch@grandec.uz",
        password="ValidPassword123!",
        role="student",
        first_name="Talaba",
        last_name="Vali",
    )


@pytest.fixture
def course(db, teacher_user):
    return Course.objects.create(
        title="Ona tili va adabiyot Rasch kursi",
        slug="ona-tili-rasch",
        teacher=teacher_user,
    )


@pytest.fixture
def rasch_test(db, course):
    test = Test.objects.create(
        title="Milliy Sertifikat Rasch Mock Test",
        course=course,
        scoring_type=Test.ScoringType.RASCH_DYNAMIC,
        time_limit_minutes=30,
        pass_percentage=60,
    )
    # Question 1: Easy question (baseline 2.0)
    q1 = Question.objects.create(
        test=test,
        text="1-savol: Oson grammatika savoli",
        position=1,
        points=2,
    )
    Choice.objects.create(question=q1, text="To'g'ri variant A", is_correct=True, position=1)
    Choice.objects.create(question=q1, text="Noto'g'ri variant B", is_correct=False, position=2)

    # Question 2: Hard question (baseline 2.0)
    q2 = Question.objects.create(
        test=test,
        text="2-savol: Juda qiyin mumtoz adabiyot savoli",
        position=2,
        points=2,
    )
    Choice.objects.create(question=q2, text="To'g'ri variant A", is_correct=True, position=1)
    Choice.objects.create(question=q2, text="Noto'g'ri variant B", is_correct=False, position=2)

    return test


def test_rasch_probability_laplace_smoothing():
    """Laplace smoothing guarantees 0 < P_i < 1 without zero division."""
    # When N=0, C=0 -> P = 0.5 / 1 = 0.5
    p0 = RaschEngine.calculate_probability(0, 0)
    assert p0 == 0.5

    # When N=10, C=10 (all correct) -> P = 10.5 / 11 < 1.0
    p_all = RaschEngine.calculate_probability(10, 10)
    assert 0.95 < p_all < 1.0

    # When N=10, C=0 (all wrong) -> P = 0.5 / 11 > 0.0
    p_none = RaschEngine.calculate_probability(0, 10)
    assert 0.0 < p_none < 0.05


def test_rasch_difficulty_logit_and_weights():
    """Hard questions have positive logit and higher weight; easy have negative logit."""
    # Neutral: P = 0.5 -> logit = 0 -> weight = baseline
    p_neutral = 0.5
    logit_neutral = RaschEngine.calculate_logit(p_neutral)
    assert math.isclose(logit_neutral, 0.0, abs_tol=1e-5)
    w_neutral = RaschEngine.calculate_dynamic_weight(logit_neutral, baseline=2.0)
    assert w_neutral == 2.0

    # Hard: 10% correct -> positive logit -> weight increases significantly
    p_hard = RaschEngine.calculate_probability(1, 10)
    logit_hard = RaschEngine.calculate_logit(p_hard)
    assert logit_hard > 0.0
    w_hard = RaschEngine.calculate_dynamic_weight(logit_hard, baseline=2.0)
    assert w_hard >= 3.5

    # Easy: 90% correct -> negative logit -> weight scales down
    p_easy = RaschEngine.calculate_probability(9, 10)
    logit_easy = RaschEngine.calculate_logit(p_easy)
    assert logit_easy < 0.0
    w_easy = RaschEngine.calculate_dynamic_weight(logit_easy, baseline=2.0)
    assert w_easy <= 1.2
    assert w_easy >= 0.5


def test_rasch_grade_mapping():
    """Verify BMB standard grade thresholds."""
    assert RaschEngine.grade_from_percentage(92.5) == "A+"
    assert RaschEngine.grade_from_percentage(86.0) == "A+"
    assert RaschEngine.grade_from_percentage(80.0) == "A"
    assert RaschEngine.grade_from_percentage(70.0) == "B+"
    assert RaschEngine.grade_from_percentage(64.0) == "B"
    assert RaschEngine.grade_from_percentage(55.0) == "C+"
    assert RaschEngine.grade_from_percentage(48.0) == "C"
    assert RaschEngine.grade_from_percentage(40.0) == "Fail"


@pytest.mark.django_db
def test_full_rasch_recalculation(rasch_test, student_user, student_user2):
    """Test full recalculation across multiple attempts."""
    questions = list(rasch_test.questions.all().order_by("position"))
    q1, q2 = questions[0], questions[1]

    # Student 1: answers Q1 correctly, Q2 wrong
    att1 = TestAttempt.objects.create(
        test=rasch_test,
        student=student_user,
        status=TestAttempt.Status.COMPLETED,
    )
    StudentAnswer.objects.create(attempt=att1, question=q1, is_correct=True)
    StudentAnswer.objects.create(attempt=att1, question=q2, is_correct=False)
    res1 = Result.objects.create(
        attempt=att1,
        student=student_user,
        test=rasch_test,
        course=rasch_test.course,
        total_questions=2,
        correct_answers=1,
        wrong_answers=1,
        score=Decimal("2.0"),
        max_score=Decimal("4.0"),
        percentage=Decimal("50.0"),
        is_passed=False,
    )

    # Student 2: also answers Q1 correctly, Q2 wrong (making Q2 much harder than Q1)
    att2 = TestAttempt.objects.create(
        test=rasch_test,
        student=student_user2,
        status=TestAttempt.Status.COMPLETED,
    )
    StudentAnswer.objects.create(attempt=att2, question=q1, is_correct=True)
    StudentAnswer.objects.create(attempt=att2, question=q2, is_correct=False)
    Result.objects.create(
        attempt=att2,
        student=student_user2,
        test=rasch_test,
        course=rasch_test.course,
        total_questions=2,
        correct_answers=1,
        wrong_answers=1,
        score=Decimal("2.0"),
        max_score=Decimal("4.0"),
        percentage=Decimal("50.0"),
        is_passed=False,
    )

    # Trigger Rasch recalculation
    report = RaschEngine.recalculate_test_rasch(rasch_test.id)
    assert report["status"] == "success"
    assert report["questions_updated"] == 2
    assert report["attempts_updated"] == 2

    # Refresh questions
    q1.refresh_from_db()
    q2.refresh_from_db()

    # Q1 was answered by 2/2 students -> should have lower weight
    # Q2 was answered by 0/2 students -> should have higher weight
    assert q2.current_rasch_weight > q1.current_rasch_weight
    assert q2.difficulty_logit > q1.difficulty_logit

    # Refresh results and verify rasch_score and grade
    res1.refresh_from_db()
    att1.refresh_from_db()
    assert float(res1.rasch_score) > 0.0
    assert float(res1.max_rasch_score) > float(res1.rasch_score)
    assert res1.rasch_grade != ""


@pytest.mark.django_db
def test_recalculate_rasch_api(api_client, teacher_user, student_user, rasch_test):
    """Test API endpoint authorization and execution."""
    endpoint = f"/api/tests/{rasch_test.id}/recalculate-rasch/"

    # Unauthenticated -> 401
    resp_anon = api_client.post(endpoint)
    assert resp_anon.status_code == status.HTTP_401_UNAUTHORIZED

    # Authenticated as student -> 403 Forbidden
    api_client.force_authenticate(user=student_user)
    resp_student = api_client.post(endpoint)
    assert resp_student.status_code == status.HTTP_403_FORBIDDEN

    # Authenticated as course teacher -> 200 OK
    api_client.force_authenticate(user=teacher_user)
    resp_teacher = api_client.post(endpoint)
    assert resp_teacher.status_code == status.HTTP_200_OK
    assert resp_teacher.data["status"] == "success"
    assert resp_teacher.data["test_id"] == rasch_test.id
