from django.db import migrations, models
import django.db.models.functions as Func


def normalize_emails(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    seen_lower = {}
    for user in User.objects.only("id", "email").order_by("id"):
        raw = (user.email or "").strip()
        norm = raw.lower()
        if not norm:
            continue
        if norm in seen_lower:
            # Duplicate case-insensitive — make it unique so constraint can be added.
            # Keep earliest id, rename later duplicate to +dup{id}
            user.email = f"{norm}+dup{user.id}@example.invalid"
            user.save(update_fields=["email"])
        elif raw != norm:
            user.email = norm
            user.save(update_fields=["email"])
            seen_lower[norm] = user.id
        else:
            seen_lower[norm] = user.id


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_telegramlinkchallenge"),
    ]

    operations = [
        migrations.RunPython(normalize_emails, reverse_noop, elidable=False),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(Func.Lower("email"), name="uniq_user_email_lower"),
        ),
    ]
