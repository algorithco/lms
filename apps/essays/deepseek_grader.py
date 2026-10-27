"""
DeepSeek AI Essay Grader — Grand Education LMS.

Direct integration with DeepSeek models (via OpenRouter or DeepSeek direct API)
for evaluating:
  1. Uzbek BMB (Milliy sertifikat & Attestatsiya) 12-criteria essays (max 20 / 36 ball)
  2. English IELTS / Multi-level CEFR 4-criteria essays (Band 1.0–9.0)

With automatic fallback to secondary models and mock mode support.
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
import httpx
from openai import OpenAI

from .prompts import (
    ESSAY_GRADING_SYSTEM_PROMPT,
    ESSAY_GRADING_SYSTEM_PROMPT_SIMPLE,
    build_grading_message,
)

logger = logging.getLogger(__name__)


def get_deepseek_client(timeout: float = 60.0) -> OpenAI:
    """Return an OpenAI client configured for DeepSeek API calls."""
    api_key = (
        getattr(settings, "DEEPSEEK_API_KEY", "")
        or getattr(settings, "OPENROUTER_API_KEY", "")
        or "sk-test-deepseek-key"
    ).strip()

    base_url = (
        getattr(settings, "DEEPSEEK_BASE_URL", "")
        or (
            "https://openrouter.ai/api/v1"
            if api_key.startswith("sk-or-")
            else "https://api.deepseek.com/v1"
        )
    ).strip()

    site_url = getattr(settings, "OPENROUTER_SITE_URL", "https://grandec.uz")
    app_name = getattr(settings, "OPENROUTER_APP_NAME", "Grand Education LMS")

    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=httpx.Timeout(timeout, connect=10.0),
        max_retries=0,
        default_headers={
            "HTTP-Referer": site_url,
            "X-Title": app_name,
        },
    )


class DeepSeekGrader:
    """DeepSeek AI Grading Service for BMB and IELTS writing evaluations."""

    @staticmethod
    def get_model() -> str:
        return (
            getattr(settings, "AI_EVALUATION_MODEL", "")
            or getattr(settings, "ESSAY_GRADER_MODEL", "")
            or "deepseek/deepseek-r1-0528"
        ).strip()

    @classmethod
    def grade_bmb(cls, essay_text: str, topic_title: str = "") -> dict[str, Any]:
        """Grade BMB 12-criteria Uzbek essay using DeepSeek LLM."""
        from .services import (
            _is_mock_mode,
            _validate_result,
            grade_essay,
            parse_llm_json,
        )

        cleaned = (essay_text or "").strip()
        if not cleaned:
            raise ValueError("Esse matni bo'sh")

        from .pre_validation import pre_validate_essay

        pre_validate_essay(cleaned, topic_title=topic_title)

        if _is_mock_mode():
            return grade_essay(cleaned, topic_title)

        client = get_deepseek_client(timeout=50.0)
        model = cls.get_model()
        user_message = build_grading_message(cleaned, topic_title)

        logger.info(
            "DeepSeek BMB grading initiated: model=%s, length=%d", model, len(cleaned)
        )

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": ESSAY_GRADING_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=3000,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content or ""
            parsed = parse_llm_json(raw)
            if parsed.get("_parse_failed"):
                raise ValueError("JSON parse error from DeepSeek response")

            for crit in parsed.get("criteria", []):
                if isinstance(crit, dict):
                    crit.setdefault("reason", "")
                    crit.setdefault("errors", [])

            _validate_result(parsed, cleaned)
            parsed.setdefault("topic_match", True)
            parsed.setdefault("topic_match_reason", "")
            parsed["_model_used"] = model
            parsed["_from_cache"] = False
            parsed["_mock_mode"] = False
            return parsed
        except Exception as exc:
            logger.warning(
                "DeepSeek BMB grading failed (%s), falling back to main grading pipeline",
                exc,
            )
            try:
                return grade_essay(cleaned, topic_title)
            except Exception:
                from .services import _mock_12_criteria_response

                res = _mock_12_criteria_response(cleaned, topic_title)
                res.setdefault("topic_match", True)
                res.setdefault("topic_match_reason", "")
                res["_from_cache"] = False
                res["_mock_mode"] = True
                return res

    @classmethod
    def grade_ielts(
        cls,
        essay_text: str,
        topic_title: str = "",
        task_type: str = "ielts_task2",
        min_words: int | None = None,
    ) -> dict[str, Any]:
        """Grade English IELTS / Multi-level essay on 4 official criteria."""
        from .services import (
            IELTS_SYSTEM_PROMPT,
            WordCounter,
            _is_mock_mode,
            _validate_ielts_result,
            grade_ielts_essay,
            parse_llm_json,
        )

        cleaned = (essay_text or "").strip()
        if not cleaned:
            raise ValueError("Essay text cannot be empty.")

        from .pre_validation import pre_validate_essay

        pre_validate_essay(cleaned, topic_title=topic_title)

        if min_words is None:
            min_words = 150 if task_type == "ielts_task1" else 250

        if _is_mock_mode():
            return grade_ielts_essay(
                cleaned,
                topic_title=topic_title,
                task_type=task_type,
                min_words=min_words,
            )

        client = get_deepseek_client(timeout=50.0)
        model = cls.get_model()
        wc = WordCounter.count(cleaned)
        task_label = (
            "IELTS Academic/General Writing Task 1 (minimum 150 words)"
            if task_type == "ielts_task1"
            else "IELTS Writing Task 2 Essay (minimum 250 words)"
        )
        user_msg = (
            f"Task Type: {task_label}\n"
            f"Prompt / Topic: {topic_title or 'General IELTS Writing Task'}\n"
            f"Word Count: {wc} words (Minimum required: {min_words} words)\n\n"
            f"Candidate Response:\n{cleaned}"
        )

        logger.info(
            "DeepSeek IELTS grading initiated: model=%s, task=%s, words=%d",
            model,
            task_type,
            wc,
        )

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": IELTS_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=3000,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content or ""
            parsed = parse_llm_json(raw)
            if parsed.get("_parse_failed"):
                raise ValueError("JSON parse error from DeepSeek IELTS response")

            result = _validate_ielts_result(
                parsed,
                essay_text=cleaned,
                task_type=task_type,
                min_words=min_words,
            )
            result["_model_used"] = model
            return result
        except Exception as exc:
            logger.warning(
                "DeepSeek IELTS grading failed (%s), falling back to main IELTS evaluator",
                exc,
            )
            return grade_ielts_essay(
                cleaned,
                topic_title=topic_title,
                task_type=task_type,
                min_words=min_words,
            )


# Functional convenience wrappers
def grade_bmb_essay_deepseek(essay_text: str, topic_title: str = "") -> dict[str, Any]:
    return DeepSeekGrader.grade_bmb(essay_text, topic_title)


def grade_ielts_essay_deepseek(
    essay_text: str,
    topic_title: str = "",
    task_type: str = "ielts_task2",
    min_words: int | None = None,
) -> dict[str, Any]:
    return DeepSeekGrader.grade_ielts(
        essay_text, topic_title=topic_title, task_type=task_type, min_words=min_words
    )


# Expose module alias for backwards/cross-path imports
sys.modules.setdefault("apps.essays.services.deepseek_grader", sys.modules[__name__])
