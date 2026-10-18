"""Milliy Sertifikat Exam Engine — backend coverage.

Covers: GAP_FILL, MATCHING, WRITTEN + essay bridge, ReadingPassage,
sections + timing, attempt state machine, autosave, objective grading,
section/aggregate scoring, scoring profile/versioning, RBAC/ownership,
answer-key leakage, certificate gating, panel content creation.
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.accounts.models import User
from apps.courses.models import Category, Course
from apps.results.models import Certificate, Result, ResultSectionScore
from apps.tests.models import (
    AttemptSectionProgress,
    ExamScoringProfile,
    ExamSection,
    ExamWrittenBridge,
    GapBlank,
    MatchingOption,
    MatchingPair,
    MatchingPrompt,
    Question,
    ReadingPassage,
    StudentAnswer,
    Test,
    TestAttempt,
)
from apps.tests.scoring import (
    aggregate,
    blank_is_correct,
    grade_gap_fill,
    grade_matching,
    normalize_text,
    written_earned,
)
from apps.tests.services import (
    ExamBridgeService,
    SaveAnswerService,
    StartAttemptService,
    SubmitAttemptService,
)


def make_user(email, role="student", **kw):
    params = {"email": email, "password": "pass12345", "role": role,
              "first_name": "T", "last_name": "U"}
    params.update(kw)
    return User.objects.create_user(**params)


def make_course(teacher, title="Course"):
    category = Category.objects.create(name=f"cat-{title}-{Course.objects.count()}")
    return Course.objects.create(
        teacher=teacher, category=category, title=title, description="d",
        status=Course.Status.PUBLISHED,
    )


def make_test(teacher, title="Exam", **kw):
    params = {"title": title, "description": "d",
              "course": make_course(teacher, title=title),
              "status": Test.Status.PUBLISHED}
    params.update(kw)
    return Test.objects.create(**params)


def make_section(test, code="READING", name="Reading", duration=0, order=0):
    return ExamSection.objects.create(
        test=test, code=code, name=name, order=order,
        duration_minutes=duration,
    )


def make_passage(test, section=None, order=0, content="Matn. " * 20):
    return ReadingPassage.objects.create(
        test=test, section=section, title=f"Passage {order}",
        content=content, order=order,
    )


def make_gap(test, blanks, section=None, passage=None, points=4,
             partial=False, position=1):
    q = Question.objects.create(
        test=test, section=section, reading_passage=passage,
        text="To'ldiring: ___ ... ___", question_type="gap_fill",
        points=points, position=position,
        config={"partial_credit": partial},
    )
    for pos, answers in blanks.items():
        for a in answers:
            GapBlank.objects.create(question=q, position=pos, answer_text=a)
    return q


def make_match(test, prompts, options, pairs, section=None, passage=None,
               points=6, partial=False, position=2):
    q = Question.objects.create(
        test=test, section=section, reading_passage=passage,
        text="Moslashtiring", question_type="matching",
        points=points, position=position,
        config={"partial_credit": partial},
    )
    pmap, omap = {}, {}
    for i, text in enumerate(prompts):
        pmap[i] = MatchingPrompt.objects.create(question=q, text=text, position=i)
    for i, text in enumerate(options):
        omap[i] = MatchingOption.objects.create(question=q, text=text, position=i)
    for ppos, opos in pairs.items():
        MatchingPair.objects.create(prompt=pmap[ppos], correct_option=omap[opos])
    return q


def make_written(test, section=None, points=10, position=3, min_words=0, max_words=0):
    return Question.objects.create(
        test=test, section=section, text="Esse yozing",
        question_type="written", points=points, position=position,
        config={"min_words": min_words, "max_words": max_words},
    )


def no_dispatch():
    """Patch essay AI dispatch (deterministic offline tests)."""
    return patch.object(ExamBridgeService, "_dispatch", lambda sub: None)


class ScoringUnitTests(TestCase):
    def test_normalize(self):
        self.assertEqual(normalize_text("  ToshKENT\n\t "), "toshkent")
        self.assertEqual(normalize_text("Toshkent", case_sensitive=True), "Toshkent")

    def test_blank_matching(self):
        self.assertTrue(blank_is_correct(" olMa ", ["OLMA", "anor"]))
        self.assertFalse(blank_is_correct("", ["olma"]))
        self.assertFalse(blank_is_correct("nok", ["olma"]))

    def test_gap_full_and_partial(self):
        blanks = {0: ["olma"], 1: ["anor", "behi"]}
        full = grade_gap_fill(blanks, {0: " OLMA ", 1: "BEHI"}, 4)
        self.assertTrue(full.fully_correct)
        self.assertEqual(full.earned, Decimal("4"))
        default = grade_gap_fill(blanks, {0: "olma", 1: "nok"}, 4)
        self.assertFalse(default.fully_correct)
        self.assertEqual(default.earned, Decimal("0"))
        partial = grade_gap_fill(blanks, {0: "olma", 1: "nok"}, 4, partial_credit=True)
        self.assertEqual(partial.earned, Decimal("2.00"))
        self.assertEqual(partial.blanks_correct, 1)

    def test_matching_scores(self):
        correct = {1: 11, 2: 22, 3: 33}
        ms = grade_matching(correct, {1: 11, 2: 22, 3: 33}, 6)
        self.assertTrue(ms.fully_correct)
        self.assertEqual(ms.earned, Decimal("6"))
        default = grade_matching(correct, {1: 11, 2: 99, 3: 33}, 6)
        self.assertEqual(default.earned, Decimal("0"))
        partial = grade_matching(correct, {1: 11, 2: 99, 3: 33}, 6, partial_credit=True)
        self.assertEqual(partial.earned, Decimal("4.00"))
        # Missing response counts as wrong, never as correct.
        missing = grade_matching(correct, {1: 11}, 6, partial_credit=True)
        self.assertEqual(missing.pairs_correct, 1)

    def test_written_earned(self):
        self.assertIsNone(written_earned(10, None))
        self.assertEqual(written_earned(10, Decimal("12"), 24), Decimal("5.00"))
        self.assertEqual(written_earned(10, Decimal("24"), 24), Decimal("10.00"))

    def test_aggregate_weights(self):
        from apps.tests.scoring import QuestionScore

        qs = [
            QuestionScore(1, Decimal("8"), Decimal("10"), True, True, "READING", 1),
            QuestionScore(2, Decimal("5"), Decimal("10"), True, True, "WRITING", 2, kind="written"),
        ]
        agg = aggregate(qs, weights={"READING": 1, "WRITING": 2})
        self.assertEqual(agg.objective_earned, Decimal("8"))
        self.assertEqual(agg.writing_earned, Decimal("5"))
        self.assertEqual(agg.total_earned, Decimal("13"))
        # (8*1 + 5*2) / (10*1 + 10*2) * 100 = 60
        self.assertEqual(agg.weighted_percentage, Decimal("60.00"))
        plain = aggregate(qs, weights={})
        self.assertEqual(plain.weighted_percentage, Decimal("65.00"))


class GapFillTests(TestCase):
    def setUp(self):
        self.teacher = make_user("gap-t@e.com", "teacher")
        self.student = make_user("gap-s@e.com")
        self.test = make_test(self.teacher, title="Gap exam")
        self.q = make_gap(self.test, {0: ["olma"], 1: ["anor", "behi"]})

    def _attempt(self):
        return StartAttemptService.execute(test_id=self.test.id, student=self.student)

    def test_full_correct(self):
        attempt = self._attempt()
        SaveAnswerService.execute(
            attempt.id, self.q.id, [], self.student,
            gap_answers={"0": "olma", "1": "behi"},
        )
        out = SubmitAttemptService.execute(attempt.id, self.student)
        self.assertEqual(out.correct_answers, 1)
        self.assertEqual(out.score, Decimal("4"))

    def test_partial_default_zero(self):
        attempt = self._attempt()
        SaveAnswerService.execute(
            attempt.id, self.q.id, [], self.student,
            gap_answers={"0": "olma", "1": "nok"},
        )
        out = SubmitAttemptService.execute(attempt.id, self.student)
        self.assertEqual(out.correct_answers, 0)
        self.assertEqual(out.score, Decimal("0"))

    def test_partial_credit_config(self):
        self.q.config = {"partial_credit": True}
        self.q.save(update_fields=["config"])
        attempt = self._attempt()
        SaveAnswerService.execute(
            attempt.id, self.q.id, [], self.student,
            gap_answers={"0": "olma", "1": "nok"},
        )
        out = SubmitAttemptService.execute(attempt.id, self.student)
        self.assertEqual(out.score, Decimal("2.00"))

    def test_missing_blank_is_wrong(self):
        attempt = self._attempt()
        SaveAnswerService.execute(
            attempt.id, self.q.id, [], self.student, gap_answers={"0": "olma"},
        )
        out = SubmitAttemptService.execute(attempt.id, self.student)
        self.assertEqual(out.correct_answers, 0)

    def test_extra_positions_ignored(self):
        attempt = self._attempt()
        SaveAnswerService.execute(
            attempt.id, self.q.id, [], self.student,
            gap_answers={"0": "olma", "1": "anor", "99": "hacker"},
        )
        out = SubmitAttemptService.execute(attempt.id, self.student)
        self.assertEqual(out.correct_answers, 1)
        ans = StudentAnswer.objects.get(attempt=attempt, question=self.q)
        self.assertFalse(ans.gap_responses.filter(blank_position=99).exists())

    def test_normalization(self):
        attempt = self._attempt()
        SaveAnswerService.execute(
            attempt.id, self.q.id, [], self.student,
            gap_answers={"0": "  OLMA\n", "1": "\tAnor  "},
        )
        out = SubmitAttemptService.execute(attempt.id, self.student)
        self.assertEqual(out.correct_answers, 1)

    def test_no_answer_key_leakage(self):
        attempt = self._attempt()
        self.client.force_login(self.student)
        detail = self.client.get(f"/api/tests/{self.test.id}/")
        body = detail.content.decode()
        self.assertNotIn("behi", body)
        self.assertNotIn("anor", body)
        att = self.client.get(f"/api/tests/attempts/{attempt.id}/")
        abody = att.content.decode()
        self.assertNotIn("behi", abody)
        self.assertNotIn("anor", abody)
        # Structure present without keys.
        payload = att.json()["questions"][0]
        self.assertEqual(payload["question_type"], "gap_fill")
        self.assertEqual(len(payload["gaps"]), 2)


class MatchingTests(TestCase):
    def setUp(self):
        self.teacher = make_user("m-t@e.com", "teacher")
        self.student = make_user("m-s@e.com")
        self.test = make_test(self.teacher, title="Match exam")
        self.q = make_match(
            self.test, prompts=["1+1", "2+2", "3+3"],
            options=["ikki", "to'rt", "olti", "yetti"],
            pairs={0: 0, 1: 1, 2: 2},
        )

    def _attempt(self):
        return StartAttemptService.execute(test_id=self.test.id, student=self.student)

    def _mapping(self, *oids):
        pids = list(MatchingPrompt.objects.filter(question=self.q).order_by("position")
                    .values_list("id", flat=True))
        oids_all = list(MatchingOption.objects.filter(question=self.q).order_by("position")
                         .values_list("id", flat=True))
        return {str(p): o for p, o in zip(pids, [oids_all[i] for i in oids])}

    def test_full_correct(self):
        attempt = self._attempt()
        SaveAnswerService.execute(
            attempt.id, self.q.id, [], self.student, matching=self._mapping(0, 1, 2))
        out = SubmitAttemptService.execute(attempt.id, self.student)
        self.assertEqual(out.correct_answers, 1)
        self.assertEqual(out.score, Decimal("6"))

    def test_partial_default_zero(self):
        attempt = self._attempt()
        SaveAnswerService.execute(
            attempt.id, self.q.id, [], self.student, matching=self._mapping(0, 1, 3))
        out = SubmitAttemptService.execute(attempt.id, self.student)
        self.assertEqual(out.correct_answers, 0)
        self.assertEqual(out.score, Decimal("0"))

    def test_partial_credit(self):
        self.q.config = {"partial_credit": True}
        self.q.save(update_fields=["config"])
        attempt = self._attempt()
        SaveAnswerService.execute(
            attempt.id, self.q.id, [], self.student, matching=self._mapping(0, 1, 3))
        out = SubmitAttemptService.execute(attempt.id, self.student)
        self.assertEqual(out.score, Decimal("4.00"))

    def test_invalid_option_rejected(self):
        attempt = self._attempt()
        pids = list(MatchingPrompt.objects.filter(question=self.q).values_list("id", flat=True))
        with self.assertRaises(ValueError):
            SaveAnswerService.execute(
                attempt.id, self.q.id, [], self.student,
                matching={str(pids[0]): 999999})

    def test_unknown_prompt_rejected(self):
        attempt = self._attempt()
        with self.assertRaises(ValueError):
            SaveAnswerService.execute(
                attempt.id, self.q.id, [], self.student, matching={"999999": 1})

    def test_missing_mapping_is_wrong(self):
        attempt = self._attempt()
        pids = list(MatchingPrompt.objects.filter(question=self.q).order_by("position")
                    .values_list("id", flat=True))
        oids = list(MatchingOption.objects.filter(question=self.q).order_by("position")
                    .values_list("id", flat=True))
        SaveAnswerService.execute(
            attempt.id, self.q.id, [], self.student,
            matching={str(pids[0]): oids[0]})
        out = SubmitAttemptService.execute(attempt.id, self.student)
        self.assertEqual(out.correct_answers, 0)

    def test_shuffled_display_grades_same(self):
        self.test.shuffle_choices = True
        self.test.save(update_fields=["shuffle_choices"])
        attempt = self._attempt()
        SaveAnswerService.execute(
            attempt.id, self.q.id, [], self.student, matching=self._mapping(0, 1, 2))
        out = SubmitAttemptService.execute(attempt.id, self.student)
        self.assertEqual(out.correct_answers, 1)

    def test_no_mapping_leakage(self):
        attempt = self._attempt()
        self.client.force_login(self.student)
        for url in (f"/api/tests/{self.test.id}/",
                    f"/api/tests/attempts/{attempt.id}/"):
            body = self.client.get(url).content.decode()
            self.assertNotIn("correct_option", body)
            self.assertNotIn("is_correct", body)
        payload = self.client.get(
            f"/api/tests/attempts/{attempt.id}/").json()["questions"][0]
        self.assertEqual(len(payload["prompts"]), 3)
        self.assertEqual(len(payload["matching_options"]), 4)


class WrittenBridgeTests(TestCase):
    def setUp(self):
        self.teacher = make_user("w-t@e.com", "teacher")
        self.student = make_user("w-s@e.com")
        self.test = make_test(self.teacher, title="Written exam", pass_percentage=50)
        self.q = make_written(self.test, points=10)

    def _attempt(self):
        return StartAttemptService.execute(test_id=self.test.id, student=self.student)

    def test_autosave_draft_no_bridge(self):
        attempt = self._attempt()
        ans = SaveAnswerService.execute(
            attempt.id, self.q.id, [], self.student, written_text="Mening essem. " * 20)
        ans.refresh_from_db()
        self.assertTrue(ans.written_word_count > 0)
        self.assertFalse(ExamWrittenBridge.objects.filter(answer=ans).exists())

    def test_submit_creates_one_submission_pending(self):
        from apps.essays.models import EssaySubmission

        attempt = self._attempt()
        SaveAnswerService.execute(
            attempt.id, self.q.id, [], self.student, written_text="Matn. " * 30)
        with no_dispatch():
            out = SubmitAttemptService.execute(attempt.id, self.student)
        self.assertEqual(out.grading_status, "pending_grading")
        self.assertEqual(out.pending_written_count, 1)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, TestAttempt.Status.PENDING_GRADING)
        ans = StudentAnswer.objects.get(attempt=attempt, question=self.q)
        bridge = ExamWrittenBridge.objects.get(answer=ans)
        self.assertIsNotNone(bridge.essay_submission)
        self.assertEqual(bridge.rubric_version, "grandec-essay-bmb-20p-v1")
        self.assertEqual(
            EssaySubmission.objects.filter(pk=bridge.essay_submission_id).count(), 1)
        result = Result.objects.get(attempt=attempt)
        self.assertEqual(result.grading_status, "pending_grading")
        self.assertFalse(result.is_passed)
        # No certificate while writing is pending.
        self.assertFalse(Certificate.objects.filter(result=result).exists())

    def test_duplicate_submit_no_duplicate_submission(self):
        from apps.essays.models import EssaySubmission

        attempt = self._attempt()
        SaveAnswerService.execute(
            attempt.id, self.q.id, [], self.student, written_text="Matn. " * 30)
        with no_dispatch():
            SubmitAttemptService.execute(attempt.id, self.student)
            with self.assertRaises(ValueError):
                SubmitAttemptService.execute(attempt.id, self.student)
        self.assertEqual(EssaySubmission.objects.count(), 1)
        self.assertEqual(ExamWrittenBridge.objects.filter(attempt=attempt).count(), 1)

    def _grade_bridge(self, bridge, total=Decimal("18")):
        from apps.essays.models import EssaySubmission

        sub = bridge.essay_submission
        sub.transition_to(EssaySubmission.Status.GRADED)
        sub.total_score = total
        sub.save(update_fields=["status", "total_score"])

    def test_finalize_after_grading(self):
        attempt = self._attempt()
        SaveAnswerService.execute(
            attempt.id, self.q.id, [], self.student, written_text="Matn. " * 30)
        with no_dispatch():
            SubmitAttemptService.execute(attempt.id, self.student)
        ans = StudentAnswer.objects.get(attempt=attempt, question=self.q)
        bridge = ExamWrittenBridge.objects.get(answer=ans)
        self._grade_bridge(bridge, Decimal("18"))
        with no_dispatch():
            out = SubmitAttemptService.finalize_pending_grading(attempt.id, self.student)
        # 18/20 of 10 points = 9.00; percentage 90 >= 50 → passed.
        self.assertEqual(out.grading_status, "graded")
        self.assertEqual(out.writing_score, Decimal("9.00"))
        self.assertTrue(out.is_passed)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, TestAttempt.Status.COMPLETED)
        result = Result.objects.get(attempt=attempt)
        self.assertEqual(result.grading_status, "graded")
        self.assertEqual(result.rubric_version, "grandec-essay-bmb-20p-v1")
        self.assertEqual(result.scoring_version, "default:v1")
        # Default profile is UNVERIFIED → graded but no certificate.
        from apps.certificates.services.generation import certificate_status

        self.assertEqual(certificate_status(result), "rules_unverified")
        self.assertFalse(Certificate.objects.filter(result=result).exists())
        # After the profile is verified with a met threshold, finalize on the
        # COMPLETED attempt dispatches and the certificate is issued.
        from apps.tests.models import ExamScoringProfile

        profile = ExamScoringProfile.objects.get(name="default", version="v1")
        profile.is_verified = True
        profile.certificate_min_percentage = 70
        profile.save(update_fields=["is_verified", "certificate_min_percentage"])
        with no_dispatch():
            SubmitAttemptService.finalize_pending_grading(attempt.id, self.student)
        self.assertTrue(
            Certificate.objects.filter(result=result, status="generated").exists())

    def test_finalize_idempotent(self):
        attempt = self._attempt()
        SaveAnswerService.execute(
            attempt.id, self.q.id, [], self.student, written_text="Matn. " * 30)
        with no_dispatch():
            SubmitAttemptService.execute(attempt.id, self.student)
        ans = StudentAnswer.objects.get(attempt=attempt, question=self.q)
        self._grade_bridge(ExamWrittenBridge.objects.get(answer=ans))
        with no_dispatch():
            first = SubmitAttemptService.finalize_pending_grading(attempt.id, self.student)
            second = SubmitAttemptService.finalize_pending_grading(attempt.id, self.student)
        self.assertEqual(first.score, second.score)
        self.assertEqual(Result.objects.filter(attempt=attempt).count(), 1)

    def test_empty_written_is_unanswered(self):
        attempt = self._attempt()
        out = SubmitAttemptService.execute(attempt.id, self.student)
        self.assertEqual(out.grading_status, "graded")
        self.assertEqual(out.unanswered, 1)
        self.assertFalse(ExamWrittenBridge.objects.filter(attempt=attempt).exists())

    def test_finalize_endpoint_pending_returns_202(self):
        attempt = self._attempt()
        SaveAnswerService.execute(
            attempt.id, self.q.id, [], self.student, written_text="Matn. " * 30)
        self.client.force_login(self.student)
        with no_dispatch():
            self.client.post(f"/api/tests/attempts/{attempt.id}/submit/")
            resp = self.client.post(f"/api/tests/attempts/{attempt.id}/finalize/")
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(resp.json()["status"], "pending")


class ReadingSectionTests(TestCase):
    def setUp(self):
        self.teacher = make_user("r-t@e.com", "teacher")
        self.student = make_user("r-s@e.com")
        self.test = make_test(self.teacher, title="Reading exam")
        self.section = make_section(self.test, code="READING", name="O'qish")
        self.passage = make_passage(self.test, self.section, content="Bir bor ekan...")
        self.q1 = make_gap(self.test, {0: ["kitob"]}, section=self.section,
                           passage=self.passage, position=1)
        self.q2 = make_match(
            self.test, prompts=["a"], options=["b", "c"], pairs={0: 0},
            section=self.section, passage=self.passage, position=2)

    def test_passage_shared_not_duplicated(self):
        self.assertEqual(self.passage.questions.count(), 2)
        self.assertEqual(
            ReadingPassage.objects.filter(test=self.test).count(), 1)

    def test_payload_order_and_structure(self):
        attempt = StartAttemptService.execute(test_id=self.test.id, student=self.student)
        self.client.force_login(self.student)
        data = self.client.get(f"/api/tests/attempts/{attempt.id}/").json()
        self.assertEqual([q["id"] for q in data["questions"]],
                         [self.q1.id, self.q2.id])
        for q in data["questions"]:
            self.assertEqual(q["passage"]["content"], "Bir bor ekan...")
            self.assertEqual(q["section_id"], self.section.id)
        self.assertEqual(len(data["passages"]), 1)
        self.assertEqual(data["sections"][0]["code"], "READING")

    def test_section_timing_expiry(self):
        section = make_section(self.test, code="LANGUAGE", name="Til",
                               duration=1, order=1)
        from apps.tests.models import Choice, Question
        q = Question.objects.create(
            test=self.test, section=section, text="1+1?", position=9)
        c = Choice.objects.create(question=q, text="2", is_correct=True)
        attempt = StartAttemptService.execute(test_id=self.test.id, student=self.student)
        progress = AttemptSectionProgress.objects.get(attempt=attempt, section=section)
        AttemptSectionProgress.objects.filter(pk=progress.pk).update(
            started_at=timezone.now() - timedelta(minutes=5))
        with self.assertRaisesMessage(ValueError, "Bo'lim vaqti"):
            SaveAnswerService.execute(attempt.id, q.id, [c.id], self.student)
        progress.refresh_from_db()
        self.assertIsNotNone(progress.completed_at)
        # Other sections still accept answers.
        SaveAnswerService.execute(
            attempt.id, self.q1.id, [], self.student, gap_answers={"0": "kitob"})
        self.assertTrue(
            StudentAnswer.objects.filter(attempt=attempt, question=self.q1).exists())

    def test_section_progress_created_on_start(self):
        make_section(self.test, code="LANGUAGE", name="Til", duration=30, order=1)
        attempt = StartAttemptService.execute(test_id=self.test.id, student=self.student)
        self.client.force_login(self.student)
        data = self.client.get(f"/api/tests/attempts/{attempt.id}/").json()
        timed = [s for s in data["section_progress"]
                 if s["section_id"] != self.section.id]
        self.assertEqual(len(timed), 1)
        self.assertFalse(timed[0]["is_expired"])
        self.assertGreater(timed[0]["remaining_seconds"], 0)


class StateMachineTests(TestCase):
    def setUp(self):
        self.teacher = make_user("sm-t@e.com", "teacher")
        self.student = make_user("sm-s@e.com")
        self.test = make_test(self.teacher, title="SM exam")
        from apps.tests.models import Choice, Question
        self.q = Question.objects.create(test=self.test, text="1+1?", position=1)
        self.c = Choice.objects.create(question=self.q, text="2", is_correct=True)

    def test_transition_map(self):
        m = TestAttempt.STATUS_TRANSITIONS
        self.assertIn(TestAttempt.Status.COMPLETED, m[TestAttempt.Status.IN_PROGRESS])
        self.assertIn(TestAttempt.Status.PENDING_GRADING, m[TestAttempt.Status.IN_PROGRESS])
        self.assertEqual(m[TestAttempt.Status.PENDING_GRADING],
                         frozenset({TestAttempt.Status.COMPLETED}))
        for terminal in (TestAttempt.Status.COMPLETED, TestAttempt.Status.TIMEOUT,
                         TestAttempt.Status.CANCELLED):
            self.assertEqual(m[terminal], frozenset())

    def test_save_after_submit_rejected(self):
        attempt = StartAttemptService.execute(test_id=self.test.id, student=self.student)
        SaveAnswerService.execute(attempt.id, self.q.id, [self.c.id], self.student)
        SubmitAttemptService.execute(attempt.id, self.student)
        with self.assertRaises(ValueError):
            SaveAnswerService.execute(attempt.id, self.q.id, [self.c.id], self.student)

    def test_double_submit_rejected(self):
        attempt = StartAttemptService.execute(test_id=self.test.id, student=self.student)
        SubmitAttemptService.execute(attempt.id, self.student)
        with self.assertRaises(ValueError):
            SubmitAttemptService.execute(attempt.id, self.student)

    def test_finalize_non_pending_rejected(self):
        attempt = StartAttemptService.execute(test_id=self.test.id, student=self.student)
        with self.assertRaises(ValueError):
            SubmitAttemptService.finalize_pending_grading(attempt.id, self.student)

    def test_finalize_completed_is_idempotent(self):
        attempt = StartAttemptService.execute(test_id=self.test.id, student=self.student)
        first = SubmitAttemptService.execute(attempt.id, self.student)
        second = SubmitAttemptService.finalize_pending_grading(attempt.id, self.student)
        self.assertEqual(first.score, second.score)


class AutosaveTests(TestCase):
    def setUp(self):
        self.teacher = make_user("as-t@e.com", "teacher")
        self.student = make_user("as-s@e.com")
        self.other = make_user("as-o@e.com")
        self.test = make_test(self.teacher, title="Autosave exam")
        self.q = make_gap(self.test, {0: ["olma"], 1: ["anor"]})

    def test_repeated_saves_no_duplicates(self):
        attempt = StartAttemptService.execute(test_id=self.test.id, student=self.student)
        for text in ("ol", "olm", "olma"):
            SaveAnswerService.execute(
                attempt.id, self.q.id, [], self.student, gap_answers={"0": text, "1": "anor"})
        self.assertEqual(
            StudentAnswer.objects.filter(attempt=attempt, question=self.q).count(), 1)
        ans = StudentAnswer.objects.get(attempt=attempt, question=self.q)
        self.assertEqual(ans.gap_responses.count(), 2)
        self.assertEqual(
            ans.gap_responses.get(blank_position=0).response_text, "olma")

    def test_foreign_student_rejected(self):
        attempt = StartAttemptService.execute(test_id=self.test.id, student=self.student)
        with self.assertRaises(ValueError):
            SaveAnswerService.execute(
                attempt.id, self.q.id, [], self.other, gap_answers={"0": "olma"})

    def test_api_ownership(self):
        attempt = StartAttemptService.execute(test_id=self.test.id, student=self.student)
        self.client.force_login(self.other)
        resp = self.client.post(
            f"/api/tests/attempts/{attempt.id}/save-answer/",
            {"question_id": self.q.id, "gap_answers": {"0": "olma"}},
            content_type="application/json")
        self.assertEqual(resp.status_code, 404)
        resp = self.client.post(f"/api/tests/attempts/{attempt.id}/submit/")
        self.assertEqual(resp.status_code, 404)
        resp = self.client.get(f"/api/tests/attempts/{attempt.id}/")
        self.assertIn(resp.status_code, (403, 404))

    def test_anonymous_rejected(self):
        attempt = StartAttemptService.execute(test_id=self.test.id, student=self.student)
        resp = self.client.post(
            f"/api/tests/attempts/{attempt.id}/save-answer/",
            {"question_id": self.q.id, "gap_answers": {"0": "olma"}},
            content_type="application/json")
        self.assertIn(resp.status_code, (401, 403))

    def test_teacher_cannot_start(self):
        self.client.force_login(self.teacher)
        resp = self.client.post(f"/api/tests/{self.test.id}/start/")
        self.assertEqual(resp.status_code, 403)


class AggregateScoringTests(TestCase):
    def test_mixed_exam_sections_and_pending(self):
        from apps.tests.models import Choice, Question

        teacher = make_user("ag-t@e.com", "teacher")
        student = make_user("ag-s@e.com")
        test = make_test(teacher, title="Mixed", pass_percentage=50)
        s_read = make_section(test, code="READING", name="O'qish", order=0)
        s_lang = make_section(test, code="LANGUAGE", name="Til", order=1)
        s_write = make_section(test, code="WRITING", name="Yozuv", order=2)
        passage = make_passage(test, s_read)

        q_single = Question.objects.create(
            test=test, section=s_read, reading_passage=passage, text="s",
            question_type="single", points=2, position=1)
        sc = Choice.objects.create(question=q_single, text="ok", is_correct=True)
        Choice.objects.create(question=q_single, text="nope")
        q_multi = Question.objects.create(
            test=test, section=s_lang, text="m", question_type="multiple",
            points=3, position=2)
        m1 = Choice.objects.create(question=q_multi, text="a", is_correct=True)
        Choice.objects.create(question=q_multi, text="b", is_correct=True)
        q_text = Question.objects.create(
            test=test, section=s_lang, text="t", question_type="text",
            correct_text="Tashkent", points=5, position=3)
        q_gap = make_gap(test, {0: ["x"], 1: ["y"]}, section=s_lang, position=4)
        q_match = make_match(test, prompts=["p1", "p2", "p3"],
                             options=["o1", "o2", "o3", "o4"],
                             pairs={0: 0, 1: 1, 2: 2},
                             section=s_read, passage=passage, points=6,
                             partial=True, position=5)
        q_written = make_written(test, section=s_write, points=10, position=6)

        attempt = StartAttemptService.execute(test_id=test.id, student=student)
        SaveAnswerService.execute(attempt.id, q_single.id, [sc.id], student)
        # Multiple partially wrong (only one of two correct).
        SaveAnswerService.execute(attempt.id, q_multi.id, [m1.id], student)
        SaveAnswerService.execute(
            attempt.id, q_text.id, [], student, text_answer="  tashkent ")
        SaveAnswerService.execute(
            attempt.id, q_gap.id, [], student, gap_answers={"0": "x", "1": "zzz"})
        mp = list(MatchingPrompt.objects.filter(question=q_match).order_by("position"))
        mo = list(MatchingOption.objects.filter(question=q_match).order_by("position"))
        SaveAnswerService.execute(
            attempt.id, q_match.id, [], student,
            matching={str(mp[0].id): mo[0].id, str(mp[1].id): mo[1].id,
                      str(mp[2].id): mo[3].id})
        SaveAnswerService.execute(
            attempt.id, q_written.id, [], student, written_text="Essem. " * 40)

        with no_dispatch(), CaptureQueriesContext(connection) as ctx:
            out = SubmitAttemptService.execute(attempt.id, student)
        # Objective: single 2 + text 5 + matching 4.00 = 11; max 30.
        self.assertEqual(out.grading_status, "pending_grading")
        self.assertEqual(out.objective_score, Decimal("11.00"))
        self.assertEqual(out.writing_score, Decimal("0"))
        # Fully correct: single + text only (partial multiple/gap/matching
        # earn 0 or partial points without counting as correct).
        self.assertEqual(out.correct_answers, 2)
        self.assertLess(len(ctx), 80)

        result = Result.objects.get(attempt=attempt)
        self.assertEqual(result.grading_status, "pending_grading")
        self.assertEqual(result.objective_score, Decimal("11.00"))
        self.assertEqual(result.scoring_version, "default:v1")
        by_code = {s.section_code: s for s in result.section_scores.all()}
        self.assertEqual(by_code["READING"].earned, Decimal("6.00"))  # 2 + 4
        self.assertEqual(by_code["READING"].maximum, Decimal("8"))
        self.assertEqual(by_code["LANGUAGE"].earned, Decimal("5.00"))
        self.assertEqual(by_code["LANGUAGE"].maximum, Decimal("12"))
        self.assertEqual(by_code["WRITING"].maximum, Decimal("10"))
        self.assertEqual(by_code["WRITING"].earned, Decimal("0"))

    def test_profile_weights_configurable_no_official_values(self):
        profile = ExamScoringProfile.objects.create(
            name="custom", version="v9", weights={"READING": 3})
        self.assertEqual(profile.weight_for("READING"), 3.0)
        self.assertEqual(profile.weight_for("UNKNOWN"), 1.0)
        # Default profile carries no official coefficients.
        default, _ = ExamScoringProfile.objects.get_or_create(
            name="default", version="v1")
        self.assertEqual(default.weights, {})


class PanelContentTests(TestCase):
    def setUp(self):
        self.teacher = make_user("pc-t@e.com", "teacher")
        self.admin = make_user("pc-a@e.com", "admin")
        self.test = make_test(self.teacher, title="Panel exam")
        self.client.force_login(self.admin)

    def test_create_gap_question(self):
        resp = self.client.post(
            f"/api/v1/panel/tests/{self.test.id}/questions/",
            {"text": "Bo'shliq", "question_type": "gap_fill", "points": 4,
             "gaps": [{"position": 0, "answers": ["olma", "OLMA"]}]},
            content_type="application/json")
        self.assertEqual(resp.status_code, 201)
        q = Question.objects.get(test=self.test, question_type="gap_fill")
        self.assertEqual(
            sorted(q.gap_blanks.values_list("answer_text", flat=True)),
            ["OLMA", "olma"])

    def test_create_matching_question(self):
        resp = self.client.post(
            f"/api/v1/panel/tests/{self.test.id}/questions/",
            {"text": "Moslik", "question_type": "matching", "points": 6,
             "matching": {
                 "prompts": [{"text": "p1", "position": 0}],
                 "options": [{"text": "o1", "position": 0}, {"text": "o2", "position": 1}],
                 "pairs": [{"prompt_position": 0, "option_position": 1}]}},
            content_type="application/json")
        self.assertEqual(resp.status_code, 201)
        q = Question.objects.get(test=self.test, question_type="matching")
        prompt = MatchingPrompt.objects.get(question=q)
        self.assertEqual(prompt.correct_pair.correct_option.text, "o2")

    def test_create_section_and_passage(self):
        sec = self.client.post(
            f"/api/v1/panel/tests/{self.test.id}/sections/",
            {"name": "O'qish", "code": "READING", "order": 0},
            content_type="application/json")
        self.assertEqual(sec.status_code, 201)
        section_id = sec.json()["id"]
        pas = self.client.post(
            f"/api/v1/panel/tests/{self.test.id}/passages/",
            {"title": "Matn", "content": "Bir bor ekan...", "section": section_id},
            content_type="application/json")
        self.assertEqual(pas.status_code, 201)
