import pytest
from django.test import Client, override_settings


@pytest.mark.django_db
def test_google_auth_start_unconfigured_redirects_cleanly():
    """When Google OAuth is unconfigured, GET /api/auth/google/ must redirect cleanly to /login."""
    with override_settings(GOOGLE_CLIENT_ID="", GOOGLE_CLIENT_SECRET=""):
        client = Client()
        response = client.get("/api/auth/google/")
        assert response.status_code == 302
        assert response.url == "/login"


@pytest.mark.django_db
def test_google_auth_v1_start_unconfigured_redirects_cleanly():
    """When Google OAuth is unconfigured, GET /api/v1/auth/google/ must redirect cleanly to /login."""
    with override_settings(GOOGLE_CLIENT_ID="", GOOGLE_CLIENT_SECRET=""):
        client = Client()
        response = client.get("/api/v1/auth/google/")
        assert response.status_code == 302
        assert response.url == "/login"
