import json
import os
from collections import defaultdict
from urllib.parse import unquote, urlparse

from azure.storage.blob import BlobServiceClient
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    COARecord, EmailLog, EscalationRecord, OrderTrackingRecord,
    ReplyEmail, SkipLog,
)
from .serializers import (
    COARecordSerializer, EmailLogSerializer, EscalationRecordSerializer,
    ReplyEmailSerializer,
)
from .tasks import check_and_process_emails
from apps.escalation.teams_notifier import send_teams_alert


# ─── API Views ───────────────────────────────────────────────

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


class COARecordListView(APIView):
    def get(self, request):
        records = COARecord.objects.select_related("email", "reply_email").order_by("-id")
        serializer = COARecordSerializer(records, many=True)
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


# ─── Escalation action endpoints ─────────────────────────────

@csrf_exempt
@require_POST
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


# ─── UI Views ────────────────────────────────────────────────

def dashboard(request):
    all_emails = EmailLog.objects.order_by("-received_at")

    paginator = Paginator(all_emails, 10)
    page = request.GET.get("page", 1)
    recent_emails = paginator.get_page(page)

    context = {
        "total_emails": EmailLog.objects.count() + ReplyEmail.objects.count(),
        "total_coa": COARecord.objects.filter(is_current=True).count(),
        "total_escalations": EscalationRecord.objects.count(),
        "total_orders": OrderTrackingRecord.objects.count(),
        "pending_orders": OrderTrackingRecord.objects.filter(status="PENDING").count(),
        "total_skipped": SkipLog.objects.count(),
        "recent_emails": recent_emails,
    }
    return render(request, "core/dashboard.html", context)


def emails_page(request):
    emails = list(EmailLog.objects.order_by("-received_at"))

    reply_counts = defaultdict(int)
    for r in ReplyEmail.objects.values_list("thread_id", flat=True):
        if r:
            reply_counts[r] += 1

    for e in emails:
        e.thread_size = 1 + reply_counts.get(e.thread_id, 0) if e.thread_id else 1
        e.is_thread_root = True
        e.is_reply = False
        e.parent_email = None

    return render(request, "core/emails.html", {"emails": emails})


def coa_page(request):
    show_all = request.GET.get("show_all") == "1"
    qs = COARecord.objects.select_related(
        "email", "reply_email", "parent_record"
    ).order_by("-id")
    if not show_all:
        qs = qs.filter(is_current=True)
    return render(request, "core/coa.html", {
        "records": qs,
        "show_all": show_all,
    })


def escalations_page(request):
    return render(request, "core/escalations.html", {
        "records": EscalationRecord.objects.select_related("email", "reply_email").order_by("-id"),
    })


def orders_page(request):
    return render(request, "core/orders.html", {
        "records": OrderTrackingRecord.objects.select_related("email", "reply_email").order_by("-id")
    })


def skip_log_page(request):
    return render(request, "core/skip_log.html", {
        "records": SkipLog.objects.order_by("-skipped_at")
    })


def trigger_view(request):
    if request.method == "POST":
        check_and_process_emails.delay()
    return redirect("/dashboard/")


def download_coa_pdf(request, record_id):
    record = get_object_or_404(COARecord, id=record_id)

    conn_str = os.getenv("AZURE_STORAGE_CONTAINER_STRING")
    container = os.getenv("AZURE_STORAGE_CONTAINER_NAME")
    parsed = urlparse(record.pdf_url)
    blob_name = unquote(parsed.path.split(f"/{container}/", 1)[-1])

    blob_service = BlobServiceClient.from_connection_string(conn_str)
    blob_client = blob_service.get_blob_client(container=container, blob=blob_name)

    pdf_data = blob_client.download_blob().readall()

    response = HttpResponse(pdf_data, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="COA_{record.lot_number or record.id}.pdf"'
    return response
