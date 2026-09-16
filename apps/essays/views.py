"""
Essays views — student essay writing, AI grading, teacher review.

Endpoints:
    GET  /essays/                           — Essay topics list
    GET  /essays/<topic_id>/write/          — Essay write page
    POST /essays/api/autosave/              — HTMX autosave
    POST /essays/<submission_id>/submit/    — Submit essay for AI grading
    GET  /essays/<submission_id>/result/    — AI evaluation result
    POST /essays/<submission_id>/request-review/  — Request teacher review
    GET  /essays/teacher/review/            — Teacher review queue
    POST /essays/teacher/<submission_id>/review/  — Submit teacher review
"""
from __future__ import annotations

import logging
from functools import wraps
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.access import is_platform_admin

from apps.core.spa import serve_spa_shell

from .models import EssayCriterionScore, EssaySubmission, EssayTopic, TeacherReview
from .services import (
    TeacherReviewService,
    WordCounter,
    can_review_submission,
    essay_has_grade_result,
    start_grading,
)

logger = logging.getLogger(__name__)


# Maximum essay length accepted for AI grading (characters).
# Protects against LLM context/413 errors and DB abuse.
MAX_ESSAY_LENGTH = 50_000


def _t(request: HttpRequest, key: str) -> str:
    """Translate a key in the request user's language (for JS i18n bundles)."""
    from apps.core.translations import t as translate, get_user_language
    return translate(key, get_user_language(request))


def teacher_required(view_func):
    """
    Restrict a view to teachers and platform admins.

    The essay teacher endpoints (queue / review / submit-review) expose other
    students' essays and the ability to grade them, so they must never be
    reachable by regular students.
    """

    @wraps(view_func)
    def _wrapped(request: HttpRequest, *args, **kwargs):
        user = request.user
        if not (user.is_authenticated and user.is_active and (
            user.role == "teacher" or is_platform_admin(user)
        )):
            raise PermissionDenied("Faqat o'qituvchi va adminlar uchun.")
        return view_func(request, *args, **kwargs)

    return _wrapped


# ---------------------------------------------------------------------------
# Student: Topic List
# ---------------------------------------------------------------------------

@login_required
def essay_topics_view(request: HttpRequest) -> HttpResponse:
    """GET /essays/ — SPA shell (React Router owns /essays/)."""
    return serve_spa_shell(request, fallback="/")


# ---------------------------------------------------------------------------
# Student: Password Gate (parol bilan himoyalangan mavzu kirishi)
# ---------------------------------------------------------------------------

@login_required
def essay_password_gate_view(request: HttpRequest, topic_id: int) -> HttpResponse:
    """GET /essays/<id>/start/ — SPA shell (password gate lives in React)."""
    get_object_or_404(EssayTopic, id=topic_id, is_active=True)
    return serve_spa_shell(request, fallback="/essays")


def _ensure_submission_and_redirect(request: HttpRequest, topic: EssayTopic) -> HttpResponse:
    """Mavjud submission topish yoki yangisini yaratish, keyin write sahifasiga redirect."""
    from django.utils import timezone

    # Mavjud (parol tasdiqlangan) submission topish
    submission = EssaySubmission.objects.filter(
        student=request.user,
        topic=topic,
        password_verified_at__isnull=False,
    ).first()

    if submission:
        if submission.is_expired:
            # Vaqt tugagan — result sahifasiga redirect
            return redirect("essays:result", submission_id=submission.id)
        return redirect("essays:write", submission_id=submission.id)

    # Yangi submission yaratish
    submission = EssaySubmission.objects.create(
        student=request.user,
        topic=topic,
        status=EssaySubmission.Status.DRAFT,
        password_verified_at=timezone.now(),
    )

    logger.info(
        "Essay started: submission=%d, student=%d, topic=%d",
        submission.id, request.user.id, topic.id,
    )

    return redirect("essays:write", submission_id=submission.id)


# ---------------------------------------------------------------------------
# Student: Write Essay (submission_id-based, not topic_id)
# ---------------------------------------------------------------------------

