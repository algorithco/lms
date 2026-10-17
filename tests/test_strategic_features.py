"""
Comprehensive integration tests for the 3 Strategic Features:
1. Parent Monitoring & Smart Alerts (ParentStudentRelation, Celery Tasks, API)
2. Sunday Live League (Tournament, TournamentParticipant, Real-time Leaderboard, Awards)
3. B2B Enterprise SaaS (LearningCenter, CenterBranch, Bulk Import, Executive Dashboard)
"""
import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import ParentStudentRelation, Profile
from apps.arena.models import Tournament, TournamentParticipant
from apps.arena.services_tournament import finalize_tournament_awards, get_tournament_leaderboard, submit_tournament_answers
from apps.courses.models import Course
from apps.notifications.tasks_parent import calculate_bmb_grade, send_parent_test_alert_task
from apps.organizations.models import CenterBranch, LearningCenter
from apps.payments.models import SubscriptionPlan
from apps.results.models import Result
from apps.tests.models import Choice, Question, Test, TestAttempt

User = get_user_model()


@pytest.fixture
def student_user(db):
    user = User.objects.create_user(
        email="student_test@grandec.uz",
        password="Password123!",
        first_name="Aziz",
        last_name="Valiyev",
        role="student",
        telegram_chat_id=111222333,
    )
    Profile.objects.filter(user=user).update(phone="+998901112233")
    user.refresh_from_db()
    return user


@pytest.fixture
def test_instance(db, student_user):
    course = Course.objects.create(
        teacher=student_user,
        title="Ona tili va adabiyot kursi",
        slug="ona-tili-kursi-test",
    )
    t = Test.objects.create(
        course=course,
        title="Ona tili Milliy sertifikat diagnostika #1",
        description="To'liq 30 talik test",
        time_limit_minutes=30,
        pass_percentage=60,
    )
    # Q1 (Correct: C)
    q1 = Question.objects.create(test=t, position=1, text="Qaysi javobda imlo xatosi bor?")
    Choice.objects.create(question=q1, position=1, text="muammo", is_correct=False)
    Choice.objects.create(question=q1, position=2, text="tushkunlik", is_correct=False)
    Choice.objects.create(question=q1, position=3, text="tashshakkur", is_correct=True)
    Choice.objects.create(question=q1, position=4, text="hamkorlik", is_correct=False)

    # Q2 (Correct: A)
    q2 = Question.objects.create(test=t, position=2, text="Egalik qo'shimchasi qatnashgan so'zni toping:")
    Choice.objects.create(question=q2, position=1, text="kitobim", is_correct=True)
    Choice.objects.create(question=q2, position=2, text="maktabga", is_correct=False)
    Choice.objects.create(question=q2, position=3, text="yozdi", is_correct=False)
    Choice.objects.create(question=q2, position=4, text="chiroyli", is_correct=False)

    # Q3 (Correct: B)
    q3 = Question.objects.create(test=t, position=3, text="Fe'l nisbatini aniqlang: 'xat yozildi'")
    Choice.objects.create(question=q3, position=1, text="aniq nisbat", is_correct=False)
    Choice.objects.create(question=q3, position=2, text="majhul nisbat", is_correct=True)
    Choice.objects.create(question=q3, position=3, text="orttirma nisbat", is_correct=False)
    Choice.objects.create(question=q3, position=4, text="birgalik nisbat", is_correct=False)

    return t


# ==============================================================================
# 1. 👨‍👩‍👧 OTA-ONALAR NAZORATI TIZIMI TESTLARI
# ==============================================================================

@pytest.mark.django_db
def test_parent_student_relation_flow(student_user):
    client = APIClient()
    client.force_authenticate(user=student_user)

    # 1. Create relation via API
    resp = client.post("/api/v1/parents/relation/", {"parent_phone": "+998909876543"})
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert data["parent_phone"] == "+998909876543"
    assert data["is_verified"] is False
    assert len(data["verification_code"]) == 6
    code = data["verification_code"]

    # 2. Verify code via API
    verify_resp = client.post("/api/v1/parents/verify-code/", {"verification_code": code})
    assert verify_resp.status_code == 200
    assert verify_resp.json()["success"] is True

    rel = ParentStudentRelation.objects.get(student=student_user)
    assert rel.is_verified is True

    # 3. Toggle settings
    patch_resp = client.patch(
        f"/api/v1/parents/relation/{rel.id}/",
        {
            "instant_alerts_enabled": False,
            "weekly_report_enabled": True,
        },
        format="json",
    )
    assert patch_resp.status_code == 200
    rel.refresh_from_db()
    assert rel.instant_alerts_enabled is False
    assert rel.weekly_report_enabled is True


@pytest.mark.django_db
def test_parent_instant_alert_task(student_user, test_instance):
    # Setup relation with telegram ID
    ParentStudentRelation.objects.create(
        student=student_user,
        parent_phone="+998909876543",
        parent_telegram_id=999888777,
        is_verified=True,
        instant_alerts_enabled=True,
    )

    # Create attempt & result
    attempt = TestAttempt.objects.create(
        test=test_instance,
        student=student_user,
        status=TestAttempt.Status.COMPLETED,
    )
    result = Result.objects.create(
        attempt=attempt,
        student=student_user,
        test=test_instance,
        course=test_instance.course,
        total_questions=3,
        correct_answers=2,
        wrong_answers=1,
        score=Decimal("80.00"),
        max_score=Decimal("100.00"),
        percentage=Decimal("80.00"),
        is_passed=True,
    )

    grade = calculate_bmb_grade(80.0)
    assert "A" in grade

    # Execute task
    task_res = send_parent_test_alert_task(result.id)
    assert task_res["status"] == "sent"
    assert task_res["count"] == 1


