"""
Tests app — Test, Question, Choice, StudentAnswer, TestAttempt.

This is the heart of the platform. Key design decisions:

    1. TestAttempt is separate from TestAttemptAnswer so that partial saves
       (auto-save during a timed test) can be written row-by-row without
       locking the whole attempt.

    2. `time_limit_minutes` lives on the Test model, not on Attempt —
       an instructor sets the limit once; every attempt enforces it.

    3. `correct_answer` on Question is the *authoritative* answer.
       The student's picked option is stored in StudentAnswer. This
       decoupling means we can regrade or adjust scoring later.

    4. `points` on Question allows weighted scoring — a harder question
       can be worth more than a simple recall one.
"""

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


# ---------------------------------------------------------------------------
# Test (quiz / exam)
# ---------------------------------------------------------------------------
class Test(models.Model):
    """
    A time-bound test that students can attempt.

    Relationships:
        course    — which course this test belongs to (optional: standalone).
        module    — optionally scoped to a specific module.
        questions — ordered set of questions (M2M through position).

    `time_limit_minutes`  — 0 means no time limit.
    `max_attempts`        — how many times a student can retake (0 = unlimited).
    `pass_percentage`     — minimum % to pass (used for certificate eligibility).
    """

    __test__ = False

    class Difficulty(models.TextChoices):
        EASY = "easy", _("Oson")
        MEDIUM = "medium", _("O'rta")
        HARD = "hard", _("Qiyin")

    class Status(models.TextChoices):
        DRAFT = "draft", _("Qoralama")
        PUBLISHED = "published", _("E'lon qilingan")
        ARCHIVED = "archived", _("Arxivlangan")

    subject = models.CharField(
        _("fan / yo'nalish"),
        max_length=20,
        choices=[
            ("uzbek", _("Ona tili va adabiyot")),
            ("english", _("Ingliz tili (IELTS & Multi-level)")),
        ],
        default="uzbek",
        db_index=True,
    )
    title = models.CharField(_("sarlavha"), max_length=255)
    description = models.TextField(_("tavsif"), blank=True)
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="tests",
        verbose_name=_("kurs"),
    )
    module = models.ForeignKey(
        "courses.Module",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tests",
        verbose_name=_("modul"),
    )

    # -- Scoring & timing -----------------------------------------------------
    time_limit_minutes = models.PositiveIntegerField(
        _("vaqt cheklovi (daqiqa)"),
        default=0,
        help_text=_("0 = cheksiz vaqt."),
    )
    scoring_profile = models.ForeignKey(
        "ExamScoringProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tests",
        verbose_name=_("skoring profili"),
        help_text=_(
            "Milliy imtihonlar uchun bog'langan konfiguratsiya. Bo'sh = legacy."
        ),
    )
    max_attempts = models.PositiveIntegerField(
        _("maksimal urinishlar"),
        default=1,
        help_text=_("0 = cheksiz urinishlar."),
    )
    pass_percentage = models.PositiveIntegerField(
        _("o'tish foizi (%)"),
        default=60,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    difficulty = models.CharField(
        _("qiyinlik darajasi"),
        max_length=10,
        choices=Difficulty.choices,
        default=Difficulty.MEDIUM,
    )

    # -- State ----------------------------------------------------------------
    status = models.CharField(
        _("holat"),
        max_length=12,
        choices=Status.choices,
        default=Status.PUBLISHED,
        db_index=True,
        help_text=_(
            "Qoralama — o'quvchilarga ko'rinmaydi; E'lon qilingan — ochiq; Arxivlangan — yashirin."
        ),
    )
    is_active = models.BooleanField(_("faolmi"), default=True)
    show_results_immediately = models.BooleanField(
        _("natijani darhol ko'rsatish"),
        default=True,
        help_text=_("Topshirgandan keyin natijani ko'rsatish."),
    )
    shuffle_questions = models.BooleanField(
        _("savollarni aralashtirish"),
        default=False,
    )
    shuffle_choices = models.BooleanField(
        _("variantlarni aralashtirish"),
        default=True,
    )
    mock_code = models.CharField(
        _("mock kodi"),
        max_length=32,
        blank=True,
        null=True,
        unique=True,
        db_index=True,
        help_text=_(
            "O'quvchilar tezkor ulanishi uchun unikal kod (masalan: #MOCK-401)"
        ),
    )
    audio_url = models.CharField(
        _("Listening audio URL"),
        max_length=500,
        blank=True,
        default="",
        help_text=_("Listening testi uchun audio fayl manzili."),
    )
    is_strict_mode = models.BooleanField(
        _("Strict Exam Mode (Anti-Cheat)"),
        default=False,
        help_text=_(
            "Yoqilsa, o'quvchi oynadan chiqsa ogohlantiriladi va 3-urinishda test yakunlanadi."
        ),
    )

    # -- Meta -----------------------------------------------------------------
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    updated_at = models.DateTimeField(_("yangilangan"), auto_now=True)

    class Meta:
        verbose_name = _("Test")
        verbose_name_plural = _("Testlar")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["course"], name="idx_test_course"),
            models.Index(fields=["is_active"], name="idx_test_active"),
            models.Index(
                fields=["subject", "is_active"], name="idx_test_subject_active"
            ),
        ]

    def __str__(self) -> str:
        return self.title

    @property
    def total_questions(self) -> int:
        # When the queryset annotates total_questions (TestListView),
        # Django sets it via the property setter below — return that
        # annotated value instead of firing an extra COUNT query.
        if hasattr(self, "_annotated_total_questions"):
            return self._annotated_total_questions  # type: ignore[attr-defined]
        return self.questions.count()

    @total_questions.setter
    def total_questions(self, value: int) -> None:
        self._annotated_total_questions = int(value)  # type: ignore[attr-defined]

    @property
    def total_points(self) -> int:
        """Sum of all question point values."""
        return self.questions.aggregate(total=models.Sum("points"))["total"] or 0

    @property
    def has_time_limit(self) -> bool:
        return self.time_limit_minutes > 0

    def save(self, *args, **kwargs) -> None:
        """Keep legacy `is_active` in sync with the three-state `status`.

        DRAFT and ARCHIVED tests must never be attemptable by students;
        all existing filters use is_active, so derive it from status.
        """
        self.is_active = self.status == self.Status.PUBLISHED
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# ExamSection  (Milliy Sertifikat bo'limi: Reading / Language / ...)
# ---------------------------------------------------------------------------
class ExamSection(models.Model):
    """
    Configurable exam section inside a Test.

    Sections are optional: ordinary tests without sections keep working
    (their questions simply have section=NULL). Codes are free text so new
    exam layouts never require code changes; the four constants below are
    the conventional Milliy Sertifikat sections.
    """

    READING = "READING"
    LISTENING = "LISTENING"
    LANGUAGE = "LANGUAGE"
    LITERATURE = "LITERATURE"
    WRITING = "WRITING"

    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name="sections",
        verbose_name=_("test"),
    )
    name = models.CharField(_("bo'lim nomi"), max_length=120)
    code = models.CharField(
        _("bo'lim kodi"),
        max_length=20,
        help_text=_("Masalan: READING, LISTENING, LANGUAGE, LITERATURE, WRITING."),
    )
    audio_url = models.CharField(
        _("bo'lim audio URL"),
        max_length=500,
        blank=True,
        default="",
    )
    order = models.PositiveIntegerField(_("tartib"), default=0)
    duration_minutes = models.PositiveIntegerField(
        _("bo'lim vaqti (daqiqa)"),
        default=0,
        help_text=_("0 = testning umumiy vaqti ishlatiladi."),
    )
    weight = models.DecimalField(
        _("vazn koeffitsiyenti"),
        max_digits=5,
        decimal_places=2,
        default=1,
        help_text=_("Agregat ballda bo'lim vazni (konfiguratsiya; rasmiy emas)."),
    )

    class Meta:
        verbose_name = _("Imtihon bo'limi")
        verbose_name_plural = _("Imtihon bo'limlari")
        ordering = ["order"]
        indexes = [
            models.Index(fields=["test", "order"], name="idx_section_test_order"),
        ]

    def __str__(self) -> str:
        return f"{self.test.title} — {self.name}"


