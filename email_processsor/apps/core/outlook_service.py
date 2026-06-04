import logging
import requests
import os

GRAPH_URL = "https://graph.microsoft.com/v1.0"
MAILBOX = os.getenv("MAILBOX")

logger = logging.getLogger(__name__)


def get_access_token():
    tenant_id = os.getenv("TENANT_ID")
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    try:
        res = requests.post(url, data={
            "grant_type": "client_credentials",
            "client_id": os.getenv("CLIENT_ID"),
            "client_secret": os.getenv("CLIENT_SECRET"),
            "scope": "https://graph.microsoft.com/.default",
        }, timeout=15)
        res.raise_for_status()
    except requests.RequestException as exc:
        logger.error("Outlook OAuth token request failed: %s", exc)
        raise
    return res.json()["access_token"]


class OutlookService:

    def __init__(self, token):
        self.token = token

    def headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def fetch_unread_emails(self):
        url = (
            f"{GRAPH_URL}/users/{MAILBOX}/mailFolders/Inbox/messages"
            "?$filter=isRead eq false"
            "&$orderby=receivedDateTime asc"
            "&$top=50"
            "&$select=id,subject,from,body,conversationId,internetMessageId,internetMessageHeaders,receivedDateTime"
        )
        messages = []
        while url:
            try:
                res = requests.get(url, headers=self.headers(), timeout=30)
                res.raise_for_status()
            except requests.RequestException as exc:
                logger.error("Failed to fetch emails from Graph API: %s", exc)
                break
            data = res.json()
            messages.extend(data.get("value", []))
            url = data.get("@odata.nextLink")
        return [self._normalize(m) for m in messages]

    def _normalize(self, message):
        raw_headers = message.get("internetMessageHeaders") or []
        header_map = {h["name"].lower(): h["value"] for h in raw_headers}
        rfc_message_id = (message.get("internetMessageId") or "").strip()
        in_reply_to = (header_map.get("in-reply-to") or "").strip()
        return {
            "id": message.get("id"),
            "subject": (message.get("subject") or "").strip(),
            "from": message.get("from", {}),
            "body": message.get("body", {}),
            "thread_id": message.get("conversationId"),
            "rfc_message_id": rfc_message_id or None,
            "in_reply_to": in_reply_to or None,
            "headers": header_map,
            "received_at": message.get("receivedDateTime"),
        }

    def mark_as_read(self, message_id):
        url = f"{GRAPH_URL}/users/{MAILBOX}/messages/{message_id}"
        try:
            res = requests.patch(url, headers=self.headers(), json={"isRead": True}, timeout=10)
            res.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Failed to mark message %s as read: %s", message_id, exc)



    # def send_email(self, to_address, subject, body):
    #     url = f"{GRAPH_URL}/users/{MAILBOX}/sendMail"
    #     payload = {
    #         "message": {
    #             "subject": subject,
    #             "body": {
    #                 "contentType": "Text",
    #                 "content": body
    #             },
    #             "toRecipients": [
    #                 {"emailAddress": {"address": to_address}}
    #             ]
    #         }
    #     }
    #     res = requests.post(url, headers=self.headers(), json=payload)
    #     res.raise_for_status()
