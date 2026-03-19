"""
Calendar Connector — Google Calendar + Apple iCloud Calendar.

Fetches upcoming events from:
1. Google Calendar (via Google API)
2. Apple iCloud Calendar (via CalDAV)
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta
from typing import Any

from .base import BaseConnector, ConnectorResult


class CalendarConnector(BaseConnector):
    name = "calendar"

    def __init__(self, config):
        self.config = config

    def is_available(self) -> bool:
        return self.config.has_google or self.config.has_icloud

    async def fetch(self) -> ConnectorResult:
        events = []
        errors = []

        if self.config.has_google:
            try:
                google_events = await self._fetch_google_calendar()
                events.extend(google_events)
            except Exception as e:
                errors.append(f"Google Calendar: {e}")

        if self.config.has_icloud:
            try:
                icloud_events = await self._fetch_icloud_calendar()
                events.extend(icloud_events)
            except Exception as e:
                errors.append(f"iCloud Calendar: {e}")

        # Sort by start time
        events.sort(key=lambda e: e.get("start", ""))

        return ConnectorResult(
            source=self.name,
            data_type="event",
            items=events,
            error="; ".join(errors) if errors and not events else None,
        )

    async def _fetch_google_calendar(self) -> list[dict]:
        """Fetch events from Google Calendar API."""
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
            import asyncio

            creds = None
            token_path = self.config.google_token_path

            if token_path.exists():
                creds = Credentials.from_authorized_user_file(str(token_path))

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    with open(token_path, "w") as f:
                        f.write(creds.to_json())
                else:
                    return []  # Need OAuth flow — handled by API server

            service = build("calendar", "v3", credentials=creds)

            now = datetime.utcnow().isoformat() + "Z"
            end = (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z"

            result = service.events().list(
                calendarId="primary",
                timeMin=now,
                timeMax=end,
                maxResults=20,
                singleEvents=True,
                orderBy="startTime",
            ).execute()

            items = result.get("items", [])
            events = []
            for item in items:
                start = item["start"].get("dateTime", item["start"].get("date", ""))
                events.append({
                    "id": item["id"],
                    "title": item.get("summary", "Untitled"),
                    "start": start,
                    "end": item["end"].get("dateTime", item["end"].get("date", "")),
                    "location": item.get("location", ""),
                    "description": item.get("description", ""),
                    "attendees": [a.get("email") for a in item.get("attendees", [])],
                    "source": "google",
                    "url": item.get("htmlLink", ""),
                })
            return events

        except ImportError:
            return []

    async def _fetch_icloud_calendar(self) -> list[dict]:
        """Fetch events from Apple iCloud Calendar via CalDAV."""
        try:
            import caldav
            from datetime import timezone

            client = caldav.DAVClient(
                url="https://caldav.icloud.com",
                username=self.config.icloud_email,
                password=self.config.icloud_password,
            )
            principal = client.principal()
            calendars = principal.calendars()

            now = datetime.now(timezone.utc)
            end = now + timedelta(days=7)
            events = []

            for cal in calendars:
                try:
                    cal_events = cal.date_search(start=now, end=end, expand=True)
                    for event in cal_events:
                        try:
                            comp = event.icalendar_component
                            dtstart = comp.get("DTSTART")
                            dtend = comp.get("DTEND")
                            events.append({
                                "id": str(comp.get("UID", "")),
                                "title": str(comp.get("SUMMARY", "Untitled")),
                                "start": dtstart.dt.isoformat() if dtstart else "",
                                "end": dtend.dt.isoformat() if dtend else "",
                                "location": str(comp.get("LOCATION", "")),
                                "description": str(comp.get("DESCRIPTION", "")),
                                "source": "icloud",
                            })
                        except Exception:
                            pass
                except Exception:
                    pass

            return events

        except ImportError:
            return []

    def format_for_briefing(self, events: list[dict], owner_tz: str) -> str:
        """Format events into a human-readable briefing section."""
        if not events:
            return "No upcoming events in the next 7 days."

        import pytz
        from datetime import timezone

        tz = pytz.timezone(owner_tz)
        lines = []
        today = datetime.now(tz).date()

        # Group by day
        by_day: dict[str, list[dict]] = {}
        for event in events:
            start_str = event.get("start", "")
            try:
                if "T" in start_str:
                    dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                    dt_local = dt.astimezone(tz)
                    day = dt_local.strftime("%A, %B %d")
                    time_str = dt_local.strftime("%I:%M %p")
                else:
                    dt_local = datetime.strptime(start_str, "%Y-%m-%d")
                    day = dt_local.strftime("%A, %B %d")
                    time_str = "All day"
            except Exception:
                day = start_str[:10]
                time_str = ""

            by_day.setdefault(day, []).append({**event, "_time": time_str})

        for day, day_events in by_day.items():
            lines.append(f"\n📅 **{day}**")
            for e in day_events:
                title = e.get("title", "Untitled")
                time = e.get("_time", "")
                loc = e.get("location", "")
                loc_str = f" @ {loc}" if loc else ""
                source = e.get("source", "")
                lines.append(f"  • {time} — {title}{loc_str} [{source}]")

        return "\n".join(lines)
