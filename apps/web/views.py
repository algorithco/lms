"""
Web views — Django template views for the frontend.

OPTIMIZATIONS (Phase 7):
    1. All stats use DB aggregation (Count, Avg, Sum, Max) instead of Python loops.
    2. select_related / prefetch_related on every queryset to eliminate N+1.
    3. Django cache.get/cache.set for public and slow-changing data.
    4. Proper logging for error paths.
    5. Template partials reuse (stat-card, empty-state) via include/.
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
from django.db.models import Avg, Count, Max, Q, Sum
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET
from django.utils.decorators import method_decorator
from django.views import View

from apps.courses.models import Course, StudentGroup
from apps.essays.models import EssaySubmission, EssayCriterionScore
from apps.results.models import Certificate, Result
from apps.tests.models import Test, TestAttempt

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

# Cache timeout constants
CACHE_TEST_LIST = 60 * 5          # 5 minutes
CACHE_DASHBOARD_STATS = 60 * 2    # 2 minutes
CACHE_CERT_VERIFY = 60 * 10       # 10 minutes


# ---------------------------------------------------------------------------
# Auth Views
# ---------------------------------------------------------------------------

class LoginView(View):
    """Tizimga kirish sahifasi."""

    def get(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated:
            return redirect("web:dashboard")
        return render(request, "registration/login.html")

    def post(self, request: HttpRequest) -> HttpResponse:
        from apps.core.translations import get_user_language, t as _t

        _lang = get_user_language(request)
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")

        if not email or not password:
            return render(request, "registration/login.html", {
                "error": _t("incorrect_credentials", _lang),
            })

        try:
            user = authenticate(request, username=email, password=password)
        except Exception as e:
            logger.error("Auth system error for %s: %s", email, e)
            return render(request, "registration/login.html", {
                "error": "Tizimda xatolik yuz berdi. Qayta urinib ko'ring.",
            })

        if user is not None:
            login(request, user)
            # Remember me: session expiry
            if not request.POST.get("remember_me"):
                request.session.set_expiry(0)  # Browser close = logout
            else:
                request.session.set_expiry(60 * 60 * 24 * 30)  # 30 days

            # Update daily streak
            try:
                from apps.games.models import DailyStreak
                streak_obj, _ = DailyStreak.objects.get_or_create(user=user)
                streak_result = streak_obj.update_streak()
                if streak_result.get("reward_claimed"):
                    messages.success(
                        request,
                        f"🔥 {streak_result['new_streak']} kunlik streak! +{streak_result['xp_earned']} XP olindi!",
                    )
                elif streak_result["new_streak"] > 1:
                    messages.info(
                        request,
                        f"🔥 {streak_result['new_streak']} kunlik streak davom etmoqda!",
                    )
            except Exception:
                pass  # Streak xatosi login'ni to'xtatmasin

            messages.success(request, f"Xush kelibsiz, {user.first_name}!")
            logger.info("User logged in: %s (ip=%s)", user.email, request.META.get("REMOTE_ADDR", "?"))
            return redirect("web:dashboard")

        logger.warning("Failed login attempt for email: %s (ip=%s)", email, request.META.get("REMOTE_ADDR", "?"))
        return render(request, "registration/login.html", {
            "error": _t("incorrect_login", _lang),
        })


class RegisterView(View):
    """Ro'yxatdan o'tish sahifasi."""

    def get(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated:
            return redirect("web:dashboard")
        return render(request, "registration/register.html")

    def post(self, request: HttpRequest) -> HttpResponse:
        from apps.accounts.serializers import RegisterSerializer

        data = {
            "email": request.POST.get("email", ""),
            "password": request.POST.get("password", ""),
            "password_confirm": request.POST.get("password_confirm", ""),
            "first_name": request.POST.get("first_name", ""),
            "last_name": request.POST.get("last_name", ""),
        }

        serializer = RegisterSerializer(data=data)
        if serializer.is_valid():
            user = serializer.save()
            login(request, user)

            # Send welcome email
            try:
                from apps.notifications.services.email_service import EmailService
                EmailService.send_welcome(
                    to_email=user.email,
                    student_name=user.get_full_name(),
                    recipient=user,
                )
            except Exception as e:
                logger.warning("Welcome email failed: %s", e)

            messages.success(request, "Muvaffaqiyatli ro'yxatdan o'tdingiz!")
            logger.info("New user registered: %s (role=%s)", user.email, user.role)
            return redirect("web:dashboard")

        logger.warning("Registration failed: %s", serializer.errors)
        return render(request, "registration/register.html", {
            "errors": serializer.errors,
            "form_data": data,
        })


@login_required
def logout_view(request: HttpRequest) -> HttpResponse:
    """Tizimdan chiqish."""
    logger.info("User logged out: %s", request.user.email)
    logout(request)
    messages.success(request, "Tizimdan muvaffaqiyatli chiqdingiz.")
    return redirect("web:login")


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
# Home / Landing Page
# ---------------------------------------------------------------------------

def home_view(request: HttpRequest) -> HttpResponse:
    """Landing page — not authenticated users see this."""
    if request.user.is_authenticated:
        return redirect("web:dashboard")
    return render(request, "web/home.html")


# ---------------------------------------------------------------------------
# Dashboard Views
# ---------------------------------------------------------------------------

@login_required
def dashboard_view(request: HttpRequest) -> HttpResponse:
    """Dashboard — role ga qarab yo'naltirish."""
    from apps.accounts.access import is_platform_admin

    if is_platform_admin(request.user):
        return redirect("panel:dashboard")
    if request.user.role == "student":
        return _student_dashboard(request)
    elif request.user.role == "teacher":
        return _teacher_dashboard(request)
    if request.user.role == "parent":
        return redirect("web:parent-portal")
    raise PermissionDenied


