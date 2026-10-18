"""Official-rules readiness: placeholder safety, E2E lifecycle, idempotency,
failure paths, leakage audit, scoring consistency, cert safety, TMA/bulk guards.

Proves the engine is safe to receive verified official Milliy Sertifikat
rules/content. No official coefficients are invented anywhere here.
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.certificates.services.generation import (
    certificate_status,
    exam_uses_milliy_rules,
    resolve_profile,
)
from apps.courses.models import Category, Course
from apps.essays.services import ESSAY_RUBRIC_VERSION
from apps.results.models import Certificate, Result
from apps.tests.models import (
    Choice,
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
from apps.tests.services import (
    ExamBridgeService,
    SaveAnswerService,
    StartAttemptService,
    SubmitAttemptService,
)
from apps.tests.bulk_import import BulkTestImportService


def make_user(email, role="student"):
    return User.objects.create_user(
        email=email, password="pass12345", role=role,
        first_name="T", last_name="U")


def make_test(teacher, title="Milliy", **kw):
    category = Category.objects.create(name=f"cat-{title}-{Test.objects.count()}")
    course = Course.objects.create(
        teacher=teacher, category=category, title=title, description="d",
        status=Course.Status.PUBLISHED)
    params = {"title": title, "description": "d", "course": course,
              "status": Test.Status.PUBLISHED,
              "shuffle_questions": False, "shuffle_choices": False}
    params.update(kw)
    return Test.objects.create(**params)


def make_course(teacher, title="Course"):
    category = Category.objects.create(name=f"cat-{title}-{Course.objects.count()}")
    return Course.objects.create(
        teacher=teacher, category=category, title=title, description="d",
        status=Course.Status.PUBLISHED)


def no_dispatch():
    return patch.object(ExamBridgeService, "_dispatch", lambda sub: None)


def build_milliy_exam(teacher, title="Milliy mock"):
    """Reading(3Q+passage) + Language(3Q) + Writing(1Q) mixed exam."""
    test = make_test(teacher, title=title, pass_percentage=50)
    s_read = ExamSection.objects.create(
        test=test, code="READING", name="O'qish", order=0)
    s_lang = ExamSection.objects.create(
        test=test, code="LANGUAGE", name="Til", order=1)
    s_write = ExamSection.objects.create(
        test=test, code="WRITING", name="Yozuv", order=2)
    passage = ReadingPassage.objects.create(
        test=test, section=s_read, title="Matn", content="Bir bor ekan...", order=0)
    q_single = Question.objects.create(
        test=test, section=s_read, reading_passage=passage, text="s?",
        question_type="single", points=2, position=1)
    sc_ok = Choice.objects.create(question=q_single, text="togri", is_correct=True)
    Choice.objects.create(question=q_single, text="xato")
    q_gap = Question.objects.create(
        test=test, section=s_read, reading_passage=passage, text="Bo'sh ___ joy",
        question_type="gap_fill", points=4, position=2)
    GapBlank.objects.create(question=q_gap, position=0, answer_text="kitob")
    GapBlank.objects.create(question=q_gap, position=1, answer_text="daftar")
    q_match = Question.objects.create(
        test=test, section=s_read, reading_passage=passage, text="Mosla",
        question_type="matching", points=6, position=3)
    pr = [MatchingPrompt.objects.create(question=q_match, text=f"p{i}", position=i)
          for i in range(2)]
    op = [MatchingOption.objects.create(question=q_match, text=f"o{i}", position=i)
          for i in range(3)]
    MatchingPair.objects.create(prompt=pr[0], correct_option=op[0])
    MatchingPair.objects.create(prompt=pr[1], correct_option=op[1])
    q_s2 = Question.objects.create(
        test=test, section=s_lang, text="s2?", question_type="single",
        points=2, position=4)
    s2_ok = Choice.objects.create(question=q_s2, text="ok", is_correct=True)
    Choice.objects.create(question=q_s2, text="no")
    q_m = Question.objects.create(
        test=test, section=s_lang, text="m?", question_type="multiple",
        points=3, position=5)
    m_ok = Choice.objects.create(question=q_m, text="a", is_correct=True)
    Choice.objects.create(question=q_m, text="b", is_correct=True)
    q_t = Question.objects.create(
        test=test, section=s_lang, text="t?", question_type="text",
        correct_text="Toshkent", points=5, position=6)
    q_w = Question.objects.create(
        test=test, section=s_write, text="Esse yozing",
        question_type="written", points=10, position=7)
    return {
        "test": test, "sections": (s_read, s_lang, s_write), "passage": passage,
        "q_single": q_single, "sc_ok": sc_ok, "q_gap": q_gap,
        "q_match": q_match, "q_s2": q_s2, "s2_ok": s2_ok,
        "q_m": q_m, "m_ok": m_ok, "q_t": q_t, "q_w": q_w,
    }


class PlaceholderScoringTests(TestCase):
    def setUp(self):
        self.teacher = make_user("ph-t@e.com", "teacher")
        self.student = make_user("ph-s@e.com")

    def _passing_milliy(self, title, gap_mistake=False):
        ex = build_milliy_exam(self.teacher, title=title)
        test = ex["test"]
        attempt = StartAttemptService.execute(test_id=test.id, student=self.student)
        SaveAnswerService.execute(attempt.id, ex["q_single"].id, [ex["sc_ok"].id], self.student)
        gap_resp = {"0": "kitob", "1": "daftar"} if not gap_mistake else {"0": "xato", "1": "daftar"}
        SaveAnswerService.execute(
            attempt.id, ex["q_gap"].id, [], self.student, gap_answers=gap_resp)
        mp = list(MatchingPrompt.objects.filter(question=ex["q_match"]).order_by("position"))
        mo = list(MatchingOption.objects.filter(question=ex["q_match"]).order_by("position"))
        SaveAnswerService.execute(
            attempt.id, ex["q_match"].id, [], self.student,
            matching={str(mp[0].id): mo[0].id, str(mp[1].id): mo[1].id})
        SaveAnswerService.execute(attempt.id, ex["q_s2"].id, [ex["s2_ok"].id], self.student)
        m1 = ex["m_ok"]
        m2 = Choice.objects.filter(question=ex["q_m"], is_correct=True).exclude(pk=m1.pk).first()
        SaveAnswerService.execute(attempt.id, ex["q_m"].id, [m1.id, m2.id], self.student)
        SaveAnswerService.execute(
            attempt.id, ex["q_t"].id, [], self.student, text_answer="toshkent")
        SaveAnswerService.execute(
            attempt.id, ex["q_w"].id, [], self.student, written_text="Essem. " * 40)
        return ex, attempt

    def _grade_written(self, attempt):
        ans = StudentAnswer.objects.get(
            attempt=attempt, question__question_type="written")
        bridge = ExamWrittenBridge.objects.get(answer=ans)
        sub = bridge.essay_submission
        sub.transition_to("graded")
        sub.total_score = Decimal("24")
        sub.save(update_fields=["status", "total_score"])
        return SubmitAttemptService.finalize_pending_grading(attempt.id, self.student)

    def test_unverified_default_issues_no_certificate(self):
        ex, attempt = self._passing_milliy("Unverified exam")
        with no_dispatch():
            SubmitAttemptService.execute(attempt.id, self.student)
        out = self._grade_written(attempt)
        self.assertEqual(out.grading_status, "graded")
        self.assertTrue(out.is_passed)
        result = Result.objects.get(attempt=attempt)
        # Placeholder 60 is inert: graded + passed, but no certificate.
        self.assertEqual(certificate_status(result), "rules_unverified")
        self.assertFalse(Certificate.objects.filter(result=result).exists())

        self.client.force_login(self.student)
        response = self.client.get("/api/results/my-results/")
        self.assertEqual(response.status_code, 200)
        listed = next(row for row in response.json()["results"] if row["id"] == result.id)
        self.assertEqual(listed["certificate_status"], "rules_unverified")
        self.assertEqual(listed["grading_status"], "graded")

    def test_verified_profile_with_threshold_issues_certificate(self):
        ex, attempt = self._passing_milliy("Verified exam")
        profile = ExamScoringProfile.objects.create(
            name="milliy-2026", version="v1", is_verified=True,
            certificate_min_percentage=60)
        ex["test"].scoring_profile = profile
        ex["test"].save(update_fields=["scoring_profile"])
        with no_dispatch():
            SubmitAttemptService.execute(attempt.id, self.student)
        self._grade_written(attempt)
        result = Result.objects.get(attempt=attempt)
        self.assertEqual(result.scoring_version, "milliy-2026:v1")
        self.assertEqual(certificate_status(result), "eligible")
        self.assertTrue(
            Certificate.objects.filter(result=result, status="generated").exists())

    def test_verified_threshold_blocks_below_threshold(self):
        # 28/32 = 87.5% < 90% threshold → graded but not certificate-eligible.
        ex, attempt = self._passing_milliy("Strict exam", gap_mistake=True)
        profile = ExamScoringProfile.objects.create(
            name="milliy-strict", version="v1", is_verified=True,
            certificate_min_percentage=90)
        ex["test"].scoring_profile = profile
        ex["test"].save(update_fields=["scoring_profile"])
        with no_dispatch():
            SubmitAttemptService.execute(attempt.id, self.student)
        self._grade_written(attempt)
        result = Result.objects.get(attempt=attempt)
        self.assertEqual(certificate_status(result), "below_threshold")
        self.assertFalse(Certificate.objects.filter(result=result).exists())

    def test_legacy_tests_unaffected(self):
        test = make_test(self.teacher, title="Legacy", pass_percentage=50)
        q = Question.objects.create(test=test, text="1+1?", position=1)
        c = Choice.objects.create(question=q, text="2", is_correct=True)
        attempt = StartAttemptService.execute(test_id=test.id, student=self.student)
        SaveAnswerService.execute(attempt.id, q.id, [c.id], self.student)
        out = SubmitAttemptService.execute(attempt.id, self.student)
        self.assertTrue(out.is_passed)
        result = Result.objects.get(attempt=attempt)
        # Legacy path: no milliy rules involved, historical behavior intact.
        self.assertFalse(exam_uses_milliy_rules(test))
        self.assertEqual(certificate_status(result), "eligible")
        self.assertTrue(
            Certificate.objects.filter(result=result, status="generated").exists())

        self.client.force_login(self.student)
        response = self.client.get("/api/results/my-results/")
        listed = next(row for row in response.json()["results"] if row["id"] == result.id)
        self.assertEqual(listed["certificate_status"], "eligible")

    def test_profile_change_does_not_rewrite_history(self):
        ex, attempt = self._passing_milliy("History exam")
        profile = ExamScoringProfile.objects.create(
            name="milliy-h", version="v1", is_verified=True,
            certificate_min_percentage=60, weights={"READING": 5})
        ex["test"].scoring_profile = profile
        ex["test"].save(update_fields=["scoring_profile"])
        with no_dispatch():
            SubmitAttemptService.execute(attempt.id, self.student)
        self._grade_written(attempt)
        before = Result.objects.values(
            "score", "percentage", "scoring_version",
        ).get(attempt=attempt)
        profile.weights = {"READING": 1}
        profile.certificate_min_percentage = 10
        profile.save()
        after = Result.objects.values(
            "score", "percentage", "scoring_version",
        ).get(attempt=attempt)
        self.assertEqual(before, after)
        self.assertEqual(after["scoring_version"], "milliy-h:v1")


class RubricVersionTests(TestCase):
    def test_identifier_is_neutral_internal(self):
        self.assertEqual(ESSAY_RUBRIC_VERSION, "grandec-essay-bmb-20p-v1")

    def test_version_persisted_on_bridge_and_result(self):
        teacher = make_user("rv-t@e.com", "teacher")
        student = make_user("rv-s@e.com")
        ex = build_milliy_exam(teacher, title="Rubric exam")
        attempt = StartAttemptService.execute(test_id=ex["test"].id, student=student)
        SaveAnswerService.execute(
            attempt.id, ex["q_w"].id, [], student, written_text="Matn. " * 30)
        with no_dispatch():
            SubmitAttemptService.execute(attempt.id, student)
        ans = StudentAnswer.objects.get(attempt=attempt, question=ex["q_w"])
        bridge = ExamWrittenBridge.objects.get(answer=ans)
        self.assertEqual(bridge.rubric_version, ESSAY_RUBRIC_VERSION)
        result = Result.objects.get(attempt=attempt)
        self.assertEqual(result.rubric_version, ESSAY_RUBRIC_VERSION)


class FullJourneyTests(TestCase):
    """25-step student lifecycle over the API + services."""

    def setUp(self):
        self.teacher = make_user("e2e-t@e.com", "teacher")
        self.student = make_user("e2e-s@e.com")
        self.ex = build_milliy_exam(self.teacher, title="E2E mock")
        self.test = self.ex["test"]
        self.client.force_login(self.student)

    def test_full_journey(self):
        # 1-2. discover + start
        listed = self.client.get("/api/tests/").json()
        self.assertTrue(any(r["id"] == self.test.id for r in listed["results"]))
        started = self.client.post(f"/api/tests/{self.test.id}/start/")
        self.assertEqual(started.status_code, 201)
        attempt_id = started.json()["id"]
        # 3-4. sections/passages/questions, no keys
        body = self.client.get(f"/api/tests/attempts/{attempt_id}/").json()
        self.assertEqual(len(body["sections"]), 3)
        self.assertEqual(len(body["passages"]), 1)
        self.assertEqual(len(body["questions"]), 7)
        blob = str(body)
        for leaked in ("is_correct", "correct_option", "kitob", "daftar"):
            self.assertNotIn(leaked, blob)
        qmap = {q["question_type"]: q for q in body["questions"]}
        # 5-10. save every type
        gap = qmap["gap_fill"]
        match = qmap["matching"]
        prompts = {p["id"]: p for p in match["prompts"]}
        options = match["matching_options"]
        opt_by_text = {o["text"]: o["id"] for o in options}
        # single (reading) + single (language); fixture lists correct first
        singles = [q for q in body["questions"] if q["question_type"] == "single"]
        self.assertEqual(len(singles), 2)
        for sq in singles:
            r = self.client.post(
                f"/api/tests/attempts/{attempt_id}/save-answer/",
                {"question_id": sq["id"], "choice_ids": [sq["choices"][0]["id"]]},
                content_type="application/json")
            self.assertEqual(r.status_code, 200)
        multi = [q for q in body["questions"] if q["question_type"] == "multiple"][0]
        r = self.client.post(
            f"/api/tests/attempts/{attempt_id}/save-answer/",
            {"question_id": multi["id"],
             "choice_ids": [c["id"] for c in multi["choices"][:2]]},
            content_type="application/json")
        self.assertEqual(r.status_code, 200)
        txt = [q for q in body["questions"] if q["question_type"] == "text"][0]
        r = self.client.post(
            f"/api/tests/attempts/{attempt_id}/save-answer/",
            {"question_id": txt["id"], "text_answer": "  TOSHKENT "},
            content_type="application/json")
        self.assertEqual(r.status_code, 200)
        r = self.client.post(
            f"/api/tests/attempts/{attempt_id}/save-answer/",
            {"question_id": gap["id"], "gap_answers": {"0": "kitob", "1": "daftar"}},
            content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(sorted(r.json()["saved_gap_positions"]), [0, 1])
        # matching: correct mapping is p0->o0, p1->o1 per fixture
        pids = sorted(prompts)
        r = self.client.post(
            f"/api/tests/attempts/{attempt_id}/save-answer/",
            {"question_id": match["id"],
             "matching": {str(pids[0]): opt_by_text["o0"],
                          str(pids[1]): opt_by_text["o1"]}},
            content_type="application/json")
        self.assertEqual(r.status_code, 200)
        written = [q for q in body["questions"] if q["question_type"] == "written"][0]
        r = self.client.post(
            f"/api/tests/attempts/{attempt_id}/save-answer/",
            {"question_id": written["id"], "written_text": "Mening essem. " * 30},
            content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertGreater(r.json()["written_word_count"], 0)
        # 11-13. resume: refetch, answers persist, started_at/timers stable
        attempt = TestAttempt.objects.get(id=attempt_id)
        started_at = attempt.started_at
        reloaded = self.client.get(f"/api/tests/attempts/{attempt_id}/").json()
        self.assertEqual(len(reloaded["questions"]), 7)
        reloaded_map = {q["id"]: q for q in reloaded["questions"]}
        self.assertEqual(reloaded_map[gap["id"]]["gap_answers"], {"0": "kitob", "1": "daftar"})
        # DRF trims CharField whitespace at the API boundary (service keeps raw).
        self.assertEqual(
            reloaded_map[written["id"]]["written_text"], ("Mening essem. " * 30).strip())
        attempt.refresh_from_db()
        self.assertEqual(attempt.started_at, started_at)
        # 14-17. submit → objective done, one submission, pending
        with no_dispatch():
            sub = self.client.post(f"/api/tests/attempts/{attempt_id}/submit/")
        self.assertEqual(sub.status_code, 200)
        payload = sub.json()["result"]
        self.assertEqual(payload["grading_status"], "pending_grading")
        self.assertEqual(
            __import__("apps.essays.models", fromlist=["EssaySubmission"])
            .EssaySubmission.objects.filter(
                exam_bridge__attempt_id=attempt_id).count(), 1)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, TestAttempt.Status.PENDING_GRADING)
        # 18. mutation rejected while pending
        r = self.client.post(
            f"/api/tests/attempts/{attempt_id}/save-answer/",
            {"question_id": txt["id"], "text_answer": "o'zgartirish"},
            content_type="application/json")
        self.assertEqual(r.status_code, 400)
        # 19-20. canonical essay grade + finalize
        from apps.essays.models import EssaySubmission as _ES

        ans = StudentAnswer.objects.get(attempt_id=attempt_id, question=ex_written_id(self.ex))
        bridge = ExamWrittenBridge.objects.get(answer=ans)
        submission = bridge.essay_submission
        submission.transition_to(_ES.Status.GRADED)
        submission.total_score = Decimal("24")
        submission.save(update_fields=["status", "total_score"])
        with no_dispatch():
            fin = self.client.post(f"/api/tests/attempts/{attempt_id}/finalize/")
        self.assertEqual(fin.status_code, 200)
        fpayload = fin.json()["result"]
        self.assertEqual(fpayload["grading_status"], "graded")
        # 21-23. result + sections + aggregate persisted
        result = Result.objects.get(attempt_id=attempt_id)
        self.assertEqual(result.grading_status, "graded")
        self.assertEqual(result.section_scores.count(), 3)
        self.assertEqual(
            sum((s.earned for s in result.section_scores.all()), Decimal("0")),
            result.score)
        # 24. result page/API state
        detail = self.client.get(f"/api/results/{result.id}/detail/").json()
        self.assertEqual(detail["grading_status"], "graded")
        self.assertEqual(len(detail["section_scores"]), 3)
        self.assertIn(detail["certificate_status"],
                      ("eligible", "rules_unverified", "below_threshold", "not_passed"))
        # 25. certificate follows verified rules only (default unverified)
        self.assertEqual(detail["certificate_status"], "rules_unverified")


def ex_written_id(ex):
    return ex["q_w"].id


class ResumeSafetyTests(TestCase):
    def test_resume_stability_and_idempotent_autosave(self):
        teacher = make_user("rs-t@e.com", "teacher")
        student = make_user("rs-s@e.com")
        ex = build_milliy_exam(teacher, title="Resume exam")
        attempt = StartAttemptService.execute(test_id=ex["test"].id, student=student)
        started_at = TestAttempt.objects.get(pk=attempt.pk).started_at
        payload_gap = {"0": "kitob", "1": "daftar"}
        mp = list(MatchingPrompt.objects.filter(question=ex["q_match"]).order_by("position"))
        mo = list(MatchingOption.objects.filter(question=ex["q_match"]).order_by("position"))
        payload_match = {str(mp[0].id): mo[0].id, str(mp[1].id): mo[1].id}
        for _ in range(3):  # repeated autosave bursts
            SaveAnswerService.execute(
                attempt.id, ex["q_gap"].id, [], student, gap_answers=dict(payload_gap))
            SaveAnswerService.execute(
                attempt.id, ex["q_match"].id, [], student, matching=dict(payload_match))
            SaveAnswerService.execute(
                attempt.id, ex["q_w"].id, [], student, written_text="Qoralama. " * 10)
        # No duplicate rows anywhere.
        self.assertEqual(
            StudentAnswer.objects.filter(attempt=attempt).count(), 3)
        ans_gap = StudentAnswer.objects.get(attempt=attempt, question=ex["q_gap"])
        self.assertEqual(ans_gap.gap_responses.count(), 2)
        ans_m = StudentAnswer.objects.get(attempt=attempt, question=ex["q_match"])
        self.assertEqual(ans_m.matching_responses.count(), 2)
        # Refetch: everything stable, timers server-side.
        self.client.force_login(student)
        first = self.client.get(f"/api/tests/attempts/{attempt.id}/").json()
        second = self.client.get(f"/api/tests/attempts/{attempt.id}/").json()
        self.assertEqual(first["questions"], second["questions"])
        fmap = {q["id"]: q for q in first["questions"]}
        self.assertEqual(
            fmap[ex["q_gap"].id]["gap_answers"], {"0": "kitob", "1": "daftar"})
        self.assertEqual(
            fmap[ex["q_match"].id]["matching"],
            {str(mp[0].id): mo[0].id, str(mp[1].id): mo[1].id})
        self.assertTrue(fmap[ex["q_w"].id]["written_text"].startswith("Qoralama."))
        self.assertEqual(
            fmap[ex["q_match"].id]["prompts"], second["questions"][2]["prompts"])
        attempt.refresh_from_db()
        self.assertEqual(attempt.started_at, started_at)


class IdempotencyTests(TestCase):
    def test_repeat_everything_single_state(self):
        teacher = make_user("id-t@e.com", "teacher")
        student = make_user("id-s@e.com")
        ex = build_milliy_exam(teacher, title="Idem exam")
        attempt = StartAttemptService.execute(test_id=ex["test"].id, student=student)
        SaveAnswerService.execute(
            attempt.id, ex["q_w"].id, [], student, written_text="Matn. " * 30)
        from apps.essays.models import EssaySubmission as _ES

        with no_dispatch():
            SubmitAttemptService.execute(attempt.id, student)
            with self.assertRaises(ValueError):  # submit twice while pending
                SubmitAttemptService.execute(attempt.id, student)
        ans = StudentAnswer.objects.get(attempt=attempt, question=ex["q_w"])
        bridge = ExamWrittenBridge.objects.get(answer=ans)
        sub = bridge.essay_submission
        sub.transition_to(_ES.Status.GRADED)
        sub.total_score = Decimal("12")
        sub.save(update_fields=["status", "total_score"])
        with no_dispatch():
            first = SubmitAttemptService.finalize_pending_grading(attempt.id, student)
            second = SubmitAttemptService.finalize_pending_grading(attempt.id, student)
        self.assertEqual(first.score, second.score)
        self.assertEqual(Result.objects.filter(attempt=attempt).count(), 1)
        self.assertEqual(_ES.objects.filter(pk=sub.pk).count(), 1)
        self.assertEqual(ExamWrittenBridge.objects.filter(attempt=attempt).count(), 1)
        result = Result.objects.get(attempt=attempt)
        codes = list(result.section_scores.values_list("section_code", flat=True))
        self.assertEqual(len(codes), len(set(codes)))
        self.assertEqual(
            Certificate.objects.filter(result=result).count(), 0)  # unverified default


class FailurePathTests(TestCase):
    def setUp(self):
        self.teacher = make_user("fp-t@e.com", "teacher")
        self.student = make_user("fp-s@e.com")
        self.ex = build_milliy_exam(self.teacher, title="Failure exam")
        self.test = self.ex["test"]

    def test_dispatch_failure_keeps_pending_and_objective_safe(self):
        attempt = StartAttemptService.execute(test_id=self.test.id, student=self.student)
        SaveAnswerService.execute(
            attempt.id, self.ex["q_s2"].id, [self.ex["s2_ok"].id], self.student)
        SaveAnswerService.execute(
            attempt.id, self.ex["q_w"].id, [], self.student, written_text="Matn. " * 30)
        # Realistic provider outage: start_grading raises inside _dispatch,
        # which catches it — the exam must stay pending, objective safe.
        with patch("apps.essays.services.start_grading",
                   side_effect=RuntimeError("provider down")):
            out = SubmitAttemptService.execute(attempt.id, self.student)
        self.assertEqual(out.grading_status, "pending_grading")
        self.assertGreater(out.objective_score, Decimal("0"))
        result = Result.objects.get(attempt=attempt)
        self.assertEqual(result.grading_status, "pending_grading")
        self.assertFalse(Certificate.objects.filter(result=result).exists())
        # Retry remains possible: grade, then finalize succeeds.
        ans = StudentAnswer.objects.get(attempt=attempt, question=self.ex["q_w"])
        bridge = ExamWrittenBridge.objects.get(answer=ans)
        from apps.essays.models import EssaySubmission as _ES

        bridge.essay_submission.transition_to(_ES.Status.GRADED)
        bridge.essay_submission.total_score = Decimal("20")
        bridge.essay_submission.save(update_fields=["status", "total_score"])
        with no_dispatch():
            done = SubmitAttemptService.finalize_pending_grading(attempt.id, self.student)
        self.assertEqual(done.grading_status, "graded")

    def test_repeated_identical_autosave_same_state(self):
        attempt = StartAttemptService.execute(test_id=self.test.id, student=self.student)
        payload = {"0": "kitob", "1": "daftar"}
        for _ in range(4):
            SaveAnswerService.execute(
                attempt.id, self.ex["q_gap"].id, [], self.student,
                gap_answers=dict(payload))
        ans = StudentAnswer.objects.get(attempt=attempt, question=self.ex["q_gap"])
        self.assertEqual(ans.gap_responses.count(), 2)
        self.assertEqual(
            {g.blank_position: g.response_text for g in ans.gap_responses.all()},
            {0: "kitob", 1: "daftar"})

    def test_invalid_matching_rejected_consistently(self):
        attempt = StartAttemptService.execute(test_id=self.test.id, student=self.student)
        self.client.force_login(self.student)
        mp = MatchingPrompt.objects.filter(question=self.ex["q_match"]).first()
        for bad in ({"999999": 1}, {str(mp.id): 999999}, {"abc": 1}):
            resp = self.client.post(
                f"/api/tests/attempts/{attempt.id}/save-answer/",
                {"question_id": self.ex["q_match"].id, "matching": bad},
                content_type="application/json")
            self.assertEqual(resp.status_code, 400)
        self.assertFalse(
            StudentAnswer.objects.filter(attempt=attempt, question=self.ex["q_match"],
                                         matching_responses__isnull=False).exists())

    def test_invalid_gap_positions_ignored(self):
        attempt = StartAttemptService.execute(test_id=self.test.id, student=self.student)
        SaveAnswerService.execute(
            attempt.id, self.ex["q_gap"].id, [], self.student,
            gap_answers={"0": "kitob", "1": "daftar", "7": "zzz", "-1": "qq"})
        ans = StudentAnswer.objects.get(attempt=attempt, question=self.ex["q_gap"])
        # "-1" fails serializer validation at API; service ignores unknown >= 0.
        self.assertFalse(ans.gap_responses.filter(blank_position=7).exists())
        self.assertEqual(ans.gap_responses.count(), 2)

    def test_expired_section_no_mutation(self):
        section = ExamSection.objects.create(
            test=self.test, code="LANG", name="Til", order=9, duration_minutes=1)
        q = Question.objects.create(test=self.test, section=section, text="s?", position=50)
        c = Choice.objects.create(question=q, text="ok", is_correct=True)
        attempt = StartAttemptService.execute(test_id=self.test.id, student=self.student)
        from apps.tests.models import AttemptSectionProgress

        AttemptSectionProgress.objects.filter(
            attempt=attempt, section=section).update(
            started_at=timezone.now() - timedelta(minutes=10))
        with self.assertRaisesMessage(ValueError, "Bo'lim vaqti"):
            SaveAnswerService.execute(attempt.id, q.id, [c.id], self.student)
        self.assertFalse(
            StudentAnswer.objects.filter(attempt=attempt, question=q).exists())

    def test_expired_attempt_no_mutation(self):
        from apps.tests.models import Choice as _C, Question as _Q

        legacy = make_test(self.teacher, title="Timed", time_limit_minutes=1)
        q = _Q.objects.create(test=legacy, text="1+1?", position=1)
        c = _C.objects.create(question=q, text="2", is_correct=True)
        attempt = StartAttemptService.execute(test_id=legacy.id, student=self.student)
        TestAttempt.objects.filter(pk=attempt.pk).update(
            started_at=timezone.now() - timedelta(minutes=10))
        with self.assertRaises(ValueError):
            SaveAnswerService.execute(attempt.id, q.id, [c.id], self.student)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, TestAttempt.Status.TIMEOUT)

    def test_foreign_and_anonymous(self):
        other = make_user("fp-o@e.com")
        attempt = StartAttemptService.execute(test_id=self.test.id, student=self.student)
        self.client.force_login(other)
        for method, url, payload in (
            ("post", f"/api/tests/attempts/{attempt.id}/save-answer/",
             {"question_id": self.ex["q_s2"].id, "choice_ids": [self.ex["s2_ok"].id]}),
            ("post", f"/api/tests/attempts/{attempt.id}/submit/", None),
            ("post", f"/api/tests/attempts/{attempt.id}/finalize/", None),
        ):
            resp = getattr(self.client, method)(
                url, payload or {}, content_type="application/json")
            self.assertIn(resp.status_code, (403, 404))
        self.client.logout()
        resp = self.client.get(f"/api/tests/attempts/{attempt.id}/")
        self.assertIn(resp.status_code, (401, 403, 404))


class LeakageAuditTests(TestCase):
    FORBIDDEN = ("is_correct", "correct_option", "accepted", "correct_text",
                 "fraud_checksum", "raw_result", "rubric")

    def setUp(self):
        self.teacher = make_user("lk-t@e.com", "teacher")
        self.student = make_user("lk-s@e.com")
        self.ex = build_milliy_exam(self.teacher, title="Leak exam")
        self.test = self.ex["test"]
        self.client.force_login(self.student)

    def _scan(self, obj, path="root"):
        """Fail on forbidden keys anywhere nested (values unchecked)."""
        if isinstance(obj, dict):
            for key, value in obj.items():
                lowered = str(key).lower()
                for bad in self.FORBIDDEN:
                    self.assertNotIn(
                        bad, lowered,
                        f"leaked key {key!r} at {path} "
                        "(answer-key material in student payload)")
                self._scan(value, f"{path}.{key}")
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                self._scan(item, f"{path}[{i}]")

    def test_active_exam_payloads_clean(self):
        attempt = StartAttemptService.execute(test_id=self.test.id, student=self.student)
        SaveAnswerService.execute(
            attempt.id, self.ex["q_gap"].id, [], self.student,
            gap_answers={"0": "kitob"})
        for url in (f"/api/tests/{self.test.id}/",
                    f"/api/tests/attempts/{attempt.id}/"):
            payload = self.client.get(url).json()
            self._scan(payload, url)
        # Structure present without keys.
        attempt_body = self.client.get(f"/api/tests/attempts/{attempt.id}/").json()
        by_type = {q["question_type"]: q for q in attempt_body["questions"]}
        self.assertIn("gaps", by_type["gap_fill"])
        self.assertIn("prompts", by_type["matching"])
        self.assertIn("written", by_type["written"])
        self.assertNotIn("accepted", str(by_type))
        self.assertNotIn("correct_option", str(by_type))

    def test_save_responses_clean(self):
        attempt = StartAttemptService.execute(test_id=self.test.id, student=self.student)
        mp = MatchingPrompt.objects.filter(question=self.ex["q_match"]).order_by("position")
        mo = MatchingOption.objects.filter(question=self.ex["q_match"]).order_by("position")
        for payload in (
            {"question_id": self.ex["q_s2"].id, "choice_ids": [self.ex["s2_ok"].id]},
            {"question_id": self.ex["q_t"].id, "text_answer": "x"},
            {"question_id": self.ex["q_gap"].id, "gap_answers": {"0": "x"}},
            {"question_id": self.ex["q_match"].id,
             "matching": {str(mp[0].id): mo[0].id}},
            {"question_id": self.ex["q_w"].id, "written_text": "x" * 50},
        ):
            resp = self.client.post(
                f"/api/tests/attempts/{attempt.id}/save-answer/",
                payload, content_type="application/json")
            self.assertEqual(resp.status_code, 200)
            self._scan(resp.json(), "save-answer")

    def test_result_list_clean(self):
        attempt = StartAttemptService.execute(test_id=self.test.id, student=self.student)
        SubmitAttemptService.execute(attempt.id, self.student)
        payload = self.client.get("/api/results/my-results/").json()
        self._scan(payload, "my-results")


class ScoringConsistencyTests(TestCase):
    def test_layers_agree(self):
        teacher = make_user("sc-t@e.com", "teacher")
        student = make_user("sc-s@e.com")
        ex = build_milliy_exam(teacher, title="Consistency exam")
        profile = ExamScoringProfile.objects.create(
            name="m-cons", version="v1", is_verified=True,
            certificate_min_percentage=50)
        ex["test"].scoring_profile = profile
        ex["test"].save(update_fields=["scoring_profile"])
        attempt = StartAttemptService.execute(test_id=ex["test"].id, student=student)
        SaveAnswerService.execute(attempt.id, ex["q_single"].id, [ex["sc_ok"].id], student)
        SaveAnswerService.execute(
            attempt.id, ex["q_gap"].id, [], student,
            gap_answers={"0": "kitob", "1": "daftar"})
        mp = list(MatchingPrompt.objects.filter(question=ex["q_match"]).order_by("position"))
        mo = list(MatchingOption.objects.filter(question=ex["q_match"]).order_by("position"))
        SaveAnswerService.execute(
            attempt.id, ex["q_match"].id, [], student,
            matching={str(mp[0].id): mo[0].id, str(mp[1].id): mo[1].id})
        SaveAnswerService.execute(attempt.id, ex["q_s2"].id, [ex["s2_ok"].id], student)
        m_ids = list(Choice.objects.filter(question=ex["q_m"], is_correct=True)
                     .values_list("id", flat=True))
        SaveAnswerService.execute(attempt.id, ex["q_m"].id, m_ids, student)
        SaveAnswerService.execute(
            attempt.id, ex["q_t"].id, [], student, text_answer="Toshkent")
        SaveAnswerService.execute(
            attempt.id, ex["q_w"].id, [], student, written_text="Essem. " * 40)
        with no_dispatch():
            SubmitAttemptService.execute(attempt.id, student)
        ans = StudentAnswer.objects.get(attempt=attempt, question=ex["q_w"])
        bridge = ExamWrittenBridge.objects.get(answer=ans)
        sub = bridge.essay_submission
        sub.transition_to("graded")
        sub.total_score = Decimal("12")
        sub.save(update_fields=["status", "total_score"])
        with no_dispatch():
            SubmitAttemptService.finalize_pending_grading(attempt.id, student)
        db_result = Result.objects.get(attempt=attempt)
        section_sum = sum(
            (s.earned for s in db_result.section_scores.all()), Decimal("0"))
        section_max = sum(
            (s.maximum for s in db_result.section_scores.all()), Decimal("0"))
        # DB agreement: sections roll up to the stored totals.
        self.assertEqual(section_sum, db_result.score)
        self.assertEqual(section_max, db_result.max_score)
        self.assertEqual(
            db_result.objective_score + db_result.writing_score, db_result.score)
        # API agreement (what the frontend renders).
        self.client.force_login(student)
        api_result = self.client.get(f"/api/results/{db_result.id}/detail/").json()
        self.assertEqual(Decimal(str(api_result["score"])), db_result.score)
        self.assertEqual(Decimal(str(api_result["percentage"])), db_result.percentage)
        api_sections = sum(Decimal(str(s["earned"])) for s in api_result["section_scores"])
        self.assertEqual(api_sections, db_result.score)
        # Certificate input agreement: canonical PDF uses stored percentage.
        self.assertEqual(api_result["certificate_status"], "eligible")
        cert, generated = __import__(
            "apps.certificates.services.generation", fromlist=["generate_certificate"]
        ).generate_certificate(db_result)
        # Eager finalize dispatch may already have generated it — either way
        # exactly one GENERATED row exists.
        self.assertEqual(cert.status, "generated")
        self.assertEqual(
            Certificate.objects.filter(result=db_result, status="generated").count(), 1)


class WritingScaleTests(TestCase):
    def test_boundaries(self):
        from apps.tests.scoring import written_earned

        self.assertIsNone(written_earned(10, None))
        self.assertEqual(written_earned(10, Decimal("0"), 24), Decimal("0.00"))
        self.assertEqual(written_earned(10, Decimal("24"), 24), Decimal("10.00"))
        self.assertEqual(written_earned(10, Decimal("12"), 24), Decimal("5.00"))
        # Decimal precision: 10 * 1/24 rounds half-even to 0.42.
        self.assertEqual(written_earned(10, Decimal("1"), 24), Decimal("0.42"))

    def test_invalid_clamped(self):
        from apps.tests.scoring import written_earned

        self.assertEqual(written_earned(10, Decimal("-5"), 24), Decimal("0.00"))
        self.assertEqual(written_earned(10, Decimal("99"), 24), Decimal("10.00"))
        self.assertIsNone(written_earned(10, "not-a-number", 24))


class ResultStateTests(TestCase):
    def test_certificate_status_matrix(self):
        teacher = make_user("rs2-t@e.com", "teacher")
        student = make_user("rs2-s@e.com")
        # Legacy fail → not_passed.
        legacy = make_test(teacher, title="Legacy fail", pass_percentage=100)
        q = Question.objects.create(test=legacy, text="1+1?", position=1)
        Choice.objects.create(question=q, text="2", is_correct=True)
        Choice.objects.create(question=q, text="3")
        attempt = StartAttemptService.execute(test_id=legacy.id, student=student)
        SubmitAttemptService.execute(attempt.id, student)
        self.assertEqual(
            certificate_status(Result.objects.get(attempt=attempt)), "not_passed")
        # Milliy pending → pending_writing.
        ex = build_milliy_exam(teacher, title="State exam")
        attempt2 = StartAttemptService.execute(test_id=ex["test"].id, student=student)
        SaveAnswerService.execute(
            attempt2.id, ex["q_w"].id, [], student, written_text="Matn. " * 30)
        with no_dispatch():
            SubmitAttemptService.execute(attempt2.id, student)
        pending_result = Result.objects.get(attempt=attempt2)
        self.assertEqual(certificate_status(pending_result), "pending_writing")


class CertificateSafetyTests(TestCase):
    def test_no_cert_when_pending(self):
        teacher = make_user("cs-t@e.com", "teacher")
        student = make_user("cs-s@e.com")
        ex = build_milliy_exam(teacher, title="Pending cert exam")
        attempt = StartAttemptService.execute(test_id=ex["test"].id, student=student)
        SaveAnswerService.execute(
            attempt.id, ex["q_w"].id, [], student, written_text="Matn. " * 30)
        with no_dispatch():
            SubmitAttemptService.execute(attempt.id, student)
        result = Result.objects.get(attempt=attempt)
        from apps.certificates.services.generation import generate_certificate

        cert, generated = generate_certificate(result)
        self.assertFalse(generated)
        self.assertIsNone(cert)
        self.assertFalse(Certificate.objects.filter(result=result).exists())

    def test_no_cert_when_unverified_even_if_passed(self):
        teacher = make_user("cs2-t@e.com", "teacher")
        student = make_user("cs2-s@e.com")
        ex = build_milliy_exam(teacher, title="Unverified cert exam")
        test = ex["test"]
        attempt = StartAttemptService.execute(test_id=test.id, student=student)
        SaveAnswerService.execute(attempt.id, ex["q_single"].id, [ex["sc_ok"].id], student)
        SaveAnswerService.execute(
            attempt.id, ex["q_gap"].id, [], student,
            gap_answers={"0": "kitob", "1": "daftar"})
        mp = list(MatchingPrompt.objects.filter(question=ex["q_match"]).order_by("position"))
        mo = list(MatchingOption.objects.filter(question=ex["q_match"]).order_by("position"))
        SaveAnswerService.execute(
            attempt.id, ex["q_match"].id, [], student,
            matching={str(mp[0].id): mo[0].id, str(mp[1].id): mo[1].id})
        SaveAnswerService.execute(attempt.id, ex["q_s2"].id, [ex["s2_ok"].id], student)
        m_ids = list(Choice.objects.filter(question=ex["q_m"], is_correct=True)
                     .values_list("id", flat=True))
        SaveAnswerService.execute(attempt.id, ex["q_m"].id, m_ids, student)
        SaveAnswerService.execute(
            attempt.id, ex["q_t"].id, [], student, text_answer="Toshkent")
        with no_dispatch():
            out = SubmitAttemptService.execute(attempt.id, student)
        # Fully objective 32/32 → graded + passed, still no certificate.
        self.assertEqual(out.grading_status, "graded")
        self.assertTrue(out.is_passed)
        result = Result.objects.get(attempt=attempt)
        self.assertEqual(certificate_status(result), "rules_unverified")
        from apps.certificates.services.generation import generate_certificate

        cert, generated = generate_certificate(result)
        self.assertFalse(generated)
        self.assertFalse(Certificate.objects.filter(result=result).exists())

    def test_generation_idempotent_hmac_intact(self):
        teacher = make_user("cs3-t@e.com", "teacher")
        student = make_user("cs3-s@e.com")
        test = make_test(teacher, title="Idem cert", pass_percentage=0)
        q = Question.objects.create(test=test, text="1+1?", position=1)
        c = Choice.objects.create(question=q, text="2", is_correct=True)
        attempt = StartAttemptService.execute(test_id=test.id, student=student)
        SaveAnswerService.execute(attempt.id, q.id, [c.id], student)
        SubmitAttemptService.execute(attempt.id, student)
        result = Result.objects.get(attempt=attempt)
        from apps.certificates.services.generation import generate_certificate

        cert1, gen1 = generate_certificate(result)
        cert2, gen2 = generate_certificate(result)
        # Eager dispatch during submit may already have generated it —
        # either way exactly one GENERATED row exists and HMAC verifies.
        self.assertFalse(gen2)
        self.assertEqual(cert1.pk, cert2.pk)
        self.assertEqual(Certificate.objects.filter(result=result).count(), 1)
        cert1.refresh_from_db()
        self.assertTrue(cert1.fraud_checksum)
        from apps.certificates.services.anti_fraud import AntiFraudService

        self.assertEqual(
            AntiFraudService.generate_checksum(cert1), cert1.fraud_checksum)


class PanelAdminScopeTests(TestCase):
    def setUp(self):
        self.teacher = make_user("pa-t@e.com", "teacher")
        self.admin = make_user("pa-a@e.com", "admin")
        self.test = make_test(self.teacher, title="Scope exam")

    def test_teacher_forbidden_admin_allowed(self):
        self.client.force_login(self.teacher)
        for url, payload in (
            (f"/api/v1/panel/tests/{self.test.id}/sections/",
             {"name": "X", "code": "READING"}),
            (f"/api/v1/panel/tests/{self.test.id}/passages/",
             {"title": "T", "content": "matn"}),
            (f"/api/v1/panel/tests/{self.test.id}/questions/",
             {"text": "Q", "question_type": "gap_fill", "points": 1,
              "gaps": [{"position": 0, "answers": ["a"]}]}),
        ):
            resp = self.client.post(url, payload, content_type="application/json")
            self.assertEqual(resp.status_code, 403)
        self.client.force_login(self.admin)
        resp = self.client.post(
            f"/api/v1/panel/tests/{self.test.id}/sections/",
            {"name": "O'qish", "code": "READING", "order": 0},
            content_type="application/json")
        self.assertEqual(resp.status_code, 201)

    def test_profile_admin_surface(self):
        from django.contrib import admin as _admin

        from apps.tests.models import ExamScoringProfile

        model_admin = _admin.site._registry[ExamScoringProfile]
        self.assertIn("is_verified", model_admin.list_display)
        self.assertIn("is_verified", model_admin.list_filter)


class BulkImportGuardTests(TestCase):
    def test_unknown_columns_rejected(self):
        teacher = make_user("bi-t@e.com", "teacher")
        course = make_course(teacher, title="BI course")
        csv_text = "question,choice_a,choice_b,correct,type\n1+1?,2,3,A,gap_fill\n"
        result = BulkTestImportService.import_test(
            csv_text, "BI test", course.id, created_by=teacher)
        self.assertFalse(result["success"])
        self.assertIsNone(result["test_id"])
        self.assertTrue(any("gap_fill" in e["error"] or "ustun" in e["error"]
                            for e in result["errors"]))
        self.assertFalse(Test.objects.filter(title="BI test").exists())

    def test_single_choice_still_imports(self):
        teacher = make_user("bi2-t@e.com", "teacher")
        teacher.can_create_test = True
        teacher.save(update_fields=["can_create_test"])
        course = make_course(teacher, title="BI course 2")
        csv_text = "question,choice_a,choice_b,correct\n1+1?,2,3,A\n"
        result = BulkTestImportService.import_test(
            csv_text, "BI ok", course.id, created_by=teacher)
        self.assertTrue(result["success"], result["errors"])
        self.assertEqual(
            Question.objects.get(test_id=result["test_id"]).question_type, "single")


class TMASafetyTests(TestCase):
    def _header(self, user):
        token = str(RefreshToken.for_user(user).access_token)
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_start_rejected_no_attempt_created(self):
        teacher = make_user("tma-t@e.com", "teacher")
        student = make_user("tma-s@e.com")
        ex = build_milliy_exam(teacher, title="TMA milliy")
        header = self._header(student)
        resp = self.client.post(
            f"/tma/api/tests/{ex['test'].id}/start/", data="{}",
            content_type="application/json", **header)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json().get("code"), "unsupported_question_type")
        self.assertFalse(
            TestAttempt.objects.filter(test=ex["test"], student=student).exists())

    def test_answer_and_submit_rejected(self):
        teacher = make_user("tma2-t@e.com", "teacher")
        student = make_user("tma2-s@e.com")
        ex = build_milliy_exam(teacher, title="TMA milliy 2")
        attempt = StartAttemptService.execute(test_id=ex["test"].id, student=student)
        header = self._header(student)
        resp = self.client.post(
            f"/tma/api/tests/{ex['test'].id}/answer/",
            data=('{"attempt_id":%d,"question_id":%d,"choice_ids":[]}'
                  % (attempt.id, ex["q_gap"].id)),
            content_type="application/json", **header)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json().get("code"), "unsupported_question_type")
        resp = self.client.post(
            f"/tma/api/tests/{ex['test'].id}/submit/",
            data=('{"attempt_id":%d,"answers":{}}' % attempt.id),
            content_type="application/json", **header)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json().get("code"), "unsupported_question_type")
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, TestAttempt.Status.IN_PROGRESS)
