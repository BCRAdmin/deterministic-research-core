"""Issuer-neutral grammar for safe, reported FFO total-row labels."""

from __future__ import annotations

import re
import unicodedata


_PLAIN_FFO = r"(?:funds from operations(?:\s*\(ffo\))?|ffo)"
_HOLDER = (
    r"(?:common\s+(?:stockholders|shareholders|unitholders)|"
    r"(?:third[- ]party\s+)?op\s+unitholders)"
)
_BENEFICIARY = rf".*\b{_HOLDER}(?:\s+and\s+{_HOLDER})*"
_DISALLOWED = re.compile(
    r"\b(?:adjusted|core|normalized|excluding|before|after)\b|\bper\s+share\b",
    re.IGNORECASE,
)
_TOTAL = re.compile(
    rf"(?:nareit\s+)?{_PLAIN_FFO}(?:\s+attributable\s+to\s+{_BENEFICIARY})?",
    re.IGNORECASE,
)


def normalize_reit_total_row_label(value: str) -> str:
    """Normalize harmless typography without changing semantic tokens."""

    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.translate(
        str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})
    )
    normalized = re.sub(
        r"\(\s*['\"]?\s*ffo\s*['\"]?\s*\)",
        "(FFO)",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(r"(?:\s*[*†‡]+|\s*\(\d+\))+$", "", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def is_plain_reported_ffo_total_label(value: str) -> bool:
    """Return true only for a complete, non-adjusted plain-FFO total label."""

    normalized = normalize_reit_total_row_label(value)
    return not _DISALLOWED.search(normalized) and _TOTAL.fullmatch(normalized) is not None
