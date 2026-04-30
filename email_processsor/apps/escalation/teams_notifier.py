import requests
import os


def send_teams_alert(email, reason=""):

    webhook = os.getenv("TEAMS_WEBHOOK_URL")

    sender = email.get("from", {}).get("emailAddress", {}).get("address", "Unknown")
    body = email.get("body", {}).get("content", "")
    body_preview = body[:500] + "..." if len(body) > 500 else body

    payload = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": "FF0000",
        "summary": "Escalation Email Received",
        "sections": [
            {
                "activityTitle": "🚨 ESCALATION EMAIL RECEIVED",
                "activitySubtitle": "Please revert as soon as possible.",
                "facts": [
                    {"name": "Subject", "value": email.get("subject", "")},
                    {"name": "From",    "value": sender},
                    {"name": "Reason",  "value": reason},
                ],
                "markdown": True
            },
            {
                "title": "Email Body",
                "text": body_preview,
                "markdown": True
            }
        ]
    }

    requests.post(webhook, json=payload)