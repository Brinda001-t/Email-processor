import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_remove_unused_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='escalationrecord',
            name='reply_email',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='escalations',
                to='core.replyemail',
            ),
        ),
    ]
