import logging
import datetime
import os
import re

from celery import shared_task
from django.db import models, transaction
from django.utils import timezone

from .models import (
    EmailLog, ReplyEmail, COARecord, EscalationRecord,
    OrderTrackingRecord, SkipLog,
)
from .gmail_service import GmailService
from .db_service import get_order_status
from apps.classifier.ai_classifier import classify_email
from apps.classifier.rule_classifier import rule_classify
from apps.coa.extractor import extract_coa_data
from apps.coa.pdf_generator import generate_pdf
from apps.coa.azure_storage import upload_to_azure
from apps.escalation.teams_notifier import send_teams_alert

logger = logging.getLogger(__name__)

# Minutes unresponded before HIGH priority escalation
PRIORITY_HIGH_MINUTES = 60

_COMPARABLE_FIELDS = [
    "company", "address", "contact_phone", "contact_email",
    "product_name", "part_number", "lot_number", "lot_quantity",
    "manufacture_date", "expiration_date", "report_date",
    "approved_by", "test_results",
]

_ORDER_NUMBER_RE = re.compile(
    r'\b(?:order|po|purchase[\s_-]*order|p\.o\.?)[\s#:.-]*([A-Z0-9][A-Z0-9-]{2,18})',
    re.IGNORECASE,
)

_DOC_ID_RE = re.compile(
    r'(?:^|\t)([A-Z]{2,}[A-Z0-9]{3,})\b',
    re.MULTILINE,
)


def _extract_all_order_numbers(text: str) -> list:
    seen = set()
    results = []
    for m in _ORDER_NUMBER_RE.finditer(text):
        candidate = m.group(1).upper().rstrip('-')
        if any(c.isdigit() for c in candidate) and candidate not in seen:
            seen.add(candidate)
            results.append(candidate)
    for m in _DOC_ID_RE.finditer(text):
        candidate = m.group(1).upper()
        if any(c.isdigit() for c in candidate) and candidate not in seen:
            seen.add(candidate)
            results.append(candidate)
    return results


def _norm_lot(lot):
    return re.sub(r'[\s\-_/]', '', (lot or '')).upper()


def _norm_company(name):
    cleaned = re.sub(
        r'\s*\b(inc|llc|ltd|corp|corporation|co|company|group|pvt|limited|gmbh)\.?\b\s*',
        ' ', (name or ''), flags=re.IGNORECASE
    )
    return re.sub(r'\s+', ' ', cleaned).strip().lower()


