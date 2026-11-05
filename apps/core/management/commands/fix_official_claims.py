"""Find (and, once approved, soften) wording that promises more than the platform is.

    python manage.py fix_official_claims                 # dry run (default): list matches and the proposed text
    python manage.py fix_official_claims --apply         # write the proposed text

Looks at the text fields of tests, essay topics, plans and subjects for
"rasmiy", "official", "British Council", "Cambridge", "kafolat" / "guarantee".
Grandec is not an official exam body, so claims of official status or of a
guaranteed result must not be shown to students.

* "rasmiy " and "official " (a plain adjective) are removed from the sentence.
* "British Council" / "Cambridge" are only reported: the name may be a real
  reference to a published practice material, so a person decides.
* "kafolat" / "guarantee" are only reported: the sentence has to be rewritten.

Nothing is written without ``--apply``; the output lists model, id and field only
plus the proposed replacement for the automatic cases. Safe to run twice.
"""

from __future__ import annotations

import re
from typing import Any

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import transaction

#: (app, model) -> text fields scanned
TARGETS: dict[tuple[str, str], tuple[str, ...]] = {
    ("tests", "Test"): ("title", "description"),
    ("essays", "EssayTopic"): ("title", "description"),
    ("payments", "SubscriptionPlan"): ("name", "description"),
    ("courses", "Subject"): ("name", "description"),
}

AUTO = re.compile(r"\b(rasmiy|official)\s+", re.I)
REPORT_ONLY = re.compile(r"british council|cambridge|kafolat\w*|guarantee\w*", re.I)


def _soften(text: str) -> str:
    out = AUTO.sub("", text)
    return out[:1].upper() + out[1:] if out and text[:1].isupper() else out


class Command(BaseCommand):
    help = "Report and (with --apply) soften 'official' / 'guarantee' wording in stored texts."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write the automatic replacements (default: dry run).")

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        apply = options["apply"]
        changed = manual = 0
        for (app, name), fields in TARGETS.items():
            try:
                model = apps.get_model(app, name)
            except LookupError:
                continue
            for obj in model.objects.all().iterator():
                updates: dict[str, str] = {}
                for field in fields:
                    value = getattr(obj, field, None)
                    if not isinstance(value, str) or not value:
                        continue
                    if AUTO.search(value):
                        new = _soften(value)
                        updates[field] = new
                        self.stdout.write(f"{app}.{name} id={obj.pk} field={field}: remove 'rasmiy/official'")
                        self.stdout.write(f"    before: {value[:200]!r}")
                        self.stdout.write(f"    after : {new[:200]!r}")
                    if REPORT_ONLY.search(value):
                        manual += 1
                        self.stdout.write(f"{app}.{name} id={obj.pk} field={field}: needs a person (name or guarantee wording)")
                if updates:
                    changed += 1
                    if apply:
                        for field, new in updates.items():
                            setattr(obj, field, new)
                        obj.save(update_fields=list(updates))
        suffix = "" if apply else " (dry run, nothing written; pass --apply)"
        self.stdout.write(f"Automatic fixes: {changed} rows. Left for a person: {manual} fields.{suffix}")
