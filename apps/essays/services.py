"""
Essays services — AI grading (BMB Milliy sertifikat, 12 mezon / 24 ball).

Architecture:
    - WordCounter: counts words in Uzbek text (handles Latin/Cyrillic)
    - grade_essay(): 12-criteria rubric grading via OpenRouter
      (har bir mezon max 2.0 ball, jami 24.0 ball) — yagona baholash tizimi
    - TeacherReviewService: validates and saves teacher's final review

The AI grading uses a structured prompt that returns JSON with:
    - Per-criteria scores (12 mezon: 0/0.5/1/1.5/2 ball, jami 24)
    - Per-criterion short reasons (1-2 jumla)
    - Summary and topic-match info in Uzbek
"""
from __future__ import annotations

import json
import logging
import re
import time
from decimal import Decimal, InvalidOperation
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models import F
from django.db import transaction
from django.core.exceptions import PermissionDenied
from django.utils import timezone

import hashlib

import httpx

from .models import (
    EssayGradingCache,
    EssaySubmission,
    EssayTopic,
    TeacherReview,
    VALID_CRITERION_IDS,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# AI provider resolution (OpenRouter / Groq — OpenAI-compatible APIs)
# ---------------------------------------------------------------------------

VALID_PROVIDERS = {"openrouter", "groq"}

# Key prefixes so a mismatched provider fails fast with a clear message
# instead of a confusing 401 "Missing Authentication header" from the API.
_PROVIDER_KEY_PREFIX = {
    "openrouter": "sk-or-",
    "groq": "gsk_",
}


def _provider_key(provider: str) -> str:
    """Return the configured API key for a provider (stripped)."""
    return (getattr(settings, f"{provider.upper()}_API_KEY", "") or "").strip()


_PLACEHOLDER_KEY_MARKERS = ("your", "here", "change", "example", "placeholder")


def _is_placeholder_key(api_key: str) -> bool:
    """Detect .env.example placeholder keys (never send them to providers).

    Local .env files copied from .env.example keep values like
    ``sk-or-v1-your-openrouter-key-here`` / ``gsk_your-groq-key-here``.
    They pass the prefix guard but always 401 on the live API, costing a
    full fallback-chain retry before ERROR. Treat them as missing so the
    user gets a clear ImproperlyConfigured message (or mock mode) instead.
    """
    if not api_key:
        return True
    lowered = api_key.lower()
    return any(marker in lowered for marker in _PLACEHOLDER_KEY_MARKERS)


def _has_real_key(provider: str) -> bool:
    """True only for a configured, non-placeholder provider key."""
    return bool(_provider_key(provider)) and not _is_placeholder_key(
        _provider_key(provider)
    )


def _resolve_provider() -> str:
    """
    Resolve which AI provider to use and validate its key.

    Honors ``ESSAY_AI_PROVIDER``:
      - "openrouter" / "groq" → forced provider (its key must exist)
      - "auto" (default)      → openrouter if its key is set, else groq

    Raises ImproperlyConfigured (a subclass of ImportError, so callers'
    existing ``except (ValueError, ImportError)`` paths still catch it)
    with a clear, actionable message — never a raw 401.
    """
    configured = (getattr(settings, "ESSAY_AI_PROVIDER", "auto") or "auto").lower()

    if configured in VALID_PROVIDERS:
        provider = configured
    elif configured == "auto":
        if _has_real_key("openrouter"):
            provider = "openrouter"
        elif _has_real_key("groq"):
            provider = "groq"
        else:
            raise ImproperlyConfigured(
                "AI uchun API kalit topilmadi. .env faylida "
                "OPENROUTER_API_KEY yoki GROQ_API_KEY ni sozlang "
                "yoki ESSAY_AI_MOCK_MODE=True qilib testing."
            )
    else:
        raise ImproperlyConfigured(
            f"ESSAY_AI_PROVIDER={configured!r} yaroqsiz. "
            f"Qabul qilinadigan qiymatlar: auto, openrouter, groq."
        )

    api_key = _provider_key(provider)
    if not api_key or _is_placeholder_key(api_key):
        if api_key and _is_placeholder_key(api_key):
            raise ImproperlyConfigured(
                f"{provider.upper()}_API_KEY hali .env.example dagi placeholder "
                f"qiymat ({api_key[:9]}…). Haqiqiy kalit kiriting yoki "
                f"lokal test uchun ESSAY_AI_MOCK_MODE=True qiling."
            )
        raise ImproperlyConfigured(
            f"{provider.upper()}_API_KEY sozlanmagan. "
            f"ESSAY_AI_PROVIDER={provider} uchun .env fayliga "
            f"{provider.upper()}_API_KEY ni qo'shing."
        )

    # Key-format guard: a Groq key (gsk_...) sent to OpenRouter returns a
    # misleading 401 "Missing Authentication header". Detect it up front.
    expected_prefix = _PROVIDER_KEY_PREFIX[provider]
    if not api_key.startswith(expected_prefix):
        hint = (
            f"{provider.upper()} kaliti {expected_prefix} bilan boshlanishi kerak. "
            f"Olingan kalit: {api_key[:6]}… "
        )
        if provider == "openrouter" and api_key.startswith("gsk_"):
            hint += "Bu Groq kaliti (gsk_) — ESSAY_AI_PROVIDER=groq qilib sozlang yoki haqiqiy OpenRouter kaliti (sk-or-…) kiriting."
        elif provider == "groq" and api_key.startswith("sk-or-"):
            hint += "Bu OpenRouter kaliti (sk-or-) — ESSAY_AI_PROVIDER=openrouter qilib sozlang yoki haqiqiy Groq kaliti (gsk_) kiriting."
        raise ImproperlyConfigured(hint)

    return provider


def _get_llm_client(timeout: float | None = None):
    """
    Return an OpenAI-compatible client pointed at the resolved provider
    (OpenRouter or Groq), passing the provider's own API key.

    ``timeout`` bounds each HTTP attempt (network hangs fail fast instead
    of pinning a web worker). Defaults to settings.ESSAY_AI_REQUEST_TIMEOUT
    (60s). Raises ImproperlyConfigured if no API key is configured and
    ESSAY_AI_MOCK_MODE is not True.
    """
    if timeout is None:
        timeout = float(getattr(settings, "ESSAY_AI_REQUEST_TIMEOUT", 90.0))
    # Single source of truth for mock mode — same rule as grade_essay() and
    # _is_mock_mode(): mock ONLY when no API key is configured AND the flag
    # is on. If a key exists, we always build a real provider client (a
    # half-mocked client pointing at a live endpoint would 401).
    if _is_mock_mode():
        api_key = "mock-key"
        base_url = getattr(settings, "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        provider = "openrouter"
    else:
        provider = _resolve_provider()
        # Defensive strip: .env'da kalit oxirida tab/space qolsa, httpx
        # "Illegal header value: b'Bearer ...\t'" bilan rad etadi.
        api_key = _provider_key(provider).strip()
        base_url = getattr(
            settings,
            f"{provider.upper()}_BASE_URL",
            "https://openrouter.ai/api/v1",
        ).strip()

    from openai import OpenAI

    site_url = getattr(settings, "OPENROUTER_SITE_URL", "http://localhost:8000")
    app_name = getattr(settings, "OPENROUTER_APP_NAME", "Ona Tili & Adabiyot")

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        # Per-attempt READ timeout (providers can be slow), but a short
        # CONNECT timeout: httpx's default connect budget is generous, and a
        # hung TCP/TLS connect used to pin the request thread until the full
        # read timeout elapsed — exactly the "LLM blocks the worker" failure
        # mode behind the Cloudflare 502s. max_retries=1 keeps one automatic
        # retry; _chat_with_fallback does the real model-level retrying.
        timeout=httpx.Timeout(timeout, connect=10.0),
        max_retries=1,
        default_headers={
            "HTTP-Referer": site_url,
            "X-Title": app_name,
        },
    )
    return client


def _get_ai_model() -> str:
    """
    Return the LLM model name, honoring an explicit ESSAY_AI_MODEL override
    and otherwise the resolved provider's default model.
    """
    explicit = (getattr(settings, "ESSAY_AI_MODEL", "") or "").strip()
    if explicit:
        return explicit

    provider = "openrouter"
    try:
        provider = _resolve_provider()
    except ImproperlyConfigured:
        # No usable key (e.g. mock mode) — fall back to the OpenRouter default
        provider = "openrouter"

    return getattr(
        settings,
        f"{provider.upper()}_AI_MODEL",
        "nvidia/nemotron-3.5-lightning:free",
    )


def _get_fallback_models() -> list[str]:
    """
    Return the ordered fallback-model chain for the resolved provider.

    OpenRouter: settings.OPENROUTER_FALLBACK_MODELS (list, in order).
    Groq:       settings.GROQ_FALLBACK_MODEL (single; kept for parity).
    Empty list = fallbacks disabled — only the primary model is tried.
    """
    try:
        provider = _resolve_provider()
    except ImproperlyConfigured:
        provider = "openrouter"

    if provider == "openrouter":
        models = getattr(settings, "OPENROUTER_FALLBACK_MODELS", []) or []
        return [m.strip() for m in models if m and m.strip()]

    single = (getattr(settings, "GROQ_FALLBACK_MODEL", "") or "").strip()
    return [single] if single else []


def _model_candidates() -> list[str]:
    """Primary model first, then the fallback chain — deduplicated."""
    try:
        primary = _get_ai_model()
    except ImproperlyConfigured:
        primary = ""
    fallbacks = _get_fallback_models()
    return [m for m in dict.fromkeys([primary, *fallbacks]) if m]


def _is_transient_ai_error(e: Exception) -> bool:
    """
    Classify errors worth retrying with the fallback model: rate-limits,
    5xx, timeouts, connection errors, and model-unavailable (404) — a
    retired/deprecated model should fail over, not abort. Auth errors
    (401/403) and bad requests stay fatal: another model won't fix them.
    """
    import openai

    if isinstance(e, (openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError)):
        return True
    status = getattr(e, "status_code", None)
    if isinstance(status, int) and status >= 500:
        return True
    if isinstance(status, int) and status == 404:
        return True  # model not found / no endpoints — fail over to fallback
    s = str(e).lower()
    return (
        "429" in s
        or "rate limit" in s
        or "overloaded" in s
        or "temporarily" in s
        or "no endpoints found" in s
        or ("404" in s and "not found" in s)
    )


def _is_unsupported_response_format(e: Exception) -> bool:
    """Model response_format=json_object ni qo'llamasa 400 qaytaradi.

    Bunday xato transiyent emas — lekin uni "fallback modelga o'tish" emas,
    "shu modelni json-rejimsiz qayta urinish" sifatida ko'ramiz: JSON rejimi
    faqat kuchaytirish, boshqa modelga o'tish shart emas.
    """
    status = getattr(e, "status_code", None)
    if status != 400:
        return False
    s = str(e).lower()
    return (
        "response_format" in s
        or "json_object" in s
        or "json mode" in s
        or "structured output" in s
    )


def _is_invalid_model_error(e: Exception) -> bool:
    """OpenRouter 400 "X is not a valid model ID" — model ID provider'da
    umuman mavjud emas (eskirgan yoki noto'g'ri yozilgan).

    Bunday xato transiyent emas, lekin butun taskni o'ldirmasligi kerak:
    zanjirdagi keyingi modelga o'tiladi (auth xatosidan farqli ravishda —
    boshqa model ham xuddi shu kalit bilan ishlaydi, muammo model'da).
    """
    status = getattr(e, "status_code", None)
    if status != 400:
        return False
    s = str(e).lower()
    return (
        "is not a valid model" in s
        or "invalid model id" in s
        or ("invalid model" in s and "id" in s)
        or "no endpoints found matching" in s
    )


def _chat_with_fallback(
    client,
    model: str,
    fallback_models: "list[str] | str" = "",
    *,
    messages: list,
    max_tokens: int,
    temperature: float,
    max_attempts: int = 2,
    response_format: dict | None = None,
):
    """
    Try each model in sequence: ``model`` first, then every entry of
    ``fallback_models`` (a list, or a single model string for convenience).

    Per model, transient failures (429 rate limit, 5xx, timeout, connection
    error, 404 model-unavailable) and empty replies are retried up to
    ``max_attempts`` times with a short pause between tries; then the next
    model in the chain takes over. A 400 "is not a valid model ID" skips
    straight to the next model without burning attempts. An exception is
    raised only when the whole chain is exhausted. Other non-transient
    errors (auth, bad request) propagate immediately — retrying them
    anywhere is pointless.

    Returns ``(response, model_used)``.
    """
    if isinstance(fallback_models, str):
        fallback_models = [fallback_models] if fallback_models else []
    candidates = [m for m in dict.fromkeys([model, *fallback_models]) if m]

    last_exc: Exception | None = None
    # Qat'iy JSON rejimi (json_object) — model fikrlash matni yoki boshqa
    # tekst chiqarsa, ba'zi modellar bu parametrni 400 bilan rad etadi;
    # unda shu modelni json-rejimsiz qayta urinamiz (use_json_mode=False).
    use_json_mode = response_format is not None

    for ci, candidate in enumerate(candidates):
        is_last_model = ci == len(candidates) - 1
        next_model = None if is_last_model else candidates[ci + 1]
        # Transient 429s/empty bodies on free models often clear in ~1s.
        for attempt in range(max(1, max_attempts)):
            tail = f"; falling back to {next_model}" if next_model else "; chain exhausted"
            try:
                kwargs = {
                    "model": candidate,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "messages": messages,
                }
                if use_json_mode:
                    kwargs["response_format"] = {"type": "json_object"}
                response = client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content if response.choices else None
                if content and content.strip():
                    return response, candidate
                logger.warning(
                    "AI model %s returned an empty reply (attempt %d)%s",
                    candidate,
                    attempt + 1,
                    tail,
                )
                last_exc = last_exc or ValueError("LLM bo'sh javob qaytardi")
            except Exception as e:
                if use_json_mode and _is_unsupported_response_format(e):
                    # Ba'zi modellar response_format=json_object ni qo'llamaydi
                    # (400 "Unsupported parameter: 'response_format'") — bu
                    # halokatli emas: shu modelni json-rejimsiz qayta urinamiz.
                    use_json_mode = False
                    logger.warning(
                        "AI model %s rejects response_format=json_object (%s) — retrying without it",
                        candidate, e,
                    )
                    continue  # urinish sarflanmaydi; darhol qayta uriniladi
                if _is_invalid_model_error(e):
                    # Model ID provider'da mavjud emas (400 "is not a valid
                    # model ID") — task o'lib qolmasin: urinish sarflanmaydi,
                    # darhol zanjirdagi keyingi modelga o'tiladi.
                    last_exc = e
                    logger.warning(
                        "AI model %s is not a valid model ID on the provider (%s) — skipping to next model%s",
                        candidate,
                        e,
                        tail,
                    )
                    break  # ichki attempt sikldan chiqib keyingi modelga
                last_exc = e
                if not _is_transient_ai_error(e):
                    raise
                logger.warning(
                    "AI model %s failed transiently (attempt %d): %s%s",
                    candidate,
                    attempt + 1,
                    e,
                    tail,
                )
            if max(1, max_attempts) > 1 and attempt == 0:
                time.sleep(1.2)

    assert last_exc is not None  # candidates is never empty (model is set)
    raise last_exc


def _is_mock_mode() -> bool:
    """Check if we're running in mock mode (no real API key)."""
    has_key = _has_real_key("openrouter") or _has_real_key("groq")
    return not has_key and getattr(settings, "ESSAY_AI_MOCK_MODE", False)


# ---------------------------------------------------------------------------
# Word Counter
# ---------------------------------------------------------------------------

class WordCounter:
    """
    Uzbek text word counter.

    Handles:
        - Latin and Cyrillic characters
        - Multiple spaces and newlines
        - punctuation (not counted as separate words)
    """

    @staticmethod
    def count(text: str) -> int:
        """
        Count words in text.

        Args:
            text: Essay text (Uzbek, Latin or Cyrillic).

        Returns:
            Word count (integer).
        """
        if not text or not text.strip():
            return 0

        # Normalize: replace multiple whitespace with single space
        normalized = re.sub(r'\s+', ' ', text.strip())

        # Split by spaces
        words = normalized.split(' ')

        # Filter out empty strings and pure punctuation
        valid_words = []
        for w in words:
            w = w.strip()
            if w and re.search(r'[a-zA-ZА-Яа-яЁё]', w):
                valid_words.append(w)

        return len(valid_words)

    @staticmethod
    def get_word_status(text: str, topic: EssayTopic) -> dict[str, Any]:
        """
        Get word count status relative to topic limits.

        Returns:
            {"count": int, "status": "ok"|"under"|"over", "min": int, "max": int}
        """
        count = WordCounter.count(text)

        if count < topic.word_limit_min:
            status = "under"
        elif count > topic.word_limit_max:
            status = "over"
        else:
            status = "ok"

        return {
            "count": count,
            "status": status,
            "min": topic.word_limit_min,
            "max": topic.word_limit_max,
        }


# ---------------------------------------------------------------------------
# Mock response helper (only used when ESSAY_AI_MOCK_MODE=True)
# ---------------------------------------------------------------------------

def _mock_12_criteria_response(essay_text: str, topic_title: str = "") -> dict[str, Any]:
    """Generate a mock 12-criteria response for frontend testing."""
    word_count = WordCounter.count(essay_text)
    base = min(2, max(0, word_count // 100))
    half = min(1.5, max(0.5, word_count // 150))

    criteria = [
        {"id": 1, "name": "Uslub", "score": base, "reason": "[SINOV REJIMI] Mock baholash"},
        {"id": 2, "name": "Ikkala qarash va shaxsiy fikr", "score": base, "reason": "[SINOV REJIMI] Mock baholash"},
        {"id": 3, "name": "Dalillar bilan asoslanganlik", "score": base, "reason": "[SINOV REJIMI] Mock baholash"},
        {"id": 4, "name": "Kirish/asosiy qism/xulosa", "score": base, "reason": "[SINOV REJIMI] Mock baholash"},
        {"id": 5, "name": "Mantiqiy-qurilish", "score": half, "reason": "[SINOV REJIMI] Mock baholash"},
        {"id": 6, "name": "Mantiqiy-mazmuniy izchillik", "score": half, "reason": "[SINOV REJIMI] Mock baholash"},
        {"id": 7, "name": "Imlo xatolari", "score": base, "reason": "[SINOV REJIMI] Mock baholash"},
        {"id": 8, "name": "Punktuatsiya xatolari", "score": half, "reason": "[SINOV REJIMI] Mock baholash"},
        {"id": 9, "name": "Qo'shimcha qo'llash xatolari", "score": base, "reason": "[SINOV REJIMI] Mock baholash"},
        {"id": 10, "name": "So'z qo'llash uslubiy xatolari", "score": half, "reason": "[SINOV REJIMI] Mock baholash"},
        {"id": 11, "name": "Leksik xilma-xillik", "score": half, "reason": "[SINOV REJIMI] Mock baholash"},
        {"id": 12, "name": "Sheva/vulgarizm/parazit so'zlar", "score": base, "reason": "[SINOV REJIMI] Mock baholash"},
    ]

    total = sum(c["score"] for c in criteria)
    return {
        "criteria": criteria,
        "total_score": float(total),
        "max_score": 24,
        "summary": f"[SINOV REJIMI] {word_count} so'zlik esse. Haqiqiy AI bahosi uchun OPENROUTER_API_KEY ni sozlang.",
        "topic_match": True,
        "topic_match_reason": "[SINOV REJIMI] Mock tekshiruv",
    }



# ---------------------------------------------------------------------------
# Escalation: find the right reviewer for a student
# ---------------------------------------------------------------------------

def _find_reviewer_for_student(student):
    """
    Find the appropriate reviewer for a student's essay.

    Logic:
      1. If student is in a group → return the group's teacher
      2. If student is not in any group → return the first admin user
      3. If no admin found → return None (fallback)
    """
    from django.contrib.auth import get_user_model
    from apps.courses.models import StudentGroup

    User = get_user_model()

    # Check if student is in any group
    group = StudentGroup.objects.filter(students=student).select_related("teacher").first()
    if group and group.teacher:
        return group.teacher

    # No group → find admin
    admin_user = User.objects.filter(role="admin").first()
    if admin_user:
        return admin_user

    # Fallback: find any teacher
    return User.objects.filter(role="teacher").first()


def can_review_submission(user, submission: EssaySubmission) -> bool:
    """Object-level authorization for reading or grading an essay."""
    from apps.accounts.access import is_platform_admin

    if not user or not user.is_authenticated or not user.is_active:
        return False
    if is_platform_admin(user):
        return True
    if getattr(user, "role", None) != "teacher":
        return False
    if submission.assigned_reviewer_id:
        return submission.assigned_reviewer_id == user.id
    if submission.topic_id and submission.topic.created_by_id == user.id:
        return True
    return submission.student.student_groups.filter(teacher=user).exists()


def _notify_reviewer(submission, reviewer):
    """Notify reviewer about new essay review request via Telegram."""
    if (
        not reviewer or not getattr(reviewer, "telegram_chat_id", None)
        or not getattr(reviewer, "telegram_identity_verified_at", None)
    ):
        return

    try:
        from apps.notifications.services.telegram_service import TelegramService

        student_name = submission.student.get_full_name() or submission.student.email
        topic_name = submission.topic.title if submission.topic else "Mavzu yo'q"

        # Determine if it's student-requested
        is_student_request = submission.teacher_review_requested
        priority_text = "🚨 O'quvchi e'tiroz bildirdi!" if is_student_request else "📝 Yangi esse tekshirish kerak"

        text = (
            f"{priority_text}\n\n"
            f"👤 O'quvchi: *{student_name}*\n"
            f"📝 Mavzu: *{topic_name}*\n"
            f"🤖 AI baho: *{submission.total_score}/{submission.max_score}*\n"
        )

        if is_student_request and submission.teacher_review_reason:
            text += f"💬 Sabab: {submission.teacher_review_reason}\n"

        text += f"\n🔗 Tekshirish: /essays/teacher/{submission.id}/review/"

        # Sync httpx call — safe inside Django views and Celery tasks without
        # any asyncio/event-loop juggling. Failures are logged, never raised.
        TelegramService.send_message_with_keyboard(
            chat_id=reviewer.telegram_chat_id,
            text=text,
            parse_mode="Markdown",
            notification_type="essay_review_request" if is_student_request else "general",
            recipient=reviewer,
            title=f"Esse tekshirish: {student_name}",
        )
    except Exception as e:
        logger.warning("Failed to notify reviewer %s: %s", reviewer.email, e)


# ---------------------------------------------------------------------------
# Teacher Review Service
# ---------------------------------------------------------------------------

class TeacherReviewService:
    """
    Handles teacher review workflow (12-criteria, 24-point system):
        1. Teacher views AI evaluation (12 criteria)
        2. Teacher can modify individual criterion scores
        3. Teacher adds comments
        4. Final score is saved (max 24 points)

    Each criterion is scored 0-2 (increments of 0.5).
    Total max: 12 * 2 = 24.
    """

    @staticmethod
    @transaction.atomic
    def submit_review(
        submission: EssaySubmission,
        teacher,
        criteria_scores: dict[int, float],
        teacher_comments: str = "",
    ) -> TeacherReview:
        """
        Ustoz bahosini saqlash (12-mezon, 24 ball).

        Args:
            submission: EssaySubmission instance.
            teacher: User instance (role=teacher).
            criteria_scores: {1: 1.5, 2: 2.0, ..., 12: 1.0} (int key -> float value)
            teacher_comments: Ustoz izohi.

        Returns:
            TeacherReview instance.

        Raises:
            ValueError: Ballar yaroqsiz bo'lsa.
        """
        submission = (
            EssaySubmission.objects.select_for_update(of=("self",))
            .select_related("student", "topic", "assigned_reviewer")
            .get(pk=submission.pk)
        )
        if not can_review_submission(teacher, submission):
            raise PermissionDenied("Bu esseni tekshirishga ruxsatingiz yo'q.")

        VALID_SCORES = {0.0, 0.5, 1.0, 1.5, 2.0}

        # Validate scores
        total_score = Decimal("0")
        validated_scores = {}

        for cid in range(1, 13):
            raw = criteria_scores.get(cid, 0)
            score = Decimal(str(raw))
            if score not in VALID_SCORES:
                raise ValueError(
                    f"Mezon #{cid}: ball {raw} yaroqsiz. "
                    f"Ruxsat etilgan: {VALID_SCORES}"
                )
            total_score += score
            validated_scores[str(cid)] = float(score)

        total_score = min(total_score, Decimal("24"))

        # Create or update review
        review, created = TeacherReview.objects.update_or_create(
            submission=submission,
            defaults={
                "teacher": teacher,
                "criteria_scores": validated_scores,
                "final_score": total_score,
                "teacher_comments": teacher_comments,
            },
        )

        # Update submission status
        submission.status = EssaySubmission.Status.TEACHER_REVIEWED
        submission.final_score = total_score
        submission.teacher_review_requested = False
        submission.save(update_fields=[
            "status", "final_score", "teacher_review_requested", "updated_at",
        ])

        logger.info(
            "Teacher review submitted: submission=%d, teacher=%d, score=%s/24, created=%s",
            submission.id, teacher.id, total_score, created,
        )

        return review

    @staticmethod
    @transaction.atomic
    def request_teacher_review(
        submission: EssaySubmission, student, reason: str = "",
    ) -> EssaySubmission:
        """
        O'quvchi ustoz tekshiruvini so'raydi.

        Escalation logic:
          1. Agar o'quvchi guruhda bo'lsa → guruh o'qituvchisiga yuboriladi
          2. Agar guruhda bo'lmasa → sayt adminiga yuboriladi

        Updates submission status to PENDING_TEACHER.
        """
        submission = EssaySubmission.objects.select_for_update().get(pk=submission.pk)
        if not student.is_authenticated or not student.is_active or submission.student_id != student.pk:
            raise PermissionDenied("Bu esseni qayta ko'rishni so'rashga ruxsat yo'q.")
        if submission.status not in (
            EssaySubmission.Status.AI_EVALUATED,
            EssaySubmission.Status.GRADED,
        ):
            raise ValueError(
                "Faqat AI baholangan esselarni ustozga yuborish mumkin."
            )

        reviewer = _find_reviewer_for_student(submission.student)
        submission.status = EssaySubmission.Status.PENDING_TEACHER
        submission.assigned_reviewer = reviewer
        submission.teacher_review_requested = True
        submission.teacher_review_requested_at = timezone.now()
        submission.teacher_review_reason = reason
        submission.save(update_fields=[
            "status", "assigned_reviewer", "teacher_review_requested",
            "teacher_review_requested_at", "teacher_review_reason", "updated_at",
        ])

        # Notify reviewer via Telegram
        transaction.on_commit(lambda: _notify_reviewer(submission, reviewer))

        logger.info(
            "Teacher review requested: submission=%d, student=%d, reviewer=%s",
            submission.id, submission.student_id,
            reviewer.email if reviewer else "admin",
        )

        return submission


# ---------------------------------------------------------------------------
# 12-Mezon Grading Service (OpenRouter via OpenAI SDK)
# Used by: essay_create_view (free-form essay flow)
# ---------------------------------------------------------------------------

# Allowed scores for each criterion
ALLOWED_SCORES = {Decimal("0"), Decimal("0.5"), Decimal("1"), Decimal("1.5"), Decimal("2")}


def _validate_result(result: dict) -> None:
    """
    Validate the parsed JSON result from LLM.

    Checks:
        1. 'criteria' key exists and is a list of exactly 12 items
        2. Each criterion has 'id', 'name', 'score'
            ('reason'/'errors' ixtiyoriy — normalize bosqichida "" / []
            bilan to'ldiriladi, chunki ba'zi modellar ularni yozmaydi)
        3. Each score is in {0, 0.5, 1, 1.5, 2}
        4. 'total_score' and 'max_score' are present (recomputed, never trusted)
        5. Optional 'errors' is normalized to a short list of evidence snippets
    """
    if not isinstance(result, dict):
        raise ValueError("Result must be a dict")

    criteria = result.get("criteria")
    if not isinstance(criteria, list) or len(criteria) != 12:
        raise ValueError(
            f"'criteria' must be a list of 12 items, got {len(criteria) if isinstance(criteria, list) else type(criteria)}"
        )

    for i, c in enumerate(criteria, 1):
        if not isinstance(c, dict):
            raise ValueError(f"Criterion #{i} must be a dict")

        for field in ("id", "name", "score"):
            if field not in c:
                raise ValueError(f"Criterion #{i} missing '{field}'")

        score = c["score"]
        try:
            if isinstance(score, bool):
                raise InvalidOperation
            score_decimal = Decimal(str(score))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"Criterion #{i} score must be numeric") from exc
        if not score_decimal.is_finite():
            raise ValueError(f"Criterion #{i} score must be finite")
        if score_decimal not in ALLOWED_SCORES:
            raise ValueError(
                f"Criterion #{i} score {score} not in allowed set {ALLOWED_SCORES}"
            )

        try:
            if isinstance(c["id"], bool) or str(c["id"]) != str(int(c["id"])):
                raise ValueError
            criterion_id = int(c["id"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Criterion #{i} id must be an integer") from exc
        if criterion_id not in VALID_CRITERION_IDS:
            raise ValueError(f"Criterion #{i} id is outside 1..12")
        c["id"] = criterion_id
        if not isinstance(c["name"], str) or not c["name"].strip():
            raise ValueError(f"Criterion #{i} name must be non-empty text")
        if not isinstance(c.get("reason", ""), str):
            raise ValueError(f"Criterion #{i} reason must be text")
        if len(c["name"]) > 300 or len(c.get("reason", "")) > 4000:
            raise ValueError(f"Criterion #{i} text is too long")

        # Optional evidence snippets ("errors"): model topgan xatolarning
        # esse matnidan qisqa iqtiboslari. Noto'g'ri tip kelda — bo'sh ro'yxat;
        # har bir element matnga aylantirilib, 200 belgigacha qisqartiriladi,
        # jami 6 tadan ko'pi saqlanmaydi (DB raw_result JSON shishmasligi uchun).
        raw_errors = c.get("errors", [])
        if not isinstance(raw_errors, list):
            raw_errors = []
        errors: list[str] = []
        for e in raw_errors[:6]:
            if isinstance(e, str):
                snippet = e.strip()
            else:
                try:
                    snippet = str(e).strip()
                except Exception:
                    continue
            if snippet:
                errors.append(snippet[:200])
        c["errors"] = errors
        # Har bir mezon maksimumi qat'iy 2 (BBA rubrikasi).
        c["max_score"] = 2

    criterion_ids = [c["id"] for c in criteria]
    if set(criterion_ids) != VALID_CRITERION_IDS or len(set(criterion_ids)) != 12:
        raise ValueError("Criteria must contain each canonical id 1..12 exactly once")

    # Model-provided totals are never authoritative.
    result["total_score"] = float(sum(
        Decimal(str(c["score"])) for c in criteria
    ))
    result["max_score"] = 24
    if not isinstance(result.get("summary"), str) or len(result["summary"]) > 8000:
        raise ValueError("'summary' must be text of at most 8000 characters")

    # topic_match is optional (backward-compatible with old cached results)
    if "topic_match" in result and not isinstance(result["topic_match"], bool):
        raise ValueError("'topic_match' must be a boolean")


def _strip_thinking_tags(text: str) -> str:
    """Strip thinking/reasoning tags that some models (Qwen, etc.) return.

    Models like qwen3 wrap their reasoning in <thinking>...</thinking> or
    <tool_call>...</tool_call> tags. We need to strip these to get the actual JSON response.
    """
    if not text:
        return text

    # Strip <tool_call>...</tool_call> (Qwen thinking)
    text = re.sub(r"<tool_call>.*?</tool_call>", "", text, flags=re.DOTALL)
    # Strip <thinking>...</thinking> (generic)
    text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL)
    # Strip <think>...</think> (some models)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Strip <think>...</think> (DeepSeek style)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Strip <reasoning>...</reasoning> (some models)
    text = re.sub(r"<reasoning>.*?</reasoning>", "", text, flags=re.DOTALL)

    return text.strip()


def _try_load_json(text: str) -> dict | None:
    """json.loads — muvaffaqiyatli va natija dict bo'lsa qaytaradi, aks holda None."""
    if not text or not text.strip():
        return None
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None


def _extract_json_block(text: str) -> str | None:
    """Birinchi `{` dan oxirgi `}` gacha bo'lgan blokni ajratadi.

    Bu "Here's a thinking process: ..." kabi fikrlash matni oldida yozilgan
    holatlarda JSON ob'ektini tekstdan uzib oladi.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start:end + 1]


def _parse_failed_result() -> dict:
    """Buzilgan javob uchun xavfsiz fallback — chaqiruvchi `_parse_failed`ni tekshiradi."""
    return {
        "_parse_failed": True,
        "criteria": [],
        "total_score": 0,
        "max_score": 24,
        "summary": "",
    }


def parse_llm_json(raw_text: str) -> dict:
    """
    LLM javobidan JSON ob'ektni mustahkam ajratib olish va buzilgan JSON'ni
    imkon qadar ta'mirlash. Hech qachon exception qo'tarmaydi.

    Nima qiladi:
      1. Thinking teglarini (<thinking>, <tool_call>, …) va markdown
         ```json … ``` qobig'ini tozalaydi.
      2. Modellar xato qiladigan `\'` kabi yaroqsiz escape'larni tuzatadi
         (bu "Invalid \\escape" xatosining manbai edi).
      3. To'g'ridan-to'g'ri json.loads() — yoki regex bilan birinchi `{` dan
         oxirgi `}` gacha blokni ajratib parse qiladi (fikrlash matni ichida
         JSON yashirilgan bo'lsa — "Expecting value" xatosining manbai edi).
      4. To'liq ob'ektdan keyin qo'shimcha tekst bo'lsa raw_decode ishlaydi;
         kesilgan JSON uchun cheklangan (5 urinish) qisqartirish ta'mirlashi.
      5. Hammasi muvaffaqiyatsiz bo'lsa — xavfsiz fallback dict qaytaradi
         ("_parse_failed": True). Chaqiruvchi bu belgi orqali retry qiladi.
    """
    if not raw_text or not raw_text.strip():
        return _parse_failed_result()

    text = _strip_thinking_tags(raw_text)

    # Markdown qobig'i: ```json ... ```
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)
    text = text.strip()

    # Umumiy model xatosi: JSON ichida `\'` (PHP/JS uslubidagi escape).
    # JSON'da bu yaroqsiz — oddiy `'` ga aylantiramiz (`\'` JSON'da hech
    # qachon legitim emas, boshqa escape'larga ta'sir qilmaydi).
    text = re.sub(r"\\'", "'", text)

    # 1) To'g'ridan-to'g'ri parse
    result = _try_load_json(text)
    if result is not None:
        return result

    # 2) Fikrlash matni orasidagi JSON blok: birinchi `{` dan oxirgi `}` gacha
    block = _extract_json_block(text)
    if block is not None:
        result = _try_load_json(block)
        if result is not None:
            return result
        # 3) To'liq ob'ektdan keyin qo'shimcha tekst bo'lsa (raw_decode)
        try:
            obj, _ = json.JSONDecoder().raw_decode(block)
            if isinstance(obj, dict):
                return obj
        except (json.JSONDecodeError, ValueError):
            pass
        # 4) Kesilgan JSON: oxiridan boshlab qisqartirib, eng uzun to'liq
        #    prefiksni topishga urinish (cheklangan — 5 urinish).
        for _ in range(5):
            end = block.rfind("}")
            if end <= 0:
                break
            block = block[:end]
            result = _try_load_json(block)
            if result is not None:
                return result

    logger.warning(
        "parse_llm_json: JSON ajratib bo'lmadi (first 300 chars): %s",
        raw_text[:300],
    )
    return _parse_failed_result()


def _compute_text_hash(
    essay_text: str,
    topic_title: str = "",
    *,
    provider: str = "",
    model: str = "",
    mock_mode: bool = False,
    prompt_version: str = "v2",
    rubric_digest: str = "",
    language: str = "",
) -> str:
    """Compute SHA-256 hash of normalized essay text + topic.

    Includes topic_title so the same text under different topics
    produces different hashes (and potentially different topic_match).
    """
    norm_text = re.sub(r'\s+', ' ', essay_text.strip())
    norm_topic = topic_title.strip() if topic_title else ""
    combined = (
        f"{prompt_version}|{rubric_digest}|{language}|{provider}|{model}|mock={int(mock_mode)}|"
        f"{norm_topic}||{norm_text}"
    )
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def _grade_via_llm(client, candidates: list[str], user_message: str, system_prompt: str) -> tuple[dict, str]:
    """
    One full grading attempt: chat call (with fallback-model retry across
    ``candidates``) → extract → clean → parse JSON → validate.

    Uses strict JSON mode (response_format=json_object), low temperature and
    a compact token budget. Returns ``(validated_result, model_used)``. Raises
    ValueError on any failure (API error, empty reply, unparsable JSON,
    invalid structure) — the caller may retry with a simpler prompt.
    """
    try:
        response, model_used = _chat_with_fallback(
            client,
            candidates[0],
            candidates[1:],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            # Qat'iy JSON rejimi + past temperature + keng token budjeti:
            # model fikrlash matni yozmaydi, 12 mezonlik JSON yarmida
            # kesilmaydi ("Unterminated string" xatosining oldi olinadi).
            max_tokens=3000,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        error_str = str(e).lower()
        if "413" in error_str or "too large" in error_str or "rate" in error_str:
            logger.error("AI provider rate/TPM limit exceeded: model=%s", candidates)
            raise ValueError(
                "Esse juda uzun yoki tizim band. "
                "Iltimos, matnni biroz qisqartirib qayta yuboring."
            ) from e
        logger.error("AI provider API call failed: %s", e)
        raise ValueError(f"API xatolik: {e}") from e

    # --- Extract text from response ---
    raw_text = response.choices[0].message.content or ""
    if not raw_text.strip():
        logger.error("Empty response from LLM")
        raise ValueError("LLM bo'sh javob qaytardi")

    # --- Parse JSON (thinking text, code fences, `\'` escapes, truncation) ---
    result = parse_llm_json(raw_text)
    if result.get("_parse_failed"):
        logger.error(
            "Failed to parse LLM JSON (first 500 chars): %s",
            raw_text[:500],
        )
        raise ValueError("LLM javobini JSON formatida parse qilib bo'lmadi")

    # --- Normalize: ba'zi modellar 'reason'/'errors' yozmaydi → "" / [] bilan to'ldirish ---
    for c in result.get("criteria", []):
        if isinstance(c, dict):
            c.setdefault("reason", "")
            c.setdefault("errors", [])

    # --- Validate structure ---
    try:
        _validate_result(result)
    except ValueError as e:
        logger.error(
            "Validation failed (error=%s, first 500 chars): %s",
            e, raw_text[:500],
        )
        raise ValueError(f"LLM javob formati noto'g'ri: {e}") from e

    return result, model_used


def grade_essay(essay_text: str, topic_title: str = "") -> dict:
    """
    Grade an essay using OpenRouter LLM with the 12-mezon rubric.

    Args:
        essay_text: The essay text to grade.
        topic_title: The essay topic title (optional, for topic relevance check).

    Returns:
        dict with keys: criteria, total_score, max_score, summary,
                        topic_match, topic_match_reason, _from_cache, _mock_mode

    Raises:
        ValueError: If the LLM response cannot be parsed or validated.
        ImproperlyConfigured: If no API key is set and mock mode is off.
    """
    from .prompts import (
        ESSAY_GRADING_SYSTEM_PROMPT,
        ESSAY_GRADING_SYSTEM_PROMPT_SIMPLE,
        build_grading_message,
    )

    if not essay_text or not essay_text.strip():
        raise ValueError("Esse matni bo'sh")

    model = _get_ai_model()
    mock_mode = _is_mock_mode()
    provider = "mock" if mock_mode else _resolve_provider()
    prompt_version = getattr(settings, "ESSAY_GRADING_CACHE_VERSION", "v3")
    prompt_material = "|".join([
        ESSAY_GRADING_SYSTEM_PROMPT,
        ESSAY_GRADING_SYSTEM_PROMPT_SIMPLE,
        build_grading_message(essay_text, topic_title),
        ",".join(str(i) for i in sorted(VALID_CRITERION_IDS)),
    ])
    rubric_digest = hashlib.sha256(prompt_material.encode("utf-8")).hexdigest()

    # The key separates providers, models, mock data and rubric/prompt versions.
    text_hash = _compute_text_hash(
        essay_text,
        topic_title,
        provider=provider,
        model=model,
        mock_mode=mock_mode,
        prompt_version=prompt_version,
        rubric_digest=rubric_digest,
        language=getattr(settings, "LANGUAGE_CODE", "uz"),
    )
    from datetime import timedelta
    cache_lifetime_days = max(1, int(getattr(settings, "ESSAY_GRADING_CACHE_DAYS", 30)))
    cached = EssayGradingCache.objects.filter(
        text_hash=text_hash,
        created_at__gte=timezone.now() - timedelta(days=cache_lifetime_days),
    ).first()
    if cached is not None:
        # Cache hit — increment hit_count atomically and return cached result
        EssayGradingCache.objects.filter(pk=cached.pk).update(
            hit_count=F("hit_count") + 1,
        )
        result = cached.raw_result.copy()
        result["_from_cache"] = True
        logger.info(
            "Essay grading cache HIT: hash=%s, score=%s/%s, hit_count=%d",
            text_hash[:12], cached.total_score, cached.max_score, cached.hit_count + 1,
        )
        return result

    logger.info(
        "Starting essay grading: model=%s, text_length=%d, hash=%s, mock=%s",
        model, len(essay_text), text_hash[:12], mock_mode,
    )

    # --- Mock mode: return fake scores without calling API ---
    if mock_mode:
        logger.warning(
            "ESSAY_AI_MOCK_MODE=True — returning mock scores. "
            "Set OPENROUTER_API_KEY for real AI grading."
        )
        result = _mock_12_criteria_response(essay_text, topic_title)
        result.setdefault("topic_match", True)
        result.setdefault("topic_match_reason", "")
        result["_from_cache"] = False
        result["_mock_mode"] = True

        # Cache mock results too (they're deterministic per text+topic)
        try:
            EssayGradingCache.objects.create(
                text_hash=text_hash,
                essay_text=essay_text.strip(),
                raw_result=result,
                total_score=Decimal(str(result["total_score"])),
                max_score=result["max_score"],
            )
        except Exception as e:
            logger.warning("Failed to cache mock result: %s", e)

        return result

    # --- Call OpenRouter API via OpenAI SDK ---
    # Attempt 1: primary model (fallback-model retry inside for transient
    # errors). Attempt 2 (only on failure): candidate order reversed, so the
    # fallback model grades from scratch. Free models occasionally return
    # malformed JSON or ≠12 criteria; one clean re-grade fixes transient
    # quirks without ever accepting a malformed result.
    client = _get_llm_client()
    user_message = build_grading_message(essay_text, topic_title)

    candidates = _model_candidates()
    try:
        result, model = _grade_via_llm(client, candidates, user_message, ESSAY_GRADING_SYSTEM_PROMPT)
    except ValueError as first_err:
        # Parse/validation failure (≠12 criteria, malformed JSON, thinking text,
        # truncated reply, …): one re-grade with a SIMPLIFIED prompt and reversed
        # candidate order. Ixcham prompt bepul modellar uchun toza JSON qaytarish
        # ancha oson — birinchi urinishdagi transient quirk'lar shu bilan hal
        # bo'ladi, lekin buzilgan natija HECH QACHON qabul qilinmaydi.
        if len(candidates) > 1:
            logger.warning(
                "Grading attempt 1 failed (%s) — retrying with simplified prompt + reversed candidate order",
                first_err,
            )
            result, model = _grade_via_llm(
                client, list(reversed(candidates)), user_message,
                ESSAY_GRADING_SYSTEM_PROMPT_SIMPLE,
            )
        else:
            raise

    # --- Ensure topic_match fields exist (backward-compatible) ---
    result.setdefault("topic_match", True)
    result.setdefault("topic_match_reason", "")

    logger.info(
        "Essay grading completed: total_score=%s/%s, criteria_count=%d, topic_match=%s, model=%s",
        result["total_score"], result["max_score"], len(result["criteria"]),
        result["topic_match"], model,
    )

    # --- Save to cache (only real LLM results) ---
    try:
        EssayGradingCache.objects.update_or_create(
            text_hash=text_hash,
            defaults={
                "essay_text": essay_text.strip(),
                "raw_result": result,
                "total_score": Decimal(str(result["total_score"])),
                "max_score": result["max_score"],
            },
        )
        logger.info("Essay grading result cached: hash=%s", text_hash[:12])
    except Exception as e:
        # Non-fatal: if cache save fails, the grading still succeeded
        logger.warning("Failed to cache grading result: %s", e)

    result["_from_cache"] = False
    return result


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Improved Essay Version — AI-ga asoslangan yaxshilangan nusxa
# ---------------------------------------------------------------------------

IMPROVED_ESSAY_SYSTEM_PROMPT = """\
Siz o'zbek tili va adabiyoti fani bo'yicha ekspert muharrirsiz.
Sizga o'quvchining essesi, uning AI bahosi (12 mezon bo'yicha) va shu mezonlardagi
tanqid variantsi beriladi. Vazifangiz — essening YAXSHILANGAN versiyasini yozish.

QATIY QOIDALAR:
1. Esse mazmuni, asosiy g'oyalari va argumentlari SAQLANSHIN — yangi mavzu ochmang.
2. Lug'atni boyitiring, gaplarni ravon qiling, barcha imlo va punktuatsiya
   xatolarini tuzatish (milliy sertifikat 12 mezon bo'yicha eng yuqori daraja).
3. Har bir mezon bo'yicha tanqid qilingan joylarni tuzatish: uslub, ikkala qarash,
   dalillar, kompozitsiya, izchillik, leksik xilma-xillik.
4. Hajm taxminan asl esse bilan bir xil qolsin (±20%).
5. Yakuniy javobingizda yozgan yozing: <essay> va </essay> teglari ICHIDA faqat
   essening o'zini qaytaring. Teglardan TASHQARIDA hech narsa yozmang — izoh,
   reja, tahlil yoki tushuntirish qat'iyan taqiqlanadi.
"""

_IMPROVED_ESSAY_RE = re.compile(r"<essay>\s*(.*?)\s*</essay>", re.DOTALL | re.IGNORECASE)


def build_improve_message(essay_text: str, criteria_feedback: list[dict] | None, summary: str = "") -> str:
    """Build the user message for the improved-version request."""
    parts = [f"ASL ESSE:\n{essay_text.strip()}"]

    if criteria_feedback:
        lines = []
        for c in criteria_feedback:
            name = c.get("name", "?")
            score = c.get("score", "?")
            reason = (c.get("reason") or "").strip()
            line = f"- {name}: {score}/2"
            if reason:
                line += f" — {reason}"
            lines.append(line)
        parts.append("AI BAHOSI (12 mezon):\n" + "\n".join(lines))

    if summary:
        parts.append(f"AI XULOSASI:\n{summary}")

    parts.append(
        "Yuqoridagi tanqidlarni hisobga olib, essening to'liq YAXSHILANGAN "
        "versiyasini yozing. Faqat esse matnini qaytaring."
    )
    return "\n\n".join(parts)


def generate_improved_essay(submission: "EssaySubmission") -> str:
    """
    Generate an improved version of the student's essay using the AI provider
    (with the same primary/fallback model chain as grading).

    The result is persisted on ``submission.improved_content`` so repeated
    page loads never re-generate. Raises ValueError on API/validation failure.
    """
    # Already generated — return the stored version (idempotent).
    if submission.improved_content.strip():
        return submission.improved_content

    essay_text = (submission.essay_text or "").strip()
    if not essay_text:
        raise ValueError("Esse matni bo'sh — yaxshilash mumkin emas")

    # Respect the same length cap as grading.
    from .views import MAX_ESSAY_LENGTH  # local import avoids a cycle
    if len(essay_text) > MAX_ESSAY_LENGTH:
        raise ValueError("Esse juda uzun")

    client = _get_llm_client(timeout=45.0)  # bounded: sync web request
    candidates = _model_candidates()

    criteria_feedback = list(submission.raw_result.get("criteria", [])) if submission.raw_result else []
    user_message = build_improve_message(essay_text, criteria_feedback, submission.summary or "")

    logger.info(
        "Generating improved essay: submission=%s, model=%s, text_length=%d",
        submission.id, candidates[0], len(essay_text),
    )

    try:
        response, model_used = _chat_with_fallback(
            client,
            candidates[0],
            candidates[1:],
            messages=[
                {"role": "system", "content": IMPROVED_ESSAY_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=4096,
            temperature=0.4,  # slight creativity for vocabulary upgrades
            max_attempts=1,  # fail over fast; don't pin the web worker
        )
    except Exception as e:
        logger.error("Improved-essay generation failed: submission=%s, %s", submission.id, e)
        raise ValueError(f"API xatolik: {e}") from e

    raw = _strip_thinking_tags(response.choices[0].message.content or "").strip()

    # Extract the <essay>…</essay> block (reasoning models think outside it).
    match = _IMPROVED_ESSAY_RE.search(raw)
    if match:
        improved = match.group(1).strip()
    else:
        # Older behavior: whole reply minus code fences.
        improved = raw
        if improved.startswith("```"):
            lines = improved.split("\n")
            if lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            improved = "\n".join(lines).strip()

    if len(improved) < 50:
        logger.error(
            "Improved essay implausibly short (%d chars): submission=%s",
            len(improved), submission.id,
        )
        raise ValueError("AI javobi juda qisqa — qayta urinib ko'ring")

    submission.improved_content = improved
    submission.improved_at = timezone.now()
    submission.save(update_fields=["improved_content", "improved_at", "updated_at"])
    # In-memory marker so the view can tell "freshly generated" from a
    # cache hit (improved_at stays set forever after the first run).
    submission._improved_fresh = True
    logger.info(
        "Improved essay saved: submission=%s, model=%s, chars=%d",
        submission.id, model_used, len(improved),
    )
    return improved


# Auto-submit: vaqt tugaganda avtomatik baholash
# ---------------------------------------------------------------------------

# Statuses that may still be (re)graded. PENDING is included so a Celery
# task (or the broker-down sync fallback) can grade a submission that was
# already marked pending by the web view. Prevents double-grading: the
# task re-checks the status under a row lock before grading.
_GRADEABLE_STATUSES = frozenset({
    EssaySubmission.Status.DRAFT,
    EssaySubmission.Status.AI_EVALUATED,
    EssaySubmission.Status.PENDING,
})


def essay_has_grade_result(submission) -> bool:
    """Submission to'liq baholangani: baho/izoh bazaga yozilganmi.

    Faqat SHU holatda "Bu esse allaqachon baholangan" deb bloklash kerak.
    ERROR / PENDING_TEACHER / PENDING — bazada natija yo'q, qayta yuborish
    mumkin (user talabi: timeout bo'lsa, baho saqlanmaguncha qayta urinish
    ochiq qolsin).
    """
    if submission.final_score is not None:
        # Ustoz yakuniy balni qo'ygan — bloklaymiz.
        return True
    if submission.status in (
        EssaySubmission.Status.GRADED,
        EssaySubmission.Status.TEACHER_REVIEWED,
    ):
        return True
    if submission.status == EssaySubmission.Status.AI_EVALUATED:
        # Legacy 30-ballik tizim: AIEvaluation modelida natija saqlanganmi.
        # hasattr ishlatamiz — reverse OneToOne yo'q bo'lsa
        # RelatedObjectDoesNotExist (AttributeError'ningvorisi) ko'taradi.
        if hasattr(submission, "ai_evaluation"):
            return True
        # 12-mezon tizimi: raw_result JSON da haqiqiy javob bormi.
        return bool(submission.raw_result)
    return False


def _send_to_teacher(submission, reason: str, error_message: str = "") -> dict:
    """Mark a submission PENDING_TEACHER (fallback when AI can't grade it)."""
    submission.status = EssaySubmission.Status.PENDING_TEACHER
    submission.auto_submitted = True
    submission.submitted_at = timezone.now()
    if error_message:
        submission.error_message = error_message
    update_fields = ["status", "auto_submitted", "submitted_at", "updated_at"]
    if error_message:
        update_fields.append("error_message")
    submission.save(update_fields=update_fields)
    logger.info(
        "Essay → PENDING_TEACHER: submission=%d, reason=%s%s",
        submission.id, reason,
        f", error={error_message[:120]!r}" if error_message else "",
    )
    return {"success": True, "error": error_message or None, "fallback": True}


def apply_ai_result(submission, result: dict) -> None:
    """Write a validated grade_essay() result onto a submission.

    Persists scores/summary/status and (re)creates the 12 EssayCriterionScore
    rows. Shared by the Celery task, auto_submit_essay, and any sync fallback.
    """
    from .models import EssayCriterionScore

    submission.is_off_topic = not result.get("topic_match", True)
    submission.topic_match_reason = result.get("topic_match_reason", "")
    submission.raw_result = result
    submission.total_score = Decimal(str(result["total_score"]))
    submission.max_score = result["max_score"]
    submission.summary = result.get("summary", "")
    submission.status = EssaySubmission.Status.GRADED
    submission.graded_at = timezone.now()
    submission.save(update_fields=[
        "raw_result", "total_score", "max_score",
        "summary", "status", "graded_at", "updated_at",
        "is_off_topic", "topic_match_reason",
    ])

    submission.criteria.all().delete()
    for criterion in result["criteria"]:
        EssayCriterionScore.objects.create(
            submission=submission,
            criterion_id=criterion["id"],
            name=criterion["name"],
            score=Decimal(str(criterion["score"])),
            reason=criterion.get("reason", ""),
        )


def auto_submit_essay(submission, fail_status: str = "pending_teacher") -> dict:
    """
    Avtomatik baholash — vaqt tugaganda yoki brauzer yopilganda.

    AI xatoligida submission fail_status ga o'tkaziladi: default
    PENDING_TEACHER (fallback), manual submit yo'lida esa "error".

    Args:
        submission: EssaySubmission model instance.
        fail_status: status to set when the LLM call fails.

    Returns:
        {"success": bool, "error": str|None, "fallback": bool}
    """
    # Guard: only DRAFT/AI_EVALUATED/PENDING submissions may be graded.
    # Prevents the Celery beat task and a concurrent browser submit from
    # grading the same essay twice (duplicated EssayCriterionScore rows /
    # wasted LLM calls).
    if submission.status not in _GRADEABLE_STATUSES:
        return {"success": False, "error": "Essa allaqachon yakunlangan", "fallback": False}

    essay_text = submission.essay_text.strip()

    # Bo'sh matn → o'qituvchiga yuborish
    if not essay_text:
        return _send_to_teacher(submission, "empty")

    topic_title = submission.topic.title if submission.topic else ""
    word_count = WordCounter.count(essay_text)

    # Minimal so'z soni yetmasa → o'qituvchiga yuborish
    min_words = submission.topic.word_limit_min if submission.topic else 50
    if word_count < min_words:
        return _send_to_teacher(
            submission, f"under_min ({word_count} < {min_words})"
        )

    # AI baholashga urinish
    try:
        result = grade_essay(essay_text, topic_title=topic_title)
    except (ValueError, ImportError) as e:
        # AI xato → fail_status (PENDING_TEACHER fallback yoki ERROR)
        submission.auto_submitted = True
        submission.submitted_at = timezone.now()
        submission.status = fail_status
        submission.error_message = str(e)
        submission.save(update_fields=[
            "status", "auto_submitted", "submitted_at",
            "error_message", "updated_at",
        ])
        logger.error(
            "Auto-submit AI FAILED: submission=%d, error=%s → %s",
            submission.id, str(e), fail_status,
        )
        fallback = fail_status == EssaySubmission.Status.PENDING_TEACHER
        return {"success": False, "error": str(e), "fallback": fallback}

    # Muvaffaqiyatli baholash
    apply_ai_result(submission, result)
    submission.auto_submitted = True
    submission.submitted_at = timezone.now()
    submission.save(update_fields=["auto_submitted", "submitted_at", "updated_at"])

    logger.info(
        "Auto-submit GRADED: submission=%d, score=%s/%d",
        submission.id, submission.total_score, submission.max_score,
    )
    return {"success": True, "error": None, "fallback": False}


def start_async_grading(submission, *, fail_status: str = "pending_teacher") -> dict:
    """
    Web-path entry point for AI grading — never blocks a request thread.

    Cheap pre-checks (empty / under min-words) run inline; the slow LLM call
    is offloaded to the Celery task essays.grade_submission. If the broker is
    unreachable the grading runs in a daemon background thread instead of
    synchronously — a Redis outage must never pin a web request for 30–90s
    (that was the Cloudflare 502 root cause).

    Returns the same shape as auto_submit_essay plus "async": bool and "mode".
    """
    from apps.essays.tasks import grade_submission_task

    if submission.status not in _GRADEABLE_STATUSES:
        # Qayta yuborish (resubmit) mantiqi:
        # ERROR / PENDING_TEACHER holatida, lekin bazada AI natijasi YO'Q
        # bo'lsa (timeout yoki LLM xatosi sababli baholanmagan) — foydalanuvchi
        # qayta yuborishi mumkin: DRAFT'ga qaytaramiz va qayta baholaymiz.
        # Faqat to'liq baholangan (baho/izoh saqlangan) esse bloklanadi.
        if (
            submission.status
            in (
                EssaySubmission.Status.ERROR,
                EssaySubmission.Status.PENDING_TEACHER,
            )
            and not essay_has_grade_result(submission)
        ):
            old_status = submission.status
            submission.status = EssaySubmission.Status.DRAFT
            submission.error_message = ""
            submission.save(update_fields=["status", "error_message", "updated_at"])
            logger.info(
                "Essay resubmitted after failed grading: submission=%d (old status=%s)",
                submission.id, old_status,
            )
        else:
            return {
                "success": False,
                "error": "Bu esse allaqachon baholangan",
                "fallback": False,
                "async": False,
            }

    essay_text = submission.essay_text.strip()
    if not essay_text:
        return {**_send_to_teacher(submission, "empty"), "async": False}

    # Min-word contract only exists for topic-based submissions (the
    # submit-new form grades whatever non-empty text was provided). The
    # Celery task applies the same rule under its row lock.
    if submission.topic is not None:
        min_words = submission.topic.word_limit_min
        if WordCounter.count(essay_text) < min_words:
            return {**_send_to_teacher(submission, "under_min"), "async": False}

    # Mark as pending so the result page shows the spinner and any concurrent
    # submit is rejected by the status guard above.
    submission.status = EssaySubmission.Status.PENDING
    submission.save(update_fields=["status", "updated_at"])

    # Dev/test rejimida Celery eager bo'lsa (CELERY_TASK_ALWAYS_EAGER=True),
    # .delay() LLM chaqiruvini SHU request thread ichida sinxron bajaradi —
    # 30–90s bloklanib, Daphne "took too long to shut down" bilan o'ldiradi.
    # Eager rejimda ham baholashni background thread'ga tashlaymiz;
    # request darhol qaytadi, natija polling orqali ko'rinadi.
    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        result = start_thread_grading(submission, fail_status=fail_status)
        result["mode"] = "thread"
        return result

    try:
        grade_submission_task.delay(submission.id, fail_status=fail_status)
    except Exception as exc:
        # Redis/Celery tushib qolgan — request'ni 30–90s LLM chaqiruvi bilan
        # BLOKLAMAYMIZ (bu Cloudflare 502/524 sababi edi). Background
        # thread'da baholaymiz: request darhol qaytadi, natija polling orqali
        # ko'rinadi (start_thread_grading quyida).
        logger.warning(
            "Could not enqueue essay grading (broker down?): submission=%d, %s — background thread fallback",
            submission.id, exc,
        )
        result = start_thread_grading(submission, fail_status=fail_status)
        result["mode"] = "thread"
        return result

    logger.info("Essay grading enqueued: submission=%d", submission.id)
    return {"success": True, "error": None, "fallback": False, "async": True}


# ---------------------------------------------------------------------------
# Celery-siz yengil fallback: background thread (asyncio.create_task muqobili)
# ---------------------------------------------------------------------------

def start_thread_grading(submission, *, fail_status: str = "pending_teacher") -> dict:
    """Celery ishlamaganda AI baholashni background thread'da boshlash.

    asyncio.create_task'ga o'xshash yengil yechim, lekin barqaror: grade_essay()
    sinxron (OpenAI SDK + Django ORM) bo'lgani uchun uni event-loop'da emas,
    alohida thread'da ishga tushiramiz — daphne event-loop'ini hech qachon
    bloklamaydi. Request darhol qaytadi, natija DB ga yoziladi va sahifa
    polling orqali uni ko'radi.

    Thread daemon=True — server to'xtaganda kutib turmaydi. Celery'dan farqi:
        - restart bo'lsa task yo'qoladi (PENDING submission auto_submit_expired
          beat taski yoki qayta submit orqali tiklanadi)
        - retry'lar shu thread ichida qo'lda boshqariladi (quyida)

    Returns: start_async_grading bilan bir xil shakl + "async": True.
    """
    import threading

    from apps.essays.tasks import _mark_grading_failed, grade_submission_task

    def _is_still_gradeable() -> bool:
        # DB vaqtincha band bo'lsa (sqlite test lockout, failover va h.k.) —
        # xato sifatida emas, "baribir gradeable" deb davom etamiz: yakuniy
        # _mark_grading_failed baribir statusni lock ostida qayta tekshiradi.
        try:
            sub = EssaySubmission.objects.filter(pk=submission.pk).first()
        except Exception:
            logger.warning(
                "Could not check submission state (db busy?): submission=%d",
                submission.id,
            )
            return True
        return sub is not None and sub.status in _GRADEABLE_STATUSES

    def _run() -> None:
        try:
            # 3 urinish (Celery max_retries=2 + 1 boshlang'ich urinishga teng).
            # apply() — task shu thread'da lokal bajariladi (broker kerak emas).
            # Har qanday xatoda task o'zi retry() qo'taradi (yoki eager-propagate
            # rejimida asl exception'o'tadi) — ikkalasi ham ushlanadi.
            # Backoff: ESSAY_THREAD_RETRY_BACKOFF sozlamasi (default 5/10/15s).
            backoff = getattr(settings, "ESSAY_THREAD_RETRY_BACKOFF", None) or (5, 10, 15)
            last_exc: Exception | None = None
            for attempt in range(1, 4):
                try:
                    grade_submission_task.apply(
                        args=[submission.id],
                        kwargs={"fail_status": fail_status},
                    )
                    return  # graded / not_gradeable / missing — task tugadi
                except Exception as exc:  # Retry ham Exception (celery.exceptions.Retry)
                    last_exc = exc
                    logger.warning(
                        "Thread grading attempt %d failed: submission=%d, error=%s",
                        attempt, submission.id, exc,
                    )
                if not _is_still_gradeable():
                    # Konkurrent jarayon allaqachon yakunlagan yoki status o'zgargan
                    return
                time.sleep(min(backoff[attempt - 1], 15))

            # Barcha urinishlar tugadi — submission hech qachon PENDING'da
            # qotib qolmasin (Celery retry kontraktining thread-muqobili).
            if _is_still_gradeable():
                _mark_grading_failed(
                    submission.id, last_exc or Exception("thread grading failed"),
                )
        finally:
            # Thread'ning o'z DB ulanishi — daphne to'xtaganda "connection
            # already closed" yoki uzun yashovchi bo'sh ulanishlarni oldini olish.
            from django.db import close_old_connections

            close_old_connections()

    thread = threading.Thread(
        target=_run,
        name=f"essay-grade-{submission.id}",
        daemon=True,
    )
    thread.start()
    logger.info(
        "Essay grading started in background thread: submission=%d",
        submission.id,
    )
    return {"success": True, "error": None, "fallback": False, "async": True}


def start_grading(submission, *, fail_status: str = "pending_teacher") -> dict:
    """AI baholashni fon rejimida boshlash — broker'ga qarab yo'l tanlaydi.

    1. Celery worker + Redis ishlab tursa  → essays.grade_submission (Celery)
    2. Broker tushib qolgan bo'lsa         → background thread fallback

    Ikki holatda ham view request'ni darhol qaytaradi (status=PENDING,
    frontend "processing" spinner + polling). Sinxron grade_essay() chaqiruvi
    qolmagani uchun web thread HECH QACHON LLM'ni kutmaydi — Cloudflare
    502/524 timeout'lari yo'qoladi.

    Returns: {"success", "error", "fallback", "async", "mode"}.
    """
    result = start_async_grading(submission, fail_status=fail_status)
    # start_async_grading thread-fallback path'ida "mode": "thread" qo'yadi —
    # uni QAYTA YOZMAYMIZ (setdefault), aks holda thread fallback "celery"
    # deb noto'g'ri belgilanadi.
    result.setdefault(
        "mode",
        "celery" if result.get("async")
        else "inline" if result.get("fallback")
        else "sync",
    )
    return result


# ---------------------------------------------------------------------------
# Telegram: baholash tugaganda o'quvchiga xabar
# ---------------------------------------------------------------------------

def notify_student_essay_graded(submission) -> None:
    """AI baholash tugagach o'quvchining Telegram'iga natijani yuborish.

    Celery task tugashida chaqiriladi (background) — hech qachon request
    ichidan emas. telegram_chat_id bo'lmasa yoki Telegram API xato bersa —
    faqat log; baholash natijasi baribir DB da saqlanadi.
    """
    student = submission.student
    chat_id = getattr(student, "telegram_chat_id", None)
    if not chat_id or not getattr(student, "telegram_identity_verified_at", None):
        logger.info(
            "Essay graded, student has no telegram_chat_id — skipping: submission=%d, student=%s",
            submission.id, student.email,
        )
        return

    try:
        from apps.notifications.services.telegram_service import TelegramService

        topic_title = submission.topic.title if submission.topic else "Erkin mavzu"
        score = str(submission.total_score) if submission.total_score is not None else "-"
        max_score = str(submission.max_score) if submission.max_score else "24"
        is_passed = bool(submission.is_passed)
        converted = submission.converted_score
        status_line = (
            "✅ Tabriklaymiz — o'tdingiz!" if is_passed else "❌ Afsuski — o'tmadingiz."
        )

        text = (
            f"🤖 *Essingiz baholandi!*\n\n"
            f"📚 Mavzu: *{topic_title}*\n"
            f"📊 Ball: *{score}/{max_score}*"
        )
        if converted is not None:
            text += f"\n📈 Umumiy tizimda: *{converted}/75*"
        text += f"\n{status_line}\n\n"
        text += f"🔗 Batafsil: /essays/result/{submission.id}/"

        sent = TelegramService._send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="Markdown",
            notification_type="essay_graded",
            recipient=student,
            title=f"Esse baholandi: {topic_title}",
        )
        if not sent.get("success"):
            logger.warning(
                "Essay-graded Telegram notification failed: submission=%d, error=%s",
                submission.id, sent.get("error"),
            )
    except Exception as e:  # notification hech qachon baholashni buzmasin
        logger.warning(
            "Essay-graded notification error: submission=%d, %s", submission.id, e,
        )
