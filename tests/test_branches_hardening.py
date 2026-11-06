"""Tenant isolation (IDOR), query-count and PII guards for branches / groups."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts.models import Profile, User
from apps.courses.group_service import get_group_full_analytics
from apps.courses.models import Course, StudentGroup
from apps.organizations.models import CenterBranch, LearningCenter
from apps.results.models import Result
from apps.tests.models import Test, TestAttempt


def _user(email, role="student", **extra):
    user = User.objects.create_user(email=email, password="Pass-12345-xy!", role=role, **extra)
    Profile.objects.get_or_create(user=user)
    return user


def _api(user=None):
    client = APIClient()
    if user:
        client.force_authenticate(user)
    return client


@pytest.fixture
def world(db):
    owner = _user("hard_owner@example.test", role="admin", is_superuser=True, is_staff=True)
    center = LearningCenter.objects.create(name="Hard Center", owner=owner)
    branch_a = CenterBranch.objects.create(center=center, name="Branch A", branch_code="HA-01")
    branch_b = CenterBranch.objects.create(center=center, name="Branch B", branch_code="HB-01")
    admin_a = _user("hard_admin_a@example.test", role="center_admin", branch=branch_a)
    branch_a.director = admin_a
    branch_a.save()
    teacher_b = _user("hard_teacher_b@example.test", role="teacher", branch=branch_b)
    group_b = StudentGroup.objects.create(teacher=teacher_b, branch=branch_b, name="B group", invite_code="HB-GR1")
    return {
        "owner": owner, "center": center, "branch_a": branch_a, "branch_b": branch_b,
        "admin_a": admin_a, "teacher_b": teacher_b, "group_b": group_b,
    }


# -- IDOR ---------------------------------------------------------------------


@pytest.mark.django_db
def test_center_admin_cannot_touch_foreign_branch(world):
    client = _api(world["admin_a"])
    foreign = f"/api/v1/panel/branches/{world['branch_b'].id}/"

    assert client.get(foreign).status_code == 404
    assert client.patch(foreign, {"name": "Pwned"}, format="json").status_code == 404
    assert client.delete(foreign).status_code == 404
    world["branch_b"].refresh_from_db()
    assert world["branch_b"].name == "Branch B" and world["branch_b"].is_active

    listed = client.get("/api/v1/panel/branches/").json()
    assert [b["branch_code"] for b in listed] == ["HA-01"]


@pytest.mark.django_db
def test_center_admin_cannot_escalate_or_create(world):
    client = _api(world["admin_a"])
    own = f"/api/v1/panel/branches/{world['branch_a'].id}/"
    victim = _user("hard_victim@example.test")

    assert client.post("/api/v1/panel/branches/", {"name": "Spawned"}, format="json").status_code == 403
    assert client.patch(own, {"director_id": victim.id}, format="json").status_code == 403
    assert client.patch(own, {"max_students_limit": 99999}, format="json").status_code == 403
    victim.refresh_from_db()
    assert victim.role == "student"

    # Harmless own-branch edit still works.
    assert client.patch(own, {"address": "New street 1"}, format="json").status_code == 200
    world["branch_a"].refresh_from_db()
    assert world["branch_a"].address == "New street 1"


@pytest.mark.django_db
def test_center_admin_teacher_assignment_is_scoped(world):
    client = _api(world["admin_a"])
    url = "/api/v1/panel/teachers/assign/"

    # cannot place a teacher into a foreign branch or grab a foreign teacher
    assert client.post(url, {"teacher_id": world["teacher_b"].id, "branch_id": world["branch_a"].id}, format="json").status_code == 404
    new = {"email": "hard_new@example.test", "name": "New T", "branch_id": world["branch_b"].id}
    assert client.post(url, new, format="json").status_code == 403
    # cannot demote platform admins
    assert client.post(url, {"teacher_id": world["owner"].id, "branch_id": world["branch_a"].id}, format="json").status_code == 403
    world["owner"].refresh_from_db()
    assert world["owner"].role == "admin"

    # own branch: allowed, and the generated password is random, never a shared default
    ok = client.post(url, {"email": "hard_ok@example.test", "name": "Ok T", "branch_id": world["branch_a"].id}, format="json")
    assert ok.status_code == 200
    pwd = ok.json()["temporary_password"]
    assert pwd != "GrandTeacher2026!" and len(pwd) >= 12
    created = User.objects.get(email="hard_ok@example.test")
    assert created.check_password(pwd) and created.branch_id == world["branch_a"].id

    listed = client.get("/api/v1/panel/teachers/").json()
    assert {t["email"] for t in listed["results"]} == {"hard_ok@example.test"}


@pytest.mark.django_db
def test_invalid_limits_return_400_not_500(world):
    client = _api(world["owner"])
    res = client.post("/api/v1/panel/branches/", {"name": "X", "max_teachers_limit": "abc"}, format="json")
    assert res.status_code == 400


@pytest.mark.django_db
def test_group_view_is_branch_scoped_and_hides_emails(world):
    student = _user("hard_student@example.test")
    mate = _user("hard_mate@example.test")
    world["group_b"].students.add(student, mate)

    # center admin of another branch: forbidden
    assert _api(world["admin_a"]).get(f"/api/v1/school/groups/{world['group_b'].id}/student-view/").status_code == 403
    # outsider: forbidden
    assert _api(_user("hard_out@example.test")).get(f"/api/v1/school/groups/{world['group_b'].id}/student-view/").status_code == 403

    data = _api(student).get(f"/api/v1/school/groups/{world['group_b'].id}/student-view/").json()
    emails = {row["student_id"]: row["email"] for row in data["leaderboard"]}
    assert emails[student.id] == student.email  # own e-mail ok
    assert emails[mate.id] is None  # classmate's e-mail hidden
    assert data["group"]["invite_token"] is None

    staff = _api(world["teacher_b"]).get(f"/api/v1/school/groups/{world['group_b'].id}/student-view/").json()
    assert all(row["email"] for row in staff["leaderboard"])


@pytest.mark.django_db
def test_public_catalog_hides_secrets(world):
    res = _api().get("/api/v1/school/branches/catalog/")
    assert res.status_code == 200
    group = next(b for b in res.json() if b["branch_code"] == "HB-01")["groups"][0]
    assert "invite_token" not in group and "teacher_phone" not in group
    assert group["invite_code"] == "HB-GR1"


# -- PRO safety ---------------------------------------------------------------


@pytest.mark.django_db
def test_joining_group_never_grants_pro(world):
    student = _user("hard_join@example.test")
    res = _api(student).post("/api/v1/school/groups/join/", {"code": "HB-GR1"}, format="json")
    assert res.status_code == 200
    student.refresh_from_db()
    assert student.profile.plan in ("free", "", None)
    assert student.has_pro_access is False
    assert student.branch_id == world["branch_b"].id  # branch sync still works


# -- N+1 ----------------------------------------------------------------------


def _make_results(group, students, n_tests):
    course = Course.objects.create(teacher=group.teacher, title=f"C{group.id}-{len(students)}", slug=f"hc-{group.id}-{len(students)}-{n_tests}")
    for t in range(n_tests):
        test = Test.objects.create(course=course, title=f"T{t}", is_active=True, assigned_group=group)
        for s in students:
            att = TestAttempt.objects.create(test=test, student=s, status=TestAttempt.Status.COMPLETED)
            Result.objects.create(
                attempt=att, student=s, test=test, course=course, total_questions=10, correct_answers=7,
                wrong_answers=3, score=7, max_score=10, percentage=70, is_passed=True,
            )


@pytest.mark.django_db
def test_group_analytics_query_count_is_constant(world):
    group = world["group_b"]
    few = [_user(f"hard_few{i}@example.test") for i in range(2)]
    group.students.add(*few)
    _make_results(group, few, 2)
    with CaptureQueriesContext(connection) as small:
        get_group_full_analytics(group)

    many = [_user(f"hard_many{i}@example.test") for i in range(12)]
    group.students.add(*many)
    _make_results(group, many, 3)
    with CaptureQueriesContext(connection) as big:
        big_data = get_group_full_analytics(group)

    assert len(big) == len(small) <= 5
    assert big_data["total_students"] == 14
    first = big_data["students"][0]
    assert first["tests_taken"] >= 2 and first["avg_test_pct"] == 70.0
    assert first["latest_test_score"].endswith("/10.00")


@pytest.mark.django_db
def test_branch_list_and_catalog_query_count_is_constant(world):
    client = _api(world["owner"])

    def run():
        with CaptureQueriesContext(connection) as ctx:
            assert client.get("/api/v1/panel/branches/").status_code == 200
            assert _api().get("/api/v1/school/branches/catalog/").status_code == 200
        return len(ctx)

    baseline = run()
    for i in range(6):
        br = CenterBranch.objects.create(center=world["center"], name=f"Extra {i}")
        t = _user(f"hard_extra_t{i}@example.test", role="teacher", branch=br)
        g = StudentGroup.objects.create(teacher=t, branch=br, name=f"G{i}")
        g.students.add(_user(f"hard_extra_s{i}@example.test", branch=br))
    assert run() == baseline
