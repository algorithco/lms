"""
Courses app — Category, Course, Module, Lesson.

Hierarchy:
    Category  1 ──► * Course  1 ──► * Module  1 ──► * Lesson

A Course belongs to a teacher (User with role=TEACHER).
Modules and Lessons are ordered via `position` so instructors can drag/reorder.
"""

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from apps.core.validators import validate_attachment_upload, validate_image_upload


# ---------------------------------------------------------------------------
# Subject (Multi-Subject Architecture: uzbek / english)
# ---------------------------------------------------------------------------
class Subject(models.Model):
    """
    Platform subject/direction (Ona tili va adabiyot, Ingliz tili: IELTS / Multi-level).
    """

    class SlugChoices(models.TextChoices):
        UZBEK = "uzbek", _("Ona tili va adabiyot")
        ENGLISH = "english", _("Ingliz tili (IELTS & Multi-level)")

    name = models.CharField(_("fan nomi"), max_length=120)
    slug = models.SlugField(_("slug"), max_length=50, unique=True, db_index=True)
    description = models.TextField(_("tavsif"), blank=True)
    icon = models.CharField(
        _("ikonka / bayroq"), max_length=32, default="🇺🇿", blank=True
    )
    is_active = models.BooleanField(_("faolmi"), default=True)
    position = models.PositiveSmallIntegerField(_("tartib"), default=0)
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)

    class Meta:
        verbose_name = _("Fan / Yo'nalish")
        verbose_name_plural = _("Fanlar / Yo'nalishlar")
        ordering = ["position", "name"]

    def __str__(self) -> str:
        return f"{self.icon} {self.name}".strip()


