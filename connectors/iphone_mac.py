"""
iPhone / Mac Connector.

Receives data pushed from:
1. Apple Shortcuts (automations on iPhone/Mac)
2. iCloud Reminders (via CalDAV)
3. Apple Notes (via Shortcuts webhook)

Setup instructions for Apple Shortcuts are in README.md.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

from .base import BaseConnector, ConnectorResult


class iPhoneMacConnector(BaseConnector):
    name = "iphone_mac"

    def __init__(self, config):
        self.config = config
        # Buffer for data pushed via Shortcuts webhooks
        self._shortcuts_data: list[dict] = []
        self._reminders: list[dict] = []
        self._notes: list[dict] = []
        self._location: dict | None = None
        self._battery: dict | None = None
        self._focus_mode: str | None = None

    def is_available(self) -> bool:
        return True  # Always available (collects via webhook)

    def receive_shortcut_data(self, payload: dict) -> None:
        """
        Called when Apple Shortcuts sends data to Barry's webhook.
        Payload types: reminder, note, location, battery, focus_mode, screenshot, clipboard
        """
        data_type = payload.get("type", "unknown")
        timestamp = payload.get("timestamp", datetime.now().isoformat())

        if data_type == "reminder":
            self._reminders.append({
                "id": payload.get("id", f"reminder_{timestamp}"),
                "title": payload.get("title", ""),
                "due_date": payload.get("due_date"),
                "list": payload.get("list", "Reminders"),
                "completed": payload.get("completed", False),
                "timestamp": timestamp,
                "source": "iphone_reminders",
            })
        elif data_type == "note":
            self._notes.append({
                "id": payload.get("id", f"note_{timestamp}"),
                "title": payload.get("title", ""),
                "body": payload.get("body", ""),
                "folder": payload.get("folder", "Notes"),
                "timestamp": timestamp,
                "source": "iphone_notes",
            })
        elif data_type == "location":
            self._location = {
                "latitude": payload.get("latitude"),
                "longitude": payload.get("longitude"),
                "address": payload.get("address", ""),
                "timestamp": timestamp,
            }
        elif data_type == "battery":
            self._battery = {
                "level": payload.get("level"),
                "charging": payload.get("charging", False),
                "timestamp": timestamp,
            }
        elif data_type == "focus_mode":
            self._focus_mode = payload.get("mode", "None")
        else:
            self._shortcuts_data.append({**payload, "timestamp": timestamp})

    async def fetch(self) -> ConnectorResult:
        """Fetch all data received from iPhone/Mac."""
        items = []

        # Include reminders
        for r in self._reminders:
            if not r.get("completed"):
                items.append({**r, "data_type": "reminder"})

        # Include notes (recent only)
        for n in self._notes[-20:]:
            items.append({**n, "data_type": "note"})

        # Include other shortcuts data
        for d in self._shortcuts_data[-10:]:
            items.append({**d, "data_type": "shortcuts"})

        return ConnectorResult(
            source=self.name,
            data_type="mixed",
            items=items,
        )

    async def fetch_icloud_reminders(self) -> list[dict]:
        """Fetch reminders from iCloud via CalDAV."""
        if not self.config.has_icloud:
            return []

        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(None, self._fetch_reminders_sync)
        except Exception as e:
            print(f"[iPhoneMac] Reminders fetch failed: {e}")
            return []

    def _fetch_reminders_sync(self) -> list[dict]:
        try:
            import caldav
            from datetime import timezone

            # iCloud reminders live in the Reminders CalDAV endpoint
            client = caldav.DAVClient(
                url="https://reminders.caldav.icloud.com/reminders/",
                username=self.config.icloud_email,
                password=self.config.icloud_password,
            )
            principal = client.principal()
            calendars = principal.calendars()

            reminders = []
            for cal in calendars:
                try:
                    todos = cal.todos()
                    for todo in todos:
                        comp = todo.icalendar_component
                        status = str(comp.get("STATUS", "NEEDS-ACTION"))
                        if status in ("COMPLETED", "CANCELLED"):
                            continue
                        due = comp.get("DUE")
                        reminders.append({
                            "id": str(comp.get("UID", "")),
                            "title": str(comp.get("SUMMARY", "")),
                            "due_date": due.dt.isoformat() if due else None,
                            "list": str(cal.name or "Reminders"),
                            "source": "icloud_reminders",
                            "completed": False,
                        })
                except Exception:
                    continue

            return reminders
        except ImportError:
            return []

    def get_status(self) -> dict:
        """Get current iPhone/Mac status."""
        return {
            "battery": self._battery,
            "focus_mode": self._focus_mode,
            "location": self._location,
            "reminder_count": len([r for r in self._reminders if not r.get("completed")]),
            "note_count": len(self._notes),
        }

    def format_for_briefing(self) -> str:
        """Format iPhone data for daily briefing."""
        lines = []

        if self._battery:
            level = self._battery.get("level", "?")
            charging = "🔌" if self._battery.get("charging") else "🔋"
            lines.append(f"{charging} iPhone battery: {level}%")

        if self._focus_mode and self._focus_mode != "None":
            lines.append(f"🎯 Focus mode: {self._focus_mode}")

        active_reminders = [r for r in self._reminders if not r.get("completed")]
        if active_reminders:
            lines.append(f"\n⏰ **{len(active_reminders)} Reminder(s):**")
            for r in active_reminders[:5]:
                due = r.get("due_date", "")
                due_str = f" (due {due[:10]})" if due else ""
                lines.append(f"  • {r.get('title', 'Untitled')}{due_str}")

        return "\n".join(lines) if lines else ""

    def get_shortcuts_setup_guide(self) -> str:
        """Return Apple Shortcuts setup instructions."""
        return SHORTCUTS_SETUP_GUIDE.format(
            port=self.config.shortcuts_webhook_port,
            secret=self.config.shortcuts_webhook_secret,
        )


SHORTCUTS_SETUP_GUIDE = """
# Apple Shortcuts Setup for Barry

Barry can receive data from your iPhone and Mac through Apple Shortcuts automations.

## Barry's Webhook URL
http://YOUR_MAC_IP:{port}/iphone/shortcut
Secret: {secret}

## Shortcut 1: Send Reminders to Barry (runs hourly)
1. Open Shortcuts app
2. New Shortcut → Add Action
3. "Find Reminders" (filter: incomplete, sort by due date)
4. "Get Details of Reminders" → Title, Due Date, List
5. "Make Dictionary" with keys: type="reminder", title, due_date, list
6. "Get Contents of URL":
   - URL: http://YOUR_MAC_IP:{port}/iphone/shortcut
   - Method: POST
   - Headers: X-Barry-Secret = {secret}
   - Body: Dictionary above
7. Set Automation → Every 1 hour

## Shortcut 2: Morning Status (runs at 7 AM)
1. "Get Battery Level" → Add to dict
2. "Get Focus" → Add to dict
3. POST to Barry with type="status"

## Shortcut 3: New Note → Barry
1. Trigger: "When I create a Note"
2. "Get Details of Note" → title, body
3. POST to Barry with type="note"

## Shortcut 4: Ask Barry (via Siri)
1. New Shortcut named "Ask Barry"
2. "Ask for Input" → Your question
3. POST to Barry: /chat endpoint with the question
4. "Show Result" → Barry's response
5. Use: "Hey Siri, Ask Barry [question]"
"""
