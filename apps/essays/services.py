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

import hashlib
import hmac
import json
import logging
import re
import secrets
import threading
import time
import unicodedata
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps
from typing import Any

import httpx
from billiard.exceptions import SoftTimeLimitExceeded

logger = logging.getLogger(__name__)

# Module-level semaphore for background thread grading (Phase 6 fix:
# previously lazy-initialized inside function -> race/thread-unsafe).
_THREAD_GRADE_SEMAPHORE = threading.Semaphore(3)

VALID_PROVIDERS = {"openrouter", "groq"}

# Key prefixes so a mismatched provider fails fast with a clear message
# instead of a confusing 401 "Missing Authentication header" from the API.
_PROVIDER_KEY_PREFIX = {
    "openrouter": "sk-or-",
    "groq": "gsk_",
}

# ---------------------------------------------------------------------------
# Django setup (at module level so service helpers are easy to mock)
# ---------------------------------------------------------------------------

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.core.cache import cache as default_cache
from django.db import IntegrityError, transaction as _db_txn
from django.db.models import Case, F, IntegerField, Q, Value, When
from django.utils import timezone as _timezone

from . import metrics

from .models import (
    EssayCriterionScore,
    EssayGradingCache,
    EssayRewriteCache,
    EssaySubmission,
    EssayTopic,
    TeacherReview,
    VALID_CRITERION_IDS,
)

# ---------------------------------------------------------------------------
# Canonical essay rubric version
# ---------------------------------------------------------------------------
# Persisted on exam written bridges and results so a historical writing score
# always identifies the rubric that produced it. Neutral internal identifier
# (UNVERIFIED against any official BMB rubric unless an authoritative source
# is supplied). Bump when the 12-criteria / 24-point semantics change; never
# rewrite history.
ESSAY_RUBRIC_VERSION = "grandec-essay-bmb-20p-v1"

# Raw rubric maximum: 12 criteria (BMB official scale, exactly 20.0 max score).
# Criteria 1-3, 7 max 2.0; Criteria 4-6, 8-12 max 1.5. Total = 20.0 points.
ESSAY_RUBRIC_MAX_SCORE = 20

