"""
AI Vocabulary Generator Service.
Generates 4 distinct exercise formats from a raw list of 50-60 English words:
1. Multiple Choice Quiz (4 options with context)
2. Spelling / Imlo (Word scramble, letter clues, and definition)
3. English -> Uzbek (Select correct Uzbek translation)
4. Uzbek -> English (Select correct English equivalent)
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from django.conf import settings

from apps.core.ai_health import AIUnavailable

logger = logging.getLogger(__name__)


def clean_word_list(raw_text: str) -> List[str]:
    """Parse newline or comma separated words into a clean deduplicated list."""
    lines = re.split(r"[\n,\r]+", raw_text)
    words = []
    seen = set()
    for line in lines:
        cleaned = re.sub(r"^[0-9]+[\.\)\-\s]+", "", line).strip()
        cleaned = re.sub(r"[^a-zA-Z\s'-]", "", cleaned).strip()
        if cleaned and len(cleaned) >= 2 and cleaned.lower() not in seen:
            seen.add(cleaned.lower())
            words.append(cleaned)
    return words


def generate_exercises_with_ai(words: List[str]) -> Dict[str, Any]:
    """
    Generates 4 formats using DeepSeek or Gemini via OpenRouter.
    """
    api_key = (
        getattr(settings, "OPENROUTER_API_KEY", "")
        or getattr(settings, "DEEPSEEK_API_KEY", "")
        or os.environ.get("OPENROUTER_API_KEY", "")
        or os.environ.get("DEEPSEEK_API_KEY", "")
    )

    if not api_key:
        # Without a provider there are no real exercises: say so, never make
        # up translations or distractors from a built-in word list.
        raise AIUnavailable("AI kaliti sozlanmagan", feature="vocab")

    prompt = f"""You are an elite English language curriculum architect.
Given this list of {len(words)} English vocabulary words:
{", ".join(words)}

Generate 4 interactive exercise formats for these words:
1. "format_1_quiz": Array of objects: {{"id": int, "word": str, "question": str, "options": [4 strings], "correct_answer": str, "explanation": str}}
2. "format_2_spelling": Array of objects: {{"id": int, "word": str, "prompt": "Uzbek translation/definition", "hint_pattern": "e.g. r _ _ _ _ _ t", "scrambled_letters": [list of single letters], "correct_word": str}}
3. "format_3_eng_uzb": Array of objects: {{"id": int, "word": str, "options": [4 Uzbek translation strings], "correct_answer": str}}
4. "format_4_uzb_eng": Array of objects: {{"id": int, "uzbek_word": str, "options": [4 English words], "correct_answer": str}}

Output strictly valid JSON with top-level keys:
{{"format_1_quiz": [...], "format_2_spelling": [...], "format_3_eng_uzb": [...], "format_4_uzb_eng": [...]}}
"""

    try:
        import requests

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek/deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.2,
            },
            timeout=40,
        )

        if response.status_code == 200:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            if all(
                k in parsed
                for k in [
                    "format_1_quiz",
                    "format_2_spelling",
                    "format_3_eng_uzb",
                    "format_4_uzb_eng",
                ]
            ):
                return parsed
    except Exception as e:
        logger.warning("AI vocabulary generation call failed: %s", e)
        raise AIUnavailable(str(e), feature="vocab") from e

    raise AIUnavailable("AI javobi to'liq emas yoki xato", feature="vocab")


def create_vocabulary_pack(
    raw_text: str,
    title: str = "Ingliz tili Lug'at Mashg'uloti",
    teacher=None,
    group=None,
) -> Any:
    """
    Cleans raw words, runs generator, and saves VocabularyPack instance.
    """
    from apps.vocabulary.models import VocabularyPack

    words = clean_word_list(raw_text)
    if not words:
        raise ValueError("Kamida bitta so'z kiritilishi shart.")

    exercises_data = generate_exercises_with_ai(words)

    pack = VocabularyPack.objects.create(
        teacher=teacher,
        group=group,
        title=title,
        subject="english",
        raw_words_text=raw_text,
        word_count=len(words),
        exercises_data=exercises_data,
    )
    return pack
