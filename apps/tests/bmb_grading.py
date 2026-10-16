"""
BMB (Bilim va malakalarni baholash agentligi) Milliy Sertifikat Gradatsiya Tizimi.

Rasmiy baholash standartlari:
    86% - 100% -> A+ (Maksimal imtiyoz)
    75% - 85%  -> A
    68% - 74%  -> B+
    60% - 67%  -> B
    53% - 59%  -> C+
    46% - 52%  -> C
    < 46%      -> Fail (Sertifikat berilmaydi)

Umumiy ball: Test (40 ta savol) + Yozma ish / Esse (20-25 ball) integratsiyasi.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any


BMB_GRADES = {
    "A+": {
        "grade": "A+",
        "min_pct": 86.0,
        "max_pct": 100.0,
        "title": "A+ daraja (Maksimal imtiyoz)",
        "short_title": "A+ (Maksimal)",
        "is_passed": True,
        "color": "#10B981",  # emerald
        "badge_class": "badge green",
    },
    "A": {
        "grade": "A",
        "min_pct": 75.0,
        "max_pct": 85.99,
        "title": "A daraja",
        "short_title": "A",
        "is_passed": True,
        "color": "#059669",  # green
        "badge_class": "badge green",
    },
    "B+": {
        "grade": "B+",
        "min_pct": 68.0,
        "max_pct": 74.99,
        "title": "B+ daraja",
        "short_title": "B+",
        "is_passed": True,
        "color": "#3B82F6",  # blue
        "badge_class": "badge blue",
    },
    "B": {
        "grade": "B",
        "min_pct": 60.0,
        "max_pct": 67.99,
        "title": "B daraja",
        "short_title": "B",
        "is_passed": True,
        "color": "#2563EB",  # dark blue
        "badge_class": "badge blue",
    },
    "C+": {
        "grade": "C+",
        "min_pct": 53.0,
        "max_pct": 59.99,
        "title": "C+ daraja",
        "short_title": "C+",
        "is_passed": True,
        "color": "#F59E0B",  # amber
        "badge_class": "badge amber",
    },
    "C": {
        "grade": "C",
        "min_pct": 46.0,
        "max_pct": 52.99,
        "title": "C daraja",
        "short_title": "C",
        "is_passed": True,
        "color": "#D97706",  # dark amber
        "badge_class": "badge amber",
    },
    "Fail": {
        "grade": "Fail",
        "min_pct": 0.0,
        "max_pct": 45.99,
        "title": "Sertifikat berilmaydi (Yetarli emas)",
        "short_title": "Sertifikat berilmaydi",
        "is_passed": False,
        "color": "#EF4444",  # red
        "badge_class": "badge rose",
    },
}


def calculate_bmb_grade(
    percentage: float | Decimal | int | None = None,
    *,
    test_score: float | Decimal | None = None,
    test_max: float | Decimal | None = None,
    essay_score: float | Decimal | None = None,
    essay_max: float | Decimal | None = None,
) -> dict[str, Any]:
    """
    Hisoblangan foiz yoki test + esse ballari orqali rasmiy BMB sertifikat darajasini qaytaradi.

    Agarda test_score va essay_score berilsa, umumiy ball = test_score + essay_score
    umumiy maksimal ball = test_max + essay_max sifatida umumiy foiz hisoblanadi.
    """
    final_pct = 0.0

    if test_score is not None and test_max is not None and float(test_max) > 0:
        t_score = float(test_score)
        t_max = float(test_max)

        if essay_score is not None and essay_max is not None and float(essay_max) > 0:
            e_score = float(essay_score)
            e_max = float(essay_max)
            total_earned = t_score + e_score
            total_possible = t_max + e_max
            final_pct = (total_earned / total_possible) * 100.0 if total_possible > 0 else 0.0
        else:
            final_pct = (t_score / t_max) * 100.0
    elif percentage is not None:
        try:
            final_pct = float(percentage)
        except (ValueError, TypeError):
            final_pct = 0.0

    final_pct = max(0.0, min(100.0, round(final_pct, 2)))

    # Aniqlash
    if final_pct >= 86.0:
        info = BMB_GRADES["A+"]
    elif final_pct >= 75.0:
        info = BMB_GRADES["A"]
    elif final_pct >= 68.0:
        info = BMB_GRADES["B+"]
    elif final_pct >= 60.0:
        info = BMB_GRADES["B"]
    elif final_pct >= 53.0:
        info = BMB_GRADES["C+"]
    elif final_pct >= 46.0:
        info = BMB_GRADES["C"]
    else:
        info = BMB_GRADES["Fail"]

    return {
        "grade": info["grade"],
        "percentage": final_pct,
        "title": info["title"],
        "short_title": info["short_title"],
        "is_passed": info["is_passed"],
        "color": info["color"],
        "badge_class": info["badge_class"],
        "min_pct": info["min_pct"],
        "max_pct": info["max_pct"],
    }


def bmb_grade_distribution(percentages: list[float]) -> dict[str, int]:
    """
    O'quvchilar guruhining BMB darajalari bo'yicha taqsimotini qaytaradi.
    """
    dist: dict[str, int] = {"A+": 0, "A": 0, "B+": 0, "B": 0, "C+": 0, "C": 0, "Fail": 0}
    for p in percentages:
        g = calculate_bmb_grade(p)["grade"]
        if g in dist:
            dist[g] += 1
    return dist
