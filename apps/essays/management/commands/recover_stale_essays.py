"""
Management command: recover_stale_essays

Yoqilgan sabab (2026-09-16 outage): CELERY_TASK_ROUTES essa baholash task'larini
"essay_grading" queue'ga yo'naltirdi, worker esa faqat default "celery" queue'ni
 consume qilardi. Natija: submit → PENDING, task hech qachon bajarilmadi,
o'quvchilar "AI baholamoqda" spinnerida qotib qoldi.

Bu buyruq PENDING'da qotib qolgan (stale) submissionlarni xavfsiz qayta
navbatga qo'yadi:

  * Faqat status=PENDING va updated_at <= now - minutes (default 10) qatorlar.
  * Har bir qator atomic select_for_update + shartli claim bilan oladi va
    updated_at ni yangilaydi (dedup oynasi) — parallel ishga tushirish
    (cron/beat/command) bir qatorni ikki marta ololmaydi.
  * Task qayta urinishda ham statusni lock ostida qayta tekshiradi va
    apply_ai_result FSM guard'i stale worker yozuvini tashlaydi — double
    grading yo'q.
  * --dry-run: faqat ro'yxat chiqaradi, hech narsani o'zgartirmaydi.
  * --inline: broker tushib qolgan holat uchun gradingni shu jarayonda
    (task.apply) bajaradi. Ehtiyot bo'ling — LLM chaqiruvlari shu yerda
    ketadi (har biri ~30-180s).

Ishlatish:
    python manage.py recover_stale_essays --dry-run
    python manage.py recover_stale_essays
    python manage.py recover_stale_essays --minutes 10 --limit 100
    python manage.py recover_stale_essays --inline   # broker ishlamayotganda
"""
from __future__ import annotations

import logging

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.essays.models import EssaySubmission

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "PENDING holatida qotib qolgan esselarni (worker queue ochliganidan "
        "keyin ham) xavfsiz qayta baholashga yuboradi. Double grading yo'q: "
        "har bir qator atomic claim bilan olinadi va task statusni qayta "
        "tekshiradi."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--minutes",
            type=int,
            default=10,
            help="Necha daqiqadan beri PENDING'da turgan qatorlar stale hisoblanadi (default 10).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=50,
            help="Bir ishga tushirishda ko'pi bilan nechta qator qayta ishlanadi (default 50).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Faqat stale qatorlarni ko'rsatadi, hech narsani o'zgartirmaydi.",
        )
        parser.add_argument(
            "--inline",
            action="store_true",
            help=(
                "Broker orqali emas, shu jarayonda baholash (task.apply). "
                "Broker tushgan holat uchun — sekin, LLM chaqiruvi shu yerda."
            ),
        )

    def handle(self, *args, **options):
        minutes: int = max(1, options["minutes"])
        limit: int = max(1, options["limit"])
        dry_run: bool = options["dry_run"]
        inline: bool = options["inline"]

        threshold = timezone.now() - timedelta(minutes=minutes)
        stale_ids = list(
            EssaySubmission.objects.filter(
                status=EssaySubmission.Status.PENDING,
                updated_at__lte=threshold,
            )
            .order_by("updated_at")
            .values_list("id", flat=True)[:limit]
        )

        if not stale_ids:
            self.stdout.write(self.style.SUCCESS("Stale PENDING esse topilmadi."))
            return

        self.stdout.write(f"Stale PENDING: {len(stale_ids)} ta (threshold={threshold.isoformat()})")

        if dry_run:
            for sid in stale_ids:
                self.stdout.write(f"  [dry-run] submission={sid} qayta navbatga olinadi")
            self.stdout.write(self.style.NOTICE("DRY-RUN: hech narsa o'zgartirilmadi."))
            return

        # Inline rejimda broker kerak emas; .delay() xatosiga tushmaymiz.
        from apps.essays.tasks import grade_submission_task

        claimed = 0
        enqueued = 0
        failed = 0
        skipped = 0

        for sid in stale_ids:
            # Atomic claim: status haliyam PENDING va updated_at eski bo'lsa
            # olamiz, so'ng updated_at ni yangilaymiz — keyingi sweep/parallel
            # ishga tushirish shu qatorni darhol qayta olmaydi (dedup oynasi).
            try:
                with transaction.atomic():
                    row = (
                        EssaySubmission.objects.select_for_update()
                        .filter(
                            pk=sid,
                            status=EssaySubmission.Status.PENDING,
                            updated_at__lte=threshold,
                        )
                        .first()
                    )
                    if row is None:
                        skipped += 1
                        continue
                    row.save(update_fields=["updated_at"])
            except Exception as exc:
                failed += 1
                logger.warning("recover_stale_essays claim failed: id=%s %s", sid, exc)
                self.stdout.write(self.style.ERROR(f"  submission={sid} claim xatosi: {exc}"))
                continue

            claimed += 1
            if inline:
                try:
                    grade_submission_task.apply(
                        args=[sid],
                        kwargs={"fail_status": EssaySubmission.Status.ERROR},
                    )
                    enqueued += 1
                    self.stdout.write(self.style.SUCCESS(f"  submission={sid} inline baholandi/navbatga olindi"))
                except Exception as exc:
                    failed += 1
                    logger.error("recover_stale_essays inline grade failed: id=%s %s", sid, exc)
                    self.stdout.write(self.style.ERROR(f"  submission={sid} inline xato: {exc}"))
            else:
                try:
                    grade_submission_task.delay(
                        sid, fail_status=EssaySubmission.Status.ERROR,
                    )
                    enqueued += 1
                    self.stdout.write(self.style.SUCCESS(f"  submission={sid} navbatga qo'yildi"))
                except Exception as exc:
                    failed += 1
                    # Broker tushgan — updated_at yangilangan, keyingi ishga
                    # tushirishda yana oladi (stale oyna qayta to'lgach).
                    logger.error("recover_stale_essays enqueue failed: id=%s %s", sid, exc)
                    self.stdout.write(self.style.ERROR(f"  submission={sid} navbatga qo'yilmadi (broker?): {exc}"))

        summary = (
            f"Yakuniy: stale={len(stale_ids)}, claimed={claimed}, "
            f"enqueued={enqueued}, skipped={skipped}, failed={failed}"
        )
        self.stdout.write(self.style.SUCCESS(summary))
