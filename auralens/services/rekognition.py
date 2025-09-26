"""AWS Rekognition integration."""

from __future__ import annotations

from typing import Any, Dict, List

import boto3

from auralens.config import AWSConfig


class RekognitionService:
    """Wrapper around AWS Rekognition for face analysis."""

    def __init__(self, config: AWSConfig) -> None:
        if not config.is_valid:
            raise ValueError("Invalid AWS configuration for RekognitionService")
        self._client = boto3.client(
            "rekognition",
            aws_access_key_id=config.access_key_id,
            aws_secret_access_key=config.secret_access_key,
            region_name=config.region,
        )

    def detect_faces(self, image_bytes: bytes) -> List[Dict[str, Any]]:
        response = self._client.detect_faces(Image={"Bytes": image_bytes}, Attributes=["ALL"])
        return response.get("FaceDetails", [])
