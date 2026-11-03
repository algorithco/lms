"""Feedback: validation, rate limit, privacy, consent-gated public list, admin inbox, XSS, Celery hand-off."""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import Profile
from apps.notifications.models import UserFeedback

User = get_user_model()
URL = "/api/v1/feedback/"


@pytest.fixture(autouse=True)
def _fresh_throttle_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def _no_broker():
    with patch("apps.notifications.tasks.notify_admin_new_feedback.delay") as notify, patch(
        "apps.notifications.tasks.send_feedback_reply.delay"
    ) as reply:
        yield notify, reply


def make_user(email, role="student", **extra):
    u = User.objects.create_user(email=email, password="x-Pass-123!", role=role, first_name="Komiljon", last_name="Roziyev", **extra)
    Profile.objects.get_or_create(user=u)
    return u


def client(user=None):
    c = APIClient()
    if user:
        c.force_authenticate(user)
    return c


def payload(**over):
    return {"rating": 5, "category": "praise", "message": "Juda yaxshi platforma", **over}


@pytest.mark.django_db
def test_guest_and_user_can_submit_and_context_is_sanitised(_no_broker, django_capture_on_commit_callbacks):
    user = make_user("fb1@example.test")
    with django_capture_on_commit_callbacks(execute=True):
        res = client(user).post(
            URL,
            payload(
                category="bug",
                context={
                    "path": "/tests/14",
                    "subject": "uzbek",
                    "role": "admin",  # client claim must be ignored
                    "plan": "premium",
                    "last_error": "Failed with Bearer abc.def.ghi and password=hunter2",
                    "evil_key": "x",
                },
            ),
            format="json",
        )
    assert res.status_code == 201
    fb = UserFeedback.objects.get(pk=res.json()["id"])
    assert fb.context["role"] == "student" and fb.context["plan"] == "free"  # server truth
    assert "evil_key" not in fb.context
    assert "hunter2" not in fb.context["last_error"] and "abc.def.ghi" not in fb.context["last_error"]
    _no_broker[0].assert_called_once_with(fb.pk)  # admin alert goes through Celery

    guest = client().post(URL, payload(name="Mehmon Mehmonov"), format="json")
    assert guest.status_code == 201
    assert UserFeedback.objects.get(pk=guest.json()["id"]).user_id is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "body",
    [
        {"message": "ok", "rating": 5},  # too short
        {"message": "x" * 2001, "rating": 5},  # too long
        {"message": "valid text", "rating": 0},
        {"message": "valid text", "rating": 6},
        {"message": "valid text"},  # rating is required, not silently 5
        {"message": "valid text", "rating": 4, "category": "hack"},
    ],
)
def test_validation(body):
    assert client().post(URL, body, format="json").status_code == 400
    assert UserFeedback.objects.count() == 0


@pytest.mark.django_db
def test_rate_limit_five_per_hour():
    c = client(make_user("fb2@example.test"))
    codes = [c.post(URL, payload(message=f"Fikr raqami {i} yaxshi"), format="json").status_code for i in range(7)]
    assert codes[:5] == [201] * 5 and codes[5:] == [429, 429]


@pytest.mark.django_db
def test_double_click_and_honeypot():
    c = client(make_user("fb3@example.test"))
    first = c.post(URL, payload(), format="json")
    again = c.post(URL, payload(), format="json")
    assert first.status_code == 201 and again.status_code == 200 and again.json()["duplicate"] is True
    assert UserFeedback.objects.count() == 1
    bot = client().post(URL, payload(message="spam spam spam", website="http://spam.example"), format="json")
    assert bot.status_code == 201 and UserFeedback.objects.count() == 1  # pretended, not stored


@pytest.mark.django_db
def test_html_is_stripped_before_storage():
    res = client().post(URL, payload(message='Salom <script>alert(1)</script><b>dunyo</b>', name="<img src=x onerror=1>Ali"), format="json")
    fb = UserFeedback.objects.get(pk=res.json()["id"])
    assert "<" not in fb.message and "<" not in fb.user_name
    assert "dunyo" in fb.message