# ---------------------------------------------------------------------------
# ReadingPassage  (bitta matn — bir nechta savol)
# ---------------------------------------------------------------------------
class ReadingPassage(models.Model):
    """
    First-class reading passage. One passage serves many questions of any
    type; the passage text is stored once and referenced, never duplicated
    into every question.
    """

    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name="passages",
        verbose_name=_("test"),
    )
    section = models.ForeignKey(
        ExamSection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="passages",
        verbose_name=_("bo'lim"),
    )
    title = models.CharField(_("sarlavha"), max_length=255, blank=True)
    content = models.TextField(_("matn"))
    audio_url = models.CharField(
        _("audio URL"),
        max_length=500,
        blank=True,
        default="",
        help_text=_("Listening yoki audio-matn uchun mp3/wav havola."),
    )
    source = models.CharField(
        _("manba"),
        max_length=255,
        blank=True,
        help_text=_("Ixtiyoriy: muallif/manba izohi."),
    )
    order = models.PositiveIntegerField(_("tartib"), default=0)

    class Meta:
        verbose_name = _("O'qish matni")
        verbose_name_plural = _("O'qish matnlari")
        ordering = ["order"]
        indexes = [
            models.Index(fields=["test", "order"], name="idx_passage_test_order"),
        ]

    def __str__(self) -> str:
        return self.title or f"Matn #{self.order}"


