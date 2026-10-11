"""Seed the Grandec commercial plan catalogue (additive, idempotent).

Creates the START / PRO / TEACHER_SPONSORED rows, plus a FREE row that
represents the platform's default access policy. Existing rows are never
overwritten: only a plan that is *absent* is created, so an administrator's
live configuration (prices, quotas, descriptions) survives this migration.

Prices are the business reference prices in UZS. Telegram Stars prices are
deliberately left NULL — an administrator must fill in the actual amount
charged in Stars; nothing here invents a UZS→Stars conversion.
"""

from django.db import migrations

#: (plan_type, name, description, price_uzs_monthly, fields...)
START_PLAN = {
    "plan_type": "start",
    "name": "START",
    "description": (
        "Haftalik 5 ta rasmli va 3 ta matnli esse baholash, matnli esselar "
        "orasida kamida 5 soat. Standart mashq imkoniyatlari."
    ),
    "price_monthly": 15000,
    "price_yearly": 0,
    "max_tests_per_day": 5,
    "max_essays_per_week": 8,
    "image_essay_weekly_limit": 5,
    "text_essay_weekly_limit": 3,
    "text_essay_cooldown_hours": 5,
    # Test quota is intentionally NOT set: the commercial spec says it is
    # administrator-configurable and must not be invented here.
    "test_limit": None,
    "is_unlimited_image_essays": False,
    "is_unlimited_text_essays": False,
    "is_unlimited_tests": False,
    "unlimited_essays": False,
    "unlimited_tests": False,
    "max_ai_grading": True,
    "duration_days": 30,
    "quota_period_days": 7,
    "telegram_stars_price": None,
    "is_public": True,
    "is_active": True,
    "sort_order": 10,
}

PRO_PLAN = {
    "plan_type": "pro",
    "name": "PRO",
    "description": (
        "Cheklanmagan rasmli va matnli esse baholash, cheklanmagan mashq "
        "testlari, sovutish (cooldown) yo'q, to'liq AI feedback."
    ),
    "price_monthly": 60000,
    "price_yearly": 0,
    "max_tests_per_day": 0,
    "max_essays_per_week": 0,
    "image_essay_weekly_limit": None,
    "text_essay_weekly_limit": None,
    "text_essay_cooldown_hours": 0,
    "test_limit": None,
    "is_unlimited_image_essays": True,
    "is_unlimited_text_essays": True,
    "is_unlimited_tests": True,
    "unlimited_essays": True,
    "unlimited_tests": True,
    "max_ai_grading": True,
    "detailed_analytics": True,
    "duration_days": 30,
    "quota_period_days": 7,
    "telegram_stars_price": None,
    "is_public": True,
    "is_active": True,
    "sort_order": 20,
}

SPONSORED_PLAN = {
    "plan_type": "teacher_sponsored",
    "name": "Ustoz guruhi (homiylik)",
    "description": (
        "Administrator tasdiqlagan ustoz guruhi o'quvchilari uchun bepul "
        "kirish. Sotilmaydi."
    ),
    "price_monthly": 0,
    "price_yearly": 0,
    "max_tests_per_day": 5,
    "max_essays_per_week": 8,
    "image_essay_weekly_limit": 5,
    "text_essay_weekly_limit": 3,
    "text_essay_cooldown_hours": 5,
    "test_limit": None,
    "is_unlimited_image_essays": False,
    "is_unlimited_text_essays": False,
    "is_unlimited_tests": False,
    "unlimited_essays": False,
    "unlimited_tests": False,
    "max_ai_grading": True,
    "duration_days": 30,
    "quota_period_days": 7,
    "telegram_stars_price": None,
    "is_public": False,  # never shown in the public store
    "is_active": True,
    "sort_order": 90,
}

#: Default access policy for a student with no subscription, sponsorship or
#: override. Every quota field stays NULL (= no enforced quota) so that
#: introducing the commercial plans does not silently restrict accounts that
#: already exist. Admins can tighten this by editing the FREE row.
FREE_PLAN = {
    "plan_type": "free",
    "name": "Bepul",
    "description": "Standart kirish siyosati (administrator sozlaydi).",
    "price_monthly": 0,
    "price_yearly": 0,
    "image_essay_weekly_limit": None,
    "text_essay_weekly_limit": None,
    "text_essay_cooldown_hours": None,
    "test_limit": None,
    "is_unlimited_image_essays": False,
    "is_unlimited_text_essays": False,
    "is_unlimited_tests": False,
    "duration_days": 30,
    "quota_period_days": 7,
    "telegram_stars_price": None,
    "is_public": False,
    "is_active": True,
    "sort_order": 0,
}

PLANS = (FREE_PLAN, START_PLAN, PRO_PLAN, SPONSORED_PLAN)


def seed_plans(apps, schema_editor):
    SubscriptionPlan = apps.get_model("payments", "SubscriptionPlan")
    for spec in PLANS:
        plan_type = spec["plan_type"]
        if SubscriptionPlan.objects.filter(plan_type=plan_type).exists():
            # Never overwrite live configuration.
            continue
        SubscriptionPlan.objects.create(**spec)


def unseed_plans(apps, schema_editor):
    """Reverse only removes rows this migration could have created.

    The plan catalogue is referenced by subscriptions/orders (PROTECT), so a
    reverse is a no-op when anything still points at these rows.
    """
    SubscriptionPlan = apps.get_model("payments", "SubscriptionPlan")
    codes = [spec["plan_type"] for spec in PLANS]
    SubscriptionPlan.objects.filter(plan_type__in=codes).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0007_subscriptionplan_duration_days_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_plans, unseed_plans),
    ]
