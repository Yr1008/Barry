"""
Tone Learner — analyzes and remembers how the user communicates
with different people (formal, casual, emoji-heavy, brief, etc.)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import anthropic


@dataclass
class ToneProfile:
    contact_id: str
    contact_name: str
    platform: str
    formality: str          # formal / semi-formal / casual / very-casual
    emoji_usage: str        # none / rare / moderate / heavy
    avg_message_length: str # brief / medium / long
    language_patterns: list[str]  # e.g. ["starts with 'Hey'", "signs off with 'Cheers'"]
    full_description: str


class ToneLearner:
    """
    Analyzes conversation samples to learn the user's tone
    with each contact and generates tone-matched reply drafts.
    """

    def __init__(self, client: "anthropic.Anthropic"):
        self.client = client

    def analyze_messages(
        self,
        contact_name: str,
        platform: str,
        user_messages: list[str],
    ) -> ToneProfile | None:
        """
        Given a list of messages the user has sent to a contact,
        analyze the communication style and return a ToneProfile.
        """
        if not user_messages:
            return None

        sample = "\n---\n".join(user_messages[-15:])
        prompt = f"""Analyze the communication style in these messages that a person sent to {contact_name} on {platform}:

<messages>
{sample}
</messages>

Return a JSON object with exactly these fields:
{{
  "formality": "formal|semi-formal|casual|very-casual",
  "emoji_usage": "none|rare|moderate|heavy",
  "avg_message_length": "brief|medium|long",
  "language_patterns": ["list", "of", "observed", "patterns"],
  "full_description": "2-3 sentence summary of the tone and style"
}}

Only return the JSON, nothing else."""

        try:
            resp = self.client.messages.create(
                model="claude-opus-4-6",
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text.strip()
            # Clean markdown code blocks if present
            text = re.sub(r"^```[a-z]*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
            data = json.loads(text)

            return ToneProfile(
                contact_id=f"{platform}:{contact_name}".lower().replace(" ", "_"),
                contact_name=contact_name,
                platform=platform,
                formality=data.get("formality", "casual"),
                emoji_usage=data.get("emoji_usage", "rare"),
                avg_message_length=data.get("avg_message_length", "medium"),
                language_patterns=data.get("language_patterns", []),
                full_description=data.get("full_description", ""),
            )
        except Exception as e:
            print(f"[ToneLearner] Failed to analyze: {e}")
            return None

    def generate_reply(
        self,
        contact_name: str,
        platform: str,
        incoming_message: str,
        context: str,
        tone_description: str,
        user_intent: str,
    ) -> str:
        """
        Generate a reply draft matching the user's established tone.
        """
        prompt = f"""You are helping {context} draft a reply to {contact_name} on {platform}.

The user's established communication style with this person:
{tone_description}

Incoming message from {contact_name}:
"{incoming_message}"

What the user wants to say:
{user_intent}

Write a reply that:
1. Matches the established tone and style exactly
2. Conveys the user's intent naturally
3. Feels authentic, not AI-generated
4. Respects the platform norms ({platform})

Return ONLY the reply text, nothing else."""

        try:
            resp = self.client.messages.create(
                model="claude-opus-4-6",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.content[0].text.strip()
        except Exception as e:
            return f"[Error generating reply: {e}]"

    def tone_to_system_context(self, tone_profile: dict) -> str:
        """Convert a stored tone profile dict into a system prompt snippet."""
        if not tone_profile:
            return ""

        patterns = tone_profile.get("language_patterns", [])
        patterns_str = ", ".join(patterns) if patterns else "none noted"

        return (
            f"Communication style with {tone_profile['contact_name']} "
            f"({tone_profile['platform']}): "
            f"{tone_profile.get('tone_description', '')} "
            f"Language patterns: {patterns_str}."
        )
