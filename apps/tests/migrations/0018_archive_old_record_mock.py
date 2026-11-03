"""Archive the superseded Record Mock (CEFR-RECORD-1, #12) and drop
unfounded "official British Council" claims from its texts.

- Test: status=archived, is_active=False → hidden from students and not
  startable; admins still see it. Attempts and results are untouched.
- Texts are replaced only when they still equal the old seed strings,
  so anything edited by hand is left alone.
"""

from django.db import migrations

MOCK_CODE = "CEFR-RECORD-1"
OLD_TEST_DESCRIPTION = (
    "BMB va British Council CD-IELTS rasmiy kompyuter imtihoni nusxasi. "
    "Listening (35 ta), Reading (35 ta), Writing (3 ta) va Speaking (4 qism)."
)
NEW_TEST_DESCRIPTION = (
    "Multi-level formatidagi mashq testi (eski versiya). "
    "Listening (35 ta), Reading (35 ta), Writing (3 ta) va Speaking (4 qism)."
)
TEXT_FIXES = [
    # (app, model, field, old, new)
    ("courses", "Category", "description",
     "Authentic British Council & BMB Multi-Level Computer Delivered Exams",
     "CEFR Multi-level va IELTS formatidagi mashq testlari."),
    ("courses", "Category", "name", "CEFR & IELTS Official Mocks", "CEFR & IELTS Mocks"),
    ("courses", "Course", "title",
     "CEFR Multi-Level & IELTS Authentic Exam Series", "CEFR Multi-Level & IELTS Practice Series"),
    ("courses", "Course", "description",
     "Rasmiy BMB va British Council andozasidagi Multi-Level va CD-IELTS sinov imtihonlari to'plami.",
     "Multi-level va IELTS formatidagi mashq testlari to'plami."),
]


def forwards(apps, schema_editor):
    Test = apps.get_model("tests", "Test")
    Test.objects.filter(mock_code=MOCK_CODE).update(status="archived", is_active=False)
    Test.objects.filter(mock_code=MOCK_CODE, description=OLD_TEST_DESCRIPTION).update(
        description=NEW_TEST_DESCRIPTION
    )
    for app, model, field, old, new in TEXT_FIXES:
        Model = apps.get_model(app, model)
        if field == "name" and Model.objects.filter(name=new).exists():
            continue  # name is unique
        Model.objects.filter(**{field: old}).update(**{field: new})


def backwards(apps, schema_editor):
    Test = apps.get_model("tests", "Test")
    Test.objects.filter(mock_code=MOCK_CODE, status="archived").update(status="published", is_active=True)


class Migration(migrations.Migration):
    dependencies = [
        ("tests", "0017_testattempt_trial_part"),
        ("courses", "0010_studentgroup_telegram_chat_id"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