# ==============================================================================
# 2. 🏆 JONLI YAKSHANBA TURNIRI TESTLARI
# ==============================================================================

@pytest.mark.django_db
def test_tournament_e_sport_flow(student_user, test_instance):
    SubscriptionPlan.objects.get_or_create(plan_type="premium", defaults={"name": "Premium", "price_monthly": 60000})
    SubscriptionPlan.objects.get_or_create(plan_type="starter", defaults={"name": "Starter", "price_monthly": 15000})

    # Create Tournament
    tournament = Tournament.objects.create(
        title="Katta Yakshanba Turniri #15",
        scheduled_at=timezone.now(),
        duration_minutes=40,
        test=test_instance,
        status=Tournament.Status.LIVE,
    )

    # Second participant
    user2 = User.objects.create_user(
        email="second_player@grandec.uz",
        password="Password123!",
        first_name="Bobur",
        last_name="Mirzo",
    )

    # Submit user 1 answers (all 3 correct: Q1->C, Q2->A, Q3->B)
    q_ids = list(test_instance.questions.order_by("position").values_list("id", flat=True))
    answers_user1 = {str(q_ids[0]): "C", str(q_ids[1]): "A", str(q_ids[2]): "B"}
    res1 = submit_tournament_answers(
        tournament_id=tournament.id,
        user=student_user,
        answers_dict=answers_user1,
        time_taken_seconds=45,
    )
    assert res1["score"] == 100.0
    assert res1["correct_answers"] == 3

    # Submit user 2 answers (1 correct: Q1->C, Q2->B, Q3->D)
    answers_user2 = {str(q_ids[0]): "C", str(q_ids[1]): "B", str(q_ids[2]): "D"}
    res2 = submit_tournament_answers(
        tournament_id=tournament.id,
        user=user2,
        answers_dict=answers_user2,
        time_taken_seconds=30,
    )
    assert res2["score"] == 33.33
    assert res2["correct_answers"] == 1

    # Check leaderboard
    lb = get_tournament_leaderboard(tournament.id)
    assert len(lb) == 2
    assert lb[0]["user_id"] == student_user.id
    assert lb[0]["rank"] == 1
    assert lb[1]["user_id"] == user2.id
    assert lb[1]["rank"] == 2

    # Finalize tournament awards
    final_res = finalize_tournament_awards(tournament.id)
    assert final_res["status"] == "finished"
    assert len(final_res["awarded"]) == 2

    # 1st place should have premium plan
    student_user.profile.refresh_from_db()
    assert student_user.profile.plan == "premium"

    # 2nd place should have starter plan
    user2.profile.refresh_from_db()
    assert user2.profile.plan == "starter"


# ==============================================================================
# 3. 🏢 O'QUV MARKAZLARI PORTALI (B2B SAAS) TESTLARI
# ==============================================================================

@pytest.mark.django_db
def test_enterprise_hub_flow(student_user, test_instance):
    director = User.objects.create_user(
        email="director@grandcenter.uz",
        password="Password123!",
        first_name="Javohir",
        last_name="Karimov",
        role="center_admin",
    )

    center = LearningCenter.objects.create(
        name="Registon Grand Markazi",
        owner=director,
        student_seat_limit=50,
    )
    CenterBranch.objects.create(center=center, name="Chilonzor filiali")
    CenterBranch.objects.create(center=center, name="Yunusobod filiali")

    director.learning_center = center
    director.save()

    client = APIClient()
    client.force_authenticate(user=director)

    # 1. Bulk Import 2 students
    import_payload = {
        "students": [
            {"first_name": "Sardor", "last_name": "Aliyev", "email": "sardor1@grand.uz", "branch_name": "Chilonzor filiali"},
            {"first_name": "Kamola", "last_name": "Saidova", "email": "kamola2@grand.uz", "branch_name": "Yunusobod filiali"},
        ]
    }
    import_resp = client.post("/api/v1/enterprise/students/bulk-import/", import_payload, format="json")
    assert import_resp.status_code == 200
    assert import_resp.json()["imported"] == 2
    assert center.total_students_count == 2

    # 2. Add test results for one of the center's students
    sardor = User.objects.get(email="sardor1@grand.uz")
    attempt = TestAttempt.objects.create(
        test=test_instance,
        student=sardor,
        status=TestAttempt.Status.COMPLETED,
    )
    Result.objects.create(
        attempt=attempt,
        student=sardor,
        test=test_instance,
        course=test_instance.course,
        total_questions=3,
        correct_answers=3,
        wrong_answers=0,
        score=Decimal("90.00"),
        max_score=Decimal("100.00"),
        percentage=Decimal("90.00"),
        is_passed=True,
    )

    # 3. Check Dashboard analytics
    dash_resp = client.get("/api/v1/enterprise/dashboard/")
    assert dash_resp.status_code == 200
    d_data = dash_resp.json()
    assert d_data["stats"]["total_students"] == 2
    assert d_data["stats"]["seat_limit"] == 50
    assert d_data["stats"]["avg_score"] == 90.0
    assert len(d_data["branches"]) == 2

    # 4. Export monthly CSV report
    report_resp = client.get("/api/v1/enterprise/report/download/")
    assert report_resp.status_code == 200
    assert "text/csv" in report_resp["Content-Type"]
