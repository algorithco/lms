import hashlib
import hmac
import re
from decimal import Decimal

from django.conf import settings
from django.db import migrations


def prepare_certificates(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        with schema_editor.connection.cursor() as cursor:
            cursor.execute("CREATE SEQUENCE IF NOT EXISTS cert_number_seq START 1")

    Certificate = apps.get_model("results", "Certificate")
    if schema_editor.connection.vendor == "postgresql":
        highest = 0
        for number in Certificate.objects.values_list("certificate_number", flat=True).iterator():
            match = re.fullmatch(r"LMS-\d{4}-(\d+)", number or "")
            if match:
                highest = max(highest, int(match.group(1)))
        if highest:
            with schema_editor.connection.cursor() as cursor:
                cursor.execute("SELECT setval('cert_number_seq', %s, true)", [highest])
    for certificate in Certificate.objects.select_related("result").iterator():
        percentage = (
            format(Decimal(str(certificate.result.percentage)).normalize(), "f")
            if certificate.result_id else "0"
        )
        issued = certificate.issued_at.strftime("%Y-%m-%d") if certificate.issued_at else ""
        canonical = "|".join([
            str(certificate.certificate_number or ""),
            str(certificate.student_id),
            str(certificate.course_id),
            str(certificate.test_id),
            str(certificate.result_id),
            str(percentage),
            issued,
            "LMS-PLATFORM-V2",
        ])
        key = getattr(settings, "CERTIFICATE_SECRET_KEY", "") or hashlib.sha256(
            f"lms-cert-{settings.SECRET_KEY}".encode()
        ).hexdigest()
        certificate.fraud_checksum = hmac.new(
            key.encode(), canonical.encode(), hashlib.sha256
        ).hexdigest()
        certificate.save(update_fields=["fraud_checksum"])


def drop_sequence(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        with schema_editor.connection.cursor() as cursor:
            cursor.execute("DROP SEQUENCE IF EXISTS cert_number_seq")


class Migration(migrations.Migration):
    dependencies = [("results", "0003_certificate_fraud_checksum")]
    operations = [
        migrations.RunPython(prepare_certificates, drop_sequence),
    ]