@pytest.mark.django_db
def test_public_list_needs_admin_approval_and_consent_and_shows_short_name():
    u = make_user("fb4@example.test")
    approved_consent = UserFeedback.objects.create(user=u, rating=5, message="Yaxshi", is_published=True, consent_public=True)
    UserFeedback.objects.create(user=u, rating=5, message="Rozi emas", is_published=True, consent_public=False)
    UserFeedback.objects.create(user=u, rating=5, message="Kutilmoqda", is_published=False, consent_public=True)
    data = client().get("/api/v1/feedback/public/").json()
    assert [r["id"] for r in data["results"]] == [approved_consent.pk]
    assert data["results"][0]["name"] == "Komiljon R."  # never the full name
    assert "phone" not in str(data) and "@" not in str(data)


@pytest.mark.django_db
def test_my_feedback_is_private():
    a, b = make_user("fb5@example.test"), make_user("fb6@example.test")
    UserFeedback.objects.create(user=a, rating=4, message="A ning fikri")
    UserFeedback.objects.create(user=b, rating=2, message="B ning fikri")
    mine = client(a).get("/api/v1/feedback/mine/").json()["results"]
    assert [m["message"] for m in mine] == ["A ning fikri"]
    assert client().get("/api/v1/feedback/mine/").status_code in (401, 403)


@pytest.mark.django_db
def test_admin_inbox_permissions_filters_reply_and_publish(_no_broker, django_capture_on_commit_callbacks):
    admin = User.objects.create_superuser(email="fb_admin@example.test", password="x-Pass-123!")
    student = make_user("fb7@example.test")
    bug = UserFeedback.objects.create(user=student, rating=1, category="bug", message="Tugma ishlamayapti", context={"path": "/tests"})
    UserFeedback.objects.create(user=student, rating=5, category="praise", message="Zo'r", consent_public=True)

    assert client(student).get("/api/v1/panel/feedback/").status_code == 403
    assert client().get("/api/v1/panel/feedback/").status_code in (401, 403)

    c = client(admin)
    listing = c.get("/api/v1/panel/feedback/", {"category": "bug"}).json()
    assert [r["id"] for r in listing["results"]] == [bug.pk]
    assert listing["results"][0]["context"]["path"] == "/tests"
    assert c.get("/api/v1/panel/feedback/", {"q": "Zo'r"}).json()["count"] == 1
    assert c.get("/api/v1/panel/feedback/").json()["stats"]["total"] == 2

    # publishing without the author's consent is refused
    assert c.patch(f"/api/v1/panel/feedback/{bug.pk}/", {"is_published": True}, format="json").status_code == 400

    with django_capture_on_commit_callbacks(execute=True):
        done = c.patch(
            f"/api/v1/panel/feedback/{bug.pk}/", {"status": "resolved", "admin_reply": "Tuzatildi, rahmat"}, format="json"
        ).json()
    assert done["status"] == "resolved" and done["admin_reply"] == "Tuzatildi, rahmat"
    _no_broker[1].assert_called_once_with(bug.pk)  # reply is delivered by Celery
    mine = {m["id"]: m for m in client(student).get("/api/v1/feedback/mine/").json()["results"]}
    assert mine[bug.pk]["admin_reply"] == "Tuzatildi, rahmat" and mine[bug.pk]["status"] == "resolved"

    praise = UserFeedback.objects.get(category="praise")
    assert c.patch(f"/api/v1/panel/feedback/{praise.pk}/", {"is_published": True}, format="json").status_code == 200
    assert client().get("/api/v1/feedback/public/").json()["count"] == 1


@pytest.mark.django_db
def test_admin_alert_text_is_escaped_and_has_no_contact_data():
    from apps.notifications.tasks import notify_admin_new_feedback

    fb = UserFeedback.objects.create(
        user_name="<b>Eve</b>", rating=1, category="bug", message="<i>boom</i> & more", context={"role": "guest"}
    )
    with patch("apps.notifications.services.telegram_service.TelegramService.send_message_with_keyboard") as send, patch(
        "django.conf.settings.ADMIN_TELEGRAM_ID", 123, create=True
    ):
        notify_admin_new_feedback.run(fb.pk)
    text = send.call_args.kwargs["text"]
    assert "<i>boom</i>" not in text and "&lt;i&gt;boom&lt;/i&gt;" in text
    assert "telefon" not in text.lower() and "@" not in text
