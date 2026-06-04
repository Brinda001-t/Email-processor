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
    logger.info("check_and_process_emails task started")
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
    received_at = parse_datetime(email.get("received_at") or "") or timezone.now()

    if not sender:
        logger.warning("Malformed email data for message %s — missing sender, skipping", message_id)
        SkipLog.objects.get_or_create(
            message_id=message_id,
            defaults={"sender": "", "subject": subject, "skip_reason": "malformed_email_data", "received_at": received_at},
        )
        outlook.mark_as_read(message_id)
        return
    headers = email.get("headers", {})
    in_reply_to = email.get("in_reply_to")
    thread_id = email.get("thread_id")
    rfc_message_id = email.get("rfc_message_id")

    rule_result = rule_classify(subject, sender, headers)
    if rule_result and rule_result["type"] == "SKIP":
        SkipLog.objects.get_or_create(
            message_id=message_id,
            defaults={
                "sender": sender,
                "subject": subject,
                "skip_reason": rule_result.get("reason", "unknown"),
                "received_at": received_at,
            },
        )
        outlook.mark_as_read(message_id)
        return

    if in_reply_to:
        parent = EmailLog.objects.filter(thread_id=thread_id).first() if thread_id else None
        if parent is None:
            # Parent not in DB (predates system) — classify before deciding to skip
            if rule_result:
                _result = {
                    "type": rule_result["type"],
                    "subtype": rule_result.get("subtype", "general"),
                    "confidence": 1.0,
                    "reason": "rule_based",
                    "tokens": 0,
                }
                _method = "rule_based"
            else:
                _result = classify_email(f"Subject: {subject}\n\n{body}")
                _method = "ai"

            if _result["type"] != "ESCALATION":
                SkipLog.objects.get_or_create(
                    message_id=message_id,
                    defaults={
                        "sender": sender,
                        "subject": subject,
                        "skip_reason": "reply_no_escalation_parent",
                        "received_at": received_at,
                    },
                )
                outlook.mark_as_read(message_id)
                return

            # Escalation reply with no parent in DB — save to ReplyEmail and alert
            reply_log, _ = ReplyEmail.objects.get_or_create(
                message_id=message_id,
                defaults={
                    "subject": subject,
                    "sender": sender,
                    "body": body,
                    "received_at": received_at,
                    "rfc_message_id": rfc_message_id,
                    "in_reply_to": in_reply_to,
                    "thread_id": thread_id,
                    "parent": None,
                    "status": "PROCESSED",
                    "classification": _result["type"],
                    "email_subtype": _result.get("subtype", "general"),
                    "classification_method": _method,
                    "confidence_score": _result.get("confidence"),
                    "classification_tokens": _result.get("tokens"),
                },
            )
            reason = f"Reply classified as ESCALATION (no parent in DB): {subject}"
            try:
                record = EscalationRecord.objects.create(reply_email=reply_log, priority="HIGH", reason=reason)
                send_reply_escalation_alert.apply_async(args=[record.id], countdown=PRIORITY_HIGH_MINUTES * 60)
                logger.info("Escalation alert scheduled for orphan reply: message_id=%s reply_id=%s", message_id, reply_log.id)
            except Exception:
                logger.exception("Failed to schedule escalation alert for orphan reply message_id=%s", message_id)
            outlook.mark_as_read(message_id)
            return
        else:
            if rule_result:
                reply_result = {
                    "type": rule_result["type"],
                    "subtype": rule_result.get("subtype", "general"),
                    "confidence": 1.0,
                    "reason": "rule_based",
                    "tokens": 0,
                }
                reply_method = "rule_based"
            else:
                reply_result = classify_email(f"Subject: {subject}\n\n{body}")
                reply_method = "ai"

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
                    "classification": reply_result["type"],
                    "email_subtype": reply_result.get("subtype", "general"),
                    "classification_method": reply_method,
                    "confidence_score": reply_result.get("confidence"),
                    "classification_tokens": reply_result.get("tokens"),
                },
            )

            if reply_result["type"] == "ESCALATION":
                reason = f"Reply classified as ESCALATION on thread: {subject}"
                try:
                    record = EscalationRecord.objects.create(email=parent, priority="HIGH", reason=reason)
                    send_reply_escalation_alert.apply_async(args=[record.id], countdown=PRIORITY_HIGH_MINUTES * 60)
                    logger.info("Escalation alert scheduled for reply: message_id=%s parent_id=%s", message_id, parent.id)
                except Exception:
                    logger.exception("Failed to schedule escalation alert for reply message_id=%s", message_id)
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
                "received_at": received_at,
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
def send_reply_escalation_alert(record_id):
    try:
        record = EscalationRecord.objects.get(id=record_id)
    except EscalationRecord.DoesNotExist:
        return

    if record.teams_sent:
        return

    source = record.reply_email or record.email
    if not source:
        logger.warning("EscalationRecord id=%s has no linked email, skipping alert", record_id)
        return

    alert_payload = {
        "subject": source.subject,
        "from": {"emailAddress": {"address": source.sender}},
        "body": {"content": source.body},
    }
    sent, err = send_teams_alert(alert_payload, reason=record.reason, priority=record.priority)
    record.teams_sent = sent
    record.teams_error = "" if sent else err
    record.save(update_fields=["teams_sent", "teams_error"])
    logger.info("Reply escalation alert sent: record id=%s sent=%s", record_id, sent)


