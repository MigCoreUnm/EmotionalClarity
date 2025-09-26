"""Advice composition utilities."""

from __future__ import annotations

from typing import Dict, List, Tuple

PERSONA_ORDER: List[Tuple[str, str]] = [
    ("empathetic", "Empathetic coach"),
    ("logical", "Logical strategist"),
    ("creative", "Creative wildcard"),
]


class AdviceComposer:
    """Formats multi-agent advice into scripts suitable for narration."""

    @staticmethod
    def build_script(advice: Dict[str, str]) -> str:
        if not advice:
            return ""
        segments = []
        for key, label in PERSONA_ORDER:
            message = advice.get(key)
            if not message:
                continue
            segments.append(f"{label} says: {message}")
        return " ".join(segments).strip()
