"""Record Mock – Test 1 (CD format): answer keys vs the PDF, import
structure, no key leaks to students, gap-fill normalisation, scoring."""

import re
import shutil
import tempfile
from io import StringIO
from pathlib import Path
from unittest import skipUnless

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APITestCase

from apps.tests.management.commands.import_cd_mock import LETTERS, answer_key, load_mock
from apps.tests.models import Choice, GapBlank, Question, Test, TestAttempt
from apps.tests.scoring import answers_match
from apps.tests.services import SaveAnswerService, StartAttemptService

try:
    import pypdf
except ImportError:  # pragma: no cover - dev requirement
    pypdf = None

User = get_user_model()
PDF = Path(settings.BASE_DIR) / "docs" / "mocks" / "record_mock_test1.pdf"


def pdf_answer_key() -> dict[str, dict[int, str]]:
    """Parse the 'TEST 1 – ANSWERS' page: number line followed by answer line."""
    reader = pypdf.PdfReader(str(PDF))
    text = next(p.extract_text() for p in reversed(reader.pages) if "ANSWERS" in (p.extract_text() or ""))
    tokens = [t.strip() for t in text.splitlines() if t.strip()]
    keys: dict[str, dict[int, str]] = {}
    section = None
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("LISTENING", "READING"):
            section = tok
        elif section and tok.isdigit() and i + 1 < len(tokens) and not re.fullmatch(r"\d+|PART \d+", tokens[i + 1]):
            keys.setdefault(section, {})[int(tok)] = tokens[i + 1]
            i += 1
        i += 1
    return keys


def json_key_text(answer) -> str:
    return answer[0] if isinstance(answer, list) else answer


@skipUnless(pypdf and PDF.exists(), "pypdf or the mock PDF is missing")
class PdfKeyTests(SimpleTestCase):
    def test_json_keys_match_pdf_answer_page(self):
        pdf = pdf_answer_key()
        data, _ = load_mock("record_mock_1")
        ours = answer_key(data)
        for section in ("LISTENING", "READING"):
            self.assertEqual(len(pdf[section]), 35, section)
            for number, expected in pdf[section].items():
                with self.subTest(section=section, number=number):
                    self.assertEqual(json_key_text(ours[section][number]).lower(), expected.lower())


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="cd-mock-media-"))
class ImportedMockTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        User.objects.create_superuser(email="mock_admin@example.com", password="x-Pass-123!")
        call_command("import_cd_mock", "record_mock_1", "--publish", stdout=StringIO())
        self.test = Test.objects.get(mock_code="CEFR-RECORD-1-CD")
        self.student = User.objects.create_user(email="mock_student@example.com", password="x-Pass-123!", role="student")

    def questions(self, code: str):
        return Question.objects.filter(test=self.test, section__code=code).order_by("position")

    def test_structure_matches_pdf_layout(self):
        counts = {code: self.questions(code).count() for code in ("LISTENING", "READING", "WRITING", "SPEAKING")}
        self.assertEqual(counts, {"LISTENING": 35, "READING": 35, "WRITING": 3, "SPEAKING": 8})
        minutes = dict(self.test.sections.values_list("code", "duration_minutes"))
        self.assertEqual((minutes["LISTENING"], minutes["READING"], minutes["WRITING"]), (45, 60, 60))
        self.assertEqual(
            list(self.test.sections.get(code="LISTENING").parts.values_list("number", flat=True)),
            ["1", "2", "3", "4", "5", "6"],
        )
        self.assertTrue(self.questions("LISTENING").filter(config__number=19).first().group.image)

    def test_database_keys_match_json(self):
        data, _ = load_mock("record_mock_1")
        keys = answer_key(data)
        for code in ("LISTENING", "READING"):
            for q in self.questions(code):
                expected = keys[code][q.config["number"]]
                with self.subTest(code=code, number=q.config["number"]):
                    if q.question_type == Question.QuestionType.INLINE_GAP_FILL:
                        self.assertEqual(
                            sorted(GapBlank.objects.filter(question=q).values_list("answer_text", flat=True)),
                            sorted(expected),
                        )
                    else:
                        choices = list(Choice.objects.filter(question=q).order_by("position"))
                        correct = [i for i, c in enumerate(choices) if c.is_correct]
                        self.assertEqual(len(correct), 1)
                        got = choices[correct[0]].text if q.question_type == "TRUE_FALSE_NOT_GIVEN" else LETTERS[correct[0]]
                        self.assertEqual(got, expected)

    def test_attempt_api_never_exposes_answer_keys(self):
        attempt = StartAttemptService.execute(test_id=self.test.id, student=self.student, mode="strict")
        self.client.force_authenticate(self.student)
        body = self.client.get(f"/api/tests/attempts/{attempt.id}/").content.decode()
        self.assertNotIn("is_correct", body)
        self.assertNotIn("answer_text", body)
        # Listening gap answers never appear in any text the student receives.
        for word in ("coach", "raincoat", "cookies", "happiness", "feelings"):
            self.assertNotIn(word, body.lower())

    def test_reimport_refuses_to_drop_attempts(self):
        StartAttemptService.execute(test_id=self.test.id, student=self.student, mode="practice")
        with self.assertRaisesMessage(Exception, "urinishlar bor"):
            call_command("import_cd_mock", "record_mock_1", "--replace", stdout=StringIO())

    def _answer_listening(self, attempt, correct: int):
        """Answer `correct` Listening questions right (gap-fills typed in odd case/space)."""
        for q in list(self.questions("LISTENING"))[:correct]:
            if q.question_type == Question.QuestionType.INLINE_GAP_FILL:
                word = GapBlank.objects.filter(question=q).first().answer_text
                SaveAnswerService.execute(attempt_id=attempt.id, question_id=q.id, student=self.student,
                                          text_answer=f"  {word.upper()} ")
            else:
                right = Choice.objects.get(question=q, is_correct=True)
                SaveAnswerService.execute(attempt_id=attempt.id, question_id=q.id, student=self.student,
                                          choice_ids=[right.id])

    def test_scoring_0_15_35_listening(self):
        for correct, score, level in ((0, None, None), (15, 46.6, "B1"), (35, 75.0, "C1")):
            with self.subTest(correct=correct):
                TestAttempt.objects.filter(student=self.student).delete()
                attempt = StartAttemptService.execute(test_id=self.test.id, student=self.student, mode="practice")
                self._answer_listening(attempt, correct)
                self.client.force_authenticate(self.student)
                self.client.post(f"/api/tests/attempts/{attempt.id}/submit/", format="json")
                attempt.refresh_from_db()
                listening = attempt.section_scores["LISTENING"]
                self.assertEqual(listening["score"], score)
                self.assertEqual(listening["level"], level)
                # Speaking is never auto-graded: it stays "missing" in the CBT result.
                self.assertEqual(attempt.section_scores["SPEAKING"]["status"], "missing")
                self.assertIsNone(attempt.band_score)


