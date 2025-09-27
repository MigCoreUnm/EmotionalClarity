"""Utility script to verify S3 + Twilio call integration for AuraLens."""

from __future__ import annotations

import argparse
import base64
import os
import sys
import uuid
from typing import Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client as TwilioClient
from twilio.twiml.voice_response import VoiceResponse

# 1-second silent MP3 (44.1 kHz) in base64; enough for connectivity checks.
_SILENCE_MP3_BASE64 = (
    "SUQzAwAAAAAAF1RTU0UAAAAPAAADTGF2ZjU4LjI5LjEwMAAAAAAAAAAAAAAA//uQZAAAAAAAAA\n"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n"
    "AAAA//uQZAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n"
    "AAAA//sQZAAAAAADAAADSAAAAAEAAACyAAAACAAADSAAAAAEAAACyAAAC/+xBkAAAAAMAAANIAAA\n"
    "AAgAAAARAAANIAAABAAEAACyAAAA//sQZAAAAAADAAAAbAAAAAEAAAACAAAAGwAAAAEAAAACAAAA\n"
    "G/+xBkAAAAAMAAABsAAAABAAAABIAAABsAAAAAQAAAAIAAAAb/7EGQAAAAAwAAABsAAAABAAAAEgA\n"
    "AABsAAAAAQAAAAIAAAAb/7EGQAAAAAwAAABsAAAABAAAAEgAAABsAAAAAQAAAAIAAAAb/7EGQAAAAA\n"
    "wAAABsAAAABAAAAEgAAABsAAAAAQAAAAIAAAAb//sQZAAAAAAgAAADQAAAAAQAAAAIAAABNAAAACAA\n"
    "AAANIAAAABAAAAAgAAAAk//uQZAAAACAgAAADQAAAAAQAAAAMAAABNAAAACAAAANIAAAABAAAAAgAAA\n"
    "Ak//uQZAAAACAgAAADQAAAAAQAAAAMAAABNAAAACAAAANIAAAABAAAAAgAAAAk//uQZAAAACAgAAADQ\n"
    "AAAAAQAAAAMAAABNAAAACAAAANIAAAABAAAAAgAAAAk//uQZAAAACAgAAADQAAAAAQAAAAMAAABNAAA\n"
    "ACAAAANIAAAABAAAAAgAAAAk//uQZAAAACAgAAADQAAAAAQAAAAMAAABNAAAACAAAANIAAAABAAAAAgA\n"
    "AAAk//uQZAAAACAgAAADQAAAAAQAAAAMAAABNAAAACAAAANIAAAABAAAAAgAAAAk//uQZAAAACAgAAADQ\n"
    "AAAAAQAAAAMAAABNAAAACAAAANIAAAABAAAAAgAAAAk//uQZAAAACAgAAADQAAAAAQAAAAMAAABNAAAACAAAANIAAAABAAAAAgAAAAk//uQZAAAACAgAAADQAAAAAQAAAAMAAABNAAAACAAAANIAAAABAAAAAgAAAAk//uQZAAAACAgAAADQAAAAAQAAAAMAAABNAAAACAAAANIAAAABAAAAAgAAAAk//uQZAAAACAgAAADQAAAAAQAAAAMAAABNAAAACAAAANIAAAABAAAAAgAAAAk//uQZAAAACAgAAADQAAAAAQAAAAMAAABNAAAACAAAANIAAAABAAAAAgAAAAk//uQZAAAACAgAAADQAAAAAQAAAAMAAABNAAAACAAAANIAAAABAAAAAgAAAAk//uQZAAAACAgAAADQAAAAAQAAAAMAAABNAAAACAAAANIAAAABAAAAAgAAAAk//uQZAAAACAgAAADQAAAAAQAAAAMAAABNAAAACAAAANIAAAABAAAAAgAAAAk//uQZAAAACAgAAADQAAAAAQAAAAMAAABNAAAACAAAANIAAAABAAAAAgAAAAk//uQZAAAACAgAAADQAAAAAQAAAAMAAABNAAAACAAAANIAAAABAAAAAgAAAAk//sQZAAAAAAgAAANIAAAABAAAAAgAAAAk//uQZAAAACAgAAADQAAAAAQAAAAMAAABNAAAACAAAANIAAAABAAAAAgAAAAk//uQZAAAACAgAAADQAAAAAQAAAAMAAABNAAAACAAAANIAAAABAAAAAgAAAAk//sQZAAAAAAgAAANIAAAABAAAAAgAAAAk"
)


def _decode_silence() -> bytes:
    raw = "".join(_SILENCE_MP3_BASE64.split())
    missing = (-len(raw)) % 4
    if missing:
        raw += "=" * missing
    return base64.b64decode(raw)


def _configure_clients():
    load_dotenv()

    aws_region = os.getenv("AWS_REGION") or "us-west-2"
    bucket = os.getenv("AURALENS_AUDIO_BUCKET")
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_FROM_NUMBER")
    to_number = os.getenv("AURALENS_DEFAULT_TO_NUMBER")

    missing = [
        ("AWS_REGION", aws_region),
        ("AURALENS_AUDIO_BUCKET", bucket),
        ("TWILIO_ACCOUNT_SID", account_sid),
        ("TWILIO_AUTH_TOKEN", auth_token),
        ("TWILIO_FROM_NUMBER", from_number),
    ]
    errors = [name for name, value in missing if not value]
    if errors:
        raise SystemExit(f"Missing required environment variables: {', '.join(errors)}")

    s3 = boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=aws_region,
    )
    twilio_client = TwilioClient(account_sid, auth_token)

    return s3, bucket, twilio_client, from_number, to_number


def upload_test_audio(s3, bucket: str) -> str:
    key = f"auralens-test/{uuid.uuid4()}.mp3"
    audio_bytes = _decode_silence()
    s3.put_object(Bucket=bucket, Key=key, Body=audio_bytes, ContentType="audio/mpeg")
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=3600,
    )
    return url


def place_test_call(client: TwilioClient, from_number: str, to_number: str, audio_url: str) -> str:
    response = VoiceResponse()
    response.play(audio_url)

    call = client.calls.create(
        to=to_number,
        from_=from_number,
        twiml=str(response),
    )
    return call.sid


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Verify S3 + Twilio connectivity with a scripted call.")
    parser.add_argument("--skip-call", action="store_true", help="Upload to S3 only; do not place a call.")
    args = parser.parse_args(argv)

    try:
        s3, bucket, twilio_client, from_number, to_number = _configure_clients()
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        return 1

    print(f"Uploading test audio to bucket '{bucket}'...")
    try:
        presigned_url = upload_test_audio(s3, bucket)
    except (BotoCoreError, ClientError) as aws_error:
        print(f"S3 upload failed: {aws_error}", file=sys.stderr)
        return 1

    print(f"Presigned URL generated (valid 1 hour): {presigned_url}")

    if args.skip_call:
        print("Skipping Twilio call per --skip-call flag.")
        return 0

    destination = to_number or input("Enter destination phone number (E.164, e.g. +14155551234): ")

    print(f"Placing Twilio call from {from_number} to {destination}...")
    try:
        sid = place_test_call(twilio_client, from_number, destination, presigned_url)
    except TwilioRestException as twilio_error:
        print(
            "Twilio call failed:\n"
            f"  Status: {twilio_error.status}\n"
            f"  Code:   {twilio_error.code}\n"
            f"  Msg:    {twilio_error.msg}\n",
            file=sys.stderr,
        )
        return 1

    print(f"Call initiated successfully. SID: {sid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