# ---------------------------------------------------------------------------
# Category  (self-referential tree, e.g. "Backend → Django → REST API")
# ---------------------------------------------------------------------------
class Category(models.Model):
    """
    Hierarchical course category.

    `parent` allows arbitrary nesting — one level deep is recommended
    for UX, but the model supports deeper trees if needed.
    """

    name = models.CharField(_("nomi"), max_length=150, unique=True)
    slug = models.SlugField(_("slug"), max_length=160, unique=True, blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        verbose_name=_("ota kategoriya"),
    )
    description = models.TextField(_("tavsif"), blank=True)
    icon = models.CharField(
        _("ikonka (CSS class)"),
        max_length=50,
        blank=True,
        help_text=_("Bootstrap Icons yoki boshqa CSS klass nomi."),
    )

    class Meta:
        verbose_name = _("Kategoriya")
        verbose_name_plural = _("Kategoriyalar")
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# Course
# ---------------------------------------------------------------------------
class Course(models.Model):
    """
    The main teachable unit.

    Fields:
        teacher      — FK to User (role=teacher enforced in serializer/view).
        title/slug   — human-readable identifier + URL-safe slug.
        category     — which Category this course belongs to.
        is_published — draft ↔ live toggle.
        price        — 0 = free course.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", _("Qoralama")
        PUBLISHED = "published", _("Nashr etilgan")
        ARCHIVED = "archived", _("Arxivlangan")

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="courses_taught",
        verbose_name=_("o'qituvchi"),
    )
    subject = models.CharField(
        _("fan / yo'nalish"),
        max_length=20,
        choices=Subject.SlugChoices.choices,
        default=Subject.SlugChoices.UZBEK,
        db_index=True,
    )
    title = models.CharField(_("sarlavha"), max_length=255)
    slug = models.SlugField(_("slug"), max_length=280, unique=True, blank=True)
    description = models.TextField(_("tavsif"))
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="courses",
        verbose_name=_("kategoriya"),
    )
    thumbnail = models.ImageField(
        _("kichik rasm"),
        upload_to="courses/thumbnails/%Y/%m/",
        blank=True,
        null=True,
        validators=[validate_image_upload],
    )
    status = models.CharField(
        _("holat"),
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    price = models.DecimalField(
        _("narx"),
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    max_students = models.PositiveIntegerField(
        _("maksimal o'quvchilar soni"),
        null=True,
        blank=True,
        help_text=_("Cheksiz bo'lsa, bo'sh qoldiring."),
    )

    # -- Enrollment (M2M via intermediary) ------------------------------------
    enrolled_students = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="Enrollment",
        related_name="courses_enrolled",
        blank=True,
        verbose_name=_("yozilgan o'quvchilar"),
    )

    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    updated_at = models.DateTimeField(_("yangilangan"), auto_now=True)

    class Meta:
        verbose_name = _("Kurs")
        verbose_name_plural = _("Kurslar")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"], name="idx_course_status"),
            models.Index(fields=["teacher"], name="idx_course_teacher"),
            models.Index(fields=["subject"], name="idx_course_subject"),
        ]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    @property
    def is_published(self) -> bool:
        return self.status == self.Status.PUBLISHED

    @property
    def total_modules(self) -> int:
        return self.modules.count()


# ---------------------------------------------------------------------------
# Enrollment  (through model for Course ↔ Student M2M)
# ---------------------------------------------------------------------------
class Enrollment(models.Model):
    """
    Through model: records which student enrolled in which course, and when.

    Using an explicit through model (instead of bare M2M) lets us add
    `enrolled_at`, `is_completed`, and later certificate references.
    """

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="enrollments",
        verbose_name=_("o'quvchi"),
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="enrollments",
        verbose_name=_("kurs"),
    )
    enrolled_at = models.DateTimeField(_("yozilgan sana"), auto_now_add=True)
    is_completed = models.BooleanField(_("tugatilgan"), default=False)

    class Meta:
        verbose_name = _("Yozilish")
        verbose_name_plural = _("Yozilishlar")
        unique_together = ("student", "course")  # a student can enroll once
        ordering = ["-enrolled_at"]

    def __str__(self) -> str:
        return f"{self.student} → {self.course}"


def generate_invite_token() -> str:
    import secrets

    return secrets.token_urlsafe(16)


# ---------------------------------------------------------------------------
# StudentGroup  (teacher's class groups)
# ---------------------------------------------------------------------------
class StudentGroup(models.Model):
    """
    Guruh — o'qituvchi talabalarni guruhlarga ajratadi.
    Masalan: "9-A sinf", "10-B sinf", "Adabiyot guruhi".
    """

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="managed_groups",
        verbose_name=_("o'qituvchi"),
    )
    subject = models.CharField(
        _("fan / yo'nalish"),
        max_length=20,
        choices=Subject.SlugChoices.choices,
        default=Subject.SlugChoices.UZBEK,
        db_index=True,
    )
    name = models.CharField(_("guruh nomi"), max_length=150)
    description = models.TextField(_("tavsif"), blank=True)
    students = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="student_groups",
        blank=True,
        verbose_name=_("talabalar"),
    )
    invite_code = models.CharField(
        _("taklif kodi"),
        max_length=32,
        blank=True,
        null=True,
        unique=True,
        db_index=True,
        help_text=_("O'quvchilar qo'shilishi uchun unikal kod (masalan: GR-101)"),
    )
    invite_token = models.CharField(
        _("taklif tokeni"),
        max_length=64,
        blank=True,
        null=True,
        unique=True,
        db_index=True,
        help_text=_("Guruhga 1-klikda qo'shilish uchun xavfsiz unikal havola tokeni"),
    )
    monthly_fee = models.PositiveIntegerField(
        _("oylik to'lov (so'm)"),
        default=400000,
        help_text=_("O'quvchilar uchun oylik to'lov summasi."),
    )
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    updated_at = models.DateTimeField(_("yangilangan"), auto_now=True)

    class Meta:
        verbose_name = _("Guruh")
        verbose_name_plural = _("Guruhlar")
        ordering = ["name"]
        unique_together = (
            "teacher",
            "name",
        )  # bir o'qituvchida bir xil nomli guruh bo'lmasin

    def __str__(self) -> str:
        return f"{self.name} ({self.teacher.get_full_name()})"

    def save(self, *args, **kwargs) -> None:
        import secrets

        if not self.invite_code:
            self.invite_code = f"GR-{secrets.token_hex(3).upper()}"
        if not self.invite_token:
            self.invite_token = generate_invite_token()
        super().save(*args, **kwargs)

    @property
    def student_count(self) -> int:
        return self.students.count()


# ---------------------------------------------------------------------------
# Module  (a logical section inside a course)
# ---------------------------------------------------------------------------
class Module(models.Model):
    """
    Logical grouping inside a course (e.g. "Chapter 1: Basics").

    `position` controls display order; use it for drag-and-drop reordering.
    """

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="modules",
        verbose_name=_("kurs"),
    )
    title = models.CharField(_("sarlavha"), max_length=255)
    description = models.TextField(_("tavsif"), blank=True)
    position = models.PositiveIntegerField(_("tartib raqami"), default=0)

    class Meta:
        verbose_name = _("Modul")
        verbose_name_plural = _("Modullar")
        ordering = ["position"]
        unique_together = ("course", "title")

    def __str__(self) -> str:
        return f"{self.course.title} — {self.title}"


# ---------------------------------------------------------------------------
# Lesson  (individual content unit inside a module)
# ---------------------------------------------------------------------------
class Lesson(models.Model):
    """
    Atomic content unit — text, video link, or file.

    `content_type` helps the frontend decide how to render:
        text   → rich HTML content in `content_body`
        video  → embed URL in `content_url`
        file   → uploaded file in `attachment`
    """

    class ContentType(models.TextChoices):
        TEXT = "text", _("Matn")
        VIDEO = "video", _("Video")
        FILE = "file", _("Fayl")

    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name="lessons",
        verbose_name=_("modul"),
    )
    title = models.CharField(_("sarlavha"), max_length=255)
    content_type = models.CharField(
        _("kontent turi"),
        max_length=10,
        choices=ContentType.choices,
        default=ContentType.TEXT,
    )
    content_body = models.TextField(_("matn kontenti"), blank=True)
    content_url = models.URLField(
        _("video/link URL"),
        blank=True,
        help_text=_("Video embed URL yoki tashqi havola."),
    )
    attachment = models.FileField(
        _("ilova fayl"),
        upload_to="lessons/attachments/%Y/%m/",
        blank=True,
        null=True,
        validators=[validate_attachment_upload],
    )
    position = models.PositiveIntegerField(_("tartib raqami"), default=0)
    is_free = models.BooleanField(
        _("bepul ko'rish mumkinmi"),
        default=False,
        help_text=_("Ro'yxatdan o'tmasdan ko'rishga ruxsat."),
    )

    class Meta:
        verbose_name = _("Dars")
        verbose_name_plural = _("Darslar")
        ordering = ["position"]
        unique_together = ("module", "title")

    def __str__(self) -> str:
        return f"{self.module} — {self.title}"


# ---------------------------------------------------------------------------
# Homework (Uyga vazifa tizimi)
# ---------------------------------------------------------------------------
class Homework(models.Model):
    """
    Ustoz tomonidan guruhga berilgan uyga vazifa (Test yoki Esse).
    """

    group = models.ForeignKey(
        StudentGroup,
        on_delete=models.CASCADE,
        related_name="homeworks",
        verbose_name=_("guruh"),
    )
    title = models.CharField(_("vazifa sarlavhasi"), max_length=200)
    description = models.TextField(_("tavsif va ko'rsatmalar"), blank=True)
    test = models.ForeignKey(
        "tests.Test",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="homework_assignments",
        verbose_name=_("biriktirilgan test"),
    )
    essay_topic = models.ForeignKey(
        "essays.EssayTopic",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="homework_assignments",
        verbose_name=_("biriktirilgan esse mavzusi"),
    )
    due_date = models.DateTimeField(
        _("topshirish muddati (deadline)"),
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_homeworks",
    )
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    updated_at = models.DateTimeField(_("yangilangan"), auto_now=True)

    class Meta:
        verbose_name = _("Uyga vazifa")
        verbose_name_plural = _("Uyga vazifalar")
        ordering = ["-due_date", "-created_at"]

    def __str__(self) -> str:
        return f"{self.group.name}: {self.title} (Muddat: {self.due_date})"


class HomeworkSubmission(models.Model):
    """
    O'quvchining uyga vazifani bajarganlik holati.
    """

    homework = models.ForeignKey(
        Homework,
        on_delete=models.CASCADE,
        related_name="submissions",
        verbose_name=_("uyga vazifa"),
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="homework_submissions",
        verbose_name=_("o'quvchi"),
    )
    is_completed = models.BooleanField(_("bajarildimi"), default=False, db_index=True)
    completed_at = models.DateTimeField(_("bajarilgan vaqt"), null=True, blank=True)
    score_display = models.CharField(_("natija"), max_length=50, blank=True)
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)

    class Meta:
        verbose_name = _("Vazifa bajarilishi")
        verbose_name_plural = _("Vazifa bajarilishlari")
        unique_together = ("homework", "student")

    def __str__(self) -> str:
        status = "Bajarildi" if self.is_completed else "Bajarilmadi"
        return f"{self.student_id} — {self.homework_id} ({status})"


# ---------------------------------------------------------------------------
# GroupEnrollment (Guruh a'zoligi, kurs to'lovlari grafigi & CRM)
# ---------------------------------------------------------------------------
class GroupEnrollment(models.Model):
    """
    Guruh a'zoligi va kurs to'lovlari grafigi (Ustozlar Mini CRM).
    O'quvchining oylik kurs to'lovi, to'lov kuni va ota-onasi bilan bog'lanish.
    """

    class PaymentStatus(models.TextChoices):
        PAID = "paid", _("To'langan")
        DUE_SOON = "due_soon", _("To'lov yaqin")
        OVERDUE = "overdue", _("Muddati o'tgan")
        GRACE_PERIOD = "grace_period", _("Imtiyozli davr")

    group = models.ForeignKey(
        StudentGroup,
        on_delete=models.CASCADE,
        related_name="group_enrollments",
        verbose_name=_("guruh"),
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_group_enrollments",
        verbose_name=_("o'quvchi"),
    )
    monthly_fee = models.DecimalField(
        _("oylik to'lov (so'm)"),
        max_digits=12,
        decimal_places=2,
        default=400000.00,
        help_text=_("O'quvchi uchun kelishilgan oylik to'lov summasi."),
    )
    billing_cycle_day = models.PositiveSmallIntegerField(
        _("oylik to'lov kuni"),
        default=10,
        help_text=_("Har oyning to'lov kuni (1–31)."),
    )
    last_payment_date = models.DateField(
        _("oxirgi to'lov sanasi"),
        null=True,
        blank=True,
    )
    next_payment_due = models.DateField(
        _("keyingi to'lov muddati"),
        null=True,
        blank=True,
        db_index=True,
    )
    payment_status = models.CharField(
        _("to'lov holati"),
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PAID,
        db_index=True,
    )
    parent_telegram_id = models.CharField(
        _("ota-ona Telegram ID"),
        max_length=64,
        blank=True,
        default="",
        help_text=_("Ota-onaning Telegram hisob identifikatori."),
    )
    parent_phone = models.CharField(
        _("ota-ona telefoni"),
        max_length=32,
        blank=True,
        default="",
        help_text=_("Ota-onaning aloqa telefoni."),
    )
    is_active = models.BooleanField(_("faolmi"), default=True)
    joined_at = models.DateTimeField(_("qo'shilgan vaqti"), auto_now_add=True)
    updated_at = models.DateTimeField(_("yangilangan"), auto_now=True)

    class Meta:
        verbose_name = _("Guruh a'zoligi va to'lov grafigi")
        verbose_name_plural = _("Guruh a'zoliklari va to'lov grafiki")
        unique_together = ("group", "student")
        ordering = ["-joined_at"]

    def __str__(self) -> str:
        return f"{self.student.get_full_name()} @ {self.group.name} ({self.payment_status})"

    def record_payment(self, amount=None, payment_date=None, extend_days=30):
        from datetime import timedelta
        from django.utils import timezone

        p_date = payment_date or timezone.localdate()
        self.last_payment_date = p_date
        base_date = max(p_date, self.next_payment_due or p_date)
        self.next_payment_due = base_date + timedelta(days=extend_days)
        self.payment_status = self.PaymentStatus.PAID
        self.save(
            update_fields=[
                "last_payment_date",
                "next_payment_due",
                "payment_status",
                "updated_at",
            ]
        )

    def update_status(self, today=None):
        from django.utils import timezone

        today = today or timezone.localdate()
        if not self.next_payment_due:
            return self.payment_status
        if self.next_payment_due < today:
            self.payment_status = self.PaymentStatus.OVERDUE
        elif (self.next_payment_due - today).days <= 3:
            self.payment_status = self.PaymentStatus.DUE_SOON
        else:
            self.payment_status = self.PaymentStatus.PAID
        self.save(update_fields=["payment_status", "updated_at"])
        return self.payment_status
