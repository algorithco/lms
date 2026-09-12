"""
Tests services — core business logic for test-taking lifecycle.

OPTIMIZATIONS (Phase 7):
    1. Proper logging throughout (logger.error, logger.warning, logger.info).
    2. Double-submit protection: SubmitAttemptService uses select_for_update()
       to prevent race conditions from concurrent submit requests.
    3. Timeout check uses DB-level comparison to avoid clock skew.
    4. All queries use select_related/prefetch_related where possible.
    5. Consistent error messages with structured logging.

Single Responsibility: each method handles ONE business operation.

Lifecycle:
    1. StartAttemptService   — create attempt, enforce max_attempts
    2. SaveAnswerService     — auto-save individual answers (M2M choices)
    3. SubmitAttemptService  — grade answers, compute score, create Result
    4. TimerService          — timeout enforcement (called by Celery beat or submit)
"""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.results.models import Result
from apps.tests.models import (
    Choice,
    Question,
    StudentAnswer,
    Test,
    TestAttempt,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes for structured return values
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AttemptResult:
    """Immutable data object returned after attempt submission."""

    attempt_id: int
    total_questions: int
    correct_answers: int
    wrong_answers: int
    unanswered: int
    score: Decimal
    max_score: Decimal
    percentage: Decimal
    is_passed: bool
    time_taken_seconds: int


@dataclass(frozen=True)
class QuestionResult:
    """Per-question grading result."""

    question_id: int
    is_correct: bool
    earned_points: Decimal
    max_points: Decimal
    correct_choice_ids: list[int]
    selected_choice_ids: list[int]


# ---------------------------------------------------------------------------
# 1. StartAttemptService
# ---------------------------------------------------------------------------

class StartAttemptService:
    """
    Testni boshlash — yangi TestAttempt yaratish.

    Business rules:
        - Test faol (is_active) bo'lishi kerak.
        - Student roli bo'lishi kerak.
        - Agar max_attempts > 0 bo'lsa, necha marta urinishganini tekshirish.
        - Agar allaqachon IN_PROGRESS attempt bo'lsa, yangisini yaratmaslik.
        - shuffle_questions=True bo'lsa, savollar tartibini aralashtirish.
    """

    @staticmethod
    @transaction.atomic
    def execute(test_id: int, student: Any) -> TestAttempt:
        """Yangi attempt yaratish."""
        # -- Test mavjudligini tekshirish ---------------------------------
        try:
            test = Test.objects.get(id=test_id, is_active=True)
        except Test.DoesNotExist:
            logger.warning("Start attempt failed: test=%d not found or inactive", test_id)
            raise ValueError("Test topilmadi yoki faol emas.")

        # -- Role tekshirish -----------------------------------------------
        if student.role != "student":
            logger.warning(
                "Start attempt denied: user=%d role=%s (not student)",
                student.id, student.role,
            )
            raise ValueError("Faqat o'quvchilar test topshira oladi.")

        # -- Aktiv attempt mavjudmi? --------------------------------------
        active_attempt = TestAttempt.objects.filter(
            test=test,
            student=student,
            status=TestAttempt.Status.IN_PROGRESS,
        ).first()

        if active_attempt:
            logger.info(
                "Active attempt already exists: attempt=%d, student=%d",
                active_attempt.id, student.id,
            )
            raise ValueError(
                "Sizda allaqachon davom etayotgan attempt bor. "
                "Avval uni tugating yoki timeout bo'lishini kuting."
            )

        # -- Max attempts tekshirish ---------------------------------------
        if test.max_attempts > 0:
            completed_count = TestAttempt.objects.filter(
                test=test,
                student=student,
                status__in=[
                    TestAttempt.Status.COMPLETED,
                    TestAttempt.Status.TIMEOUT,
                ],
            ).count()

            if completed_count >= test.max_attempts:
                logger.warning(
                    "Max attempts exceeded: test=%d, student=%d, count=%d/%d",
                    test.id, student.id, completed_count, test.max_attempts,
                )
                raise ValueError(
                    f"Test uchun maksimal urinishlar soni ({test.max_attempts}) "
                    f"tugadi. Siz {completed_count} marta topshirdingiz."
                )

        # -- Attempt yaratish ----------------------------------------------
        attempt = TestAttempt.objects.create(
            test=test,
            student=student,
            status=TestAttempt.Status.IN_PROGRESS,
        )

        logger.info(
            "Attempt started: id=%d, test=%d, student=%d",
            attempt.id, test.id, student.id,
        )
        return attempt


# ---------------------------------------------------------------------------
# 2. SaveAnswerService
# ---------------------------------------------------------------------------

class SaveAnswerService:
    """
    Javobni auto-save qilish (har bir javob yozilganda).

    Business rules:
        - Attempt IN_PROGRESS holatda bo'lishi kerak.
        - Vaqt tugamagan bo'lishi kerak.
        - Savol shu testga tegishli bo'lishi kerak.
        - Single choice: bitta variant tanlash shart.
        - Multiple choice: kamida bitta variant tanlash kerak.
        - Oldingi javob bo'lsa, yangilash (upsert).
    """

    _CLEARED = object()

    @staticmethod
    def execute(
        attempt_id: int,
        question_id: int,
        choice_ids: list[int],
        student: Any,
        text_answer: str = "",
        allow_clear: bool = False,
    ) -> StudentAnswer | None:
        """Save an answer and report timeout only after finalization commits."""
        answer = SaveAnswerService._execute_atomic(
            attempt_id=attempt_id,
            question_id=question_id,
            choice_ids=choice_ids,
            student=student,
            text_answer=text_answer,
            allow_clear=allow_clear,
        )
        if answer is SaveAnswerService._CLEARED:
            return None
        if answer is None:
            raise ValueError("Vaqt tugadi! Test avtomatik yakunlandi.")
        return answer

    @staticmethod
    @transaction.atomic
    def _execute_atomic(
        attempt_id: int,
        question_id: int,
        choice_ids: list[int],
        student: Any,
        text_answer: str = "",
        allow_clear: bool = False,
    ) -> StudentAnswer | object | None:
        """Javobni saqlash yoki yangilash."""
        # -- Attempt ni olish va tekshirish --------------------------------
        try:
            attempt = TestAttempt.objects.select_related("test").select_for_update().get(
                id=attempt_id,
                student=student,
            )
        except TestAttempt.DoesNotExist:
            logger.warning(
                "Save answer failed: attempt=%d not found for user=%d",
                attempt_id, student.id,
            )
            raise ValueError("Attempt topilmadi.")

        # -- Status tekshirish ---------------------------------------------
        if attempt.status != TestAttempt.Status.IN_PROGRESS:
            logger.warning(
                "Save answer blocked: attempt=%d status=%s",
                attempt.id, attempt.status,
            )
            raise ValueError(
                "Bu attempt allaqachon yakunlangan. "
                "Javob o'zgartirib bo'lmaydi."
            )

        # -- Timer tekshirish ----------------------------------------------
        if attempt.is_time_expired:
            # Timeout — avtomatik yakunlash
            logger.info("Timeout during save-answer: attempt=%d", attempt.id)
            SubmitAttemptService._timeout_attempt(attempt)
            return None

        # -- Savol tekshirish ----------------------------------------------
        try:
            question = Question.objects.get(
                id=question_id,
                test=attempt.test,
            )
        except Question.DoesNotExist:
            logger.warning(
                "Save answer failed: question=%d not in test=%d",
                question_id, attempt.test.id,
            )
            raise ValueError("Savol topilmadi yoki bu testga tegishli emas.")

        if allow_clear and not choice_ids and not text_answer.strip():
            StudentAnswer.objects.filter(attempt=attempt, question=question).delete()
            return SaveAnswerService._CLEARED

        # -- Matnli javob savollari (TEXT_MATCH) ---------------------------
        if question.question_type == Question.QuestionType.TEXT_MATCH:
            student_answer, created = StudentAnswer.objects.update_or_create(
                attempt=attempt,
                question=question,
                defaults={"text_answer": text_answer.strip()},
            )
            if not created and student_answer.text_answer != text_answer.strip():
                student_answer.text_answer = text_answer.strip()
                student_answer.save(update_fields=["text_answer"])
            student_answer.selected_choices.clear()
            return student_answer

        # -- Choice larni tekshirish ---------------------------------------
        valid_choices = Choice.objects.filter(
            question=question,
            id__in=choice_ids,
        )
        if valid_choices.count() != len(choice_ids):
            raise ValueError("Noto'g'ri variantlar tanlandi.")

        # -- Single choice tekshirish --------------------------------------
        if question.question_type == Question.QuestionType.SINGLE_CHOICE:
            if len(choice_ids) != 1:
                raise ValueError(
                    "Bitta to'g'ri javobli savolda faqat bitta variant "
                    "tanlash kerak."
                )

        # -- Multiple choice tekshirish -------------------------------------
        if question.question_type == Question.QuestionType.MULTIPLE_CHOICE:
            if len(choice_ids) < 1:
                raise ValueError(
                    "Ko'p to'g'ri javobli savolda kamida bitta variant "
                    "tanlash kerak."
                )

        # -- Javobni saqlash (upsert) --------------------------------------
        student_answer, created = StudentAnswer.objects.update_or_create(
            attempt=attempt,
            question=question,
            defaults={"text_answer": ""},
        )
        if not created and student_answer.text_answer:
            student_answer.text_answer = ""
            student_answer.save(update_fields=["text_answer"])

        # M2M ni tozalab qayta o'rnatish
        student_answer.selected_choices.set(valid_choices)

        action = "created" if created else "updated"
        logger.debug(
            "Answer %s: attempt=%d, question=%d, choices=%s",
            action, attempt.id, question.id, choice_ids,
        )

        return student_answer


# ---------------------------------------------------------------------------
# Sync certificate generation (fallback when Celery is not running)
# ---------------------------------------------------------------------------

def _generate_certificate_sync(result) -> None:
    """
    Sertifikat generatsiya qilish — Celery'siz, to'g'ridan-to'g'ri.

    Agar o'tgan bo'lsa → PDF yaratiladi va saqlanadi.
    Xatolik bo'lsa → log yoziladi, lekin test natijasi buzilmaydi.
    """
    from apps.results.models import Certificate
    from apps.results.services.pdf_service import generate_certificate_pdf
    from django.conf import settings
    from django.core.files.base import ContentFile

    if not result.is_passed:
        return

    try:
        cert, created = Certificate.objects.get_or_create(
            result=result,
            defaults={
                "student": result.student,
                "test": result.test,
                "course": result.course,
            },
        )

        if cert.status == Certificate.Status.GENERATED and cert.file:
            logger.info("Certificate already generated: %s", cert.certificate_number)
            return

        base_url = getattr(settings, "SITE_URL", "http://localhost:8000")
        verify_url = f"{base_url}/certificates/verify/{cert.certificate_number}/"

        pdf_bytes = generate_certificate_pdf(
            certificate_number=cert.certificate_number,
            student_full_name=result.student.get_full_name(),
            course_title=result.course.title,
            test_title=result.test.title,
            percentage=float(result.percentage),
            issued_at=cert.issued_at,
            verify_url=verify_url,
        )

        filename = f"{cert.certificate_number}.pdf"
        cert.file.save(filename, ContentFile(pdf_bytes), save=False)
        cert.status = Certificate.Status.GENERATED
        cert.save(update_fields=["file", "status"])
        from apps.certificates.services.anti_fraud import generate_and_store_checksum
        generate_and_store_checksum(cert)

        logger.info(
            "Certificate generated (sync): %s, size=%d bytes",
            cert.certificate_number, cert.file.size if cert.file else 0,
        )

    except Exception as e:
        logger.error("Sync certificate generation failed: %s", e, exc_info=True)


# ---------------------------------------------------------------------------
# 3. SubmitAttemptService
# ---------------------------------------------------------------------------

class SubmitAttemptService:
    """
    Testni yakunlash va natijani hisoblash.

    DOUBLE-SUBMIT PROTECTION:
        Uses select_for_update() to lock the attempt row, preventing
        race conditions when multiple submit requests arrive simultaneously.

    Business rules:
        - Attempt IN_PROGRESS bo'lishi kerak.
        - Barcha javoblar tekshiriladi (single + multiple).
        - Multiple choice: FAQAT barcha to'g'ri variantlar tanlangan
          bo'lsa 100% ball beriladi. Qisman tanlangan = 0 ball.
        - Natija Result modeliga denormalized saqlanadi.
        - Certificate avtomatik generatsiya qilinadi (agar o'tgan bo'lsa).
    """

    @staticmethod
    @transaction.atomic
    def execute(attempt_id: int, student: Any) -> AttemptResult:
        """Testni yakunlash va natijani hisoblash."""
        # -- Attempt ni olish (SELECT FOR UPDATE — double-submit lock) -----
        try:
            attempt = (
                TestAttempt.objects.select_related(
                    "test", "test__course",
                )
                .prefetch_related(
                    "answers", "answers__question", "answers__selected_choices",
                )
                .select_for_update()
                .get(id=attempt_id, student=student)
            )
        except TestAttempt.DoesNotExist:
            logger.warning(
                "Submit failed: attempt=%d not found for user=%d",
                attempt_id, student.id,
            )
            raise ValueError("Attempt topilmadi.")

        # -- Status tekshirish (prevents double-submit) --------------------
        if attempt.status != TestAttempt.Status.IN_PROGRESS:
            logger.info(
                "Submit blocked (already done): attempt=%d status=%s",
                attempt.id, attempt.status,
            )
            raise ValueError("Bu attempt allaqachon yakunlangan.")

        # -- Vaqt tekshirish -----------------------------------------------
        if attempt.is_time_expired:
            logger.info("Timeout on submit: attempt=%d", attempt.id)
            return SubmitAttemptService._timeout_attempt(attempt)

        return SubmitAttemptService._grade_attempt(attempt)

    @staticmethod
    @transaction.atomic
    def _timeout_attempt(attempt: TestAttempt) -> AttemptResult:
        """
        Timeout — avtomatik yakunlash.

        Vaqt tugaganda ishlaydi: status TIMEOUT qilinadi,
        lekin javoblar hali hisoblanadi (qisman topshirilgan bo'lsa).
        """
        # Use F() to avoid race condition on status update
        updated = TestAttempt.objects.filter(
            id=attempt.id,
            status=TestAttempt.Status.IN_PROGRESS,
        ).update(
            status=TestAttempt.Status.TIMEOUT,
            completed_at=timezone.now(),
        )

        if updated == 0:
            # Already completed/timed out by another request
            attempt.refresh_from_db()
            existing = Result.objects.filter(attempt=attempt).first()
            if existing:
                return SubmitAttemptService._build_result_from_attempt(attempt)

        attempt.refresh_from_db()
        logger.info("Attempt timed out: id=%d", attempt.id)

        return SubmitAttemptService._grade_attempt(attempt, is_timeout=True)

    @staticmethod
    def _grade_attempt(
        attempt: TestAttempt,
        is_timeout: bool = False,
    ) -> AttemptResult:
        """
        Javoblarni tekshirish va ball hisoblash.

        Grading algorithm:
            1. Savolning to'g'ri Choice larini aniqlash.
            2. Student tanlagan Choice lar bilan solishtirish.
            3. Single choice: to'g'ri bo'lsa -> savol points, noto'g'ri -> 0.
            4. Multiple choice: BARCHA to'g'ri tanlangan bo'lsa -> savol points,
               aks holda -> 0 (qisman javob ball olmaydi).
            5. Foiz = (score / max_score) * 100.
            6. is_passed = (foiz >= pass_percentage).
        """
        test = attempt.test
        now = timezone.now()

        # -- Vaqt hisoblash ------------------------------------------------
        time_taken = 0
        if attempt.started_at:
            delta = now - attempt.started_at
            time_taken = int(delta.total_seconds())

        # -- Barcha savollarni olish (prefetch eliminates N+1) -------------
        all_questions = list(
            test.questions.prefetch_related("choices").order_by("position")
        )

        total_questions = len(all_questions)
        correct_count = 0
        wrong_count = 0
        unanswered_count = 0
        total_score = Decimal("0")
        max_score = Decimal("0")

        # -- Har bir savolni tekshirish ------------------------------------
        for question in all_questions:
            max_score += Decimal(str(question.points))

            # Student javobini topish
            try:
                student_answer = attempt.answers.get(question=question)
            except StudentAnswer.DoesNotExist:
                # Javob berilmagan
                unanswered_count += 1
                continue

            # To'g'ri choice ID larini olish
            correct_choice_ids = set(
                question.choices.filter(is_correct=True).values_list(
                    "id", flat=True
                )
            )

            # Student tanlangan choice ID larini olish
            selected_choice_ids = set(
                student_answer.selected_choices.values_list("id", flat=True)
            )

            # -- Grading logic ----------------------------------------------
            if question.question_type == Question.QuestionType.TEXT_MATCH:
                # Matnli javob: normalize (kichik harf, bo'shliqlar) va taqqoslash
                student_text = (student_answer.text_answer or "").strip().lower()
                correct_text = (question.correct_text or "").strip().lower()
                is_correct = bool(student_text and correct_text and student_text == correct_text)
            elif not selected_choice_ids:
                # Hech narsa tanlanmagan
                wrong_count += 1
                student_answer.is_correct = False
                student_answer.save(update_fields=["is_correct"])
                continue
            elif question.question_type == Question.QuestionType.SINGLE_CHOICE:
                is_correct = correct_choice_ids == selected_choice_ids
            else:
                # Multiple choice: BARCHA to'g'ri tanlangan bo'lishi kerak
                is_correct = (
                    correct_choice_ids == selected_choice_ids
                    and len(selected_choice_ids) > 0
                )

            # -- Ball hisoblash ---------------------------------------------
            if is_correct:
                correct_count += 1
                total_score += Decimal(str(question.points))
            else:
                wrong_count += 1

            student_answer.is_correct = is_correct
            student_answer.save(update_fields=["is_correct"])

        # -- Foiz hisoblash -------------------------------------------------
        if max_score > 0:
            percentage = (total_score / max_score) * Decimal("100")
        else:
            percentage = Decimal("0")

        is_passed = percentage >= Decimal(str(test.pass_percentage))

        # -- Attempt ni yangilash -------------------------------------------
        TestAttempt.objects.filter(id=attempt.id).update(
            status=(
                TestAttempt.Status.TIMEOUT
                if is_timeout
                else TestAttempt.Status.COMPLETED
            ),
            completed_at=now,
            score=total_score,
            percentage=percentage,
            is_passed=is_passed,
        )

        # -- Result modeliga saqlash (denormalized) -------------------------
        result = Result.objects.create(
            attempt=attempt,
            student=attempt.student,
            test=test,
            course=test.course,
            total_questions=total_questions,
            correct_answers=correct_count,
            wrong_answers=wrong_count,
            unanswered=unanswered_count,
            score=total_score,
            max_score=max_score,
            percentage=percentage,
            is_passed=is_passed,
            time_taken_seconds=time_taken,
        )

        logger.info(
            "Attempt graded: id=%d, score=%s/%s, pct=%s%%, passed=%s",
            attempt.id, total_score, max_score, percentage, is_passed,
        )

        # -- Async tasks: PDF + Telegram notification ----------------------
        def dispatch_result_task() -> None:
            try:
                from apps.notifications.tasks import process_test_result_task
                process_test_result_task.delay(result_id=result.id)
            except Exception:
                logger.warning(
                    "Could not dispatch async task for result %d. "
                    "Is Celery/Redis running? Falling back to sync.",
                    result.id,
                )
                try:
                    _generate_certificate_sync(result)
                except Exception:
                    logger.error(
                        "Sync certificate generation also failed for result %d",
                        result.id, exc_info=True,
                    )

        from django.conf import settings
        if settings.CELERY_TASK_ALWAYS_EAGER:
            dispatch_result_task()
        else:
            transaction.on_commit(dispatch_result_task)

        return AttemptResult(
            attempt_id=attempt.id,
            total_questions=total_questions,
            correct_answers=correct_count,
            wrong_answers=wrong_count,
            unanswered=unanswered_count,
            score=total_score,
            max_score=max_score,
            percentage=percentage,
            is_passed=is_passed,
            time_taken_seconds=time_taken,
        )

    @staticmethod
    def _build_result_from_attempt(attempt: TestAttempt) -> AttemptResult:
        """Build AttemptResult from existing Result (for double-submit recovery)."""
        try:
            result = Result.objects.get(attempt=attempt)
            return AttemptResult(
                attempt_id=attempt.id,
                total_questions=result.total_questions,
                correct_answers=result.correct_answers,
                wrong_answers=result.wrong_answers,
                unanswered=result.unanswered,
                score=result.score,
                max_score=result.max_score,
                percentage=result.percentage,
                is_passed=result.is_passed,
                time_taken_seconds=result.time_taken_seconds,
            )
        except Result.DoesNotExist:
            raise ValueError("Attempt yakunlangan, lekin natija topilmadi.")


# ---------------------------------------------------------------------------
# 4. TimerService
# ---------------------------------------------------------------------------

class TimerService:
    """
    Timer boshqaruvi — vaqt holatini tekshirish va timeout amalga oshirish.

    Celery beat yoki request ichida chaqirilishi mumkin.
    """

    @staticmethod
    def check_timeout(attempt: TestAttempt) -> bool:
        """Attempt timeout bo'lganligini tekshirish."""
        if attempt.status != TestAttempt.Status.IN_PROGRESS:
            return False

        if attempt.is_time_expired:
            SubmitAttemptService._timeout_attempt(attempt)
            return True

        return False

    @staticmethod
    def get_remaining_seconds(attempt: TestAttempt) -> int | None:
        """Qolgan vaqtni soniyalarda qaytarish."""
        return attempt.remaining_seconds
