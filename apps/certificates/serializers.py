"""
Certificates serializers — list and verify.
"""
from rest_framework import serializers

from apps.results.models import Certificate


class CertificateListSerializer(serializers.ModelSerializer):
    """Sertifikat list serializer — o'quvchi uchun."""

    course_title = serializers.CharField(source="course.title", read_only=True)
    test_title = serializers.CharField(source="test.title", read_only=True)
    percentage = serializers.CharField(source="result.percentage", read_only=True)

    class Meta:
        model = Certificate
        fields = [
            "id", "certificate_number", "course_title", "test_title",
            "percentage", "status", "issued_at",
        ]


class CertificateVerifySerializer(serializers.Serializer):
    """Sertifikat tekshirish uchun serializer."""

    certificate_number = serializers.CharField(max_length=30)
