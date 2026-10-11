"""Teacher group essay report regressions.

The reporting contract: only explicit group context is reportable (an
assignment for this group, or the student's own ``group_visible`` opt-in), the
AI raw score, the teacher-adjusted grade and the converted *practice* score stay
distinct concepts, and a pending essay is never presented as graded.
"""
import datetime as dt

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.courses.models import StudentGroup
from apps.essays import group_reports
from apps.essays.models import EssayAssignment, EssaySubmission, EssayTopic

TODAY = timezone.localdate()


class _ReportFixture(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            email="gr-teacher@example.test", password="testpass123", role="teacher",
        )
        self.other_teacher = User.objects.create_user(
            email="gr-other@example.test", password="testpass123", role="teacher",
        )
        self.ali = User.objects.create_user(
            email="gr-ali@example.test", password="testpass123", role="student",
            first_name="Ali", last_name="Valiyev",
        )
        self.zuhra = User.objects.create_user(
            email="gr-zuhra@example.test", password="testpass123", role="student",
            first_name="Zuhra", last_name="Karimova",
        )
        self.gulnora = User.objects.create_user(
            email="gr-gulnora@example.test", password="testpass123", role="student",
            first_name="Gulnora", last_name="Yusupova",
        )
        self.group = StudentGroup.objects.create(teacher=self.teacher, name="9-A")
        self.group.students.add(self.ali, self.zuhra, self.gulnora)
        self.foreign_group = StudentGroup.objects.create(
            teacher=self.other_teacher, name="10-B",
        )
        self.topic = EssayTopic.objects.create(
            title="Kitobxonlik", description="d", created_by=self.teacher,
        )
        self.assignment = EssayAssignment.objects.create(
            topic=self.topic, group=self.group, assigned_by=self.teacher,
        )

    def submit(
        self,
        *,
        student=None,
        status=EssaySubmission.Status.GRADED,
        source=EssaySubmission.Source.WEB,
        visibility=EssaySubmission.GroupVisibility.ASSIGNMENT_ONLY,
        assignment="default",
        total_score=20,
        final_score=None,
        topic="default",
    ):
        # `topic=None` must mean "no topic" (a general essay), so the default is
        # a sentinel rather than None — the same pattern as `assignment`.
        return EssaySubmission.objects.create(
            student=student or self.ali,
            topic=self.topic if topic == "default" else topic,
            assignment=self.assignment if assignment == "default" else assignment,
            essay_text="Matn " * 60,
            status=status,
            total_score=total_score,
            max_score=24,
            final_score=final_score,
            source=source,
            group_visibility=visibility,
            submitted_at=timezone.now(),
        )


class ChannelSynchronizationTests(_ReportFixture):
    """Website, bot and Mini App submissions all land in one report."""

    def test_web_and_telegram_submissions_appear_in_the_same_report(self):
        web = self.submit(source=EssaySubmission.Source.WEB, total_score=20)
        bot = self.submit(
            student=self.zuhra, source=EssaySubmission.Source.TELEGRAM,
            total_score=18,
        )
        tma = self.submit(
            student=self.gulnora, source=EssaySubmission.Source.TMA,
            total_score=16,
        )

        report = group_reports.group_essay_results(self.group)
        self.assertEqual(report["total"], 3)
        by_id = {row["submission_id"]: row for row in report["results"]}
        self.assertEqual(by_id[web.pk]["source_label"], "WEB")
        self.assertEqual(by_id[bot.pk]["source_label"], "TELEGRAM")
        self.assertEqual(by_id[tma.pk]["source_label"], "TMA")
        self.assertTrue(all(row["is_graded"] for row in report["results"]))

    def test_source_filter_selects_one_channel(self):
        self.submit(source=EssaySubmission.Source.WEB)
        self.submit(student=self.zuhra, source=EssaySubmission.Source.TELEGRAM)

        report = group_reports.group_essay_results(
            self.group, source=EssaySubmission.Source.TELEGRAM,
        )
        self.assertEqual(report["total"], 1)
        self.assertEqual(report["results"][0]["student_id"], self.zuhra.pk)


