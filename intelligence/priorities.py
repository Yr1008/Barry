"""
Todo Prioritizer — uses Claude to intelligently sort and prioritize tasks.

Takes into account:
- Due dates
- Context from calendar (what's coming up)
- Email urgency signals
- User preferences
- Time of day / day of week
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import anthropic
    from memory.store import MemoryStore


class TodoPrioritizer:
    """AI-powered todo prioritization."""

    def __init__(self, client: "anthropic.Anthropic", memory: "MemoryStore", config):
        self.client = client
        self.memory = memory
        self.config = config

    async def prioritize_todos(
        self,
        todos: list[dict],
        events: list[dict] | None = None,
        emails: list[dict] | None = None,
    ) -> list[dict]:
        """
        Prioritize todos using Claude's intelligence.
        Returns todos sorted by priority with reasoning.
        """
        if not todos:
            return []

        owner = self.config.owner_name
        now = datetime.now()

        todos_str = "\n".join(
            f"{i+1}. [{t.get('id')}] {t.get('title')} "
            f"(due: {t.get('due_date', 'none')}, source: {t.get('source', '?')})"
            for i, t in enumerate(todos)
        )

        events_str = ""
        if events:
            events_str = "Upcoming calendar events:\n" + "\n".join(
                f"• {e.get('start', '')[:16]} — {e.get('title', '')}"
                for e in events[:5]
            )

        emails_str = ""
        if emails:
            # Show only subjects that imply action
            urgent_keywords = ["urgent", "asap", "deadline", "action required", "important", "follow up"]
            urgent_emails = [
                e for e in emails
                if any(kw in e.get("subject", "").lower() for kw in urgent_keywords)
            ]
            if urgent_emails:
                emails_str = "Urgent emails:\n" + "\n".join(
                    f"• {e.get('subject', '')}" for e in urgent_emails[:3]
                )

        prompt = f"""You are Barry, {owner}'s AI assistant. Analyze and prioritize these tasks intelligently.

Current time: {now.strftime('%A, %B %d at %I:%M %p')}

Tasks to prioritize:
{todos_str}

{events_str}

{emails_str}

Return a JSON array where each item has:
- "id": the task id (number)
- "priority": 1 (critical), 2 (high), 3 (medium), 4 (low)
- "reason": brief explanation of why this priority (max 15 words)
- "suggested_time": when to do this today (e.g., "morning", "afternoon", "evening", "this week")

Order by priority (1 first). Return ONLY valid JSON array, nothing else."""

        try:
            resp = self.client.messages.create(
                model="claude-opus-4-6",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text.strip()
            text = re.sub(r"^```[a-z]*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
            priorities = json.loads(text)

            # Build lookup
            priority_map = {str(p["id"]): p for p in priorities}

            # Update todos with new priorities
            updated = []
            for todo in todos:
                todo_id = str(todo.get("id", ""))
                if todo_id in priority_map:
                    p_info = priority_map[todo_id]
                    updated.append({
                        **todo,
                        "priority": p_info.get("priority", 3),
                        "ai_reason": p_info.get("reason", ""),
                        "suggested_time": p_info.get("suggested_time", ""),
                    })
                    # Persist updated priority
                    self.memory.update_todo_priority(todo["id"], p_info.get("priority", 3))
                else:
                    updated.append(todo)

            return sorted(updated, key=lambda t: t.get("priority", 3))

        except Exception as e:
            print(f"[Prioritizer] Error: {e}")
            return todos

    async def extract_todos_from_text(self, text: str, source: str = "conversation") -> list[str]:
        """Extract actionable to-do items from free text."""
        prompt = f"""Extract actionable to-do items from this text.
Return a JSON array of strings, each being a clear, actionable task.
If there are no actionable items, return an empty array [].

Text:
{text}

Return ONLY a JSON array of strings."""

        try:
            resp = self.client.messages.create(
                model="claude-opus-4-6",
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            text_out = resp.content[0].text.strip()
            text_out = re.sub(r"^```[a-z]*\n?", "", text_out)
            text_out = re.sub(r"\n?```$", "", text_out)
            tasks = json.loads(text_out)
            return tasks if isinstance(tasks, list) else []
        except Exception:
            return []

    def format_prioritized_todos(self, todos: list[dict]) -> str:
        """Format prioritized todos for display."""
        if not todos:
            return "No pending todos. You're all caught up! 🎉"

        priority_icons = {1: "🔴", 2: "🟠", 3: "🟡", 4: "⚪"}
        lines = [f"**Your {len(todos)} tasks, prioritized:**\n"]

        for t in todos:
            priority = t.get("priority", 3)
            icon = priority_icons.get(priority, "⚪")
            title = t.get("title", "Untitled")
            due = f" — due {t['due_date'][:10]}" if t.get("due_date") else ""
            time_hint = f" [{t['suggested_time']}]" if t.get("suggested_time") else ""
            reason = f"\n   _{t['ai_reason']}_" if t.get("ai_reason") else ""
            lines.append(f"{icon} **{title}**{due}{time_hint}{reason}")

        return "\n".join(lines)
