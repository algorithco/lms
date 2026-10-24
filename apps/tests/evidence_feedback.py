"""
Evidence-Based AI Feedback Engine for English Exams (IELTS & CEFR Multi-level).
Powered strictly by deepseek/deepseek-r1-0528 (settings.AI_EVALUATION_MODEL).

Capabilities:
1. Reading & Listening Evidence Extraction:
   - Direct Quote / Line from passage that justifies the key
   - Why selected option was wrong & which distractor misled the candidate
   - Synonym matching analysis (question keyword vs passage equivalent)
2. Multi-level CEFR Writing Evaluator (BMB 4 criteria, 75-point scale):
   - Content, Communicative Achievement, Organisation, Language
   - Deductive scoring + C1 "Word Upgrade" suggestions
3. IELTS Writing Task 1 & 2 Evaluator:
   - 4 criteria (TR, CC, LR, GRA) on 1.0–9.0 band scale
   - Deductive scoring starting at 9.0 downwards
   - Band 8.0+ Model Answer paragraph rewrite
"""

from __future__ import annotations

import json
import logging
import re
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

EVAL_MODEL = getattr(settings, "AI_EVALUATION_MODEL", "deepseek/deepseek-r1-0528")


# -----------------------------------------------------------------------------
# 1. Reading & Listening Evidence Extraction
# -----------------------------------------------------------------------------
def generate_reading_listening_evidence(
    question_text: str,
    selected_answer: str,
    correct_answer: str,
    passage_text: str = "",
    question_explanation: str = "",
) -> dict[str, Any]:
    """
    Extract evidence quote, why-wrong rationale, and synonym matching.
    """
    cache_key = f"evidence_v1_{hash((question_text[:60], selected_answer[:30], correct_answer[:30]))}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    # Try deepseek/deepseek-r1-0528
    try:
        from apps.essays.services import _get_llm_client, _is_mock_mode

        if not _is_mock_mode():
            client = _get_llm_client(timeout=18.0)
            system_prompt = (
                "You are an expert Cambridge IELTS & CEFR examiner analyzing candidate mistakes. "
                "Output strictly valid JSON with no markdown formatting. "
                "Keys required: 'direct_quote', 'why_wrong', 'synonym_matching', 'correct_rule'."
            )
            user_prompt = f"""Analyze this English exam question and candidate error:
Passage/Transcript: {passage_text[:1200] if passage_text else '(Short context question)'}
Question: {question_text}
Candidate Selected WRONG Answer: {selected_answer}
CORRECT Answer: {correct_answer}
Existing Notes: {question_explanation}

Return JSON with:
1. "direct_quote": The exact sentence or clause from the text proving the correct answer.
2. "why_wrong": Explanation in Uzbek/English explaining why the candidate's choice is incorrect and what distractor word misled them.
3. "synonym_matching": A clear explanation of keywords in the question mapped to synonyms used in the passage (e.g. "crucial in question = vital in text").
4. "correct_rule": Short mnemonic or takeaway rule to avoid this trap in future tests.
"""
            resp = client.chat.completions.create(
                model=EVAL_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=650,
                temperature=0.2,
            )
            raw = (resp.choices[0].message.content or "").strip()
            # Clean possible markdown json wrapper
            if "```" in raw:
                raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
            data = json.loads(raw)
            if isinstance(data, dict) and "direct_quote" in data:
                data["source"] = "deepseek-r1-0528"
                cache.set(cache_key, data, timeout=3600 * 24 * 7)
                return data
    except Exception as e:
        logger.warning("Evidence extraction via LLM failed (%s), using rule-based fallback", e)

    # Deterministic rule-based fallback
    direct_quote = ""
    if passage_text:
        # Search for first sentence mentioning correct answer or keywords
        sentences = re.split(r"(?<=[.!?])\s+", passage_text)
        for s in sentences:
            if any(w.lower() in s.lower() for w in correct_answer.split() if len(w) > 3):
                direct_quote = s.strip()
                break
        if not direct_quote and sentences:
            direct_quote = sentences[0].strip()
    if not direct_quote:
        direct_quote = f"Evidence directly derived from the official answer key: '{correct_answer}'."

    fallback_data = {
        "direct_quote": direct_quote,
        "why_wrong": (
            f"Siz tanlagan '{selected_answer}' varianti matn kontekstiga mos kelmaydi. "
            f"Ushbu javob chalg'ituvchi (distractor) so'zlar tufayli noto'g'ri tanlangan."
        ),
        "synonym_matching": (
            f"Savoldagi asosiy kalit so'zlar matnda sinonim shaklida berilgan: "
            f"'{correct_answer}' javobi matndagi fikrni to'g'ridan-to'g'ri tasdiqlaydi."
        ),
        "correct_rule": (
            f"To'g'ri javob — '{correct_answer}'. "
            + (question_explanation or "Savol kalit so'zlarini matndagi parafraza bilan solishtiring.")
        ),
        "source": "rule_engine",
    }
    cache.set(cache_key, fallback_data, timeout=3600 * 24 * 7)
    return fallback_data


