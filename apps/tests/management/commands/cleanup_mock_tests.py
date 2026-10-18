"""
Django Management Command: cleanup_mock_tests

Deletes seeded legacy mock tests from the database so that only
user/teacher-created tests remain visible:
- #MOCK-SHUKUROV / MOCK-SHUKUROV
- #MOCK-BMB04 / MOCK-BMB04
- Optional: #MOCK-BMB-DIAGNOSTIC (with --all-mock flag)
"""
from __future__ import annotations

from typing import Any
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.tests.models import Test


class Command(BaseCommand):
    help = "Cleans up legacy seeded mock tests (#MOCK-SHUKUROV, #MOCK-BMB04, etc.) from the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--codes",
            nargs="+",
            default=["#MOCK-SHUKUROV", "MOCK-SHUKUROV", "#MOCK-BMB04", "MOCK-BMB04"],
            help="Specific mock codes to delete.",
        )
        parser.add_argument(
            "--all-seeded",
            action="store_true",
            help="Also delete #MOCK-BMB-DIAGNOSTIC and related seeded tests.",
        )

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        codes = list(options.get("codes") or [])
        if options.get("all_seeded"):
            codes.extend(["#MOCK-BMB-DIAGNOSTIC", "MOCK-BMB-DIAGNOSTIC"])

        # Normalize unique codes
        unique_codes = list(dict.fromkeys(codes))
        self.stdout.write(self.style.NOTICE(f"Searching for tests with mock codes: {unique_codes}"))

        tests_qs = Test.objects.filter(mock_code__in=unique_codes)
        found_count = tests_qs.count()

        if found_count == 0:
            self.stdout.write(self.style.WARNING("No matching mock tests found in the database."))
            return

        deleted_summary = []
        for test in tests_qs:
            deleted_summary.append(f"ID={test.id}, Title='{test.title}', Code='{test.mock_code}'")

        count, deleted_breakdown = tests_qs.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully deleted {found_count} test(s) ({count} related objects):\n"
                + "\n".join(f"  - {item}" for item in deleted_summary)
            )
        )
