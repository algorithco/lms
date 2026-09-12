"""Core app URL configuration."""
from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.healthz_view, name="healthz"),
]