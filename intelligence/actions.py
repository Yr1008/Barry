"""
Action Executor — enables Barry to take real actions.

Supported actions:
- Send emails
- Send WhatsApp messages
- Add/complete todos
- Create calendar events (via Google API)
- Send push notifications (Pushover)
- Store facts / preferences
"""
from __future__ import annotations

import httpx
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from connectors.email_conn import EmailConnector
    from connectors.whatsapp_conn import WhatsAppConnector
    from connectors.calendar_conn import CalendarConnector
    from memory.store import MemoryStore


class ActionExecutor:
    """Executes actions on behalf of the user."""

    def __init__(
        self,
        memory: "MemoryStore",
        config,
        email: "EmailConnector | None" = None,
        whatsapp: "WhatsAppConnector | None" = None,
        calendar: "CalendarConnector | None" = None,
    ):
        self.memory = memory
        self.config = config
        self.email = email
        self.whatsapp = whatsapp
        self.calendar = calendar

    async def send_email(self, to: str, subject: str, body: str) -> dict:
        """Send an email."""
        if not self.email or not self.email.is_available():
            return {"success": False, "error": "Email connector not configured"}
        ok = await self.email.send_email(to, subject, body)
        return {"success": ok, "action": "send_email", "to": to, "subject": subject}

    async def send_whatsapp(self, to: str, message: str) -> dict:
        """Send a WhatsApp message."""
        if not self.whatsapp or not self.whatsapp.is_available():
            return {"success": False, "error": "WhatsApp connector not configured"}
        ok = await self.whatsapp.send_message(to, message)
        return {"success": ok, "action": "send_whatsapp", "to": to}

    async def notify_self(self, message: str, title: str = "Barry") -> dict:
        """Send a push notification to yourself."""
        results = []

        # WhatsApp self-notification
        if self.whatsapp and self.whatsapp.is_available() and self.config.my_whatsapp_number:
            ok = await self.whatsapp.send_to_self(f"*{title}*\n{message}")
            results.append({"channel": "whatsapp", "success": ok})

        # Pushover notification
        if self.config.has_pushover:
            ok = await self._send_pushover(title, message)
            results.append({"channel": "pushover", "success": ok})

        return {"action": "notify_self", "results": results}

    async def _send_pushover(self, title: str, message: str) -> bool:
        """Send notification via Pushover."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.pushover.net/1/messages.json",
                    data={
                        "token": self.config.pushover_api_token,
                        "user": self.config.pushover_user_key,
                        "title": title,
                        "message": message,
                    },
                    timeout=10,
                )
                return resp.status_code == 200
        except Exception:
            return False

    async def add_todo(
        self,
        title: str,
        description: str = "",
        priority: int = 3,
        due_date: str | None = None,
        tags: list[str] | None = None,
    ) -> dict:
        """Add a todo item."""
        todo_id = self.memory.add_todo(
            title=title,
            description=description,
            priority=priority,
            due_date=due_date,
            source="barry",
            tags=tags,
        )
        return {"success": True, "action": "add_todo", "id": todo_id, "title": title}

    async def complete_todo(self, todo_id: int) -> dict:
        """Mark a todo as complete."""
        self.memory.update_todo_status(todo_id, "completed")
        return {"success": True, "action": "complete_todo", "id": todo_id}

    async def remember_preference(self, key: str, value: Any) -> dict:
        """Store a user preference."""
        self.memory.set_preference(key, value)
        return {"success": True, "action": "remember", "key": key, "value": value}

    async def learn_fact(self, category: str, fact: str, source: str = "conversation") -> dict:
        """Store a fact Barry has learned."""
        self.memory.add_fact(category, fact, source=source)
        return {"success": True, "action": "learn_fact", "category": category}

    def get_tool_definitions(self) -> list[dict]:
        """Return Claude tool definitions for all available actions."""
        tools = [
            {
                "name": "add_todo",
                "description": "Add a new to-do item to the user's task list",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Task title"},
                        "description": {"type": "string", "description": "Optional details"},
                        "priority": {"type": "integer", "enum": [1, 2, 3, 4], "description": "1=critical, 2=high, 3=medium, 4=low"},
                        "due_date": {"type": "string", "description": "ISO date string, e.g. 2024-03-15"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["title"],
                },
            },
            {
                "name": "complete_todo",
                "description": "Mark a to-do item as completed",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "todo_id": {"type": "integer", "description": "The todo item ID"},
                    },
                    "required": ["todo_id"],
                },
            },
            {
                "name": "remember_preference",
                "description": "Remember a user preference or setting",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "Preference key"},
                        "value": {"description": "Preference value (any type)"},
                    },
                    "required": ["key", "value"],
                },
            },
            {
                "name": "learn_fact",
                "description": "Store an important fact Barry has learned about the user",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string", "description": "Category like 'personal', 'work', 'preference'"},
                        "fact": {"type": "string", "description": "The fact to remember"},
                    },
                    "required": ["category", "fact"],
                },
            },
            {
                "name": "notify_self",
                "description": "Send a push notification or WhatsApp message to the user",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "Notification message"},
                        "title": {"type": "string", "description": "Notification title"},
                    },
                    "required": ["message"],
                },
            },
        ]

        if self.email and self.email.is_available():
            tools.append({
                "name": "send_email",
                "description": "Send an email on behalf of the user",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "to": {"type": "string", "description": "Recipient email address"},
                        "subject": {"type": "string", "description": "Email subject"},
                        "body": {"type": "string", "description": "Email body text"},
                    },
                    "required": ["to", "subject", "body"],
                },
            })

        if self.whatsapp and self.whatsapp.is_available():
            tools.append({
                "name": "send_whatsapp",
                "description": "Send a WhatsApp message on behalf of the user",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "to": {"type": "string", "description": "Recipient phone number (with country code)"},
                        "message": {"type": "string", "description": "Message text"},
                    },
                    "required": ["to", "message"],
                },
            })

        return tools

    async def execute_tool(self, tool_name: str, tool_input: dict) -> str:
        """Execute a tool call from Claude."""
        actions = {
            "add_todo": lambda: self.add_todo(**tool_input),
            "complete_todo": lambda: self.complete_todo(**tool_input),
            "remember_preference": lambda: self.remember_preference(**tool_input),
            "learn_fact": lambda: self.learn_fact(**tool_input),
            "notify_self": lambda: self.notify_self(**tool_input),
            "send_email": lambda: self.send_email(**tool_input),
            "send_whatsapp": lambda: self.send_whatsapp(**tool_input),
        }

        action = actions.get(tool_name)
        if not action:
            return f"Unknown action: {tool_name}"

        try:
            result = await action()
            return str(result)
        except Exception as e:
            return f"Error executing {tool_name}: {e}"
