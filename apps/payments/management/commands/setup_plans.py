"""
Management command: setup_plans

Creates the default subscription plans:
    Bepul (free)  — 0 so'm
    Starter       — 5 000 so'm/oy
    Pro           — 20 000 so'm/oy
    Premium       — 49 000 so'm/oy  [recommended]

Usage:
    python manage.py setup_plans
"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.payments.models import SubscriptionPlan


class Command(BaseCommand):
    help = "Default obuna rejalarni yaratish (Bepul / Starter / Pro / Premium)"

    def handle(self, *args, **options):
        plans = [
            {
                "name": "Bepul",
                "plan_type": "free",
                "description": "Boshlang'ich reja — asosiy imkoniyatlar",
                "price_monthly": Decimal("0"),
                "price_yearly": Decimal("0"),
                "max_tests_per_day": 5,
                "max_essays_per_week": 2,
                "max_ai_grading": True,
                "detailed_analytics": False,
                "pdf_certificate": False,
                "priority_support": False,
                "unlimited_tests": False,
                "unlimited_essays": False,
                "sort_order": 1,
            },
            {
                "name": "Starter",
                "plan_type": "starter",
                "description": "Boshlovchilar uchun — kunlik esse va haftalik testlar",
                "price_monthly": Decimal("5000"),
                "price_yearly": Decimal("50000"),
                "max_tests_per_day": 3,
                "max_essays_per_week": 7,  # kuniga 1 ta ≈ haftasiga 7
                "max_ai_grading": True,
                "detailed_analytics": False,
                "pdf_certificate": False,
                "priority_support": False,
                "unlimited_tests": False,
                "unlimited_essays": False,
                "sort_order": 2,
            },
            {
                "name": "Pro",
                "plan_type": "pro",
                "description": "Faol o'quvchilar uchun — cheklovli test va cheksiz esse",
                "price_monthly": Decimal("20000"),
                "price_yearly": Decimal("200000"),
                "max_tests_per_day": 10,
                "max_essays_per_week": 0,  # unlimited essays
                "max_ai_grading": True,
                "detailed_analytics": True,
                "pdf_certificate": False,
                "priority_support": False,
                "unlimited_tests": False,
                "unlimited_essays": True,
                "sort_order": 3,
            },
            {
                "name": "Premium",
                "plan_type": "premium",
                "description": "To'liq imkoniyatlar — cheksiz test va esse, PDF sertifikat",
                "price_monthly": Decimal("49000"),
                "price_yearly": Decimal("490000"),
                "max_tests_per_day": 0,  # unlimited
                "max_essays_per_week": 0,  # unlimited
                "max_ai_grading": True,
                "detailed_analytics": True,
                "pdf_certificate": True,
                "priority_support": True,
                "unlimited_tests": True,
                "unlimited_essays": True,
                "sort_order": 4,
            },
        ]

        for plan_data in plans:
            plan, created = SubscriptionPlan.objects.update_or_create(
                plan_type=plan_data["plan_type"],
                defaults=plan_data,
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Yaratildi: {plan.name}"))
            else:
                self.stdout.write(self.style.WARNING(f"Yangilandi: {plan.name}"))

        # Retire the old Family plan (no longer part of the tariff lineup)
        SubscriptionPlan.objects.filter(plan_type="family", is_active=True).update(
            is_active=False
        )

        self.stdout.write(self.style.SUCCESS("Barcha rejalar tayyor!"))
