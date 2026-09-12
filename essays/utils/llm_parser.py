import re
import json
import logging
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# Regex to extract JSON from markdown code blocks or bare JSON
JSON_BLOCK_RE = re.compile(
    r'```(?:json)?\s*(\{.*?\})\s*```',
    re.DOTALL | re.IGNORECASE
)
BARE_JSON_RE = re.compile(r'(\{.*\})', re.DOTALL)


def extract_json(text: str) -> Optional[str]:
    """
    Extract JSON string from LLM response.
    Handles: ```json {...}```, ``` {...}```, or bare {...}
    Returns the first valid-looking JSON object string or None.
    """
    if not text or not isinstance(text, str):
        return None

    # 1. Try markdown code block first
    match = JSON_BLOCK_RE.search(text)
    if match:
        return match.group(1).strip()

    # 2. Fallback: find first {...} that looks like our schema
    # Look for the specific keys we expect
    for match in BARE_JSON_RE.finditer(text):
        candidate = match.group(1).strip()
        if '"criteria_scores"' in candidate and '"total_score"' in candidate:
            return candidate

    # 3. Last resort: return the first {...} block
    match = BARE_JSON_RE.search(text)
    return match.group(1).strip() if match else None


def parse_llm_json(text: str) -> Dict[str, Any]:
    """
    Parse LLM response to dict. Raises ValueError if parsing fails.
    """
    json_str = extract_json(text)
    if not json_str:
        raise ValueError("No JSON object found in LLM response")

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}. Extracted: {json_str[:200]}")
        raise ValueError(f"Invalid JSON from LLM: {e}") from e


# --- Validation Schema ---

CRITERIA_KEYS = [
    "Mavzuga moslik",
    "Tuzilishi va kompozitsiya",
    "Dalillash va misollar",
    "Mantiqiylik va izchillik",
    "Leksik boylik",
    "Uslubiy to'g'rilik",
    "Xatboshilar izchilligi",
    "Bog'lovchi vositalar",
    "Grammatik to'g'rilik",
    "Puktuatsion qoidalar",
    "Imlo qoidalari",
    "Umumiy taassurot",
]

REQUIRED_TOP_KEYS = {
    "initial_grading_summary": str,
    "topic_match": bool,
    "topic_match_reason": str,
    "criteria_scores": list,
    "total_score": (int, float),
    "max_score": (int, float),
    "summary_feedback": str,
}


def _validate_grading_result(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and normalize LLM grading result to strict schema.
    - Ensures all 12 criteria present with scores 0.0-2.0
    - Clamps total_score to 0-24, max_score=24
    - Provides defaults for missing fields
    """
    # Top-level defaults
    result = {
        "initial_grading_summary": "",
        "topic_match": False,
        "topic_match_reason": "",
        "criteria_scores": [],
        "total_score": 0.0,
        "max_score": 24.0,
        "summary_feedback": "",
    }
    result.update({k: v for k, v in data.items() if k in REQUIRED_TOP_KEYS})

    # Validate / normalize criteria_scores
    existing = {item.get("criterion"): item for item in result.get("criteria_scores", []) if isinstance(item, dict)}
    validated_scores = []

    for idx, criterion_name in enumerate(CRITERIA_KEYS, start=1):
        item = existing.get(criterion_name, {})
        score = item.get("score", 0.0)
        try:
            score = float(score)
        except (TypeError, ValueError):
            score = 0.0
        score = max(0.0, min(2.0, score))  # clamp 0-2

        validated_scores.append({
            "id": idx,
            "criterion": criterion_name,
            "score": round(score, 1),
            "reason": str(item.get("reason", "")).strip() or "Baholash sababi keltirilmagan",
        })

    result["criteria_scores"] = validated_scores

    # Recalculate total from criteria (more reliable than LLM sum)
    calc_total = sum(item["score"] for item in validated_scores)
    llm_total = result.get("total_score", 0.0)
    try:
        llm_total = float(llm_total)
    except (TypeError, ValueError):
        llm_total = calc_total

    # Use calculated total if LLM total is way off, else use LLM (rounded)
    if abs(llm_total - calc_total) > 1.0:
        result["total_score"] = round(calc_total, 1)
    else:
        result["total_score"] = round(max(0.0, min(24.0, llm_total)), 1)

    result["max_score"] = 24.0

    # Ensure strings
    for key in ("initial_grading_summary", "topic_match_reason", "summary_feedback"):
        result[key] = str(result.get(key, "")).strip()

    result["topic_match"] = bool(result.get("topic_match", False))

    return result


def parse_and_validate_grading(text: str) -> Dict[str, Any]:
    """
    Full pipeline: extract JSON -> parse -> validate.
    Returns validated dict ready for JSONResponse.
    """
    parsed = parse_llm_json(text)
    return _validate_grading_result(parsed)