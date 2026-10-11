"""
Management command: subscription_maintenance

Operatsion buyruq — Grandec tijoriy obuna tizimini kuzatish va tozalash.

Muammo: ``UserSubscription`` obyektida ``status=active`` qolib, ``expires_at``
o'tib ketishi mumkin (veb/Telegram oqimlari har doim ham EXPIRED ga
o'tkazmaydi). Shu sababli muddati o'tgan obunalar "faol" ko'rinib qoladi.

Bu buyruq:
  * ``--expire`` (default): muddati o'tgan ACTIVE obunalarni EXPIRED ga
    o'tkazadi (``expire_overdue_subscriptions``). O'quvchining esselari,
    natijalari va homiylik yozuvlariga TEGMAYDI.
  * ``--reminders``: yaqin 3 kun ichida tugaydigan obunalar sonini chop etadi
    (hech qanday xabar YUBORMAYDI — faqat hisobot).
  * ``--stats``: rejalar konfiguratsiyasi, joriy kvota oynasidagi sarf
    hisoblari, homiylik/ustunlik soni, Telegram buyurtmalari va esse kesh
    metrikalarini chop etadi.

Buyruq idempotent: qayta ishga tushirish xavfsiz, xatolar yutilmaydi.

Ishlatish:
    python manage.py subscription_maintenance
    python manage.py subscription_maintenance --reminders --stats
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Count

from apps.payments.entitlements import quota_period_start
from apps.payments.models import (
    EntitlementAuditLog,
    SubscriptionOverride,
    SubscriptionPlan,
    SubscriptionUsage,
    TeacherSponsorship,
    TelegramOrder,
    UserSubscription,
)
from apps.payments.subscriptions import (
    expire_overdue_subscriptions,
    subscription_expiring_between,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Obuna tizimini kuzatadi va tozalaydi: muddati o'tgan obunalarni "
        "EXPIRED ga o'tkazadi, ixtiyoriy ravishda tugash eslatmalari va "
        "operatsion statistikani chop etadi. Foydalanuvchi ishiga tegmaydi."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--expire",
            action="store_true",
            help="Muddati o'tgan ACTIVE obunalarni EXPIRED qilish (default).",
        )
        parser.add_argument(
            "--reminders",
            action="store_true",
            help=(
                "Yaqin 3 kun ichida tugaydigan obunalar sonini chop etish "
                "(xabar yuborilmaydi)."
            ),
        )
        parser.add_argument(
            "--stats",
            action="store_true",
            help="Reja konfiguratsiyasi, kvota sarfi va buyurtma statistikasi.",
        )

    def handle(self, *args, **options):
        # ``--expire`` is the default behaviour; running with no flags still
        # performs it, matching the cron usage in deployment.
        run_expire = options["expire"] or not (
            options["reminders"] or options["stats"]
        )

        expired = 0
        if run_expire:
            expired = expire_overdue_subscriptions()
            if expired:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Muddati o'tgan obunalar EXPIRED qilindi: {expired} ta."
                    )
                )
            else:
                self.stdout.write("Muddati o'tgan faol obuna topilmadi.")

        reminder_count = 0
        if options["reminders"]:
            expiring = subscription_expiring_between(timedelta(days=3))
            reminder_count = len(expiring)
            self.stdout.write(
                f"3 kun ichida tugaydigan obunalar: {reminder_count} ta "
                "(xabar yuborilmadi)."
            )
            for subscription in expiring[:20]:
                self.stdout.write(
                    f"  - {subscription.user.email}: {subscription.plan.name} "
                    f"→ {subscription.expires_at:%Y-%m-%d %H:%M}"
                )

        if options["stats"]:
            self._print_stats()

        summary = (
            f"Yakuniy: expired={expired}, expiring_soon={reminder_count}"
        )
        self.stdout.write(self.style.SUCCESS(summary))
        logger.info("subscription_maintenance: %s", summary)

    # -- statistics ----------------------------------------------------------

    def _print_stats(self) -> None:
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("REJALAR"))
        plans = SubscriptionPlan.objects.all().order_by("sort_order", "price_monthly")
        if not plans:
            self.stdout.write("  Reja topilmadi.")
        for plan in plans:
            snapshot = plan.quota_snapshot()
            self.stdout.write(
                f"  {plan.plan_type:<18} {plan.name:<28} "
                f"{snapshot['price_uzs']:>8,} UZS  "
                f"stars={plan.telegram_stars_price!r}  "
                f"img={snapshot['image_essay_weekly_limit']!r} "
                f"txt={snapshot['text_essay_weekly_limit']!r} "
                f"cd={snapshot['text_essay_cooldown_hours']!r} "
                f"test={snapshot['test_limit']!r} "
                f"unlim=({int(snapshot['is_unlimited_image_essays'])}"
                f"{int(snapshot['is_unlimited_text_essays'])}"
                f"{int(snapshot['is_unlimited_tests'])}) "
                f"public={plan.is_public} active={plan.is_active}"
            )

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"KVOTA SARFI (joriy oyna: {quota_period_start():%Y-%m-%d %H:%M %Z})"
        ))
        rows = (
            SubscriptionUsage.objects.filter(created_at__gte=quota_period_start())
            .values("kind", "status")
            .annotate(total=Count("id"))
            .order_by("kind", "status")
        )
        if not rows:
            self.stdout.write("  Joriy oynada sarf yo'q.")
        for row in rows:
            self.stdout.write(
                f"  {row['kind']:<12} {row['status']:<10} {row['total']}"
            )
        charged = SubscriptionUsage.objects.filter(
            created_at__gte=quota_period_start(), counts_towards_quota=True,
        ).exclude(status=SubscriptionUsage.Status.RELEASED).count()
        not_charged = SubscriptionUsage.objects.filter(
            created_at__gte=quota_period_start(), counts_towards_quota=False,
        ).count()
        self.stdout.write(
            f"  Limitdan hisoblangan: {charged} · hisoblanmagan (cheksiz/"
            f"homiylik): {not_charged}"
        )

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("KIRISH HUQUQI"))
        active_subs = UserSubscription.objects.filter(
            status=UserSubscription.Status.ACTIVE,
        ).count()
        self.stdout.write(f"  Faol obunalar: {active_subs}")
        sponsorships = list(
            TeacherSponsorship.objects.filter(
                is_active=True, approved_at__isnull=False,
            ).select_related("student", "group", "group__teacher")
        )
        effective_sponsorships = [s for s in sponsorships if s.is_effective]
        pending_sponsorships = TeacherSponsorship.objects.filter(
            is_active=True, approved_at__isnull=True,
        ).count()
        self.stdout.write(
            f"  Homiyliklar: jami={len(sponsorships)}, "
            f"samarali={len(effective_sponsorships)}, "
            f"tasdiq kutilayotgan={pending_sponsorships}"
        )
        active_overrides = SubscriptionOverride.objects.filter(is_active=True).count()
        self.stdout.write(f"  Faol admin ustunliklari: {active_overrides}")

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("TELEGRAM BUYURTMALARI"))
        orders = (
            TelegramOrder.objects.values("status")
            .annotate(total=Count("id"))
            .order_by("status")
        )
        if not orders:
            self.stdout.write("  Buyurtma yo'q.")
        for row in orders:
            self.stdout.write(f"  {row['status']:<14} {row['total']}")
        paid = TelegramOrder.objects.filter(
            status=TelegramOrder.Status.PAID,
        ).aggregate(total=Count("id"), stars=Count("amount_stars"))
        self.stdout.write(f"  To'langan: {paid['total']} ta")
        audit_count = EntitlementAuditLog.objects.count()
        self.stdout.write(f"  Homiylik/obuna tarixi yozuvlari: {audit_count}")

        self._print_cache_stats()

    def _print_cache_stats(self) -> None:
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("ESSE KESH METRIKALARI"))
        try:
            from apps.essays import metrics
        except Exception as exc:  # pragma: no cover - metrics module optional
            self.stdout.write(f"  Kesh metrikalari mavjud emas: {exc}")
            return
        try:
            self.stdout.write(
                "  Shu jarayon: "
                f"hit={metrics.get_counter('hit')} "
                f"miss={metrics.get_counter('miss')} "
                f"reuse={metrics.get_counter('reuse')} "
                f"ai_request={metrics.get_counter('ai_request')} "
                f"hit_rate={metrics.cache_hit_rate()}"
            )
            snapshot = metrics.snapshot()
            if snapshot:
                self.stdout.write(f"  Barcha hodisalar: {snapshot}")
            else:
                self.stdout.write(
                    "  Hodisalar yo'q (metrikalar jarayon ichida yig'iladi)."
                )
        except Exception as exc:  # pragma: no cover - defensive, never silent
            self.stdout.write(
                self.style.WARNING(f"  Kesh metrikalarini o'qib bo'lmadi: {exc}")
            )
