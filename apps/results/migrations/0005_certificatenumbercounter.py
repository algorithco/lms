import re

from django.db import migrations, models


def seed_certificate_counters(apps, schema_editor):
    Certificate = apps.get_model("results", "Certificate")
    Counter = apps.get_model("results", "CertificateNumberCounter")
    maxima = {}
    for number in Certificate.objects.values_list("certificate_number", flat=True).iterator():
        match = re.fullmatch(r"LMS-(\d{4})-(\d+)", number or "")
        if match:
            year, suffix = int(match.group(1)), int(match.group(2))
            maxima[year] = max(maxima.get(year, 0), suffix)
    Counter.objects.bulk_create([
        Counter(year=year, last_value=value) for year, value in maxima.items()
    ])


class Migration(migrations.Migration):
    dependencies = [("results", "0004_certificate_sequence_and_checksums")]
    operations = [
        migrations.CreateModel(
            name="CertificateNumberCounter",
            fields=[
                ("year", models.PositiveSmallIntegerField(primary_key=True, serialize=False)),
                ("last_value", models.PositiveBigIntegerField(default=0)),
            ],
        ),
        migrations.RunPython(seed_certificate_counters, migrations.RunPython.noop),
    ]