@login_required
def essay_write_view(request: HttpRequest, submission_id: int) -> HttpResponse:
    """GET /essays/write/<id>/ — SPA shell (React Router owns /essays/write/:id)."""
    get_object_or_404(EssaySubmission, id=submission_id, student=request.user)
    return serve_spa_shell(request, fallback=f"/essays/write/{submission_id}")


# ---------------------------------------------------------------------------
# Student: Autosave (HTMX)
# ---------------------------------------------------------------------------

@login_required
@require_POST
def essay_autosave_view(request: HttpRequest) -> HttpResponse:
    """Esse matnini avtomatik saqlash (HTMX).

    Agar vaqt tugagan bo'lsa → avtomatik submit (auto_submit_essay).
    """
    submission_id = request.POST.get("submission_id")
    essay_text = request.POST.get("essay_text", "")

    submission = get_object_or_404(
        EssaySubmission,
        id=submission_id,
        student=request.user,
    )

    # Vaqt tugagan bo'lsa → avtomatik submit qilish
    if (
        submission.password_verified_at
        and submission.is_expired
        and submission.status == EssaySubmission.Status.DRAFT
    ):
        # Avval matnni saqlash
        submission.essay_text = essay_text
        submission.word_count = WordCounter.count(essay_text)
        submission.save(update_fields=["essay_text", "word_count", "updated_at"])

        # Avtomatik baholash — sekin LLM chaqiruvi fonda (Celery yoki thread)
        result = start_grading(submission)

        if result["fallback"]:
            # AI xato yoki bo'sh matn → o'qituvchiga yuborildi
            messages.info(
                request,
                "Vaqt tugadi. Essingiz o'qituvchiga tekshirish uchun yuborildi.",
            )
        elif result["success"]:
            messages.info(
                request,
                "Vaqt tugadi. Essingiz avtomatik baholashga yuborildi.",
            )
        else:
            messages.error(
                request,
                f"Vaqt tugadi. Baholashda xatolik: {result['error']}",
            )

        return render(request, "essays/autosave_result_partial.html", {
            "time_expired": True,
            "auto_submitted": True,
            "fallback": result["fallback"],
            "submission": submission,
        })

    # Oddiy autosave (vaqt hali bor)
    if submission.status == EssaySubmission.Status.DRAFT:
        submission.essay_text = essay_text
        submission.word_count = WordCounter.count(essay_text)
        submission.save(update_fields=["essay_text", "word_count", "updated_at"])

    word_info = WordCounter.get_word_status(essay_text, submission.topic)

    return render(request, "essays/word_counter_partial.html", {
        "word_info": word_info,
        "submission": submission,
    })


# ---------------------------------------------------------------------------
# Student: Submit for AI Grading
# ---------------------------------------------------------------------------

def _js_i18n(request) -> dict:
    """JS i18n bundle for the standalone submit form (request user's language)."""
    from apps.core.translations import t as translate, get_user_language
    lang = get_user_language(request)
    return {
        "js_need_more": translate("essay_js_need_more", lang),
        "js_words": translate("essay_js_words_short", lang),
    }