def _student_dashboard(request: HttpRequest) -> HttpResponse:
    """
    Student dashboard — all stats via DB aggregation (1 query per stat).
    Cached for CACHE_DASHBOARD_STATS seconds.
    """
    user = request.user
    cache_key = f"student_dashboard_{user.id}"

    cached = cache.get(cache_key)
    if cached is not None:
        return render(request, "web/student_dashboard.html", cached)

    # Single aggregation query for stats
    stats_qs = Result.objects.filter(student=user)
    stats_raw = stats_qs.aggregate(
        total_tests=Count("id"),
        passed=Count("id", filter=Q(is_passed=True)),
        avg_percentage=Avg("percentage"),
    )

    stats = {
        "total_tests": stats_raw["total_tests"],
        "passed": stats_raw["passed"],
        "avg_percentage": round(stats_raw["avg_percentage"] or 0, 1),
        "certificates": Certificate.objects.filter(student=user).count(),
    }

    # Optimized: select_related eliminates N+1 on test.course
    recent_results = (
        Result.objects.filter(student=user)
        .select_related("test", "course")
        .order_by("-calculated_at")[:5]
    )

    # Optimized: select_related + annotate eliminates N+1 on course
    available_tests = (
        Test.objects.filter(is_active=True)
        .select_related("course")
        .annotate(total_questions_count=Count("questions"))
        .order_by("-created_at")[:6]
    )

    # --- Essay stats (single aggregation query) ---
    essay_qs = EssaySubmission.objects.filter(student=user)
    essay_raw = essay_qs.aggregate(
        total_essays=Count("id"),
        graded=Count("id", filter=Q(status=EssaySubmission.Status.GRADED)),
        avg_score=Avg("total_score"),
    )
    essay_stats = {
        "total_essays": essay_raw["total_essays"],
        "graded": essay_raw["graded"],
        "avg_score": round(float(essay_raw["avg_score"] or 0), 1),
        "avg_percentage": 0.0,
    }
    # Calculate average percentage from graded essays
    if essay_stats["graded"] > 0:
        graded_essays = essay_qs.filter(status=EssaySubmission.Status.GRADED)
        total_pct = sum(e.score_percentage for e in graded_essays)
        essay_stats["avg_percentage"] = round(total_pct / essay_stats["graded"], 1)

    # Recent essays (last 5)
    recent_essays = (
        EssaySubmission.objects.filter(student=user)
        .select_related("topic")
        .order_by("-updated_at")[:5]
    )

    # --- Game stats (XP, coins, badges) ---
    from apps.games.models import UserGameScore, UserBadge
    game_scores = UserGameScore.objects.filter(user=user)
    game_stats = {
        "total_xp": sum(gs.total_xp for gs in game_scores),
        "total_coins": sum(gs.total_coins for gs in game_scores),
        "games_played": sum(gs.games_played for gs in game_scores),
        "badges_count": UserBadge.objects.filter(user=user).count(),
    }

    ctx = {
        "stats": stats,
        "recent_results": recent_results,
        "available_tests": available_tests,
        "essay_stats": essay_stats,
        "recent_essays": recent_essays,
        "game_stats": game_stats,
    }

    cache.set(cache_key, ctx, CACHE_DASHBOARD_STATS)
    return render(request, "web/student_dashboard.html", ctx)


def _teacher_dashboard(request: HttpRequest) -> HttpResponse:
    """
    Teacher dashboard — all stats via DB aggregation.
    Eliminates the old Python `sum(t.attempt_count for t in tests)` pattern.
    """
    user = request.user
    cache_key = f"teacher_dashboard_{user.id}"

    cached = cache.get(cache_key)
    if cached is not None:
        return render(request, "web/teacher_dashboard.html", cached)

    # Teacher's test IDs (base queryset)
    teacher_test_ids = list(
        Test.objects.filter(course__teacher=user).values_list("id", flat=True)
    )

    # Optimized: single aggregation query for all teacher stats
    if teacher_test_ids:
        attempt_stats = (
            TestAttempt.objects.filter(test_id__in=teacher_test_ids)
            .aggregate(
                total_attempts=Count("id"),
                avg_percentage=Avg("percentage"),
            )
        )
        passed_count = (
            Result.objects.filter(
                test_id__in=teacher_test_ids,
                is_passed=True,
            ).count()
        )
    else:
        attempt_stats = {"total_attempts": 0, "avg_percentage": 0}
        passed_count = 0

    total_attempts = attempt_stats["total_attempts"]
    avg_pct = round(attempt_stats["avg_percentage"] or 0, 1)
    pass_rate = round(
        (passed_count / total_attempts * 100) if total_attempts > 0 else 0, 1
    )

    # Tests with annotation (no N+1 — single query)
    tests = (
        Test.objects.filter(course__teacher=user)
        .select_related("course")
        .annotate(
            attempt_count=Count("attempts"),
            avg_pct=Avg("attempts__percentage"),
        )
        .order_by("-created_at")
    )

    total_tests = tests.count()

    # Recent results (select_related eliminates N+1)
    recent_results = (
        Result.objects.filter(test_id__in=teacher_test_ids)
        .select_related("student", "test")
        .order_by("-calculated_at")[:10]
    )

    # --- Essay review queue stats ---
    pending_essays = EssaySubmission.objects.filter(
        status=EssaySubmission.Status.PENDING_TEACHER,
    ).select_related("student", "topic").order_by("-submitted_at")
    pending_count = pending_essays.count()
    pending_essays_list = list(pending_essays[:5])

    # Essay grading stats (all graded essays)
    essay_raw = EssaySubmission.objects.filter(
        status=EssaySubmission.Status.GRADED,
    ).aggregate(
        total_graded=Count("id"),
        avg_score=Avg("total_score"),
    )
    essay_avg_pct = 0.0
    if essay_raw["avg_score"] is not None:
        essay_avg_pct = round(float(essay_raw["avg_score"]) / 24 * 100, 1)

    # --- Student-requested reviews (priority) ---
    student_requested = pending_essays.filter(teacher_review_requested=True)
    student_requested_count = student_requested.count()

    # --- Student Progress (top 10 by attempts) ---
    from apps.accounts.models import User
    student_progress = (
        Result.objects.filter(test_id__in=teacher_test_ids)
        .values(
            "student__id", "student__first_name", "student__last_name", "student__email",
        )
        .annotate(
            total_attempts=Count("id"),
            avg_pct=Avg("percentage"),
            passed=Count("id", filter=Q(is_passed=True)),
            best_score=Max("percentage"),
        )
        .order_by("-total_attempts")[:10]
    )

    # Enrich with essay stats per student
    student_ids = [s["student__id"] for s in student_progress]
    essay_per_student = (
        EssaySubmission.objects.filter(
            student_id__in=student_ids,
            status=EssaySubmission.Status.GRADED,
        )
        .values("student_id")
        .annotate(
            essay_count=Count("id"),
            essay_avg=Avg("total_score"),
        )
    )
    essay_map = {s["student_id"]: s for s in essay_per_student}

    enriched_progress = []
    for sp in student_progress:
        sid = sp["student__id"]
        essay_data = essay_map.get(sid, {})
        enriched_progress.append({
            "id": sid,
            "name": f"{sp['student__first_name']} {sp['student__last_name']}",
            "email": sp["student__email"],
            "total_attempts": sp["total_attempts"],
            "avg_pct": round(float(sp["avg_pct"] or 0), 1),
            "passed": sp["passed"],
            "best_score": round(float(sp["best_score"] or 0), 1),
            "essay_count": essay_data.get("essay_count", 0),
            "essay_avg": round(float(essay_data.get("essay_avg", 0) or 0), 1),
        })

    # --- Total unique students ---
    total_students = (
        Result.objects.filter(test_id__in=teacher_test_ids)
        .values("student").distinct().count()
    )

    # --- Chart data: monthly attempts (last 6 months) ---
    from django.db.models.functions import Trunc
    from django.utils import timezone
    from datetime import timedelta

    six_months_ago = timezone.now() - timedelta(days=180)
    monthly_attempts = (
        TestAttempt.objects.filter(
            test_id__in=teacher_test_ids,
            completed_at__gte=six_months_ago,
        )
        .annotate(month=Trunc("completed_at", "month"))
        .values("month")
        .annotate(
            count=Count("id"),
            passed=Count("id", filter=Q(percentage__gte=60)),
        )
        .order_by("month")
    )

    chart_labels = [d["month"].strftime("%b") for d in monthly_attempts]
    chart_attempts = [d["count"] for d in monthly_attempts]
    chart_passed = [d["passed"] for d in monthly_attempts]

    # --- Chart data: essay score distribution ---
    essay_scores = list(
        EssaySubmission.objects.filter(
            status=EssaySubmission.Status.GRADED,
        ).values_list("total_score", flat=True)
    )
    essay_dist = {"low1": 0, "low2": 0, "mid1": 0, "mid2": 0, "high1": 0, "high2": 0}
    for score in essay_scores:
        s = float(score)
        if s < 4: essay_dist["low1"] += 1
        elif s < 8: essay_dist["low2"] += 1
        elif s < 12: essay_dist["mid1"] += 1
        elif s < 16: essay_dist["mid2"] += 1
        elif s < 20: essay_dist["high1"] += 1
        else: essay_dist["high2"] += 1

    ctx = {
        "stats": {
            "total_tests": total_tests,
            "total_attempts": total_attempts,
            "avg_percentage": avg_pct,
            "pass_rate": pass_rate,
            "total_students": total_students,
        },
        "tests": tests,
        "recent_results": recent_results,
        "essay_stats": {
            "pending_count": pending_count,
            "total_graded": essay_raw["total_graded"],
            "avg_percentage": essay_avg_pct,
            "student_requested_count": student_requested_count,
        },
        "pending_essays": pending_essays_list,
        "student_requested_essays": list(student_requested[:5]),
        "student_progress": enriched_progress,
        # Chart data
        "chart_labels": chart_labels,
        "chart_attempts": chart_attempts,
        "chart_passed": chart_passed,
        "essay_dist": essay_dist,
        # All graded essays (for teacher to see all results)
        "all_graded_essays": list(
            EssaySubmission.objects.filter(
                status=EssaySubmission.Status.GRADED,
            ).select_related("student", "topic")
            .order_by("-graded_at")[:20]
        ),
    }

    cache.set(cache_key, ctx, CACHE_DASHBOARD_STATS)
    return render(request, "web/teacher_dashboard.html", ctx)


