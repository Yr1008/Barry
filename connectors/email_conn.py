"""
Email Connector — Gmail / IMAP.

Fetches unread emails and important messages.
Can also send replies.
"""
from __future__ import annotations

import asyncio
import email
import imaplib
import re
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from .base import BaseConnector, ConnectorResult


class EmailConnector(BaseConnector):
    name = "email"

    def __init__(self, config):
        self.config = config

    def is_available(self) -> bool:
        return self.config.has_email

    async def fetch(self) -> ConnectorResult:
        """Fetch unread emails."""
        loop = asyncio.get_event_loop()
        try:
            emails = await loop.run_in_executor(None, self._fetch_emails_sync)
            return ConnectorResult(
                source=self.name,
                data_type="email",
                items=emails,
            )
        except Exception as e:
            return ConnectorResult(source=self.name, data_type="email", error=str(e))

    def _fetch_emails_sync(self) -> list[dict]:
        """Synchronous IMAP email fetch."""
        emails = []

        with imaplib.IMAP4_SSL(self.config.imap_server, self.config.imap_port) as imap:
            imap.login(self.config.email_address, self.config.email_password)
            imap.select("INBOX")

            # Search for unread emails in last 7 days
            since_date = (datetime.now() - timedelta(days=7)).strftime("%d-%b-%Y")
            _, message_numbers = imap.search(None, f'(UNSEEN SINCE {since_date})')

            if not message_numbers[0]:
                return []

            ids = message_numbers[0].split()
            # Get most recent N emails
            recent_ids = ids[-self.config.email_scan_count:]

            for num in reversed(recent_ids):
                try:
                    _, data = imap.fetch(num, "(RFC822)")
                    raw = data[0][1]
                    msg = email.message_from_bytes(raw)

                    subject = self._decode_header(msg.get("Subject", ""))
                    sender = self._decode_header(msg.get("From", ""))
                    date_str = msg.get("Date", "")
                    body = self._get_body(msg)

                    emails.append({
                        "id": num.decode(),
                        "subject": subject,
                        "from": sender,
                        "date": date_str,
                        "body": body[:2000],  # Truncate long bodies
                        "source": "email",
                        "unread": True,
                    })
                except Exception:
                    continue

        return emails

    def _decode_header(self, value: str) -> str:
        """Decode email header value."""
        if not value:
            return ""
        try:
            parts = email.header.decode_header(value)
            decoded = []
            for part, charset in parts:
                if isinstance(part, bytes):
                    decoded.append(part.decode(charset or "utf-8", errors="replace"))
                else:
                    decoded.append(part)
            return " ".join(decoded)
        except Exception:
            return value

    def _get_body(self, msg: email.message.Message) -> str:
        """Extract plain text body from email."""
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                disposition = str(part.get("Content-Disposition", ""))
                if ctype == "text/plain" and "attachment" not in disposition:
                    try:
                        charset = part.get_content_charset() or "utf-8"
                        return part.get_payload(decode=True).decode(charset, errors="replace")
                    except Exception:
                        pass
        else:
            try:
                charset = msg.get_content_charset() or "utf-8"
                return msg.get_payload(decode=True).decode(charset, errors="replace")
            except Exception:
                pass
        return ""

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        reply_to_id: str | None = None,
    ) -> bool:
        """Send an email."""
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None, self._send_email_sync, to, subject, body
            )
            return True
        except Exception as e:
            print(f"[EmailConnector] Send failed: {e}")
            return False

    def _send_email_sync(self, to: str, subject: str, body: str) -> None:
        """Synchronous email send."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.config.email_address
        msg["To"] = to
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port) as smtp:
            smtp.starttls()
            smtp.login(self.config.email_address, self.config.email_password)
            smtp.send_message(msg)

    def format_email_summary(self, emails: list[dict]) -> str:
        """Format emails into a readable summary."""
        if not emails:
            return "No unread emails."

        lines = [f"📧 **{len(emails)} unread emails:**"]
        for e in emails[:10]:
            sender = e.get("from", "Unknown")
            # Extract just the name/email part
            match = re.search(r'"?([^"<]+)"?\s*<?([^>]*)>?', sender)
            if match:
                name = match.group(1).strip() or match.group(2).strip()
            else:
                name = sender[:40]

            subject = e.get("subject", "(no subject)")[:60]
            lines.append(f"  • **{name}**: {subject}")

        if len(emails) > 10:
            lines.append(f"  ... and {len(emails) - 10} more")

        return "\n".join(lines)
