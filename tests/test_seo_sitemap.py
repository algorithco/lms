"""
Unit tests for SEO Views (sitemap.xml and robots.txt).
"""

import pytest
from django.test import Client
from apps.courses.models import Course
from apps.tests.models import Test
from django.contrib.auth import get_user_model

User = get_user_model()


from django.test import TestCase


class TestSeoSitemap(TestCase):
    """Test dynamic sitemap.xml and robots.txt generation."""

    def test_robots_txt(self):
        client = Client()
        response = client.get("/robots.txt")
        assert response.status_code == 200
        assert "text/plain" in response["Content-Type"]
        content = response.content.decode("utf-8")
        assert "User-agent: *" in content
        assert "Disallow: /admin/" in content
        assert "Disallow: /api/" in content
        assert "Sitemap: https://grandec.uz/sitemap.xml" in content

    def test_sitemap_xml_static_routes(self):
        client = Client()
        response = client.get("/sitemap.xml")
        assert response.status_code == 200
        assert "application/xml" in response["Content-Type"]
        content = response.content.decode("utf-8")
        assert '<?xml version="1.0" encoding="UTF-8"?>' in content
        assert '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' in content
        assert "<loc>https://grandec.uz/</loc>" in content
        assert "<loc>https://grandec.uz/tests</loc>" in content
        assert "<loc>https://grandec.uz/pricing</loc>" in content
        assert "<loc>https://grandec.uz/arena</loc>" in content
        assert "<loc>https://grandec.uz/faq</loc>" in content

    def test_sitemap_xml_includes_published_tests(self):
        teacher = User.objects.create_user(
            email="teacher_seo@grandec.uz",
            password="testpass12345",
            first_name="Teacher",
            last_name="Seo",
            role="teacher",
        )
        course = Course.objects.create(
            title="Ona tili SEO kursi",
            teacher=teacher,
            subject="uzbek",
            description="Kurs tavsifi",
            status=Course.Status.PUBLISHED,
            price=0,
        )
        test_pub = Test.objects.create(
            title="Milliy sertifikat SEO test",
            course=course,
            status=Test.Status.PUBLISHED,
            is_active=True,
        )
        test_draft = Test.objects.create(
            title="Qoralama test",
            course=course,
            status=Test.Status.DRAFT,
            is_active=True,
        )

        client = Client()
        response = client.get("/sitemap.xml")
        assert response.status_code == 200
        content = response.content.decode("utf-8")

        # Published test must be present
        assert f"<loc>https://grandec.uz/tests/{test_pub.id}</loc>" in content
        # Draft test must not be present
        assert f"<loc>https://grandec.uz/tests/{test_draft.id}</loc>" not in content
