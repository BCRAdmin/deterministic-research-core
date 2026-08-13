from __future__ import annotations

import re
from typing import Iterable, Optional

from research_agent.audit.audit_report import ExtractedNumericClaim
from research_agent.audit.claim_mapper import infer_possible_metric


DATE_RE = re.compile(
    r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{4}|"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|"
    r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+"
    r"\d{1,2},\s*\d{4})\b",
    re.IGNORECASE,
)
PERCENT_RE = re.compile(r"(?<![\w$])([+-]?\d+(?:[.,]\d+)?)\s*(?:%|Prozent)", re.IGNORECASE)
MULTIPLE_RE = re.compile(r"(?<![\w$])([+-]?\d+(?:[.,]\d+)?)\s*-?\s*(?:x|faches|fach|fache)\b", re.IGNORECASE)
PLAIN_NUMBER_RE = re.compile(
    r"(?<![\w$])(?P<number>[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*"
    r"(?P<scale>billion|million|thousand|bn|mn|m|k)?(?![\w])",
    re.IGNORECASE,
)
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
PLAIN_COUNT_CONTEXT_RE = re.compile(
    r"\b(?:members?|cardholders?|customers?|subscribers?|warehouses?|stores?|"
    r"locations?|shares?|employees?|units?|patients?)\b",
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
                source_start=match.start(),
            )
        )

    currency_matches = list(_iter_currency_matches(line))
    for match, currency in currency_matches:
        scale = match.group("scale") or _inherited_currency_scale(
            line,
            match,
            [item[0] for item in currency_matches],
        )
        claims.append(
            _claim(
                raw_text=match.group(0),
                value=_normalize_number(
                    f"{match.groupdict().get('leading_sign') or ''}{match.group('number')}",
                    scale,
                ),
                unit=currency,
                nearby_text=nearby,
                line_number=line_number,
                metric_context=_metric_context(line, match.start(), match.end()),
                source_start=match.start(),
            )
        )

    for match in PERCENT_RE.finditer(line):
        metric_context = _metric_context(line, match.start(), match.end())
        claims.append(
            _claim(
                raw_text=match.group(0),
                value=_normalize_directional_percent(
                    _normalize_plain_number(match.group(1)),
                    metric_context,
                ),
                unit="percent",
                nearby_text=nearby,
                line_number=line_number,
                metric_context=metric_context,
                source_start=match.start(),
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
                source_start=match.start(),
            )
        )

    occupied = [
        item.span()
        for regex in (DATE_RE, PERCENT_RE, MULTIPLE_RE)
        for item in regex.finditer(line)
    ]
    occupied.extend(match.span() for match, _ in currency_matches)
    occupied.extend(match.span() for match in re.finditer(r"`[^`]*`|<!--.*?-->", line))
    for match in PLAIN_NUMBER_RE.finditer(line):
        if any(_spans_overlap(match.span(), span) for span in occupied):
            continue
        if _plain_number_is_non_material(line, match):
            continue
        claims.append(
            _claim(
                raw_text=match.group(0).strip(),
                value=_normalize_number(match.group("number"), match.group("scale")),
                unit="count",
                nearby_text=nearby,
                line_number=line_number,
                metric_context=_metric_context(line, match.start(), match.end()),
                source_start=match.start(),
            )
        )

    return sorted(claims, key=lambda item: item.source_start or 0)


def _spans_overlap(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return left[0] < right[1] and right[0] < left[1]


def _plain_number_is_non_material(line: str, match: re.Match[str]) -> bool:
    value = float(match.group("number").replace(",", ""))
    before = line[max(0, match.start() - 30) : match.start()]
    after = line[match.end() : match.end() + 24]
    if not match.group("scale") and not PLAIN_COUNT_CONTEXT_RE.search(line):
        return True
    if str(match.group("scale") or "").casefold() == "m" and re.match(
        r"\s+(?:ended|period|results?)\b",
        after,
        re.IGNORECASE,
    ):
        return True
    if not match.group("scale") and value.is_integer() and 1900 <= value <= 2100:
        return True
    if re.match(r"\s*(?:-|–|—)?\s*(?:SMA|week|weeks|day|days|month|months|year|years)\b", after, re.IGNORECASE):
        return True
    if re.search(r"(?:^|\s)\d+[.)]\s*$", line[: match.end()]):
        return True
    if re.search(r"\b(?:CIK|ISIN|WKN|accession|claim|evidence|source)\s*[:#-]?\s*$", before, re.IGNORECASE):
        return True
    return False


def _inherited_currency_scale(
    line: str,
    current: re.Match[str],
    matches: list[re.Match[str]],
) -> Optional[str]:
    """Apply an explicitly stated range scale to the unscaled range bound."""

    candidates: list[tuple[int, str]] = []
    for other in matches:
        scale = other.group("scale")
        if other is current or not scale:
            continue
        between = line[
            min(current.end(), other.end()) : max(current.start(), other.start())
        ]
        if len(between) > 80 or re.search(r"[.;:]", between):
            continue
        candidates.append((_span_distance(*current.span(), *other.span()), scale))
    return min(candidates, default=(0, None), key=lambda item: item[0])[1]


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
    source_start: Optional[int] = None,
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
        source_start=source_start,
    )


def _metric_context(line: str, start: int, end: int) -> str:
    # Include the label after a value (for example ``10% discount rate``) as
    # well as the lead-in before it. A one-sided window misclassified DCF
    # assumptions as the nearest earlier FCF or price metric.
    left = line[max(0, start - 56) : start]
    right = line[end : min(len(line), end + 28)]
    return f"{left} metricvalueanchor {right}"


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


def _normalize_directional_percent(value: float, context: str) -> float:
    if value < 0:
        return value
    anchor = context.casefold().find("metricvalueanchor")
    anchor_end = anchor + len("metricvalueanchor") if anchor >= 0 else anchor
    direction_markers = [
        (_span_distance(match.start(), match.end(), anchor, anchor_end), -1.0)
        for match in re.finditer(
            r"\b(?:decline|declined|decrease|decreased|fell)\b",
            context,
            re.IGNORECASE,
        )
    ]
    direction_markers.extend(
        (_span_distance(match.start(), match.end(), anchor, anchor_end), 1.0)
        for match in re.finditer(
            r"\b(?:growth|increase|increased|rose)\b",
            context,
            re.IGNORECASE,
        )
    )
    if not direction_markers:
        return value
    return abs(value) * min(direction_markers, key=lambda item: item[0])[1]


def _span_distance(start: int, end: int, anchor_start: int, anchor_end: int) -> int:
    if anchor_start < 0:
        return start
    if end <= anchor_start:
        return anchor_start - end
    if start >= anchor_end:
        return start - anchor_end
    return 0


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
    seen: set[tuple[int, int | None, str, str]] = set()
    for claim in claims:
        key = (
            claim.line_number,
            claim.source_start,
            claim.raw_text,
            claim.unit or "",
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(claim)
    return deduped
