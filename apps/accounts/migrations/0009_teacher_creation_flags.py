from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0008_email_lower_unique"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="can_create_essay_topic",
            field=models.BooleanField(
                default=False,
                help_text="O'qituvchiga esse mavzulari yaratishga ruxsat berish. Admin tomonidan boshqariladi.",
                verbose_name="esse mavzusi yaratish huquqi",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="can_create_test",
            field=models.BooleanField(
                default=False,
                help_text="O'qituvchiga testlar yaratish / import qilishga ruxsat berish. Admin tomonidan boshqariladi.",
                verbose_name="test yaratish huquqi",
            ),
        ),
    ]