class GapNormalisationTests(SimpleTestCase):
    def test_case_and_spaces(self):
        self.assertTrue(answers_match("  CoAcH ", "coach"))
        self.assertFalse(answers_match("coaches", "coach"))

    def test_number_words(self):
        self.assertTrue(answers_match("6", "six"))
        self.assertTrue(answers_match("Six", "6"))
        self.assertTrue(answers_match("twenty-one", "21"))
        self.assertTrue(answers_match("twenty one", "21"))
        self.assertFalse(answers_match("7", "six"))


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="cd-mock-preview-"))
class PreviewModeTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.teacher = User.objects.create_superuser(email="preview_admin@example.com", password="x-Pass-123!")
        call_command("import_cd_mock", "record_mock_1", "--publish", stdout=StringIO())
        self.test = Test.objects.get(mock_code="CEFR-RECORD-1-CD")

    def test_staff_attempt_is_preview_and_stays_out_of_stats(self):
        attempt = StartAttemptService.execute(test_id=self.test.id, student=self.teacher, mode="strict")
        self.assertTrue(attempt.is_preview)
        q = Question.objects.filter(test=self.test, section__code="LISTENING").order_by("position").first()
        right = Choice.objects.get(question=q, is_correct=True)
        SaveAnswerService.execute(attempt_id=attempt.id, question_id=q.id, student=self.teacher, choice_ids=[right.id])
        self.client.force_authenticate(self.teacher)
        self.client.post(f"/api/tests/attempts/{attempt.id}/submit/", format="json")

        q.refresh_from_db()
        self.assertEqual(q.total_attempts, 0)  # item statistics untouched
        gradebook = self.client.get(f"/api/tests/{self.test.id}/gradebook/").json()
        self.assertEqual(gradebook.get("ranking", []), [])
        card = self.client.get(f"/api/tests/attempts/{attempt.id}/certificate-card/").json()
        self.assertEqual(card["sections"][0]["status"], "scored")  # preview still sees its own result
