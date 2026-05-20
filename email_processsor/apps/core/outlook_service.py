import requests
import os

GRAPH_URL = "https://graph.microsoft.com/v1.0"
MAILBOX = os.getenv("MAILBOX")


def get_access_token():
    tenant_id = os.getenv("TENANT_ID")
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    res = requests.post(url, data={
        "grant_type": "client_credentials",
        "client_id": os.getenv("CLIENT_ID"),
        "client_secret": os.getenv("CLIENT_SECRET"),
        "scope": "https://graph.microsoft.com/.default",
    })
    res.raise_for_status()
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
            "&$select=id,subject,from,body,conversationId,internetMessageId,internetMessageHeaders"
        )
        res = requests.get(url, headers=self.headers())
        if not res.text:
            return []
        messages = res.json().get("value", [])
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
        }

    def mark_as_read(self, message_id):
        url = f"{GRAPH_URL}/users/{MAILBOX}/messages/{message_id}"
        requests.patch(
            url,
            headers=self.headers(),
            json={"isRead": True}
        )



    def send_email(self, to_address, subject, body):
        url = f"{GRAPH_URL}/users/{MAILBOX}/sendMail"
        payload = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "Text",
                    "content": body
                },
                "toRecipients": [
                    {"emailAddress": {"address": to_address}}
                ]
            }
        }
        res = requests.post(url, headers=self.headers(), json=payload)
        res.raise_for_status()
