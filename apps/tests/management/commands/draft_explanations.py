"""
Write draft explanations (and evidence sentences) for questions that have none.

    python manage.py draft_explanations --exam-type cefr_multilevel --dry-run
    python manage.py draft_explanations --test-id 13

Only fills empty ``explanation`` fields, never overwrites staff text, and marks
every draft ``explanation_status="draft"``. Safe to run twice.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.tests.explanation_drafts import draft_for
from apps.tests.models import Question, Test


class Command(BaseCommand):
    help = "Draft explanations from the stored passage and answer key (no AI, no invention)."

    def add_arguments(self, parser):
        parser.add_argument("--test-id", type=int, action="append", help="Test id (repeatable).")
        parser.add_argument("--exam-type", help="Every test of this exam type, e.g. cefr_multilevel.")
        parser.add_argument("--lang", default="uz", choices=["uz", "ru", "en"])
        parser.add_argument("--dry-run", action="store_true", help="Show counts, write nothing.")

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        tests = Test.objects.all()
        if options["test_id"]:
            tests = tests.filter(id__in=options["test_id"])
        elif options["exam_type"]:
            tests = tests.filter(exam_type=options["exam_type"])
        else:
            raise CommandError("Pass --test-id or --exam-type.")

        drafted = skipped = 0
        for test in tests:
            questions = (
                Question.objects.filter(test=test, explanation="")
                .select_related("section", "group", "group__passage", "reading_passage")
                .prefetch_related("choices", "gap_blanks")
            )
            for q in questions:
                draft = draft_for(q, options["lang"])
                if not draft:
                    skipped += 1
                    continue
                drafted += 1
                if not options["dry_run"]:
                    q.explanation, q.evidence = draft
                    q.explanation_status = Question.ExplanationStatus.DRAFT
                    q.save(update_fields=["explanation", "evidence", "explanation_status"])
        suffix = " (dry run, nothing written)" if options["dry_run"] else ""
        self.stdout.write(f"Drafted {drafted}, left without explanation {skipped}{suffix}.")
