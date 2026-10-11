"""Essay assignment completion regressions.

Completion must answer "who has not handed this in?" without ever confusing a
grading failure with a missing submission, and it must follow live group
membership so a student who joins later is expected and one who left is not.
"""
import datetime as dt

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.courses.models import StudentGroup
from apps.essays import group_reports
from apps.essays.models import EssayAssignment, EssaySubmission, EssayTopic


class _AssignmentFixture(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            email="ac-teacher@example.test", password="testpass123", role="teacher",
        )
        self.other_teacher = User.objects.create_user(
            email="ac-other@example.test", password="testpass123", role="teacher",
        )
        self.ali = User.objects.create_user(
            email="ac-ali@example.test", password="testpass123", role="student",
            first_name="Ali", last_name="Valiyev",
        )
        self.zuhra = User.objects.create_user(
            email="ac-zuhra@example.test", password="testpass123", role="student",
            first_name="Zuhra", last_name="Karimova",
        )
        self.group = StudentGroup.objects.create(teacher=self.teacher, name="9-A")
        self.group.students.add(self.ali, self.zuhra)
        self.foreign_group = StudentGroup.objects.create(
            teacher=self.other_teacher, name="10-B",
        )
        self.topic = EssayTopic.objects.create(
            title="Tabiat", description="d", created_by=self.teacher,
        )
        self.assignment = group_reports.create_assignment(
            topic=self.topic, group=self.group, assigned_by=self.teacher,
        )

    def submit(self, *, student=None, status=EssaySubmission.Status.GRADED,
               assignment="default", total_score=18, source=EssaySubmission.Source.WEB,
               topic=None):
        return EssaySubmission.objects.create(
            student=student or self.ali,
            topic=topic if topic is not None else self.topic,
            assignment=self.assignment if assignment == "default" else assignment,
            essay_text="Matn " * 60,
            status=status,
            total_score=total_score,
            max_score=24,
            source=source,
            submitted_at=timezone.now(),
        )


class AssignmentCreationTests(_AssignmentFixture):
    def test_create_assignment_is_idempotent_per_topic_and_group(self):
        again = group_reports.create_assignment(
            topic=self.topic, group=self.group, assigned_by=self.teacher,
        )
        self.assertEqual(again.pk, self.assignment.pk)
        self.assertEqual(EssayAssignment.objects.count(), 1)

    def test_later_creation_can_update_due_date_and_instructions(self):
        due = timezone.now() + dt.timedelta(days=3)
        updated = group_reports.create_assignment(
            topic=self.topic, group=self.group, assigned_by=self.teacher,
            due_at=due, instructions="Kamida 250 so'z.",
        )
        self.assertEqual(updated.pk, self.assignment.pk)
        self.assertEqual(updated.instructions, "Kamida 250 so'z.")
        self.assertIsNotNone(updated.due_at)

    def test_create_assignment_refuses_a_group_the_teacher_does_not_own(self):
        with self.assertRaises(PermissionDenied):
            group_reports.create_assignment(
                topic=self.topic, group=self.foreign_group,
                assigned_by=self.teacher,
            )

    def test_expected_students_follows_live_membership(self):
        self.assertEqual(self.assignment.expected_students().count(), 2)
        self.group.students.remove(self.zuhra)
        self.assertEqual(self.assignment.expected_students().count(), 1)