class VisibilityTests(_ReportFixture):
    """Membership alone is never enough to expose an essay."""

    def test_general_essay_with_default_visibility_is_not_reported(self):
        self.submit(assignment=None, topic=None)
        report = group_reports.group_essay_results(self.group)
        self.assertEqual(report["total"], 0)

    def test_group_visible_general_essay_is_reported(self):
        submission = self.submit(
            assignment=None, topic=None,
            visibility=EssaySubmission.GroupVisibility.GROUP_VISIBLE,
        )
        self.assertIsNone(submission.topic_id)
        report = group_reports.group_essay_results(self.group)
        self.assertEqual(report["total"], 1)
        self.assertEqual(report["results"][0]["topic_title"], "Umumiy esse")

    def test_private_submission_is_never_reported_even_when_assigned(self):
        private = self.submit(visibility=EssaySubmission.GroupVisibility.PRIVATE)
        report = group_reports.group_essay_results(self.group)
        self.assertEqual(report["total"], 0)
        self.assertNotIn(
            private.pk, [row["submission_id"] for row in report["results"]],
        )

    def test_group_visible_essay_from_a_non_member_is_not_reported(self):
        outsider = User.objects.create_user(
            email="gr-outsider@example.test", password="testpass123", role="student",
        )
        self.submit(
            student=outsider, assignment=None, topic=None,
            visibility=EssaySubmission.GroupVisibility.GROUP_VISIBLE,
        )
        report = group_reports.group_essay_results(self.group)
        self.assertEqual(report["total"], 0)

    def test_student_with_no_submission_has_no_rows(self):
        self.submit(student=self.ali)
        report = group_reports.group_essay_results(self.group)
        self.assertEqual(
            {row["student_id"] for row in report["results"]}, {self.ali.pk},
        )


class StateAndScoreTests(_ReportFixture):
    def test_pending_submission_is_not_reported_as_graded(self):
        self.submit(status=EssaySubmission.Status.PENDING, total_score=0)
        report = group_reports.group_essay_results(self.group)
        self.assertEqual(report["total"], 1)
        self.assertEqual(report["graded"], 0)
        self.assertEqual(report["pending"], 1)
        row = report["results"][0]
        self.assertFalse(row["is_graded"])
        self.assertTrue(row["is_pending"])

    def test_error_submission_is_reported_as_failed(self):
        self.submit(status=EssaySubmission.Status.ERROR, total_score=0)
        report = group_reports.group_essay_results(self.group)
        self.assertEqual(report["failed"], 1)
        self.assertEqual(report["graded"], 0)
        self.assertTrue(report["results"][0]["is_failed"])

    def test_state_filter_splits_graded_pending_and_failed(self):
        self.submit()
        self.submit(student=self.zuhra, status=EssaySubmission.Status.PENDING,
                    total_score=0)
        self.submit(student=self.gulnora, status=EssaySubmission.Status.ERROR,
                    total_score=0)

        self.assertEqual(
            group_reports.group_essay_results(self.group, state="graded")["total"], 1,
        )
        self.assertEqual(
            group_reports.group_essay_results(self.group, state="pending")["total"], 1,
        )
        self.assertEqual(
            group_reports.group_essay_results(self.group, state="failed")["total"], 1,
        )

    def test_ai_and_teacher_scores_stay_distinct(self):
        self.submit(total_score=20, final_score=22)
        row = group_reports.group_essay_results(self.group)["results"][0]
        self.assertEqual(row["ai_total_score"], 20.0)
        self.assertEqual(row["final_score"], 22.0)
        # The effective score is the teacher-adjusted one when present.
        self.assertEqual(row["effective_score"], 22.0)
        # ...and the conversion follows the teacher grade, not the AI grade.
        self.assertEqual(row["converted_practice_score"], 69)
        self.assertEqual(row["max_score"], 24)

    def test_converted_score_matches_the_existing_practice_rule(self):
        self.submit(total_score=20)
        row = group_reports.group_essay_results(self.group)["results"][0]
        self.assertIsNone(row["final_score"])
        self.assertEqual(row["effective_score"], 20.0)
        # 20/24 * 75 = 62.5 -> round-half-even gives 62, matching the
        # leaderboard conversion exactly. It is a PRACTICE score only.
        self.assertEqual(row["converted_practice_score"], 62)

    def test_average_excludes_ungraded_rows(self):
        self.submit(total_score=20)
        self.submit(student=self.zuhra, total_score=10)
        self.submit(student=self.gulnora, status=EssaySubmission.Status.PENDING,
                    total_score=0)

        report = group_reports.group_essay_results(self.group)
        self.assertEqual(report["graded"], 2)
        self.assertEqual(report["pending"], 1)
        self.assertEqual(report["average_ai_score"], 15.0)

    def test_average_is_none_when_nothing_is_graded(self):
        self.submit(status=EssaySubmission.Status.PENDING, total_score=0)
        report = group_reports.group_essay_results(self.group)
        self.assertIsNone(report["average_ai_score"])

    def test_teacher_review_requirement_is_surfaced(self):
        self.submit(status=EssaySubmission.Status.PENDING_TEACHER, total_score=14)
        report = group_reports.group_essay_results(self.group)
        self.assertTrue(report["results"][0]["teacher_review_required"])

        filtered = group_reports.group_essay_results(
            self.group, review_required=True,
        )
        self.assertEqual(filtered["total"], 1)

    def test_review_request_by_student_is_flagged(self):
        submission = self.submit(total_score=17)
        submission.teacher_review_requested = True
        submission.save(update_fields=["teacher_review_requested", "updated_at"])
        report = group_reports.group_essay_results(
            self.group, review_required=True,
        )
        self.assertEqual(report["total"], 1)
        self.assertTrue(report["results"][0]["teacher_review_requested"])


