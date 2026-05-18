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
    extraction_tokens = models.IntegerField(null=True, blank=True)
    total_tokens = models.IntegerField(null=True, blank=True)

    rfc_message_id = models.CharField(max_length=500, null=True, blank=True, db_index=True)
    in_reply_to = models.CharField(max_length=500, null=True, blank=True)
    thread_id = models.CharField(max_length=50, unique=True, null=True, blank=True)

    responded_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.subject


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
    extraction_tokens = models.IntegerField(null=True, blank=True)
    total_tokens = models.IntegerField(null=True, blank=True)

    rfc_message_id = models.CharField(max_length=500, null=True, blank=True, db_index=True)
    in_reply_to = models.CharField(max_length=500, null=True, blank=True)

    # Gmail thread_id stored directly (same value as parent.thread_id)
    thread_id = models.CharField(max_length=50, null=True, blank=True, db_index=True)

    responded_at = models.DateTimeField(null=True, blank=True)

    # Relational FK to the parent email using EmailLog.id (PK)
    parent = models.ForeignKey(
        EmailLog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replies',
    )

    def __str__(self):
        return f"Re: {self.subject}"


class SkipLog(models.Model):
    message_id = models.CharField(max_length=255, unique=True)
    sender = models.CharField(max_length=255)
    subject = models.TextField()
    skip_reason = models.CharField(max_length=50)
    skipped_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["skipped_at"])]


class COARecord(models.Model):
    # Exactly one of email / reply_email is set per record
    email = models.OneToOneField(
        EmailLog, null=True, blank=True, on_delete=models.CASCADE, related_name='coa'
    )
    reply_email = models.OneToOneField(
        ReplyEmail, null=True, blank=True, on_delete=models.CASCADE, related_name='coa'
    )

    company = models.CharField(max_length=255, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    contact_phone = models.CharField(max_length=50, null=True, blank=True)
    contact_email = models.EmailField(null=True, blank=True)
    product_name = models.CharField(max_length=255, null=True, blank=True)
    part_number = models.CharField(max_length=100, null=True, blank=True)
    lot_number = models.CharField(max_length=100, null=True, blank=True)
    lot_quantity = models.CharField(max_length=100, null=True, blank=True)
    manufacture_date = models.CharField(max_length=50, null=True, blank=True)
    expiration_date = models.CharField(max_length=50, null=True, blank=True)
    report_date = models.CharField(max_length=50, null=True, blank=True)
    approved_by = models.CharField(max_length=255, null=True, blank=True)
    test_results = models.JSONField(null=True, blank=True)
    pdf_url = models.URLField(null=True, blank=True)
    status = models.CharField(max_length=20, default="PENDING")

    version = models.IntegerField(default=1)
    is_current = models.BooleanField(default=True)
    parent_record = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='amendments'
    )
    amendment_reason = models.TextField(blank=True)
    superseded_at = models.DateTimeField(null=True, blank=True)
    changes_summary = models.JSONField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["lot_number", "company", "is_current"]),
        ]

    @property
    def linked_email(self):
        return self.email or self.reply_email


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

    @property
    def linked_email(self):
        return self.email or self.reply_email


class OrderTrackingRecord(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "PENDING"),
        ("RESOLVED", "RESOLVED"),
    ]

    email = models.OneToOneField(
        EmailLog, null=True, blank=True, on_delete=models.CASCADE
    )
    reply_email = models.OneToOneField(
        ReplyEmail, null=True, blank=True, on_delete=models.CASCADE
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    order_number = models.CharField(max_length=100, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
        ]

    @property
    def linked_email(self):
        return self.email or self.reply_email


