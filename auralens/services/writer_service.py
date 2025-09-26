"""Writer API integration for generating multi-agent advice."""

from __future__ import annotations

import json
from typing import Any, Dict

from writerai import Writer

from auralens.config import WriterConfig


class WriterService:
    """Provides access to the Writer LLM for multi-agent recommendations."""

    def __init__(self, config: WriterConfig) -> None:
        if not config.is_valid:
            raise ValueError("Writer API key missing")
        self._client = Writer(api_key=config.api_key)

    def get_multi_agent_advice(self, emotion: str, visual_details_json: str, conversation_text: str) -> Dict[str, Any]:
        prompt = f"""
        You are a panel of three expert AI social coaches. Analyze the situation and provide three distinct courses of action.
        SITUATIONAL CONTEXT:
        - Visual Emotion Detected: {emotion}
        - Detailed Visual Analysis (JSON): {visual_details_json}
        - Last thing the other person said: "{conversation_text}"

        TASK:
        Generate a response for each persona. Be concise and actionable.
        1. The Empathetic Coach: Focus on feelings and connection.
        2. The Logical Strategist: Focus on direct problem-solving.
        3. The Creative Wildcard: Suggest an unconventional approach.

        Format your output as a single, valid JSON object with three keys: "empathetic", "logical", and "creative".
        Example: {{"empathetic": "Acknowledge their feelings by saying...", "logical": "Clarify the situation by asking...", "creative": "Try changing the topic to something lighter like..."}}
        """

        response = self._client.completions.create(
            model="palmyra-x-003-instruct",
            prompt=prompt,
            max_tokens=350,
        )

        advice_text = response.choices[0].text.strip()
        cleaned = advice_text[advice_text.find("{"): advice_text.rfind("}") + 1]
        return json.loads(cleaned)
