import imaplib
import email as email_lib
from email.header import decode_header
from email.utils import parseaddr
from html.parser import HTMLParser
import os
import re


class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
    def handle_data(self, data):
        self.text.append(data)
    def get_text(self):
        return " ".join(self.text)


def _strip_html(html):
    stripper = _HTMLStripper()
    stripper.feed(html)
    return stripper.get_text()


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
            _, msg_data = self.mail.uid("fetch", uid, "(X-GM-THRID RFC822)")
            header_part = msg_data[0][0]
            thread_match = re.search(rb'X-GM-THRID\s+(\d+)', header_part)
            thread_id = thread_match.group(1).decode() if thread_match else None

            raw = msg_data[0][1]
            msg = email_lib.message_from_bytes(raw)

            subject = self._decode_str(msg.get("Subject", ""))

            # Bug 1 fix: extract clean email address from "Name <email>" format
            raw_from = msg.get("From", "")
            _, sender = parseaddr(raw_from)
            if not sender:
                sender = raw_from

            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                        break
                if not body:
                    for part in msg.walk():
                        if part.get_content_type() == "text/html":
                            html = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                            body = _strip_html(html)
                            break
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    body = payload.decode("utf-8", errors="ignore")
                    if msg.get_content_type() == "text/html":
                        body = _strip_html(body)

            headers = {}
            for h in ("List-Unsubscribe", "Precedence", "X-Mailer", "X-Campaign-Id"):
                val = msg.get(h)
                if val:
                    headers[h.lower()] = val

            rfc_message_id = (msg.get("Message-ID") or "").strip()
            in_reply_to = (msg.get("In-Reply-To") or "").strip()

            emails.append({
                "id": uid.decode(),
                "subject": subject,
                "from": {"emailAddress": {"address": sender}},
                "body": {"content": body},
                "headers": headers,
                "rfc_message_id": rfc_message_id or None,
                "in_reply_to": in_reply_to or None,
                "thread_id": thread_id,
            })

        return emails

    def mark_as_read(self, uid):
        self.mail.uid("store", uid.encode(), "+FLAGS", "\\Seen")

    def send_email(self, to_address, subject, body):
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart()
        msg["From"] = os.getenv("GMAIL_EMAIL")
        msg["To"] = to_address
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(os.getenv("GMAIL_EMAIL"), os.getenv("GMAIL_APP_PASSWORD"))
            server.send_message(msg)