@login_required
@require_POST
def essay_submit_view(request: HttpRequest, submission_id: int) -> HttpResponse:
    """Esseni AI baholash uchun yuborish (qayta yuborish ham ruxsat).

    Resubmit qoidasi: agar esse to'liq baholanib, natija (score / izoh)
    BAZAGA yozilgan bo'lsa — "allaqachon baholangan" deb bloklanadi. Agar
    AI timeout berib, baho saqlanmagan bo'lsa (status=error / pending_teacher
    / draft) — xatolik qaytarilmaydi, OpenRouter'ga qayta so'rov yuboriladi.
    """
    submission = get_object_or_404(
        EssaySubmission,
        id=submission_id,
        student=request.user,
    )

    # To'liq baholangan → bloklash. Baho hali yo'q → qayta baholashga ruxsat.
    if essay_has_grade_result(submission):
        return render(request, "essays/submit_result_partial.html", {
            "success": False,
            "error": "Bu esse allaqachon baholangan.",
        })

    # Baholash hali davom etmoqda — queue'ga takror qo'shish shart emas;
    # frontend natija sahifasiga o'tib, statusni poll qiladi.
    if submission.status == EssaySubmission.Status.PENDING:
        return render(request, "essays/submit_result_partial.html", {
            "success": True,
            "submission": submission,
            "async_grading": True,
        })

    # Server-side vaqt nazorati
    if submission.password_verified_at and submission.is_expired:
        return render(request, "essays/submit_result_partial.html", {
            "success": False,
            "error": "Vaqt tugadi. Essingizni endi yubora olmaysiz.",
        })

    # Word count validation
    word_count = WordCounter.count(submission.essay_text)
    if word_count < submission.topic.word_limit_min:
        return render(request, "essays/submit_result_partial.html", {
            "success": False,
            "error": f"Kamida {submission.topic.word_limit_min} so'z kerak. Hozir: {word_count} so'z.",
        })

    # AI baholashni fon rejimiga yuklash — grade_essay() 30–90 soniya davom
    # etadigan tashqi LLM chaqiruvi: Celery worker'da, broker tushsa
    # background thread'da. Har ikkala holatda ham request DARHOL qaytadi
    # (status=PENDING; sahifa polling bilan natijani ko'rsatadi) — Cloudflare
    # 502/524 timeout'lari uchun sabab qolmaydi.
    result = start_grading(submission, fail_status=EssaySubmission.Status.ERROR)

    if result["fallback"] and not result.get("async"):
        # Bo'sh / kam so'zli matn → o'qituvchiga yuborildi (defensive —
        # word-count validation yuqorida allaqachon o'tgan)
        return render(request, "essays/submit_result_partial.html", {
            "success": False,
            "error": result.get("error") or "Esse o'qituvchiga yuborildi.",
        })

    return render(request, "essays/submit_result_partial.html", {
        "success": True,
        "submission": submission,
        "async_grading": result.get("async", False),
    })


# ---------------------------------------------------------------------------
# Student: Grading Status (polling endpoint for async grading)
# ---------------------------------------------------------------------------

@login_required
def essay_grading_status_view(request: HttpRequest, submission_id: int) -> JsonResponse:
    """Asinxron AI baholash holati (JSON) — frontend polling uchun.

    GET /essays/api/<submission_id>/status/

    Response:
        {"status": "pending", "poll_after": 3}                  — baholanmoqda
        {"status": "graded", "result_url": "/essays/result/7/"} — tayyor
        {"status": "pending_teacher", ...}                      — o'qituvchiga yuborildi
        {"status": "error", "error": "...", "result_url": ...}  — xatolik
    """
    submission = get_object_or_404(
        EssaySubmission, id=submission_id, student=request.user,
    )

    status = submission.status
    data: dict[str, Any] = {
        "status": status,
        "submission_id": submission.id,
    }

    if status == EssaySubmission.Status.PENDING:
        data["poll_after"] = 3
    elif status in (
        EssaySubmission.Status.GRADED,
        EssaySubmission.Status.AI_EVALUATED,
        EssaySubmission.Status.TEACHER_REVIEWED,
    ):
        data["result_url"] = f"/essays/result/{submission.id}/"
        if submission.total_score is not None:
            data["total_score"] = float(submission.total_score)
            data["max_score"] = submission.max_score
    elif status == EssaySubmission.Status.PENDING_TEACHER:
        data["result_url"] = f"/essays/result/{submission.id}/"
        data["message"] = "Essingiz o'qituvchiga tekshirish uchun yuborildi."
    elif status == EssaySubmission.Status.ERROR:
        data["result_url"] = f"/essays/result/{submission.id}/"
        data["error"] = submission.error_message or "Baholashda xatolik."

    return JsonResponse(data)


