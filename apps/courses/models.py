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
    name = models.CharField(_("guruh nomi"), max_length=150)
    description = models.TextField(_("tavsif"), blank=True)
    students = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="student_groups",
        blank=True,
        verbose_name=_("talabalar"),
    )
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    updated_at = models.DateTimeField(_("yangilangan"), auto_now=True)

    class Meta:
        verbose_name = _("Guruh")
        verbose_name_plural = _("Guruhlar")
        ordering = ["name"]
        unique_together = ("teacher", "name")  # bir o'qituvchida bir xil nomli guruh bo'lmasin

    def __str__(self) -> str:
        return f"{self.name} ({self.teacher.get_full_name()})"

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
