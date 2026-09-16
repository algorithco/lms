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

    class Difficulty(models.TextChoices):
        EASY = "easy", _("Oson")
        MEDIUM = "medium", _("O'rta")
        HARD = "hard", _("Qiyin")

    class Status(models.TextChoices):
        DRAFT = "draft", _("Qoralama")
        PUBLISHED = "published", _("E'lon qilingan")
        ARCHIVED = "archived", _("Arxivlangan")

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
        help_text=_("Qoralama — o'quvchilarga ko'rinmaydi; E'lon qilingan — ochiq; Arxivlangan — yashirin."),
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
        return self.questions.aggregate(
            total=models.Sum("points")
        )["total"] or 0

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
# Question
# ---------------------------------------------------------------------------
class Question(models.Model):
    """
    A single question inside a test.

    `correct_option` — FK to the correct Choice. Set by the instructor.
    `points`         — weight for this question in scoring.
    `explanation`    — shown after submission (if `show_results_immediately`).
    """

    class QuestionType(models.TextChoices):
        SINGLE_CHOICE = "single", _("Bita to'g'ri javob")
        MULTIPLE_CHOICE = "multiple", _("Ko'p to'g'ri javob")
        TEXT_MATCH = "text", _("Matnli javob")

    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name="questions",
        verbose_name=_("test"),
    )
    passage = models.TextField(
        _("kontekst matni (passage)"),
        blank=True,
        help_text=_("Savol ustida ko'rsatiladigan matn/parcha (matnli tahlil savollari uchun)."),
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
        help_text=_("Matnli javob savollari uchun — kutilayotgan javob (katta-kichik harf farqi hisobga olinmaydi)."),
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

    class Meta:
        verbose_name = _("Savol")
        verbose_name_plural = _("Savollar")
        ordering = ["position"]
        indexes = [
            models.Index(fields=["test", "position"], name="idx_question_test_pos"),
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

    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", _("Davom etmoqda")
        COMPLETED = "completed", _("Tugallangan")
        TIMEOUT = "timeout", _("Vaqt tugadi")
        CANCELLED = "cancelled", _("Bekor qilingan")

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

    class Meta:
        verbose_name = _("Test urinishi")
        verbose_name_plural = _("Test urinishlari")
        ordering = ["-started_at"]
        # NOTE: unique_together removed — business logic enforces max_attempts.
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
