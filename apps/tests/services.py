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
    AttemptSectionProgress,
    Choice,
    ExamSection,
    ExamWrittenBridge,
    GapBlank,
    GapResponse,
    MatchingOption,
    MatchingPair,
    MatchingPrompt,
    MatchingResponse,
    Question,
    ReadingPassage,
    StudentAnswer,
    Test,
    TestAttempt,
)
from apps.tests.scoring import (
    aggregate as _aggregate_scores,
)
from apps.tests.scoring import (
    grade_gap_fill as _grade_gap_fill,
)
from apps.tests.scoring import (
    grade_matching as _grade_matching,
)
from apps.tests.scoring import (
    normalize_text as _normalize_text,
)
from apps.tests.scoring import (
    written_earned as _written_earned,
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
    # Milliy Sertifikat extension (defaults keep legacy callers working).
    grading_status: str = "graded"
    objective_score: Decimal = Decimal("0")
    writing_score: Decimal = Decimal("0")
    pending_written_count: int = 0
    certificate_status: str = ""


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
        # DB conditional-unique is the authority against concurrent starts;
        # translate IntegrityError into the friendly active-attempt error.
        from django.db import IntegrityError

        try:
            attempt = TestAttempt.objects.create(
                test=test,
                student=student,
                status=TestAttempt.Status.IN_PROGRESS,
            )
        except IntegrityError:
            raise ValueError(
                "Sizda allaqachon davom etayotgan attempt bor. "
                "Avval uni tugating yoki timeout bo'lishini kuting."
            )

        # -- Bo'lim taymerlari (faqat mustaqil vaqtli bo'limlar uchun) -------
        timed_sections = test.sections.filter(duration_minutes__gt=0)
        if timed_sections:
            AttemptSectionProgress.objects.bulk_create(
                [
                    AttemptSectionProgress(attempt=attempt, section=section)
                    for section in timed_sections
                ],
                ignore_conflicts=True,
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
        - Attempt IN_PROGRESS holatda bo'lishi kerak (yakunlangan yoki
          PENDING_GRADING attemptga yozish taqiqlanadi).
        - Vaqt tugamagan bo'lishi kerak (test + bo'lim vaqti).
        - Savol shu testga tegishli bo'lishi kerak.
        - Single choice: bitta variant tanlash shart.
        - Multiple choice: kamida bitta variant tanlash kerak.
        - GAP_FILL: faqat belgilangan bo'shliq pozitsiyalari saqlanadi.
        - MATCHING: prompt/option ID lar shu savolga tegishli bo'lishi shart.
        - WRITTEN: matn qoralamasi saqlanadi, baholanmaydi.
        - Oldingi javob bo'lsa, yangilash (upsert — duplicate row yo'q).
    """

    _CLEARED = object()
    _SECTION_EXPIRED = object()

    @staticmethod
    def execute(
        attempt_id: int,
        question_id: int,
        choice_ids: list[int] | None = None,
        student: Any = None,
        text_answer: str = "",
        allow_clear: bool = False,
        gap_answers: dict | None = None,
        matching: dict | None = None,
        written_text: str | None = None,
    ) -> StudentAnswer | None:
        """Save an answer and report timeout only after finalization commits."""
        answer = SaveAnswerService._execute_atomic(
            attempt_id=attempt_id,
            question_id=question_id,
            choice_ids=list(choice_ids or []),
            student=student,
            text_answer=text_answer,
            allow_clear=allow_clear,
            gap_answers=gap_answers,
            matching=matching,
            written_text=written_text,
        )
        if answer is SaveAnswerService._CLEARED:
            return None
        if answer is SaveAnswerService._SECTION_EXPIRED:
            raise ValueError("Bo'lim vaqti tugadi! Bu bo'limga javob yozib bo'lmaydi.")
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
        gap_answers: dict | None = None,
        matching: dict | None = None,
        written_text: str | None = None,
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

        # -- Status tekshirish (state machine: faqat IN_PROGRESS yozadi) ---
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
            question = Question.objects.select_related("section").get(
                id=question_id,
                test=attempt.test,
            )
        except Question.DoesNotExist:
            logger.warning(
                "Save answer failed: question=%d not in test=%d",
                question_id, attempt.test.id,
            )
            raise ValueError("Savol topilmadi yoki bu testga tegishli emas.")

        # -- Bo'lim vaqti (server authority) --------------------------------
        if question.section_id and question.section.duration_minutes:
            progress, _ = AttemptSectionProgress.objects.get_or_create(
                attempt=attempt,
                section_id=question.section_id,
            )
            if progress.is_expired:
                if not progress.completed_at:
                    progress.completed_at = timezone.now()
                    progress.save(update_fields=["completed_at"])
                logger.info(
                    "Section expired on save: attempt=%d section=%d",
                    attempt.id, question.section_id,
                )
                return SaveAnswerService._SECTION_EXPIRED

        qtype = question.question_type
        has_content = bool(choice_ids) or bool(text_answer.strip()) or gap_answers or matching
        if written_text is not None and written_text.strip():
            has_content = True
        if allow_clear and not has_content and not (written_text and written_text.strip()):
            StudentAnswer.objects.filter(attempt=attempt, question=question).delete()
            return SaveAnswerService._CLEARED

        # -- GAP_FILL -------------------------------------------------------
        if qtype == Question.QuestionType.GAP_FILL:
            return SaveAnswerService._save_gap_fill(attempt, question, gap_answers or {})

        # -- MATCHING --------------------------------------------------------
        if qtype == Question.QuestionType.MATCHING:
            return SaveAnswerService._save_matching(attempt, question, matching or {})

        # -- WRITTEN (qoralama; baholash esse dvigateli orqali) --------------
        if qtype == Question.QuestionType.WRITTEN:
            return SaveAnswerService._save_written(attempt, question, written_text or "")

        # -- Matnli javob savollari (TEXT_MATCH) ---------------------------
        if qtype == Question.QuestionType.TEXT_MATCH:
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

    # -- GAP_FILL / MATCHING / WRITTEN helpers ------------------------------

    @staticmethod
    def _save_gap_fill(attempt, question, gap_answers: dict) -> StudentAnswer:
        """Upsert per-blank responses. Unknown positions are ignored (extras)."""
        known = set(
            GapBlank.objects.filter(question=question).values_list("position", flat=True)
        )
        student_answer, _ = StudentAnswer.objects.get_or_create(
            attempt=attempt, question=question,
        )
        for raw_pos, raw_text in (gap_answers or {}).items():
            try:
                pos = int(raw_pos)
            except (TypeError, ValueError):
                raise ValueError("Bo'shliq pozitsiyasi noto'g'ri.")
            if pos not in known:
                continue  # extra answers never persist, never grade
            GapResponse.objects.update_or_create(
                answer=student_answer,
                blank_position=pos,
                defaults={"response_text": str(raw_text or "")[:200]},
            )
        return student_answer

    @staticmethod
    def _save_matching(attempt, question, matching: dict) -> StudentAnswer:
        """Upsert per-prompt mappings. IDs are validated against the question.

        Raises ValueError on unknown prompt ids or foreign option ids —
        invalid mappings never persist.
        """
        prompt_ids = set(
            MatchingPrompt.objects.filter(question=question).values_list("id", flat=True)
        )
        option_ids = set(
            MatchingOption.objects.filter(question=question).values_list("id", flat=True)
        )
        student_answer, _ = StudentAnswer.objects.get_or_create(
            attempt=attempt, question=question,
        )
        for raw_pid, raw_oid in (matching or {}).items():
            try:
                pid = int(raw_pid)
            except (TypeError, ValueError):
                raise ValueError("Moslashtirish so'rovi noto'g'ri.")
            if pid not in prompt_ids:
                raise ValueError("Moslashtirish so'rovi topilmadi.")
            if raw_oid in (None, ""):
                option = None
            else:
                try:
                    oid = int(raw_oid)  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    raise ValueError("Moslashtirish varianti noto'g'ri.")
                if oid not in option_ids:
                    raise ValueError("Moslashtirish varianti bu savolga tegishli emas.")
                option = MatchingOption(id=oid)
            prompt = MatchingPrompt(id=pid)
            MatchingResponse.objects.update_or_create(
                answer=student_answer,
                prompt=prompt,
                defaults={"selected_option": option},
            )
        return student_answer

    @staticmethod
    def _save_written(attempt, question, written_text: str) -> StudentAnswer:
        """Persist the written draft (autosave). Never grades — the essay
        bridge grades via the canonical engine at submit time."""
        from apps.essays.services import WordCounter

        text = str(written_text or "")
        student_answer, _ = StudentAnswer.objects.get_or_create(
            attempt=attempt, question=question,
        )
        student_answer.written_text = text
        student_answer.written_word_count = WordCounter.count(text)
        student_answer.save(update_fields=["written_text", "written_word_count"])
        return student_answer


# ---------------------------------------------------------------------------
# Sync certificate generation (fallback when Celery is not running)
# ---------------------------------------------------------------------------

def _generate_certificate_sync(result, *, is_milliy: bool | None = None, profile=None) -> None:
    """
    Sertifikat generatsiya qilish — Celery'siz, to'g'ridan-to'g'ri (thin wrapper).

    Agar o'tgan bo'lsa → PDF yaratiladi va saqlanadi.
    Xatolik bo'lsa → log yoziladi, lekin test natijasi buzilmaydi.
    """
    if not result.is_passed:
        return

    try:
        from apps.certificates.services.generation import generate_certificate as _gen

        _gen(result, is_milliy=is_milliy, profile=profile)
        logger.info("Certificate generated (sync): result=%s", getattr(result, "id", "?"))
    except Exception as e:
        logger.error("Sync certificate generation failed: %s", e, exc_info=True)


# ---------------------------------------------------------------------------
# 2b. ExamBridgeService — TestAttempt WRITTEN ↔ canonical EssaySubmission
# ---------------------------------------------------------------------------

class ExamBridgeService:
    """
    Idempotent bridge between exam written answers and the ONE canonical
    essay grading pipeline (apps.essays). No grading is duplicated here:
    the essay engine grades, exams only scale the effective score onto the
    question's points.
    """

    @staticmethod
    def ensure_bridge(answer: StudentAnswer) -> ExamWrittenBridge:
        """Get-or-create the bridge row for an answer (idempotent)."""
        from apps.essays.services import ESSAY_RUBRIC_VERSION

        bridge, created = ExamWrittenBridge.objects.get_or_create(
            attempt_id=answer.attempt_id,
            question_id=answer.question_id,
            defaults={"answer": answer, "rubric_version": ESSAY_RUBRIC_VERSION},
        )
        if created:
            logger.info(
                "Written bridge created: attempt=%d question=%d",
                answer.attempt_id, answer.question_id,
            )
        return bridge

    @staticmethod
    def submit_written(answer: StudentAnswer, student_id: int):
        """Create (once) + dispatch grading for a written answer.

        Returns the EssaySubmission, or None when there is no text to grade
        (unanswered). Never raises: AI dispatch failure leaves the exam in
        PENDING_GRADING and finalize retries.
        """
        from apps.essays.models import EssaySubmission
        from apps.essays.services import ESSAY_RUBRIC_VERSION, WordCounter

        text = (answer.written_text or "").strip()
        if not text:
            return None
        bridge = ExamBridgeService.ensure_bridge(answer)
        if bridge.essay_submission_id:
            submission = bridge.essay_submission
            if submission.status == EssaySubmission.Status.DRAFT:
                ExamBridgeService._dispatch(submission)
            return submission
        submission = EssaySubmission.objects.create(
            student_id=student_id,
            topic=None,
            essay_text=text,
            word_count=WordCounter.count(text),
            status=EssaySubmission.Status.DRAFT,
            # Written answers arriving from the Milliy exam engine, not the
            # student's website/bot essay flow.
            source=EssaySubmission.Source.EXAM,
            # Milliy Sertifikat written answers are high-stakes: they are
            # graded per student and never reuse another account's evaluation
            # (see apps/essays/services.build_grading_context).
            cache_scope=EssaySubmission.CacheScope.HIGH_STAKES,
        )
        bridge.essay_submission = submission
        bridge.rubric_version = ESSAY_RUBRIC_VERSION
        bridge.save(update_fields=["essay_submission", "rubric_version"])
        ExamBridgeService._dispatch(submission)
        return submission

    @staticmethod
    def _rubric_version() -> str:
        from apps.essays.services import ESSAY_RUBRIC_VERSION

        return ESSAY_RUBRIC_VERSION

    @staticmethod
    def _dispatch(submission) -> None:
        from apps.essays.services import start_grading

        try:
            result = start_grading(submission)
            if not result.get("success"):
                logger.warning(
                    "Written grading not started: submission=%d error=%s",
                    submission.id, result.get("error"),
                )
        except Exception:
            logger.exception(
                "Written grading dispatch failed: submission=%d", submission.id
            )

    @staticmethod
    def written_points(question: Question, submission) -> Decimal | None:
        """Scale the canonical effective score onto question points.

        None = not graded yet (pending — never zero).
        """
        from apps.essays.services import (
            ESSAY_RUBRIC_MAX_SCORE,
            essay_has_grade_result,
        )

        if submission is None or not essay_has_grade_result(submission):
            return None
        return _written_earned(
            question.points, submission.effective_score, ESSAY_RUBRIC_MAX_SCORE
        )


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
        # State machine: IN_PROGRESS → COMPLETED/TIMEOUT/PENDING_GRADING;
        # PENDING_GRADING → COMPLETED (finalize, idempotent); terminal
        # holatlardan qaytish mumkin emas (GRADED → IN_PROGRESS yo'q).
        if attempt.status == TestAttempt.Status.PENDING_GRADING:
            logger.info(
                "Submit on pending attempt — finalizing: attempt=%d",
                attempt.id,
            )
            return SubmitAttemptService.finalize_pending_grading(
                attempt_id=attempt_id, student=student
            )
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

        Grading algorithm (scoring semantics unchanged):
            1. Savolning to'g'ri Choice larini aniqlash.
            2. Student tanlagan Choice lar bilan solishtirish.
            3. Single choice: to'g'ri bo'lsa -> savol points, noto'g'ri -> 0.
            4. Multiple choice: BARCHA to'g'ri tanlangan bo'lsa -> savol points,
               aks holda -> 0 (qisman javob ball olmaydi).
            5. Foiz = (score / max_score) * 100.
            6. is_passed = (foiz >= pass_percentage).

        Performance: 1 query for questions+choices, 1 for answers, 1 for the
        M2M through table; scoring in Python; single bulk_update.
        """
        test = attempt.test
        now = timezone.now()

        # -- Vaqt hisoblash ------------------------------------------------
        time_taken = 0
        if attempt.started_at:
            delta = now - attempt.started_at
            time_taken = int(delta.total_seconds())

        # -- Barcha savollarni olish (prefetch: choices, gaps, matching) ----
        all_questions = list(
            test.questions.select_related("section", "reading_passage")
            .prefetch_related(
                "choices",
                "gap_blanks",
                "matching_prompts__correct_pair",
                "matching_options",
            )
            .order_by("position")
        )

        # -- Javoblarni bir marta olish (queries: answers, M2M, gap, match) --
        answers = list(
            attempt.answers.select_related("question").prefetch_related(
                "gap_responses", "matching_responses",
            )
        )
        answers_by_qid = {a.question_id: a for a in answers}
        selected_map: dict[int, set[int]] = {}
        gap_map: dict[int, dict[int, str]] = {}
        match_map: dict[int, dict[int, int | None]] = {}
        if answers:
            through = StudentAnswer.selected_choices.through
            rows = through.objects.filter(studentanswer_id__in=[a.id for a in answers]).values_list(
                "studentanswer_id", "choice_id"
            )
            tmp: dict[int, set[int]] = {}
            for ans_id, choice_id in rows:
                tmp.setdefault(ans_id, set()).add(choice_id)
            for a in answers:
                selected_map[a.id] = tmp.get(a.id, set())
                gap_map[a.id] = {
                    gr.blank_position: gr.response_text
                    for gr in a.gap_responses.all()
                }
                match_map[a.id] = {
                    mr.prompt_id: mr.selected_option_id
                    for mr in a.matching_responses.all()
                }

        # -- To'g'ri javoblar xaritasi (prefetch'dan, qo'shimcha query yo'q) -
        correct_map = {
            q.id: {c.id for c in q.choices.all() if c.is_correct}
            for q in all_questions
        }
        gaps_by_qid: dict[int, dict[int, list[str]]] = {}
        for q in all_questions:
            if q.question_type != Question.QuestionType.GAP_FILL:
                continue
            accepted: dict[int, list[str]] = {}
            for b in q.gap_blanks.all():
                accepted.setdefault(b.position, []).append(b.answer_text)
            gaps_by_qid[q.id] = accepted
        pairs_by_qid: dict[int, dict[int, int | None]] = {}
        for q in all_questions:
            if q.question_type != Question.QuestionType.MATCHING:
                continue
            pairs_by_qid[q.id] = {
                p.id: (p.correct_pair.correct_option_id if hasattr(p, "correct_pair") else None)
                for p in q.matching_prompts.all()
            }

        # -- Skoring profili (konfiguratsiya; rasmiy qiymatlar yo'q) ----------
        # Bog'langan profil bo'lsa — o'sha; bo'lmasa umumiy default
        # (UNVERIFIED — sertifikat bermaydi, faqat ball hisoblaydi).
        from apps.certificates.services.generation import resolve_profile

        profile = resolve_profile(test)

        from apps.tests.scoring import QuestionScore

        total_questions = len(all_questions)
        to_update: list[StudentAnswer] = []
        question_scores: list[QuestionScore] = []
        pending_written_answers: list[StudentAnswer] = []

        def _section_of(question) -> tuple[int | None, str]:
            if question.section_id:
                return question.section_id, question.section.code or ""
            return None, ""

        # -- Har bir savolni tekshirish (Python'da, query'siz) --------------
        for question in all_questions:
            qmax = Decimal(str(question.points))
            section_id, section_code = _section_of(question)
            cfg = question.config or {}
            case_sensitive = bool(cfg.get("case_sensitive", False))
            partial_credit = bool(cfg.get("partial_credit", False))

            student_answer = answers_by_qid.get(question.id)
            if student_answer is None:
                # Javob berilmagan
                question_scores.append(QuestionScore(
                    question_id=question.id, earned=Decimal("0"), maximum=qmax,
                    is_correct=False, answered=False,
                    section_code=section_code, section_id=section_id,
                ))
                continue

            qtype = question.question_type

            # -- GAP_FILL ----------------------------------------------------
            if qtype == Question.QuestionType.GAP_FILL:
                accepted = gaps_by_qid.get(question.id, {})
                if not accepted:
                    logger.warning("Gap-fill without blanks: question=%d", question.id)
                    is_correct, earned = False, Decimal("0")
                else:
                    gs = _grade_gap_fill(
                        accepted, gap_map.get(student_answer.id, {}),
                        question.points, partial_credit=partial_credit,
                        case_sensitive=case_sensitive,
                    )
                    is_correct, earned = gs.fully_correct, gs.earned
                question_scores.append(QuestionScore(
                    question_id=question.id, earned=earned, maximum=qmax,
                    is_correct=is_correct, section_code=section_code,
                    section_id=section_id,
                ))
                if student_answer.is_correct != is_correct:
                    student_answer.is_correct = is_correct
                    to_update.append(student_answer)
                continue

            # -- MATCHING -----------------------------------------------------
            if qtype == Question.QuestionType.MATCHING:
                correct_pairs = {
                    pid: oid for pid, oid in pairs_by_qid.get(question.id, {}).items()
                    if oid is not None
                }
                if not correct_pairs:
                    logger.warning("Matching without pairs: question=%d", question.id)
                    is_correct, earned = False, Decimal("0")
                else:
                    ms = _grade_matching(
                        correct_pairs, match_map.get(student_answer.id, {}),
                        question.points, partial_credit=partial_credit,
                    )
                    is_correct, earned = ms.fully_correct, ms.earned
                question_scores.append(QuestionScore(
                    question_id=question.id, earned=earned, maximum=qmax,
                    is_correct=is_correct, section_code=section_code,
                    section_id=section_id,
                ))
                if student_answer.is_correct != is_correct:
                    student_answer.is_correct = is_correct
                    to_update.append(student_answer)
                continue

            # -- WRITTEN (esse ko'prigi; obyektiv ball yo'q) ------------------
            if qtype == Question.QuestionType.WRITTEN:
                if not (student_answer.written_text or "").strip():
                    question_scores.append(QuestionScore(
                        question_id=question.id, earned=Decimal("0"), maximum=qmax,
                        is_correct=False, answered=False,
                        section_code=section_code, section_id=section_id,
                        kind="written",
                    ))
                    continue
                submission = ExamBridgeService.submit_written(
                    student_answer, attempt.student_id
                )
                earned = (
                    ExamBridgeService.written_points(question, submission)
                    if submission is not None else None
                )
                if earned is None:
                    pending_written_answers.append(student_answer)
                    question_scores.append(QuestionScore(
                        question_id=question.id, earned=Decimal("0"), maximum=qmax,
                        is_correct=None, section_code=section_code,
                        section_id=section_id, kind="written",
                    ))
                    if student_answer.is_correct is not None:
                        student_answer.is_correct = None
                        to_update.append(student_answer)
                else:
                    is_correct = earned >= qmax
                    question_scores.append(QuestionScore(
                        question_id=question.id, earned=earned, maximum=qmax,
                        is_correct=is_correct, section_code=section_code,
                        section_id=section_id, kind="written",
                    ))
                    if student_answer.is_correct != is_correct:
                        student_answer.is_correct = is_correct
                        to_update.append(student_answer)
                continue

            correct_choice_ids = correct_map.get(question.id, set())
            selected_choice_ids = selected_map.get(student_answer.id, set())

            # -- Grading logic (semantika o'zgarmagan) ----------------------
            if qtype == Question.QuestionType.TEXT_MATCH:
                # Matnli javob: normalize (kichik harf, bo'shliqlar) va taqqoslash
                student_text = _normalize_text(student_answer.text_answer or "")
                correct_text = _normalize_text(question.correct_text or "")
                is_correct = bool(student_text and correct_text and student_text == correct_text)
                question_scores.append(QuestionScore(
                    question_id=question.id,
                    earned=qmax if is_correct else Decimal("0"), maximum=qmax,
                    is_correct=is_correct, section_code=section_code,
                    section_id=section_id,
                ))
            elif not selected_choice_ids:
                # Hech narsa tanlanmagan (matnli savollar yuqorida qaytdi)
                question_scores.append(QuestionScore(
                    question_id=question.id, earned=Decimal("0"), maximum=qmax,
                    is_correct=False, section_code=section_code,
                    section_id=section_id,
                ))
                if student_answer.is_correct is not False:
                    student_answer.is_correct = False
                    to_update.append(student_answer)
                continue
            elif qtype == Question.QuestionType.SINGLE_CHOICE:
                is_correct = correct_choice_ids == selected_choice_ids
                question_scores.append(QuestionScore(
                    question_id=question.id,
                    earned=qmax if is_correct else Decimal("0"), maximum=qmax,
                    is_correct=is_correct, section_code=section_code,
                    section_id=section_id,
                ))
            else:
                # Multiple choice: BARCHA to'g'ri tanlangan bo'lishi kerak
                is_correct = (
                    correct_choice_ids == selected_choice_ids
                    and len(selected_choice_ids) > 0
                )
                question_scores.append(QuestionScore(
                    question_id=question.id,
                    earned=qmax if is_correct else Decimal("0"), maximum=qmax,
                    is_correct=is_correct, section_code=section_code,
                    section_id=section_id,
                ))

            if student_answer.is_correct != is_correct:
                student_answer.is_correct = is_correct
                to_update.append(student_answer)

        if to_update:
            StudentAnswer.objects.bulk_update(to_update, ["is_correct"])

        # -- Kanonik agregatsiya (bitta manba: apps.tests.scoring) -----------
        agg = _aggregate_scores(question_scores, weights=profile.weights)
        section_names = {
            q.section_id: (q.section.name if q.section_id else "")
            for q in all_questions if q.section_id
        }
        for sec in agg.sections:
            if sec.section_id in section_names:
                sec.section_name = section_names[sec.section_id] or sec.section_code
        total_score = agg.total_earned
        max_score = agg.total_max
        correct_count = agg.correct_count
        wrong_count = agg.wrong_count
        unanswered_count = agg.unanswered_count

        # -- Foiz (vaznli; teng vaznda legacy formula bilan bir xil) ---------
        percentage = agg.weighted_percentage

        is_passed = percentage >= Decimal(str(test.pass_percentage))
        grading_status = "pending_grading" if agg.has_pending_writing else "graded"

        # -- Attempt ni yangilash -------------------------------------------
        if grading_status == "pending_grading":
            new_status = TestAttempt.Status.PENDING_GRADING
        else:
            new_status = (
                TestAttempt.Status.TIMEOUT
                if is_timeout
                else TestAttempt.Status.COMPLETED
            )
        TestAttempt.objects.filter(id=attempt.id).update(
            status=new_status,
            completed_at=now,
            score=total_score,
            percentage=percentage,
            is_passed=is_passed and grading_status == "graded",
        )

        # -- Result modeliga saqlash (denormalized, race-safe) --------------
        # finalize_pending_grading qayta chaqirilganda Result allaqachon
        # mavjud bo'ladi — uni yangilaymiz (qisman natijani saqlamaymiz).
        # get_or_create/update_or_create handle concurrency internally
        # (own savepoints) — never catch IntegrityError in this transaction.
        from apps.results.models import ResultSectionScore

        result, _created = Result.objects.get_or_create(
            attempt=attempt,
            defaults={
                "student": attempt.student,
                "test": test,
                "course": test.course,
                "total_questions": total_questions,
                "correct_answers": correct_count,
                "wrong_answers": wrong_count,
                "unanswered": unanswered_count,
                "score": total_score,
                "max_score": max_score,
                "percentage": percentage,
                "is_passed": is_passed and grading_status == "graded",
                "time_taken_seconds": time_taken,
                "grading_status": grading_status,
                "objective_score": agg.objective_earned,
                "writing_score": agg.writing_earned,
                "scoring_profile": profile,
                "scoring_version": f"{profile.name}:{profile.version}",
                "rubric_version": ExamBridgeService._rubric_version(),
            },
        )
        # Refresh path (finalize) or concurrent winner: overwrite with the
        # deterministic re-grade — same inputs always produce same outputs.
        Result.objects.filter(pk=result.pk).update(
            total_questions=total_questions,
            correct_answers=correct_count,
            wrong_answers=wrong_count,
            unanswered=unanswered_count,
            score=total_score,
            max_score=max_score,
            percentage=percentage,
            is_passed=is_passed and grading_status == "graded",
            time_taken_seconds=time_taken,
            grading_status=grading_status,
            objective_score=agg.objective_earned,
            writing_score=agg.writing_earned,
            scoring_profile=profile,
            scoring_version=f"{profile.name}:{profile.version}",
            rubric_version=ExamBridgeService._rubric_version(),
        )
        # NOTE: no refresh_from_db() here — downstream code only needs
        # result.id, and callers/tests re-query for fresh values. Saves 1 query.
        for sec in agg.sections:
            ResultSectionScore.objects.update_or_create(
                result=result,
                section_code=sec.section_code,
                defaults={
                    "section_id": sec.section_id,
                    "section_name": sec.section_name,
                    "earned": sec.earned,
                    "maximum": sec.maximum,
                    "weight": sec.weight,
                },
            )

        logger.info(
            "Attempt graded: id=%d, score=%s/%s, pct=%s%%, passed=%s, status=%s",
            attempt.id, total_score, max_score, percentage, is_passed, grading_status,
        )

        # -- Async tasks: PDF + Telegram (faqat to'liq baholanganda) --------
        # PENDING_GRADING attemptlar uchun hech qanday sertifikat/xabar
        # jo'natilmaydi — finalize() yozma baho tayyor bo'lgach dispatch qiladi.
        # is_milliy in-memory hisoblanadi (all_questions dan — query'siz).
        _is_milliy = any(
            q.section_id is not None
            or q.question_type
            in (
                Question.QuestionType.GAP_FILL,
                Question.QuestionType.MATCHING,
                Question.QuestionType.WRITTEN,
            )
            for q in all_questions
        )

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
                    _generate_certificate_sync(result, is_milliy=_is_milliy, profile=profile)
                except Exception:
                    logger.error(
                        "Sync certificate generation also failed for result %d",
                        result.id, exc_info=True,
                    )

        from django.conf import settings
        if grading_status != "graded":
            logger.info(
                "Result %d pending written grading — dispatch deferred.",
                result.id,
            )
        elif settings.CELERY_TASK_ALWAYS_EAGER:
            dispatch_result_task()
        else:
            transaction.on_commit(dispatch_result_task)

        from apps.certificates.services.generation import (
            certificate_status as _cert_status,
        )

        return AttemptResult(
            attempt_id=attempt.id,
            total_questions=total_questions,
            correct_answers=correct_count,
            wrong_answers=wrong_count,
            unanswered=unanswered_count,
            score=total_score,
            max_score=max_score,
            percentage=percentage,
            is_passed=is_passed and grading_status == "graded",
            time_taken_seconds=time_taken,
            grading_status=grading_status,
            objective_score=agg.objective_earned,
            writing_score=agg.writing_earned,
            pending_written_count=len(pending_written_answers),
            certificate_status=_cert_status(
                result, is_milliy=_is_milliy, profile=profile),
        )

    @staticmethod
    def _dispatch_if_newly_eligible(attempt: TestAttempt) -> None:
        """Dispatch notifications/cert task when a COMPLETED result became
        certificate-eligible after the fact (e.g. profile verified later).

        Best-effort and idempotent: the canonical service refuses when still
        ineligible, and reuses an existing GENERATED certificate.
        """
        try:
            result = Result.objects.select_related("test").get(attempt=attempt)
        except Result.DoesNotExist:
            return
        from apps.certificates.services.generation import certificate_status

        if certificate_status(result) != "eligible":
            return
        from apps.results.models import Certificate

        if Certificate.objects.filter(
            result=result, status=Certificate.Status.GENERATED
        ).exists():
            return
        try:
            from apps.notifications.tasks import process_test_result_task

            process_test_result_task.delay(result_id=result.id)
        except Exception:
            logger.warning(
                "Could not dispatch newly-eligible task for result %d.",
                result.id,
            )
            try:
                _generate_certificate_sync(result)
            except Exception:
                logger.error(
                    "Sync certificate generation also failed for result %d",
                    result.id, exc_info=True,
                )

    @staticmethod
    def _build_result_from_attempt(attempt: TestAttempt) -> AttemptResult:
        """Build AttemptResult from existing Result (for double-submit recovery)."""
        try:
            result = Result.objects.get(attempt=attempt)
            from apps.certificates.services.generation import (
                certificate_status as _cert_status,
            )

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
                grading_status=result.grading_status,
                objective_score=result.objective_score,
                writing_score=result.writing_score,
                pending_written_count=(
                    ExamWrittenBridge.objects.filter(
                        attempt=attempt, essay_submission__isnull=False
                    ).count()
                    if result.grading_status == "pending_grading" else 0
                ),
                certificate_status=_cert_status(result),
            )
        except Result.DoesNotExist:
            raise ValueError("Attempt yakunlangan, lekin natija topilmadi.")

    @staticmethod
    @transaction.atomic
    def finalize_pending_grading(attempt_id: int, student: Any) -> AttemptResult:
        """Complete a PENDING_GRADING attempt once writing is graded.

        Idempotent: repeated calls reuse the existing Result when nothing
        changed; raises ValueError while writing is still pending or the
        attempt is not in PENDING_GRADING state (invalid transition).
        """
        try:
            attempt = (
                TestAttempt.objects.select_related("test", "test__course")
                .select_for_update()
                .get(id=attempt_id, student=student)
            )
        except TestAttempt.DoesNotExist:
            raise ValueError("Attempt topilmadi.")
        if attempt.status != TestAttempt.Status.PENDING_GRADING:
            if attempt.status in (
                TestAttempt.Status.COMPLETED, TestAttempt.Status.TIMEOUT,
            ):
                outcome = SubmitAttemptService._build_result_from_attempt(attempt)
                SubmitAttemptService._dispatch_if_newly_eligible(attempt)
                return outcome
            raise ValueError("Bu attempt yakunlanmagan.")
        bridges = list(
            ExamWrittenBridge.objects.select_related("essay_submission", "answer__question")
            .filter(attempt=attempt)
        )
        from apps.essays.services import essay_has_grade_result

        still_pending = [
            b for b in bridges
            if b.essay_submission is None or not essay_has_grade_result(b.essay_submission)
        ]
        # Retry dispatch for submissions stuck in DRAFT (AI failure recovery).
        for b in bridges:
            sub = b.essay_submission
            if sub is not None and not essay_has_grade_result(sub):
                from apps.essays.models import EssaySubmission as _ES

                if sub.status == _ES.Status.DRAFT:
                    ExamBridgeService._dispatch(sub)
        if still_pending:
            raise ValueError(
                f"Yozma ish baholanmoqda ({len(still_pending)} ta kutilmoqda)."
            )
        return SubmitAttemptService._grade_attempt(attempt)


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
