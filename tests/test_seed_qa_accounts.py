import json
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.payments.models import EntitlementAuditLog, UserSubscription
from apps.payments.ai_quota import get_user_plan_tier

User = get_user_model()


@pytest.mark.django_db
def test_seed_qa_accounts_local_only_and_audited(tmp_path):
    out = tmp_path / "creds.json"
    stdout = StringIO()
    call_command("seed_qa_accounts", "--out", str(out), "--tokens", stdout=stdout)
    creds = json.loads(out.read_text(encoding="utf-8"))
    assert set(creds) == {"admin", "teacher", "free", "paid"}
    # passwords/tokens go to the file, never to stdout
    for c in creds.values():
        assert c["password"] not in stdout.getvalue() and c["access"] not in stdout.getvalue()
    free, paid = User.objects.get(pk=creds["free"]["id"]), User.objects.get(pk=creds["paid"]["id"])
    assert get_user_plan_tier(free) == "free" and not UserSubscription.objects.filter(user=free).exists()
    assert get_user_plan_tier(paid) == "pro"
    log = EntitlementAuditLog.objects.get(student=paid)
    assert log.details["kind"] == "admin" and log.actor_id == creds["admin"]["id"]
    # idempotent: second run keeps one subscription and one audit row
    call_command("seed_qa_accounts", "--out", str(out), stdout=StringIO())
    assert EntitlementAuditLog.objects.filter(student=paid).count() == 1


@pytest.mark.django_db
def test_seed_qa_accounts_refuses_non_local_database(tmp_path, monkeypatch):
    # Patch the guard itself: mutating settings.DATABASES in place would leak into later tests.
    monkeypatch.setattr("apps.accounts.management.commands.seed_qa_accounts._is_local_dev", lambda: False)
    with pytest.raises(CommandError):
        call_command("seed_qa_accounts", "--out", str(tmp_path / "x.json"), stdout=StringIO())
