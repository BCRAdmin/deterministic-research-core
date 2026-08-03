from __future__ import annotations

import re
from typing import Iterable, Optional

from research_agent.audit.audit_report import ExtractedNumericClaim
from research_agent.audit.claim_mapper import infer_possible_metric


DATE_RE = re.compile(r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{4})\b")
PERCENT_RE = re.compile(r"(?<![\w$])([+-]?\d+(?:[.,]\d+)?)\s*(?:%|Prozent)", re.IGNORECASE)
MULTIPLE_RE = re.compile(r"(?<![\w$])([+-]?\d+(?:[.,]\d+)?)\s*-?\s*(?:x|faches|fach|fache)\b", re.IGNORECASE)
CURRENCY_PREFIX_RE = re.compile(
    r"(?P<leading_sign>[+-]?)\s*(?:(?P<symbol>\$)|(?P<currency>USD|HUF)\s*)\s*"
    r"(?P<number>[+-]?\d+(?:[.,]\d{1,3})*)\s*"
    r"(?P<scale>B|bn|billion|Mrd\.?|Mio\.?|million|M|k)?(?=\W|$)",
    re.IGNORECASE,
)
CURRENCY_SUFFIX_RE = re.compile(
    r"(?<![\w])(?P<number>[+-]?\d+(?:[.,]\d{1,3})*)\s*"
    r"(?P<scale>B|bn|billion|Mrd\.?|Mio\.?|million|M|k)?\s*"
    r"(?:(?P<symbol>\$)|(?P<currency>USD|HUF)|US-Dollar)(?=\W|$)",
    re.IGNORECASE,
)


def extract_numeric_claims(markdown: str) -> list[ExtractedNumericClaim]:
    claims: list[ExtractedNumericClaim] = []
    for line_number, line in enumerate(markdown.splitlines(), start=1):
        if line.strip().lower().startswith("## evidence appendix"):
            break
        claims.extend(_extract_line_claims(line, line_number))
    return _dedupe_claims(claims)


def _extract_line_claims(line: str, line_number: int) -> list[ExtractedNumericClaim]:
    line = _claim_text_without_metadata(line)
    nearby = line.strip()
    claims: list[ExtractedNumericClaim] = []

    for match in DATE_RE.finditer(line):
        claims.append(
            _claim(
                raw_text=match.group(0),
                value=None,
                unit="date",
                nearby_text=nearby,
                line_number=line_number,
            )
        )

    for match, currency in _iter_currency_matches(line):
        claims.append(
            _claim(
                raw_text=match.group(0),
                value=_normalize_number(
                    f"{match.groupdict().get('leading_sign') or ''}{match.group('number')}",
                    match.group("scale"),
                ),
                unit=currency,
                nearby_text=nearby,
                line_number=line_number,
                metric_context=_metric_context(line, match.start(), match.end()),
            )
        )

    for match in PERCENT_RE.finditer(line):
        claims.append(
            _claim(
                raw_text=match.group(0),
                value=_normalize_plain_number(match.group(1)),
                unit="percent",
                nearby_text=nearby,
                line_number=line_number,
                metric_context=_metric_context(line, match.start(), match.end()),
            )
        )

    for match in MULTIPLE_RE.finditer(line):
        claims.append(
            _claim(
                raw_text=match.group(0),
                value=_normalize_plain_number(match.group(1)),
                unit="multiple",
                nearby_text=nearby,
                line_number=line_number,
                metric_context=_metric_context(line, match.start(), match.end()),
            )
        )

    return claims


def _claim_text_without_metadata(line: str) -> str:
    metadata = re.search(
        r"\s+(?:Evidence metrics|Evidence IDs|Confidence):",
        line,
        re.IGNORECASE,
    )
    return line[: metadata.start()] if metadata else line


def _iter_currency_matches(line: str) -> Iterable[tuple[re.Match[str], str]]:
    seen_spans: set[tuple[int, int]] = set()
    for regex in [CURRENCY_PREFIX_RE, CURRENCY_SUFFIX_RE]:
        for match in regex.finditer(line):
            if match.span() in seen_spans:
                continue
            seen_spans.add(match.span())
            currency = "usd" if match.group("symbol") else (match.group("currency") or "USD").lower()
            yield match, currency


def _claim(
    raw_text: str,
    value: Optional[float],
    unit: str,
    nearby_text: str,
    line_number: int,
    metric_context: Optional[str] = None,
) -> ExtractedNumericClaim:
    return ExtractedNumericClaim(
        raw_text=raw_text,
        normalized_value=value,
        unit=unit,
        nearby_text=nearby_text,
        line_number=line_number,
        possible_metric=infer_possible_metric(
            metric_context or nearby_text,
            unit=unit,
        ),
        period_hint=_infer_period_hint(nearby_text),
    )


def _metric_context(line: str, start: int, end: int) -> str:
    return line[max(0, start - 48) : end]


def _normalize_number(number_text: str, scale_text: Optional[str]) -> float:
    value = _normalize_plain_number(number_text)
    scale = (scale_text or "").lower().replace(".", "")
    if scale in {"b", "bn", "billion", "mrd"}:
        return value * 1_000_000_000
    if scale in {"m", "mio", "million"}:
        return value * 1_000_000
    if scale == "k":
        return value * 1_000
    return value


def _normalize_plain_number(number_text: str) -> float:
    text = number_text.strip().replace(" ", "")
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        after = text.split(",")[-1]
        if len(after) == 3 and text.count(",") >= 1:
            text = text.replace(",", "")
        else:
            text = text.replace(",", ".")
    return float(text)


def _infer_period_hint(text: str) -> str:
    lower = text.lower()
    has_q4 = bool(re.search(r"\bq4\b|fourth quarter|4\. quartal", lower))
    has_ttm = "ttm" in lower or "trailing twelve" in lower
    if has_q4 and has_ttm:
        return "mixed"
    if has_q4:
        return "q4"
    if has_ttm:
        return "ttm"
    if "forward" in lower or "konsens" in lower or "consensus" in lower or "guidance" in lower:
        return "forward"
    if re.search(r"\bfy\d{4}\b|\bfy\b|fiscal year|geschäftsjahr", lower):
        return "fy"
    return "unknown"


def _dedupe_claims(claims: list[ExtractedNumericClaim]) -> list[ExtractedNumericClaim]:
    deduped: list[ExtractedNumericClaim] = []
    seen: set[tuple[int, str, str]] = set()
    for claim in claims:
        key = (claim.line_number, claim.raw_text, claim.unit or "")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(claim)
    return deduped
