from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        # EmailLog
        migrations.RemoveField(model_name='emaillog', name='extraction_tokens'),
        migrations.RemoveField(model_name='emaillog', name='total_tokens'),
        migrations.RemoveField(model_name='emaillog', name='responded_at'),

        # ReplyEmail
        migrations.RemoveField(model_name='replyemail', name='extraction_tokens'),
        migrations.RemoveField(model_name='replyemail', name='total_tokens'),
        migrations.RemoveField(model_name='replyemail', name='responded_at'),

        # EscalationRecord
        migrations.RemoveField(model_name='escalationrecord', name='reply_email'),
    ]
