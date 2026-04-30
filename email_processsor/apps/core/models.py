
from django.db import models

class EmailLog(models.Model):
    message_id = models.CharField(max_length=255, unique=True)
    subject = models.TextField()
    sender = models.EmailField()
    body = models.TextField()
    received_at = models.DateTimeField()

    status = models.CharField(
        max_length=20,
        choices=[
            ("NEW", "NEW"),
            ("PROCESSED", "PROCESSED"),
            ("FAILED", "FAILED"),
        ],
        default="NEW"
    )

    classification = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return self.subject


class COARecord(models.Model):
    email = models.OneToOneField(EmailLog, on_delete=models.CASCADE)
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


class EscalationRecord(models.Model):
    email = models.OneToOneField(EmailLog, on_delete=models.CASCADE)
    reason = models.TextField()
    teams_sent = models.BooleanField(default=False)