# ---------------------------------------------------------------------------
# Student: View Result (unified — handles 12-mezon AND legacy 30-point)
# ---------------------------------------------------------------------------

@login_required
def essay_result_view(request: HttpRequest, submission_id: int) -> HttpResponse:
    """GET /essays/result/<id>/ — SPA shell (React Router owns /essays/result/:id)."""
    get_object_or_404(EssaySubmission, id=submission_id, student=request.user)
    return serve_spa_shell(request, fallback=f"/essays/result/{submission_id}")


# ---------------------------------------------------------------------------
# 12-Mezon Grading: View Result (alias)
# ---------------------------------------------------------------------------

@login_required
def essay_detail_view(request: HttpRequest, submission_id: int) -> HttpResponse:
    """GET essay detail — SPA shell (alias of the result route)."""
    get_object_or_404(EssaySubmission, id=submission_id, student=request.user)
    return serve_spa_shell(request, fallback=f"/essays/result/{submission_id}")


# ---------------------------------------------------------------------------
# 12-Mezon Grading: Improved Version (AI)
# ---------------------------------------------------------------------------

@login_required
@require_POST
def essay_improve_view(request: HttpRequest, submission_id: int) -> HttpResponse:
    """
    AJAX: AI yaxshilangan esse versiyasini qaytarish (yoki yaratish).

    Response JSON:
        {"ok": true, "improved": bool, "content": "..."}  — improved= false
        bo'lsa kontent allaqachon saqlangan (kesh), true bo'lsa endigina
        yaratildi. Xatolikda 400/500 + {"ok": false, "error": "..."}.
    """
    submission = get_object_or_404(
        EssaySubmission.objects.select_related("student", "topic"),
        id=submission_id,
        student=request.user,
    )

    if submission.status not in (
        EssaySubmission.Status.GRADED,
        EssaySubmission.Status.AI_EVALUATED,
    ):
        return JsonResponse(
            {"ok": False, "error": "Esse hali baholanmagan — yaxshilash mumkin emas."},
            status=400,
        )

    from .services import generate_improved_essay

    try:
        content = generate_improved_essay(submission)
    except ImproperlyConfigured as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=503)
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=502)
    except Exception:
        logger.exception("Unexpected improve error: submission=%s", submission_id)
        return JsonResponse(
            {"ok": False, "error": "Kutilmagan xatolik. Qayta urinib ko'ring."},
            status=500,
        )

    return JsonResponse({
        "ok": True,
        # True only when this request generated a new version; False on cache hits.
        "improved": bool(getattr(submission, "_improved_fresh", False)),
        "content": content,
        "word_count": WordCounter.count(content),
    })


# ---------------------------------------------------------------------------
# Student: Request Teacher Review
# ---------------------------------------------------------------------------

@login_required
@require_POST
def essay_request_review_view(request: HttpRequest, submission_id: int) -> HttpResponse:
    """Ustoz tekshiruvini so'rash."""
    submission = get_object_or_404(
        EssaySubmission,
        id=submission_id,
        student=request.user,
    )

    try:
        TeacherReviewService.request_teacher_review(
            submission, request.user, request.POST.get("reason", ""),
        )
    except ValueError as e:
        return render(request, "essays/review_request_partial.html", {
            "success": False,
            "error": str(e),
        })

    submission.refresh_from_db()

    logger.info(
        "Teacher review requested: submission=%d, reason=%s",
        submission.id, submission.teacher_review_reason[:100] if submission.teacher_review_reason else "",
    )

    return render(request, "essays/review_request_partial.html", {
        "success": True,
        "submission": submission,
    })


# ---------------------------------------------------------------------------
# Teacher: Review Queue
# ---------------------------------------------------------------------------

@login_required
@teacher_required
def teacher_essay_queue_view(request: HttpRequest) -> HttpResponse:
    """GET /essays/teacher/queue/ — SPA shell (React owns /teacher/essays)."""
    return serve_spa_shell(request, fallback="/teacher/essays")


# ---------------------------------------------------------------------------
# Teacher: Review Single Essay
# ---------------------------------------------------------------------------

