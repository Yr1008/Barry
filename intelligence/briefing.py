"""
Daily Briefing Generator.

Synthesizes data from all connectors into a smart,
personalized daily briefing with priorities and actions.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import anthropic
    from connectors import CalendarConnector, EmailConnector
    from connectors.whatsapp_conn import WhatsAppConnector
    from connectors.iphone_mac import iPhoneMacConnector
    from memory.store import MemoryStore


class BriefingGenerator:
    """Generates smart daily and situational briefings using Claude."""

    def __init__(self, client: "anthropic.Anthropic", memory: "MemoryStore", config):
        self.client = client
        self.memory = memory
        self.config = config

    async def generate_daily_briefing(
        self,
        events: list[dict],
        emails: list[dict],
        whatsapp_messages: list[dict],
        todos: list[dict],
        reminders: list[dict],
        iphone_status: dict | None = None,
    ) -> str:
        """Generate a comprehensive daily briefing."""

        # Gather preferences and facts
        prefs = self.memory.get_all_preferences()
        facts = self.memory.get_facts()
        facts_str = "\n".join(f"- {f['category']}: {f['fact']}" for f in facts[:20]) or "None yet"

        # Build context sections
        now = datetime.now()
        tz = self.config.timezone
        owner = self.config.owner_name

        events_section = self._format_events(events)
        emails_section = self._format_emails(emails)
        whatsapp_section = self._format_messages(whatsapp_messages)
        todos_section = self._format_todos(todos)
        reminders_section = self._format_reminders(reminders)
        iphone_str = self._format_iphone(iphone_status) if iphone_status else ""

        prompt = f"""You are Barry, {owner}'s personal AI assistant. Generate a smart, concise morning briefing.

Current time: {now.strftime('%A, %B %d, %Y at %I:%M %p')} ({tz})

## What's on {owner}'s plate today:

### Calendar Events (next 7 days):
{events_section}

### Unread Emails ({len(emails)}):
{emails_section}

### WhatsApp Messages ({len(whatsapp_messages)}):
{whatsapp_section}

### To-Do Items ({len(todos)} pending):
{todos_section}

### Reminders:
{reminders_section}

### iPhone Status:
{iphone_str or 'N/A'}

### Known facts about {owner}:
{facts_str}

Generate a briefing that:
1. **Opens** with a warm, brief greeting and key highlights (2-3 sentences)
2. **Today's priorities** — what needs attention RIGHT NOW, in order of urgency
3. **Schedule overview** — just today's events (what to prepare for)
4. **Inbox highlights** — only emails/messages that need a response or action
5. **Smart recommendations** — 2-3 things Barry suggests doing today based on context
6. **Coming up** — what's approaching in next 48-72 hours to be aware of

Keep it energetic, smart, and actionable. No fluff. Bullet points where helpful.
Address {owner} directly. Be like a smart EA who knows their priorities."""

        with self.client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=2048,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            return stream.get_final_message().content[-1].text

    async def generate_situation_update(
        self,
        new_data: dict[str, list[dict]],
        context: str = "",
    ) -> str:
        """Generate a brief update when new important data arrives."""
        owner = self.config.owner_name
        items = []
        for source, data_items in new_data.items():
            for item in data_items:
                items.append(f"[{source}] {item.get('title') or item.get('subject') or item.get('body', '')[:100]}")

        if not items:
            return ""

        items_str = "\n".join(items)
        prompt = f"""Barry is {owner}'s AI assistant. New information just arrived:

{items_str}

{f'Context: {context}' if context else ''}

Write a brief (2-4 sentences) smart update for {owner}. Highlight what's urgent or needs attention.
Be direct and actionable. Start with the most important thing."""

        resp = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text

    def _format_events(self, events: list[dict]) -> str:
        if not events:
            return "No upcoming events."
        lines = []
        for e in events[:10]:
            start = e.get("start", "")[:16].replace("T", " ")
            title = e.get("title", "Untitled")
            loc = f" @ {e['location']}" if e.get("location") else ""
            lines.append(f"• {start} — {title}{loc}")
        return "\n".join(lines)

    def _format_emails(self, emails: list[dict]) -> str:
        if not emails:
            return "No unread emails."
        lines = []
        for e in emails[:8]:
            sender = e.get("from", "Unknown")[:40]
            subject = e.get("subject", "(no subject)")[:60]
            lines.append(f"• From {sender}: \"{subject}\"")
        if len(emails) > 8:
            lines.append(f"• ... and {len(emails) - 8} more")
        return "\n".join(lines)

    def _format_messages(self, messages: list[dict]) -> str:
        if not messages:
            return "No new WhatsApp messages."
        lines = []
        for m in messages[:5]:
            sender = m.get("from", "Unknown").replace("whatsapp:", "")
            body = m.get("body", "")[:80]
            lines.append(f"• {sender}: \"{body}\"")
        return "\n".join(lines)

    def _format_todos(self, todos: list[dict]) -> str:
        if not todos:
            return "No pending todos."
        lines = []
        for t in todos[:8]:
            priority = "🔴" if t.get("priority", 3) == 1 else "🟡" if t.get("priority", 3) == 2 else "⚪"
            due = f" (due {t['due_date'][:10]})" if t.get("due_date") else ""
            lines.append(f"• {priority} {t.get('title', 'Untitled')}{due}")
        return "\n".join(lines)

    def _format_reminders(self, reminders: list[dict]) -> str:
        if not reminders:
            return "No active reminders."
        lines = []
        for r in reminders[:5]:
            due = f" — due {r['due_date'][:10]}" if r.get("due_date") else ""
            lines.append(f"• {r.get('title', 'Untitled')}{due}")
        return "\n".join(lines)

    def _format_iphone(self, status: dict) -> str:
        if not status:
            return ""
        lines = []
        if status.get("battery"):
            b = status["battery"]
            charging = "charging" if b.get("charging") else "not charging"
            lines.append(f"Battery: {b.get('level')}% ({charging})")
        if status.get("focus_mode") and status["focus_mode"] != "None":
            lines.append(f"Focus: {status['focus_mode']}")
        return " | ".join(lines)
