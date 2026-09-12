"""
Bulk Test Import Service — Testlarni CSV fayldan import qilish.

Supports:
    - CSV with columns: question, choice_a, choice_b, choice_c, choice_d, correct, points
    - Auto-create test and questions
    - Multiple question types (single choice)
    - Validation and error reporting
"""
from __future__ import annotations

import csv
import io
import logging
from typing import Any

from django.db import transaction

logger = logging.getLogger(__name__)


class BulkTestImportService:
    """
    CSV fayldan testlarni import qilish xizmati.

    CSV format:
        question,choice_a,choice_b,choice_c,choice_d,correct,points
        "Matematikada 2+2=?",A.3,B.4,C.5,D.6,B,1
        "Poytaxt Toshkentmi?",A.Ha,B.Yo'q,,,A,1
    """

    REQUIRED_COLUMNS = {"question", "choice_a", "choice_b", "correct"}
    OPTIONAL_COLUMNS = {"choice_c", "choice_d", "points", "explanation"}
    VALID_COLUMNS = REQUIRED_COLUMNS | OPTIONAL_COLUMNS

    @classmethod
    def import_test(
        cls,
        csv_content: str | bytes,
        test_title: str,
        course_id: int,
        created_by: Any = None,
        time_limit_minutes: int = 30,
        pass_percentage: float = 60.0,
    ) -> dict[str, Any]:
        """
        CSV dan test import qilish.

        Args:
            csv_content: CSV faylning kontenti.
            test_title: Test nomi.
            course_id: Kurs ID si.
            created_by: Kim tomonidan yaratilgan.
            time_limit_minutes: Vaqt limiti (daqiqa).
            pass_percentage: O'tish foizi.

        Returns:
            {
                "success": bool,
                "test_id": int | None,
                "questions_created": int,
                "errors": list[dict],
            }
        """
        if isinstance(csv_content, bytes):
            csv_content = csv_content.decode("utf-8-sig")

        reader = csv.DictReader(io.StringIO(csv_content))

        # Validate columns
        if not reader.fieldnames:
            return {
                "success": False,
                "test_id": None,
                "questions_created": 0,
                "errors": [{"row": 0, "error": "CSV fayl bo'sh"}],
            }

        missing = cls.REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            return {
                "success": False,
                "test_id": None,
                "questions_created": 0,
                "errors": [{"row": 0, "error": f"Kerakli ustunlar yo'q: {', '.join(missing)}"}],
            }

        questions_data = []
        errors = []

        for i, row in enumerate(reader, start=2):
            try:
                question_text = row.get("question", "").strip()
                choice_a = row.get("choice_a", "").strip()
                choice_b = row.get("choice_b", "").strip()
                choice_c = row.get("choice_c", "").strip()
                choice_d = row.get("choice_d", "").strip()
                correct = row.get("correct", "").strip().upper()
                points = int(row.get("points", 1) or 1)
                explanation = row.get("explanation", "").strip()

                # Validate
                if not question_text:
                    errors.append({"row": i, "error": "Savol matni bo'sh"})
                    continue
                if not choice_a:
                    errors.append({"row": i, "error": "A javobi bo'sh"})
                    continue
                if not choice_b:
                    errors.append({"row": i, "error": "B javobi bo'sh"})
                    continue
                if correct not in ("A", "B", "C", "D"):
                    errors.append({"row": i, "error": f"To'g'ri javob noto'g'ri: {correct}"})
                    continue

                # Build choices
                choices = [
                    {"text": choice_a, "is_correct": correct == "A"},
                    {"text": choice_b, "is_correct": correct == "B"},
                ]
                if choice_c:
                    choices.append({"text": choice_c, "is_correct": correct == "C"})
                if choice_d:
                    choices.append({"text": choice_d, "is_correct": correct == "D"})

                questions_data.append({
                    "text": question_text,
                    "choices": choices,
                    "points": points,
                    "explanation": explanation,
                })

            except Exception as e:
                errors.append({"row": i, "error": str(e)})

        if not questions_data:
            return {
                "success": False,
                "test_id": None,
                "questions_created": 0,
                "errors": errors or [{"row": 0, "error": "Hech qanday savol topilmadi"}],
            }

        # Create test with questions in a transaction
        try:
            from apps.tests.models import Test, Question, Choice
            from apps.courses.models import Course

            with transaction.atomic():
                course = Course.objects.get(id=course_id)
                from apps.accounts.access import is_platform_admin

                is_admin = is_platform_admin(created_by)
                if not is_admin and not (
                    created_by and created_by.is_authenticated and created_by.is_active
                    and created_by.role == "teacher" and course.teacher_id == created_by.pk
                ):
                    raise PermissionError("Bu kursga test import qilishga ruxsat yo'q.")

                test = Test.objects.create(
                    title=test_title,
                    course=course,
                    time_limit_minutes=time_limit_minutes,
                    pass_percentage=pass_percentage,
                    is_active=True,
                )

                for pos, q_data in enumerate(questions_data, start=1):
                    question = Question.objects.create(
                        test=test,
                        text=q_data["text"],
                        question_type=Question.QuestionType.SINGLE_CHOICE,
                        points=q_data["points"],
                        position=pos,
                        explanation=q_data.get("explanation", ""),
                    )

                    for c_data in q_data["choices"]:
                        Choice.objects.create(
                            question=question,
                            text=c_data["text"],
                            is_correct=c_data["is_correct"],
                        )

            logger.info(
                "Bulk test import: test=%d, questions=%d, errors=%d",
                test.id, len(questions_data), len(errors),
            )

            return {
                "success": True,
                "test_id": test.id,
                "questions_created": len(questions_data),
                "errors": errors,
            }

        except Exception as e:
            logger.error("Bulk test import failed: %s", e)
            return {
                "success": False,
                "test_id": None,
                "questions_created": 0,
                "errors": [{"row": 0, "error": f"Test yaratishda xatolik: {str(e)}"}],
            }

    @classmethod
    def validate_csv(cls, csv_content: str | bytes) -> dict[str, Any]:
        """
        CSV faylni tekshirish (import qilmasdan).

        Returns:
            {"valid": bool, "errors": list, "row_count": int, "columns": list}
        """
        if isinstance(csv_content, bytes):
            csv_content = csv_content.decode("utf-8-sig")

        reader = csv.DictReader(io.StringIO(csv_content))

        if not reader.fieldnames:
            return {"valid": False, "errors": ["CSV fayl bo'sh"], "row_count": 0, "columns": []}

        missing = cls.REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            return {
                "valid": False,
                "errors": [f"Kerakli ustunlar yo'q: {', '.join(missing)}"],
                "row_count": 0,
                "columns": list(reader.fieldnames),
            }

        rows = list(reader)
        errors = []
        for i, row in enumerate(rows, start=2):
            if not row.get("question", "").strip():
                errors.append(f"{i}-qator: Savol bo'sh")
            if not row.get("choice_a", "").strip():
                errors.append(f"{i}-qator: A javobi bo'sh")
            if not row.get("choice_b", "").strip():
                errors.append(f"{i}-qator: B javobi bo'sh")
            correct = row.get("correct", "").strip().upper()
            if correct not in ("A", "B", "C", "D"):
                errors.append(f"{i}-qator: To'g'ri javob noto'g'ri ({correct})")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "row_count": len(rows),
            "columns": list(reader.fieldnames),
        }