class CompletionCountingTests(_AssignmentFixture):
    def test_graded_pending_failed_and_missing_are_separate(self):
        self.submit(student=self.ali)  # graded
        self.submit(student=self.zuhra, status=EssaySubmission.Status.PENDING,
                    total_score=0)

        completion = group_reports.assignment_completion(self.assignment)
        self.assertEqual(completion["expected"], 2)
        self.assertEqual(completion["graded"], 1)
        self.assertEqual(completion["pending"], 1)
        self.assertEqual(completion["failed"], 0)
        self.assertEqual(completion["not_submitted"], 0)
        self.assertEqual(completion["average_ai_score"], 18.0)

    def test_ai_failure_is_failed_not_non_submission(self):
        self.submit(student=self.ali, status=EssaySubmission.Status.ERROR,
                    total_score=0)
        completion = group_reports.assignment_completion(self.assignment)
        self.assertEqual(completion["failed"], 1)
        self.assertEqual(completion["not_submitted"], 1)
        self.assertEqual(completion["expected"], 2)
        # The submitting student is not in the missing list.
        self.assertEqual(
            [row["student_id"] for row in completion["missing"]], [self.zuhra.pk],
        )
        self.assertEqual(
            [row["student_id"] for row in completion["submitted"]], [self.ali.pk],
        )

    def test_draft_submission_still_counts_as_not_submitted(self):
        self.submit(student=self.ali, status=EssaySubmission.Status.DRAFT,
                    total_score=0)
        completion = group_reports.assignment_completion(self.assignment)
        self.assertEqual(completion["graded"], 0)
        self.assertEqual(completion["pending"], 0)
        self.assertEqual(completion["failed"], 0)
        self.assertEqual(completion["not_submitted"], 2)
        self.assertEqual(
            {row["student_id"] for row in completion["missing"]},
            {self.ali.pk, self.zuhra.pk},
        )

    def test_student_joining_after_creation_becomes_expected(self):
        self.submit()
        before = group_reports.assignment_completion(self.assignment)
        self.assertEqual(before["expected"], 2)
        self.assertEqual(before["not_submitted"], 1)

        late_joiner = User.objects.create_user(
            email="ac-late@example.test", password="testpass123", role="student",
            first_name="Gulnora", last_name="Y",
        )
        self.group.students.add(late_joiner)

        after = group_reports.assignment_completion(self.assignment)
        self.assertEqual(after["expected"], 3)
        self.assertEqual(after["not_submitted"], 2)
        self.assertIn(
            late_joiner.pk, [row["student_id"] for row in after["missing"]],
        )

    def test_student_leaving_the_group_is_no_longer_expected(self):
        self.submit(student=self.zuhra)
        self.group.students.remove(self.zuhra)
        completion = group_reports.assignment_completion(self.assignment)
        self.assertEqual(completion["expected"], 1)
        # Their existing submission is surfaced as outside the current roster
        # rather than silently dropped.
        outside = [row for row in completion["submitted"] if row.get("outside_roster")]
        self.assertEqual(len(outside), 1)
        self.assertEqual(outside[0]["student_id"], self.zuhra.pk)

    def test_submission_from_outside_the_roster_is_surfaced(self):
        outsider = User.objects.create_user(
            email="ac-outsider@example.test", password="testpass123", role="student",
        )
        self.submit(student=outsider)
        completion = group_reports.assignment_completion(self.assignment)
        self.assertEqual(completion["expected"], 2)
        self.assertEqual(completion["graded"], 0)
        self.assertEqual(completion["not_submitted"], 2)
        outside = [row for row in completion["submitted"] if row.get("outside_roster")]
        self.assertEqual(len(outside), 1)
        self.assertEqual(outside[0]["student_id"], outsider.pk)

    def test_submissions_pointing_at_another_assignment_are_ignored(self):
        other_topic = EssayTopic.objects.create(
            title="Boshqa", description="d", created_by=self.teacher,
        )
        other_assignment = group_reports.create_assignment(
            topic=other_topic, group=self.group, assigned_by=self.teacher,
        )
        self.submit(assignment=other_assignment, topic=other_topic)

        completion = group_reports.assignment_completion(self.assignment)
        self.assertEqual(completion["graded"], 0)
        self.assertEqual(completion["not_submitted"], 2)

    def test_average_uses_only_graded_scores(self):
        self.submit(student=self.ali, total_score=20)
        self.submit(student=self.zuhra, status=EssaySubmission.Status.PENDING,
                    total_score=0)
        completion = group_reports.assignment_completion(self.assignment)
        self.assertEqual(completion["average_ai_score"], 20.0)

    def test_average_is_none_without_graded_submissions(self):
        self.assertEqual(
            group_reports.assignment_completion(self.assignment)["average_ai_score"],
            None,
        )

    def test_completion_reports_group_and_topic_context(self):
        completion = group_reports.assignment_completion(self.assignment)
        self.assertEqual(completion["group_id"], self.group.pk)
        self.assertEqual(completion["group_name"], "9-A")
        self.assertEqual(completion["topic_id"], self.topic.pk)
        self.assertEqual(completion["topic_title"], "Tabiat")
        self.assertTrue(completion["is_active"])

    def test_source_label_is_reported_for_submitters(self):
        self.submit(student=self.ali, source=EssaySubmission.Source.TELEGRAM)
        completion = group_reports.assignment_completion(self.assignment)
        row = next(r for r in completion["submitted"] if r["student_id"] == self.ali.pk)
        self.assertEqual(row["source_label"], "TELEGRAM")


