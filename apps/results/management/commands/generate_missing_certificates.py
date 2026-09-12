"""
Management command: generate_missing_certificates

O'tgan lekin sertifikati yo'q natijalar uchun PDF sertifikat yaratadi.

Usage:
    python manage.py generate_missing_certificates
"""
from __future__ import annotations

import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "O'tgan testlar uchun yetishmayotgan PDF sertifikatlarni yaratish"

    def handle(self, *args, **options):
        from apps.results.models import Certificate, Result

        passed = Result.objects.filter(is_passed=True)
        passed_ids = set(passed.values_list("id", flat=True))
        cert_ids = set(Certificate.objects.values_list("result_id", flat=True))

        missing = passed_ids - cert_ids

        if not missing:
            self.stdout.write(self.style.SUCCESS(
                f"✅ Barcha o'tgan testlar sertifikatga ega "
                f"({Certificate.objects.count()} ta sertifikat)"
            ))
            return

        self.stdout.write(f"📝 {len(missing)} ta sertifikat kerak...")

        # Import the sync function
        from apps.tests.services import _generate_certificate_sync

        created = 0
        failed = 0

        for result_id in missing:
            result = Result.objects.select_related(
                "student", "test", "course"
            ).get(id=result_id)

            try:
                _generate_certificate_sync(result)
                created += 1
                self.stdout.write(self.style.SUCCESS(
                    f"  ✅ {result.student.get_full_name()} — "
                    f"{result.test.title} — {result.percentage}%"
                ))
            except Exception as e:
                failed += 1
                self.stdout.write(self.style.ERROR(
                    f"  ❌ {result.student.get_full_name()} — {e}"
                ))

        self.stdout.write(self.style.SUCCESS(
            f"\n📊 Natija: {created} yaratildi, {failed} xato, "
            f"{Certificate.objects.count()} ta jami sertifikat"
        ))
