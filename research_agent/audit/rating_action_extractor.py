from __future__ import annotations

import re
from typing import Optional


RATING_VALUES = [
    "Strong Buy",
    "Buy",
    "Accumulate",
    "Hold",
    "Tactical Trim",
    "Tactical Underweight",
    "Underweight",
    "Sell",
    "Avoid",
]

RATING_RE = re.compile(
    r"(?:final\s+rating|rating|recommendation|finale\s+empfehlung|anlageurteil|urteil)\s*[:\-]\s*\*{0,2}([A-Za-z ]+)",
    re.IGNORECASE,
)

ACTION_TERMS = [
    "reduce",
    "trim",
    "teilweise reduzieren",
    "hold core",
    "kern halten",
    "close position",
    "sell entire",
    "exit fully",
    "startposition",
    "pullback",
    "breakout",
    "staged",
    "gestaffelt",
    "accumulate",
    "buy",
]


def extract_final_rating(markdown: str) -> Optional[str]:
    for match in RATING_RE.finditer(markdown):
        candidate = _clean_rating_candidate(match.group(1))
        for rating in sorted(RATING_VALUES, key=len, reverse=True):
            if candidate.lower().startswith(rating.lower()):
                return rating
    for rating in sorted(RATING_VALUES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(rating)}\b", markdown, re.IGNORECASE):
            return rating
    return None


def extract_action_lines(markdown: str) -> list[str]:
    lines = []
    for line in markdown.splitlines():
        lower = line.lower()
        if any(term in lower for term in ACTION_TERMS):
            lines.append(line.strip())
    return lines


def infer_report_action_class(actions: list[str]) -> str:
    text = " ".join(actions).lower()

    if "close position" in text or "sell entire" in text or "exit fully" in text:
        return "sell"

    if "startposition" in text or "staged" in text or "gestaffelt" in text:
        return "staged_entry"

    if "trim" in text or "reduce" in text or "teilweise reduzieren" in text:
        return "tactical_trim"

    if "hold" in text and "add" not in text:
        return "hold"

    if "accumulate" in text:
        return "accumulate"

    if "buy" in text:
        return "buy"

    return "unknown"


def _clean_rating_candidate(candidate: str) -> str:
    return " ".join(candidate.replace("*", "").strip().split())

