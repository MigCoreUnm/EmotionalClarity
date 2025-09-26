"""Configuration loading for the AuraLens application."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv
import os


@dataclass(frozen=True)
class AWSConfig:
    access_key_id: str
    secret_access_key: str
    region: str

    @property
    def is_valid(self) -> bool:
        return all([self.access_key_id, self.secret_access_key, self.region])


@dataclass(frozen=True)
class WriterConfig:
    api_key: str

    @property
    def is_valid(self) -> bool:
        return bool(self.api_key)


@dataclass(frozen=True)
class ElevenLabsConfig:
    api_key: Optional[str]
    default_voice: str
    fallback_voice_id: str

    @property
    def is_enabled(self) -> bool:
        return bool(self.api_key)


@dataclass(frozen=True)
class TwilioConfig:
    account_sid: Optional[str]
    auth_token: Optional[str]
    from_number: Optional[str]
    default_to_number: Optional[str]

    @property
    def is_enabled(self) -> bool:
        return all([self.account_sid, self.auth_token, self.from_number])


@dataclass(frozen=True)
class StorageConfig:
    audio_bucket: Optional[str]

    @property
    def is_enabled(self) -> bool:
        return bool(self.audio_bucket)


@dataclass(frozen=True)
class AppConfig:
    aws: AWSConfig
    writer: WriterConfig
    elevenlabs: ElevenLabsConfig
    twilio: TwilioConfig
    storage: StorageConfig


class ConfigLoader:
    """Loads configuration for the AuraLens application from environment variables."""

    @staticmethod
    def load() -> AppConfig:
        load_dotenv()

        aws = AWSConfig(
            access_key_id=os.getenv("AWS_ACCESS_KEY_ID", ""),
            secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", ""),
            region=os.getenv("AWS_REGION", "") or "us-west-2",
        )
        writer = WriterConfig(api_key=os.getenv("WRITER_API_KEY", ""))
        elevenlabs = ElevenLabsConfig(
            api_key=os.getenv("ELEVENLABS_API_KEY"),
            default_voice=os.getenv("ELEVENLABS_VOICE_ID", "Rachel"),
            fallback_voice_id=os.getenv("ELEVENLABS_FALLBACK_VOICE_ID", "21m00Tcm4TlvDq8ikWAM"),
        )
        twilio = TwilioConfig(
            account_sid=os.getenv("TWILIO_ACCOUNT_SID"),
            auth_token=os.getenv("TWILIO_AUTH_TOKEN"),
            from_number=os.getenv("TWILIO_FROM_NUMBER"),
            default_to_number=os.getenv("AURALENS_DEFAULT_TO_NUMBER"),
        )
        storage = StorageConfig(audio_bucket=os.getenv("AURALENS_AUDIO_BUCKET"))

        return AppConfig(
            aws=aws,
            writer=writer,
            elevenlabs=elevenlabs,
            twilio=twilio,
            storage=storage,
        )
