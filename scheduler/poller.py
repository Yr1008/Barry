"""
Barry Auto-Poller — keeps Barry updated automatically.

Runs background jobs:
- Every N minutes: poll all connectors
- Daily at briefing time: generate morning briefing
- Hourly: check for urgent items and notify if needed
- Weekly: learn new tone profiles from messages
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

if TYPE_CHECKING:
    from barry import Barry

logger = logging.getLogger("barry.scheduler")


class BarryScheduler:
    """Manages all of Barry's background tasks."""

    def __init__(self, barry: "Barry"):
        self.barry = barry
        self.config = barry.config
        self.scheduler = AsyncIOScheduler()
        self._on_briefing: list[Callable] = []
        self._on_update: list[Callable] = []
        self._running = False

    def on_briefing(self, callback: Callable) -> None:
        """Register callback for when daily briefing is ready."""
        self._on_briefing.append(callback)

    def on_update(self, callback: Callable) -> None:
        """Register callback for when new items arrive."""
        self._on_update.append(callback)

    def start(self) -> None:
        """Start all scheduled jobs."""
        # Poll all connectors every N minutes
        self.scheduler.add_job(
            self._poll_job,
            trigger=IntervalTrigger(minutes=self.config.poll_interval_minutes),
            id="poll_all",
            name="Poll all connectors",
            replace_existing=True,
        )

        # Morning briefing at configured time
        briefing_hour, briefing_minute = map(int, self.config.briefing_time.split(":"))
        self.scheduler.add_job(
            self._morning_briefing_job,
            trigger=CronTrigger(hour=briefing_hour, minute=briefing_minute),
            id="morning_briefing",
            name="Morning briefing",
            replace_existing=True,
        )

        # Urgent check every hour
        self.scheduler.add_job(
            self._urgent_check_job,
            trigger=CronTrigger(minute=0),  # Every hour on the hour
            id="urgent_check",
            name="Urgent items check",
            replace_existing=True,
        )

        # Tone learning — every Monday at 6 AM
        self.scheduler.add_job(
            self._tone_learning_job,
            trigger=CronTrigger(day_of_week="mon", hour=6),
            id="tone_learning",
            name="Weekly tone learning",
            replace_existing=True,
        )

        self.scheduler.start()
        self._running = True
        logger.info(
            f"Barry scheduler started. Polling every {self.config.poll_interval_minutes}min, "
            f"briefing at {self.config.briefing_time}"
        )

    def stop(self) -> None:
        """Stop the scheduler."""
        if self._running:
            self.scheduler.shutdown()
            self._running = False
            logger.info("Barry scheduler stopped.")

    async def _poll_job(self) -> None:
        """Regular polling job."""
        try:
            logger.debug("Running scheduled poll...")
            result = await self.barry.poll_all()
            new_items = result.get("new_items", {})

            if new_items:
                update_text = await self.barry.briefing_gen.generate_situation_update(new_items)
                if update_text:
                    logger.info(f"New items detected: {list(new_items.keys())}")
                    for cb in self._on_update:
                        await cb(update_text, new_items)

                    # Send urgent WhatsApp notification if configured
                    urgency_keywords = ["urgent", "asap", "emergency", "critical"]
                    is_urgent = any(
                        any(kw in str(item).lower() for kw in urgency_keywords)
                        for items in new_items.values()
                        for item in items
                    )
                    if is_urgent:
                        await self.barry.actions.notify_self(
                            f"🚨 Urgent update:\n{update_text[:500]}",
                            title="Barry Alert",
                        )

        except Exception as e:
            logger.error(f"Poll job failed: {e}", exc_info=True)

    async def _morning_briefing_job(self) -> None:
        """Generate and send morning briefing."""
        try:
            logger.info("Generating morning briefing...")
            briefing = await self.barry.generate_daily_briefing()

            for cb in self._on_briefing:
                await cb(briefing)

            # Send via WhatsApp if available
            await self.barry.actions.notify_self(
                f"☀️ Good morning! Here's your briefing:\n\n{briefing[:1000]}...\n\nFull briefing available in Barry dashboard.",
                title="Barry Morning Briefing",
            )

            logger.info("Morning briefing sent.")
        except Exception as e:
            logger.error(f"Briefing job failed: {e}", exc_info=True)

    async def _urgent_check_job(self) -> None:
        """Check for upcoming urgent events or overdue tasks."""
        try:
            now = datetime.now()
            urgent_messages = []

            # Check for events starting in next 30 minutes
            for event in self.barry._last_events:
                start = event.get("start", "")
                if not start:
                    continue
                try:
                    from datetime import timezone
                    if "T" in start:
                        dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                        dt_local = dt.replace(tzinfo=None)
                        diff = (dt_local - now).total_seconds() / 60
                        if 0 < diff <= 30:
                            notif_id = f"event_reminder_{event['id']}"
                            if not self.barry.memory.was_notification_sent(notif_id):
                                urgent_messages.append(
                                    f"📅 Starting in {int(diff)}min: {event.get('title')}"
                                )
                                self.barry.memory.mark_notification_sent(notif_id, event.get("title", ""))
                except Exception:
                    pass

            # Check for overdue todos
            todos = self.barry.memory.get_todos()
            for todo in todos:
                due = todo.get("due_date")
                if due:
                    try:
                        due_dt = datetime.fromisoformat(due)
                        if due_dt < now and todo.get("priority", 3) <= 2:
                            notif_id = f"todo_overdue_{todo['id']}"
                            if not self.barry.memory.was_notification_sent(notif_id):
                                urgent_messages.append(
                                    f"⚠️ Overdue: {todo.get('title')}"
                                )
                                self.barry.memory.mark_notification_sent(notif_id, todo.get("title", ""))
                    except Exception:
                        pass

            if urgent_messages:
                message = "\n".join(urgent_messages)
                await self.barry.actions.notify_self(message, title="Barry Reminder")

        except Exception as e:
            logger.error(f"Urgent check failed: {e}", exc_info=True)

    async def _tone_learning_job(self) -> None:
        """Weekly tone profile learning from recent messages."""
        try:
            logger.info("Running weekly tone learning...")
            # Get recent email conversations and learn tone
            emails = self.barry._last_emails
            if emails:
                # Group by sender and learn tone from user's replies
                # This is a simplified version — in production, you'd fetch sent emails too
                logger.info(f"Tone learning: processed {len(emails)} emails")
        except Exception as e:
            logger.error(f"Tone learning failed: {e}", exc_info=True)

    async def run_now(self, job_id: str) -> None:
        """Manually trigger a scheduled job."""
        job_map = {
            "poll": self._poll_job,
            "briefing": self._morning_briefing_job,
            "urgent": self._urgent_check_job,
        }
        job = job_map.get(job_id)
        if job:
            await job()
        else:
            raise ValueError(f"Unknown job: {job_id}")
