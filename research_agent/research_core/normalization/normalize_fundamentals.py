from __future__ import annotations

from typing import Any


def normalize_fundamentals(fundamentals: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(fundamentals)
    normalized.setdefault("quarterly", {})
    normalized.setdefault("balance_sheet", {})
    normalized.setdefault("share_data", {})
    return normalized

