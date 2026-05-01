from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from azure.storage.blob import BlobServiceClient
from urllib.parse import urlparse, unquote
import os

from .models import EmailLog, COARecord, EscalationRecord
from .serializers import EmailLogSerializer, COARecordSerializer, EscalationRecordSerializer
from .tasks import check_and_process_emails


# ─── API Views ───────────────────────────────────────────────

class EmailLogListView(APIView):
    def get(self, request):
        emails = EmailLog.objects.all().order_by("-received_at")
        serializer = EmailLogSerializer(emails, many=True)
        return Response(serializer.data)


class COARecordListView(APIView):
    def get(self, request):
        records = COARecord.objects.select_related("email").order_by("-id")
        serializer = COARecordSerializer(records, many=True)
        return Response(serializer.data)


class EscalationRecordListView(APIView):
    def get(self, request):
        records = EscalationRecord.objects.select_related("email").order_by("-id")
        serializer = EscalationRecordSerializer(records, many=True)
        return Response(serializer.data)


class TriggerEmailProcessingView(APIView):
    def post(self, request):
        check_and_process_emails.delay()
        return Response({"message": "Email processing triggered."}, status=status.HTTP_202_ACCEPTED)


# ─── UI Views ────────────────────────────────────────────────

def dashboard(request):
    context = {
        "total_emails": EmailLog.objects.count(),
        "total_coa": COARecord.objects.count(),
        "total_escalations": EscalationRecord.objects.count(),
        "recent_emails": EmailLog.objects.order_by("-received_at")[:10],
    }
    return render(request, "core/dashboard.html", context)


def emails_page(request):
    return render(request, "core/emails.html", {
        "emails": EmailLog.objects.order_by("received_at")
    })


def coa_page(request):
    return render(request, "core/coa.html", {
        "records": COARecord.objects.select_related("email").order_by("-id")
    })


def escalations_page(request):
    return render(request, "core/escalations.html", {
        "records": EscalationRecord.objects.select_related("email").order_by("-id")
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
