import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Profile, User
from apps.courses.models import StudentGroup
from apps.organizations.models import CenterBranch, LearningCenter
from apps.tests.models import Question, Test


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def center(db):
    owner = User.objects.create_user(
        email="owner@grandec.uz",
        password="Password123!",
        first_name="Grand",
        last_name="Owner",
        role="admin",
        is_staff=True,
        is_superuser=True,
    )
    center, _ = LearningCenter.objects.get_or_create(
        name="Grand Education",
        defaults={"owner": owner, "student_seat_limit": 500},
    )
    return center


@pytest.fixture
def admin_user(db, center):
    admin = User.objects.create_user(
        email="admin_branch@grandec.uz",
        password="Password123!",
        first_name="Platform",
        last_name="Admin",
        role="admin",
        is_staff=True,
        is_superuser=True,
    )
    Profile.objects.get_or_create(user=admin)
    return admin


@pytest.fixture
def teacher_user(db, center):
    teacher = User.objects.create_user(
        email="bio_teacher@grandec.uz",
        password="Password123!",
        first_name="Zafar",
        last_name="Qodirov",
        role="teacher",
    )
    prof, _ = Profile.objects.get_or_create(user=teacher)
    prof.active_subject = "biology"
    prof.save()
    return teacher


@pytest.fixture
def student_user(db):
    student = User.objects.create_user(
        email="student_sam@grandec.uz",
        password="Password123!",
        first_name="Bobur",
        last_name="Aliyev",
        role="student",
    )
    prof, _ = Profile.objects.get_or_create(user=student)
    prof.plan = "free"
    prof.save()
    return student


@pytest.mark.django_db
def test_branch_creation_and_listing(api_client, admin_user, center):
    api_client.force_authenticate(user=admin_user)

    # 1. Create Branch
    payload = {
        "name": "Grand Education — Samarqand Markaziy Filiali",
        "branch_code": "SAM-01",
        "region": "Samarqand",
        "address": "Registon ko'chasi 12",
        "phone": "+998901234567",
        "telegram_channel": "@grandec_sam",
        "subjects_offered": ["biology", "chemistry", "law"],
        "max_teachers_limit": 15,
        "max_students_limit": 300,
    }
    res = api_client.post("/api/v1/panel/branches/", payload, format="json")
    assert res.status_code == 201
    assert res.data["success"] is True
    branch_id = res.data["branch"]["id"]
    assert res.data["branch"]["branch_code"] == "SAM-01"

    # 2. List Branches
    list_res = api_client.get("/api/v1/panel/branches/")
    assert list_res.status_code == 200
    assert any(b["branch_code"] == "SAM-01" for b in list_res.data)


@pytest.mark.django_db
def test_assign_teacher_to_branch(api_client, admin_user, teacher_user, center):
    api_client.force_authenticate(user=admin_user)

    branch = CenterBranch.objects.create(
        center=center,
        name="Registon Kursxonasi — Buxoro Filiali",
        branch_code="BUX-01",
        region="Buxoro",
    )

    payload = {
        "teacher_id": teacher_user.id,
        "branch_id": branch.id,
        "subject": "biology",
        "can_create_test": True,
        "can_create_essay_topic": True,
    }
    res = api_client.post("/api/v1/panel/teachers/assign/", payload, format="json")
    assert res.status_code == 200
    assert res.data["success"] is True

    teacher_user.refresh_from_db()
    assert teacher_user.branch_id == branch.id
    assert teacher_user.profile.active_subject == "biology"
    assert teacher_user.can_create_test is True


@pytest.mark.django_db
def test_group_creation_with_branch_and_custom_invite_code(db, teacher_user, center):
    branch = CenterBranch.objects.create(
        center=center,
        name="Toshkent Chilonzor Filiali",
        branch_code="TAS-01",
        region="Toshkent sh.",
    )

    group = StudentGroup.objects.create(
        teacher=teacher_user,
        branch=branch,
        name="Biologiya Milliy Sertifikat 1-Guruh",
        subject="biology",
        invite_code="BIO-104",
    )

    assert group.branch == branch
    assert group.invite_code == "BIO-104"
    assert group.subject == "biology"


@pytest.mark.django_db
def test_student_join_group_via_code_and_sync_branch(api_client, student_user, teacher_user, center):
    branch = CenterBranch.objects.create(
        center=center,
        name="Samarqand Filiali",
        branch_code="SAM-02",
        region="Samarqand",
    )
    group = StudentGroup.objects.create(
        teacher=teacher_user,
        branch=branch,
        name="Kimyo Intensiv Guruh",
        subject="chemistry",
        invite_code="KIM-205",
    )

    api_client.force_authenticate(user=student_user)

    # Student joins via invite code KIM-205
    res = api_client.post("/api/v1/school/groups/join/", {"code": "KIM-205"}, format="json")
    assert res.status_code == 200
    assert res.data["success"] is True

    student_user.refresh_from_db()
    assert group.students.filter(id=student_user.id).exists()
    assert student_user.branch_id == branch.id
    assert student_user.profile.plan == "pro"


@pytest.mark.django_db
def test_student_group_detail_view_and_live_leaderboard(api_client, student_user, teacher_user, center):
    branch = CenterBranch.objects.create(
        center=center,
        name="Huquq Akademiyasi",
        branch_code="HUQ-01",
        region="Toshkent",
    )
    group = StudentGroup.objects.create(
        teacher=teacher_user,
        branch=branch,
        name="Huquqshunoslik Kazus Guruhi",
        subject="law",
        invite_code="HUQ-301",
    )
    group.students.add(student_user)

    # Assign a mock test to the group
    from apps.courses.models import Course
    course = Course.objects.create(
        title="Huquq kursi",
        teacher=teacher_user,
        subject="law",
    )
    test = Test.objects.create(
        course=course,
        title="Huquq Konstitutsiya 1-Modul",
        subject="law",
        created_by=teacher_user,
        assigned_group=group,
        is_active=True,
        time_limit_minutes=60,
    )

    api_client.force_authenticate(user=student_user)
    res = api_client.get(f"/api/v1/school/groups/{group.id}/student-view/")
    assert res.status_code == 200

    data = res.data
    assert data["group"]["id"] == group.id
    assert data["group"]["invite_code"] == "HUQ-301"
    assert data["branch"]["name"] == "Huquq Akademiyasi"
    assert data["teacher"]["name"] == teacher_user.get_full_name()
    assert len(data["assigned_tests"]) == 1
    assert data["assigned_tests"][0]["title"] == "Huquq Konstitutsiya 1-Modul"
    assert len(data["leaderboard"]) >= 1
    assert data["leaderboard"][0]["student_id"] == student_user.id
    assert data["leaderboard"][0]["medal"] == "🥇"


@pytest.mark.django_db
def test_public_branches_catalog(api_client, teacher_user, center):
    branch = CenterBranch.objects.create(
        center=center,
        name="Grand Farg'ona Filiali",
        branch_code="FAR-01",
        region="Farg'ona",
        subjects_offered=["biology", "english"],
    )
    StudentGroup.objects.create(
        teacher=teacher_user,
        branch=branch,
        name="Farg'ona Biologiya",
        subject="biology",
        invite_code="BIO-999",
    )

    res = api_client.get("/api/v1/school/branches/catalog/")
    assert res.status_code == 200
    catalog = res.data
    assert any(b["branch_code"] == "FAR-01" for b in catalog)
    f_branch = next(b for b in catalog if b["branch_code"] == "FAR-01")
    assert len(f_branch["groups"]) == 1
    assert f_branch["groups"][0]["invite_code"] == "BIO-999"
