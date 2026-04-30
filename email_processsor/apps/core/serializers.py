from rest_framework import serializers
from .models import EmailLog, COARecord, EscalationRecord


class EmailLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailLog
        fields = "__all__"


class COARecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = COARecord
        fields = "__all__"


class EscalationRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = EscalationRecord
        fields = "__all__"
