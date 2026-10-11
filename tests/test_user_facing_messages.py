"""User-facing message contract.

These two contracts are invisible to the API tests but are exactly what a user
sees when something goes wrong, and both have silently rotted before:

1. **Translation parity.** ``translate()`` in ``i18n/LangContext.tsx`` falls
   back to the Uzbek dictionary and then to the raw key, so a key that exists
   in only some languages ships as Uzbek text to Russian/English users, and a
   key missing everywhere ships as ``t('retry')``-style debris. A typo'd key in
   the dictionary (``pay_card_older`` for ``pay_card_holder``) is equally
   invisible and produces the same fallback.

2. **Explicit permission messages.** A DRF ``BasePermission`` without a
   ``message`` answers 403 with the generic "You do not have permission to
   perform this action.", which is precisely the string that made the
   /dashboard certificate bug hard to diagnose.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.permissions import BasePermission
from rest_framework.test import APIClient

from tests.conftest import LMSBaseTestCase

FRONTEND_SRC = Path(settings.BASE_DIR) / "frontend" / "src"
TRANSLATIONS = FRONTEND_SRC / "i18n" / "translations.json"

# `t('key')` / t("key") — only literal keys; dynamic ones such as
# t(`difficulty_${x}`) are resolved at runtime and cannot be checked here.
LITERAL_T = re.compile(r"\bt\(\s*['\"]([\w.]+)['\"]")

GENERIC_403 = "You do not have permission to perform this action."


def _used_keys() -> set[str]:
    used: set[str] = set()
    for path in FRONTEND_SRC.rglob("*"):
        if path.suffix in {".ts", ".tsx"}:
            used.update(LITERAL_T.findall(path.read_text(encoding="utf-8")))
    return used


def _levenshtein(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


class TranslationParityTests(LMSBaseTestCase):
    """The shipped dictionary must cover every key the client uses, in uz/ru/en."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not TRANSLATIONS.exists():
            raise unittest.SkipTest(
                "frontend sources are not part of this checkout",
            )
        cls.dicts = json.loads(TRANSLATIONS.read_text(encoding="utf-8"))
        cls.used = _used_keys()

    def test_every_language_has_the_same_keys(self):
        langs = sorted(self.dicts)
        self.assertEqual(langs, ["en", "ru", "uz"])
        first = set(self.dicts["uz"])
        for lang in langs[1:]:
            self.assertEqual(
                first, set(self.dicts[lang]),
                f"{lang} dictionary has drifted from uz",
            )

    def test_every_key_used_by_the_client_exists_in_every_language(self):
        for lang, dictionary in self.dicts.items():
            missing = sorted(k for k in self.used if k not in dictionary)
            self.assertEqual(
                missing, [],
                f"{lang} is missing keys the client asks for: {missing}",
            )

    def test_no_near_miss_key_typos(self):
        """A one/two-character key typo silently falls back to another language."""
        for lang, dictionary in self.dicts.items():
            for key in sorted(self.used):
                if key in dictionary:
                    continue
                twins = [
                    candidate for candidate in dictionary
                    if abs(len(candidate) - len(key)) <= 3
                    and _levenshtein(candidate, key) <= 2
                ]
                self.assertEqual(
                    twins, [],
                    f"{lang}: '{key}' is missing and looks like a typo of {twins}",
                )

    def test_no_translation_is_an_empty_string(self):
        for lang, dictionary in self.dicts.items():
            empty = sorted(k for k, v in dictionary.items() if not str(v).strip())
            self.assertEqual(empty, [], f"{lang} has empty translations: {empty}")


class PermissionMessageTests(LMSBaseTestCase):
    """Every DRF permission class must explain itself in the 403 body."""

    def test_all_permission_classes_declare_a_message(self):
        from apps.accounts import permissions as accounts_permissions
        from apps.tests import permissions as tests_permissions
        from apps.webapi import permissions as webapi_permissions

        found = 0
        for module in (accounts_permissions, tests_permissions, webapi_permissions):
            for name in dir(module):
                obj = getattr(module, name)
                if (
                    isinstance(obj, type)
                    and issubclass(obj, BasePermission)
                    and obj is not BasePermission
                ):
                    found += 1
                    message = getattr(obj, "message", None)
                    self.assertTrue(
                        message and str(message).strip(),
                        f"{module.__name__}.{name} has no explicit 403 message",
                    )
        self.assertGreaterEqual(found, 8)

    def test_student_only_endpoint_explains_itself_to_staff(self):
        """The /dashboard bug: staff got DRF's generic text with no hint why."""
        teacher = get_user_model().objects.create_user(
            email="msg-teacher@test.com", password="x", role="teacher",
        )
        client = APIClient()
        client.force_authenticate(user=teacher)
        response = client.get("/api/certificates/my-certificates/")
        self.assertEqual(response.status_code, 403)
        detail = str(response.json().get("detail", ""))
        self.assertNotEqual(detail, GENERIC_403)
        self.assertIn("Student", detail)
