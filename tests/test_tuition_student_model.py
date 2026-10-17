import pytest
from datetime import date, timedelta
from django.utils import timezone
from apps.accounts.models import User
from apps.courses.models import StudentGroup, Homework, HomeworkSubmission
from apps.tuition.models import StudentTuition


@pytest.mark.django_db
def test_student_tuition_lifecycle_and_mark_paid():
    teacher = User.objects.create_user(
        email="teacher_tuit@example.com",
        first_name="Ustoz",
        last_name="Testov",
        role=User.Role.TEACHER,
    )
    student = User.objects.create_user(
        email="student_tuit@example.com",
        first_name="Oquvchi",
        last_name="Testov",
        role=User.Role.STUDENT,
    )
    group = StudentGroup.objects.create(
        name="11-A Guruh",
        teacher=teacher,
    )
    group.students.add(student)

    # 1. Create StudentTuition
    due = date.today() + timedelta(days=5)
    tuition = StudentTuition.objects.create(
        student=student,
        group=group,
        monthly_fee=450000,
        due_date=due,
        status=StudentTuition.Status.PENDING,
    )

    assert tuition.status == StudentTuition.Status.PENDING
    assert tuition.paid_at is None
    assert tuition.monthly_fee == 450000

    # 2. Mark Paid
    tuition.mark_paid()
    tuition.refresh_from_db()
    assert tuition.status == StudentTuition.Status.PAID
    assert tuition.paid_at is not None


@pytest.mark.django_db
def test_homework_creation_and_due_date():
    teacher = User.objects.create_user(
        email="teacher_hw@example.com",
        first_name="Ustoz",
        role=User.Role.TEACHER,
    )
    student = User.objects.create_user(
        email="student_hw@example.com",
        first_name="Oquvchi",
        role=User.Role.STUDENT,
    )
    group = StudentGroup.objects.create(name="10-B Guruh", teacher=teacher)
    group.students.add(student)

    hw = Homework.objects.create(
        group=group,
        title="40 ta test va 1 ta esse",
        description="BMB mock test topshirilsin",
        due_date=timezone.now() + timedelta(days=3),
        created_by=teacher,
    )

    assert hw.title == "40 ta test va 1 ta esse"
    assert hw.group == group
    assert "10-B Guruh" in str(hw)
