import pytest
from django.contrib.auth import get_user_model
from apps.tests.bmb_grading import calculate_bmb_grade, bmb_grade_distribution
from apps.tests.mock_service import parse_mock_keys, create_quick_mock, find_mock_by_code
from apps.tests.ai_tutor import explain_question_mistake
from apps.courses.models import StudentGroup
from apps.courses.group_service import (
    get_group_full_analytics,
    export_group_to_excel,
    export_group_to_pdf,
    join_group_by_invite_code,
)

User = get_user_model()


@pytest.mark.django_db
class TestBmbGrading:
    def test_grade_boundaries(self):
        assert calculate_bmb_grade(100.0)["grade"] == "A+"
        assert calculate_bmb_grade(86.0)["grade"] == "A+"
        assert calculate_bmb_grade(85.9)["grade"] == "A"
        assert calculate_bmb_grade(75.0)["grade"] == "A"
        assert calculate_bmb_grade(74.9)["grade"] == "B+"
        assert calculate_bmb_grade(68.0)["grade"] == "B+"
        assert calculate_bmb_grade(67.9)["grade"] == "B"
        assert calculate_bmb_grade(60.0)["grade"] == "B"
        assert calculate_bmb_grade(59.9)["grade"] == "C+"
        assert calculate_bmb_grade(53.0)["grade"] == "C+"
        assert calculate_bmb_grade(52.9)["grade"] == "C"
        assert calculate_bmb_grade(46.0)["grade"] == "C"
        assert calculate_bmb_grade(45.9)["grade"] == "Fail"
        assert calculate_bmb_grade(0.0)["grade"] == "Fail"

    def test_bmb_distribution(self):
        scores = [90, 80, 70, 65, 55, 50, 30]
        dist = bmb_grade_distribution(scores)
        assert dist["A+"] == 1
        assert dist["A"] == 1
        assert dist["B+"] == 1
        assert dist["B"] == 1
        assert dist["C+"] == 1
        assert dist["C"] == 1
        assert dist["Fail"] == 1


@pytest.mark.django_db
class TestQuickMockService:
    def test_parse_mock_keys(self):
        keys_str = "1a2b3c4d5a"
        parsed = parse_mock_keys(keys_str)
        assert len(parsed) == 5
        assert parsed[1] == "A"
        assert parsed[2] == "B"
        assert parsed[3] == "C"
        assert parsed[4] == "D"
        assert parsed[5] == "A"

    def test_create_and_find_quick_mock(self):
        teacher = User.objects.create_user(
            email="teacher_mock@example.com",
            password="pass",
            role="Teacher",
        )
        keys_str = "".join(f"{i}{'abcd'[i % 4]}" for i in range(1, 41))
        mock_data = create_quick_mock(
            teacher=teacher,
            key_string=keys_str,
            title="Ona tili Mock #77",
            time_limit_minutes=60,
        )
        assert mock_data["mock_code"] is not None
        assert mock_data["mock_code"].startswith("#MOCK-")
        assert mock_data["total_questions"] == 40

        found = find_mock_by_code(mock_data["mock_code"])
        assert found.id == mock_data["test_id"]

        # Also find without '#'
        found_no_hash = find_mock_by_code(mock_data["mock_code"].replace("#", ""))
        assert found_no_hash.id == mock_data["test_id"]


@pytest.mark.django_db
class TestGroupManagementAndReports:
    def test_group_invite_code_and_analytics(self):
        teacher = User.objects.create_user(
            email="teacher_group@example.com",
            password="pass",
            role="Teacher",
        )
        group = StudentGroup.objects.create(
            name="Milliy Sertifikat Guruhi #99",
            teacher=teacher,
        )
        assert group.invite_code is not None
        assert "GR-" in group.invite_code

        student = User.objects.create_user(
            email="student_group@example.com",
            password="pass",
            role="Student",
        )
        # Student joins via invite code
        joined = join_group_by_invite_code(student, group.invite_code)
        assert joined.id == group.id
        assert group.students.filter(id=student.id).exists()

        analytics = get_group_full_analytics(group)
        assert analytics["group_id"] == group.id
        assert analytics["total_students"] == 1

        # Excel export
        xlsx_bytes = export_group_to_excel(group)
        assert isinstance(xlsx_bytes, bytes)
        assert len(xlsx_bytes) > 1000

        # PDF export
        pdf_bytes = export_group_to_pdf(group)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 1000
