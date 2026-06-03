from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import EmailLog, EscalationRecord, ReplyEmail, SkipLog
from .permissions import ApiKeyPermission
from .serializers import EmailLogSerializer, EscalationRecordSerializer, ReplyEmailSerializer, SkipLogSerializer
from .tasks import check_and_process_emails
from apps.escalation.teams_notifier import send_teams_alert


class _StandardPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 200


class EmailLogListView(APIView):
    permission_classes = [ApiKeyPermission]

    def get(self, request):
        emails = EmailLog.objects.all().order_by("-received_at")
        paginator = _StandardPagination()
        page = paginator.paginate_queryset(emails, request)
        serializer = EmailLogSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class ReplyEmailListView(APIView):
    permission_classes = [ApiKeyPermission]

    def get(self, request):
        replies = ReplyEmail.objects.select_related("parent").order_by("-received_at")
        paginator = _StandardPagination()
        page = paginator.paginate_queryset(replies, request)
        serializer = ReplyEmailSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class EscalationRecordListView(APIView):
    permission_classes = [ApiKeyPermission]

    def get(self, request):
        records = EscalationRecord.objects.select_related("email", "reply_email").order_by("-id")
        paginator = _StandardPagination()
        page = paginator.paginate_queryset(records, request)
        serializer = EscalationRecordSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class SkipLogListView(APIView):
    permission_classes = [ApiKeyPermission]

    def get(self, request):
        logs = SkipLog.objects.all().order_by("-skipped_at")
        paginator = _StandardPagination()
        page = paginator.paginate_queryset(logs, request)
        serializer = SkipLogSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class TriggerEmailProcessingView(APIView):
    permission_classes = [ApiKeyPermission]

    def post(self, request):
        try:
            check_and_process_emails.delay()
        except Exception as exc:
            return Response(
                {"error": "Task queue unavailable", "detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"message": "Email processing triggered."}, status=status.HTTP_202_ACCEPTED)


# @api_view(["POST"])
# @permission_classes([ApiKeyPermission])
# def resend_escalation(request, record_id):
#     record = get_object_or_404(EscalationRecord, id=record_id)
#     source = record.email or record.reply_email
#     if not source:
#         return Response({"error": "No linked email found"}, status=status.HTTP_400_BAD_REQUEST)
#     alert_payload = {
#         "subject": source.subject,
#         "from": {"emailAddress": {"address": source.sender}},
#         "body": {"content": source.body},
#     }
#     sent, err = send_teams_alert(alert_payload, reason=record.reason, priority=record.priority)
#     record.teams_sent = sent
#     record.teams_error = "" if sent else err
#     record.save(update_fields=["teams_sent", "teams_error"])
#     if sent:
#         return Response({"status": "ok"})
#     return Response({"status": "error", "error": err}, status=status.HTTP_502_BAD_GATEWAY)