# ---------------------------------------------------------------------------
# Question
# ---------------------------------------------------------------------------
class Question(models.Model):
    """
    A single question inside a test.

    `correct_option` — FK to the correct Choice. Set by the instructor.
    `points`         — weight for this question in scoring.
    `explanation`    — shown after submission (if `show_results_immediately`).

    Milliy Sertifikat types: SINGLE/MULTIPLE/TEXT are the legacy objective
    types. GAP_FILL/MATCHING are objective with their own relational answer
    keys (GapBlank / MatchingPrompt+Option+Pair). WRITTEN is long-form and is
    never auto-graded — it bridges to the canonical essay engine.
    """

    class QuestionType(models.TextChoices):
        SINGLE_CHOICE = "single", _("Bita to'g'ri javob")
        MULTIPLE_CHOICE = "multiple", _("Ko'p to'g'ri javob")
        TEXT_MATCH = "text", _("Matnli javob")
        GAP_FILL = "gap_fill", _("Bo'shliqni to'ldirish")
        MATCHING = "matching", _("Moslashtirish")
        WRITTEN = "written", _("Yozma ish")

    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name="questions",
        verbose_name=_("test"),
    )
    section = models.ForeignKey(
        "ExamSection",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="questions",
        verbose_name=_("bo'lim"),
        help_text=_("Bo'sh bo'lsa — bo'limsiz oddiy test savoli (backward compat)."),
    )
    reading_passage = models.ForeignKey(
        "ReadingPassage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="questions",
        verbose_name=_("matn (passage)"),
        help_text=_("Bir matnga bir nechta savol biriktirilishi mumkin."),
    )
    passage = models.TextField(
        _("kontekst matni (passage)"),
        blank=True,
        help_text=_(
            "Savol ustida ko'rsatiladigan matn/parcha (matnli tahlil savollari uchun)."
        ),
    )
    text = models.TextField(_("savol matni"))
    question_type = models.CharField(
        _("savol turi"),
        max_length=10,
        choices=QuestionType.choices,
        default=QuestionType.SINGLE_CHOICE,
    )
    correct_text = models.CharField(
        _("to'g'ri javob matni"),
        max_length=500,
        blank=True,
        help_text=_(
            "Matnli javob savollari uchun — kutilayotgan javob (katta-kichik harf farqi hisobga olinmaydi)."
        ),
    )
    points = models.PositiveIntegerField(
        _("ball"),
        default=1,
        validators=[MinValueValidator(1)],
    )
    explanation = models.TextField(
        _("tushuntirish"),
        blank=True,
        help_text=_("Javob topshirilgandan keyin ko'rsatiladi."),
    )
    position = models.PositiveIntegerField(_("tartib raqami"), default=0)
    config = models.JSONField(
        _("sozlama"),
        default=dict,
        blank=True,
        help_text=_(
            "Ixtiyoriy: partial_credit (gap/matching qisman ball), "
            "case_sensitive, min_words/max_words (written yo'riqnoma)."
        ),
    )

    class Meta:
        verbose_name = _("Savol")
        verbose_name_plural = _("Savollar")
        ordering = ["position"]
        indexes = [
            models.Index(fields=["test", "position"], name="idx_question_test_pos"),
            models.Index(fields=["section", "position"], name="idx_question_sect_pos"),
            models.Index(fields=["reading_passage"], name="idx_question_passage"),
        ]

    def __str__(self) -> str:
        short = self.text[:60]
        return f"Q{self.position}: {short}…"


