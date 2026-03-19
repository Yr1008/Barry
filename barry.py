"""
Barry — The Core AI Assistant Brain.

This is the main orchestrator that:
1. Holds the Claude client and conversation history
2. Routes requests to connectors and intelligence modules
3. Handles the agentic loop with tools
4. Manages memory and preferences
5. Provides a unified interface for the CLI and API server
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator

import anthropic

from config import get_config
from connectors.calendar_conn import CalendarConnector
from connectors.email_conn import EmailConnector
from connectors.whatsapp_conn import WhatsAppConnector
from connectors.iphone_mac import iPhoneMacConnector
from intelligence.briefing import BriefingGenerator
from intelligence.priorities import TodoPrioritizer
from intelligence.actions import ActionExecutor
from memory.store import MemoryStore
from memory.tone import ToneLearner


BARRY_SYSTEM_PROMPT = """You are Barry, {owner}'s personal AI assistant — smart, proactive, and deeply integrated into their digital life.

## Your Capabilities
- **Calendar & Schedule**: You see {owner}'s upcoming events (Google Calendar + Apple Calendar)
- **Email**: You monitor the inbox and can draft/send emails
- **WhatsApp**: You receive and can send WhatsApp messages
- **iPhone/Mac**: You receive data from {owner}'s devices via Apple Shortcuts
- **Memory**: You remember preferences, facts, and communication styles with contacts
- **Actions**: You can add todos, send messages, set reminders, and more
- **Tone matching**: You know how {owner} communicates with different people

## Your Personality
- Proactive, not passive — you anticipate needs
- Concise and direct — no fluff
- Smart prioritization — you know what actually matters
- Remembers everything — you build on past conversations
- Action-oriented — you suggest AND help take action

## What You Know About {owner}
{user_facts}

## Current Context
Date/Time: {current_time}
Timezone: {timezone}
Pending todos: {todo_count}

## Communication Style Guide
{tone_summary}

