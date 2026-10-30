from django.db import migrations


def enforce_free_limits(apps, schema_editor):
    SubscriptionPlan = apps.get_model("payments", "SubscriptionPlan")
    free_plan = SubscriptionPlan.objects.filter(plan_type="free").first()
    if free_plan:
        free_plan.text_essay_weekly_limit = 1
        free_plan.image_essay_weekly_limit = 0
        free_plan.test_limit = 1
        free_plan.is_unlimited_text_essays = False
        free_plan.is_unlimited_image_essays = False
        free_plan.is_unlimited_tests = False
        free_plan.save()


def reverse_free_limits(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0012_fix_pro_plan_price"),
    ]

    operations = [
        migrations.RunPython(enforce_free_limits, reverse_free_limits),
    ]