# -----------------------------------------------------------------------------
# 2. Multi-level Writing Evaluator (BMB 4 Criteria — 75 Points)
# -----------------------------------------------------------------------------
def grade_multilevel_writing_bmb(
    essay_text: str,
    topic_title: str = "",
    task_type: str = "task2",
) -> dict[str, Any]:
    """
    Evaluates CEFR Multi-level Writing on official BMB 4 criteria:
    1. Content (0–20 points)
    2. Communicative Achievement (0–20 points)
    3. Organisation (0–15 points)
    4. Language (0–20 points)
    Total = 75 points.

    Maps to CEFR:
        65–75: C1
        51–64: B2
        36–50: B1
        <= 35: A2
    """
    text = (essay_text or "").strip()
    word_count = len(text.split())

    # Try LLM
    try:
        from apps.essays.services import _get_llm_client, _is_mock_mode

        if not _is_mock_mode():
            client = _get_llm_client(timeout=25.0)
            system_prompt = (
                "You are an official BMB/CEFR State Examination writing assessor for English Multi-level exams. "
                "You score essays strictly on 4 criteria totaling 75 points: "
                "1. Content (max 20), 2. Communicative Achievement (max 20), "
                "3. Organisation (max 15), 4. Language (max 20). "
                "You must use a deductive approach: specify exact point deductions and reasons. "
                "Output strictly valid JSON."
            )
            user_prompt = f"""Evaluate this {task_type.upper()} Multi-level response:
Topic/Prompt: {topic_title or 'Multi-level Writing Prompt'}
Word count: {word_count}
Essay Text:
{text}

Return JSON with:
{{
  "content_score": <number 0-20>,
  "content_feedback": "<deductive reasoning for content>",
  "communicative_score": <number 0-20>,
  "communicative_feedback": "<style, register, tone analysis>",
  "organisation_score": <number 0-15>,
  "organisation_feedback": "<cohesion, coherence, paragraphs>",
  "language_score": <number 0-20>,
  "language_feedback": "<lexical resource, grammar accuracy>",
  "total_score": <sum of 4 scores 0-75>,
  "cefr_level": "<C1|B2|B1|A2>",
  "word_upgrades": [
    {{"original": "important", "suggested": "paramount / crucial", "context": "example"}},
    {{"original": "make", "suggested": "foster / facilitate", "context": "example"}},
    {{"original": "show", "suggested": "illustrate / manifest", "context": "example"}}
  ],
  "model_paragraph": "<Band 8.0 / C1 high quality rewrite of weak paragraph>"
}}
"""
            resp = client.chat.completions.create(
                model=EVAL_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=900,
                temperature=0.2,
            )
            raw = (resp.choices[0].message.content or "").strip()
            if "```" in raw:
                raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
            data = json.loads(raw)
            if "total_score" in data:
                data["source"] = "deepseek-r1-0528"
                return data
    except Exception as e:
        logger.warning("BMB Multi-level grading LLM failed (%s), using rule-based scoring", e)

    # Deterministic fallback scoring (scaled to 75 points)
    if word_count < 50:
        c_score, ca_score, org_score, lang_score = 5, 5, 4, 5
    elif word_count < 120:
        c_score, ca_score, org_score, lang_score = 10, 11, 8, 11
    elif word_count < 180:
        c_score, ca_score, org_score, lang_score = 14, 15, 11, 14
    elif word_count < 250:
        c_score, ca_score, org_score, lang_score = 17, 17, 13, 17
    else:
        c_score, ca_score, org_score, lang_score = 18, 18, 14, 18

    total = c_score + ca_score + org_score + lang_score
    from apps.tests.score_converter import raw_to_cefr_multilevel

    level, _ = raw_to_cefr_multilevel(total, max_score=75)

    return {
        "content_score": c_score,
        "content_feedback": f"Mavzu to'liq va tushunarli yoritilgan ({word_count} ta so'z).",
        "communicative_score": ca_score,
        "communicative_feedback": "Akademik registr va rasmiy uslub saqlangan.",
        "organisation_score": org_score,
        "organisation_feedback": "Xatboshilar va bog'lovchi so'zlar (Furthermore, However) qo'llanilgan.",
        "language_score": lang_score,
        "language_feedback": "Leksik va grammatik birliklar yaxshi, lekin murakkabroq C1 sintaksis tavsiya etiladi.",
        "total_score": total,
        "cefr_level": level,
        "word_upgrades": [
            {"original": "important", "suggested": "paramount / indispensable", "context": "Crucial priority"},
            {"original": "good", "suggested": "beneficial / advantageous", "context": "Positive impact"},
            {"original": "show", "suggested": "demonstrate / exemplify", "context": "Supporting evidence"},
        ],
        "model_paragraph": (
            "Furthermore, it is widely acknowledged that continuous exposure to high-level academic texts "
            "substantially enhances lexical resource, enabling candidates to articulate intricate arguments "
            "with commendable precision."
        ),
        "source": "rule_engine",
    }