# ---------------------------------------------------------------------------
# Analytics (Teacher)
# ---------------------------------------------------------------------------

@login_required
def analytics_view(request: HttpRequest) -> HttpResponse:
    """Batafsil statistika va tahlil sahifasi — talabalar dashboard + Chart.js grafiklar."""
    user = request.user

    if user.role != "teacher" and not user.is_platform_admin:
        messages.error(request, "Faqat o'qituvchilar uchun.")
        return redirect("web:dashboard")

    from django.db.models.functions import Trunc
    from django.utils import timezone
    from datetime import timedelta

    scoped_tests = Test.objects.all() if user.is_platform_admin else Test.objects.filter(course__teacher=user)
    teacher_test_ids = list(scoped_tests.values_list("id", flat=True))

    # --- 1. Test attempt stats by day (last 30 days) ---
    thirty_days_ago = timezone.now() - timedelta(days=30)
    daily_attempts = (
        TestAttempt.objects.filter(
            test_id__in=teacher_test_ids,
            completed_at__gte=thirty_days_ago,
        )
        .annotate(date=Trunc("completed_at", "day"))
        .values("date")
        .annotate(
            count=Count("id"),
            avg_pct=Avg("percentage"),
        )
        .order_by("date")
    )

    chart_labels = [d["date"].strftime("%d.%m") for d in daily_attempts]
    chart_attempts = [d["count"] for d in daily_attempts]
    chart_avg_pct = [round(float(d["avg_pct"] or 0), 1) for d in daily_attempts]

    # --- 2. Pass/fail distribution ---
    if teacher_test_ids:
        pass_fail = Result.objects.filter(test_id__in=teacher_test_ids).aggregate(
            passed=Count("id", filter=Q(is_passed=True)),
            failed=Count("id", filter=Q(is_passed=False)),
        )
    else:
        pass_fail = {"passed": 0, "failed": 0}

    # --- 3. Per-test stats ---
    per_test_stats = (
        scoped_tests
        .select_related("course")
        .annotate(
            attempt_count=Count("attempts"),
            avg_pct=Avg("attempts__percentage"),
            pass_count=Count("attempts", filter=Q(attempts__percentage__gte=60)),
        )
        .order_by("-attempt_count")[:10]
    )

    test_labels = [t.title[:20] for t in per_test_stats]
    test_attempts_data = [t.attempt_count for t in per_test_stats]
    test_avg_data = [round(float(t.avg_pct or 0), 1) for t in per_test_stats]

    # --- 4. Top students (enriched with essay stats) ---
    top_students_raw = (
        Result.objects.filter(test_id__in=teacher_test_ids)
        .values("student__id", "student__first_name", "student__last_name", "student__email")
        .annotate(
            total_tests=Count("id"),
            avg_pct=Avg("percentage"),
            passed=Count("id", filter=Q(is_passed=True)),
            best_score=Max("percentage"),
        )
        .order_by("-avg_pct")
    )

    student_ids = [s["student__id"] for s in top_students_raw]
    essay_per_student = (
        EssaySubmission.objects.filter(
            student_id__in=student_ids,
            status=EssaySubmission.Status.GRADED,
        )
        .values("student_id")
        .annotate(
            essay_count=Count("id"),
            essay_avg=Avg("total_score"),
        )
    )
    essay_map = {s["student_id"]: s for s in essay_per_student}

    top_students = []
    for s in top_students_raw:
        sid = s["student__id"]
        ed = essay_map.get(sid, {})
        essay_avg = round(float(ed.get("essay_avg", 0) or 0), 1)
        top_students.append({
            "student__id": sid,
            "student__first_name": s["student__first_name"],
            "student__last_name": s["student__last_name"],
            "student__email": s["student__email"],
            "total_tests": s["total_tests"],
            "avg_pct": round(float(s["avg_pct"] or 0), 1),
            "passed": s["passed"],
            "best_score": round(float(s["best_score"] or 0), 1),
            "essay_count": ed.get("essay_count", 0),
            "essay_avg": essay_avg,
        })

    # --- 5. Score distribution (histogram) ---
    score_dist = {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0}
    if teacher_test_ids:
        all_scores = list(
            Result.objects.filter(test_id__in=teacher_test_ids)
            .values_list("percentage", flat=True)
        )
        for score in all_scores:
            s = float(score)
            if s <= 20: score_dist["0-20"] += 1
            elif s <= 40: score_dist["21-40"] += 1
            elif s <= 60: score_dist["41-60"] += 1
            elif s <= 80: score_dist["61-80"] += 1
            else: score_dist["81-100"] += 1

    # --- 6. Essay stats ---
    essay_stats = EssaySubmission.objects.filter(
        status=EssaySubmission.Status.GRADED,
    ).aggregate(
        total=Count("id"),
        avg_score=Avg("total_score"),
        off_topic=Count("id", filter=Q(is_off_topic=True)),
    )

    # --- 7. Essay score distribution ---
    essay_score_dist = {"0-4": 0, "4-8": 0, "8-12": 0, "12-16": 0, "16-20": 0, "20-24": 0}
    essay_scores = list(
        EssaySubmission.objects.filter(status=EssaySubmission.Status.GRADED)
        .values_list("total_score", flat=True)
    )
    for score in essay_scores:
        s = float(score)
        if s < 4: essay_score_dist["0-4"] += 1
        elif s < 8: essay_score_dist["4-8"] += 1
        elif s < 12: essay_score_dist["8-12"] += 1
        elif s < 16: essay_score_dist["12-16"] += 1
        elif s < 20: essay_score_dist["16-20"] += 1
        else: essay_score_dist["20-24"] += 1

    # --- 8. Hourly activity (last 7 days) ---
    seven_days_ago = timezone.now() - timedelta(days=7)
    hourly_activity = (
        TestAttempt.objects.filter(
            test_id__in=teacher_test_ids,
            completed_at__gte=seven_days_ago,
        )
        .extra(select={"hour": "EXTRACT(HOUR FROM completed_at)"})
        .values("hour")
        .annotate(count=Count("id"))
        .order_by("hour")
    )

    hour_labels = [f"{int(h['hour']):02d}:00" for h in hourly_activity]
    hour_data = [h["count"] for h in hourly_activity]

    # --- 9. Group stats — fixed N+1, bulk aggregates ---
    groups = StudentGroup.objects.filter(teacher=user).prefetch_related("students") if not user.is_platform_admin else StudentGroup.objects.all().prefetch_related("students")
    # Prefetch students count already via prefetched relation len
    group_stats = []
    for group in groups:
        group_student_ids = list(group.students.values_list("id", flat=True))
        if group_student_ids:
            g_stats = Result.objects.filter(student_id__in=group_student_ids).aggregate(
                total=Count("id"),
                avg_pct=Avg("percentage"),
                passed=Count("id", filter=Q(is_passed=True)),
            )
            group_stats.append({
                "id": group.id,
                "name": group.name,
                "student_count": group.students.count(),
                "total_tests": g_stats["total"],
                "avg_pct": round(float(g_stats["avg_pct"] or 0), 1),
                "passed": g_stats["passed"],
            })

    # --- 10. Summary stats ---
    total_students = len(set(student_ids)) if student_ids else 0
    total_attempts = sum(test_attempts_data) if test_attempts_data else 0
    overall_avg = round(float(Result.objects.filter(test_id__in=teacher_test_ids).aggregate(avg=Avg("percentage"))["avg"] or 0), 1)

    ctx = {
        # Summary
        "total_students": total_students,
        "total_attempts": total_attempts,
        "overall_avg": overall_avg,
        # Charts
        "chart_labels": chart_labels,
        "chart_attempts": chart_attempts,
        "chart_avg_pct": chart_avg_pct,
        "pass_fail": pass_fail,
        "test_labels": test_labels,
        "test_attempts_data": test_attempts_data,
        "test_avg_data": test_avg_data,
        "score_dist": score_dist,
        "essay_score_dist": essay_score_dist,
        "hour_labels": hour_labels,
        "hour_data": hour_data,
        # Students
        "top_students": top_students[:15],
        # Essay
        "essay_stats": essay_stats,
        # Groups
        "group_stats": group_stats,
    }

    return render(request, "web/analytics.html", ctx)


