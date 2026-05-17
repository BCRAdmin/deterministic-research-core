from __future__ import annotations

from typing import Iterable


def normalize_news_items(items: Iterable[dict]) -> list[dict]:
    normalized = []
    for item in items:
        normalized.append(
            {
                "ticker": item.get("ticker"),
                "headline": item.get("headline") or item.get("title"),
                "date": item.get("date") or item.get("published_at"),
                "source_id": item.get("source_id") or item.get("url"),
                "source_type": item.get("source_type") or item.get("source"),
                "url": item.get("url"),
            }
        )
    return normalized
