"""Admin configuration for courses app."""
from django.contrib import admin

from .models import Category, Course, Enrollment, Lesson, Module, StudentGroup


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "slug")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


class ModuleInline(admin.TabularInline):
    model = Module
    extra = 0
    ordering = ["position"]


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "teacher", "status", "category", "price", "created_at")
    list_filter = ("status", "category")
    search_fields = ("title", "teacher__email")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [ModuleInline]


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("student", "course", "enrolled_at", "is_completed")
    list_filter = ("is_completed",)


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "position")
    list_filter = ("course",)


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("title", "module", "content_type", "position", "is_free")
    list_filter = ("content_type", "is_free")


@admin.register(StudentGroup)
class StudentGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "teacher", "student_count", "created_at")
    list_filter = ("teacher",)
    search_fields = ("name", "teacher__email")
    filter_horizontal = ("students",)
