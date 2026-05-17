from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel


class GuidanceRange(BaseModel):
    metric: str
    low: Optional[float]
    high: Optional[float]
    unit: str
    period: str
    source_text: str


def extract_eps_guidance(text: str, period: str) -> list[GuidanceRange]:
    patterns = [
        r"non-GAAP (?:diluted )?EPS.*?\$([0-9]+(?:\.[0-9]+)?)\s*(?:to|-|and)\s*\$([0-9]+(?:\.[0-9]+)?)",
        r"non-GAAP net income per share.*?\$([0-9]+(?:\.[0-9]+)?)\s*(?:to|-|and)\s*\$([0-9]+(?:\.[0-9]+)?)",
    ]
    return _extract_ranges(text, period, patterns, metric="company_guidance_eps", unit="usd_per_share")


def extract_revenue_guidance(text: str, period: str) -> list[GuidanceRange]:
    patterns = [
        r"revenue.*?\$([0-9]+(?:\.[0-9]+)?)\s*(million|billion|m|bn|b)?\s*(?:to|-|and)\s*\$([0-9]+(?:\.[0-9]+)?)\s*(million|billion|m|bn|b)?",
    ]
    results: list[GuidanceRange] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE | re.DOTALL):
            low = _scale(float(match.group(1)), match.group(2))
            high = _scale(float(match.group(3)), match.group(4) or match.group(2))
            results.append(
                GuidanceRange(
                    metric="company_guidance_revenue",
                    low=low,
                    high=high,
                    unit="usd",
                    period=period,
                    source_text=match.group(0)[:500],
                )
            )
    return results


def _extract_ranges(text: str, period: str, patterns: list[str], metric: str, unit: str) -> list[GuidanceRange]:
    results: list[GuidanceRange] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE | re.DOTALL):
            results.append(
                GuidanceRange(
                    metric=metric,
                    low=float(match.group(1)),
                    high=float(match.group(2)),
                    unit=unit,
                    period=period,
                    source_text=match.group(0)[:500],
                )
            )
    return results


def _scale(value: float, suffix: Optional[str]) -> float:
    normalized = (suffix or "").lower()
    if normalized in {"billion", "bn", "b"}:
        return value * 1_000_000_000
    if normalized in {"million", "m"}:
        return value * 1_000_000
    return value