@login_required
def analytics_api_view(request: HttpRequest) -> HttpResponse:
    """Analytics data API — JSON for dynamic chart updates."""
    from django.http import JsonResponse
    from django.db.models.functions import Trunc
    from django.utils import timezone
    from datetime import timedelta

    user = request.user
    if user.role != "teacher" and not user.is_platform_admin:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    scoped_tests = Test.objects.all() if user.is_platform_admin else Test.objects.filter(course__teacher=user)
    teacher_test_ids = list(scoped_tests.values_list("id", flat=True))

    days = int(request.GET.get("days", 30))
    since = timezone.now() - timedelta(days=days)

    daily = (
        TestAttempt.objects.filter(
            test_id__in=teacher_test_ids,
            completed_at__gte=since,
        )
        .annotate(date=Trunc("completed_at", "day"))
        .values("date")
        .annotate(
            count=Count("id"),
            avg_pct=Avg("percentage"),
        )
        .order_by("date")
    )

    return JsonResponse({
        "labels": [d["date"].strftime("%d.%m") for d in daily],
        "attempts": [d["count"] for d in daily],
        "avg_percentage": [round(float(d["avg_pct"] or 0), 1) for d in daily],
    })


# ---------------------------------------------------------------------------
# Test Views
# ---------------------------------------------------------------------------

@login_required
def test_list_view(request: HttpRequest) -> HttpResponse:
    """Testlar ro'yxati — cached for 5 minutes."""
    from apps.accounts.access import is_platform_admin

    user = request.user
    cache_key = f"test_list_{user.id}_{user.role}"

    cached = cache.get(cache_key)
    if cached is not None:
        return render(request, "web/test_list.html", cached)

    if is_platform_admin(user):
        qs = Test.objects.all().select_related("course")
    elif user.role == "student":
        qs = Test.objects.filter(is_active=True).select_related("course")
    else:
        qs = Test.objects.filter(course__teacher=user).select_related("course")

    # Annotate question count (1 query, no N+1)
    # NOTE: annotation name must NOT collide with Test.total_questions @property
    tests = qs.annotate(questions_count=Count("questions")).order_by("-created_at")

    ctx = {"tests": tests}
    cache.set(cache_key, ctx, CACHE_TEST_LIST)
    return render(request, "web/test_list.html", ctx)


