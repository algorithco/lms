from django.db import migrations
from decimal import Decimal


def update_plan_prices(apps, schema_editor):
    SubscriptionPlan = apps.get_model("payments", "SubscriptionPlan")

    # 1. Starter / Start plan
    SubscriptionPlan.objects.filter(plan_type__in=["starter", "start"]).update(
        price_monthly=Decimal("7000"),
        telegram_stars_price=30,
        test_limit=5,
        text_essay_weekly_limit=3,
        image_essay_weekly_limit=0,
        is_unlimited_tests=False,
        is_unlimited_text_essays=False,
        is_unlimited_image_essays=False,
        description="5 ta to'liq test, haftasiga 3 ta esse tekshirish matnli, xatolar va zaif mavzular tahlili",
    )

    # 2. Pro plan
    SubscriptionPlan.objects.filter(plan_type__iexact="pro").update(
        price_monthly=Decimal("15000"),
        telegram_stars_price=60,
        test_limit=30,
        text_essay_weekly_limit=15,
        image_essay_weekly_limit=15,
        is_unlimited_tests=False,
        is_unlimited_text_essays=False,
        is_unlimited_image_essays=False,
        description="Haftasiga 15 ta esse rasmli/matnli, kunlik rasmiy Mock testlar, CBT testlar va AI repetitor",
    )

    # 3. Premium plan
    SubscriptionPlan.objects.filter(plan_type__iexact="premium").update(
        price_monthly=Decimal("27000"),
        telegram_stars_price=100,
        test_limit=None,
        text_essay_weekly_limit=None,
        image_essay_weekly_limit=None,
        is_unlimited_tests=True,
        is_unlimited_text_essays=True,
        is_unlimited_image_essays=True,
        detailed_analytics=True,
        pdf_certificate=True,
        description="Cheksiz esse 12 mezon, cheksiz Mock testlar va 1v1 Arena, ustoz tekshiruvi va rasmiy PDF sertifikat",
    )


def revert_plan_prices(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0013_enforce_free_plan_limits"),
    ]

    operations = [
        migrations.RunPython(update_plan_prices, revert_plan_prices),
    ]
