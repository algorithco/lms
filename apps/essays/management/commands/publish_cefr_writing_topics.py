"""Offer the CEFR Multi-level Writing tasks (1.1, 1.2, Part 2) in the Essay studio.

    python manage.py publish_cefr_writing_topics              # dry run (default)
    python manage.py publish_cefr_writing_topics --apply

The task text is NOT written here: it is read from the ``written`` questions of
published CEFR Multi-level tests (the Record Mock), so the studio shows exactly
what the exam shows. One EssayTopic per task is created (English subject,
category "multilevel"), once: rerunning never duplicates or overwrites a topic.
Grading then goes through the same honest pipeline as every other essay: with
no AI result the essay is "not graded" and the allowance is returned.

Nothing is created unless ``--apply`` is given.
"""

from __future__ import annotations

import re
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.essays.models import EssayTopic
from apps.tests.models import Question, Test

_RANGE = re.compile(r"(\d{2,3})\s*[–-]\s*(\d{2,3})\s*words?", re.I)
_ABOUT = re.compile(r"about\s+(\d{2,3})\s*words?", re.I)


def _limits(text: str) -> tuple[int, int] | None:
    m = _RANGE.search(text)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = _ABOUT.search(text)
    if m:
        n = int(m.group(1))
        return max(10, int(n * 0.8)), int(n * 1.5)
    return None


def _title(text: str) -> str:
    first = (text or "").strip().splitlines()[0] if (text or "").strip() else ""
    first = re.sub(r"\s*[—-]\s*Write .*$", "", first).strip()
    return first[:300]


class Command(BaseCommand):
    help = "Create Essay-studio topics from the Writing tasks of published CEFR Multi-level tests."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Create the topics (default: dry run).")

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        apply = options["apply"]
        tests = Test.objects.filter(exam_type=Test.ExamType.CEFR_MULTILEVEL, status=Test.Status.PUBLISHED)
        found = created = existing = skipped = 0
        for test in tests:
            for q in Question.objects.filter(test=test, question_type="written").order_by("position", "id"):
                found += 1
                text = (q.text or "").strip()
                limits = _limits(text)
                title = _title(text)
                if not title or not limits:
                    skipped += 1
                    self.stdout.write(f"  skip question {q.id}: no title or word range in the task text")
                    continue
                if EssayTopic.objects.filter(
                    category=EssayTopic.Category.MULTILEVEL, title=title, description=text
                ).exists():
                    existing += 1
                    continue
                created += 1
                self.stdout.write(f"  {'create' if apply else 'would create'}: {title}  ({limits[0]}-{limits[1]} words)")
                if apply:
                    EssayTopic.objects.create(
                        title=title,
                        description=text,
                        subject="english",
                        category=EssayTopic.Category.MULTILEVEL,
                        rubric_type=(
                            EssayTopic.RubricType.IELTS_TASK2 if limits[0] >= 150 else EssayTopic.RubricType.IELTS_TASK1
                        ),
                        word_limit_min=limits[0],
                        word_limit_max=limits[1],
                        is_active=True,
                    )
        suffix = "" if apply else " (dry run, nothing written; pass --apply)"
        self.stdout.write(
            f"Writing tasks found {found}, created {created if apply else 0}, "
            f"would create {0 if apply else created}, already published {existing}, skipped {skipped}{suffix}."
        )
