import re
from rest_framework import serializers
from .models import EmailLog, ReplyEmail, EscalationRecord, SkipLog


def _body_preview(html_body, length=300):
    text = re.sub(r"<[^>]+>", " ", html_body or "")
    text = " ".join(text.split())
    return text[:length] + "..." if len(text) > length else text


class EmailLogSerializer(serializers.ModelSerializer):
    body_preview = serializers.SerializerMethodField()
    received_at = serializers.DateTimeField(format="%d %b %Y, %I:%M %p")

    class Meta:
        model = EmailLog
        fields = ["id", "subject", "sender", "received_at", "classification", "email_subtype", "responded_at", "body_preview"]

    def get_body_preview(self, obj):
        return _body_preview(obj.body)


class ReplyEmailSerializer(serializers.ModelSerializer):
    received_at = serializers.DateTimeField(format="%d %b %Y, %I:%M %p")

    class Meta:
        model = ReplyEmail
        fields = ["id", "subject", "sender", "received_at", "parent"]


class EscalationRecordSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format="%d %b %Y, %I:%M %p")

    class Meta:
        model = EscalationRecord
        fields = ["id", "email", "reply_email", "priority", "reason", "teams_sent", "teams_error", "created_at"]


class SkipLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SkipLog
        fields = ["id", "sender", "subject", "skip_reason", "skipped_at"]
