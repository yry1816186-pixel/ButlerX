from __future__ import annotations

import imaplib
import smtplib
from email import message_from_bytes
from email.header import decode_header
from email.message import EmailMessage
from typing import Any, Dict, List, Optional


def _decode_header_value(value: str) -> str:
    parts = decode_header(value)
    decoded = []
    for part, encoding in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(encoding or "utf-8", errors="ignore"))
        else:
            decoded.append(str(part))
    return "".join(decoded)


def _extract_text(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                try:
                    return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8")
                except Exception:
                    continue
    else:
        try:
            return msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8")
        except Exception:
            return ""
    return ""


class EmailClient:
    def __init__(
        self,
        imap_host: str,
        imap_port: int,
        imap_ssl: bool,
        smtp_host: str,
        smtp_port: int,
        smtp_ssl: bool,
        smtp_starttls: bool,
        username: str,
        password: str,
        default_from: str,
    ) -> None:
        self.imap_host = imap_host
        self.imap_port = int(imap_port)
        self.imap_ssl = bool(imap_ssl)
        self.smtp_host = smtp_host
        self.smtp_port = int(smtp_port)
        self.smtp_ssl = bool(smtp_ssl)
        self.smtp_starttls = bool(smtp_starttls)
        self.username = username
        self.password = password
        self.default_from = default_from

    def read_latest(self, limit: int = 5, folder: str = "INBOX", unread_only: bool = False) -> Dict[str, Any]:
        if not self.imap_host or not self.username or not self.password:
            return {"error": "imap_not_configured"}
        limit = max(int(limit), 1)
        try:
            if self.imap_ssl:
                client = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
            else:
                client = imaplib.IMAP4(self.imap_host, self.imap_port)
            client.login(self.username, self.password)
            client.select(folder)
            search_flag = "UNSEEN" if unread_only else "ALL"
            status, data = client.search(None, search_flag)
            if status != "OK":
                return {"error": "imap_search_failed"}
            ids = data[0].split()
            ids = ids[-limit:]
            messages: List[Dict[str, Any]] = []
            for msg_id in reversed(ids):
                status, msg_data = client.fetch(msg_id, "(RFC822)")
                if status != "OK":
                    continue
                msg = message_from_bytes(msg_data[0][1])
                subject = _decode_header_value(msg.get("Subject", ""))
                sender = _decode_header_value(msg.get("From", ""))
                date = _decode_header_value(msg.get("Date", ""))
                body = _extract_text(msg)
                messages.append(
                    {
                        "subject": subject,
                        "from": sender,
                        "date": date,
                        "snippet": body[:300],
                    }
                )
            client.logout()
            return {"messages": messages}
        except Exception as exc:
            return {"error": str(exc)}

    def send(self, to_addrs: List[str], subject: str, body: str, from_addr: Optional[str] = None) -> Dict[str, Any]:
        if not self.smtp_host or not self.username or not self.password:
            return {"error": "smtp_not_configured"}
        if not to_addrs:
            return {"error": "missing_recipient"}
        from_addr = from_addr or self.default_from or self.username

        msg = EmailMessage()
        msg["From"] = from_addr
        msg["To"] = ", ".join(to_addrs)
        msg["Subject"] = subject
        msg.set_content(body)

        try:
            if self.smtp_ssl:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            server.ehlo()
            if self.smtp_starttls and not self.smtp_ssl:
                server.starttls()
                server.ehlo()
            server.login(self.username, self.password)
            server.send_message(msg)
            server.quit()
            return {"status": "sent"}
        except Exception as exc:
            return {"error": str(exc)}
