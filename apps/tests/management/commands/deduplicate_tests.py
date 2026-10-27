"""
Django Management Command: deduplicate_tests

Safely detects and removes duplicate / cloned tests:
1. Two tests are duplicates if and only if:
   - Same title (stripped, case-insensitive)
   - Same subject ('uzbek' / 'english')
   - Same questions count (> 0)
   - 100% matching question sequence and content (verified via SHA-256 fingerprint).
2. Distinct tests (Variant 1, Variant 2, Variant 3, Attestatsiya 2026, IELTS Mock 1, IELTS Mock 2)
   are never touched.
3. Canonical primary test selection:
   - Test with the highest TestAttempt count, or lowest ID if attempt count is tied.
4. Safe migration:
   - All TestAttempt, Result, Certificate, Tournament, and Homework references
     are re-pointed to the primary test before deletion.
5. Atomic transaction and --dry-run support.
"""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.arena.models import Tournament
from apps.courses.models import Homework
from apps.results.models import Certificate, Result
from apps.tests.models import Test, TestAttempt

logger = logging.getLogger(__name__)


def compute_test_questions_fingerprint(test: Test) -> tuple[int, str]:
    """Computes (question_count, sha256_hash) of ordered question content."""
    qs = list(
        test.questions.order_by("position", "id").values_list(
            "position", "text", "correct_text", "question_type"
        )
    )
    if not qs:
        return (0, "")

    hasher = hashlib.sha256()
    for pos, text, corr, qt in qs:
        norm_t = " ".join((text or "").strip().lower().split())
        norm_c = " ".join((corr or "").strip().lower().split())
        hasher.update(f"{pos}:{norm_t}:{norm_c}:{qt}|".encode("utf-8"))

    return (len(qs), hasher.hexdigest())


class Command(BaseCommand):
    help = "Deduplicates cloned tests while safely preserving student attempts, results, and certificates."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Scan and report duplicate tests without making any database changes.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        dry_run: bool = options.get("dry_run", False)

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "Running deduplication in DRY-RUN mode. No changes will be saved."
                )
            )
        else:
            self.stdout.write(
                self.style.NOTICE("Scanning database for duplicate tests...")
            )

        all_tests = list(Test.objects.all().prefetch_related("questions", "attempts"))
        self.stdout.write(f"Total tests evaluated: {len(all_tests)}")

        groups: dict[tuple[str, str, int, str], list[Test]] = defaultdict(list)

        for test in all_tests:
            q_count, fp = compute_test_questions_fingerprint(test)
            if q_count == 0:
                continue

            normalized_title = test.title.strip().lower()
            key = (test.subject, normalized_title, q_count, fp)
            groups[key].append(test)

        cloned_groups = {k: v for k, v in groups.items() if len(v) > 1}

        if not cloned_groups:
            self.stdout.write(
                self.style.SUCCESS(
                    "[OK] No duplicate cloned tests detected. Database is clean!"
                )
            )
            return

        self.stdout.write(
            self.style.WARNING(
                f"Found {len(cloned_groups)} test group(s) with duplicate clones."
            )
        )

        total_clones_removed = 0
        total_attempts_migrated = 0

        for key, tests in cloned_groups.items():
            subject, norm_title, q_count, _ = key
            # Sort: primary has most attempts, then lowest ID
            sorted_tests = sorted(
                tests,
                key=lambda t: (-t.attempts.count(), t.id),
            )
            primary = sorted_tests[0]
            clones = sorted_tests[1:]

            self.stdout.write(
                f"\n--- Group: '{norm_title}' (Subject: {subject}, Questions: {q_count}) ---"
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"  [PRIMARY CANONICAL] ID: {primary.id} (code: {primary.mock_code}, attempts: {primary.attempts.count()})"
                )
            )

            for clone in clones:
                attempt_count = clone.attempts.count()
                self.stdout.write(
                    self.style.NOTICE(
                        f"  [CLONE TO MERGE] ID: {clone.id} (code: {clone.mock_code}, attempts: {attempt_count})"
                    )
                )

                if dry_run:
                    total_clones_removed += 1
                    total_attempts_migrated += attempt_count
                    continue

                with transaction.atomic():
                    # 1. Migrate attempts
                    migrated_attempts = TestAttempt.objects.filter(test=clone).update(
                        test=primary
                    )
                    # 2. Migrate results
                    Result.objects.filter(test=clone).update(test=primary)
                    # 3. Migrate certificates
                    Certificate.objects.filter(test=clone).update(test=primary)
                    # 4. Migrate tournaments
                    Tournament.objects.filter(test=clone).update(test=primary)
                    # 5. Migrate homework
                    Homework.objects.filter(test=clone).update(test=primary)

                    # 6. Preserve mock_code if primary didn't have one
                    if not primary.mock_code and clone.mock_code:
                        primary.mock_code = clone.mock_code
                        primary.save(update_fields=["mock_code"])

                    # 7. Clear mock_code on clone to avoid unique constraint issues
                    if clone.mock_code:
                        clone.mock_code = None
                        clone.save(update_fields=["mock_code"])

                    # 8. Delete clone test (cascade removes its questions and choices)
                    clone_id = clone.id
                    clone.delete()

                    total_clones_removed += 1
                    total_attempts_migrated += migrated_attempts

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"    Successfully merged clone ID {clone_id} into primary ID {primary.id} ({migrated_attempts} attempts migrated)."
                        )
                    )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"\n[DRY RUN SUMMARY] Would delete {total_clones_removed} clone(s) and migrate {total_attempts_migrated} attempt(s)."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n[COMPLETE] Successfully eliminated {total_clones_removed} duplicate test(s) and safely migrated {total_attempts_migrated} attempt(s)!"
                )
            )
