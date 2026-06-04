from django.db import models


_STATUS_CHOICES = [
    ("NEW", "NEW"),
    ("PROCESSED", "PROCESSED"),
    ("FAILED", "FAILED"),
]


class EmailLog(models.Model):
    """Parent/original inbound emails (no in_reply_to)."""
    message_id = models.CharField(max_length=255, unique=True)
    subject = models.TextField()
    sender = models.EmailField()
    body = models.TextField()
    received_at = models.DateTimeField()

    status = models.CharField(max_length=20, choices=_STATUS_CHOICES, default="NEW")

    classification = models.CharField(max_length=50, null=True, blank=True)
    email_subtype = models.CharField(max_length=50, null=True, blank=True)
    classification_method = models.CharField(max_length=20, null=True, blank=True)
    confidence_score = models.FloatField(null=True, blank=True)

    classification_tokens = models.IntegerField(null=True, blank=True)

    rfc_message_id = models.CharField(max_length=500, null=True, blank=True, db_index=True)
    in_reply_to = models.CharField(max_length=500, null=True, blank=True)
    thread_id = models.CharField(max_length=255, unique=True, null=True, blank=True)

    def __str__(self):
        return self.subject

    class Meta:
        db_table = 'emailflow].[EmailLog'


class ReplyEmail(models.Model):
    """Reply/follow-up emails. Linked to the parent EmailLog via the parent FK."""
    message_id = models.CharField(max_length=255, unique=True)
    subject = models.TextField()
    sender = models.EmailField()
    body = models.TextField()
    received_at = models.DateTimeField()

    status = models.CharField(max_length=20, choices=_STATUS_CHOICES, default="NEW")

    classification = models.CharField(max_length=50, null=True, blank=True)
    email_subtype = models.CharField(max_length=50, null=True, blank=True)
    classification_method = models.CharField(max_length=20, null=True, blank=True)
    confidence_score = models.FloatField(null=True, blank=True)

    classification_tokens = models.IntegerField(null=True, blank=True)

    rfc_message_id = models.CharField(max_length=500, null=True, blank=True, db_index=True)
    in_reply_to = models.CharField(max_length=500, null=True, blank=True)
    thread_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)

    parent = models.ForeignKey(
        EmailLog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replies',
    )

    def __str__(self):
        return f"Re: {self.subject}"

    class Meta:
        db_table = 'emailflow].[ReplyEmail'


class SkipLog(models.Model):
    message_id = models.CharField(max_length=255, unique=True)
    sender = models.CharField(max_length=255)
    subject = models.TextField()
    skip_reason = models.CharField(max_length=50)
    received_at = models.DateTimeField(null=True, blank=True)
    skipped_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'emailflow].[SkipLog'
        indexes = [models.Index(fields=["skipped_at"])]


_PRIORITY_CHOICES = [
    ("HIGH", "High"),
    ("MEDIUM", "Medium"),
    ("LOW", "Low"),
]


class EscalationRecord(models.Model):
    email = models.ForeignKey(
        EmailLog, null=True, blank=True, on_delete=models.CASCADE, related_name='escalations'
    )
    reply_email = models.ForeignKey(
        ReplyEmail, null=True, blank=True, on_delete=models.CASCADE, related_name='escalations'
    )
    priority = models.CharField(max_length=10, choices=_PRIORITY_CHOICES, default="LOW")
    reason = models.TextField(blank=True)
    teams_sent = models.BooleanField(default=False)
    teams_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        db_table = 'emailflow].[EscalationRecord'


class AppLog(models.Model):
    level = models.CharField(max_length=20)
    logger_name = models.CharField(max_length=255)
    message = models.TextField()
    traceback = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'emailflow].[AppLog'
