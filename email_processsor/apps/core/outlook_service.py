import requests
import os

GRAPH_URL = "https://graph.microsoft.com/v1.0"
MAILBOX = os.getenv("MAILBOX")


class OutlookService:

    def __init__(self, token):
        self.token = token

    def headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def fetch_unread_emails(self):
        url = f"{GRAPH_URL}/users/{MAILBOX}/mailFolders/Inbox/messages?$filter=isRead eq false"
        res = requests.get(url, headers=self.headers())
        print("GRAPH API RESPONSE:", res.status_code, res.text)
        if not res.text:
            return []
        return res.json().get("value", [])

    def mark_as_read(self, message_id):
        url = f"{GRAPH_URL}/users/{MAILBOX}/messages/{message_id}"
        requests.patch(
            url,
            headers=self.headers(),
            json={"isRead": True}
        )