"""Conversation-to-face correlation helpers."""

from __future__ import annotations

from typing import Dict, List, Optional

POSITIVE_WORDS = {
    "great",
    "good",
    "happy",
    "love",
    "excited",
    "awesome",
    "amazing",
    "thanks",
    "appreciate",
    "glad",
    "yes",
}

NEGATIVE_WORDS = {
    "bad",
    "upset",
    "angry",
    "sad",
    "frustrated",
    "no",
    "worried",
    "nervous",
    "unhappy",
    "confused",
    "anxious",
}

EMOTION_GROUPS = {
    "positive": {"HAPPY", "SURPRISED"},
    "negative": {"SAD", "ANGRY", "DISGUSTED", "FEAR", "CONFUSED", "NEGATIVE"},
    "neutral": {"CALM", "UNKNOWN", "NEUTRAL"},
}


def detect_utterance_tone(text: str) -> str:
    words = [token.strip(".,!?\"'").lower() for token in text.split()]
    score = sum(1 for w in words if w in POSITIVE_WORDS) - sum(1 for w in words if w in NEGATIVE_WORDS)
    if score > 0:
        return "positive"
    if score < 0:
        return "negative"
    return "neutral"


def dominant_emotion(face: Dict) -> tuple[str, float]:
    emotions = face.get("Emotions", [])
    if not emotions:
        return "UNKNOWN", 0.0
    top = max(emotions, key=lambda e: e.get("Confidence", 0.0))
    return top.get("Type", "UNKNOWN"), top.get("Confidence", 0.0)


def select_face_for_tone(faces: List[Dict], tone: str) -> Optional[int]:
    if not faces:
        return None
    target = EMOTION_GROUPS.get(tone, EMOTION_GROUPS["neutral"])
    best_idx = 0
    best_score = -1.0
    for idx, face in enumerate(faces):
        score = 0.0
        for emotion in face.get("Emotions", []):
            if emotion.get("Type") in target:
                score += emotion.get("Confidence", 0.0)
        if score > best_score:
            best_idx = idx
            best_score = score
    return best_idx


def correlate_utterances_to_faces(faces: List[Dict], utterances: List[Dict]) -> Dict[int, List[Dict]]:
    assignments: Dict[int, List[Dict]] = {idx: [] for idx in range(len(faces))}
    if not faces or not utterances:
        return assignments

    for utterance in sorted(utterances, key=lambda u: u["ts"]):
        tone = utterance.get("tone") or detect_utterance_tone(utterance.get("text", ""))
        face_idx = select_face_for_tone(faces, tone)
        if face_idx is None:
            continue
        enriched = {
            "text": utterance.get("text", ""),
            "tone": tone,
            "ts": utterance.get("ts"),
        }
        assignments.setdefault(face_idx, []).append(enriched)

    return assignments


def describe_face(face: Dict) -> str:
    gender = face.get("Gender", {}).get("Value")
    age_range = face.get("AgeRange", {})
    age_low = age_range.get("Low")
    age_high = age_range.get("High")
    emotion, confidence = dominant_emotion(face)

    descriptors = []
    if gender:
        descriptors.append(gender.title())
    if age_low and age_high:
        descriptors.append(f"age {age_low}-{age_high}")
    elif age_low:
        descriptors.append(f"age {age_low}+")
    elif age_high:
        descriptors.append(f"age ≤{age_high}")
    if emotion and confidence:
        descriptors.append(f"dominant emotion {emotion} ({confidence:.0f}%)")

    return ", ".join(descriptors) if descriptors else "Unlabeled"
