"""Handles outbound phone calls using Twilio and S3."""

from __future__ import annotations

import uuid
from typing import Optional

from botocore.client import BaseClient
from twilio.rest import Client as TwilioClient
from twilio.twiml.voice_response import VoiceResponse

from auralens.config import StorageConfig, TwilioConfig


class CallService:
    """Uploads audio to S3 and initiates Twilio calls."""

    def __init__(
        self,
        storage_config: StorageConfig,
        twilio_config: TwilioConfig,
        s3_client: BaseClient,
        twilio_client: TwilioClient,
    ) -> None:
        if not storage_config.is_enabled:
            raise ValueError("Storage configuration missing for call service")
        if not twilio_config.is_enabled:
            raise ValueError("Twilio configuration missing for call service")

        self._storage_config = storage_config
        self._twilio_config = twilio_config
        self._s3_client = s3_client
        self._twilio_client = twilio_client

    def place_call(self, audio_bytes: bytes, phone_number: Optional[str]) -> str:
        if not audio_bytes:
            raise RuntimeError("No audio payload available")

        destination = phone_number or self._twilio_config.default_to_number
        if not destination:
            raise RuntimeError("Destination phone number is required")

        object_key = f"auralens-calls/{uuid.uuid4()}.mp3"
        self._s3_client.put_object(
            Bucket=self._storage_config.audio_bucket,
            Key=object_key,
            Body=audio_bytes,
            ContentType="audio/mpeg",
        )
        presigned_url = self._s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._storage_config.audio_bucket, "Key": object_key},
            ExpiresIn=3600,
        )

        response = VoiceResponse()
        response.play(presigned_url)

        self._twilio_client.calls.create(
            to=destination,
            from_=self._twilio_config.from_number,
            twiml=str(response),
        )

        return presigned_url
