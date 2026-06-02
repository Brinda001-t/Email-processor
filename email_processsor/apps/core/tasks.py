import logging

from celery import shared_task
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import EmailLog, ReplyEmail, EscalationRecord, SkipLog
from .outlook_service import OutlookService, get_access_token
from apps.classifier.ai_classifier import classify_email
from apps.classifier.rule_classifier import rule_classify
from apps.escalation.teams_notifier import send_teams_alert

logger = logging.getLogger(__name__)

PRIORITY_HIGH_MINUTES = 60


@shared_task
def check_and_process_emails():
    try:
        outlook = OutlookService(token=get_access_token())
        emails = outlook.fetch_unread_emails()
    except Exception:
        logger.exception("Failed to connect to Outlook or fetch emails")
        return

    for email in emails:
        try:
            _process_single_email(outlook, email)
        except Exception:
            logger.exception("Unexpected error processing email %s", email.get("id"))


def _process_single_email(outlook, email):
    message_id = email["id"]

    already_done = (
        EmailLog.objects.filter(message_id=message_id).exists()
        or ReplyEmail.objects.filter(message_id=message_id).exists()
        or SkipLog.objects.filter(message_id=message_id).exists()
    )
    if already_done:
        outlook.mark_as_read(message_id)
        return

    subject = email.get("subject", "")
    sender = email.get("from", {}).get("emailAddress", {}).get("address", "")
    body = email.get("body", {}).get("content", "")

    if not sender:
        logger.warning("Malformed email data for message %s — missing sender, skipping", message_id)
        SkipLog.objects.get_or_create(
            message_id=message_id,
            defaults={"sender": "", "subject": subject, "skip_reason": "malformed_email_data"},
        )
        outlook.mark_as_read(message_id)
        return
    headers = email.get("headers", {})
    in_reply_to = email.get("in_reply_to")
    thread_id = email.get("thread_id")
    rfc_message_id = email.get("rfc_message_id")
    received_at = parse_datetime(email.get("received_at") or "") or timezone.now()

    rule_result = rule_classify(subject, sender, headers)
    if rule_result and rule_result["type"] == "SKIP":
        SkipLog.objects.get_or_create(
            message_id=message_id,
            defaults={
                "sender": sender,
                "subject": subject,
                "skip_reason": rule_result.get("reason", "unknown"),
            },
        )
        outlook.mark_as_read(message_id)
        return

    if in_reply_to:
        parent = EmailLog.objects.filter(thread_id=thread_id).first() if thread_id else None
        if parent is None:
            # Reply to a non-escalation thread — no action needed
            SkipLog.objects.get_or_create(
                message_id=message_id,
                defaults={
                    "sender": sender,
                    "subject": subject,
                    "skip_reason": "reply_no_escalation_parent",
                },
            )
        else:
            ReplyEmail.objects.get_or_create(
                message_id=message_id,
                defaults={
                    "subject": subject,
                    "sender": sender,
                    "body": body,
                    "received_at": received_at,
                    "rfc_message_id": rfc_message_id,
                    "in_reply_to": in_reply_to,
                    "thread_id": thread_id,
                    "parent": parent,
                    "status": "PROCESSED",
                },
            )
        outlook.mark_as_read(message_id)
        return

    # Original email — classify first, then store based on result
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

    if result["type"] != "ESCALATION":
        SkipLog.objects.get_or_create(
            message_id=message_id,
            defaults={
                "sender": sender,
                "subject": subject,
                "skip_reason": "classified_other",
            },
        )
        outlook.mark_as_read(message_id)
        return

    log = EmailLog.objects.create(
        message_id=message_id,
        subject=subject,
        sender=sender,
        body=body,
        received_at=received_at,
        rfc_message_id=rfc_message_id,
        in_reply_to=in_reply_to,
        thread_id=thread_id,
        classification=result["type"],
        email_subtype=result.get("subtype", "general"),
        classification_method=method,
        confidence_score=result.get("confidence"),
        classification_tokens=result.get("tokens"),
        total_tokens=result.get("tokens") or 0,
        status="PROCESSED",
    )
    send_escalation_alert.apply_async(args=[log.id], countdown=PRIORITY_HIGH_MINUTES * 60)
    outlook.mark_as_read(message_id)


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
    try:
        record = EscalationRecord.objects.create(email=log, priority="HIGH", reason=reason)
    except Exception:
        logger.exception("Failed to create EscalationRecord for email id=%s", log.id)
        return

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
        try:
            _escalate_single(log, now)
        except Exception:
            logger.exception("Failed escalating email id=%s", log.id)


def _escalate_single(log, now):
    elapsed_minutes = (now - log.received_at).total_seconds() / 60

    if elapsed_minutes < PRIORITY_HIGH_MINUTES:
        return

    existing = EscalationRecord.objects.filter(email=log).first()
    if existing:
        if existing.teams_sent:
            return
        alert_payload = {
            "subject": log.subject,
            "from": {"emailAddress": {"address": log.sender}},
            "body": {"content": log.body},
        }
        sent, err = send_teams_alert(alert_payload, reason=existing.reason, priority=existing.priority)
        existing.teams_sent = sent
        existing.teams_error = "" if sent else err
        existing.save(update_fields=["teams_sent", "teams_error"])
        if sent:
            logger.info("Escalation alert retried successfully: email id=%s", log.id)
        else:
            logger.warning("Escalation alert retry failed: email id=%s error=%s", log.id, err)
        return

    reason = f"Email unattended for {int(elapsed_minutes)} minutes (type: {log.classification or 'UNKNOWN'})"
    record = EscalationRecord.objects.create(email=log, priority="HIGH", reason=reason)

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