@login_required
@teacher_required
def teacher_review_view(request: HttpRequest, submission_id: int) -> HttpResponse:
    """GET /essays/teacher/<id>/review/ — SPA shell."""
    submission = get_object_or_404(EssaySubmission, id=submission_id)
    if not can_review_submission(request.user, submission):
        raise PermissionDenied
    return serve_spa_shell(
        request, fallback=f"/teacher/essays/{submission_id}/review"
    )


@login_required
@teacher_required
@require_POST
def teacher_submit_review_view(request: HttpRequest, submission_id: int) -> HttpResponse:
    """Ustoz bahosini saqlash — 12 mezon, 24 ballik tizim."""
    submission = get_object_or_404(
        EssaySubmission.objects.select_related(
            "student", "topic", "assigned_reviewer",
        ),
        id=submission_id,
    )
    if not can_review_submission(request.user, submission):
        raise PermissionDenied

    # Parse 12 criteria scores from form: score_1, score_2, ..., score_12
    criteria_scores = {}
    for cid in range(1, 13):
        val = request.POST.get(f"score_{cid}", "0")
        try:
            criteria_scores[cid] = float(val)
        except (ValueError, TypeError):
            criteria_scores[cid] = 0.0

    teacher_comments = request.POST.get("teacher_comments", "")

    try:
        review = TeacherReviewService.submit_review(
            submission=submission,
            teacher=request.user,
            criteria_scores=criteria_scores,
            teacher_comments=teacher_comments,
        )
    except ValueError as e:
        return render(request, "essays/teacher_review_result_partial.html", {
            "success": False,
            "error": str(e),
        })

    submission.refresh_from_db()

    logger.info(
        "Teacher review finalized: submission=%d, final_score=%s",
        submission.id, review.final_score,
    )

    return render(request, "essays/teacher_review_result_partial.html", {
        "success": True,
        "review": review,
        "submission": submission,
    })


# ---------------------------------------------------------------------------
# 12-Mezon Grading: Submit Essay
# ---------------------------------------------------------------------------

@login_required
def essay_create_view(request: HttpRequest) -> HttpResponse:
    """POST /essays/submit/ grades (legacy flow, tested) — GET serves the SPA shell."""
    if request.method == "GET":
        return serve_spa_shell(request, fallback="/essays")

    essay_text = request.POST.get("essay_text", "").strip()
    if not essay_text:
        return JsonResponse(
            {"ok": False, "error": "Esse matni bo'sh bo'lishi mumkin emas."},
            status=400,
        )
    if len(essay_text) > MAX_ESSAY_LENGTH:
        return JsonResponse(
            {"ok": False, "error": f"Esse juda uzun. Maksimal {MAX_ESSAY_LENGTH:,} belgi."},
            status=400,
        )

    # Create pending submission
    submission = EssaySubmission.objects.create(
        student=request.user,
        essay_text=essay_text,
        word_count=len(essay_text.split()),
        status=EssaySubmission.Status.PENDING,
    )

    logger.info(
        "Essay submission created: id=%d, student=%d, word_count=%d",
        submission.id, request.user.id, submission.word_count,
    )

    # --- AI baholashni fon rejimiga yuklash ---
    # (grade_essay() sekin tashqi LLM chaqiruvi; Celery yoki background
    # thread'da bajariladi — web thread hech qachon LLM'ni kutmaydi)
    result = start_grading(submission, fail_status=EssaySubmission.Status.ERROR)

    if result["fallback"] and not result.get("async"):
        return JsonResponse(
            {"ok": False, "error": result.get("error") or "Esse o'qituvchiga yuborildi."},
            status=502,
        )

    # Redirect to result page (PENDING spinner → auto-refresh → natija)
    return redirect("essays:result", submission_id=submission.id)


# NOTE: essay_detail_view is defined above (line ~381) as a redirect to
# essay_result_view which handles both legacy 30-point AND new 12-mezon systems.
# Do NOT redefine it here.
