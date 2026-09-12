from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0005_user_is_bot")]
    operations = [
        migrations.AddField(
            model_name="user",
            name="telegram_identity_verified_at",
            field=models.DateTimeField(
                null=True,
                blank=True,
                verbose_name="Telegram identifikatori tasdiqlangan vaqt",
                help_text=(
                    "Numeric Telegram ID bot imzosi yoki ikki kanalli bog'lash "
                    "orqali tasdiqlangan bo'lsa to'ldiriladi."
                ),
            ),
        ),
    ]