## Important Guidelines
- When you learn something new about {owner}, use the `learn_fact` tool to remember it
- When {owner} mentions a task, offer to add it to their todo list
- When drafting messages/emails, match the recipient's tone profile
- Always check the calendar before suggesting meeting times
- If you're not sure about something, ask — don't guess
- Proactively mention upcoming deadlines or events when relevant"""


class Barry:
    """The main Barry AI assistant."""

    def __init__(self):
        self.config = get_config()
        self.client = anthropic.Anthropic(api_key=self.config.anthropic_api_key)
        self.memory = MemoryStore(self.config.db_path)
        self.tone_learner = ToneLearner(self.client)

        # Connectors
        self.calendar = CalendarConnector(self.config)
        self.email = EmailConnector(self.config)
        self.whatsapp = WhatsAppConnector(self.config)
        self.iphone = iPhoneMacConnector(self.config)

        # Intelligence
        self.briefing_gen = BriefingGenerator(self.client, self.memory, self.config)
        self.prioritizer = TodoPrioritizer(self.client, self.memory, self.config)
        self.actions = ActionExecutor(
            self.memory,
            self.config,
            email=self.email,
            whatsapp=self.whatsapp,
            calendar=self.calendar,
        )

        # Conversation state
        self._messages: list[dict] = []
        self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Cached data from last poll
        self._last_events: list[dict] = []
        self._last_emails: list[dict] = []
        self._last_whatsapp: list[dict] = []
        self._last_todos: list[dict] = []
        self._last_reminders: list[dict] = []

    def _build_system_prompt(self) -> str:
        """Build personalized system prompt."""
        facts = self.memory.get_facts()
        facts_str = "\n".join(
            f"- [{f['category']}] {f['fact']}" for f in facts[:30]
        ) or "None stored yet."

        tone_profiles = self.memory.get_all_tone_profiles()
        tone_summary = ""
        if tone_profiles:
            tone_parts = []
            for tp in tone_profiles[:10]:
                tone_parts.append(
                    f"- {tp['contact_name']} ({tp['platform']}): {tp.get('tone_description', '')}"
                )
            tone_summary = "\n".join(tone_parts)
        else:
            tone_summary = "No tone profiles learned yet."

        todos = self.memory.get_todos()
        self._last_todos = todos

        return BARRY_SYSTEM_PROMPT.format(
            owner=self.config.owner_name,
            user_facts=facts_str,
            current_time=datetime.now().strftime("%A, %B %d, %Y at %I:%M %p"),
            timezone=self.config.timezone,
            todo_count=len(todos),
            tone_summary=tone_summary,
        )

    async def chat(self, user_message: str, stream: bool = True) -> AsyncGenerator[str, None] | str:
        """
        Main chat interface. Handles the agentic loop with tools.
        """
        # Save to memory
        self.memory.add_message("user", user_message, self._session_id)

        # Build messages list
        self._messages.append({"role": "user", "content": user_message})

        # Keep conversation manageable (last 20 exchanges)
        if len(self._messages) > 40:
            self._messages = self._messages[-40:]

        system = self._build_system_prompt()
        tools = self.actions.get_tool_definitions()

        if stream:
            return self._chat_stream(system, tools)
        else:
            return await self._chat_complete(system, tools)

    async def _chat_complete(self, system: str, tools: list[dict]) -> str:
        """Non-streaming chat with agentic tool loop."""
        messages = list(self._messages)

        while True:
            response = self.client.messages.create(
                model="claude-opus-4-6",
                max_tokens=4096,
                thinking={"type": "adaptive"},
                system=system,
                tools=tools,
                messages=messages,
            )

            # Add assistant response to history
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                # Extract text response
                text = next(
                    (b.text for b in response.content if hasattr(b, "text") and b.type == "text"),
                    "",
                )
                self._messages = messages
                self.memory.add_message("assistant", text, self._session_id)
                return text

            if response.stop_reason == "tool_use":
                # Execute tools
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = await self.actions.execute_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                messages.append({"role": "user", "content": tool_results})
                continue

            break

        self._messages = messages
        return ""

    async def _chat_stream(self, system: str, tools: list[dict]):
        """Streaming chat (returns async generator)."""
        messages = list(self._messages)
        full_response = ""

        while True:
            tool_results = []
            text_pieces = []
            content_blocks = []

            with self.client.messages.stream(
                model="claude-opus-4-6",
                max_tokens=4096,
                thinking={"type": "adaptive"},
                system=system,
                tools=tools,
                messages=messages,
            ) as stream:
                for event in stream:
                    if event.type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            yield event.delta.text
                            text_pieces.append(event.delta.text)

                final_msg = stream.get_final_message()

            content_blocks = final_msg.content
            messages.append({"role": "assistant", "content": content_blocks})

            if final_msg.stop_reason == "end_turn":
                full_response = "".join(text_pieces)
                break

            if final_msg.stop_reason == "tool_use":
                for block in content_blocks:
                    if block.type == "tool_use":
                        result = await self.actions.execute_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                if tool_results:
                    yield f"\n_[Executing {len(tool_results)} action(s)...]_\n"
                    messages.append({"role": "user", "content": tool_results})
                    continue

            break

        self._messages = messages
        if full_response:
            self.memory.add_message("assistant", full_response, self._session_id)

    async def poll_all(self) -> dict[str, Any]:
        """Poll all connectors for latest data."""
        results = {}
        new_items: dict[str, list] = {}

        # Calendar
        cal_result = await self.calendar.safe_fetch()
        if cal_result.ok:
            self._last_events = cal_result.items
            results["calendar"] = f"{len(cal_result.items)} events"

        # Email
        email_result = await self.email.safe_fetch()
        if email_result.ok:
            new_emails = [
                e for e in email_result.items
                if not self.memory.was_notification_sent(f"email_{e.get('id')}")
            ]
            if new_emails:
                new_items["email"] = new_emails
                for e in new_emails:
                    self.memory.mark_notification_sent(f"email_{e.get('id')}", e.get("subject", ""))
            self._last_emails = email_result.items
            results["email"] = f"{len(email_result.items)} unread"

        # WhatsApp
        wa_result = await self.whatsapp.safe_fetch()
        if wa_result.ok and wa_result.items:
            new_items["whatsapp"] = wa_result.items
            self._last_whatsapp.extend(wa_result.items)
            results["whatsapp"] = f"{len(wa_result.items)} new messages"

        # iPhone/Mac
        iphone_result = await self.iphone.safe_fetch()
        if iphone_result.ok:
            results["iphone"] = f"{len(iphone_result.items)} items"
            # Add reminders as todos
            for item in iphone_result.items:
                if item.get("data_type") == "reminder":
                    existing = self.memory.was_notification_sent(f"reminder_{item['id']}")
                    if not existing:
                        self.memory.add_todo(
                            title=item.get("title", ""),
                            due_date=item.get("due_date"),
                            source="iphone_reminders",
                            tags=["reminder"],
                        )
                        self.memory.mark_notification_sent(f"reminder_{item['id']}", item.get("title", ""))

        # iCloud Reminders
        reminders = await self.iphone.fetch_icloud_reminders()
        self._last_reminders = reminders

        return {"poll_results": results, "new_items": new_items}

    async def generate_daily_briefing(self) -> str:
        """Generate and return the daily briefing."""
        # Ensure we have fresh data
        await self.poll_all()

        todos = self.memory.get_todos()
        self._last_todos = todos

        briefing = await self.briefing_gen.generate_daily_briefing(
            events=self._last_events,
            emails=self._last_emails,
            whatsapp_messages=self._last_whatsapp,
            todos=todos,
            reminders=self._last_reminders,
            iphone_status=self.iphone.get_status(),
        )

        # Save briefing as fact for context
        self.memory.set_preference("last_briefing_date", datetime.now().isoformat())

        return briefing

    async def get_prioritized_todos(self) -> str:
        """Return AI-prioritized todo list."""
        todos = self.memory.get_todos()
        if not todos:
            return "No pending todos. You're all caught up! 🎉"

        prioritized = await self.prioritizer.prioritize_todos(
            todos=todos,
            events=self._last_events,
            emails=self._last_emails,
        )
        return self.prioritizer.format_prioritized_todos(prioritized)

    async def learn_tone(
        self,
        contact_name: str,
        platform: str,
        user_messages: list[str],
    ) -> str:
        """Learn the user's communication tone with a contact."""
        profile = self.tone_learner.analyze_messages(contact_name, platform, user_messages)
        if not profile:
            return "Not enough messages to analyze tone."

        self.memory.save_tone_profile(
            contact_id=profile.contact_id,
            contact_name=profile.contact_name,
            platform=profile.platform,
            tone_description=profile.full_description,
            sample_messages=user_messages,
        )

        return f"Learned {contact_name}'s tone on {platform}: {profile.full_description}"

    def get_status(self) -> dict:
        """Return Barry's current status."""
        return {
            "name": self.config.barry_name,
            "owner": self.config.owner_name,
            "timezone": self.config.timezone,
            "connectors": {
                "google_calendar": self.config.has_google,
                "icloud": self.config.has_icloud,
                "email": self.config.has_email,
                "whatsapp": self.config.has_whatsapp,
                "iphone_shortcuts": True,
            },
            "memory": {
                "todos": len(self.memory.get_todos()),
                "facts": len(self.memory.get_facts()),
                "tone_profiles": len(self.memory.get_all_tone_profiles()),
                "conversation_history": len(self.memory.get_recent_messages(100)),
            },
            "last_events": len(self._last_events),
            "last_emails": len(self._last_emails),
            "iphone_status": self.iphone.get_status(),
        }

    def reset_conversation(self) -> None:
        """Start a fresh conversation."""
        self._messages = []
        self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.memory.clear_old_messages(keep_last=200)
