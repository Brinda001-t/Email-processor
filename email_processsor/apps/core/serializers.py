from rest_framework import serializers
from .models import EmailLog, ReplyEmail, COARecord, EscalationRecord


class EmailLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailLog
        fields = "__all__"


class ReplyEmailSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReplyEmail
        fields = "__all__"


class COARecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = COARecord
        fields = "__all__"


class EscalationRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = EscalationRecord
        fields = "__all__"
