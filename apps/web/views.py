"""
Web views — Minimal views kept for backward compatibility with tests
and legacy flows. All page rendering is now handled by the React SPA.
These views serve the baked SPA shell so that direct navigation works.
"""
from __future__ import annotations

import logging
from urllib.parse import urlsplit
from typing import Any

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView,
)
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ImproperlyConfigured
from django.utils.crypto import salted_hmac
from django.db.models import Avg, Case, Count, F, FloatField, Max, Q, Sum, Value, When
from django.db.models.functions import Coalesce, ExtractHour
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST
from django.utils.decorators import method_decorator
from django.views import View

from apps.courses.models import Course, StudentGroup
from apps.essays.models import EssaySubmission, EssayCriterionScore
from apps.results.models import Certificate, Result
from apps.tests.models import Test, TestAttempt
from apps.core.spa import serve_spa_shell

User = get_user_model()
logger = logging.getLogger(__name__)


class SecurePasswordResetView(PasswordResetView):
    """Generic reset response, shared rate limits, and trusted email links."""

    def form_valid(self, form):
        from apps.core.translations import get_user_language

        email = form.cleaned_data["email"].strip().casefold()
        ip = self.request.META.get("REMOTE_ADDR", "unknown")
        keys = (
            ("ip", ip, 20),
            ("email", email, 3),
        )
        throttled = False
        for kind, value, limit in keys:
            digest = salted_hmac("password-reset-rate", f"{kind}:{value}").hexdigest()
            key = f"password-reset:{kind}:{digest}"
            if cache.add(key, 1, timeout=3600):
                count = 1
            else:
                count = cache.incr(key)
            throttled |= count > limit
        if throttled:
            return HttpResponseRedirect(self.get_success_url())

        options = {
            "use_https": self.request.is_secure() or not settings.DEBUG,
            "token_generator": self.token_generator,
            "from_email": self.from_email,
            "email_template_name": self.email_template_name,
            "subject_template_name": self.subject_template_name,
            "request": self.request,
            "html_email_template_name": self.html_email_template_name,
            "extra_email_context": {"lang": get_user_language(self.request)},
        }
        if not settings.DEBUG:
            site = urlsplit(settings.SITE_URL)
            if site.scheme != "https" or not site.netloc or site.path not in ("", "/"):
                raise ImproperlyConfigured("SITE_URL must be an HTTPS origin for password reset.")
            options["domain_override"] = site.netloc
        form.save(**options)
        return HttpResponseRedirect(self.get_success_url())


# ---------------------------------------------------------------------------
# Auth Views — serve SPA shell for browser compatibility
# ---------------------------------------------------------------------------

class LoginView(View):
    """Serve SPA shell for /login/ — React handles the actual login page."""

    def get(self, request: HttpRequest) -> HttpResponse:
        return serve_spa_shell(request, fallback="/login")

    def post(self, request: HttpRequest) -> HttpResponse:
        # Legacy form POST — redirect to SPA which uses JSON API
        return serve_spa_shell(request, fallback="/login")


class RegisterView(View):
    """Serve SPA shell for /register/ — React handles the actual registration page.
    
    POST is handled to preserve test behavior: web form registration ignores
    role parameter and always creates a student.
    """

    def get(self, request: HttpRequest) -> HttpResponse:
        return serve_spa_shell(request, fallback="/register")

    def post(self, request: HttpRequest) -> HttpResponse:
        from apps.core.translations import get_user_language, t as _t

        _lang = get_user_language(request)
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        password_confirm = request.POST.get("password_confirm", "")
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()

        # Basic validation
        if not email or not password or not password_confirm:
            return render(request, "registration/register.html", {
                "error": _t("incorrect_credentials", _lang),
            })

        if password != password_confirm:
            return render(request, "registration/register.html", {
                "error": _t("incorrect_credentials", _lang),
            })

        if User.objects.filter(email__iexact=email).exists():
            return render(request, "registration/register.html", {
                "error": _t("incorrect_login", _lang),
            })

        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role="student",  # Always student — ignore any role param
        )
        login(request, user)
        return redirect("web:dashboard")


def logout_view(request: HttpRequest) -> HttpResponse:
    """Log out and redirect to SPA login."""
    logout(request)
    return serve_spa_shell(request, fallback="/login")