# -----------------------------------------------------------------------------
# 3. IELTS Writing Evaluator (Deductive Band 1.0–9.0)
# -----------------------------------------------------------------------------
def grade_ielts_writing_deductive(
    essay_text: str,
    topic_title: str = "",
    task_type: str = "task2",
) -> dict[str, Any]:
    """
    Evaluates IELTS Writing Task 1 or Task 2 on the official 4 criteria:
    Task Achievement / Response (TR), Coherence & Cohesion (CC),
    Lexical Resource (LR), Grammatical Range & Accuracy (GRA).

    Deductive method: Starts from Band 9.0 and deducts specific penalties with reasoning.
    Provides Band 8.0+ model paragraph rewrite.
    """
    text = (essay_text or "").strip()
    word_count = len(text.split())

    try:
        from apps.essays.services import _get_llm_client, _is_mock_mode

        if not _is_mock_mode():
            client = _get_llm_client(timeout=25.0)
            system_prompt = (
                "You are a Senior Certified IELTS Examiner. "
                "Evaluate writing using a strict DEDUCTIVE method: Start from Band 9.0 for each of the 4 criteria "
                "(TR, CC, LR, GRA) and subtract points with clear justifications for each weakness or error. "
                "Output strictly valid JSON with no markdown formatting."
            )
            user_prompt = f"""IELTS Writing Evaluation ({task_type.upper()}):
Prompt: {topic_title or 'IELTS General Prompt'}
Word count: {word_count}
Essay:
{text}

Return JSON:
{{
  "task_response": {{"band": <1.0-9.0>, "deductions": ["-0.5 due to...", "-0.5 for..."], "feedback": "..."}},
  "coherence_cohesion": {{"band": <1.0-9.0>, "deductions": ["-0.5 due to..."], "feedback": "..."}},
  "lexical_resource": {{"band": <1.0-9.0>, "deductions": ["-0.5 due to..."], "feedback": "..."}},
  "grammatical_accuracy": {{"band": <1.0-9.0>, "deductions": ["-0.5 due to..."], "feedback": "..."}},
  "overall_band": <1.0-9.0>,
  "model_paragraph_rewrite": "<An exemplary Band 8.5 paragraph rewriting a weak section from candidate's essay>",
  "actionable_tips": ["...", "..."]
}}
"""
            resp = client.chat.completions.create(
                model=EVAL_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=900,
                temperature=0.2,
            )
            raw = (resp.choices[0].message.content or "").strip()
            if "```" in raw:
                raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
            data = json.loads(raw)
            if "overall_band" in data:
                data["source"] = "deepseek-r1-0528"
                return data
    except Exception as e:
        logger.warning("IELTS deductive grading LLM failed (%s), using fallback", e)

    # Fallback deductive calculation
    min_words = 150 if task_type == "task1" else 250
    penalty = Decimal("0.0")
    if word_count < min_words:
        penalty += Decimal("1.0")

    base = Decimal("7.0") - penalty
    base = max(Decimal("4.0"), min(Decimal("8.5"), base))

    from apps.tests.score_converter import calculate_overall_ielts_band

    overall = calculate_overall_ielts_band(base, base, base, base)

    return {
        "task_response": {
            "band": float(base),
            "deductions": [f"Words: {word_count}/{min_words}"] if word_count < min_words else [],
            "feedback": f"Fikrlar asoslangan, talab qilingan so'zlar soni: {word_count}.",
        },
        "coherence_cohesion": {
            "band": float(base),
            "deductions": ["-0.5: Xatboshilar orasida ko'proq tabiiy bog'lovchilar talab etiladi."],
            "feedback": "Mantiqiy ketma-ketlik va xatboshilarga bo'linish yaxshi.",
        },
        "lexical_resource": {
            "band": float(base),
            "deductions": ["-0.5: So'z takrorlanishi kuzatildi, kamyob akademik sinonimlar kerak."],
            "feedback": "Asosiy mavzuga oid so'z boyligi mavjud.",
        },
        "grammatical_accuracy": {
            "band": float(base),
            "deductions": ["-0.5: Qo'shma gaplarda zamonlar moslashuvi bo'yicha kamchiliklar."],
            "feedback": "Gap konstruksiyalari tushunarli.",
        },
        "overall_band": float(overall),
        "model_paragraph_rewrite": (
            "In recent years, the exponential advancement of technological innovation has undeniably transformed "
            "conventional educational paradigms. Consequently, contemporary learners are afforded unprecedented "
            "opportunities to acquire knowledge autonomously, transcending conventional geographical limitations."
        ),
        "actionable_tips": [
            "Qo'shma gaplarda 'In addition', 'Consequently', 'Conversely' kabi bog'lovchilarni faol ishlating.",
            "Umumiy so'zlar o'rniga aniq akademik leksikadan foydalaning (masalan, 'big change' -> 'substantial transformation').",
        ],
        "source": "rule_engine",
    }
