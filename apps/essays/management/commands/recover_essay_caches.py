"""
Management command: recover_essay_caches

Umumiy (cross-account) esse baholash keshi uchun operatsion buyruq.

Muammo: bitta kesh kaliti uchun bitta AI chaqiruvini faqat "leader" jarayon
bajaradi (``status=processing`` + ``lease_owner`` + ``lease_expires_at``).
Worker OOM/restart/502 sababli yarim yo'lda o'lsa, kesh yozuvi ``processing``
holatida qolib ketadi va shu kalit uchun navbatdagi submission kutib qoladi.

Bu buyruq:
  * Eskirgan (muddati o'tgan yoki ijarasi umuman yo'q) ``processing``
    yozuvlarni ``failed`` holatiga o'tkazadi va ijara maydonlarini bo'shatadi —
    keyingi submission shu kalitni qayta egallab, AI'ni qayta chaqiradi.
  * ``--purge`` bilan: qayta ishlatilishi mumkin bo'lmagan yozuvlarni o'chiradi
    (eski ``cache_schema_version``, bekor qilingan yoki kesh muddati o'tgan).
    Yakunlangan va sxemasi dolzarb yozuvlar SAQLANADI; faol ijarali yozuv
    hech qachon o'chirilmaydi.
  * Oxirida process-local kesh metrikalarini (hit/miss/reuse/distributed/
    failed/stale_lease_recovered/ai_request va hit rate) chop etadi. Bu
    ko'rsatkichlar jarayonga xos — boshqa worker'larniki qo'shilmaydi.

Buyruq idempotent: ishlaydigan hech narsa bo'lmasa ham xato bermaydi
(0 qaytaradi).

Ishlatish:
    python manage.py recover_essay_caches
    python manage.py recover_essay_caches --purge
    python manage.py recover_essay_caches --purge --keep-days 7
"""

from __future__ import annotations

import logging

from django.core.management.base import BaseCommand

from apps.essays.metrics import cache_hit_rate, get_counter, snapshot
from apps.essays.services import (
    purge_obsolete_cache_entries,
    recover_stale_grading_cache_entries,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Umumiy esse baholash keshini tiklaydi: eskirgan (stale) ijaralarni "
        "bo'shatadi va ixtiyoriy ravishda qayta ishlatilmaydigan yozuvlarni "
        "tozalaydi. Faol ijarali yozuvlarga va baholarga tegmaydi."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--purge",
            action="store_true",
            help=(
                "Eskirgan kesh yozuvlarini o'chirish (eski sxema versiyasi, "
                "bekor qilingan yoki kesh muddati o'tgan). Faol ijarali va "
                "dolzarb yozuvlar saqlanadi."
            ),
        )
        parser.add_argument(
            "--keep-days",
            type=int,
            default=None,
            help=(
                "Faqat --purge bilan: necha kundan eski yozuvlar eskirgan "
                "hisoblanadi (default: ESSAY_GRADING_CACHE_DAYS sozlamasi)."
            ),
        )

    def handle(self, *args, **options):
        purge: bool = options["purge"]
        keep_days = options["keep_days"]

        if keep_days is not None and keep_days < 1:
            self.stdout.write(
                self.style.WARNING(
                    "--keep-days 1 dan kichik bo'lishi mumkin emas — e'tiborga olinmadi."
                )
            )
            keep_days = None

        recovered = recover_stale_grading_cache_entries()
        if recovered:
            self.stdout.write(
                self.style.SUCCESS(f"Stale ijaralar bo'shatildi: {recovered} ta yozuv.")
            )
        else:
            self.stdout.write("Stale ijara topilmadi.")

        purged = 0
        if purge:
            purged = purge_obsolete_cache_entries(keep_days=keep_days)
            if purged:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Eskirgan kesh yozuvlari o'chirildi: {purged} ta."
                    )
                )
            else:
                self.stdout.write("O'chiriladigan eskirgan kesh yozuvi topilmadi.")
        elif keep_days is not None:
            self.stdout.write(
                self.style.WARNING(
                    "--keep-days faqat --purge bilan ishlatiladi — hisobga olinmadi."
                )
            )

        counters = snapshot()
        self.stdout.write(
            "Kesh metrikalari (shu jarayon): "
            f"hit={get_counter('hit')} miss={get_counter('miss')} "
            f"reuse={get_counter('reuse')} distributed={get_counter('distributed')} "
            f"failed={get_counter('failed')} "
            f"stale_lease_recovered={get_counter('stale_lease_recovered')} "
            f"ai_request={get_counter('ai_request')} "
            f"hit_rate={cache_hit_rate()}"
        )
        if counters:
            self.stdout.write(f"Barcha hodisalar: {counters}")
        else:
            self.stdout.write(
                "Hodisalar yo'q: metrikalar jarayon ichida yig'iladi (worker/web "
                "loglarida essay_cache_event qatorlarini ko'ring)."
            )

        summary = f"Yakuniy: recovered={recovered}, purged={purged}"
        self.stdout.write(self.style.SUCCESS(summary))
        logger.info("recover_essay_caches: %s", summary)
