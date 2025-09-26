"""ElevenLabs text-to-speech integration."""

from __future__ import annotations

from typing import Dict, List, Optional

from elevenlabs import ElevenLabs

from auralens.config import ElevenLabsConfig


class VoiceoverService:
    """Synthesizes audio briefings using ElevenLabs."""

    def __init__(self, config: ElevenLabsConfig) -> None:
        if not config.is_enabled:
            raise ValueError("ElevenLabs API key missing")
        self._config = config
        self._client = ElevenLabs(api_key=config.api_key)

    @property
    def client(self) -> ElevenLabs:
        return self._client

    def list_voices(self) -> List[Dict[str, str]]:
        voices = self._client.voices.get_all()
        serialized: List[Dict[str, str]] = []
        for voice in voices:
            serialized.append({
                "voice_id": getattr(voice, "voice_id", ""),
                "name": getattr(voice, "name", ""),
            })
        return serialized

    def resolve_voice_id(self, voice_hint: Optional[str]) -> Optional[str]:
        catalog = self.list_voices()
        if not catalog:
            return self._config.fallback_voice_id or None

        by_id = {item.get("voice_id"): item for item in catalog if item.get("voice_id")}
        by_name = {item.get("name", "").lower(): item for item in catalog if item.get("name")}

        if voice_hint:
            trimmed = voice_hint.strip()
            if trimmed in by_id:
                return trimmed
            lowered = trimmed.lower()
            if lowered in by_name:
                return by_name[lowered]["voice_id"]

        if self._config.fallback_voice_id and self._config.fallback_voice_id in by_id:
            return self._config.fallback_voice_id

        first_voice = catalog[0]
        return first_voice.get("voice_id") if first_voice else None

    def synthesize(self, text: str, voice_id: Optional[str]) -> Optional[bytes]:
        if not text:
            return None

        resolved_voice_id = voice_id or self._config.fallback_voice_id
        audio_stream = self._client.text_to_speech.convert(
            voice_id=resolved_voice_id,
            text=text,
            model_id="eleven_turbo_v2",
            output_format="mp3_44100_128",
        )

        if isinstance(audio_stream, bytes):
            return audio_stream

        if hasattr(audio_stream, "__iter__"):
            return b"".join(chunk for chunk in audio_stream)

        return None