@require_GET
def set_language_view(request: HttpRequest, lang: str) -> HttpResponse:
    """Tilni o'zgartirish — session va profile'ga saqlash."""
    from apps.core.translations import SUPPORTED_LANGUAGES

    if lang not in SUPPORTED_LANGUAGES:
        lang = "uz"

    # Save to session
    request.session["language"] = lang

    # Save to user profile if authenticated
    if request.user.is_authenticated and request.user.pk:
        request.user.language = lang
        request.user.save(update_fields=["language"])

    # A referrer is untrusted input; keep the return URL on this host.
    referer = request.META.get("HTTP_REFERER", "/")
    if not url_has_allowed_host_and_scheme(
        referer, allowed_hosts={request.get_host()}, require_https=request.is_secure(),
    ):
        referer = "/"
    response = redirect(referer)
    response.set_cookie(
        "language", lang, max_age=365 * 24 * 60 * 60,
        secure=settings.SESSION_COOKIE_SECURE, httponly=True, samesite="Lax",
    )
    return response


# ---------------------------------------------------------------------------
# Dashboard Views — serve SPA shell
# ---------------------------------------------------------------------------

@login_required
def dashboard_view(request: HttpRequest) -> HttpResponse:
    """Dashboard — serve SPA shell, React Router handles role-based redirect."""
    return serve_spa_shell(request, fallback="/dashboard")


# ---------------------------------------------------------------------------
# Home / Landing Page
# ---------------------------------------------------------------------------

def home_view(request: HttpRequest) -> HttpResponse:
    """Landing page — serve SPA shell."""
    return serve_spa_shell(request, fallback="/")


# ---------------------------------------------------------------------------
# Password Reset Views (Django built-in) — kept for email link compatibility
# The emailed links point to /password-reset/confirm/<uid>/<token>/
# which React handles at /password-reset/confirm/:uid/:token
# These Django views are kept as a fallback but should not be reached.
# ---------------------------------------------------------------------------

# Password reset views use Django's built-in classes with our custom templates
# The templates don't exist, so these will 500 if reached directly.
# React handles password reset via JSON API at /api/auth/password-reset/*
# These are kept only for URL namespace compatibility.

# ---------------------------------------------------------------------------
# Result Detail View — preserved for security tests
# ---------------------------------------------------------------------------

@login_required
def result_detail_view(request: HttpRequest, result_id: int) -> HttpResponse:
    """Result detail — permission check: only owner or teacher of the student."""
    result = get_object_or_404(Result, id=result_id)

    # Owner can view
    if result.student == request.user:
        return serve_spa_shell(request, fallback=f"/results/{result_id}")

    # Teacher of the student can view
    if request.user.role == "teacher":
        from apps.courses.models import StudentGroup
        student_groups = StudentGroup.objects.filter(students=result.student)
        teacher_groups = StudentGroup.objects.filter(teacher=request.user)
        if student_groups.filter(id__in=teacher_groups.values_list("id", flat=True)).exists():
            return serve_spa_shell(request, fallback=f"/results/{result_id}")

    # Admin can view
    from apps.accounts.access import is_platform_admin
    if is_platform_admin(request.user):
        return serve_spa_shell(request, fallback=f"/results/{result_id}")

    # Deny access
    from django.core.exceptions import PermissionDenied
    raise PermissionDenied()


# ---------------------------------------------------------------------------
# Teacher Management Views — preserved for security tests
# ---------------------------------------------------------------------------

from apps.accounts.access import is_platform_admin

@login_required
def manage_teachers_view(request: HttpRequest) -> HttpResponse:
    """Manage teachers — platform admin only."""
    if not is_platform_admin(request.user):
        raise PermissionDenied()
    return serve_spa_shell(request, fallback="/manage-teachers")


@require_POST
@login_required
def promote_user_view(request: HttpRequest, user_id: int) -> HttpResponse:
    """Promote user to teacher — platform admin only."""
    if not is_platform_admin(request.user):
        raise PermissionDenied()
    
    target = get_object_or_404(User, id=user_id)
    target.role = User.Role.TEACHER
    target.save(update_fields=["role"])
    return redirect("web:manage-teachers")


@require_POST
@login_required
def demote_user_view(request: HttpRequest, user_id: int) -> HttpResponse:
    """Demote user to student — platform admin only."""
    if not is_platform_admin(request.user):
        raise PermissionDenied()
    
    target = get_object_or_404(User, id=user_id)
    target.role = User.Role.STUDENT
    target.save(update_fields=["role"])
    return redirect("web:manage-teachers")