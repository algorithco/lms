import io
import pytest
from decimal import Decimal
from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from apps.accounts.models import Profile
from apps.payments.models import (
    PaymentHistory,
    PaymentReceipt,
    SubscriptionPlan,
    UserSubscription,
)
from apps.payments.services import approve_payment_receipt, reject_payment_receipt

User = get_user_model()


def _create_test_image():
    file = io.BytesIO()
    image = Image.new("RGB", (100, 100), color="blue")
    image.save(file, "JPEG")
    file.seek(0)
    return SimpleUploadedFile("receipt.jpg", file.read(), content_type="image/jpeg")


@pytest.mark.django_db
def test_card_info_view():
    client = Client()
    url = reverse("webapi:payments-card-info")
    response = client.get(url)
    assert response.status_code == 200
    data = response.json()
    assert "card_number" in data
    assert "card_holder" in data
    assert "starter_price" in data
    assert "premium_price" in data
    assert data["starter_price"] == 49000
    assert data["premium_price"] == 99000


@pytest.mark.django_db
def test_receipt_upload_and_my_receipts():
    user = User.objects.create_user(
        email="student_receipt@grandec.uz",
        password="ValidPassword123!",
        first_name="Test",
        last_name="Student",
    )
    Profile.objects.get_or_create(user=user)

    client = Client()
    client.force_login(user)

    upload_url = reverse("webapi:payments-receipt-upload")
    test_img = _create_test_image()

    response = client.post(
        upload_url,
        {
            "plan": "starter",
            "amount": "49000",
            "receipt_image": test_img,
        },
        format="multipart",
    )
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["plan"] == "starter"
    assert res_data["status"] == "pending"
    assert res_data["source"] == "web"

    # Verify record in database
    receipt = PaymentReceipt.objects.get(id=res_data["id"])
    assert receipt.user == user
    assert receipt.plan == "starter"
    assert receipt.amount == Decimal("49000.00")
    assert receipt.status == PaymentReceipt.Status.PENDING

    # Test GET /api/v1/payments/my-receipts/
    my_url = reverse("webapi:payments-my-receipts")
    my_response = client.get(my_url)
    assert my_response.status_code == 200
    my_data = my_response.json()
    assert len(my_data["results"]) >= 1
    assert my_data["results"][0]["id"] == receipt.id


@pytest.mark.django_db
def test_approve_payment_receipt():
    user = User.objects.create_user(
        email="approve_user@grandec.uz",
        password="ValidPassword123!",
        first_name="Aziz",
        last_name="Karimov",
    )
    Profile.objects.get_or_create(user=user)

    admin_user = User.objects.create_superuser(
        email="superadmin@grandec.uz",
        password="ValidPassword123!",
        first_name="Admin",
        last_name="User",
    )

    test_img = _create_test_image()
    receipt = PaymentReceipt.objects.create(
        user=user,
        plan="premium",
        amount=Decimal("99000"),
        receipt_image=test_img,
        source=PaymentReceipt.Source.WEB,
        status=PaymentReceipt.Status.PENDING,
    )

    sub = approve_payment_receipt(receipt, admin_user=admin_user)

    receipt.refresh_from_db()
    assert receipt.status == PaymentReceipt.Status.APPROVED

    # Check UserSubscription
    assert sub.user == user
    assert sub.is_active is True
    assert sub.plan.plan_type == SubscriptionPlan.PlanType.PREMIUM
    assert sub.days_remaining > 0

    # Check User Profile plan
    user.profile.refresh_from_db()
    assert user.profile.plan == "premium"

    # Check PaymentHistory
    payment_record = PaymentHistory.objects.filter(user=user).first()
    assert payment_record is not None
    assert payment_record.status == PaymentHistory.PaymentStatus.COMPLETED
    assert payment_record.amount == Decimal("99000.00")


@pytest.mark.django_db
def test_reject_payment_receipt():
    user = User.objects.create_user(
        email="reject_user@grandec.uz",
        password="ValidPassword123!",
        first_name="Sardor",
        last_name="Aliyev",
    )
    Profile.objects.get_or_create(user=user)

    test_img = _create_test_image()
    receipt = PaymentReceipt.objects.create(
        user=user,
        plan="starter",
        amount=Decimal("49000"),
        receipt_image=test_img,
        source=PaymentReceipt.Source.WEB,
        status=PaymentReceipt.Status.PENDING,
    )

    reject_payment_receipt(receipt, note="To'lov kvitansiyasidagi summa noto'g'ri")

    receipt.refresh_from_db()
    assert receipt.status == PaymentReceipt.Status.REJECTED
    assert receipt.admin_note == "To'lov kvitansiyasidagi summa noto'g'ri"


