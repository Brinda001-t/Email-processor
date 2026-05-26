import logging

from celery import shared_task
from django.utils import timezone

from .models import EmailLog, ReplyEmail, EscalationRecord, SkipLog
from .outlook_service import OutlookService, get_access_token
from apps.classifier.ai_classifier import classify_email
from apps.classifier.rule_classifier import rule_classify
from apps.escalation.teams_notifier import send_teams_alert

logger = logging.getLogger(__name__)

PRIORITY_HIGH_MINUTES = 60


@shared_task
def check_and_process_emails():
    outlook = OutlookService(token=get_access_token())
    emails = outlook.fetch_unread_emails()
    for email in emails:
        message_id = email["id"]

        already_done = (
            EmailLog.objects.filter(message_id=message_id, status="PROCESSED").exists()
            or ReplyEmail.objects.filter(message_id=message_id, status="PROCESSED").exists()
        )
        if already_done:
            continue

        subject = email["subject"]
        sender = email["from"]["emailAddress"]["address"]
        body = email["body"]["content"]
        headers = email.get("headers", {})
        in_reply_to = email.get("in_reply_to")
        thread_id = email.get("thread_id")
        rfc_message_id = email.get("rfc_message_id")
        is_reply = bool(in_reply_to)

        rule_result = rule_classify(subject, sender, headers)
        if rule_result and rule_result["type"] == "SKIP":
            SkipLog.objects.get_or_create(
                message_id=message_id,
                defaults={
                    "sender": sender,
                    "subject": subject,
                    "skip_reason": rule_result.get("reason", "unknown"),
                }
            )
            outlook.mark_as_read(message_id)
            continue

        if is_reply:
            parent = EmailLog.objects.filter(thread_id=thread_id).first() if thread_id else None
            log, _ = ReplyEmail.objects.get_or_create(
                message_id=message_id,
                defaults={
                    "subject": subject,
                    "sender": sender,
                    "body": body,
                    "received_at": timezone.now(),
                    "rfc_message_id": rfc_message_id,
                    "in_reply_to": in_reply_to,
                    "thread_id": thread_id,
                    "parent": parent,
                }
            )
        else:
            log, _ = EmailLog.objects.get_or_create(
                message_id=message_id,
                defaults={
                    "subject": subject,
                    "sender": sender,
                    "body": body,
                    "received_at": timezone.now(),
                    "rfc_message_id": rfc_message_id,
                    "in_reply_to": in_reply_to,
                    "thread_id": thread_id,
                }
            )

        try:
            if rule_result:
                result = {
                    "type": rule_result["type"],
                    "subtype": rule_result.get("subtype", "general"),
                    "confidence": 1.0,
                    "reason": "rule_based",
                    "tokens": 0,
                }
                method = "rule_based"
            else:
                result = classify_email(f"Subject: {subject}\n\n{body}")
                method = "ai"

            log.classification = result["type"]
            log.email_subtype = result.get("subtype", "general")
            log.classification_method = method
            log.confidence_score = result.get("confidence")
            log.classification_tokens = result.get("tokens")
            log.total_tokens = log.classification_tokens or 0
            log.status = "PROCESSED"
            log.save()

            if result["type"] == "ESCALATION":
                send_escalation_alert.apply_async(args=[log.id], countdown=PRIORITY_HIGH_MINUTES * 60)

            outlook.mark_as_read(message_id)

        except Exception:
            logger.exception("Failed processing email %s (subject: %s)", message_id, log.subject)
            log.status = "FAILED"
            log.save()


@shared_task
def send_escalation_alert(email_log_id):
    try:
        log = EmailLog.objects.get(id=email_log_id)
    except EmailLog.DoesNotExist:
        return

    if EscalationRecord.objects.filter(email=log).exists():
        return

    if log.thread_id and ReplyEmail.objects.filter(thread_id=log.thread_id).exists():
        return

    reason = f"Email unattended for {PRIORITY_HIGH_MINUTES} minutes (type: {log.classification or 'UNKNOWN'})"
    record = EscalationRecord.objects.create(
        email=log,
        priority="HIGH",
        reason=reason,
    )

    alert_payload = {
        "subject": log.subject,
        "from": {"emailAddress": {"address": log.sender}},
        "body": {"content": log.body},
    }
    sent, err = send_teams_alert(alert_payload, reason=reason, priority="HIGH")
    record.teams_sent = sent
    record.teams_error = "" if sent else err
    record.save(update_fields=["teams_sent", "teams_error"])

    logger.info("Escalation alert sent: email id=%s sender=%s", log.id, log.sender)


@shared_task
def escalate_unattended_emails():
    """Watchdog — runs every 15 minutes. Alerts on any ESCALATION email unattended for 60+ minutes."""
    now = timezone.now()

    for log in EmailLog.objects.filter(status="PROCESSED", classification="ESCALATION"):
        elapsed_minutes = (now - log.received_at).total_seconds() / 60

        if elapsed_minutes < PRIORITY_HIGH_MINUTES:
            continue

        if EscalationRecord.objects.filter(email=log).exists():
            continue

        reason = f"Email unattended for {int(elapsed_minutes)} minutes (type: {log.classification or 'UNKNOWN'})"
        record = EscalationRecord.objects.create(
            email=log,
            priority="HIGH",
            reason=reason,
        )

        alert_payload = {
            "subject": log.subject,
            "from": {"emailAddress": {"address": log.sender}},
            "body": {"content": log.body},
        }
        sent, err = send_teams_alert(alert_payload, reason=reason, priority="HIGH")
        record.teams_sent = sent
        record.teams_error = "" if sent else err
        record.save(update_fields=["teams_sent", "teams_error"])

        logger.info(
            "Teams alert sent: email id=%s priority=HIGH elapsed=%.1fmin sender=%s",
            log.id, elapsed_minutes, log.sender,
        )
