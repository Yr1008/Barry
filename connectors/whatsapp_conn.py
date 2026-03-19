"""
WhatsApp Connector — via Twilio WhatsApp API.

Can receive incoming WhatsApp messages (via webhook)
and send replies.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from .base import BaseConnector, ConnectorResult


class WhatsAppConnector(BaseConnector):
    name = "whatsapp"

    def __init__(self, config):
        self.config = config
        self._inbox: list[dict] = []  # Messages received via webhook

    def is_available(self) -> bool:
        return self.config.has_whatsapp

    def receive_message(self, from_number: str, body: str, timestamp: str | None = None) -> None:
        """Called when a WhatsApp message comes in via Twilio webhook."""
        self._inbox.append({
            "id": f"wa_{datetime.now().timestamp()}",
            "from": from_number,
            "body": body,
            "timestamp": timestamp or datetime.now().isoformat(),
            "source": "whatsapp",
            "read": False,
        })

    async def fetch(self) -> ConnectorResult:
        """Return unread WhatsApp messages from inbox."""
        unread = [m for m in self._inbox if not m.get("read")]
        # Mark as read
        for m in unread:
            m["read"] = True
        return ConnectorResult(
            source=self.name,
            data_type="message",
            items=unread,
        )

    async def send_message(self, to: str, body: str) -> bool:
        """Send a WhatsApp message via Twilio."""
        if not self.is_available():
            return False

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, self._send_sync, to, body)
            return True
        except Exception as e:
            print(f"[WhatsApp] Send failed: {e}")
            return False

    def _send_sync(self, to: str, body: str) -> None:
        from twilio.rest import Client
        client = Client(self.config.twilio_account_sid, self.config.twilio_auth_token)

        # Ensure numbers have whatsapp: prefix
        from_num = self.config.twilio_whatsapp_number
        if not from_num.startswith("whatsapp:"):
            from_num = f"whatsapp:{from_num}"
        if not to.startswith("whatsapp:"):
            to = f"whatsapp:{to}"

        client.messages.create(body=body, from_=from_num, to=to)

    async def send_to_self(self, body: str) -> bool:
        """Send a notification to the owner's WhatsApp."""
        if not self.config.my_whatsapp_number:
            return False
        return await self.send_message(self.config.my_whatsapp_number, body)

    def format_messages(self, messages: list[dict]) -> str:
        """Format WhatsApp messages for briefing."""
        if not messages:
            return ""
        lines = [f"💬 **{len(messages)} WhatsApp message(s):**"]
        for m in messages[:10]:
            sender = m.get("from", "Unknown").replace("whatsapp:", "")
            body = m.get("body", "")[:100]
            lines.append(f"  • **{sender}**: {body}")
        return "\n".join(lines)
