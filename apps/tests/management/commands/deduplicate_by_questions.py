"""
Django Management Command: deduplicate_by_questions

Identifies and safely deduplicates tests based STRICTLY ON QUESTION CONTENT,
COMPLETELY REGARDLESS OF TEST TITLES:
1. Two tests are duplicates if:
   - Same subject ('uzbek' / 'english')
   - Questions count > 0
   - AND either:
     a) 100% matching question text sequence (full content SHA-256 fingerprint)
     b) OR 100% matching first 5 questions (prefix-5 SHA-256 fingerprint)
     c) OR 100% matching question texts ignoring order/numbering (sorted question texts SHA-256)
2. Canonical primary selection:
   - Within each group of content-duplicate tests:
     * Primary is the one with the highest TestAttempt count.
     * Tied by attempts count -> lowest ID (oldest original test).
   - All other tests in the group are marked as CLONES to be merged & removed.
3. Safe atomic dependency migration:
   - TestAttempt: all student attempts moved to primary test.
   - StudentAnswer: remapped to primary test questions and choices so answer records are preserved.
   - Result: all results moved to primary test.
   - Certificate: all certificates moved to primary test.
   - Tournament: all tournaments moved to primary test.
   - Homework: all homework moved to primary test.
   - mock_code: preserved if primary lacks one, cleared on clone before deletion.
   - Cascade delete of clones.
4. Full --dry-run support.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections import defaultdict
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.arena.models import Tournament
from apps.courses.models import Homework
from apps.results.models import Certificate, Result
from apps.tests.models import Choice, Question, StudentAnswer, Test, TestAttempt

logger = logging.getLogger(__name__)


def normalize_text(text: str | None) -> str:
    """Normalize text: lowercase, strip, collapse whitespace."""
    if not text:
        return ""
    return " ".join(text.strip().lower().split())


def clean_question_text(text: str | None) -> str:
    """Normalize question text and strip common leading numbering prefixes."""
    norm = normalize_text(text)
    # Remove leading numbering like "1-savol.", "1-savol:", "1.", "1)", "question 1:", "question 1."
    cleaned = re.sub(
        r"^(?:question\s*\d+[\.\:\)]|\d+[\.\:\)\-]\s*(?:savol[\.\:\)]?)?)\s*",
        "",
        norm,
    )
    return cleaned.strip()


def compute_question_fingerprints(test: Test) -> dict[str, Any]:
    """Computes content fingerprints for a test based solely on its questions."""
    qs = list(
        test.questions.order_by("position", "id").values_list(
            "position", "text", "correct_text", "question_type"
        )
    )
    q_count = len(qs)
    if q_count == 0:
        return {
            "q_count": 0,
            "full_fp": "",
            "clean_full_fp": "",
            "prefix_5_fp": "",
            "clean_prefix_5_fp": "",
            "sorted_clean_fp": "",
        }

    clean_texts = [clean_question_text(text) for _, text, _, _ in qs]

    # 1. Full sequential fingerprint
    h_full = hashlib.sha256()
    for _, text, corr, qt in qs:
        h_full.update(
            f"{normalize_text(text)}:{normalize_text(corr)}:{qt}|".encode("utf-8")
        )
    full_fp = h_full.hexdigest()

    # 2. Clean full sequential fingerprint (without numbering prefix)
    h_clean_full = hashlib.sha256()
    for _, text, corr, qt in qs:
        h_clean_full.update(
            f"{clean_question_text(text)}:{normalize_text(corr)}:{qt}|".encode(
                "utf-8"
            )
        )
    clean_full_fp = h_clean_full.hexdigest()

    # 3. Prefix-5 fingerprint (or all if < 5)
    limit = min(q_count, 5)
    h_p5 = hashlib.sha256()
    for _, text, corr, qt in qs[:limit]:
        h_p5.update(
            f"{normalize_text(text)}:{normalize_text(corr)}:{qt}|".encode("utf-8")
        )
    prefix_5_fp = h_p5.hexdigest()

    # 4. Clean prefix-5 fingerprint
    h_clean_p5 = hashlib.sha256()
    for _, text, corr, qt in qs[:limit]:
        h_clean_p5.update(
            f"{clean_question_text(text)}:{normalize_text(corr)}:{qt}|".encode(
                "utf-8"
            )
        )
    clean_prefix_5_fp = h_clean_p5.hexdigest()

    # 5. Sorted clean fingerprint (order-independent)
    sorted_clean = sorted(clean_texts)
    h_sorted = hashlib.sha256()
    for s_txt in sorted_clean:
        h_sorted.update(f"{s_txt}|".encode("utf-8"))
    sorted_clean_fp = h_sorted.hexdigest()

    return {
        "q_count": q_count,
        "full_fp": full_fp,
        "clean_full_fp": clean_full_fp,
        "prefix_5_fp": prefix_5_fp,
        "clean_prefix_5_fp": clean_prefix_5_fp,
        "sorted_clean_fp": sorted_clean_fp,
    }


def are_tests_duplicates(
    test_a: Test, fp_a: dict[str, Any], test_b: Test, fp_b: dict[str, Any]
) -> bool:
    """Returns True if test_a and test_b have duplicate questions regardless of titles."""
    if test_a.id == test_b.id:
        return False
    if test_a.subject != test_b.subject:
        return False
    if fp_a["q_count"] == 0 or fp_b["q_count"] == 0:
        return False

    # Condition 1: 100% full matching sequence of questions
    if fp_a["full_fp"] == fp_b["full_fp"]:
        return True
    if fp_a["clean_full_fp"] == fp_b["clean_full_fp"]:
        return True

    # Condition 2: Question count equal and first 5 questions match 100%
    if fp_a["q_count"] == fp_b["q_count"]:
        if fp_a["prefix_5_fp"] == fp_b["prefix_5_fp"]:
            return True
        if fp_a["clean_prefix_5_fp"] == fp_b["clean_prefix_5_fp"]:
            return True
        if fp_a["sorted_clean_fp"] == fp_b["sorted_clean_fp"]:
            return True

    # Condition 3: If both have >= 5 questions and first 5 questions are 100% identical
    if fp_a["q_count"] >= 5 and fp_b["q_count"] >= 5:
        if fp_a["prefix_5_fp"] == fp_b["prefix_5_fp"]:
            return True
        if fp_a["clean_prefix_5_fp"] == fp_b["clean_prefix_5_fp"]:
            return True

    return False


class UnionFind:
    """Disjoint-set data structure to cluster duplicate tests into connected components."""

    def __init__(self, elements: list[int]):
        self.parent = {e: e for e in elements}

    def find(self, i: int) -> int:
        if self.parent[i] == i:
            return i
        self.parent[i] = self.find(self.parent[i])
        return self.parent[i]

    def union(self, i: int, j: int) -> None:
        root_i = self.find(i)
        root_j = self.find(j)
        if root_i != root_j:
            self.parent[root_i] = root_j


class Command(BaseCommand):
    help = "Deduplicates tests strictly by question content regardless of test title."

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
                    "Running content-based deduplication in DRY-RUN mode. No changes will be saved."
                )
            )
        else:
            self.stdout.write(
                self.style.NOTICE(
                    "Scanning database for duplicate tests by question content..."
                )
            )

        all_tests = list(
            Test.objects.all().prefetch_related("questions", "attempts")
        )
        self.stdout.write(f"Total tests evaluated: {len(all_tests)}")

        # Compute fingerprints for all tests
        fps: dict[int, dict[str, Any]] = {}
        for test in all_tests:
            fps[test.id] = compute_question_fingerprints(test)

        # Build clusters using Union-Find
        test_ids = [t.id for t in all_tests]
        uf = UnionFind(test_ids)

        n = len(all_tests)

        for i in range(n):
            for j in range(i + 1, n):
                t_a = all_tests[i]
                t_b = all_tests[j]
                if are_tests_duplicates(t_a, fps[t_a.id], t_b, fps[t_b.id]):
                    uf.union(t_a.id, t_b.id)

        # Group tests by connected component root
        groups_by_root: dict[int, list[Test]] = defaultdict(list)
        for test in all_tests:
            root = uf.find(test.id)
            groups_by_root[root].append(test)

        # Filter to duplicate groups (size > 1)
        duplicate_groups = [g for g in groups_by_root.values() if len(g) > 1]

        if not duplicate_groups:
            self.stdout.write(
                self.style.SUCCESS(
                    "[OK] No duplicate cloned tests detected by question content. Database is clean!"
                )
            )
            return

        self.stdout.write(
            self.style.WARNING(
                f"Found {len(duplicate_groups)} test group(s) with duplicate cloned questions."
            )
        )

        total_clones_removed = 0
        total_attempts_migrated = 0

        for group_idx, tests in enumerate(duplicate_groups, 1):
            # Sort: primary has most attempts, then lowest ID (oldest test)
            sorted_tests = sorted(
                tests,
                key=lambda t: (-t.attempts.count(), t.id),
            )
            primary = sorted_tests[0]
            clones = sorted_tests[1:]

            self.stdout.write(
                f"\n=== Group {group_idx}: Subject: {primary.subject}, Questions: {fps[primary.id]['q_count']} ==="
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"  [PRIMARY CANONICAL] ID: {primary.id} | Code: '{primary.mock_code}' | Title: '{primary.title}' | Attempts: {primary.attempts.count()}"
                )
            )

            for clone in clones:
                attempt_count = clone.attempts.count()
                self.stdout.write(
                    self.style.NOTICE(
                        f"  [CLONE TO MERGE] ID: {clone.id} | Code: '{clone.mock_code}' | Title: '{clone.title}' | Attempts: {attempt_count}"
                    )
                )

                if dry_run:
                    total_clones_removed += 1
                    total_attempts_migrated += attempt_count
                    continue

                with transaction.atomic():
                    # Map questions from clone to primary by position
                    primary_q_by_pos = {
                        q.position: q for q in primary.questions.all()
                    }
                    for clone_q in clone.questions.all():
                        target_q = primary_q_by_pos.get(clone_q.position)
                        if target_q:
                            # 1. Re-map student answers so they survive deletion
                            StudentAnswer.objects.filter(
                                question=clone_q
                            ).update(question=target_q)

                            # 2. Re-map selected_choices M2M
                            target_choices_by_pos = {
                                c.position: c for c in target_q.choices.all()
                            }
                            for clone_c in clone_q.choices.all():
                                target_c = target_choices_by_pos.get(
                                    clone_c.position
                                )
                                if target_c:
                                    through_model = (
                                        StudentAnswer.selected_choices.through
                                    )
                                    through_model.objects.filter(
                                        choice_id=clone_c.id
                                    ).update(choice_id=target_c.id)

                    # 3. Resolve potential UniqueConstraint violation on in_progress attempts
                    primary_in_progress_student_ids = set(
                        TestAttempt.objects.filter(
                            test=primary, status="in_progress"
                        ).values_list("student_id", flat=True)
                    )
                    TestAttempt.objects.filter(
                        test=clone,
                        status="in_progress",
                        student_id__in=primary_in_progress_student_ids,
                    ).update(status="completed")

                    # 4. Migrate attempts
                    migrated_attempts = TestAttempt.objects.filter(
                        test=clone
                    ).update(test=primary)

                    # 5. Migrate results
                    Result.objects.filter(test=clone).update(test=primary)

                    # 6. Migrate certificates
                    Certificate.objects.filter(test=clone).update(test=primary)

                    # 7. Migrate tournaments
                    Tournament.objects.filter(test=clone).update(test=primary)

                    # 8. Migrate homework
                    Homework.objects.filter(test=clone).update(test=primary)

                    # 9. Preserve mock_code on primary if primary didn't have one
                    if not primary.mock_code and clone.mock_code:
                        primary.mock_code = clone.mock_code
                        primary.save(update_fields=["mock_code"])

                    # 10. Clear mock_code on clone to avoid unique constraint issues
                    if clone.mock_code:
                        clone.mock_code = None
                        clone.save(update_fields=["mock_code"])

                    # 11. Delete clone test (cascades clone questions, choices, passages)
                    clone_id = clone.id
                    clone_title = clone.title
                    clone.delete()

                    total_clones_removed += 1
                    total_attempts_migrated += migrated_attempts

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"    Successfully merged clone ID {clone_id} ('{clone_title}') into primary ID {primary.id} ({migrated_attempts} attempts migrated)."
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