@shared_task
def escalate_unattended_emails():
    """Watchdog — runs every 15 minutes. Alerts on any ESCALATION email unattended for 60+ minutes."""
    now = timezone.now()

    for log in EmailLog.objects.filter(status="PROCESSED", classification="ESCALATION"):
        try:
            _escalate_single(log, now)
        except Exception:
            logger.exception("Failed escalating email id=%s", log.id)

    for reply in ReplyEmail.objects.filter(status="PROCESSED", classification="ESCALATION", parent=None):
        try:
            _escalate_orphan_reply(reply, now)
        except Exception:
            logger.exception("Failed escalating orphan reply id=%s", reply.id)


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


def _escalate_orphan_reply(reply, now):
    elapsed_minutes = (now - reply.received_at).total_seconds() / 60

    if elapsed_minutes < PRIORITY_HIGH_MINUTES:
        return

    existing = EscalationRecord.objects.filter(reply_email=reply).first()
    if existing:
        if existing.teams_sent:
            return
        alert_payload = {
            "subject": reply.subject,
            "from": {"emailAddress": {"address": reply.sender}},
            "body": {"content": reply.body},
        }
        sent, err = send_teams_alert(alert_payload, reason=existing.reason, priority=existing.priority)
        existing.teams_sent = sent
        existing.teams_error = "" if sent else err
        existing.save(update_fields=["teams_sent", "teams_error"])
        if sent:
            logger.info("Orphan reply escalation alert retried successfully: reply id=%s", reply.id)
        else:
            logger.warning("Orphan reply escalation alert retry failed: reply id=%s error=%s", reply.id, err)
        return

    reason = f"Reply unattended for {int(elapsed_minutes)} minutes (type: ESCALATION, no parent)"
    record = EscalationRecord.objects.create(reply_email=reply, priority="HIGH", reason=reason)

    alert_payload = {
        "subject": reply.subject,
        "from": {"emailAddress": {"address": reply.sender}},
        "body": {"content": reply.body},
    }
    sent, err = send_teams_alert(alert_payload, reason=reason, priority="HIGH")
    record.teams_sent = sent
    record.teams_error = "" if sent else err
    record.save(update_fields=["teams_sent", "teams_error"])

    logger.info(
        "Teams alert sent for orphan reply: id=%s priority=HIGH elapsed=%.1fmin sender=%s",
        reply.id, elapsed_minutes, reply.sender,
    )
