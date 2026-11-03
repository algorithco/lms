"""Report paid-tier access that no approved payment backs. READ ONLY.

    python manage.py audit_unpaid_subscriptions [--all] [--json]

Lists active STARTER/PRO/PREMIUM subscriptions without a completed payment
(PaymentHistory / approved receipt / Stars order) and approved teacher
sponsorships created by the removed automatic group-join grant, plus how much
AI work each account used since the access started. Prints only user ids — no
names, emails or phone numbers. Nothing is changed: revocation is a separate,
explicit decision.
"""

from __future__ import annotations

import json
from collections import Counter

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

PAID_PLANS = ("start", "starter", "pro", "premium", "family")


class Command(BaseCommand):
    help = "Report subscriptions/sponsorships without an approved payment (read only)."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="Include expired/inactive rows.")
        parser.add_argument("--json", action="store_true", help="Machine-readable output.")

    def handle(self, *args, **opts):
        from apps.essays.models import EssaySubmission
        from apps.payments.models import (
            PaymentHistory,
            PaymentReceipt,
            TeacherSponsorship,
            TelegramOrder,
            UserSubscription,
        )
        from apps.speaking.models import SpeakingSubmission

        now = timezone.now()
        subs = UserSubscription.objects.select_related("plan").filter(plan__plan_type__in=PAID_PLANS)
        if not opts["all"]:
            subs = subs.filter(status=UserSubscription.Status.ACTIVE, expires_at__gt=now)

        rows = []
        for sub in subs.order_by("created_at"):
            paid = (
                PaymentHistory.objects.filter(
                    user_id=sub.user_id, status=PaymentHistory.PaymentStatus.COMPLETED
                ).exists()
                or PaymentReceipt.objects.filter(
                    user_id=sub.user_id, status=PaymentReceipt.Status.APPROVED
                ).exists()
                or TelegramOrder.objects.filter(user_id=sub.user_id, status=TelegramOrder.Status.PAID).exists()
            )
            admin_grant = sub.purchase_source == UserSubscription.Source.ADMIN
            if paid or admin_grant:
                continue
            since = sub.started_at or sub.created_at
            rows.append(
                {
                    "kind": "subscription",
                    "user_id": sub.user_id,
                    "plan": sub.plan.plan_type,
                    "status": sub.status,
                    "created_at": sub.created_at.isoformat(),
                    "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
                    "source": sub.purchase_source,
                    "grant_source": sub.grant_source,
                    "payment_method": sub.payment_method or "",
                    "payment_reference": sub.payment_reference or "",
                    "is_trial": sub.is_trial,
                    "essays_since": EssaySubmission.objects.filter(student_id=sub.user_id, created_at__gte=since).count(),
                    "speaking_since": SpeakingSubmission.objects.filter(user_id=sub.user_id, created_at__gte=since).count(),
                    "proposal": "revoke (no approved payment)",
                }
            )

        spons = TeacherSponsorship.objects.filter(is_active=True, approved_at__isnull=False)
        spons = spons.filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now)) if not opts["all"] else spons
        for sp in spons.order_by("approved_at"):
            rows.append(
                {
                    "kind": "sponsorship",
                    "user_id": sp.student_id,
                    "group_id": sp.group_id,
                    "approved_at": sp.approved_at.isoformat(),
                    "expires_at": sp.expires_at.isoformat() if sp.expires_at else None,
                    "note": (getattr(sp, "note", "") or "")[:80],
                    "proposal": "review: teacher-quota sponsorship or old auto group-join grant",
                }
            )

        if opts["json"]:
            self.stdout.write(json.dumps(rows, ensure_ascii=False, indent=2))
            return

        subs_rows = [r for r in rows if r["kind"] == "subscription"]
        self.stdout.write(f"Unpaid active paid-plan subscriptions: {len(subs_rows)}")
        by_source = Counter((r["source"], r["grant_source"] or "-") for r in subs_rows)
        for (src, gsrc), n in by_source.most_common():
            self.stdout.write(f"  {n:4d}  source={src} grant_source={gsrc}")
        by_day = Counter(r["created_at"][:10] for r in subs_rows)
        self.stdout.write("By creation day:")
        for day, n in sorted(by_day.items()):
            self.stdout.write(f"  {day}  {n}")
        for r in subs_rows:
            self.stdout.write(
                f"  user={r['user_id']} plan={r['plan']} created={r['created_at'][:16]} "
                f"expires={(r['expires_at'] or '-')[:16]} source={r['source']} grant={r['grant_source'] or '-'} "
                f"method={r['payment_method'] or '-'} trial={r['is_trial']} "
                f"essays={r['essays_since']} speaking={r['speaking_since']}"
            )
        sp_rows = [r for r in rows if r["kind"] == "sponsorship"]
        self.stdout.write(f"Active approved teacher sponsorships: {len(sp_rows)}")
        for r in sp_rows:
            self.stdout.write(f"  user={r['user_id']} group={r['group_id']} approved={r['approved_at'][:16]}")
        self.stdout.write("DRY RUN — nothing was changed.")