@login_required
def take_test_view(request: HttpRequest, test_id: int) -> HttpResponse:
    """Testni topshirish sahifasi."""
    user = request.user

    if user.role != "student":
        messages.error(request, "Faqat o'quvchilar test topshira oladi.")
        return redirect("web:dashboard")

    test = get_object_or_404(
        Test.objects.select_related("course"),
        id=test_id,
        is_active=True,
    )

    # Aktiv attempt mavjudmi?
    attempt = (
        TestAttempt.objects.filter(
            test=test,
            student=user,
            status=TestAttempt.Status.IN_PROGRESS,
        )
        .select_related("test")
        .first()
    )

    if not attempt:
        # Yangi attempt yaratish
        from apps.tests.services import StartAttemptService
        try:
            attempt = StartAttemptService.execute(test_id=test_id, student=user)
        except ValueError as e:
            logger.warning("Failed to start attempt: test=%d, user=%d, error=%s",
                           test_id, user.id, str(e))
            messages.error(request, str(e))
            return redirect("web:test-list")

    # Check if attempt timed out
    if attempt.is_time_expired:
        from apps.tests.services import SubmitAttemptService
        SubmitAttemptService._timeout_attempt(attempt)
        messages.error(request, "Vaqt tugadi! Test avtomatik yakunlandi.")
        return redirect("web:result-detail", result_id=attempt.result.id)

    # Optimized: prefetch_related eliminates N+1 on questions/choices
    import random
    questions = list(
        test.questions.prefetch_related("choices").order_by("position")
    )
    if test.shuffle_questions:
        random.shuffle(questions)

    # Oldingi javoblar (optimized with prefetch)
    answers_map: dict[int, set[int]] = {}
    text_map: dict[int, str] = {}
    for answer in attempt.answers.select_related("question").prefetch_related(
        "selected_choices"
    ):
        answers_map[answer.question_id] = set(
            answer.selected_choices.values_list("id", flat=True)
        )
        if answer.text_answer:
            text_map[answer.question_id] = answer.text_answer

    # Savollarni formatlash
    questions_data = []
    for q in questions:
        choices = list(q.choices.all())
        if test.shuffle_choices:
            random.shuffle(choices)
        questions_data.append({
            "id": q.id,
            "passage": q.passage,
            "text": q.text,
            "question_type": q.question_type,
            "points": q.points,
            "position": q.position,
            "choices": choices,
            "selected_choice_ids": answers_map.get(q.id, set()),
            "text_answer": text_map.get(q.id, ""),
        })

    return render(request, "web/take_test.html", {
        "test": test,
        "attempt": type("obj", (object,), {
            "id": attempt.id,
            "questions": questions_data,
            "remaining_seconds": attempt.remaining_seconds,
        })(),
    })


# ---------------------------------------------------------------------------
# Result Views
# ---------------------------------------------------------------------------

@login_required
def my_results_view(request: HttpRequest) -> HttpResponse:
    """O'quvchining natijalari."""
    results = (
        Result.objects.filter(student=request.user)
        .select_related("test", "course")
        .order_by("-calculated_at")
    )
    return render(request, "web/my_results.html", {"results": results})


@login_required
def result_detail_view(request: HttpRequest, result_id: int) -> HttpResponse:
    """Natija tafsilotlari — savol-blavol tahlil."""
    from apps.results.access import result_queryset_for_user
    result = get_object_or_404(
        result_queryset_for_user(request.user).select_related(
            "test", "course", "student",
        ),
        id=result_id,
    )

    # Optimized: prefetch_related eliminates N+1 on questions/choices/answers
    attempt = result.attempt
    questions = result.test.questions.prefetch_related(
        "choices",
        "student_answers",
        "student_answers__selected_choices",
    ).order_by("position")

    question_details = []
    for q in questions:
        try:
            sa = attempt.answers.get(question=q)
            selected_ids = set(sa.selected_choices.values_list("id", flat=True))
            is_correct = sa.is_correct
            text_answer = sa.text_answer
        except Exception:
            selected_ids = set()
            is_correct = None
            text_answer = ""

        choices = []
        for c in q.choices.all():
            choices.append({
                "id": c.id,
                "text": c.text,
                "is_correct": c.is_correct,
            })

        question_details.append({
            "passage": q.passage,
            "question_text": q.text,
            "question_type": q.question_type,
            "points": q.points,
            "is_correct": is_correct,
            "choices": choices,
            "selected_ids": selected_ids,
            "text_answer": text_answer,
            "correct_text": q.correct_text,
            "explanation": q.explanation,
        })

    # Vaqtni formatlash
    total_seconds = result.time_taken_seconds
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    time_taken_display = f"{minutes} daqiqa {seconds} soniya"

    return render(request, "web/result_detail.html", {
        "result": result,
        "question_details": question_details,
        "time_taken_display": time_taken_display,
    })


# ---------------------------------------------------------------------------
# Certificate Views
# ---------------------------------------------------------------------------

@login_required
def my_certificates_view(request: HttpRequest) -> HttpResponse:
    """O'quvchining sertifikatlari."""
    certificates = (
        Certificate.objects.filter(student=request.user)
        .select_related("test", "course", "result")
        .order_by("-issued_at")
    )

    return render(request, "web/my_certificates.html", {
        "certificates": [{
            "id": c.id,
            "certificate_number": c.certificate_number,
            "course_title": c.course.title,
            "test_title": c.test.title,
            "percentage": c.result.percentage,
            "status": c.status,
            "issued_at": c.issued_at,
        } for c in certificates],
    })


