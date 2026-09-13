# Generated for verified share-contact flow
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0005_telegramauthtoken_consumed_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='telegramauthtoken',
            name='phone_verified',
            field=models.BooleanField(default=False, help_text='True if phone was shared via Telegram contact (verified)'),
        ),
    ]
