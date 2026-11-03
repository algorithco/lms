"""seed_accounts: no fixed passwords, local-only, never resets an existing password silently."""

from io import StringIO
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

User = get_user_model()
SOURCE = Path(__file__).resolve().parent.parent / "apps/accounts/management/commands/seed_accounts.py"


def run(**kwargs):
    out = StringIO()
    call_command("seed_accounts", stdout=out, **kwargs)
    return out.getvalue()


def test_no_password_is_written_in_the_source():
    text = SOURCE.read_text(encoding="utf-8")
    assert "GrandAdmin2026" not in text and "GrandUstoz2026" not in text


@pytest.mark.django_db
def test_generated_passwords_are_random_and_shown_once(monkeypatch):
    monkeypatch.delenv("SEED_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("SEED_TEACHER_PASSWORD", raising=False)
    first = run()
    assert "Admin password (shown once" in first and "Teacher password (shown once" in first
    admin = User.objects.get(email="admin.grandec@gmail.com")
    old_hash = admin.password
    # A second run keeps the password and prints none.
    second = run()
    assert "password left unchanged" in second and "shown once" not in second
    admin.refresh_from_db()
    assert admin.password == old_hash
    # Explicit reset generates a new one.
    third = run(reset_passwords=True)
    assert "Admin password (shown once" in third
    admin.refresh_from_db()
    assert admin.password != old_hash


@pytest.mark.django_db
def test_password_from_environment_is_used_and_not_echoed(monkeypatch):
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "from-env-Pass-987!")
    monkeypatch.setenv("SEED_TEACHER_PASSWORD", "teacher-env-Pass-987!")
    out = run()
    assert "from-env-Pass-987!" not in out and "teacher-env-Pass-987!" not in out
    assert User.objects.get(email="admin.grandec@gmail.com").check_password("from-env-Pass-987!")


@pytest.mark.django_db
def test_refuses_on_a_non_local_database(monkeypatch, settings):
    monkeypatch.setitem(settings.DATABASES["default"], "ENGINE", "django.db.backends.postgresql")
    monkeypatch.setattr(settings, "DEBUG", False)
    with pytest.raises(CommandError):
        run()
    assert not User.objects.filter(email="admin.grandec@gmail.com").exists()
