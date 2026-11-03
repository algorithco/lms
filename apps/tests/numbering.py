"""Student-facing question numbers.

``Question.position`` is an internal sort key (CD-format imports start at
1001), never something to show a student. Numbers shown in results and on
paper answer sheets come from here:

- CEFR Multi-level: Listening and Reading are numbered 1–35 separately,
  exactly as on the official sheet ("L1" … "R35").
- Every other test: objective questions numbered 1…N in test order.

Writing and Speaking items are not numbered: they are not answered on a
bubble sheet and never count as objective questions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from apps.tests.cefr_multilevel import OBJECTIVE_SECTIONS as CEFR_OBJECTIVE_SECTIONS

NOT_OBJECTIVE = {"written", "SPEAKING_PROMPT"}


@dataclass(frozen=True)
class NumberedQuestion:
    question: Any
    key: str  # sheet key: "L1", "R12" for CEFR; "7" otherwise
    number: int  # number within its section (CEFR) or the whole test
    section_code: str


def _sort_key(q: Any) -> tuple[int, int, int]:
    section_order = q.section.order if getattr(q, "section_id", None) and q.section else 0
    return (section_order, q.position or 0, q.id)


def is_objective(q: Any) -> bool:
    return q.question_type not in NOT_OBJECTIVE


def number_questions(test: Any, questions: Iterable[Any] | None = None) -> list[NumberedQuestion]:
    """Objective questions of ``test`` in display order with their numbers."""
    if questions is None:
        questions = test.questions.select_related("section").prefetch_related("choices", "gap_blanks")
    ordered = sorted((q for q in questions if is_objective(q)), key=_sort_key)

    is_cefr = getattr(test, "exam_type", "") == "cefr_multilevel"
    numbered: list[NumberedQuestion] = []
    if is_cefr:
        counters: dict[str, int] = {}
        for q in ordered:
            code = (q.section.code if q.section_id and q.section else "").upper()
            if code not in CEFR_OBJECTIVE_SECTIONS:
                continue
            counters[code] = counters.get(code, 0) + 1
            n = counters[code]
            numbered.append(NumberedQuestion(q, f"{code[0]}{n}", n, code))
        return numbered

    for n, q in enumerate(ordered, start=1):
        code = (q.section.code if q.section_id and q.section else "").upper()
        numbered.append(NumberedQuestion(q, str(n), n, code))
    return numbered


def number_map(test: Any, questions: Iterable[Any] | None = None) -> dict[int, NumberedQuestion]:
    return {nq.question.id: nq for nq in number_questions(test, questions)}
