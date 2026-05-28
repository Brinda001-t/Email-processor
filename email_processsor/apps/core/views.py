from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import EmailLog, EscalationRecord, ReplyEmail
from .serializers import EmailLogSerializer, EscalationRecordSerializer, ReplyEmailSerializer
from .tasks import check_and_process_emails
from apps.escalation.teams_notifier import send_teams_alert


class EmailLogListView(APIView):
    def get(self, request):
        emails = EmailLog.objects.all().order_by("-received_at")
        serializer = EmailLogSerializer(emails, many=True)
        return Response(serializer.data)


class ReplyEmailListView(APIView):
    def get(self, request):
        replies = ReplyEmail.objects.select_related("parent").order_by("-received_at")
        serializer = ReplyEmailSerializer(replies, many=True)
        return Response(serializer.data)


class EscalationRecordListView(APIView):
    def get(self, request):
        records = EscalationRecord.objects.select_related("email", "reply_email").order_by("-id")
        serializer = EscalationRecordSerializer(records, many=True)
        return Response(serializer.data)


class TriggerEmailProcessingView(APIView):
    def post(self, request):
        check_and_process_emails.delay()
        return Response({"message": "Email processing triggered."}, status=status.HTTP_202_ACCEPTED)


def resend_escalation(request, record_id):
    record = get_object_or_404(EscalationRecord, id=record_id)
    source = record.linked_email
    if not source:
        return JsonResponse({"error": "No linked email found"}, status=400)
    alert_payload = {
        "subject": source.subject,
        "from": {"emailAddress": {"address": source.sender}},
        "body": {"content": source.body},
    }
    sent, err = send_teams_alert(alert_payload, reason=record.reason, priority=record.priority)
    record.teams_sent = sent
    record.teams_error = "" if sent else err
    record.save(update_fields=["teams_sent", "teams_error"])
    if sent:
        return JsonResponse({"status": "ok"})
    return JsonResponse({"status": "error", "error": err}, status=502)