# ---------------------------------------------------------------------------
# Choice  (answer options for a question)
# ---------------------------------------------------------------------------
class Choice(models.Model):
    """
    A single answer option for a Question.

    The instructor creates 2–6 choices per question and marks one (or more
    for multi-choice) as correct via `Question.correct_option` FK.
    """

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="choices",
        verbose_name=_("savol"),
    )
    text = models.CharField(_("javob varianti"), max_length=500)
    is_correct = models.BooleanField(_("to'g'ri javobmi"), default=False)
    position = models.PositiveIntegerField(_("tartib raqami"), default=0)

    class Meta:
        verbose_name = _("Variant")
        verbose_name_plural = _("Variantlar")
        ordering = ["position"]
        unique_together = ("question", "text")

    def __str__(self) -> str:
        return f"[{'✓' if self.is_correct else '✗'}] {self.text}"


# ---------------------------------------------------------------------------
# TestAttempt  (a student's session taking a test)
# ---------------------------------------------------------------------------
class TestAttempt(models.Model):
    """
    Records one attempt by a student on a test.

    Lifecycle:
        1. Student clicks "Start test" → Attempt created (status=IN_PROGRESS).
        2. Student submits answers → status=COMPLETED.
        3. If time runs out → Celery beat or submit handler sets TIMEOUT.

    `started_at` / `completed_at` let us enforce `time_limit_minutes`.
    """

    __test__ = False

    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", _("Davom etmoqda")
        COMPLETED = "completed", _("Tugallangan")
        TIMEOUT = "timeout", _("Vaqt tugadi")
        CANCELLED = "cancelled", _("Bekor qilingan")
        PENDING_GRADING = "pending_grading", _("Baholanmoqda (yozma kutilmoqda)")

    # Attempt lifecycle (single source of truth):
    #   IN_PROGRESS → COMPLETED | TIMEOUT | PENDING_GRADING | CANCELLED
    #   PENDING_GRADING → COMPLETED (finalize, idempotent)
    # Terminal: COMPLETED, TIMEOUT, CANCELLED (no transitions out).
    STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
        Status.IN_PROGRESS: frozenset(
            {
                Status.COMPLETED,
                Status.TIMEOUT,
                Status.PENDING_GRADING,
                Status.CANCELLED,
            }
        ),
        Status.PENDING_GRADING: frozenset({Status.COMPLETED}),
        Status.COMPLETED: frozenset(),
        Status.TIMEOUT: frozenset(),
        Status.CANCELLED: frozenset(),
    }

    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name="attempts",
        verbose_name=_("test"),
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="test_attempts",
        verbose_name=_("o'quvchi"),
    )
    status = models.CharField(
        _("holat"),
        max_length=20,
        choices=Status.choices,
        default=Status.IN_PROGRESS,
    )

    # -- Timing ---------------------------------------------------------------
    started_at = models.DateTimeField(_("boshlangan"), auto_now_add=True)
    completed_at = models.DateTimeField(
        _("tugallangan"),
        null=True,
        blank=True,
    )

    # -- Scoring (denormalized for fast reads) --------------------------------
    score = models.DecimalField(
        _("yig'indi ball"),
        max_digits=7,
        decimal_places=2,
        default=0,
    )
    percentage = models.DecimalField(
        _("foiz"),
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    is_passed = models.BooleanField(_("o'tdimi"), default=False)

    # -- Anti-cheat (Strict Exam Mode) ----------------------------------------
    violation_count = models.PositiveSmallIntegerField(
        _("qoidabuzarliklar soni (tab switch)"),
        default=0,
    )
    cheating_detected = models.BooleanField(
        _("ko'chirishga urinish qayd etildimi"),
        default=False,
        db_index=True,
    )
    violation_logs = models.JSONField(
        _("qoidabuzarliklar tarixi"),
        default=list,
        blank=True,
    )

    class Meta:
        verbose_name = _("Test urinishi")
        verbose_name_plural = _("Test urinishlari")
        ordering = ["-started_at"]
        # NOTE: unique_together removed — business logic enforces max_attempts.
        constraints = [
            # One active attempt per (test, student) — enforced at DB level so
            # concurrent start requests cannot create duplicates. Application
            # checks remain for friendly errors; this is the safety net.
            models.UniqueConstraint(
                fields=["test", "student"],
                condition=models.Q(status="in_progress"),
                name="uniq_attempt_test_student_in_progress",
            ),
        ]
        indexes = [
            models.Index(fields=["test", "student"], name="idx_attempt_test_student"),
            models.Index(fields=["status"], name="idx_attempt_status"),
            # Composite: timeout checker + dashboard queries
            models.Index(
                fields=["status", "student", "started_at"],
                name="idx_att_status_stu_time",
            ),
            # Composite: active attempt lookup
            models.Index(
                fields=["test", "student", "status"],
                name="idx_att_test_stu_status",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.student} — {self.test} [{self.get_status_display()}]"

    # -- Business helpers -----------------------------------------------------
    @property
    def is_time_expired(self) -> bool:
        """Check if the allowed time has elapsed."""
        if not self.test.has_time_limit:
            return False
        deadline = self.started_at + timezone.timedelta(
            minutes=self.test.time_limit_minutes
        )
        return timezone.now() > deadline

    @property
    def remaining_seconds(self) -> int | None:
        """Seconds left for this attempt, or None if no time limit."""
        if not self.test.has_time_limit:
            return None
        deadline = self.started_at + timezone.timedelta(
            minutes=self.test.time_limit_minutes
        )
        delta = deadline - timezone.now()
        return max(0, int(delta.total_seconds()))


# ---------------------------------------------------------------------------
# StudentAnswer  (individual answer to a question within an attempt)
# ---------------------------------------------------------------------------
class StudentAnswer(models.Model):
    """
    Records which choice(s) a student selected for a specific question
    during a specific attempt.

    For `single` questions, exactly one choice is FK'd.
    For `multiple` questions, a comma-separated string of choice IDs is stored
    in `selected_choices_raw` — or better, use the M2M below.

    Using a separate model (instead of JSON) makes analytics queries trivial.
    """

    attempt = models.ForeignKey(
        TestAttempt,
        on_delete=models.CASCADE,
        related_name="answers",
        verbose_name=_("urinish"),
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="student_answers",
        verbose_name=_("savol"),
    )
    selected_choices = models.ManyToManyField(
        Choice,
        related_name="selected_by",
        blank=True,
        verbose_name=_("tanlangan variantlar"),
    )
    text_answer = models.CharField(
        _("matnli javob"),
        max_length=500,
        blank=True,
        help_text=_("Matnli javob savollari uchun o'quvchining kiritgan matni."),
    )
    written_text = models.TextField(
        _("yozma ish matni"),
        blank=True,
        default="",
        help_text=_(
            "WRITTEN savol qoralamasi (autosave). Baholash esse dvigateli orqali."
        ),
    )
    written_word_count = models.PositiveIntegerField(
        _("yozma so'zlar soni"),
        default=0,
    )
    is_correct = models.BooleanField(
        _("to'g'rimi"),
        null=True,
        blank=True,
        help_text=_("Tekshirilgandan keyin o'rnatiladi."),
    )
    answered_at = models.DateTimeField(_("javob berilgan"), auto_now=True)

    class Meta:
        verbose_name = _("O'quvchi javobi")
        verbose_name_plural = _("O'quvchi javoblari")
        unique_together = ("attempt", "question")
        indexes = [
            models.Index(
                fields=["attempt", "question"],
                name="idx_answer_attempt_q",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.attempt} — Q{self.question.position}"

    class Meta:
        verbose_name = _("O'quvchi javobi")
        verbose_name_plural = _("O'quvchi javoblari")
        unique_together = ("attempt", "question")
        indexes = [
            models.Index(
                fields=["attempt", "question"],
                name="idx_answer_attempt_q",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.attempt} — Q{self.question.position}"


# ---------------------------------------------------------------------------
# GapBlank  (bitta bo'shliq — bir nechta qabul javobi)
# ---------------------------------------------------------------------------
class GapBlank(models.Model):
    """
    One blank inside a GAP_FILL question. Several rows may share the same
    position — each row is one accepted answer for that blank.
    """

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="gap_blanks",
        verbose_name=_("savol"),
    )
    position = models.PositiveIntegerField(
        _("bo'shliq tartibi"),
        default=0,
        help_text=_("Matndagi ___ markerlar ketma-ketligi (0 dan boshlanadi)."),
    )
    answer_text = models.CharField(
        _("qabul javob"),
        max_length=200,
        help_text=_("Bitta qabul qilinadigan javob varianti."),
    )

    class Meta:
        verbose_name = _("Bo'shliq javobi")
        verbose_name_plural = _("Bo'shliq javoblari")
        ordering = ["position"]
        indexes = [
            models.Index(fields=["question", "position"], name="idx_gap_q_pos"),
        ]

    def __str__(self) -> str:
        return f"Q{self.question_id}[{self.position}]: {self.answer_text}"


class GapResponse(models.Model):
    """Student's response for one blank (upsert by answer+blank)."""

    answer = models.ForeignKey(
        StudentAnswer,
        on_delete=models.CASCADE,
        related_name="gap_responses",
        verbose_name=_("javob"),
    )
    blank_position = models.PositiveIntegerField(_("bo'shliq tartibi"))
    response_text = models.CharField(_("o'quvchi javobi"), max_length=200, blank=True)

    class Meta:
        verbose_name = _("Bo'shliq javobi (o'quvchi)")
        verbose_name_plural = _("Bo'shliq javoblari (o'quvchi)")
        unique_together = ("answer", "blank_position")

    def __str__(self) -> str:
        return f"A{self.answer_id}[{self.blank_position}]: {self.response_text}"


# ---------------------------------------------------------------------------
# Matching  (prompt ↔ option, to'g'ri bog'lanish alohida)
# ---------------------------------------------------------------------------
class MatchingPrompt(models.Model):
    """Left side of a matching pair (numbered, deterministic order)."""

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="matching_prompts",
        verbose_name=_("savol"),
    )
    text = models.CharField(_("so'rov matni"), max_length=500)
    position = models.PositiveIntegerField(_("tartib"), default=0)

    class Meta:
        verbose_name = _("Moslashtirish so'rovi")
        verbose_name_plural = _("Moslashtirish so'rovlari")
        ordering = ["position"]
        indexes = [
            models.Index(fields=["question", "position"], name="idx_mprompt_q_pos"),
        ]

    def __str__(self) -> str:
        return f"Q{self.question_id} P{self.position}: {self.text[:40]}"


class MatchingOption(models.Model):
    """Right side of a matching pair (stable id, display order shufflable)."""

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="matching_options",
        verbose_name=_("savol"),
    )
    text = models.CharField(_("variant matni"), max_length=500)
    position = models.PositiveIntegerField(_("tartib"), default=0)

    class Meta:
        verbose_name = _("Moslashtirish varianti")
        verbose_name_plural = _("Moslashtirish variantlari")
        ordering = ["position"]
        indexes = [
            models.Index(fields=["question", "position"], name="idx_mopt_q_pos"),
        ]

    def __str__(self) -> str:
        return f"Q{self.question_id} O{self.position}: {self.text[:40]}"


class MatchingPair(models.Model):
    """Correct mapping: prompt → option (answer key, never sent to students)."""

    prompt = models.OneToOneField(
        MatchingPrompt,
        on_delete=models.CASCADE,
        related_name="correct_pair",
        verbose_name=_("so'rov"),
    )
    correct_option = models.ForeignKey(
        MatchingOption,
        on_delete=models.CASCADE,
        related_name="correct_for",
        verbose_name=_("to'g'ri variant"),
    )

    class Meta:
        verbose_name = _("To'g'ri moslik")
        verbose_name_plural = _("To'g'ri mosliklar")

    def __str__(self) -> str:
        return f"P{self.prompt_id} → O{self.correct_option_id}"


class MatchingResponse(models.Model):
    """Student's mapping for one prompt (upsert by answer+prompt)."""

    answer = models.ForeignKey(
        StudentAnswer,
        on_delete=models.CASCADE,
        related_name="matching_responses",
        verbose_name=_("javob"),
    )
    prompt = models.ForeignKey(
        MatchingPrompt,
        on_delete=models.CASCADE,
        related_name="responses",
        verbose_name=_("so'rov"),
    )
    selected_option = models.ForeignKey(
        MatchingOption,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("tanlangan variant"),
    )

    class Meta:
        verbose_name = _("Moslik javobi (o'quvchi)")
        verbose_name_plural = _("Moslik javoblari (o'quvchi)")
        unique_together = ("answer", "prompt")

    def __str__(self) -> str:
        return f"A{self.answer_id} P{self.prompt_id} → O{self.selected_option_id}"


# ---------------------------------------------------------------------------
# ExamWrittenBridge  (TestAttempt/answer ↔ canonical EssaySubmission)
# ---------------------------------------------------------------------------
class ExamWrittenBridge(models.Model):
    """
    Idempotent link between an exam WRITTEN answer and the ONE canonical
    essay submission that grades it. The essay engine stays the single
    source of truth — no grading is duplicated inside apps/tests.
    """

    attempt = models.ForeignKey(
        TestAttempt,
        on_delete=models.CASCADE,
        related_name="written_bridges",
        verbose_name=_("urinish"),
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="written_bridges",
        verbose_name=_("savol"),
    )
    answer = models.OneToOneField(
        StudentAnswer,
        on_delete=models.CASCADE,
        related_name="written_bridge",
        verbose_name=_("javob"),
    )
    essay_submission = models.OneToOneField(
        "essays.EssaySubmission",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exam_bridge",
        verbose_name=_("esse topshirig'i"),
    )
    rubric_version = models.CharField(
        _("rubrika versiyasi"),
        max_length=40,
        blank=True,
        default="",
    )
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)

    class Meta:
        verbose_name = _("Yozma ko'prik (imtihon→esse)")
        verbose_name_plural = _("Yozma ko'priklar (imtihon→esse)")
        unique_together = ("attempt", "question")
        indexes = [
            models.Index(fields=["attempt", "question"], name="idx_bridge_att_q"),
        ]

    def __str__(self) -> str:
        return f"Bridge A{self.attempt_id} Q{self.question_id} → E{self.essay_submission_id}"


