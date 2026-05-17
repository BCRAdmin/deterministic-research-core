from __future__ import annotations

from typing import Any


def normalize_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for event in events:
        item = dict(event)
        if "date" in item and item["date"] is not None:
            item["date"] = str(item["date"])[:10]
        normalized.append(item)
    return normalized