class OverdueAssignmentTests(_AssignmentFixture):
    def _make_overdue(self, *, group=None):
        return group_reports.create_assignment(
            topic=self.topic, group=group or self.group, assigned_by=self.teacher,
            due_at=timezone.now() - dt.timedelta(days=1),
        )

    def test_overdue_lists_only_assignments_with_missing_work(self):
        self._make_overdue()
        # Two students expected, nothing submitted -> overdue.
        rows = group_reports.overdue_assignments(self.teacher)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["not_submitted"], 2)
        self.assertEqual(rows[0]["expected"], 2)
        self.assertEqual(rows[0]["group_name"], "9-A")
        self.assertEqual(rows[0]["teacher_id"], self.teacher.pk)

        self.submit(student=self.ali)
        self.submit(student=self.zuhra)
        self.assertEqual(group_reports.overdue_assignments(self.teacher), [])

    def test_not_yet_due_assignment_is_not_overdue(self):
        group_reports.create_assignment(
            topic=self.topic, group=self.group, assigned_by=self.teacher,
            due_at=timezone.now() + dt.timedelta(days=2),
        )
        self.assertEqual(group_reports.overdue_assignments(self.teacher), [])

    def test_assignment_without_due_date_is_not_overdue(self):
        self.assertEqual(group_reports.overdue_assignments(self.teacher), [])

    def test_overdue_is_scoped_to_the_calling_teacher(self):
        self._make_overdue()
        self.assertEqual(group_reports.overdue_assignments(self.other_teacher), [])
        # A platform admin sees it across the platform.
        admin = User.objects.create_superuser(
            email="ac-admin@example.test", password="testpass123",
        )
        self.assertEqual(len(group_reports.overdue_assignments(admin)), 1)


class TeacherOverviewScopingTests(_AssignmentFixture):
    def test_overview_only_lists_owned_groups(self):
        self.submit(student=self.ali)
        overview = group_reports.teacher_essay_overview(self.teacher)
        self.assertEqual([row["group_name"] for row in overview["groups"]], ["9-A"])
        self.assertEqual(overview["groups"][0]["graded"], 1)
        self.assertEqual(overview["groups"][0]["roster_size"], 2)

    def test_overview_excludes_another_teachers_submissions(self):
        foreign_assignment = group_reports.create_assignment(
            topic=self.topic, group=self.foreign_group, assigned_by=self.other_teacher,
        )
        shared = User.objects.create_user(
            email="ac-shared@example.test", password="testpass123", role="student",
        )
        self.group.students.add(shared)
        self.foreign_group.students.add(shared)
        EssaySubmission.objects.create(
            student=shared, topic=self.topic, assignment=foreign_assignment,
            essay_text="Matn " * 60, status=EssaySubmission.Status.GRADED,
            total_score=19, max_score=24,
        )

        overview = group_reports.teacher_essay_overview(self.teacher)
        self.assertEqual(overview["groups"][0]["graded"], 0)
        self.assertEqual(
            group_reports.group_essay_results(self.group)["total"], 0,
        )
