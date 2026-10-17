"""
Tests for Attestatsiya Diagnostika 2026 seeder and model structure.
"""
from __future__ import annotations

from django.core.management import call_command
from apps.tests.models import Choice, ExamSection, Question, ReadingPassage, Test
from tests.conftest import LMSBaseTestCase


class AttestatsiyaSeederTests(LMSBaseTestCase):
    def test_seeder_creates_valid_50_question_attestation_test(self):
        # Run seeder
        call_command("seed_attestatsiya_test_2026", reset=True)

        # 1. Test exists and attributes are correct
        test = Test.objects.filter(mock_code="#MOCK-ATTEST2026").first()
        self.assertIsNotNone(test, "Attestatsiya test must exist with mock_code #MOCK-ATTEST2026")
        self.assertEqual(test.title, "Ona tili va Adabiyot — Rasmiy Attestatsiya Diagnostika 2026")
        self.assertEqual(test.time_limit_minutes, 100)
        self.assertEqual(test.course.category.name, "Attestatsiya")
        self.assertEqual(test.pass_percentage, 60)
        self.assertEqual(test.questions.count(), 50)

        # 2. Section division
        sections = {s.code: s for s in test.sections.all()}
        self.assertIn("MUTAXASSISLIK", sections)
        self.assertIn("KASB_STANDARTI", sections)
        self.assertIn("PEDAGOGIKA", sections)

        self.assertEqual(test.questions.filter(section=sections["MUTAXASSISLIK"]).count(), 35)
        self.assertEqual(test.questions.filter(section=sections["KASB_STANDARTI"]).count(), 5)
        self.assertEqual(test.questions.filter(section=sections["PEDAGOGIKA"]).count(), 10)

        # 3. Reading passages
        p1 = test.passages.filter(order=1).first()
        self.assertIsNotNone(p1)
        self.assertIn("DUNYO TILLARI", p1.content)
        self.assertEqual(p1.questions.count(), 5)

        p2 = test.passages.filter(order=2).first()
        self.assertIsNotNone(p2)
        self.assertIn("Metin", p2.content)
        self.assertEqual(p2.questions.count(), 5)

        # 4. Official answer keys verification
        official_keys = {
            1: 'D', 2: 'D', 3: 'D', 4: 'B', 5: 'A',
            6: 'D', 7: 'A', 8: 'B', 9: 'C', 10: 'C',
            11: 'B', 12: 'D', 13: 'B', 14: 'C', 15: 'D',
            16: 'D', 17: 'D', 18: 'D', 19: 'C', 20: 'D',
            21: 'A', 22: 'D', 23: 'B', 24: 'D', 25: 'C',
            26: 'C', 27: 'C', 28: 'A', 29: 'B', 30: 'A',
            31: 'C', 32: 'B', 33: 'B', 34: 'C', 35: 'B',
            36: 'C', 37: 'B', 38: 'D', 39: 'C', 40: 'A',
            41: 'D', 42: 'D', 43: 'C', 44: 'A', 45: 'B',
            46: 'C', 47: 'B', 48: 'B', 49: 'B', 50: 'A'
        }

        for q in test.questions.order_by("position"):
            self.assertEqual(q.choices.count(), 4, f"Question {q.position} must have 4 choices")
            correct_choices = list(q.choices.filter(is_correct=True))
            self.assertEqual(len(correct_choices), 1, f"Question {q.position} must have exactly 1 correct choice")
            expected_letter = official_keys[q.position]
            self.assertTrue(
                correct_choices[0].text.startswith(f"{expected_letter})"),
                f"Question {q.position} expected key {expected_letter}, got {correct_choices[0].text}"
            )
            self.assertTrue(len(q.explanation) > 10, f"Question {q.position} must have educational explanation")