@login_required
def certificate_download_view(request: HttpRequest, cert_id: int) -> HttpResponse:
    """Sertifikat PDF faylini yuklab olish."""
    cert = get_object_or_404(
        Certificate.objects.select_related("student", "course"),
        id=cert_id,
    )
    from apps.results.access import can_access_certificate
    if not can_access_certificate(request.user, cert):
        messages.error(request, "Bu sertifikat sizga tegishli emas.")
        return redirect("web:my-certificates")

    if not cert.file:
        messages.error(request, "PDF fayl hali generatsiya qilinmagan.")
        return redirect("web:my-certificates")

    from django.http import FileResponse
    response = FileResponse(cert.file.open("rb"), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{cert.certificate_number}.pdf"'
    return response


# ---------------------------------------------------------------------------
# Teacher: Student Results
# ---------------------------------------------------------------------------

@login_required
def teacher_results_view(request: HttpRequest) -> HttpResponse:
    """O'qituvchi — o'quvchilar natijalari."""
    results = (
        Result.objects.filter(course__teacher=request.user)
        .select_related("student", "test", "course")
        .order_by("-calculated_at")
    )
    return render(request, "web/my_results.html", {"results": results})


# ---------------------------------------------------------------------------
# Essay Leaderboard
# ---------------------------------------------------------------------------

@login_required
def essay_leaderboard_view(request: HttpRequest) -> HttpResponse:
    """Esse ballari bo'yicha leaderboard — podium (1/2/3) + top 10."""
    # Best essay score per student (using effective_score: final_score > total_score)
    from django.db.models import Max, Case, When, F, Value
    from decimal import Decimal

    student_essay_stats = (
        EssaySubmission.objects.filter(
            status=EssaySubmission.Status.GRADED,
        )
        .values(
            "student__id", "student__first_name", "student__last_name",
        )
        .annotate(
            best_score=Max("total_score"),
            best_converted=Max(
                Case(
                    When(final_score__isnull=False, then=F("final_score")),
                    default=F("total_score"),
                )
            ),
            essay_count=Count("id"),
            avg_score=Avg("total_score"),
        )
        .order_by("-best_score")[:20]
    )

    leaderboard = []
    for i, s in enumerate(student_essay_stats, 1):
        best = float(s["best_score"] or 0)
        target = getattr(settings, "ESSAY_TARGET_SCALE", 75)
        converted = round(best / 24 * target) if best > 0 else 0
        leaderboard.append({
            "rank": i,
            "name": f"{s['student__first_name']} {s['student__last_name']}",
            "student_id": s["student__id"],
            "best_score": best,
            "converted_score": converted,
            "essay_count": s["essay_count"],
            "avg_score": round(float(s["avg_score"] or 0), 1),
        })

    podium = leaderboard[:3] if len(leaderboard) >= 3 else leaderboard
    rest = leaderboard[3:] if len(leaderboard) > 3 else []

    return render(request, "web/essay_leaderboard.html", {
        "podium": podium,
        "rest": rest,
        "total_essays": EssaySubmission.objects.filter(status=EssaySubmission.Status.GRADED).count(),
        "total_students": len(leaderboard),
    })


# ---------------------------------------------------------------------------
# Admin: Teacher Management
# ---------------------------------------------------------------------------

@login_required
def manage_teachers_view(request: HttpRequest) -> HttpResponse:
    """Admin — o'qituvchilarni boshqarish: studentlarni teacher qilish."""
    if not request.user.is_platform_admin:
        messages.error(request, "Faqat adminlar uchun.")
        return redirect("web:dashboard")

    from apps.accounts.models import User

    # Barcha foydalanuvchilar (adminlardan tashqari)
    users = (
        User.objects.filter(is_superuser=False)
        .select_related("profile")
        .order_by("role", "-created_at")
    )

    # Qidiruv
    q = request.GET.get("q", "").strip()
    if q:
        users = users.filter(
            Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
        )

    # Rol bo'yicha filter
    role_filter = request.GET.get("role", "")
    if role_filter in ("student", "teacher"):
        users = users.filter(role=role_filter)

    # Statistika
    stats = {
        "total": User.objects.filter(is_superuser=False).count(),
        "students": User.objects.filter(role="student", is_superuser=False).count(),
        "teachers": User.objects.filter(role="teacher", is_superuser=False).count(),
    }

    return render(request, "web/manage_teachers.html", {
        "users": users[:50],
        "stats": stats,
        "q": q,
        "role_filter": role_filter,
    })


@login_required
def promote_user_view(request: HttpRequest, user_id: int) -> HttpResponse:
    """Admin — foydalanuvchini o'qituvchi qilish."""
    if not request.user.is_platform_admin:
        messages.error(request, "Faqat adminlar uchun.")
        return redirect("web:dashboard")

    if request.method != "POST":
        return redirect("web:manage-teachers")

    from apps.accounts.models import User

    target_user = get_object_or_404(User, id=user_id, is_superuser=False)

    if target_user.role == User.Role.TEACHER:
        messages.info(request, f"{target_user.get_full_name()} allaqachon o'qituvchi.")
        return redirect("web:manage-teachers")

    target_user.role = User.Role.TEACHER
    target_user.save(update_fields=["role"])

    messages.success(
        request,
        f"✅ {target_user.get_full_name()} o'qituvchi qilindi!"
    )
    logger.info("Admin promoted user to teacher: %s", target_user.email)
    return redirect("web:manage-teachers")


@login_required
def demote_user_view(request: HttpRequest, user_id: int) -> HttpResponse:
    """Admin — o'qituvchini o'quvchi qaytarish."""
    if not request.user.is_platform_admin:
        messages.error(request, "Faqat adminlar uchun.")
        return redirect("web:dashboard")

    if request.method != "POST":
        return redirect("web:manage-teachers")

    from apps.accounts.models import User

    target_user = get_object_or_404(User, id=user_id, is_superuser=False)

    if target_user.role == User.Role.STUDENT:
        messages.info(request, f"{target_user.get_full_name()} allaqachon o'quvchi.")
        return redirect("web:manage-teachers")

    target_user.role = User.Role.STUDENT
    target_user.save(update_fields=["role"])

    messages.warning(
        request,
        f"⚠️ {target_user.get_full_name()} o'quvchi qaytarildi."
    )
    logger.info("Admin demoted teacher to student: %s", target_user.email)
    return redirect("web:manage-teachers")


# ---------------------------------------------------------------------------
# Teacher: Student Groups Management
# ---------------------------------------------------------------------------

@login_required
def group_list_view(request: HttpRequest) -> HttpResponse:
    """O'qituvchi — guruhlar ro'yxati."""
    if request.user.role != "teacher" and not request.user.is_platform_admin:
        messages.error(request, "Faqat o'qituvchilar uchun.")
        return redirect("web:dashboard")

    from apps.courses.models import StudentGroup

    groups = StudentGroup.objects.all() if request.user.is_platform_admin else StudentGroup.objects.filter(teacher=request.user)
    groups = groups.prefetch_related("students").order_by("name")

    return render(request, "web/group_list.html", {
        "groups": groups,
    })


@login_required
def group_create_view(request: HttpRequest) -> HttpResponse:
    """Guruh yaratish."""
    if request.user.role != "teacher" and not request.user.is_platform_admin:
        messages.error(request, "Faqat o'qituvchilar uchun.")
        return redirect("web:dashboard")

    from apps.courses.models import StudentGroup

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()

        if not name:
            messages.error(request, "Guruh nomini kiriting.")
            return render(request, "web/group_form.html", {"editing": False})

        if StudentGroup.objects.filter(teacher=request.user, name=name).exists():
            messages.error(request, f"\"{name}\" nomli guruh allaqachon mavjud.")
            return render(request, "web/group_form.html", {"editing": False, "form_data": request.POST})

        group = StudentGroup.objects.create(
            teacher=request.user,
            name=name,
            description=description,
        )

        # Add selected students
        student_ids = request.POST.getlist("students")
        if student_ids:
            from apps.accounts.models import User
            students = User.objects.filter(id__in=student_ids, role="student")
            group.students.set(students)

        messages.success(request, f"✅ Guruh \"{name}\" yaratildi!")
        return redirect("web:group-list")

    # GET — show form with available students
    from apps.accounts.models import User
    students = User.objects.filter(role="student").order_by("first_name", "last_name")

    return render(request, "web/group_form.html", {
        "editing": False,
        "available_students": students,
    })


@login_required
def group_edit_view(request: HttpRequest, group_id: int) -> HttpResponse:
    """Guruhni tahrirlash — talabalarni qo'shish/olib tashlash."""
    if request.user.role != "teacher" and not request.user.is_platform_admin:
        messages.error(request, "Faqat o'qituvchilar uchun.")
        return redirect("web:dashboard")

    from apps.courses.models import StudentGroup
    from apps.accounts.models import User

    groups = StudentGroup.objects.all() if request.user.is_platform_admin else StudentGroup.objects.filter(teacher=request.user)
    group = get_object_or_404(groups, id=group_id)

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()

        if not name:
            messages.error(request, "Guruh nomini kiriting.")
            return render(request, "web/group_form.html", {
                "editing": True,
                "group": group,
                "available_students": User.objects.filter(role="student").order_by("first_name"),
            })

        group.name = name
        group.description = description
        group.save(update_fields=["name", "description"])

        # Update students
        student_ids = request.POST.getlist("students")
        students = User.objects.filter(id__in=student_ids, role="student")
        group.students.set(students)

        messages.success(request, f"✅ Guruh \"{name}\" yangilandi!")
        return redirect("web:group-list")

    # GET
    all_students = User.objects.filter(role="student").order_by("first_name", "last_name")
    group_student_ids = set(group.students.values_list("id", flat=True))

    return render(request, "web/group_form.html", {
        "editing": True,
        "group": group,
        "available_students": all_students,
        "group_student_ids": group_student_ids,
    })


@login_required
def group_delete_view(request: HttpRequest, group_id: int) -> HttpResponse:
    """Guruhni o'chirish."""
    if request.user.role != "teacher" and not request.user.is_platform_admin:
        messages.error(request, "Faqat o'qituvchilar uchun.")
        return redirect("web:dashboard")

    from apps.courses.models import StudentGroup

    groups = StudentGroup.objects.all() if request.user.is_platform_admin else StudentGroup.objects.filter(teacher=request.user)
    group = get_object_or_404(groups, id=group_id)

    if request.method == "POST":
        name = group.name
        group.delete()
        messages.success(request, f"🗑️ Guruh \"{name}\" o'chirildi.")
        return redirect("web:group-list")

    return render(request, "web/group_confirm_delete.html", {"group": group})


@login_required
def group_detail_view(request: HttpRequest, group_id: int) -> HttpResponse:
    """Guruh tafsilotlari — talabalar natijalari."""
    if request.user.role != "teacher" and not request.user.is_platform_admin:
        messages.error(request, "Faqat o'qituvchilar uchun.")
        return redirect("web:dashboard")

    from apps.courses.models import StudentGroup

    groups = StudentGroup.objects.all() if request.user.is_platform_admin else StudentGroup.objects.filter(teacher=request.user)
    group = get_object_or_404(groups, id=group_id)
    students = group.students.all().order_by("first_name", "last_name")

    # Har bir talaba uchun test va esse natijalarini olish
    student_data = []
    for student in students:
        # Test results
        test_results = Result.objects.filter(student=student)
        test_count = test_results.count()
        test_avg = 0
        test_passed = 0
        if test_count > 0:
            test_avg = round(float(test_results.aggregate(avg=Avg("percentage"))["avg"] or 0), 1)
            test_passed = test_results.filter(is_passed=True).count()

        # Essay results
        essay_results = EssaySubmission.objects.filter(student=student, status="graded")
        essay_count = essay_results.count()
        essay_avg = 0
        if essay_count > 0:
            essay_avg = round(float(essay_results.aggregate(avg=Avg("total_score"))["avg"] or 0), 1)

        student_data.append({
            "id": student.id,
            "name": student.get_full_name() or student.email,
            "email": student.email,
            "test_count": test_count,
            "test_avg": test_avg,
            "test_passed": test_passed,
            "essay_count": essay_count,
            "essay_avg": essay_avg,
        })

    # Saralash: o'rtacha ball bo'yicha
    student_data.sort(key=lambda x: (x["test_avg"] + x["essay_avg"] * 100 / 24) / 2, reverse=True)

    return render(request, "web/group_detail.html", {
        "group": group,
        "student_data": student_data,
    })


# ---------------------------------------------------------------------------
# Parent Portal — Ota-onalar uchun farzandlari natijalarini ko'rish
# ---------------------------------------------------------------------------

@login_required
def parent_portal_view(request: HttpRequest) -> HttpResponse:
    """Ota-ona paneli — farzandlari natijalari, testlar, esselar."""
    user = request.user
    if user.role != "parent" and not user.is_platform_admin:
        messages.error(request, "Faqat ota-onalar uchun.")
        return redirect("web:dashboard")

    from apps.accounts.models import ParentStudentLink
    from apps.games.models import DailyStreak, UserGameScore

    # Farzandlarni olish
    children_links = (
        ParentStudentLink.objects.filter(parent=user, is_approved=True)
        .select_related("student")
    )
    children = [link.student for link in children_links]

    children_data = []
    for child in children:
        # Test natijalari
        test_results = (
            Result.objects.filter(student=child)
            .select_related("test", "course")
            .order_by("-calculated_at")[:5]
        )
        test_stats = Result.objects.filter(student=child).aggregate(
            total=Count("id"),
            passed=Count("id", filter=Q(is_passed=True)),
            avg_pct=Avg("percentage"),
        )

        # Esse natijalari
        essay_results = (
            EssaySubmission.objects.filter(student=child)
            .select_related("topic")
            .order_by("-updated_at")[:5]
        )
        essay_stats = EssaySubmission.objects.filter(student=child).aggregate(
            total=Count("id"),
            graded=Count("id", filter=Q(status="graded")),
            avg_score=Avg("total_score"),
        )

        # Gamification
        game_scores = UserGameScore.objects.filter(user=child)
        total_xp = sum(gs.total_xp for gs in game_scores)
        total_coins = sum(gs.total_coins for gs in game_scores)

        # Streak
        try:
            streak = DailyStreak.objects.get(user=child)
            current_streak = streak.current_streak
        except DailyStreak.DoesNotExist:
            current_streak = 0

        children_data.append({
            "child": child,
            "test_results": test_results,
            "test_stats": {
                "total": test_stats["total"],
                "passed": test_stats["passed"],
                "avg_pct": round(float(test_stats["avg_pct"] or 0), 1),
            },
            "essay_results": essay_results,
            "essay_stats": {
                "total": essay_stats["total"],
                "graded": essay_stats["graded"],
                "avg_score": round(float(essay_stats["avg_score"] or 0), 1),
            },
            "total_xp": total_xp,
            "total_coins": total_coins,
            "current_streak": current_streak,
        })

    return render(request, "web/parent_portal.html", {
        "children_data": children_data,
    })


# ---------------------------------------------------------------------------
# CSV Import — Talabalarni to'plamda qo'shish
# ---------------------------------------------------------------------------

@login_required
def csv_import_view(request: HttpRequest) -> HttpResponse:
    """CSV fayldan talabalarni import qilish sahifasi."""
    if request.user.role != "teacher" and not request.user.is_platform_admin:
        messages.error(request, "Faqat o'qituvchilar va adminlar uchun.")
        return redirect("web:dashboard")

    if request.method == "POST":
        csv_file = request.FILES.get("csv_file")

        if not csv_file:
            messages.error(request, "CSV faylni tanlang.")
            return render(request, "web/csv_import.html")

        if not csv_file.name.endswith(".csv"):
            messages.error(request, "Faqat CSV fayllar qabul qilinadi.")
            return render(request, "web/csv_import.html")

        # Size + encoding guards: a multi-GB or binary "CSV" must never be
        # read fully into memory or fed to the parser.
        if csv_file.size > 5 * 1024 * 1024:
            messages.error(request, "CSV fayl hajmi 5 MB dan oshmasligi kerak.")
            return render(request, "web/csv_import.html")

        try:
            csv_content = csv_file.read()
            try:
                csv_content.decode("utf-8-sig")
            except UnicodeDecodeError:
                messages.error(request, "CSV fayl UTF-8 kodlangan bo'lishi kerak.")
                return render(request, "web/csv_import.html")

            from apps.accounts.services.csv_import import CSVImportService
            result = CSVImportService.import_students(
                csv_content=csv_content,
                created_by=request.user,
                send_welcome=True,
            )

            if result["created"] > 0:
                messages.success(
                    request,
                    f"✅ {result['created']} ta talaba muvaffaqiyatli qo'shildi!"
                )
            if result["skipped"] > 0:
                messages.warning(
                    request,
                    f"⚠️ {result['skipped']} ta talaba allaqachon mavjud (o'tkazib yuborildi)."
                )
            if result["errors"]:
                error_msg = f"❌ {len(result['errors'])} ta xatolik yuz berdi."
                messages.error(request, error_msg)

            return render(request, "web/csv_import_result.html", {"result": result})

        except Exception as e:
            messages.error(request, f"Import xatoligi: {str(e)}")
            return render(request, "web/csv_import.html")

    return render(request, "web/csv_import.html")


# ---------------------------------------------------------------------------
# Bulk Test Import — Testlarni CSV'dan import qilish
# ---------------------------------------------------------------------------

@login_required
def bulk_test_import_view(request: HttpRequest) -> HttpResponse:
    """CSV fayldan test import qilish sahifasi."""
    if request.user.role != "teacher" and not request.user.is_platform_admin:
        messages.error(request, "Faqat o'qituvchilar va adminlar uchun.")
        return redirect("web:dashboard")

    # Teacher's courses
    courses = Course.objects.all() if request.user.is_platform_admin else Course.objects.filter(teacher=request.user)
    courses = courses.order_by("title")

    if request.method == "POST":
        csv_file = request.FILES.get("csv_file")
        test_title = request.POST.get("test_title", "").strip()
        course_id = request.POST.get("course_id")

        if not csv_file:
            messages.error(request, "CSV faylni tanlang.")
            return render(request, "web/bulk_test_import.html", {"courses": courses})

        if not test_title:
            messages.error(request, "Test nomini kiriting.")
            return render(request, "web/bulk_test_import.html", {"courses": courses})

        if not course_id:
            messages.error(request, "Kursni tanlang.")
            return render(request, "web/bulk_test_import.html", {"courses": courses})

        if not csv_file.name.endswith(".csv"):
            messages.error(request, "Faqat CSV fayllar qabul qilinadi.")
            return render(request, "web/bulk_test_import.html", {"courses": courses})

        # Size + encoding guards (see csv_import_view)
        if csv_file.size > 5 * 1024 * 1024:
            messages.error(request, "CSV fayl hajmi 5 MB dan oshmasligi kerak.")
            return render(request, "web/bulk_test_import.html", {"courses": courses})

        # Safe numeric parsing — malformed values must not 500 the request
        try:
            time_limit = int(request.POST.get("time_limit", 30) or 30)
            pass_pct = float(request.POST.get("pass_percentage", 60) or 60)
        except (ValueError, TypeError):
            messages.error(request, "Vaqt va o'tish foizi to'g'ri son bo'lishi kerak.")
            return render(request, "web/bulk_test_import.html", {"courses": courses})
        if not (1 <= time_limit <= 600) or not (0 <= pass_pct <= 100):
            messages.error(request, "Vaqt (1-600 daqiqa) yoki foiz (0-100) oralig'idan tashqari.")
            return render(request, "web/bulk_test_import.html", {"courses": courses})

        try:
            csv_content = csv_file.read()
            try:
                csv_content.decode("utf-8-sig")
            except UnicodeDecodeError:
                messages.error(request, "CSV fayl UTF-8 kodlangan bo'lishi kerak.")
                return render(request, "web/bulk_test_import.html", {"courses": courses})

            from apps.tests.bulk_import import BulkTestImportService
            result = BulkTestImportService.import_test(
                csv_content=csv_content,
                test_title=test_title,
                course_id=int(course_id),
                created_by=request.user,
                time_limit_minutes=time_limit,
                pass_percentage=pass_pct,
            )

            if result["success"]:
                messages.success(
                    request,
                    f"✅ Test \"{test_title}\" yaratildi! {result['questions_created']} ta savol qo'shildi."
                )
                return redirect("web:test-list")
            else:
                error_msg = "Import xatolari: " + "; ".join([e["error"] for e in result["errors"][:5]])
                messages.error(request, error_msg)
                return render(request, "web/bulk_test_import.html", {
                    "courses": courses,
                    "result": result,
                })

        except Exception as e:
            messages.error(request, f"Import xatoligi: {str(e)}")
            return render(request, "web/bulk_test_import.html", {"courses": courses})

    return render(request, "web/bulk_test_import.html", {"courses": courses})
