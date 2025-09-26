"""Service container for AuraLens application."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import boto3
from botocore.client import BaseClient
from twilio.rest import Client as TwilioClient

from auralens.config import AppConfig
from auralens.services.call_service import CallService
from auralens.services.rekognition import RekognitionService
from auralens.services.voiceover import VoiceoverService
from auralens.services.writer_service import WriterService


@dataclass
class ServiceContainer:
    config: AppConfig
    rekognition: RekognitionService
    writer: WriterService
    voiceover: Optional[VoiceoverService]
    call_service: Optional[CallService]
    s3_client: Optional[BaseClient]
    twilio_client: Optional[TwilioClient]
    voiceover_error: Optional[str] = None
    call_service_error: Optional[str] = None

    @classmethod
    def build(cls, config: AppConfig) -> "ServiceContainer":
        if not config.aws.is_valid:
            raise ValueError("AWS credentials are required for Rekognition")
        if not config.writer.is_valid:
            raise ValueError("Writer API key is required")

        rekognition = RekognitionService(config.aws)
        writer = WriterService(config.writer)

        voiceover: Optional[VoiceoverService] = None
        voiceover_error: Optional[str] = None
        if config.elevenlabs.is_enabled:
            try:
                voiceover = VoiceoverService(config.elevenlabs)
            except Exception as exc:
                voiceover_error = str(exc)

        s3_client: Optional[BaseClient] = None
        if config.storage.is_enabled:
            s3_client = boto3.client(
                "s3",
                aws_access_key_id=config.aws.access_key_id,
                aws_secret_access_key=config.aws.secret_access_key,
                region_name=config.aws.region,
            )

        twilio_client: Optional[TwilioClient] = None
        if config.twilio.is_enabled:
            twilio_client = TwilioClient(config.twilio.account_sid, config.twilio.auth_token)

        call_service: Optional[CallService] = None
        call_service_error: Optional[str] = None
        if voiceover and config.storage.is_enabled and config.twilio.is_enabled and s3_client and twilio_client:
            call_service = CallService(
                storage_config=config.storage,
                twilio_config=config.twilio,
                s3_client=s3_client,
                twilio_client=twilio_client,
            )
        elif config.twilio.is_enabled and config.storage.is_enabled and (not s3_client or not twilio_client):
            call_service_error = "S3 or Twilio client could not be initialized"

        return cls(
            config=config,
            rekognition=rekognition,
            writer=writer,
            voiceover=voiceover,
            call_service=call_service,
            s3_client=s3_client,
            twilio_client=twilio_client,
            voiceover_error=voiceover_error,
            call_service_error=call_service_error,
        )