# ---------------------------------------------------------------------------
# AI provider resolution (OpenRouter / Groq — OpenAI-compatible APIs)
# ---------------------------------------------------------------------------


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
        base_url = getattr(
            settings, "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        )
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
        # mode behind the Cloudflare 502s. max_retries=0 keeps retries
        # deterministic in our own _chat_with_fallback (worker's budget math
        # counts exactly the calls it sees — no hidden OpenAI retries).
        timeout=httpx.Timeout(timeout, connect=10.0),
        max_retries=0,
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
        "deepseek/deepseek-v4-flash-0731",
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
    import openai as _openai

    if isinstance(
        e,
        (
            TimeoutError,
            _openai.RateLimitError,
            _openai.APITimeoutError,
            _openai.APIConnectionError,
        ),
    ):
        return True
    status = getattr(e, "status_code", None)
    if isinstance(status, int) and (status >= 500 or status == 404):
        return True
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
    max_attempts: int = 1,
    response_format: dict | None = None,
    deadline: float | None = None,
    request_timeout: float | None = None,
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
        # Transient 429s/empty bodies on free models often clear in ~1s, but we
        # do not retry empty within the same model beyond the fallback chain;
        # one attempt per model keeps the total budget bounded.
        attempt = 0
        max_a = max(1, max_attempts)
        while attempt < max_a:
            tail = (
                f"; falling back to {next_model}" if next_model else "; chain exhausted"
            )
            try:
                kwargs = {
                    "model": candidate,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "messages": messages,
                }
                if use_json_mode:
                    kwargs["response_format"] = {"type": "json_object"}
                if deadline is not None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 1:
                        raise TimeoutError("AI grading request budget exhausted")
                    effective_timeout = min(request_timeout or remaining, remaining)
                    kwargs["timeout"] = httpx.Timeout(
                        effective_timeout,
                        connect=min(10.0, effective_timeout),
                    )
                response = client.chat.completions.create(**kwargs)
                content = (
                    response.choices[0].message.content if response.choices else None
                )
                if content and content.strip():
                    return response, candidate
                logger.warning(
                    "AI model %s returned an empty reply (attempt %d)%s",
                    candidate,
                    attempt + 1,
                    tail,
                )
                last_exc = ValueError("LLM bo'sh javob qaytardi")
            except Exception as e:
                if isinstance(e, SoftTimeLimitExceeded):
                    # Celery's task deadline is not a model failure. Let the
                    # task retry instead of converting it into a fatal 400.
                    raise
                if use_json_mode and _is_unsupported_response_format(e):
                    # Ba'zi modellar response_format=json_object ni qo'llamaydi
                    # (400 "Unsupported parameter: 'response_format'") — bu
                    # halokatli emas: shu modelni json-rejimsiz qayta urinamiz.
                    use_json_mode = False
                    logger.warning(
                        "AI model %s rejects response_format=json_object (%s) — retrying without it",
                        candidate,
                        e,
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
            attempt += 1
            if max_a > 1 and attempt == 1:
                time.sleep(0.6)

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
        normalized = re.sub(r"\s+", " ", text.strip())

        # Split by spaces
        words = normalized.split(" ")

        # Filter out empty strings and pure punctuation
        valid_words = []
        for w in words:
            w = w.strip()
            if w and re.search(r"[a-zA-ZА-Яа-яЁё]", w):
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


def _mock_12_criteria_response(
    essay_text: str, topic_title: str = ""
) -> dict[str, Any]:
    """Generate a mock 12-criteria response for frontend testing (BMB 20-point rubric)."""
    word_count = WordCounter.count(essay_text)
    base_2 = min(
        Decimal("2.0"),
        max(Decimal("0.5"), Decimal(str(min(2, max(0, word_count // 100))))),
    )
    base_1_5 = min(
        Decimal("1.5"),
        max(Decimal("0.5"), Decimal(str(min(1.5, max(0.5, word_count // 200))))),
    )

    if word_count < 200:
        comp_score = 1.0 if word_count >= 150 else 0.5
        comp_reason = f"[HAJM YETARLI EMAS] Esse {word_count} so'zdan iborat (minimal talab: 200 so'z). Kompozitsiya to'liq ochilmagan."
        summary_warning = f" Diqqat: esse hajmi yetarli emas ({word_count}/200 so'z), hajm mezoni bo'yicha ball kesildi."
    else:
        comp_score = float(base_2)
        comp_reason = "[SINOV REJIMI] Mock baholash"
        summary_warning = ""

    b2 = float(base_2)
    b15 = float(base_1_5)

    criteria = [
        {
            "id": 1,
            "name": EssayCriterionScore.CRITERION_NAMES[1],
            "score": b2,
            "max_score": 2.0,
            "reason": "[SINOV REJIMI] Mock baholash",
            "errors": [],
        },
        {
            "id": 2,
            "name": EssayCriterionScore.CRITERION_NAMES[2],
            "score": comp_score,
            "max_score": 2.0,
            "reason": comp_reason,
            "errors": [],
        },
        {
            "id": 3,
            "name": EssayCriterionScore.CRITERION_NAMES[3],
            "score": b2 if word_count >= 200 else min(b2, 1.0),
            "max_score": 2.0,
            "reason": "[SINOV REJIMI] Mock baholash",
            "errors": [],
        },
        {
            "id": 4,
            "name": EssayCriterionScore.CRITERION_NAMES[4],
            "score": b15,
            "max_score": 1.5,
            "reason": "[SINOV REJIMI] Mock baholash",
            "errors": [],
        },
        {
            "id": 5,
            "name": EssayCriterionScore.CRITERION_NAMES[5],
            "score": b15,
            "max_score": 1.5,
            "reason": "[SINOV REJIMI] Mock baholash",
            "errors": [],
        },
        {
            "id": 6,
            "name": EssayCriterionScore.CRITERION_NAMES[6],
            "score": b15,
            "max_score": 1.5,
            "reason": "[SINOV REJIMI] Mock baholash",
            "errors": [],
        },
        {
            "id": 7,
            "name": EssayCriterionScore.CRITERION_NAMES[7],
            "score": b2,
            "max_score": 2.0,
            "reason": "[SINOV REJIMI] Mock baholash",
            "errors": [],
        },
        {
            "id": 8,
            "name": EssayCriterionScore.CRITERION_NAMES[8],
            "score": b15,
            "max_score": 1.5,
            "reason": "[SINOV REJIMI] Mock baholash",
            "errors": [],
        },
        {
            "id": 9,
            "name": EssayCriterionScore.CRITERION_NAMES[9],
            "score": b15,
            "max_score": 1.5,
            "reason": "[SINOV REJIMI] Mock baholash",
            "errors": [],
        },
        {
            "id": 10,
            "name": EssayCriterionScore.CRITERION_NAMES[10],
            "score": b15,
            "max_score": 1.5,
            "reason": "[SINOV REJIMI] Mock baholash",
            "errors": [],
        },
        {
            "id": 11,
            "name": EssayCriterionScore.CRITERION_NAMES[11],
            "score": 1.5 if word_count >= 200 else (1.0 if word_count >= 150 else 0.5),
            "max_score": 1.5,
            "reason": f"Hajm: {word_count} so'z",
            "errors": [],
        },
        {
            "id": 12,
            "name": EssayCriterionScore.CRITERION_NAMES[12],
            "score": b15,
            "max_score": 1.5,
            "reason": "[SINOV REJIMI] Mock baholash",
            "errors": [],
        },
    ]

    total = sum(Decimal(str(c["score"])) for c in criteria)
    return {
        "criteria": criteria,
        "total_score": float(total),
        "max_score": ESSAY_RUBRIC_MAX_SCORE,
        "word_count": word_count,
        "summary": f"[SINOV REJIMI] {word_count} so'zlik esse.{summary_warning} Haqiqiy AI bahosi uchun OPENROUTER_API_KEY ni sozlang.",
        "topic_match": True,
        "topic_match_reason": "[SINOV REJIMI] Mock tekshiruv",
        "spelling_errors": [],
        "strengths": ["Mavzuni tushunish", "Mustaqil fikrlash"],
        "weaknesses": ["Lug'at boyligini oshirish kerak"],
        "teacher_recommendation": "Mavzu bo'yicha ko'proq adabiy va hayotiy misollar keltirish tavsiya etiladi.",
        "improved_text": essay_text,
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
    group = (
        StudentGroup.objects.filter(students=student).select_related("teacher").first()
    )
    if group and group.teacher:
        return group.teacher

    # No group → find admin
    admin_user = User.objects.filter(role="admin").first()
    if admin_user:
        return admin_user

    # Fallback: find any teacher
    return User.objects.filter(role="teacher").first()


def can_review_submission(user, submission: EssaySubmission) -> bool:
    """Object-level authorization for reading or grading an essay.

    Strict group isolation: teacher may review only if they teach at least
    one group containing the student (or are the assigned reviewer).
    Topic creator does NOT grant review rights alone — admin can grant
    explicit can_create_* flags for creation, not review.
    """
    from apps.accounts.access import is_platform_admin

    if not user or not user.is_authenticated or not user.is_active:
        return False
    if is_platform_admin(user):
        return True
    if getattr(user, "role", None) != "teacher":
        return False
    if submission.assigned_reviewer_id:
        return submission.assigned_reviewer_id == user.id
    return submission.student.student_groups.filter(teacher=user).exists()


def _escape_markdown(text: str) -> str:
    """Escape Telegram Markdown special chars to prevent injection (*, _, [, `)."""
    if not text:
        return ""
    return (
        text.replace("\\", "\\\\")
        .replace("*", "\\*")
        .replace("_", "\\_")
        .replace("[", "\\[")
        .replace("`", "\\`")
    )


def _notify_reviewer(submission, reviewer):
    """Notify reviewer about new essay review request via Telegram."""
    if (
        not reviewer
        or not getattr(reviewer, "telegram_chat_id", None)
        or not getattr(reviewer, "telegram_identity_verified_at", None)
    ):
        return

    try:
        from apps.notifications.services.telegram_service import TelegramService

        student_name = _escape_markdown(
            submission.student.get_full_name() or submission.student.email
        )
        topic_name = _escape_markdown(
            submission.topic.title if submission.topic else "Mavzu yo'q"
        )

        # Determine if it's student-requested
        is_student_request = submission.teacher_review_requested
        priority_text = (
            "🚨 O'quvchi e'tiroz bildirdi!"
            if is_student_request
            else "📝 Yangi esse tekshirish kerak"
        )

        text = (
            f"{priority_text}\n\n"
            f"👤 O'quvchi: *{student_name}*\n"
            f"📝 Mavzu: *{topic_name}*\n"
            f"🤖 AI baho: *{submission.total_score}/{submission.max_score}*\n"
        )

        if is_student_request and submission.teacher_review_reason:
            text += f"💬 Sabab: {_escape_markdown(submission.teacher_review_reason)}\n"

        text += f"\n🔗 Tekshirish: /essays/teacher/{submission.id}/review/"

        # Sync httpx call — safe inside Django views and Celery tasks without
        # any asyncio/event-loop juggling. Failures are logged, never raised.
        TelegramService.send_message_with_keyboard(
            chat_id=reviewer.telegram_chat_id,
            text=text,
            parse_mode="Markdown",
            notification_type="essay_review_request"
            if is_student_request
            else "general",
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
    @_db_txn.atomic
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
        if submission.status not in (
            EssaySubmission.Status.GRADED,
            EssaySubmission.Status.AI_EVALUATED,
            EssaySubmission.Status.PENDING_TEACHER,
        ):
            raise ValueError(
                f"Faqat baholangan esselarni tekshirish mumkin. Hozirgi holat: {submission.status}"
            )

        VALID_SCORES = {0.0, 0.5, 1.0, 1.5, 2.0}

        # Validate scores
        total_score = Decimal("0")
        validated_scores = {}

        for cid in range(1, 13):
            raw = criteria_scores.get(cid, 0)
            score = Decimal(str(raw))
            max_s = EssayCriterionScore.CRITERION_MAX_SCORES.get(cid, Decimal("2.0"))
            if score not in VALID_SCORES or score > max_s:
                raise ValueError(
                    f"Mezon #{cid}: ball {raw} yaroqsiz (maksimal: {max_s}). "
                    f"Ruxsat etilgan: {VALID_SCORES}"
                )
            total_score += score
            validated_scores[str(cid)] = float(score)

        total_score = min(total_score, Decimal(str(ESSAY_RUBRIC_MAX_SCORE)))

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

        # Update submission status — use transition guard so illegal jumps fail.
        try:
            submission.transition_to(EssaySubmission.Status.TEACHER_REVIEWED)
        except ValueError as e:
            raise ValueError(str(e)) from e
        submission.final_score = total_score
        submission.teacher_review_requested = False
        submission.save(
            update_fields=[
                "status",
                "final_score",
                "teacher_review_requested",
                "updated_at",
            ]
        )

        logger.info(
            "Teacher review submitted: submission=%d, teacher=%d, score=%s/24, created=%s",
            submission.id,
            teacher.id,
            total_score,
            created,
        )

        return review

    @staticmethod
    @_db_txn.atomic
    def request_teacher_review(
        submission: EssaySubmission,
        student,
        reason: str = "",
    ) -> EssaySubmission:
        """
        O'quvchi ustoz tekshiruvini so'raydi.

        Escalation logic:
          1. Agar o'quvchi guruhda bo'lsa → guruh o'qituvchisiga yuboriladi
          2. Agar guruhda bo'lmasa → sayt adminiga yuboriladi

        Updates submission status to PENDING_TEACHER.
        """
        submission = EssaySubmission.objects.select_for_update().get(pk=submission.pk)
        if (
            not student.is_authenticated
            or not student.is_active
            or submission.student_id != student.pk
        ):
            raise PermissionDenied("Bu esseni qayta ko'rishni so'rashga ruxsat yo'q.")
        if submission.status not in (
            EssaySubmission.Status.AI_EVALUATED,
            EssaySubmission.Status.GRADED,
        ):
            raise ValueError("Faqat AI baholangan esselarni ustozga yuborish mumkin.")

        reviewer = _find_reviewer_for_student(submission.student)
        submission.status = EssaySubmission.Status.PENDING_TEACHER
        submission.assigned_reviewer = reviewer
        submission.teacher_review_requested = True
        submission.teacher_review_requested_at = _timezone.now()
        submission.teacher_review_reason = reason
        submission.save(
            update_fields=[
                "status",
                "assigned_reviewer",
                "teacher_review_requested",
                "teacher_review_requested_at",
                "teacher_review_reason",
                "updated_at",
            ]
        )

        # Notify reviewer via Telegram
        _db_txn.on_commit(lambda: _notify_reviewer(submission, reviewer))

        logger.info(
            "Teacher review requested: submission=%d, student=%d, reviewer=%s",
            submission.id,
            submission.student_id,
            reviewer.email if reviewer else "admin",
        )

        return submission


# ---------------------------------------------------------------------------
# 12-Mezon Grading Service (OpenRouter via OpenAI SDK)
# Used by: essay_create_view (free-form essay flow)
# ---------------------------------------------------------------------------

# Allowed scores for each criterion
ALLOWED_SCORES = {
    Decimal("0"),
    Decimal("0.5"),
    Decimal("1"),
    Decimal("1.5"),
    Decimal("2"),
}
ALLOWED_SCORES_BY_MAX = {
    Decimal("2.0"): {
        Decimal("0"),
        Decimal("0.5"),
        Decimal("1"),
        Decimal("1.5"),
        Decimal("2"),
    },
    Decimal("1.5"): {Decimal("0"), Decimal("0.5"), Decimal("1"), Decimal("1.5")},
}

ALLOWED_TOP_KEYS = {
    "criteria",
    "total_score",
    "max_score",
    "summary",
    "topic_match",
    "topic_match_reason",
    "word_count",
    "spelling_errors",
    "strengths",
    "weaknesses",
    "teacher_recommendation",
    "improved_text",
}
ALLOWED_CRITERION_KEYS = {"id", "name", "score", "reason", "errors", "max_score"}


def _validate_result(result: dict, essay_text: str = "") -> None:
    """
    Validate the parsed JSON result from LLM (BMB 20-point rubric).

    Checks:
        1. 'criteria' key exists and is a list of exactly 12 items
        2. Each criterion has 'id', 'name', 'score'
            ('reason'/'errors' ixtiyoriy — normalize bosqichida "" / []
            bilan to'ldiriladi, chunki ba'zi modellar ularni yozmaydi)
        3. Each score is within the allowed set for that criterion:
           - Criteria 1-3, 7: max 2.0 (0, 0.5, 1, 1.5, 2)
           - Criteria 4-6, 8-12: max 1.5 (0, 0.5, 1, 1.5)
        4. 'total_score' and 'max_score' are present (recomputed, never trusted)
        5. Optional 'errors' is normalized to a short list of evidence snippets
        6. No unknown keys at top level or per-criterion (strict schema)
        7. Normalize spelling_errors, strengths, weaknesses, teacher_recommendation, improved_text
    """
    if not isinstance(result, dict):
        raise ValueError("Result must be a dict")

    # Strict unknown key rejection (Phase 6) — ignore ephemeral _-prefixed keys
    unknown_top = {k for k in result.keys() if not k.startswith("_")} - ALLOWED_TOP_KEYS
    if unknown_top:
        raise ValueError(f"Unknown top-level keys: {sorted(unknown_top)}")

    criteria = result.get("criteria")
    if not isinstance(criteria, list) or len(criteria) != 12:
        raise ValueError(
            f"'criteria' must be a list of 12 items, got {len(criteria) if isinstance(criteria, list) else type(criteria)}"
        )

    for i, c in enumerate(criteria, 1):
        if not isinstance(c, dict):
            raise ValueError(f"Criterion #{i} must be a dict")

        unknown_crit = {
            k for k in c.keys() if not k.startswith("_")
        } - ALLOWED_CRITERION_KEYS
        if unknown_crit:
            raise ValueError(f"Criterion #{i} unknown keys: {sorted(unknown_crit)}")

        for field in ("id", "name", "score"):
            if field not in c:
                raise ValueError(f"Criterion #{i} missing '{field}'")

        try:
            if isinstance(c["id"], bool) or str(c["id"]) != str(int(c["id"])):
                raise ValueError
            criterion_id = int(c["id"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Criterion #{i} id must be an integer") from exc
        if criterion_id not in VALID_CRITERION_IDS:
            raise ValueError(f"Criterion #{i} id is outside 1..12")
        c["id"] = criterion_id

        score = c["score"]
        try:
            if isinstance(score, bool):
                raise InvalidOperation
            score_decimal = Decimal(str(score))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"Criterion #{i} score must be numeric") from exc
        if not score_decimal.is_finite():
            raise ValueError(f"Criterion #{i} score must be finite")

        crit_max = EssayCriterionScore.CRITERION_MAX_SCORES.get(
            criterion_id, Decimal("2.0")
        )
        allowed_set = ALLOWED_SCORES_BY_MAX.get(crit_max, ALLOWED_SCORES)
        if score_decimal not in allowed_set or score_decimal > crit_max:
            raise ValueError(
                f"Criterion #{i} score {score} not in allowed set {allowed_set} (max: {crit_max})"
            )

        if not isinstance(c["name"], str) or not c["name"].strip():
            raise ValueError(f"Criterion #{i} name must be non-empty text")
        if not isinstance(c.get("reason", ""), str):
            raise ValueError(f"Criterion #{i} reason must be text")
        if len(c.get("reason", "")) > 4000:
            raise ValueError(f"Criterion #{i} reason is too long")
        # The model's label is not part of its grade. Persist the canonical
        # rubric label: EssayCriterionScore.name is varchar(100) in Postgres,
        # while a verbose model-generated label can be arbitrarily longer.
        c["name"] = EssayCriterionScore.CRITERION_NAMES[criterion_id]

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
        # Har bir mezon maksimumi (BMB 20-point rubrikasi).
        c["max_score"] = float(crit_max)

    criterion_ids = [c["id"] for c in criteria]
    if set(criterion_ids) != VALID_CRITERION_IDS or len(set(criterion_ids)) != 12:
        raise ValueError("Criteria must contain each canonical id 1..12 exactly once")

    # Qat'iy talab: 200-500 so'z. Agar matn 200 so'zdan kam bo'lsa, ogohlantirish qo'shiladi.
    raw_text = essay_text or str(result.get("_essay_text") or "")
    if raw_text:
        wc = WordCounter.count(raw_text)
        if 0 < wc < 200:
            warn_msg = f" [Hajm talabi: esse {wc} so'zdan iborat, tavsiya etilgan minimal hajm 200 so'z]"
            if (
                "summary" in result
                and isinstance(result["summary"], str)
                and warn_msg not in result["summary"]
            ):
                result["summary"] = (result["summary"].strip() + warn_msg).strip()

    # Model-provided totals are never authoritative.
    result["total_score"] = float(sum(Decimal(str(c["score"])) for c in criteria))
    result["max_score"] = ESSAY_RUBRIC_MAX_SCORE
    if not isinstance(result.get("summary"), str) or len(result["summary"]) > 8000:
        raise ValueError("'summary' must be text of at most 8000 characters")

    # Normalize spelling_errors: [{"word": str, "correction": str, "explanation": str}]
    raw_spelling = result.get("spelling_errors", [])
    spelling_errors = []
    if isinstance(raw_spelling, list):
        for item in raw_spelling[:25]:
            if isinstance(item, dict):
                w = str(item.get("word", "")).strip()[:100]
                corr = str(item.get("correction", "")).strip()[:100]
                exp = str(item.get("explanation", "")).strip()[:200]
                if w:
                    spelling_errors.append(
                        {"word": w, "correction": corr, "explanation": exp}
                    )
    result["spelling_errors"] = spelling_errors

    # Normalize strengths and weaknesses
    for key in ("strengths", "weaknesses"):
        raw_list = result.get(key, [])
        cleaned_list = []
        if isinstance(raw_list, list):
            for item in raw_list[:6]:
                if isinstance(item, str) and item.strip():
                    cleaned_list.append(item.strip()[:300])
        result[key] = cleaned_list

    # Normalize recommendations and improved_text
    for key in ("teacher_recommendation", "improved_text"):
        val = result.get(key, "")
        result[key] = str(val).strip()[:10000] if val else ""

    # Normalize word_count
    if "word_count" not in result or not isinstance(result["word_count"], int):
        result["word_count"] = WordCounter.count(raw_text) if raw_text else 0

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
    return text[start : end + 1]


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
    norm_text = re.sub(
        r"\s+",
        " ",
        unicodedata.normalize("NFC", essay_text).strip(),
    )
    norm_topic = (
        re.sub(
            r"\s+",
            " ",
            unicodedata.normalize("NFC", topic_title).strip(),
        )
        if topic_title
        else ""
    )
    identity = {
        "prompt_version": prompt_version,
        "rubric_digest": rubric_digest,
        "language": language,
        "provider": provider,
        "model": model,
        "mock_mode": bool(mock_mode),
        "topic": norm_topic,
        "essay": norm_text,
    }
    canonical_identity = json.dumps(
        identity,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical_identity.encode("utf-8")).hexdigest()


def _essay_grading_cache_identity(
    essay_text: str,
    topic_title: str = "",
    *,
    context: dict | None = None,
) -> tuple[str, str, bool, str]:
    """Return the context-aware cache key plus model/mode identity.

    Legacy 4-tuple wrapper around :func:`grading_cache_identity`; kept because
    the grading task and the regression tests read the grader identity here.
    """
    identity = grading_cache_identity(essay_text, topic_title, context=context)
    context = identity["context"]
    return (
        identity["cache_key"],
        _get_ai_model(),
        bool(context.get("mock_mode")),
        str(context.get("provider", "")),
    )


# ---------------------------------------------------------------------------
# Shared (cross-account) grading cache
# ---------------------------------------------------------------------------
# One eligible essay must not be paid for twice. The persistent, authoritative
# store is PostgreSQL (``EssayGradingCache``); Redis is only a fast lock hint in
# the rewrite path. The cache row is also the distributed leader lock:
# ``status`` + ``lease_owner`` + ``lease_expires_at`` guarantee exactly one AI
# request per cache key, recover abandoned leaders, and never let an expired
# lease overwrite a newer valid result.

_DEFAULT_CACHEABLE_SCOPES = ("practice",)
_CACHE_KEY_PURPOSE = "grandec-essay-cache-v2"


def normalize_essay_text(text: str) -> str:
    """Canonical, meaning-preserving essay normalization for fingerprinting.

    Unicode NFC, unified line endings, and every run of insignificant
    whitespace (spaces, tabs, newlines) collapsed to one space.

    Line wrapping is deliberately insignificant: the same essay pasted from a
    different editor/client must reuse its evaluation. Wording, spelling,
    punctuation and word order stay significant — a paraphrase is a different
    essay, and punctuation is never stripped.
    """
    if not text:
        return ""
    normalized = (
        unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    )
    return re.sub(r"\s+", " ", normalized).strip()


def _cache_pepper() -> str:
    """Dedicated, environment-managed fingerprint key (SECRET_KEY fallback)."""
    configured = (getattr(settings, "ESSAY_CACHE_FINGERPRINT_KEY", "") or "").strip()
    return configured or str(settings.SECRET_KEY)


def _cache_fingerprint(payload: Any) -> str:
    """Keyed HMAC-SHA256 fingerprint of a canonical JSON payload.

    The fingerprint is an opaque internal key: it is never an authorization
    mechanism and is never exposed to students.
    """
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hmac.new(
        f"{_CACHE_KEY_PURPOSE}:{_cache_pepper()}".encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def cacheable_scopes() -> frozenset[str]:
    """Assessment scopes allowed to reuse a grade across accounts."""
    configured = getattr(
        settings, "ESSAY_CACHE_ALLOWED_SCOPES", _DEFAULT_CACHEABLE_SCOPES
    )
    if isinstance(configured, str):
        configured = [p.strip() for p in configured.split(",") if p.strip()]
    return frozenset(configured or _DEFAULT_CACHEABLE_SCOPES)


def cache_scope_allows_reuse(scope: str | None) -> bool:
    """Supervised / restricted / high-stakes assessments are never shared."""
    return (scope or "practice") in cacheable_scopes()


def build_grading_context(
    *,
    topic=None,
    topic_title: str = "",
    scope: str | None = None,
    language: str | None = None,
) -> dict:
    """Every grading input that can change the evaluation result.

    Contains no student identity and no submission metadata — only the
    parameters that make two evaluations interchangeable.
    """
    from .prompts import ESSAY_GRADING_SYSTEM_PROMPT, ESSAY_GRADING_SYSTEM_PROMPT_SIMPLE

    if topic is not None:
        topic_id = topic.pk
        title = topic.title or ""
        topic_digest = _cache_fingerprint(
            {
                "title": title,
                "description": getattr(topic, "description", "") or "",
                "word_limit_min": getattr(topic, "word_limit_min", None),
                "word_limit_max": getattr(topic, "word_limit_max", None),
                "time_limit_minutes": getattr(topic, "time_limit_minutes", None),
                "category": getattr(topic, "category", "") or "",
            }
        )
    else:
        topic_id = None
        title = topic_title or ""
        topic_digest = _cache_fingerprint(
            {"title": title, "description": "", "free_form": True}
        )

    model_chain = _model_candidates()
    model_identity = ",".join(model_chain) or _get_ai_model()
    mock_mode = _is_mock_mode()
    provider = "mock" if mock_mode else _resolve_provider()
    prompt_version = str(getattr(settings, "ESSAY_GRADING_CACHE_VERSION", "v3"))
    rubric_digest = _cache_fingerprint(
        {
            "grading_prompt": ESSAY_GRADING_SYSTEM_PROMPT,
            "simple_prompt": ESSAY_GRADING_SYSTEM_PROMPT_SIMPLE,
            "criterion_ids": sorted(VALID_CRITERION_IDS),
            "prompt_version": prompt_version,
            "model_chain": model_identity,
        }
    )
    scoring_digest = _cache_fingerprint(
        {
            "target_scale": getattr(settings, "ESSAY_TARGET_SCALE", None),
            "off_topic_score": getattr(settings, "ESSAY_OFF_TOPIC_SCORE", None),
            "scoring_version": str(getattr(settings, "ESSAY_SCORING_VERSION", "v1")),
        }
    )
    return {
        "cache_schema_version": EssayGradingCache.CACHE_SCHEMA_VERSION,
        "scope": scope or "practice",
        "language": language or str(getattr(settings, "LANGUAGE_CODE", "uz")),
        "rubric_version": ESSAY_RUBRIC_VERSION,
        "prompt_version": prompt_version,
        "rubric_digest": rubric_digest,
        "model_chain": model_identity,
        "provider": provider,
        "mock_mode": mock_mode,
        "topic_id": topic_id,
        "topic_title": title,
        "topic_digest": topic_digest,
        "scoring_digest": scoring_digest,
    }


def grading_cache_identity(
    essay_text: str,
    topic_title: str = "",
    *,
    context: dict | None = None,
) -> dict:
    """Context-aware cache key + diagnostics for one grading request.

    ``cache_key = HMAC(canonical_json(normalized_essay + grading_context))``:
    the same text under a different topic, rubric version, prompt version,
    model chain, language, scoring configuration or scope is a different key.
    """
    context = (
        dict(context) if context else build_grading_context(topic_title=topic_title)
    )
    normalized = normalize_essay_text(essay_text)
    text_fingerprint = _cache_fingerprint({"text": normalized})
    context_fingerprint = _cache_fingerprint(context)
    cache_key = _cache_fingerprint({"text": normalized, "context": context})
    return {
        "cache_key": cache_key,
        "text_fingerprint": text_fingerprint,
        "context_fingerprint": context_fingerprint,
        "context": context,
        "cacheable": cache_scope_allows_reuse(context.get("scope")),
    }


def grading_context_for_submission(submission) -> dict:
    """Grading context for a submission (topic, scope, language)."""
    topic = submission.topic if submission.topic_id else None
    return build_grading_context(
        topic=topic,
        topic_title=(topic.title if topic is not None else ""),
        scope=getattr(submission, "cache_scope", None) or "practice",
    )


def grading_cache_key_for_submission(submission) -> str:
    """Cache key a submission's grade would occupy (no AI call)."""
    return grading_cache_identity(
        submission.essay_text or "",
        submission.topic.title if submission.topic_id else "",
        context=grading_context_for_submission(submission),
    )["cache_key"]


def stamp_grading_cache_key(submission) -> str:
    """Record the cache key on a submission before it starts grading.

    Lets a completed leader find and complete the submissions that are waiting
    on the same evaluation. Best-effort: a failure here must never block
    grading, so it only writes one indexed column.
    """
    try:
        key = grading_cache_key_for_submission(submission)
    except Exception:  # pragma: no cover - defensive
        logger.exception(
            "Could not compute grading cache key: submission=%s",
            getattr(submission, "pk", None),
        )
        return ""
    submission.grading_cache_key = key
    try:
        EssaySubmission.objects.filter(pk=submission.pk).update(grading_cache_key=key)
    except Exception:  # pragma: no cover - defensive
        logger.exception(
            "Could not stamp grading cache key: submission=%s", submission.pk
        )
    return key


def _discard_unusable_entry(entry, reason: str) -> None:
    """Drop a corrupt/obsolete entry unless a live leader currently owns it."""
    now = _timezone.now()
    if (
        entry.status == EssayGradingCache.Status.PROCESSING
        and entry.lease_expires_at is not None
        and entry.lease_expires_at > now
    ):
        logger.warning(
            "Unusable cache entry kept (active leader): hash=%s reason=%s",
            entry.text_hash[:12],
            reason,
        )
        return
    EssayGradingCache.objects.filter(pk=entry.pk).delete()
    metrics.cache_event(
        "entry_discarded", cache_key=entry.text_hash, reason=reason[:80]
    )


def _load_cached_grading_result(
    text_hash: str,
    *,
    context_fingerprint: str | None = None,
) -> dict | None:
    """Return a reusable validated grade (HIT) or ``None`` (MISS).

    A grade is reusable only when it is COMPLETED, schema-current, not
    invalidated, within the cache lifetime, matching the requested grading
    context, and still passing full rubric validation. A payload that no
    longer validates is discarded instead of served, so a corrupt row can
    never masquerade as a successful grade.
    """
    import copy

    cache_lifetime_days = max(1, int(getattr(settings, "ESSAY_GRADING_CACHE_DAYS", 30)))
    entry = EssayGradingCache.objects.filter(
        text_hash=text_hash,
        created_at__gte=_timezone.now() - timedelta(days=cache_lifetime_days),
    ).first()
    if entry is None:
        return None
    if (
        context_fingerprint
        and entry.grading_context_fingerprint
        and entry.grading_context_fingerprint != context_fingerprint
    ):
        metrics.cache_event("context_mismatch", cache_key=text_hash)
        return None
    if not entry.is_reusable():
        return None
    try:
        _validate_result(copy.deepcopy(entry.raw_result))
    except ValueError as exc:
        logger.warning(
            "Invalid cached essay result discarded: hash=%s, error=%s",
            text_hash[:12],
            exc,
        )
        _discard_unusable_entry(entry, f"invalid payload: {exc}")
        return None

    EssayGradingCache.objects.filter(pk=entry.pk).update(
        hit_count=F("hit_count") + 1,
        last_used_at=_timezone.now(),
    )
    result = copy.deepcopy(entry.raw_result)
    result["_from_cache"] = True
    result["_mock_mode"] = entry.provider == "mock"
    result["_cache_entry_pk"] = entry.pk
    metrics.cache_event(
        "hit",
        cache_key=text_hash,
        score=str(entry.total_score),
        reuse_count=entry.hit_count,
    )
    logger.info(
        "Essay grading cache HIT: hash=%s, score=%s/%s (reuse #%d)",
        text_hash[:12],
        entry.total_score,
        entry.max_score,
        entry.hit_count,
    )
    return result


class _CacheClaim:
    """Outcome of the atomic leader election for one cache key."""

    __slots__ = ("identity", "entry", "token", "is_leader")

    def __init__(self, identity: dict, entry, token: str, is_leader: bool) -> None:
        self.identity = identity
        self.entry = entry
        self.token = token
        self.is_leader = is_leader

    @property
    def cache_key(self) -> str:
        return self.identity["cache_key"]


def _claim_grading_cache_entry(identity: dict, essay_text: str) -> _CacheClaim:
    """Reserve the single grading operation for this cache key.

    Uses a UNIQUE constraint plus one conditional UPDATE (atomic on both
    PostgreSQL and SQLite) instead of a process-local lock, so two workers on
    different hosts cannot both become the leader for one key.
    """
    now = _timezone.now()
    lease_seconds = max(30, int(getattr(settings, "ESSAY_CACHE_LEASE_SECONDS", 300)))
    token = secrets.token_urlsafe(24)
    key = identity["cache_key"]
    context = identity["context"]

    entry = EssayGradingCache.objects.filter(text_hash=key).first()
    if entry is None:
        try:
            with _db_txn.atomic():
                entry = EssayGradingCache.objects.create(
                    text_hash=key,
                    essay_text=(essay_text or "")[:20000],
                    raw_result={},
                    total_score=Decimal("0"),
                    max_score=ESSAY_RUBRIC_MAX_SCORE,
                    status=EssayGradingCache.Status.PENDING,
                    hit_count=1,
                    cache_schema_version=EssayGradingCache.CACHE_SCHEMA_VERSION,
                    text_fingerprint=identity["text_fingerprint"],
                    grading_context_fingerprint=identity["context_fingerprint"],
                    grading_context=context,
                    rubric_version=context.get("rubric_version", ""),
                    prompt_version=context.get("prompt_version", ""),
                    model_identifier=context.get("model_chain", ""),
                    provider=context.get("provider", ""),
                )
        except IntegrityError:
            # A concurrent worker created it first — that is the expected race.
            entry = EssayGradingCache.objects.filter(text_hash=key).first()
            if entry is None:
                raise

    claimable = (
        Q(status=EssayGradingCache.Status.PENDING)
        | Q(status=EssayGradingCache.Status.FAILED, lease_expires_at__lte=now)
        | Q(status=EssayGradingCache.Status.FAILED, lease_expires_at__isnull=True)
        | Q(status=EssayGradingCache.Status.PROCESSING, lease_expires_at__lte=now)
        | Q(status=EssayGradingCache.Status.PROCESSING, lease_expires_at__isnull=True)
        | Q(status=EssayGradingCache.Status.COMPLETED, invalidated_at__isnull=False)
        # A completed row written under an older cache schema is historical
        # only: it must never match, but it must not deadlock the key either.
        | Q(
            status=EssayGradingCache.Status.COMPLETED,
            cache_schema_version__lt=EssayGradingCache.CACHE_SCHEMA_VERSION,
        )
    )
    claimed = (
        EssayGradingCache.objects.filter(pk=entry.pk)
        .filter(claimable)
        .update(
            status=EssayGradingCache.Status.PROCESSING,
            lease_owner=token,
            lease_expires_at=now + timedelta(seconds=lease_seconds),
            text_fingerprint=identity["text_fingerprint"],
            grading_context_fingerprint=identity["context_fingerprint"],
            grading_context=context,
            rubric_version=context.get("rubric_version", ""),
            prompt_version=context.get("prompt_version", ""),
            model_identifier=context.get("model_chain", ""),
            provider=context.get("provider", ""),
            cache_schema_version=EssayGradingCache.CACHE_SCHEMA_VERSION,
            invalidated_at=None,
            invalidated_reason="",
        )
    )
    if claimed == 1:
        metrics.cache_event("leader_claimed", cache_key=key)
        return _CacheClaim(identity, entry, token, True)

    # Someone else owns the operation: register as a waiting submission.
    EssayGradingCache.objects.filter(pk=entry.pk).update(
        waiting_count=F("waiting_count") + 1
    )
    metrics.cache_event("dedup_wait", cache_key=key)
    logger.info(
        "Essay grading deduplicated: hash=%s already in progress — waiting for the leader",
        key[:12],
    )
    return _CacheClaim(identity, entry, token, False)


def _complete_cache_entry(claim: _CacheClaim, result: dict) -> None:
    """Persist the validated canonical evaluation (only while still leader)."""
    clean = {k: v for k, v in result.items() if not k.startswith("_")}
    now = _timezone.now()
    updated = EssayGradingCache.objects.filter(
        pk=claim.entry.pk, lease_owner=claim.token
    ).update(
        status=EssayGradingCache.Status.COMPLETED,
        raw_result=clean,
        total_score=Decimal(str(clean["total_score"])),
        max_score=int(clean["max_score"]),
        completed_at=now,
        lease_owner="",
        lease_expires_at=None,
        error_summary="",
        failure_count=0,
        waiting_count=0,
        hit_count=Case(
            When(hit_count__lt=1, then=Value(1)),
            default=F("hit_count"),
            output_field=IntegerField(),
        ),
    )
    if not updated:
        # The lease expired and a newer leader took over: never overwrite it.
        metrics.cache_event("lease_lost", cache_key=claim.cache_key)
        logger.warning(
            "Essay grading lease lost before completion: hash=%s — newer leader keeps the entry",
            claim.cache_key[:12],
        )
        return
    metrics.cache_event(
        "completed",
        cache_key=claim.cache_key,
        score=str(clean["total_score"]),
    )
    logger.info(
        "Essay grading cache COMPLETED: hash=%s, score=%s/%s",
        claim.cache_key[:12],
        clean["total_score"],
        clean["max_score"],
    )


def _fail_cache_entry(claim: _CacheClaim, exc: BaseException) -> None:
    """Record a failed leader attempt — never a fake successful grade.

    A failed provider response must leave no cache artifact behind when nobody
    is waiting (an unusable AI reply is not a cache entry). When other
    submissions are waiting on the key, the row is kept as ``FAILED`` with a
    bounded retry delay so recovery happens exactly once and the AI provider is
    not stampeded.
    """
    now = _timezone.now()
    retry_delay = max(5, int(getattr(settings, "ESSAY_CACHE_RETRY_DELAY_SECONDS", 30)))
    summary = f"{type(exc).__name__}: {exc}"[:250]
    metrics.cache_event("failed", cache_key=claim.cache_key, error=summary[:80])
    deleted, _ = EssayGradingCache.objects.filter(
        pk=claim.entry.pk,
        lease_owner=claim.token,
        waiting_count__lte=0,
    ).delete()
    if deleted:
        logger.warning(
            "Essay grading failed, no cache artifact kept: hash=%s, error=%s",
            claim.cache_key[:12],
            summary,
        )
        return
    EssayGradingCache.objects.filter(pk=claim.entry.pk, lease_owner=claim.token).update(
        status=EssayGradingCache.Status.FAILED,
        failure_count=F("failure_count") + 1,
        error_summary=summary,
        lease_owner="",
        lease_expires_at=now + timedelta(seconds=retry_delay),
        hit_count=0,
        raw_result={},
        completed_at=None,
    )
    logger.warning(
        "Essay grading cache FAILED (waiters pending): hash=%s, error=%s",
        claim.cache_key[:12],
        summary,
    )


def _wait_for_cache_completion(
    claim: _CacheClaim, deadline: float
) -> tuple[dict | None, bool]:
    """Poll for the leader's result.

    Returns ``(result, retry_now)``. ``retry_now`` is True when the entry is
    FAILED and its retry delay has elapsed, so the caller should try to take
    over leadership (recovery after an abandoned leader).
    """
    key = claim.cache_key
    while True:
        result = _load_cached_grading_result(
            key,
            context_fingerprint=claim.identity["context_fingerprint"],
        )
        if result is not None:
            return result, False
        entry = (
            EssayGradingCache.objects.filter(pk=claim.entry.pk)
            .values("status", "lease_expires_at")
            .first()
        )
        if entry is None:
            return None, True
        if entry["status"] == EssayGradingCache.Status.FAILED:
            lease_until = entry["lease_expires_at"]
            if lease_until is None or lease_until <= _timezone.now():
                return None, True
        elif entry["status"] == EssayGradingCache.Status.PROCESSING:
            lease_until = entry["lease_expires_at"]
            if lease_until is not None and lease_until <= _timezone.now():
                # Expired leader — take over instead of waiting forever.
                return None, True
        if time.monotonic() >= deadline:
            return None, False
        time.sleep(0.25)


def _deduplicate_cached_grading(func):
    """Single-flight + shared-cache wrapper for a grading callable.

    Cache HIT → the canonical evaluation is returned without an AI call.
    Cache MISS → exactly one caller becomes the leader and pays for the AI
    request; the others register as waiters and apply the leader's validated
    result. Failures are recorded on the cache entry (never as a grade), and a
    timed-out waiter raises so the caller's retry/recovery path can take over.
    """

    @wraps(func)
    def wrapped(essay_text: str, topic_title: str = "", *args, **kwargs):
        if not essay_text or not essay_text.strip():
            return func(essay_text, topic_title, *args, **kwargs)

        context = kwargs.get("cache_context")
        identity = grading_cache_identity(essay_text, topic_title, context=context)
        if not identity["cacheable"]:
            # Supervised / restricted / high-stakes assessment: grade per
            # student, never reuse another account's evaluation.
            metrics.cache_event(
                "bypass_scope", scope=str(identity["context"].get("scope"))
            )
            return func(essay_text, topic_title, *args, **kwargs)

        wait_seconds = max(5, int(getattr(settings, "ESSAY_CACHE_WAIT_SECONDS", 200)))
        deadline = time.monotonic() + wait_seconds

        while True:
            cached = _load_cached_grading_result(
                identity["cache_key"],
                context_fingerprint=identity["context_fingerprint"],
            )
            if cached is not None:
                return cached

            claim = _claim_grading_cache_entry(identity, essay_text)
            if claim.is_leader:
                metrics.cache_event("miss", cache_key=claim.cache_key)
                started = time.monotonic()
                try:
                    result = func(essay_text, topic_title, *args, **kwargs)
                except Exception as exc:
                    _fail_cache_entry(claim, exc)
                    metrics.cache_event(
                        "provider_failure",
                        cache_key=claim.cache_key,
                        error=type(exc).__name__,
                    )
                    raise
                _complete_cache_entry(claim, result)
                metrics.cache_event(
                    "ai_request",
                    cache_key=claim.cache_key,
                    duration_ms=int((time.monotonic() - started) * 1000),
                )
                return result

            result, retry_now = _wait_for_cache_completion(claim, deadline)
            if result is not None:
                metrics.cache_event("reuse", cache_key=claim.cache_key)
                return result
            if retry_now:
                # Abandoned/failed leader — re-enter the loop and try to claim.
                continue
            raise TimeoutError(
                "Identical essay is still being graded by another account; retry shortly"
            )

    return wrapped


def apply_cached_grade_to_submission(submission, cache_key: str) -> bool:
    """Apply a completed canonical evaluation to one waiting submission.

    Each student keeps an independent ``EssaySubmission``; only the validated
    AI evaluation is shared. Returns True when this call graded the row.
    """
    if submission.status == EssaySubmission.Status.GRADED and essay_has_grade_result(
        submission
    ):
        # Idempotent: a repeated sweep (or a late Celery delivery) must not
        # re-apply the evaluation or duplicate criterion rows.
        return False
    result = _load_cached_grading_result(cache_key)
    if result is None:
        return False
    apply_ai_result(submission, result)
    return submission.status == EssaySubmission.Status.GRADED


def distribute_cached_grade(
    cache_key: str, *, exclude_submission_id: int | None = None
) -> int:
    """Complete every authorized submission waiting on one cache key.

    Idempotent: each row is re-checked under its own lock by
    :func:`apply_ai_result`, so a late Celery delivery cannot double-grade.
    """
    if not cache_key:
        return 0
    waiters = EssaySubmission.objects.filter(
        grading_cache_key=cache_key,
        status=EssaySubmission.Status.PENDING,
    )
    if exclude_submission_id is not None:
        waiters = waiters.exclude(pk=exclude_submission_id)
    applied = 0
    for submission in list(waiters):
        if not cache_scope_allows_reuse(submission.cache_scope):
            continue
        try:
            if apply_cached_grade_to_submission(submission, cache_key):
                applied += 1
                metrics.cache_event("distributed", submission_id=submission.pk)
                notify_student_essay_graded(submission)
        except Exception:  # pragma: no cover - defensive, one row must not break others
            logger.exception(
                "Failed to distribute cached grade: submission=%d key=%s",
                submission.pk,
                cache_key[:12],
            )
    if applied:
        logger.info(
            "Distributed cached grade to %d waiting submission(s): hash=%s",
            applied,
            cache_key[:12],
        )
    return applied


def recover_stale_grading_cache_entries() -> int:
    """Release abandoned leases so grading can never be blocked forever.

    A worker that dies mid-request leaves ``PROCESSING`` behind; expired or
    missing leases are moved to ``FAILED`` with a retry delay, which lets the
    next submission claim the key and grade it again.
    """
    now = _timezone.now()
    stale = EssayGradingCache.objects.filter(
        Q(status=EssayGradingCache.Status.PROCESSING, lease_expires_at__lt=now)
        | Q(status=EssayGradingCache.Status.PROCESSING, lease_expires_at__isnull=True)
    )
    count = stale.update(
        status=EssayGradingCache.Status.FAILED,
        lease_owner="",
        # Immediately claimable: the previous leader is gone, so the next
        # submission may take over right away (a *failed* leader keeps the
        # bounded retry delay so followers cannot stampede the provider).
        lease_expires_at=now,
        error_summary="stale lease recovered",
        failure_count=F("failure_count") + 1,
        hit_count=0,
        raw_result={},
        completed_at=None,
    )
    if count:
        metrics.cache_event("stale_lease_recovered", count=count)
        logger.warning("Recovered %d stale essay grading cache lease(s)", count)
    return count


def invalidate_cache_entry(entry, reason: str = "manually invalidated") -> None:
    """Admin/ops invalidation: the entry stops matching but history survives."""
    now = _timezone.now()
    EssayGradingCache.objects.filter(pk=entry.pk).update(
        invalidated_at=now,
        invalidated_reason=(reason or "")[:250],
        status=EssayGradingCache.Status.FAILED,
        lease_owner="",
        lease_expires_at=None,
    )
    metrics.cache_event(
        "invalidated", cache_key=entry.text_hash, reason=(reason or "")[:60]
    )


def purge_obsolete_cache_entries(*, keep_days: int | None = None) -> int:
    """Delete evaluations that can never be reused again.

    Obsolete = older schema version, invalidated, or beyond the cache
    lifetime. Completed, schema-current rows are preserved.
    """
    cache_lifetime_days = keep_days or max(
        1, int(getattr(settings, "ESSAY_GRADING_CACHE_DAYS", 30))
    )
    cutoff = _timezone.now() - timedelta(days=cache_lifetime_days)
    obsolete = EssayGradingCache.objects.filter(
        Q(cache_schema_version__lt=EssayGradingCache.CACHE_SCHEMA_VERSION)
        | Q(invalidated_at__isnull=False)
        | Q(created_at__lt=cutoff)
    )
    # Never delete an entry a live leader is working on.
    obsolete = obsolete.exclude(
        status=EssayGradingCache.Status.PROCESSING,
        lease_expires_at__gt=_timezone.now(),
    )
    deleted, _ = obsolete.delete()
    if deleted:
        metrics.cache_event("purged", count=deleted)
        logger.info("Purged %d obsolete essay grading cache entries", deleted)
    return deleted


def _grade_via_llm(
    client,
    candidates: list[str],
    user_message: str,
    system_prompt: str,
    simplified_prompt: str | None = None,
    *,
    deadline: float | None = None,
    request_timeout: float | None = None,
    essay_text: str = "",
) -> tuple[dict, str]:
    """
    Try each model until one returns a complete, valid rubric result.

    Uses strict JSON mode (response_format=json_object), low temperature and
    Fallback models use the simpler prompt. With a single configured model,
    retry that model once with the simpler prompt. A nonempty but malformed
    response must not stop the fallback chain or be saved as a grade.
    """
    attempts = [
        (model, system_prompt if index == 0 else simplified_prompt or system_prompt)
        for index, model in enumerate(candidates)
    ]
    if len(candidates) == 1 and simplified_prompt:
        attempts.append((candidates[0], simplified_prompt))

    last_error: Exception | None = None
    for model, prompt in attempts:
        try:
            response, model_used = _chat_with_fallback(
                client,
                model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=3000,
                temperature=0.1,
                response_format={"type": "json_object"},
                deadline=deadline,
                request_timeout=request_timeout,
            )
        except Exception as exc:
            if isinstance(exc, SoftTimeLimitExceeded):
                raise
            error_str = str(exc).lower()
            if _is_transient_ai_error(exc):
                # Keep the provider exception type so the Celery task retries
                # after the whole model chain has a temporary outage.
                last_error = exc
                logger.warning(
                    "AI grading model %s failed temporarily; trying next candidate: %s",
                    model,
                    exc,
                )
                continue
            if "413" in error_str or "too large" in error_str:
                last_error = ValueError(
                    "Esse juda uzun yoki tizim band. "
                    "Iltimos, matnni biroz qisqartirib qayta yuboring."
                )
            else:
                last_error = ValueError(f"API xatolik: {exc}")
            if _is_invalid_model_error(exc) or (
                isinstance(exc, ValueError) and str(exc) == "LLM bo'sh javob qaytardi"
            ):
                logger.warning(
                    "AI grading model %s failed; trying next candidate: %s", model, exc
                )
                continue
            logger.error("AI provider API call failed: model=%s, error=%s", model, exc)
            raise last_error from exc

        raw_text = response.choices[0].message.content or ""
        result = parse_llm_json(raw_text)
        if result.get("_parse_failed"):
            last_error = ValueError("LLM javobini JSON formatida parse qilib bo'lmadi")
            logger.warning(
                "AI grading model %s returned invalid JSON (first 500 chars): %s",
                model,
                raw_text[:500],
            )
            continue

        for criterion in (
            result.get("criteria", [])
            if isinstance(result.get("criteria"), list)
            else []
        ):
            if isinstance(criterion, dict):
                criterion.setdefault("reason", "")
                criterion.setdefault("errors", [])
        try:
            _validate_result(result, essay_text)
        except ValueError as exc:
            last_error = ValueError(f"LLM javob formati noto'g'ri: {exc}")
            logger.warning(
                "AI grading model %s returned invalid rubric (error=%s, first 500 chars): %s",
                model,
                exc,
                raw_text[:500],
            )
            continue
        return result, model_used

    raise last_error or ValueError("AI grading model chain is empty")


@_deduplicate_cached_grading
def grade_essay(
    essay_text: str,
    topic_title: str = "",
    *,
    cache_context: dict | None = None,
) -> dict:
    """
    Grade an essay using OpenRouter LLM with the 12-mezon rubric.

    Args:
        essay_text: The essay text to grade.
        topic_title: The essay topic title (optional, for topic relevance check).
        cache_context: Full grading context (topic, scope, rubric/prompt/model
            identity, language, scoring config) built with
            :func:`build_grading_context`. It is consumed by the shared-cache
            wrapper and never changes the grading rules themselves. Defaults to
            a practice-scope context derived from ``topic_title``.

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
    cache_key = grading_cache_identity(essay_text, topic_title, context=cache_context)[
        "cache_key"
    ]

    logger.info(
        "Starting essay grading: model=%s, text_length=%d, hash=%s, mock=%s",
        model,
        len(essay_text),
        cache_key[:12],
        mock_mode,
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
        # Mock grades are deterministic (and provider="mock" is part of the
        # cache context), so the shared-cache wrapper persists them too.
        return result

    # Share a 170s budget across the model chain. The primary model may use
    # the configured 60s timeout, while later calls use only the time left.
    # Celery's soft limit is 200s; a model may require a second call without
    # JSON mode.
    candidates = _model_candidates()
    if not candidates:
        raise ImproperlyConfigured("AI grading model sozlanmagan")
    configured_timeout = float(getattr(settings, "ESSAY_AI_REQUEST_TIMEOUT", 30.0))
    if configured_timeout <= 0:
        raise ImproperlyConfigured("ESSAY_AI_REQUEST_TIMEOUT musbat bo'lishi kerak")
    client = _get_llm_client(timeout=configured_timeout)
    user_message = build_grading_message(essay_text, topic_title)

    result, model = _grade_via_llm(
        client,
        candidates,
        user_message,
        ESSAY_GRADING_SYSTEM_PROMPT,
        ESSAY_GRADING_SYSTEM_PROMPT_SIMPLE,
        deadline=time.monotonic() + 170.0,
        request_timeout=configured_timeout,
        essay_text=essay_text,
    )

    # --- Ensure topic_match fields exist (backward-compatible) ---
    result.setdefault("topic_match", True)
    result.setdefault("topic_match_reason", "")

    logger.info(
        "Essay grading completed: total_score=%s/%s, criteria_count=%d, topic_match=%s, model=%s",
        result["total_score"],
        result["max_score"],
        len(result["criteria"]),
        result["topic_match"],
        model,
    )

    # Persistence of the canonical evaluation is owned by the shared-cache
    # wrapper (_deduplicate_cached_grading), which writes it under the leader
    # lease — never as an unconditional overwrite from a non-leader.
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

_IMPROVED_ESSAY_RE = re.compile(
    r"<essay>\s*(.*?)\s*</essay>", re.DOTALL | re.IGNORECASE
)


def build_improve_message(
    essay_text: str, criteria_feedback: list[dict] | None, summary: str = ""
) -> str:
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


def _essay_rewrite_cache_hash(submission: "EssaySubmission") -> str:
    """Hash essay, grading feedback, prompts, and provider/model for rewrites."""
    from .prompts import ESSAY_GRADING_SYSTEM_PROMPT, ESSAY_GRADING_SYSTEM_PROMPT_SIMPLE

    rewrite_model = _get_ai_model()
    rewrite_provider = "mock" if _is_mock_mode() else _resolve_provider()
    essay_text = (submission.essay_text or "").strip()
    rewrite_identity = {
        "version": "essay-rewrite-v1",
        "provider": rewrite_provider,
        "model_chain": _model_candidates() or [rewrite_model],
        "rubric_version": ESSAY_RUBRIC_VERSION,
        "topic": submission.topic.title if submission.topic_id else "",
        "prompt_digest": hashlib.sha256(
            (
                IMPROVED_ESSAY_SYSTEM_PROMPT
                + ESSAY_GRADING_SYSTEM_PROMPT
                + ESSAY_GRADING_SYSTEM_PROMPT_SIMPLE
            ).encode("utf-8")
        ).hexdigest(),
        "essay": re.sub(
            r"\s+",
            " ",
            unicodedata.normalize("NFC", essay_text).strip(),
        ),
        "grade_result": submission.raw_result or {},
        "summary": submission.summary or "",
    }
    rewrite_key = json.dumps(
        rewrite_identity,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(rewrite_key.encode("utf-8")).hexdigest()


def _load_cached_rewrite(
    submission: "EssaySubmission", rewrite_hash: str
) -> str | None:
    cached = EssayRewriteCache.objects.filter(text_hash=rewrite_hash).first()
    if cached is None:
        return None
    EssayRewriteCache.objects.filter(pk=cached.pk).update(
        hit_count=F("hit_count") + 1,
        last_used_at=_timezone.now(),
    )
    submission.improved_content = cached.improved_content
    submission.improved_at = _timezone.now()
    submission.save(update_fields=["improved_content", "improved_at", "updated_at"])
    submission._improved_fresh = False
    return cached.improved_content


def _deduplicate_rewrite(func):
    """Share an in-flight rewrite and cache result across identical submissions."""

    @wraps(func)
    def wrapped(submission: "EssaySubmission") -> str:
        if submission.improved_content.strip():
            return submission.improved_content

        essay_text = (submission.essay_text or "").strip()
        if not essay_text:
            raise ValueError("Esse matni bo'sh — yaxshilash mumkin emas")
        rewrite_hash = _essay_rewrite_cache_hash(submission)
        cached = _load_cached_rewrite(submission, rewrite_hash)
        if cached is not None:
            return cached

        lock_key = f"essay-rewrite-lock:{rewrite_hash}"
        lock_token = secrets.token_urlsafe(18)
        from django.core.cache import cache as django_cache

        acquired = django_cache.add(lock_key, lock_token, timeout=240)
        if not acquired:
            wait_until = time.monotonic() + 200
            while True:
                cached = _load_cached_rewrite(submission, rewrite_hash)
                if cached is not None:
                    return cached
                acquired = django_cache.add(lock_key, lock_token, timeout=240)
                if acquired:
                    break
                if time.monotonic() >= wait_until:
                    raise TimeoutError(
                        "Bir xil esse qayta yozilmoqda; birozdan keyin urinib ko'ring"
                    )
                time.sleep(0.25)

        try:
            cached = _load_cached_rewrite(submission, rewrite_hash)
            if cached is not None:
                return cached
            return func(submission, rewrite_hash)
        finally:
            try:
                if django_cache.get(lock_key) == lock_token:
                    django_cache.delete(lock_key)
            except Exception:
                logger.exception(
                    "Could not release essay rewrite lock: %s", rewrite_hash[:12]
                )

    return wrapped


@_deduplicate_rewrite
def generate_improved_essay(submission: "EssaySubmission", rewrite_hash: str) -> str:
    """
    Generate an improved version of the student's essay using the AI provider
    (with the same primary/fallback model chain as grading).

    The result is persisted on ``submission.improved_content`` so repeated
    page loads never re-generate. Raises ValueError on API/validation failure.
    """
    if submission.improved_content.strip():
        return submission.improved_content

    essay_text = (submission.essay_text or "").strip()
    if not essay_text:
        raise ValueError("Esse matni bo'sh — yaxshilash mumkin emas")

    # Respect the same length cap as grading.
    from .views import MAX_ESSAY_LENGTH  # local import avoids a cycle

    if len(essay_text) > MAX_ESSAY_LENGTH:
        raise ValueError("Esse juda uzun")

    if _is_mock_mode():
        # Mirror grade_essay mock behavior so improved version works offline
        # without burning API quota or hitting 401.
        improved = (
            essay_text
            + "\n\n[YAXSHILANGAN — SINOV REJIMI] Lug'at boyitildi, imlo va punktuatsiya to'g'rilandi."
        )
        submission.improved_content = improved
        submission.improved_at = _timezone.now()
        submission.save(update_fields=["improved_content", "improved_at", "updated_at"])
        try:
            EssayRewriteCache.objects.get_or_create(
                text_hash=rewrite_hash,
                defaults={"essay_text": essay_text, "improved_content": improved},
            )
        except Exception:
            logger.exception("Failed to cache mock rewrite: hash=%s", rewrite_hash[:12])
        submission._improved_fresh = True
        return improved

    client = _get_llm_client(timeout=45.0)  # bounded: sync web request
    candidates = _model_candidates()

    criteria_feedback = (
        list(submission.raw_result.get("criteria", [])) if submission.raw_result else []
    )
    user_message = build_improve_message(
        essay_text, criteria_feedback, submission.summary or ""
    )

    logger.info(
        "Generating improved essay: submission=%s, model=%s, text_length=%d",
        submission.id,
        candidates[0],
        len(essay_text),
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
        logger.error(
            "Improved-essay generation failed: submission=%s, %s", submission.id, e
        )
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
            len(improved),
            submission.id,
        )
        raise ValueError("AI javobi juda qisqa — qayta urinib ko'ring")

    submission.improved_content = improved
    submission.improved_at = _timezone.now()
    submission.save(update_fields=["improved_content", "improved_at", "updated_at"])
    try:
        EssayRewriteCache.objects.get_or_create(
            text_hash=rewrite_hash,
            defaults={"essay_text": essay_text, "improved_content": improved},
        )
    except Exception:
        logger.exception("Failed to cache rewrite: hash=%s", rewrite_hash[:12])
    # In-memory marker so the view can tell "freshly generated" from a
    # cache hit (improved_at stays set forever after the first run).
    submission._improved_fresh = True
    logger.info(
        "Improved essay saved: submission=%s, model=%s, chars=%d",
        submission.id,
        model_used,
        len(improved),
    )
    return improved


# Auto-submit: vaqt tugaganda avtomatik baholash
# ---------------------------------------------------------------------------

# Statuses that may still be (re)graded. PENDING is included so a Celery
# task (or the broker-down sync fallback) can grade a submission that was
# already marked pending by the web view. Prevents double-grading: the
# task re-checks the status under a row lock before grading.
_GRADEABLE_STATUSES = frozenset(
    {
        EssaySubmission.Status.DRAFT,
        EssaySubmission.Status.AI_EVALUATED,
        EssaySubmission.Status.PENDING,
    }
)


def expire_overdue_pending_grading(submission) -> bool:
    """Turn an orphaned ``PENDING`` grading job into a terminal real error.

    A successful queue publish does not prove that a worker will consume the
    task. An unavailable worker or a misconfigured queue previously left this
    status unchanged forever while every client kept polling.
    ``grading_started_at`` is never refreshed by the stale-job reaper, so it
    provides a stable deadline even when requeue attempts touch ``updated_at``.

    Returns ``True`` only when this call makes the terminal transition. The
    row is locked and rechecked so a concurrently persisted real grade always
    wins and is never overwritten.
    """
    if submission.status != EssaySubmission.Status.PENDING:
        return False

    timeout_seconds = max(
        1, int(getattr(settings, "ESSAY_GRADING_PENDING_TIMEOUT_SECONDS", 720))
    )
    now = _timezone.now()
    started_at = submission.grading_started_at or submission.updated_at
    if started_at is None or started_at > now - timedelta(seconds=timeout_seconds):
        return False

    with _db_txn.atomic():
        locked = (
            EssaySubmission.objects.select_for_update().filter(pk=submission.pk).first()
        )
        if locked is None or locked.status != EssaySubmission.Status.PENDING:
            return False
        started_at = locked.grading_started_at or locked.updated_at
        if started_at is None or started_at > now - timedelta(seconds=timeout_seconds):
            return False
        locked.status = EssaySubmission.Status.ERROR
        locked.error_message = (
            "AI baholash belgilangan vaqt ichida yakunlanmadi. "
            "Navbat yoki AI xizmati ishlamayotgan bo'lishi mumkin; "
            "iltimos, qayta urinib ko'ring."
        )
        locked.save(update_fields=["status", "error_message", "updated_at"])

    submission.status = locked.status
    submission.error_message = locked.error_message
    submission.updated_at = locked.updated_at
    logger.error(
        "Essay grading timed out while pending: submission=%d, started_at=%s",
        submission.pk,
        started_at,
    )
    return True


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
    submission.submitted_at = _timezone.now()
    if error_message:
        submission.error_message = error_message
    update_fields = ["status", "auto_submitted", "submitted_at", "updated_at"]
    if error_message:
        update_fields.append("error_message")
    submission.save(update_fields=update_fields)
    logger.info(
        "Essay → PENDING_TEACHER: submission=%d, reason=%s%s",
        submission.id,
        reason,
        f", error={error_message[:120]!r}" if error_message else "",
    )
    return {"success": True, "error": error_message or None, "fallback": True}


def apply_ai_result(submission, result: dict, *, cache_key: str | None = None) -> None:
    """Write a validated grade_essay() result onto a submission.

    Persists scores/summary/status and (re)creates the 12 EssayCriterionScore
    rows. Shared by the Celery task, auto_submit_essay, and any sync fallback.
    The whole transition is atomic so readers never see a GRADED row with a
    partial criterion set. Internal flags (_from_cache/_mock_mode/_errors
    handling keeps backward compat) are stripped before persistence, and any
    stale error_message is cleared on success.

    Grading provenance (Phase E): a reused shared evaluation is recorded as
    ``grading_source=cache`` with a reference to the cache row, so the UI can
    say "saqlangan AI baholash natijasi qo'llandi" without ever exposing the
    other account's activity.
    """
    from django.db import transaction as _txn

    from .models import EssayCriterionScore

    # Strip ephemeral execution metadata — they belong only in the cache /
    # in-memory result, not in the canonical submission row.
    clean_result = {k: v for k, v in result.items() if not k.startswith("_")}
    # Backward-compat: Error handling for persisted errors already stored.
    # No _from_cache/_mock_mode should survive in DB.

    with _db_txn.atomic():
        # Lock the row for the short write only — grading already finished.
        locked = (
            EssaySubmission.objects.select_for_update().filter(pk=submission.pk).first()
        )
        if locked is None:
            return
        # FSM guard: only a PENDING (or legacy gradeable) submission may
        # become GRADED. Duplicate/stale workers that lost the claim
        # must not overwrite a newer GRADED/ERROR/PENDING_TEACHER result.
        allowed = locked.STATUS_TRANSITIONS.get(locked.status, frozenset())
        if EssaySubmission.Status.GRADED not in allowed:
            logger.warning(
                "FSM drop: submission=%d status=%s cannot transition to GRADED — stale worker ignored",
                locked.pk,
                locked.status,
            )
            return

        locked.is_off_topic = not clean_result.get("topic_match", True)
        locked.topic_match_reason = clean_result.get("topic_match_reason", "")
        locked.raw_result = clean_result
        locked.total_score = Decimal(str(clean_result["total_score"]))
        locked.max_score = clean_result["max_score"]
        locked.summary = clean_result.get("summary", "")
        # Use validated transition.
        try:
            locked.transition_to(EssaySubmission.Status.GRADED)
        except ValueError as _ve:
            logger.warning(
                "FSM transition failed: submission=%d %s -> GRADED: %s",
                locked.pk,
                locked.status,
                _ve,
            )
            return
        locked.graded_at = _timezone.now()
        locked.error_message = ""
        if result.get("_from_cache"):
            locked.grading_source = EssaySubmission.GradingSource.CACHE
            entry_pk = result.get("_cache_entry_pk")
            if entry_pk:
                locked.grading_cache_id = entry_pk
        elif result.get("_mock_mode"):
            locked.grading_source = EssaySubmission.GradingSource.MOCK
        else:
            locked.grading_source = EssaySubmission.GradingSource.AI
        if cache_key and not locked.grading_cache_key:
            locked.grading_cache_key = cache_key
        update_fields = [
            "raw_result",
            "total_score",
            "max_score",
            "summary",
            "status",
            "graded_at",
            "updated_at",
            "is_off_topic",
            "topic_match_reason",
            "error_message",
            "grading_source",
            "grading_cache",
            "grading_cache_key",
        ]
        if clean_result.get("improved_text") and not locked.improved_content:
            locked.improved_content = clean_result["improved_text"]
            locked.improved_at = _timezone.now()
            update_fields.extend(["improved_content", "improved_at"])
        locked.save(update_fields=update_fields)

        locked.criteria.all().delete()
        rows = [
            EssayCriterionScore(
                submission=locked,
                criterion_id=criterion["id"],
                name=criterion["name"],
                score=Decimal(str(criterion["score"])),
                reason=criterion.get("reason", ""),
            )
            for criterion in clean_result["criteria"]
        ]
        EssayCriterionScore.objects.bulk_create(rows)
        # Update the caller's in-memory instance to reflect the committed state
        # so immediate callers (e.g. task notify) see the new scores.
        submission.raw_result = locked.raw_result
        submission.total_score = locked.total_score
        submission.max_score = locked.max_score
        submission.summary = locked.summary
        submission.status = locked.status
        submission.graded_at = locked.graded_at
        submission.is_off_topic = locked.is_off_topic
        submission.topic_match_reason = locked.topic_match_reason
        submission.error_message = locked.error_message
        submission.grading_source = locked.grading_source
        submission.grading_cache_id = locked.grading_cache_id
        submission.grading_cache_key = locked.grading_cache_key


def is_ielts_submission(submission) -> bool:
    """Return True if the submission belongs to an English IELTS / Multi-level topic."""
    topic = getattr(submission, "topic", None)
    if topic is None:
        return False
    return (
        getattr(topic, "subject", "") == "english"
        or str(getattr(topic, "rubric_type", "")).startswith("ielts")
        or getattr(topic, "category", "")
        in ("ielts_task1", "ielts_task2", "multilevel")
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
    if submission.status not in _GRADEABLE_STATUSES:
        return {
            "success": False,
            "error": "Essa allaqachon yakunlangan",
            "fallback": False,
        }

    essay_text = submission.essay_text.strip()

    # Bo'sh matn → o'qituvchiga yuborish
    if not essay_text:
        return _send_to_teacher(submission, "empty")

    topic_title = submission.topic.title if submission.topic else ""
    word_count = WordCounter.count(essay_text)
    ielts_mode = is_ielts_submission(submission)

    if not ielts_mode:
        # Minimal so'z soni yetmasa → o'qituvchiga yuborish
        min_words = submission.topic.word_limit_min if submission.topic else 200
        if word_count < min_words:
            return _send_to_teacher(
                submission, f"under_min ({word_count} < {min_words})"
            )

    # AI baholashga urinish
    cache_key = "" if ielts_mode else stamp_grading_cache_key(submission)
    cache_context = None if ielts_mode else grading_context_for_submission(submission)
    try:
        if ielts_mode:
            task_type = (
                getattr(submission.topic, "rubric_type", "ielts_task2") or "ielts_task2"
            )
            min_w = getattr(
                submission.topic,
                "word_limit_min",
                150 if task_type == "ielts_task1" else 250,
            )
            result = grade_ielts_essay(
                essay_text,
                topic_title=topic_title,
                task_type=task_type,
                min_words=min_w,
            )
        else:
            result = grade_essay(
                essay_text, topic_title=topic_title, cache_context=cache_context
            )
    except (ValueError, ImportError, ImproperlyConfigured) as e:
        submission.auto_submitted = True
        submission.submitted_at = _timezone.now()
        submission.status = fail_status
        submission.error_message = str(e)
        submission.save(
            update_fields=[
                "status",
                "auto_submitted",
                "submitted_at",
                "error_message",
                "updated_at",
            ]
        )
        logger.error(
            "Auto-submit AI FAILED: submission=%d, error=%s → %s",
            submission.id,
            str(e),
            fail_status,
        )
        fallback = fail_status == EssaySubmission.Status.PENDING_TEACHER
        return {"success": False, "error": str(e), "fallback": fallback}

    # Muvaffaqiyatli baholash
    apply_ai_result(submission, result, cache_key=cache_key)
    submission.auto_submitted = True
    submission.submitted_at = _timezone.now()
    submission.save(update_fields=["auto_submitted", "submitted_at", "updated_at"])
    if cache_key:
        distribute_cached_grade(cache_key, exclude_submission_id=submission.pk)

    logger.info(
        "Auto-submit GRADED: submission=%d, score=%s/%d",
        submission.id,
        submission.total_score,
        submission.max_score,
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
        if submission.status in (
            EssaySubmission.Status.ERROR,
            EssaySubmission.Status.PENDING_TEACHER,
        ) and not essay_has_grade_result(submission):
            old_status = submission.status
            submission.status = EssaySubmission.Status.DRAFT
            submission.error_message = ""
            submission.save(update_fields=["status", "error_message", "updated_at"])
            logger.info(
                "Essay resubmitted after failed grading: submission=%d (old status=%s)",
                submission.id,
                old_status,
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

    if submission.topic is not None and not is_ielts_submission(submission):
        min_words = submission.topic.word_limit_min
        if WordCounter.count(essay_text) < min_words:
            return {**_send_to_teacher(submission, "under_min"), "async": False}
    # Mark as pending so the result page shows the spinner and any concurrent
    # submit is rejected by the status guard above. Use conditional update so
    # two parallel submits cannot both claim the same row.
    grading_started_at = _timezone.now()
    cache_key = (
        "" if is_ielts_submission(submission) else stamp_grading_cache_key(submission)
    )
    claimed = EssaySubmission.objects.filter(
        pk=submission.pk, status__in=list(_GRADEABLE_STATUSES)
    ).update(
        status=EssaySubmission.Status.PENDING,
        grading_started_at=grading_started_at,
        updated_at=grading_started_at,
        grading_cache_key=cache_key,
    )
    if not claimed:
        # Retry/resubmit path: ERROR/PENDING_TEACHER without result → DRAFT was
        # already promoted above, so retry the claim.
        claimed = EssaySubmission.objects.filter(
            pk=submission.pk, status=EssaySubmission.Status.DRAFT
        ).update(
            status=EssaySubmission.Status.PENDING,
            grading_started_at=grading_started_at,
            updated_at=grading_started_at,
            grading_cache_key=cache_key,
        )
        if not claimed:
            return {
                "success": False,
                "error": "Bu esse allaqachon baholangan",
                "fallback": False,
                "async": False,
            }
    submission.refresh_from_db(fields=["status", "grading_started_at", "updated_at"])

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
            submission.id,
            exc,
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

    Concurrency: at most 3 concurrent grading threads (semaphore) and a
    hard per-thread deadline (120s) so a hung LLM does not leak threads.
    Returns: start_async_grading bilan bir xil shakl + "async": True.
    """
    from apps.essays.tasks import _mark_grading_failed, grade_submission_task

    if not _THREAD_GRADE_SEMAPHORE.acquire(blocking=False):
        # The broker is already unavailable (this is its fallback path), so
        # there is no durable queue to drain later. Leaving the row PENDING
        # here made the UI spin forever whenever all thread slots were busy.
        error = RuntimeError("AI baholash navbati band. Iltimos, qayta urinib ko'ring.")
        _mark_grading_failed(submission.id, error)
        logger.warning("Essay thread grading throttled: submission=%d", submission.id)
        return {
            "success": False,
            "error": str(error),
            "fallback": False,
            "async": False,
        }

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
            # Deadline: hard 120s per thread (matching idea of LLM budget).
            import time as _t

            deadline = _t.monotonic() + 120
            backoff = getattr(settings, "ESSAY_THREAD_RETRY_BACKOFF", None) or (
                5,
                10,
                15,
            )
            last_exc: Exception | None = None
            for attempt in range(1, 4):
                if _t.monotonic() > deadline:
                    last_exc = TimeoutError("thread grading deadline exceeded (120s)")
                    break
                try:
                    grade_submission_task.apply(
                        args=[submission.id],
                        kwargs={"fail_status": fail_status},
                    )
                    return  # graded / not_gradeable / missing — task tugadi
                except (
                    Exception
                ) as exc:  # Retry ham Exception (celery.exceptions.Retry)
                    last_exc = exc
                    logger.warning(
                        "Thread grading attempt %d failed: submission=%d, error=%s",
                        attempt,
                        submission.id,
                        exc,
                    )
                if not _is_still_gradeable():
                    # Konkurrent jarayon allaqachon yakunlagan yoki status o'zgargan
                    return
                remaining = deadline - _t.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(backoff[attempt - 1], 15, remaining))

            # Barcha urinishlar tugadi — submission hech qachon PENDING'da
            # qotib qolmasin (Celery retry kontraktining thread-muqobili).
            if _is_still_gradeable():
                _mark_grading_failed(
                    submission.id,
                    last_exc or Exception("thread grading failed"),
                )
        finally:
            # Thread'ning o'z DB ulanishi — daphne to'xtaganda "connection
            # already closed" yoki uzun yashovchi bo'sh ulanishlarni oldini olish.
            from django.db import close_old_connections

            close_old_connections()
            try:
                _THREAD_GRADE_SEMAPHORE.release()  # type: ignore[attr-defined]
            except Exception:
                pass

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
        "celery"
        if result.get("async")
        else "inline"
        if result.get("fallback")
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
    Idempotent: the same submission is never notified twice (NotificationLog
    idempotency key) even if the grade task is retried/redelivered.
    """
    from django.db import transaction as _txn2

    # Idempotency guard — if a SENT log already exists for this submission,
    # do not send again (retry-safe).
    try:
        from apps.notifications.models import NotificationLog

        if NotificationLog.objects.filter(
            related_essay_submission_id=submission.id,
            notification_type=NotificationLog.NotificationType.ESSAY_GRADED,
            status=NotificationLog.Status.SENT,
        ).exists():
            logger.info(
                "Essay graded notification already SENT — skipping duplicate: submission=%d",
                submission.id,
            )
            return
    except Exception:
        pass
    student = submission.student
    chat_id = getattr(student, "telegram_chat_id", None)
    if not chat_id or not getattr(student, "telegram_identity_verified_at", None):
        logger.info(
            "Essay graded, student has no telegram_chat_id — skipping: submission=%d, student=%s",
            submission.id,
            student.email,
        )
        return

    try:
        from apps.notifications.services.telegram_service import TelegramService

        topic_title = submission.topic.title if submission.topic else "Erkin mavzu"
        score = (
            str(submission.total_score) if submission.total_score is not None else "-"
        )
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

        sent = TelegramService.send_essay_graded(
            chat_id=chat_id,
            submission=submission,
            recipient=student,
        )
        if not sent.get("success"):
            logger.warning(
                "Essay-graded Telegram notification failed: submission=%d, error=%s",
                submission.id,
                sent.get("error"),
            )
        else:
            # Record idempotency key so retries do not duplicate Telegram sends.
            try:
                from apps.notifications.models import NotificationLog
                from django.utils import timezone as _tzN

                NotificationLog.objects.get_or_create(
                    related_essay_submission_id=submission.id,
                    notification_type=NotificationLog.NotificationType.ESSAY_GRADED,
                    channel=NotificationLog.Channel.TELEGRAM,
                    defaults={
                        "recipient": student,
                        "title": f"Esse baholandi: {topic_title}",
                        "message": text[:500],
                        "status": NotificationLog.Status.SENT,
                        "sent_at": _tzN.now(),
                    },
                )
            except Exception:
                logger.exception(
                    "Failed to write essay_graded NotificationLog idempotency record: submission=%d",
                    submission.id,
                )
    except Exception as e:  # notification hech qachon baholashni buzmasin
        logger.warning(
            "Essay-graded notification error: submission=%d, %s",
            submission.id,
            e,
        )


def generate_essay_result_pdf(submission: Any) -> Any:
    """Generate an official A4 PDF certificate/result sheet for an essay submission.

    Includes:
    - Official GRAND EDUCATION header & branding
    - Student info, essay topic, word count, date
    - Total score (out of 24) and converted score (out of 75)
    - 12 BMB criteria table with scores and reasons
    - AI / Teacher summary
    - QR Code linking to web verification URL
    """
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        Image,
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "PDFTitle",
        parent=styles["Title"],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1e293b"),
        alignment=1,
    )
    subtitle_style = ParagraphStyle(
        "PDFSubTitle",
        parent=styles["Normal"],
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#d97706"),
        alignment=1,
    )
    heading_style = ParagraphStyle(
        "PDFHeading",
        parent=styles["Heading2"],
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=10,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "PDFBody",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#334155"),
    )
    body_bold = ParagraphStyle(
        "PDFBodyBold",
        parent=body_style,
        fontName="Helvetica-Bold",
    )

    elements = []

    # Title header
    elements.append(
        Paragraph("<b>GRAND EDUCATION — MILLIY SERTIFIKAT TIZIMI</b>", title_style)
    )
    elements.append(
        Paragraph("<b>ESSE TAHLILI VA RASMIY NATIJA HUJJATI</b>", subtitle_style)
    )
    elements.append(Spacer(1, 14))

    # Student & Essay Info Table
    student = getattr(submission, "student", None)
    student_name = student.get_full_name() if student else "O'quvchi"
    if not student_name and student:
        student_name = student.email
    topic_title = (
        submission.topic.title if getattr(submission, "topic", None) else "Erkin mavzu"
    )
    date_str = (
        submission.created_at.strftime("%d.%m.%Y %H:%M")
        if getattr(submission, "created_at", None)
        else "-"
    )
    score_str = f"{submission.total_score or 0} / {submission.max_score or 20}"
    conv_str = f"{submission.converted_score or 0} / 75"
    status_str = (
        "O'TDI (Muvaffaqiyatli)"
        if getattr(submission, "is_passed", False)
        else "O'TMADI"
    )

    info_data = [
        [
            Paragraph("<b>O'quvchi:</b>", body_style),
            Paragraph(student_name, body_style),
            Paragraph("<b>Sana:</b>", body_style),
            Paragraph(date_str, body_style),
        ],
        [
            Paragraph("<b>Esse mavzusi:</b>", body_style),
            Paragraph(topic_title, body_style),
            Paragraph("<b>So'zlar soni:</b>", body_style),
            Paragraph(str(getattr(submission, "word_count", 0)), body_style),
        ],
        [
            Paragraph("<b>Umumiy ball:</b>", body_style),
            Paragraph(f"<b>{score_str}</b>", body_bold),
            Paragraph("<b>75 shkalada:</b>", body_style),
            Paragraph(f"<b>{conv_str}</b>", body_bold),
        ],
        [
            Paragraph("<b>Holat:</b>", body_style),
            Paragraph(status_str, body_bold),
            Paragraph("<b>Hujjat ID:</b>", body_style),
            Paragraph(f"ESSE-{submission.id:06d}", body_style),
        ],
    ]

    t_info = Table(info_data, colWidths=[80, 180, 80, 180])
    t_info.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("PADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    elements.append(t_info)
    elements.append(Spacer(1, 14))

    # 12 Criteria Table
    elements.append(
        Paragraph(
            "<b>12 Mezon bo'yicha batafsil baholash (BMB 20 ballik shkala):</b>",
            heading_style,
        )
    )

    criteria_table_data = [
        [
            Paragraph("<b>#</b>", body_bold),
            Paragraph("<b>Mezon nomi</b>", body_bold),
            Paragraph("<b>Ball</b>", body_bold),
            Paragraph("<b>Max</b>", body_bold),
            Paragraph("<b>Tahlil / Izoh</b>", body_bold),
        ]
    ]

    from apps.essays.models import EssayCriterionScore

    crit_maxes = EssayCriterionScore.CRITERION_MAX_SCORES

    criteria_qs = (
        list(submission.criteria.order_by("criterion_id"))
        if hasattr(submission, "criteria")
        else []
    )
    if criteria_qs:
        for c in criteria_qs:
            c_max = str(crit_maxes.get(c.criterion_id, 2.0))
            criteria_table_data.append(
                [
                    Paragraph(str(c.criterion_id), body_style),
                    Paragraph(c.name, body_style),
                    Paragraph(f"<b>{c.score}</b>", body_bold),
                    Paragraph(c_max, body_style),
                    Paragraph(c.reason[:180] if c.reason else "-", body_style),
                ]
            )
    else:
        for cid, cname in EssayCriterionScore.CRITERION_NAMES.items():
            c_max = str(crit_maxes.get(cid, 2.0))
            criteria_table_data.append(
                [
                    Paragraph(str(cid), body_style),
                    Paragraph(cname, body_style),
                    Paragraph("-", body_style),
                    Paragraph(c_max, body_style),
                    Paragraph("-", body_style),
                ]
            )

    t_crit = Table(criteria_table_data, colWidths=[24, 180, 44, 40, 234])
    t_crit.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("PADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    elements.append(t_crit)
    elements.append(Spacer(1, 12))

    # Summary
    if getattr(submission, "summary", ""):
        elements.append(Paragraph("<b>Umumiy xulosa va tavsiyalar:</b>", heading_style))
        elements.append(Paragraph(submission.summary, body_style))
        elements.append(Spacer(1, 10))

    # QR Code + Footer
    site_url = getattr(settings, "SITE_URL", "https://grandec.uz").rstrip("/")
    verify_url = f"{site_url}/essays/result/{submission.id}/"
    qr_img = None
    try:
        import qrcode

        qr = qrcode.QRCode(box_size=3, border=1)
        qr.add_data(verify_url)
        qr.make(fit=True)
        img_buf = BytesIO()
        qr.make_image(fill_color="black", back_color="white").save(
            img_buf, format="PNG"
        )
        img_buf.seek(0)
        qr_img = Image(img_buf, width=60, height=60)
    except Exception:
        pass

    footer_data = [
        [
            qr_img if qr_img else Paragraph("", body_style),
            Paragraph(
                f"<b>GRAND EDUCATION Rasmiy Baholash Tizimi</b><br/>"
                f"Ushbu hujjat elektron tarzda shakllantirilgan va haqiqiyligi platforma bazasida saqlanadi.<br/>"
                f"Tekshirish havolasi: <font color='#2563eb'>{verify_url}</font>",
                body_style,
            ),
        ]
    ]
    t_foot = Table(footer_data, colWidths=[70, 450])
    t_foot.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("PADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    elements.append(t_foot)

    doc.build(elements)
    buffer.seek(0)
    return buffer


# ---------------------------------------------------------------------------
# IELTS / Multi-level 4-Criteria AI Grader (Band 1.0 - 9.0)
# ---------------------------------------------------------------------------

IELTS_SYSTEM_PROMPT = """You are an certified Senior IELTS Writing Examiner.
Evaluate the candidate's English writing strictly according to the 4 official IELTS Writing assessment criteria on a Band scale from 1.0 to 9.0 (in 0.5 increments):
1. Task Achievement / Task Response (id: 1)
2. Coherence and Cohesion (id: 2)
3. Lexical Resource (id: 3)
4. Grammatical Range and Accuracy (id: 4)

Return ONLY a valid JSON object with the following structure:
{
  "topic_match": true,
  "topic_match_reason": "Brief explanation of how well the essay addresses the prompt.",
  "criteria": [
    {"id": 1, "name": "Task Achievement / Task Response", "score": 7.0, "reason": "Detailed feedback...", "errors": []},
    {"id": 2, "name": "Coherence and Cohesion", "score": 7.5, "reason": "Detailed feedback...", "errors": []},
    {"id": 3, "name": "Lexical Resource", "score": 7.0, "reason": "Detailed feedback...", "errors": []},
    {"id": 4, "name": "Grammatical Range and Accuracy", "score": 6.5, "reason": "Detailed feedback...", "errors": []}
  ],
  "overall_band": 7.0,
  "cefr_level": "C1",
  "summary": "Comprehensive examiner summary and band justification.",
  "strengths": ["Clear thesis and well-structured paragraphs", "Strong academic collocations"],
  "weaknesses": ["Occasional article/preposition slips", "Could expand counter-argument examples"],
  "spelling_errors": [
    {"word": "enviroment", "correction": "environment", "explanation": "Spelling error"}
  ],
  "teacher_recommendation": "Actionable study advice to improve by +0.5 to +1.0 Band.",
  "improved_text": "A Band 8.5+ model rewrite of the student's essay."
}
"""


def _round_ielts_band(value: float) -> float:
    """Round a raw average to the nearest 0.5 IELTS Band score in [1.0, 9.0]."""
    clamped = max(1.0, min(9.0, float(value)))
    return round(clamped * 2.0) / 2.0


def _band_to_cefr(band: float) -> str:
    """Map IELTS Band score to CEFR level."""
    if band >= 8.5:
        return "C2"
    if band >= 7.0:
        return "C1"
    if band >= 5.5:
        return "B2"
    if band >= 4.0:
        return "B1"
    return "A2"


def _validate_ielts_result(
    result: dict,
    essay_text: str = "",
    task_type: str = "ielts_task2",
    min_words: int = 250,
) -> dict:
    """Validate and normalize a 4-criterion IELTS Band 1.0–9.0 evaluation payload."""
    if not isinstance(result, dict):
        raise ValueError("IELTS result must be a dict")

    raw_criteria = result.get("criteria")
    if not isinstance(raw_criteria, list) or len(raw_criteria) < 4:
        raise ValueError("IELTS 'criteria' must contain 4 items")

    wc = (
        WordCounter.count(essay_text)
        if essay_text
        else int(result.get("word_count") or 0)
    )
    normalized_criteria = []

    for idx in range(1, 5):
        canonical_name = EssayCriterionScore.IELTS_CRITERION_NAMES[idx]
        item = next(
            (
                c
                for c in raw_criteria
                if isinstance(c, dict) and int(c.get("id", 0) or 0) == idx
            ),
            raw_criteria[idx - 1]
            if idx - 1 < len(raw_criteria) and isinstance(raw_criteria[idx - 1], dict)
            else {},
        )
        raw_score = item.get("score", 6.0)
        try:
            band_score = _round_ielts_band(float(raw_score))
        except (TypeError, ValueError):
            band_score = 6.0

        reason = str(item.get("reason") or "").strip()[:3000]
        # Apply official under-length penalty on Criterion 1 (Task Achievement / Response)
        if idx == 1 and 0 < wc < min_words:
            penalty = 1.5 if wc < (min_words * 0.6) else 1.0
            band_score = _round_ielts_band(max(1.0, band_score - penalty))
            penalty_note = f" [Word count penalty: {wc}/{min_words} minimum words required for {'Task 1' if task_type == 'ielts_task1' else 'Task 2'}.]"
            if penalty_note not in reason:
                reason = (reason + penalty_note).strip()

        raw_errors = item.get("errors", [])
        errors = [
            str(e).strip()[:200]
            for e in (raw_errors if isinstance(raw_errors, list) else [])[:6]
            if str(e).strip()
        ]

        normalized_criteria.append(
            {
                "id": idx,
                "name": canonical_name,
                "score": band_score,
                "max_score": 9.0,
                "reason": reason or f"{canonical_name} evaluated at Band {band_score}.",
                "errors": errors,
            }
        )

    overall_band = _round_ielts_band(sum(c["score"] for c in normalized_criteria) / 4.0)
    cefr = _band_to_cefr(overall_band)

    summary = str(result.get("summary") or "").strip()
    if not summary:
        summary = (
            f"Overall IELTS Band Score: {overall_band} ({cefr}). "
            f"Word count: {wc} words (minimum target: {min_words})."
        )
    if 0 < wc < min_words and "minimum" not in summary.lower():
        summary += f" Note: Your response is under the {min_words}-word minimum ({wc} words), which lowers Task Achievement/Response."

    raw_spelling = result.get("spelling_errors", [])
    spelling_errors = []
    if isinstance(raw_spelling, list):
        for sp in raw_spelling[:20]:
            if isinstance(sp, dict) and sp.get("word"):
                spelling_errors.append(
                    {
                        "word": str(sp.get("word", "")).strip()[:100],
                        "correction": str(sp.get("correction", "")).strip()[:100],
                        "explanation": str(sp.get("explanation", "")).strip()[:200],
                    }
                )

    strengths = [
        str(s).strip()[:300]
        for s in (
            result.get("strengths") if isinstance(result.get("strengths"), list) else []
        )[:6]
        if str(s).strip()
    ]
    weaknesses = [
        str(w).strip()[:300]
        for w in (
            result.get("weaknesses")
            if isinstance(result.get("weaknesses"), list)
            else []
        )[:6]
        if str(w).strip()
    ]

    return {
        "rubric_type": task_type
        if task_type in ("ielts_task1", "ielts_task2")
        else "ielts_task2",
        "topic_match": bool(result.get("topic_match", True)),
        "topic_match_reason": str(
            result.get("topic_match_reason")
            or "The response addresses the given prompt."
        )[:1000],
        "criteria": normalized_criteria,
        "overall_band": overall_band,
        "cefr_level": cefr,
        "total_score": overall_band,
        "max_score": 9,
        "word_count": wc,
        "min_words": min_words,
        "summary": summary[:8000],
        "strengths": strengths,
        "weaknesses": weaknesses,
        "spelling_errors": spelling_errors,
        "teacher_recommendation": str(result.get("teacher_recommendation") or "")[
            :4000
        ],
        "improved_text": str(result.get("improved_text") or "")[:10000],
    }


def _mock_ielts_response(
    essay_text: str,
    topic_title: str = "",
    task_type: str = "ielts_task2",
    min_words: int = 250,
) -> dict:
    """Deterministic IELTS 4-criteria evaluation based on lexical richness, structure, and length."""
    words = re.findall(r"[A-Za-z']+", essay_text or "")
    wc = WordCounter.count(essay_text or "")
    unique_ratio = len({w.lower() for w in words}) / max(len(words), 1)
    paragraphs = [p.strip() for p in (essay_text or "").split("\n") if p.strip()]
    para_count = len(paragraphs)

    # Heuristic baseline band (5.5 - 8.0)
    if wc >= min_words and para_count >= 3 and unique_ratio >= 0.45:
        base_ta, base_cc, base_lr, base_gra = 7.5, 7.5, 7.0, 7.0
    elif wc >= min_words:
        base_ta, base_cc, base_lr, base_gra = 6.5, 6.5, 6.5, 6.0
    elif wc >= int(min_words * 0.7):
        base_ta, base_cc, base_lr, base_gra = 5.5, 6.0, 6.0, 5.5
    else:
        base_ta, base_cc, base_lr, base_gra = 4.5, 5.0, 5.0, 5.0

    raw = {
        "topic_match": True,
        "topic_match_reason": f"The writing responds directly to the topic '{topic_title or 'IELTS Writing Prompt'}'.",
        "criteria": [
            {
                "id": 1,
                "name": "Task Achievement / Task Response",
                "score": base_ta,
                "reason": (
                    f"Addresses the main parts of the {'Task 1 report' if task_type == 'ielts_task1' else 'Task 2 essay'} "
                    f"with {wc} words (target: {min_words}+ words)."
                ),
                "errors": [],
            },
            {
                "id": 2,
                "name": "Coherence and Cohesion",
                "score": base_cc,
                "reason": f"Organized into {para_count} paragraph(s) with logical progression and cohesive linking devices.",
                "errors": [],
            },
            {
                "id": 3,
                "name": "Lexical Resource",
                "score": base_lr,
                "reason": f"Demonstrates a lexical diversity ratio of {round(unique_ratio * 100)}% with topic-appropriate vocabulary.",
                "errors": [],
            },
            {
                "id": 4,
                "name": "Grammatical Range and Accuracy",
                "score": base_gra,
                "reason": "Uses a mix of simple and complex sentence structures with generally good control of grammar and punctuation.",
                "errors": [],
            },
        ],
        "summary": (
            f"IELTS Writing Assessment complete. Your response of {wc} words demonstrates solid structure and vocabulary. "
            f"Focus on expanding academic collocations and complex subordinate clauses to reach Band 8.0+."
        ),
        "strengths": [
            "Clear position and relevant supporting arguments throughout the response",
            "Good paragraphing and use of cohesive transitions",
        ],
        "weaknesses": [
            "Some lexical repetition could be replaced with more precise academic synonyms",
            "Include wider variety of complex grammatical structures (conditionals, passive voice, inversion)",
        ],
        "spelling_errors": [],
        "teacher_recommendation": (
            "Practice planning your paragraph structure for 3–5 minutes before writing, and review Band 8+ academic collocations."
        ),
        "improved_text": (
            essay_text.strip()
            + "\n\n[Band 8.5+ Examiner Tip: Ensure each body paragraph opens with a clear topic sentence "
            "and concludes by linking back to the main prompt.]"
        ),
    }
    validated = _validate_ielts_result(
        raw, essay_text=essay_text, task_type=task_type, min_words=min_words
    )
    validated["_mock_mode"] = True
    return validated


def grade_ielts_essay(
    essay_text: str,
    topic_title: str = "",
    task_type: str = "ielts_task2",
    min_words: int | None = None,
) -> dict:
    """Grade an English IELTS Task 1 / Task 2 / Multi-level essay on the 4 official criteria (Band 1.0–9.0)."""
    if min_words is None:
        min_words = 150 if task_type == "ielts_task1" else 250

    cleaned_text = (essay_text or "").strip()
    if not cleaned_text:
        raise ValueError("Essay text cannot be empty.")

    if _is_mock_mode():
        return _mock_ielts_response(
            cleaned_text,
            topic_title=topic_title,
            task_type=task_type,
            min_words=min_words,
        )

    try:
        client = _get_llm_client(timeout=60.0)
        candidates = _model_candidates()
        wc = WordCounter.count(cleaned_text)
        task_label = (
            "IELTS Academic/General Writing Task 1 (minimum 150 words)"
            if task_type == "ielts_task1"
            else "IELTS Writing Task 2 Essay (minimum 250 words)"
        )
        user_msg = (
            f"Task Type: {task_label}\n"
            f"Prompt / Topic: {topic_title or 'General IELTS Writing Task'}\n"
            f"Word Count: {wc} words (Minimum required: {min_words} words)\n\n"
            f"Candidate Response:\n{cleaned_text}"
        )
        response, _ = _chat_with_fallback(
            client,
            candidates[0],
            candidates[1:],
            messages=[
                {"role": "system", "content": IELTS_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=3000,
            temperature=0.1,
            max_attempts=1,
        )
        raw_content = response.choices[0].message.content or ""
        parsed = parse_llm_json(raw_content)
        if parsed.get("_parse_failed"):
            return _mock_ielts_response(
                cleaned_text,
                topic_title=topic_title,
                task_type=task_type,
                min_words=min_words,
            )
        return _validate_ielts_result(
            parsed, essay_text=cleaned_text, task_type=task_type, min_words=min_words
        )
    except Exception as exc:
        logger.warning(
            "IELTS LLM call failed (%s), using deterministic IELTS Band evaluator fallback",
            exc,
        )
        return _mock_ielts_response(
            cleaned_text,
            topic_title=topic_title,
            task_type=task_type,
            min_words=min_words,
        )
