from __future__ import annotations

import re
from typing import Optional

from research_agent.decision.decision_packet import RatingPermission
from research_agent.decision.rating_taxonomy import Rating


def enforce_rating_permission(final_text: str, permission: RatingPermission) -> None:
    rating = extract_rating_from_text(final_text)
    if rating is None:
        return
    if rating in permission.blocked_ratings:
        raise RuntimeError(f"Final report uses blocked rating: {rating.value}")


def extract_rating_from_text(text: str) -> Optional[Rating]:
    rating_pattern = re.compile(
        r"(?:final\s+rating|rating|recommendation|finale\s+empfehlung|anlageurteil|urteil)\s*[:\-]\s*\*{0,2}([A-Za-z ]+)",
        re.IGNORECASE,
    )
    candidates = [match.group(1) for match in rating_pattern.finditer(text)]
    if not candidates:
        candidates = [text]
    for candidate in candidates:
        cleaned = " ".join(candidate.replace("*", "").strip().split())
        for rating in sorted(Rating, key=lambda item: len(item.value), reverse=True):
            if cleaned.lower().startswith(rating.value.lower()) or re.search(rf"\b{re.escape(rating.value)}\b", cleaned, re.IGNORECASE):
                return rating
    return None
