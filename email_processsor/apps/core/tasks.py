from celery import shared_task
from django.utils import timezone

from .models import EmailLog, COARecord, EscalationRecord
# from .outlook_service import OutlookService  # switch back when using Microsoft 365
from .gmail_service import GmailService
from apps.classifier.ai_classifier import classify_email
from apps.coa.extractor import extract_coa_data
from apps.coa.pdf_generator import generate_pdf
from apps.coa.azure_storage import upload_to_azure
from apps.escalation.teams_notifier import send_teams_alert


import os
import msal


@shared_task
def check_and_process_emails():

    # outlook = OutlookService(token=get_token())  # switch back when using Microsoft 365
    gmail = GmailService()

    emails = gmail.fetch_unread_emails()

    for email in emails:

        message_id = email["id"]

        # ✅ Prevent re-processing
        if EmailLog.objects.filter(message_id=message_id).exists():
            continue

        body = email["body"]["content"]

        log = EmailLog.objects.create(
            message_id=message_id,
            subject=email["subject"],
            sender=email["from"]["emailAddress"]["address"],
            body=body,
            received_at=timezone.now()
        )

        # 🤖 Classify
        result = classify_email(body)
        log.classification = result["type"]
        log.save()

        # ---------------- COA FLOW ----------------
        if result["type"] == "COA":

            data = extract_coa_data(body)

            coa = COARecord.objects.create(
                email=log,
                company=data.get("company"),
                address=data.get("address"),
                contact_phone=data.get("contact_phone"),
                contact_email=data.get("contact_email"),
                product_name=data.get("product_name"),
                part_number=data.get("part_number"),
                lot_number=data.get("lot_number"),
                lot_quantity=data.get("lot_quantity"),
                manufacture_date=data.get("manufacture_date"),
                expiration_date=data.get("expiration_date"),
                report_date=data.get("report_date"),
                approved_by=data.get("approved_by"),
                test_results=data.get("test_results"),
            )

            pdf_path = generate_pdf(data)
            url = upload_to_azure(pdf_path)

            coa.pdf_url = url
            coa.status = "COMPLETED"
            coa.save()

        # ---------------- ESCALATION FLOW ----------------
        elif result["type"] == "ESCALATION":

            escalation = EscalationRecord.objects.create(
                email=log,
                reason=result["reason"]
            )

            send_teams_alert(email, reason=result["reason"])
            escalation.teams_sent = True
            escalation.save()
        
        # mark processed
        log.status = "PROCESSED"
        log.save()

        # outlook.mark_as_read(message_id)  # switch back when using Microsoft 365
        gmail.mark_as_read(message_id)


def get_token():
    app = msal.ConfidentialClientApplication(
        client_id=os.getenv("CLIENT_ID"),
        client_credential=os.getenv("CLIENT_SECRET"),
        authority=f"https://login.microsoftonline.com/{os.getenv('TENANT_ID')}"
    )
    result = app.acquire_token_for_client(
        scopes=["https://graph.microsoft.com/.default"]
    )
    if "access_token" not in result:
        raise ValueError(f"MSAL token error: {result.get('error')} - {result.get('error_description')}")
    return result["access_token"]