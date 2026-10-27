import io
import pytest
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.accounts.models import Profile
from apps.courses.models import Course
from apps.tests.models import Test, Question, Choice

User = get_user_model()

@pytest.fixture
def auth_client(db):
    user = User.objects.create_user(
        email="omr_student@example.com",
        password="testpassword123",
        first_name="Komiljon",
        role="student",
    )
    Profile.objects.get_or_create(user=user)
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user

@pytest.fixture
def test_with_choices(db):
    teacher = User.objects.create_user(
        email="omr_teacher@example.com",
        password="testpassword123",
        first_name="Nilufar",
        role="teacher",
    )
    Profile.objects.get_or_create(user=teacher)
    course = Course.objects.create(
        teacher=teacher,
        title="OMR Prep Course",
        slug="omr-prep",
    )
    test = Test.objects.create(
        title="BMB Mock 101",
        course=course,
        mock_code="BMB-101",
        subject="uzbek",
        status=Test.Status.PUBLISHED,
        is_active=True,
    )
    for i in range(1, 6):
        q = Question.objects.create(
            test=test,
            text=f"Question {i}",
            position=i,
            points=2,
            correct_text="A",
        )
        for idx, letter in enumerate(["A", "B", "C", "D"], start=1):
            Choice.objects.create(
                question=q,
                text=f"Option {letter}",
                is_correct=(letter == "A"),
                position=idx,
            )
    return test

def _create_dummy_image():
    file = io.BytesIO()
    image = Image.new("RGB", (400, 600), color="white")
    image.save(file, "JPEG")
    file.seek(0)
    file.name = "titul_test.jpg"
    return file

@pytest.mark.django_db
def test_scan_omr_get_available_tests(auth_client, test_with_choices):
    client, user = auth_client
    response = client.get("/api/v1/tests/scan-omr/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["ok"] is True
    assert response.data["count"] >= 1
    codes = [t["mock_code"] for t in response.data["tests"]]
    assert "BMB-101" in codes

@pytest.mark.django_db
def test_scan_omr_unknown_code_fallback(auth_client):
    client, user = auth_client
    img = _create_dummy_image()
    response = client.post(
        "/api/v1/tests/scan-omr/",
        data={"image": img, "mock_code": "NON_EXISTENT_CODE_999"},
        format="multipart",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["ok"] is False
    assert response.data["code_not_found"] is True
    assert "topilmadi" in response.data["error"]

@pytest.mark.django_db
def test_scan_omr_grade_success(auth_client, test_with_choices):
    client, user = auth_client
    img = _create_dummy_image()
    response = client.post(
        "/api/v1/tests/scan-omr/",
        data={"image": img, "test_id": test_with_choices.id},
        format="multipart",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["ok"] is True
    assert response.data["test_id"] == test_with_choices.id
    assert response.data["total_questions"] == 5
    assert "breakdown" in response.data
    assert len(response.data["breakdown"]) == 5
