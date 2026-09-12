"""Opt-in PostgreSQL integration settings. Never targets a production database.

Set POSTGRES_TEST_ENABLE=1 and the POSTGRES_TEST_* connection variables.
Django's test runner creates and drops a separate test_<name> database.
"""
import os

from .test import *  # noqa: F401,F403

if os.environ.get("POSTGRES_TEST_ENABLE") != "1":
    raise RuntimeError("Set POSTGRES_TEST_ENABLE=1 to opt in to PostgreSQL tests.")

database_name = os.environ.get("POSTGRES_TEST_NAME", "")
if not database_name.startswith("lms_pg_"):
    raise RuntimeError("POSTGRES_TEST_NAME must start with lms_pg_.")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": database_name,
        "USER": os.environ.get("POSTGRES_TEST_USER", ""),
        "PASSWORD": os.environ.get("POSTGRES_TEST_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_TEST_HOST", "127.0.0.1"),
        "PORT": os.environ.get("POSTGRES_TEST_PORT", "5432"),
        "OPTIONS": {"connect_timeout": 10},
        "TEST": {"NAME": f"test_{database_name}"},
    }
}
