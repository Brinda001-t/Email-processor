from collections import defaultdict

from django.core.paginator import Paginator
from django.http import JsonResponse
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import EmailLog, EscalationRecord, ReplyEmail, SkipLog
from .serializers import EmailLogSerializer, EscalationRecordSerializer, ReplyEmailSerializer
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
def logout_view(request):
    logout(request)
    return redirect("/login/")


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

@login_required
def dashboard(request):
    all_emails = EmailLog.objects.order_by("-received_at")
    paginator = Paginator(all_emails, 10)
    recent_emails = paginator.get_page(request.GET.get("page", 1))
    return render(request, "core/dashboard.html", {
        "total_emails": EmailLog.objects.count() + ReplyEmail.objects.count(),
        "total_escalations": EscalationRecord.objects.count(),
        "total_skipped": SkipLog.objects.count(),
        "recent_emails": recent_emails,
    })


@login_required
def emails_page(request):
    qs = EmailLog.objects.order_by("-received_at")
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    reply_counts = defaultdict(int)
    for r in ReplyEmail.objects.values_list("thread_id", flat=True):
        if r:
            reply_counts[r] += 1

    for e in page_obj:
        e.thread_size = 1 + reply_counts.get(e.thread_id, 0) if e.thread_id else 1
        e.is_thread_root = True
        e.is_reply = False
        e.parent_email = None

    return render(request, "core/emails.html", {
        "emails": page_obj,
        "total_emails": paginator.count,
    })


@login_required
def escalations_page(request):
    qs = EscalationRecord.objects.select_related("email", "reply_email").order_by("-id")
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    return render(request, "core/escalations.html", {
        "records": page_obj,
        "total_escalations": paginator.count,
    })


@login_required
def skip_log_page(request):
    return render(request, "core/skip_log.html", {
        "records": SkipLog.objects.order_by("-skipped_at")
    })


@login_required
def trigger_view(request):
    if request.method == "POST":
        check_and_process_emails.delay()
    return redirect("/dashboard/")
