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
    client = Client()
    # Test GET redirect to google_auth_start
    url = reverse("webapi:auth-google")
    response = client.get(url)
    # If Google OAuth isn't fully configured with real secrets in test env, it gracefully redirects or returns
    assert response.status_code in (200, 302)

    # Test POST invalid body gives 400 with Uzbek error
    response_post = client.post(url, data={"invalid": "token"}, content_type="application/json")
    assert response_post.status_code in (400, 503)