class FilterAndPaginationTests(_ReportFixture):
    def test_student_filter_and_date_range(self):
        self.submit(student=self.ali)
        self.submit(student=self.zuhra)

        by_student = group_reports.group_essay_results(
            self.group, student_id=self.ali.pk,
        )
        self.assertEqual(by_student["total"], 1)
        self.assertEqual(by_student["results"][0]["student_id"], self.ali.pk)

        outside = group_reports.group_essay_results(
            self.group,
            start=TODAY + dt.timedelta(days=5),
            end=TODAY + dt.timedelta(days=10),
        )
        self.assertEqual(outside["total"], 0)

        inside = group_reports.group_essay_results(
            self.group, start=TODAY, end=TODAY,
        )
        self.assertEqual(inside["total"], 2)

    def test_pagination_reports_accurate_total_and_window(self):
        for index in range(3):
            self.submit(student=[self.ali, self.zuhra, self.gulnora][index])

        page = group_reports.group_essay_results(self.group, limit=2, offset=0)
        self.assertEqual(page["total"], 3)
        self.assertEqual(page["shown"], 2)
        self.assertEqual(page["limit"], 2)
        self.assertEqual(page["offset"], 0)

        second = group_reports.group_essay_results(self.group, limit=2, offset=2)
        self.assertEqual(second["total"], 3)
        self.assertEqual(second["shown"], 1)
        self.assertNotEqual(
            {row["submission_id"] for row in page["results"]},
            {row["submission_id"] for row in second["results"]},
        )

    def test_results_are_newest_first(self):
        older = self.submit()
        EssaySubmission.objects.filter(pk=older.pk).update(
            submitted_at=timezone.now() - dt.timedelta(days=2),
        )
        newer = self.submit(student=self.zuhra)

        report = group_reports.group_essay_results(self.group)
        self.assertEqual(report["results"][0]["submission_id"], newer.pk)

    def test_group_essay_summary_counts_not_submitted(self):
        self.submit(student=self.ali)
        summary = group_reports.group_essay_summary(self.group)
        self.assertEqual(summary["roster_size"], 3)
        self.assertEqual(summary["graded"], 1)
        self.assertEqual(summary["not_submitted"], 2)
        self.assertEqual(summary["average_ai_score"], 20.0)

    def test_group_essay_summary_for_an_assignment_delegates_to_completion(self):
        self.submit(student=self.ali)
        self.submit(student=self.zuhra, status=EssaySubmission.Status.PENDING,
                    total_score=0)
        summary = group_reports.group_essay_summary(
            self.group, assignment=self.assignment,
        )
        self.assertEqual(summary["assignment_id"], self.assignment.pk)
        self.assertEqual(summary["roster_size"], 3)
        self.assertEqual(summary["graded"], 1)
        self.assertEqual(summary["pending"], 1)
        self.assertEqual(summary["not_submitted"], 1)
