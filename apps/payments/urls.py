"""Payments app URL configuration."""
from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    # Plans
    path("", views.subscription_plans_view, name="plans"),
    path("<int:plan_id>/subscribe/", views.subscribe_view, name="subscribe"),
    path("my/", views.my_subscription_view, name="my-subscription"),
    path("cancel/", views.cancel_subscription_view, name="cancel"),

    # Payment callbacks
    path("success/", views.payment_success_view, name="success"),
    path("cancel/", views.payment_cancel_view, name="payment-cancel"),

    # API
    path("api/status/", views.subscription_api_view, name="api-status"),
]
