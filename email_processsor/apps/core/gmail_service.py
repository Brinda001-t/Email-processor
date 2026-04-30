import imaplib
import email as email_lib
from email.header import decode_header
import os


class GmailService:

    def __init__(self):
        self.mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        self.mail.login(os.getenv("GMAIL_EMAIL"), os.getenv("GMAIL_APP_PASSWORD"))
        self.mail.select("inbox")

    def _decode_str(self, value):
        if not value:
            return ""
        decoded, charset = decode_header(value)[0]
        if isinstance(decoded, bytes):
            return decoded.decode(charset or "utf-8", errors="ignore")
        return decoded

    def fetch_unread_emails(self):
        _, uids = self.mail.uid("search", None, "UNSEEN")
        if not uids[0]:
            return []

        emails = []
        for uid in uids[0].split():
            _, msg_data = self.mail.uid("fetch", uid, "(RFC822)")
            raw = msg_data[0][1]
            msg = email_lib.message_from_bytes(raw)

            subject = self._decode_str(msg.get("Subject", ""))
            sender = msg.get("From", "")

            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                        break
            else:
                body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

            emails.append({
                "id": uid.decode(),
                "subject": subject,
                "from": {"emailAddress": {"address": sender}},
                "body": {"content": body},
            })

        return emails

    def mark_as_read(self, uid):
        self.mail.uid("store", uid.encode(), "+FLAGS", "\\Seen")
