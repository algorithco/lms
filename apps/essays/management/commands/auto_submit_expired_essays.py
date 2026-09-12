"""
Management command: auto_submit_expired_essays

Muddati o'tgan, hali yuborilmagan esse submissionlarni topib,
avtomatik baholaydi (yoki o'qituvchiga fallback qiladi).

Ishlatish:
    python manage.py auto_submit_expired_essays

Tavsiya etilgan chastota: har 1-2 daqiqa (cron yoki systemd timer).

Cron misoli (har 2 daqiqa):
    */2 * * * * cd /path/to/lms_platform && python manage.py auto_submit_expired_essays >> logs/auto_submit.log 2>&1
"""
from __future__ import annotations

import logging

from django.core.management.base import BaseCommand

from apps.essays.models import EssaySubmission

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Muddati o'tgan draft esse larni avtomatik baholash. "
        "Brauzer yopilgan holatlarda ishlaydi."
    )

    def handle(self, *args, **options):
        # Muddati o'tgan, hali DRAFT holatida (yuborilmagan) submissionlarni topish
        expired_submissions = EssaySubmission.objects.filter(
            status=EssaySubmission.Status.DRAFT,
            password_verified_at__isnull=False,
            auto_submitted=False,
            essay_text__gt="",  # bo'sh emas
        ).select_related("topic")

        count = 0
        errors = 0

        for submission in expired_submissions:
            if not submission.is_expired:
                continue  # hali vaqt bor

            try:
                from apps.essays.services import auto_submit_essay

                result = auto_submit_essay(submission)
                count += 1

                if result["fallback"]:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  submission={submission.id} → PENDING_TEACHER "
                            f"(fallback: {result.get('error', 'bosh matn')})"
                        )
                    )
                elif result["success"]:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  submission={submission.id} → GRADED "
                            f"(score={submission.total_score}/{submission.max_score})"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            f"  submission={submission.id} → ERROR: {result['error']}"
                        )
                    )
                    errors += 1

            except Exception as e:
                errors += 1
                logger.error(
                    "Failed to auto-submit submission=%d: %s",
                    submission.id, str(e), exc_info=True,
                )
                self.stdout.write(
                    self.style.ERROR(f"  submission={submission.id} → EXCEPTION: {e}")
                )

        if count == 0:
            self.stdout.write(self.style.NOTICE("Muddati o'tgan draft esse topilmadi."))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nYakuniy: {count} ta submission avtomatik yuborildi, "
                    f"{errors} ta xatolik."
                )
            )