@shared_task
def check_and_process_emails():

    gmail = GmailService()
    emails = gmail.fetch_unread_emails()

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

        # Stage 0 + 1: rule-based pre-filter / fast classifier
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
            gmail.mark_as_read(message_id)
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

        mark_read = True

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
                result = classify_email(body)
                method = "ai"

            log.classification = result["type"]
            log.email_subtype = result.get("subtype", "general")
            log.classification_method = method
            log.confidence_score = result.get("confidence")
            log.classification_tokens = result.get("tokens")
            log.save()

            def _email_fk():
                return {"reply_email": log} if is_reply else {"email": log}

            # ---------------- COA FLOW ----------------
            if result["type"] == "COA":

                data = extract_coa_data(body)
                extraction_tokens = data.pop("_tokens", None)
                log.extraction_tokens = extraction_tokens
                log.total_tokens = (log.classification_tokens or 0) + (extraction_tokens or 0)
                log.save()

                lot_number = data.get("lot_number")
                company = data.get("company")
                tid = log.thread_id

                with transaction.atomic():
                    existing = None

                    if tid:
                        existing = (
                            COARecord.objects
                            .select_for_update()
                            .filter(
                                models.Q(email__thread_id=tid)
                                | models.Q(reply_email__thread_id=tid),
                                is_current=True,
                            )
                            .exclude(**_email_fk())
                            .first()
                        )

                    if not existing and lot_number and company:
                        existing = (
                            COARecord.objects
                            .select_for_update()
                            .filter(lot_number=lot_number, company=company, is_current=True)
                            .first()
                        )
                        if not existing:
                            norm_lot = _norm_lot(lot_number)
                            norm_co = _norm_company(company)
                            for candidate in COARecord.objects.select_for_update().filter(is_current=True):
                                if _norm_lot(candidate.lot_number) == norm_lot and _norm_company(candidate.company) == norm_co:
                                    existing = candidate
                                    break

                    if existing:
                        changes = {}
                        merged = {}
                        for field in _COMPARABLE_FIELDS:
                            old_val = getattr(existing, field)
                            new_val = data.get(field)
                            if new_val not in (None, "", []):
                                if new_val != old_val:
                                    changes[field] = {"old": old_val, "new": new_val}
                                merged[field] = new_val
                            else:
                                merged[field] = old_val

                        existing.is_current = False
                        existing.superseded_at = timezone.now()
                        existing.save(update_fields=["is_current", "superseded_at"])
                        coa_parent = existing
                        version = existing.version + 1
                    else:
                        merged = {f: data.get(f) for f in _COMPARABLE_FIELDS}
                        changes = {}
                        coa_parent = None
                        version = 1

                    coa = COARecord(**_email_fk())
                    coa.company = merged.get("company")
                    coa.address = merged.get("address")
                    coa.contact_phone = merged.get("contact_phone")
                    coa.contact_email = merged.get("contact_email")
                    coa.product_name = merged.get("product_name")
                    coa.part_number = merged.get("part_number")
                    coa.lot_number = merged.get("lot_number")
                    coa.lot_quantity = merged.get("lot_quantity")
                    coa.manufacture_date = merged.get("manufacture_date")
                    coa.expiration_date = merged.get("expiration_date")
                    coa.report_date = merged.get("report_date")
                    coa.approved_by = merged.get("approved_by")
                    coa.test_results = merged.get("test_results")
                    coa.version = version
                    coa.is_current = True
                    coa.parent_record = coa_parent
                    coa.amendment_reason = "Revised COA received" if coa_parent else ""
                    coa.changes_summary = changes if changes else None

                    pdf_path = generate_pdf(merged)
                    url = upload_to_azure(pdf_path)
                    os.remove(pdf_path)
                    coa.pdf_url = url
                    coa.status = "COMPLETED"
                    coa.save()

            # ---------------- ORDER FLOW ----------------
            elif result["type"] == "ORDER":
                log.total_tokens = log.classification_tokens or 0
                log.save()

                subtype = result.get("subtype", "status_check")

                ai_numbers = result.get("order_numbers") or (
                    [result["order_number"]] if result.get("order_number") else []
                )
                regex_numbers = _extract_all_order_numbers(subject + " " + body)
                seen_ids = set()
                order_numbers = []
                for n in ai_numbers + regex_numbers:
                    if n not in seen_ids:
                        seen_ids.add(n)
                        order_numbers.append(n)
                if not order_numbers:
                    order_numbers = ["UNKNOWN"]

                order_record, _ = OrderTrackingRecord.objects.get_or_create(
                    **_email_fk(),
                    defaults={
                        "status": "PENDING",
                        "order_number": order_numbers[0],
                    }
                )

                if subtype in ("status_check", "driver_status"):
                    try:
                        sections = []
                        for doc_id in order_numbers:
                            data = get_order_status(doc_id)
                            if subtype == "status_check":
                                if data["found"]:
                                    section = (
                                        f"Document {data['document_id']}:\n"
                                        f"  Document Type : {data['document_type']}\n"
                                        f"  Status        : {data['status']}\n"
                                    )
                                    driver = data.get("driver_info")
                                    if driver and driver.get("found"):
                                        section += (
                                            f"  Driver Update:\n"
                                            f"    Current Stage : {driver['current_stage']}\n"
                                            f"    Stage Status  : {driver['stage_status']}\n"
                                        )
                                else:
                                    section = f"Document {doc_id}:\n  No record found. Please verify the ID.\n"
                            else:  # driver_status
                                if data["found"]:
                                    driver = data.get("driver_info")
                                    if driver and driver.get("found"):
                                        section = (
                                            f"Document {data['document_id']}:\n"
                                            f"  Current Stage : {driver['current_stage']}\n"
                                            f"    Stage Status  : {driver['stage_status']}\n"
                                        )
                                    else:
                                        section = f"Document {doc_id}:\n  No driver information available.\n"
                                else:
                                    section = f"Document {doc_id}:\n  No record found. Please verify the ID.\n"
                            sections.append(section)

                        reply_body = (
                            "Dear Customer,\n\n"
                            "Here is the current status for your order inquiry:\n\n"
                            + "\n".join(sections)
                            + "\nEmail Flow System"
                        )

                        gmail.send_email(
                            to_address=sender,
                            subject=f"Re: {subject}",
                            body=reply_body,
                        )

                        now = timezone.now()
                        order_record.status = "RESOLVED"
                        order_record.resolved_at = now
                        order_record.save(update_fields=["status", "resolved_at"])

                        log.responded_at = now
                        log.save(update_fields=["responded_at"])

                    except Exception:
                        logger.exception("Failed to query DB or send order reply for email %s", message_id)

            # ---------------- ESCALATION FLOW ----------------
            elif result["type"] == "ESCALATION":
                # Watchdog handles time-based escalation and Teams alerts
                log.total_tokens = log.classification_tokens or 0
                log.save()

            # ---------------- OTHER FLOW ----------------
            else:
                log.total_tokens = log.classification_tokens or 0
                log.save()

            log.status = "PROCESSED"
            log.save()
            if result["type"] == "ESCALATION":
                send_escalation_alert.apply_async(args=[log.id], countdown=PRIORITY_HIGH_MINUTES * 60)
            if mark_read:
                gmail.mark_as_read(message_id)

        except Exception:
            logger.exception("Failed processing email %s (subject: %s)", message_id, log.subject)
            log.status = "FAILED"
            log.save()