@pytest.mark.django_db
def test_google_auth_routes():
    from unittest.mock import patch
    from django.contrib.auth import get_user_model
    from django.test import override_settings

    User = get_user_model()
    client = Client()

    # 1. Test GET auth-google-config
    config_url = reverse("webapi:auth-google-config")
    resp_cfg = client.get(config_url)
    assert resp_cfg.status_code == 200
    cfg_data = resp_cfg.json()
    assert "client_id" in cfg_data
    assert "enabled" in cfg_data

    # 2. Test GET redirect to google_auth_start
    url = reverse("webapi:auth-google")
    response = client.get(url)
    assert response.status_code in (200, 302)

    # 3. Test POST invalid body gives 400 with error
    response_post = client.post(url, data={"invalid": "token"}, content_type="application/json")
    assert response_post.status_code in (400, 503)

    # 4. Test POST valid mock credential auto-creates user and returns tokens
    mock_claims = {
        "sub": "mock-google-id-12345",
        "email": "auto-google-user@grandec.uz",
        "email_verified": True,
        "name": "Alisher Navoiy",
        "given_name": "Alisher",
        "family_name": "Navoiy",
    }
    with override_settings(GOOGLE_CLIENT_ID="mock-google-client-id"), patch(
        "apps.accounts.google_auth._verified_claims", return_value=mock_claims
    ):
        resp_verify = client.post(
            url,
            data={"credential": "mock-valid-id-token"},
            content_type="application/json",
        )
        assert resp_verify.status_code == 200
        data = resp_verify.json()
        assert data["status"] == "ok"
        assert "tokens" in data
        assert "access" in data["tokens"]
        assert "refresh" in data["tokens"]
        assert data["user"]["email"] == "auto-google-user@grandec.uz"

        # Check DB record
        created_user = User.objects.get(email="auto-google-user@grandec.uz")
        assert created_user.google_id == "mock-google-id-12345"
        assert created_user.first_name == "Alisher"
        assert created_user.last_name == "Navoiy"
        assert created_user.is_active is True
        assert hasattr(created_user, "profile")


@pytest.mark.django_db
def test_receipt_image_validation_and_duplicate_hash():
    from apps.payments.services import validate_and_hash_receipt_image

    # 1. Valid image returns sha256 hash and bytes
    valid_img = _create_test_image()
    valid_bytes = valid_img.read()
    image_hash, raw_bytes = validate_and_hash_receipt_image(valid_bytes)
    assert len(image_hash) == 64
    assert raw_bytes == valid_bytes

    # 2. Rejection for non-image / invalid magic bytes
    with pytest.raises(ValueError) as exc_info:
        validate_and_hash_receipt_image(b"fake plain text file content")
    assert "Faqat JPG, PNG yoki WEBP" in str(exc_info.value)

    # 3. Rejection for file > 5MB
    large_payload = b"\xff\xd8\xff" + b"0" * (5 * 1024 * 1024 + 10)
    with pytest.raises(ValueError) as exc_info_size:
        validate_and_hash_receipt_image(large_payload)
    assert "5MB" in str(exc_info_size.value)

    # 4. Save receipt with this hash in DB
    user = User.objects.create_user(email="hash_user@grandec.uz", password="ValidPassword123!")
    PaymentReceipt.objects.create(
        user=user,
        plan="starter",
        amount=Decimal("49000"),
        image_hash=image_hash,
        status=PaymentReceipt.Status.PENDING,
    )

    # 5. Duplicate hash must be rejected
    with pytest.raises(ValueError) as exc_dup:
        validate_and_hash_receipt_image(valid_bytes)
    assert "⚠️ Ushbu to'lov cheki avval tizimga yuklangan! Qayta ishlatish taqiqlanadi." in str(exc_dup.value)


@pytest.mark.django_db
def test_ai_daily_quota_and_rate_limiting():
    from apps.payments.ai_quota import check_and_consume_ai_quota, get_user_plan_tier
    from django.core.cache import cache
    cache.clear()

    # Free user: exactly 1 request per day
    free_user = User.objects.create_user(email="free_student@grandec.uz", password="ValidPassword123!")
    free_user.profile.plan = "free"
    free_user.profile.save()

    assert get_user_plan_tier(free_user) == "free"

    # 1st request succeeds
    allowed, msg = check_and_consume_ai_quota(free_user)
    assert allowed is True
    assert msg == ""

    # 2nd request rejected
    allowed2, msg2 = check_and_consume_ai_quota(free_user)
    assert allowed2 is False
    assert "Sizning bugungi bepul AI limitingiz tugadi. Cheksiz foydalanish uchun tarifingizni yangilang!" in msg2

    # Starter user: 20 requests per day
    starter_user = User.objects.create_user(email="starter_student@grandec.uz", password="ValidPassword123!")
    starter_user.profile.plan = "starter"
    starter_user.profile.save()
    assert get_user_plan_tier(starter_user) == "starter"

    for i in range(20):
        ok, _ = check_and_consume_ai_quota(starter_user)
        assert ok is True, f"Failed at iteration {i}"

    # 21st request rejected
    ok21, err21 = check_and_consume_ai_quota(starter_user)
    assert ok21 is False
    assert "Sizning bugungi Starter AI limitingiz tugadi" in err21

    # Premium user: unlimited requests
    prem_user = User.objects.create_user(email="prem_student@grandec.uz", password="ValidPassword123!")
    prem_user.profile.plan = "premium"
    prem_user.profile.save()
    assert get_user_plan_tier(prem_user) == "premium"

    for _ in range(30):
        ok_prem, _ = check_and_consume_ai_quota(prem_user)
        assert ok_prem is True

