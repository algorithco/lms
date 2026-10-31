"""
Test suite for Stage 8.2.0:
1. Essay teacher review zero-score validation (allowing 0, 0.0, '0' without falsy missing errors).
2. Enterprise portal empty state and center creation flow.
"""

from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.essays.models import EssayCriterionScore, EssaySubmission, EssayTopic, TeacherReview
from apps.organizations.models import CenterBranch, LearningCenter

User = get_user_model()


@pytest.fixture
def teacher_user(db):
    teacher = User.objects.create_user(
        email="test_teacher_review@grandec.uz",
        password="Password123!",
        first_name="Ustoz",
        last_name="Muallim",
        role="teacher",
    )
    teacher.can_create_test = True
    teacher.can_create_essay_topic = True
    teacher.save()
    return teacher


@pytest.fixture
def student_user(db):
    return User.objects.create_user(
        email="test_student_essay@grandec.uz",
        password="Password123!",
        first_name="Talaba",
        last_name="Shogird",
        role="student",
    )


@pytest.fixture
def graded_submission(db, student_user, teacher_user):
    topic = EssayTopic.objects.create(
        title="Ona tili va milliy o'zlik",
        description="Milliy o'zlikni anglashda ona tilining o'rni haqida mulohaza yuriting.",
        subject="uzbek",
    )
    sub = EssaySubmission.objects.create(
        student=student_user,
        topic=topic,
        assigned_reviewer=teacher_user,
        essay_text="Ona tili — millatning ruhi va ma'naviy boyligidir. " * 30,
        word_count=180,
        status=EssaySubmission.Status.GRADED,
        total_score=Decimal("12.0"),
        max_score=20,
    )
    # Seed AI criteria
    for cid in range(1, 13):
        max_s = EssayCriterionScore.CRITERION_MAX_SCORES.get(cid, Decimal("2.0"))
        EssayCriterionScore.objects.create(
            submission=sub,
            criterion_id=cid,
            name=EssayCriterionScore.CRITERION_NAMES.get(cid, f"Mezon {cid}"),
            score=min(Decimal("1.0"), max_s),
            reason="AI dastlabki bahosi",
        )
    return sub


@pytest.mark.django_db
def test_essay_teacher_review_with_zero_scores(teacher_user, graded_submission):
    """
    Teacher gives 0 to criterion 1 (or multiple criteria) and ensures:
    1. HTTP 200 is returned.
    2. 'Mezon #1: ball kiritilmadi' error does NOT occur.
    3. Final score accurately reflects zeros.
    """
    client = APIClient()
    client.force_authenticate(user=teacher_user)

    # 1. Scores with 0 on criterion 1, 0 on criterion 5, 0.0 on criterion 12
    criteria_scores = {
        1: 0,
        2: 1.5,
        3: 2.0,
        4: 1.0,
        5: 0,
        6: 1.5,
        7: 2.0,
        8: 1.0,
        9: 1.5,
        10: 1.0,
        11: 1.5,
        12: 0.0,
    }

    url = f"/api/v1/essays/teacher/{graded_submission.id}/review/"
    resp = client.post(
        url,
        {
            "criteria_scores": criteria_scores,
            "teacher_comments": "Ba'zi mezonlar bo'yicha qoniqarsiz (0 ball), lekin umumiy fikr yaxshi.",
        },
        format="json",
    )

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.data}"
    data = resp.json()
    assert data["ok"] is True

    # Expected sum: 0 + 1.5 + 2.0 + 1.0 + 0 + 1.5 + 2.0 + 1.0 + 1.5 + 1.0 + 1.5 + 0.0 = 13.0
    assert data["final_score"] == 13.0

    # Verify database review record
    review = TeacherReview.objects.get(submission=graded_submission)
    assert review.teacher == teacher_user
    assert review.final_score == Decimal("13.0")
    assert review.criteria_scores["1"] == 0.0
    assert review.criteria_scores["5"] == 0.0
    assert review.criteria_scores["12"] == 0.0


@pytest.mark.django_db
def test_essay_teacher_review_all_zero_scores(teacher_user, graded_submission):
    """
    Extreme edge case: teacher gives 0 on ALL 12 criteria (total 0.0).
    Must succeed with final_score=0.0.
    """
    client = APIClient()
    client.force_authenticate(user=teacher_user)

    all_zeros = {cid: 0 for cid in range(1, 13)}
    url = f"/api/v1/essays/teacher/{graded_submission.id}/review/"
    resp = client.post(
        url,
        {
            "criteria_scores": all_zeros,
            "teacher_comments": "Esse mavzudan butunlay chetlashgan, 0 ball.",
        },
        format="json",
    )

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.data}"
    assert resp.json()["final_score"] == 0.0

    review = TeacherReview.objects.get(submission=graded_submission)
    assert review.final_score == Decimal("0.0")


@pytest.mark.django_db
def test_enterprise_dashboard_empty_state_and_create_center():
    """
    Test Enterprise Dashboard:
    1. A director with no center gets center=None (clean empty state, no infinite loop).
    2. Director posts to /api/v1/enterprise/centers/create/ to add a center.
    3. Center is created with branches.
    4. Subsequent dashboard call returns the active center and branches.
    """
    director = User.objects.create_user(
        email="new_director@grandec.uz",
        password="Password123!",
        first_name="Ulugbek",
        last_name="Qodirov",
        role="center_admin",
    )

    client = APIClient()
    client.force_authenticate(user=director)

    # 1. First call: no centers exist yet
    dash_resp = client.get("/api/v1/enterprise/dashboard/")
    assert dash_resp.status_code == 200
    dash_data = dash_resp.json()
    assert dash_data["center"] is None
    assert dash_data["stats"] is None
    assert dash_data["centers"] == []

    # 2. Create center
    create_payload = {
        "name": "Ipak Yo'li O'quv Markazi",
        "address": "Samarqand sh., Registon ko'chasi 14",
        "phone": "+998662334455",
        "branches_count": 3,
        "student_seat_limit": 100,
    }
    create_resp = client.post(
        "/api/v1/enterprise/centers/create/",
        create_payload,
        format="json",
    )
    assert create_resp.status_code == 201
    center_data = create_resp.json()["center"]
    assert center_data["name"] == "Ipak Yo'li O'quv Markazi"
    assert center_data["student_seat_limit"] == 100

    # Verify branches created in database
    center = LearningCenter.objects.get(id=center_data["id"])
    branches = center.branches.all()
    assert branches.count() == 3
    branch_names = [b.name for b in branches]
    assert "Bosh filial" in branch_names
    assert "2-filial" in branch_names
    assert "3-filial" in branch_names

    # 3. Subsequent dashboard call: center is now active
    dash_resp2 = client.get("/api/v1/enterprise/dashboard/")
    assert dash_resp2.status_code == 200
    dash_data2 = dash_resp2.json()
    assert dash_data2["center"] is not None
    assert dash_data2["center"]["name"] == "Ipak Yo'li O'quv Markazi"
    assert dash_data2["stats"]["seat_limit"] == 100
    assert len(dash_data2["branches"]) == 3