@shared_task
def send_escalation_alert(email_log_id):
    """Fires exactly 60 minutes after an email is received. Sends HIGH priority Teams alert if still unattended."""
    try:
        log = EmailLog.objects.get(id=email_log_id)
    except EmailLog.DoesNotExist:
        return

    classification = log.classification

    if classification == "COA":
        if COARecord.objects.filter(email=log, status="COMPLETED").exists():
            return
    elif classification == "ORDER":
        if OrderTrackingRecord.objects.filter(email=log, status="RESOLVED").exists():
            return
    if EscalationRecord.objects.filter(email=log).exists():
        return

    # Skip if a reply was received in the same thread
    if log.thread_id and ReplyEmail.objects.filter(thread_id=log.thread_id).exists():
        return

    reason = f"Email unattended for 60 minutes (type: {classification or 'UNKNOWN'})"
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
    """
    Watchdog — runs every 15 minutes.
    Sends a single HIGH priority Teams alert for any email unattended for 60+ minutes.
    """
    now = timezone.now()

    for log in EmailLog.objects.filter(status="PROCESSED", classification="ESCALATION"):
        elapsed_minutes = (now - log.received_at).total_seconds() / 60

        if elapsed_minutes < PRIORITY_HIGH_MINUTES:
            continue

        # Only alert once per email
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
        sent, err = send_teams_alert(
            alert_payload,
            reason=reason,
            priority="HIGH",
        )
        record.teams_sent = sent
        record.teams_error = "" if sent else err
        record.save(update_fields=["teams_sent", "teams_error"])

        logger.info(
            "Teams alert sent: email id=%s priority=HIGH elapsed=%.1fmin sender=%s",
            log.id, elapsed_minutes, log.sender,
        )


