"""AuraLens Streamlit application entrypoint."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import streamlit as st

from auralens import ConfigLoader, ServiceContainer
from auralens.advice import AdviceComposer
from auralens.analysis import (
    correlate_utterances_to_faces,
    describe_face,
    detect_utterance_tone,
    dominant_emotion,
)
from auralens.voice_ui import VoiceControlRenderer


# ---------------------------------------------------------------------------
# Cached resource initialisation
# ---------------------------------------------------------------------------


@st.cache_resource
def load_services() -> ServiceContainer:
    """Initialise core services once per session."""

    config = ConfigLoader.load()
    return ServiceContainer.build(config)


@st.cache_data
def get_visual_analysis(image_bytes: bytes) -> list[dict[str, Any]]:
    services = load_services()
    return services.rekognition.detect_faces(image_bytes)


@st.cache_data
def get_multi_agent_advice(emotion: str, visual_details_json: str, conversation_text: str) -> Dict[str, Any]:
    services = load_services()
    return services.writer.get_multi_agent_advice(emotion, visual_details_json, conversation_text)


@st.cache_data(show_spinner=False)
def synthesize_advice_audio(script: str, voice_hint: Optional[str]) -> Dict[str, Optional[Any]]:
    services = load_services()
    voiceover = services.voiceover
    if not voiceover:
        raise RuntimeError("ElevenLabs voiceover is not configured")

    resolved_id = voiceover.resolve_voice_id(voice_hint)
    audio_bytes = voiceover.synthesize(script, resolved_id)
    return {"audio": audio_bytes, "voice_id": resolved_id}


# ---------------------------------------------------------------------------
# Notes reference support
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def load_contact_notes() -> list[dict[str, str]]:
    notes_path = Path(__file__).with_name("notes.json")
    try:
        raw = notes_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [entry for entry in data if isinstance(entry, dict)]
    return []


def _normalise_contact_name(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum() or ch.isspace()).strip()


def resolve_contact_note(spoken_name: str) -> Optional[dict[str, str]]:
    target = _normalise_contact_name(spoken_name)
    if not target:
        return None

    for entry in load_contact_notes():
        name = entry.get("name")
        context = entry.get("context")
        if not isinstance(name, str) or not isinstance(context, str):
            continue

        variants = {_normalise_contact_name(name)}
        if "(" in name:
            variants.add(_normalise_contact_name(name.split("(", 1)[0]))

        for variant in variants:
            if not variant:
                continue
            if target == variant or target in variant or variant in target:
                return {"name": name, "context": context}

    return None


# ---------------------------------------------------------------------------
# Session state bootstrapping
# ---------------------------------------------------------------------------


def bootstrap_session_state() -> ServiceContainer:
    """Ensure session defaults and return the service container."""

    try:
        services = load_services()
    except ValueError as err:
        st.error(f"Configuration error: {err}")
        st.stop()
    except Exception as err:  # noqa: BLE001 - surface to UI
        st.error(f"Failed to initialise services: {err}")
        st.stop()

    config = services.config

    st.session_state.setdefault("conversation_input", "That's not what I meant.")
    st.session_state.setdefault("utterances", [])
    st.session_state.setdefault("processed_voice_ts", set())
    st.session_state.setdefault("listening_active", False)
    st.session_state.setdefault("audio_enabled", False)
    st.session_state.setdefault("tts_voice_id", config.elevenlabs.default_voice)
    st.session_state.setdefault("call_enabled", False)
    st.session_state.setdefault("call_phone_number", config.twilio.default_to_number or "")
    st.session_state.setdefault("active_contact_note", None)
    st.session_state.setdefault("active_contact_note_feedback", None)
    st.session_state.setdefault("active_contact_spoken_name", "")

    return services


# ---------------------------------------------------------------------------
# Main UI
# ---------------------------------------------------------------------------


def main() -> None:
    services = bootstrap_session_state()
    config = services.config

    st.set_page_config(layout="wide", page_title="AuraLens")

    if services.voiceover_error:
        st.warning(f"ElevenLabs voiceover unavailable: {services.voiceover_error}")
    if services.call_service_error:
        st.info(
            "Phone coach is disabled: ensure S3 and Twilio credentials are valid.",
            icon="ℹ️",
        )
    st.title("AuraLens 👓 - Multi-Agent Social Coach")
    st.write(
        "This prototype simulates a real-time AR social coach, providing advice from a panel of specialized AI agents."
    )

    # Sidebar controls ------------------------------------------------------
    voice_event: Optional[Any] = None

    with st.sidebar:
        st.header("Voice & Capture")
        voice_enabled = st.checkbox("Enable voice assistant", value=False)
        st.caption('Say "I\'m listening" to toggle dictation or "let me think about this {name}" to trigger the camera.')
        voice_event = VoiceControlRenderer.render(voice_enabled)

        st.divider()
        st.header("Relationship Notes")
        active_note = st.session_state.get("active_contact_note")
        note_feedback = st.session_state.get("active_contact_note_feedback")
        if active_note:
            st.markdown(f"**{active_note.get('name', 'Unknown contact')}**")
            st.write(active_note.get("context", ""))
        elif note_feedback:
            st.caption(note_feedback)
        else:
            st.caption('Include a name after "let me think about this" to surface saved notes.')

        st.divider()
        st.header("Audio Coach")
        if services.voiceover:
            st.checkbox("Play audio recommendations", key="audio_enabled")
            st.text_input(
                "ElevenLabs voice (name or voice_id)",
                key="tts_voice_id",
                value=st.session_state.get("tts_voice_id", config.elevenlabs.default_voice),
            )
            st.caption("Requires ELEVENLABS_API_KEY in your .env; defaults to the 'Rachel' voice.")
        else:
            st.session_state["audio_enabled"] = False
            st.caption("Add ELEVENLABS_API_KEY to enable spoken recommendations via ElevenLabs.")

        st.divider()
        st.header("Phone Coach")
        if services.call_service:
            st.checkbox("Call me with recommendations", key="call_enabled")
            st.text_input(
                "Destination phone number",
                key="call_phone_number",
                value=st.session_state.get("call_phone_number", config.twilio.default_to_number or ""),
                help="E.164 format, e.g., +14155551234",
            )
            st.caption("Requires Twilio voice credentials and an S3 bucket for temporary audio storage.")
        else:
            st.session_state["call_enabled"] = False
            missing = services.call_service_error or "Configure TWILIO_* credentials and AURALENS_AUDIO_BUCKET to enable phone calls."
            st.caption(missing)

    audio_enabled = bool(st.session_state.get("audio_enabled")) and services.voiceover is not None
    call_enabled = bool(st.session_state.get("call_enabled")) and services.call_service is not None
    voice_hint = st.session_state.get("tts_voice_id", config.elevenlabs.default_voice)
    call_phone_number = st.session_state.get("call_phone_number", config.twilio.default_to_number or "")

    # Handle voice events ---------------------------------------------------
    conversation_input = st.text_input(
        "What was the last thing the other person said?",
        value=st.session_state.get("conversation_input", "That's not what I meant."),
    )
    st.session_state["conversation_input"] = conversation_input

    picture = st.camera_input("Simulating **AuraLens** Vision Feed...")

    if voice_event:
        process_voice_event(voice_event)
        conversation_input = st.session_state.get("conversation_input", conversation_input)

    # Main content ----------------------------------------------------------
    if picture:
        face_details = get_visual_analysis(picture.getvalue())

        if face_details:
            primary_emotion, _ = dominant_emotion(face_details[0])
            st.success(f"**PRIMARY EMOTION DETECTED:** {primary_emotion}")

            with st.expander("Show Knowledge Graph: Visual Feature Extraction"):
                st.json(face_details)

            if st.session_state.get("utterances"):
                assignments = correlate_utterances_to_faces(face_details, st.session_state["utterances"])
                st.subheader("Conversation-to-Face Mapping (Heuristic)")
                for idx, face in enumerate(face_details):
                    st.markdown(f"**Face {idx + 1}: {describe_face(face)}**")
                    mapped = assignments.get(idx, [])
                    if mapped:
                        for utterance in mapped:
                            tone = utterance.get("tone", "neutral").capitalize()
                            st.write(f"- _{tone}_: {utterance.get('text')}")
                    else:
                        st.write("- No recent utterances tagged.")

            with st.spinner("Querying AI Agent Panel..."):
                visual_details_str = json.dumps(face_details)
                advice = get_multi_agent_advice(primary_emotion, visual_details_str, conversation_input)

            st.subheader("AI Agent Recommendations:")
            col1, col2, col3 = st.columns(3)
            col1.info("**❤️ Empathetic Coach**")
            col1.write(advice.get("empathetic", "No response."))
            col2.warning("**🧠 Logical Strategist**")
            col2.write(advice.get("logical", "No response."))
            col3.error("**💡 Creative Wildcard**")
            col3.write(advice.get("creative", "No response."))

            audio_bytes: Optional[bytes] = None
            audio_script = AdviceComposer.build_script(advice)

            if (audio_enabled or call_enabled) and audio_script:
                with st.spinner("Synthesizing recommendations audio..."):
                    try:
                        audio_payload = synthesize_advice_audio(audio_script, voice_hint)
                        audio_bytes = audio_payload.get("audio")
                        resolved_voice_id = audio_payload.get("voice_id")
                    except RuntimeError as audio_err:
                        audio_bytes = None
                        st.warning(f"ElevenLabs audio error: {audio_err}")
                    else:
                        if resolved_voice_id and resolved_voice_id != voice_hint:
                            st.caption(f"Using voice ID {resolved_voice_id} (matched from '{voice_hint}').")

            if audio_enabled:
                if audio_bytes:
                    st.audio(audio_bytes, format="audio/mpeg")
                elif not audio_script:
                    st.info("Audio coach skipped: no advice text available.")

            if call_enabled:
                call_service = services.call_service
                if audio_bytes and call_service:
                    try:
                        presigned_url = call_service.place_call(audio_bytes, call_phone_number)
                    except RuntimeError as call_error:
                        st.warning(f"Call failed: {call_error}")
                    else:
                        st.success("Calling your phone now with the latest recommendations.")
                        st.caption(f"Audio served from temporary link (valid 1 hour): {presigned_url}")
                elif not audio_script:
                    st.info("Phone coach skipped: no advice text available to narrate.")
        else:
            st.warning("No face detected in the current frame. Please try again.")
    else:
        st.info("Capture a frame to begin the AuraLens analysis pipeline.")


# ---------------------------------------------------------------------------
# Voice event processing
# ---------------------------------------------------------------------------


def process_voice_event(payload: Any) -> None:
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return

    if not isinstance(payload, dict):
        return

    event_ts = payload.get("ts")
    if event_ts is None:
        return

    processed_ts = st.session_state.setdefault("processed_voice_ts", set())
    if event_ts in processed_ts:
        return

    processed_ts.add(event_ts)

    event_type = payload.get("type")
    if event_type == "listening_state":
        st.session_state["listening_active"] = bool(payload.get("active"))
    elif event_type == "utterance":
        text = payload.get("text", "").strip()
        if not text:
            return
        st.session_state["conversation_input"] = text
        st.session_state["listening_active"] = True
        utterances = st.session_state.setdefault("utterances", [])
        utterances.append({"ts": event_ts, "text": text, "tone": detect_utterance_tone(text)})
        st.session_state["utterances"] = utterances[-50:]
    elif event_type == "photo_hotword":
        spoken_name = (payload.get("name") or "").strip()
        st.session_state["active_contact_spoken_name"] = spoken_name
        if spoken_name:
            note = resolve_contact_note(spoken_name)
            if note:
                st.session_state["active_contact_note"] = note
                st.session_state["active_contact_note_feedback"] = None
            else:
                st.session_state["active_contact_note"] = None
                st.session_state["active_contact_note_feedback"] = f"No saved notes found for \"{spoken_name}\"."
        else:
            st.session_state["active_contact_note"] = None
            st.session_state["active_contact_note_feedback"] = "No name detected in the voice command."


if __name__ == "__main__":
    main()