# ---------------------------------------------------------------------------
# AttemptSectionProgress  (bo'lim vaqti server-side)
# ---------------------------------------------------------------------------
class AttemptSectionProgress(models.Model):
    """Per-section timer state for one attempt (server is the authority)."""

    attempt = models.ForeignKey(
        TestAttempt,
        on_delete=models.CASCADE,
        related_name="section_progress",
        verbose_name=_("urinish"),
    )
    section = models.ForeignKey(
        ExamSection,
        on_delete=models.CASCADE,
        related_name="attempt_progress",
        verbose_name=_("bo'lim"),
    )
    started_at = models.DateTimeField(_("boshlangan"), auto_now_add=True)
    completed_at = models.DateTimeField(
        _("tugallangan"),
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = _("Bo'lim jarayoni")
        verbose_name_plural = _("Bo'lim jarayonlari")
        unique_together = ("attempt", "section")

    @property
    def is_expired(self) -> bool:
        """True when the section's own duration has elapsed."""
        if not self.section.duration_minutes:
            return False
        if self.completed_at:
            return True
        deadline = self.started_at + timezone.timedelta(
            minutes=self.section.duration_minutes
        )
        return timezone.now() > deadline

    @property
    def remaining_seconds(self) -> int | None:
        """Seconds left in this section, or None when untimed."""
        if not self.section.duration_minutes:
            return None
        if self.completed_at:
            return 0
        deadline = self.started_at + timezone.timedelta(
            minutes=self.section.duration_minutes
        )
        return max(0, int((deadline - timezone.now()).total_seconds()))

    def __str__(self) -> str:
        return f"A{self.attempt_id} S{self.section_id}"


# ---------------------------------------------------------------------------
# ExamScoringProfile  (konfiguratsiya; rasmiy qiymatlar EMAS)
# ---------------------------------------------------------------------------
class ExamScoringProfile(models.Model):
    """
    Configurable aggregate scoring profile.

    Weights/thresholds are DATA, not code — no official Uzbek scoring
    coefficients are hardcoded anywhere. A Result pins the profile+version
    it was computed with so future rule changes never rewrite history.
    """

    name = models.CharField(_("nom"), max_length=120)
    version = models.CharField(_("versiya"), max_length=40)
    is_active = models.BooleanField(_("faolmi"), default=True)
    is_verified = models.BooleanField(
        _("tasdiqlanganmi"),
        default=False,
        help_text=_(
            "Faqat tasdiqlangan profil rasmiy sertifikat huquqini beradi. "
            "Tasdiqlanmagan profil bilan ballar hisoblanadi, lekin sertifikat "
            "berilmaydi (placeholder 60 ham ishlamaydi)."
        ),
    )
    weights = models.JSONField(
        _("bo'lim vaznlari"),
        default=dict,
        blank=True,
        help_text=_('Masalan: {"READING": 1, "WRITING": 2}. Bo\'sh = teng vazn.'),
    )
    certificate_min_percentage = models.PositiveIntegerField(
        _("sertifikat minimal foizi"),
        default=60,
    )
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)

    class Meta:
        verbose_name = _("Skoring profili")
        verbose_name_plural = _("Skoring profillari")
        unique_together = ("name", "version")
        ordering = ["-created_at"]

    def weight_for(self, section_code: str) -> float:
        """Weight for a section code; 1.0 when unconfigured (equal weights)."""
        try:
            return float(self.weights.get(section_code, 1))
        except (TypeError, ValueError):
            return 1.0

    def __str__(self) -> str:
        return f"{self.name} {self.version}"
