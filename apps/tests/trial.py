"""Free trial of a full CEFR Multi-level mock.

A FREE student whose test quota is used up may still open one configured
part (``free_trial_part`` in ``scales/cefr_multilevel.json``, Reading Part 1
by default) once per test. A trial attempt:

- shows, saves and grades only that part's questions;
- is a preview (kept out of statistics, rating and vedomost);
- never gets a 0–75 estimate — one part cannot stand for a section.
"""

from __future__ import annotations

from typing import Any

from apps.tests import cefr_multilevel


def trial_part_for(test: Any):
    """The ExamPart offered for free on ``test``, or None."""
    if getattr(test, "exam_type", "") != "cefr_multilevel":
        return None
    cfg = cefr_multilevel.load_scale().get("free_trial_part") or {}
    if not cfg:
        return None
    from apps.tests.models import ExamPart

    return (
        ExamPart.objects.select_related("section")
        .filter(section__test=test, section__code__iexact=cfg["section"], number=str(cfg["part"]))
        .first()
    )


def trial_used(user: Any, test: Any) -> bool:
    from apps.tests.models import TestAttempt

    return (
        TestAttempt.objects.filter(student=user, test=test, trial_part__isnull=False)
        .exclude(status=TestAttempt.Status.IN_PROGRESS)
        .exists()
    )


def trial_info(user: Any, test: Any) -> dict[str, Any] | None:
    """What the test detail page needs to offer the trial (None = no offer)."""
    from apps.tests.models import Question

    part = trial_part_for(test)
    if part is None:
        return None
    return {
        "section_code": part.section.code,
        "section_name": part.section.name,
        "part": part.number,
        "questions": Question.objects.filter(group__part=part).count(),
        "used": bool(user and user.is_authenticated and trial_used(user, test)),
    }


def question_in_trial(attempt: Any, question: Any) -> bool:
    if not attempt.trial_part_id:
        return True
    return bool(question.group_id and question.group.part_id == attempt.trial_part_id)
