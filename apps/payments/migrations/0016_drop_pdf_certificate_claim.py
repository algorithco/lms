"""Stop advertising "rasmiy PDF sertifikat" as a paid plan feature.

The ``pdf_certificate`` flag is not enforced anywhere: platform certificates
for passed non-Milliy tests are available on every plan, and Milliy
certificates are not issued while the scoring rules are unverified. The flag
is cleared and the PREMIUM description is rewritten only if it still equals
the text set by migration 0014. No user data is touched.
"""

from django.db import migrations

OLD_PREMIUM_DESCRIPTION = (
    "Cheksiz esse 12 mezon, cheksiz Mock testlar va 1v1 Arena, ustoz tekshiruvi va rasmiy PDF sertifikat"
)
NEW_PREMIUM_DESCRIPTION = "Cheksiz esse 12 mezon, cheksiz Mock testlar va 1v1 Arena, ustoz tekshiruvi"


def forwards(apps, schema_editor):
    SubscriptionPlan = apps.get_model("payments", "SubscriptionPlan")
    SubscriptionPlan.objects.filter(pdf_certificate=True).update(pdf_certificate=False)
    SubscriptionPlan.objects.filter(description=OLD_PREMIUM_DESCRIPTION).update(
        description=NEW_PREMIUM_DESCRIPTION
    )


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0015_paymentreceipt_reviewed_at_and_more"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
