"""Extract source-bound operating KPI statements from official SEC filings."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any


KPI_PATTERNS = {
    "paid_members": r"\bpaid members(?:hips?)?\b",
    "cardholders": r"\bcardholders?\b",
    "renewal_rate": r"\brenewal rates?\b",
    "comparable_sales": r"\b(?:comparable sales|comp sales)\b",
    "traffic_frequency": r"\b(?:traffic|frequency)\b",
    "average_ticket": r"\b(?:average ticket|ticket|basket)\b",
    "digital_sales": r"\b(?:digital sales|e-?commerce)\b",
    "collection_disposal_yield": r"\b(?:collection and disposal yield|yield)\b",
    "volume": r"\bvolume\b",
    "operating_ebitda": r"\b(?:operating ebitda|adjusted ebitda|ebitda margin)\b",
    "free_cash_flow_guidance": r"\b(?:free cash flow|fcf)\b.{0,100}\b(?:guidance|outlook|range)\b|\b(?:guidance|outlook|range)\b.{0,100}\b(?:free cash flow|fcf)\b",
    "organic_comparable_growth": r"\b(?:organic|comparable)\b.{0,80}\bgrowth\b|\bgrowth\b.{0,80}\b(?:organic|comparable)\b",
    "segment_growth": r"\bsegment\b.{0,100}\bgrowth\b|\bgrowth\b.{0,100}\bsegment\b",
    "adjusted_eps_guidance": r"\badjusted eps\b.{0,120}\b(?:guidance|outlook|range)\b|\b(?:guidance|outlook|range)\b.{0,120}\badjusted eps\b",
    "transaction_financing": r"\b(?:acquisition|transaction)\b.{0,160}\b(?:debt|financ|consideration|purchase price)\b|\b(?:debt|financ)\b.{0,160}\b(?:acquisition|transaction)\b",
    "integration_effects": r"\b(?:integration costs?|amortization|purchase accounting)\b",
    "product_regulatory_catalyst": r"\b(?:approval|clearance|regulatory|product launch|clinical)\b",
}

NUMBER_RE = re.compile(
    r"(?P<currency>[$€£])?\s*(?P<number>\d+(?:[.,]\d+)?)\s*"
    r"(?P<scale>billion|million|thousand|bn|mn|m|k)?\s*(?P<percent>%)?",
    re.IGNORECASE,
)


class _BlockParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.blocks: list[str] = []
        self.parts: list[str] = []
        self.hidden = 0

    def _flush(self) -> None:
        text = " ".join("".join(self.parts).split())
        if text:
            self.blocks.append(text)
        self.parts = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style"}:
            self.hidden += 1
        elif not self.hidden and tag in {"br", "div", "p", "li", "tr", "h1", "h2", "h3"}:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        elif not self.hidden and tag in {"div", "p", "li", "tr", "h1", "h2", "h3"}:
            self._flush()

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)

    def finish(self) -> list[str]:
        self._flush()
        return self.blocks


def build_sec_operating_kpi_payload(
    *,
    ticker: str,
    cik: str,
    accession_number: str,
    filing_date: str,
    primary_document: str,
    html_documents: list[str],
    retrieved_at: str,
) -> dict[str, Any]:
    blocks: list[str] = []
    for html in html_documents:
        parser = _BlockParser()
        parser.feed(html)
        blocks.extend(parser.finish())
    cik_digits = str(int(cik)).zfill(10)
    accession_digits = accession_number.replace("-", "")
    document = primary_document.rsplit("/", 1)[-1]
    url = (
        f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
        f"{accession_digits}/{document}"
    )
    events: list[dict[str, Any]] = []
    dispositions: list[dict[str, Any]] = []
    for kpi_id, pattern in KPI_PATTERNS.items():
        matches: list[tuple[str, list[dict[str, Any]]]] = []
        for block in blocks:
            if not re.search(pattern, block, flags=re.IGNORECASE):
                continue
            numeric_evidence = _numeric_evidence(block, kpi_id=kpi_id)
            if numeric_evidence:
                matches.append((block, numeric_evidence))
            if len(matches) >= 3:
                break
        dispositions.append(
            {
                "kpi_id": kpi_id,
                "status": "found" if matches else "reviewed_not_found",
                "match_count": len(matches),
            }
        )
        for index, (statement, numeric_evidence) in enumerate(matches, start=1):
            # Metric identifiers are fact-ledger keys.  A filing can discuss the
            # same KPI more than once with different period values, so numbering
            # must include the statement occurrence as well as the value within
            # that statement.  Reusing ``..._01`` for every statement makes two
            # legitimate values look like a contradictory claim.
            scoped_numeric_evidence = [
                {
                    **item,
                    "metric_name": (
                        f"operating_kpi_{kpi_id}_{index:02d}_{numeric_index:02d}"
                    ),
                }
                for numeric_index, item in enumerate(numeric_evidence, start=1)
            ]
            events.append(
                {
                    "event_type": "operating_kpi",
                    "date": filing_date,
                    "headline": f"Issuer reported operating KPI: {kpi_id.replace('_', ' ')}",
                    "summary": statement[:1800],
                    "material": True,
                    "source_id": (
                        f"SEC_CIK{cik_digits}_{accession_digits}_KPI_"
                        f"{kpi_id.upper()}_{index:02d}"
                    ),
                    "source_type": "sec_filing",
                    "authority_rank": 1,
                    "url": url,
                    "retrieved_at": retrieved_at,
                    "numeric_evidence": scoped_numeric_evidence,
                }
            )
    return {
        "coverage_status": "complete",
        "checked_at": retrieved_at,
        "window_start": filing_date,
        "window_end": filing_date,
        "sources_checked": [url],
        "all_kpis_dispositioned": len(dispositions) == len(KPI_PATTERNS),
        "kpi_dispositions": dispositions,
        "events": events,
    }


def _numeric_evidence(statement: str, *, kpi_id: str) -> list[dict[str, Any]]:
    target_pattern = KPI_PATTERNS[kpi_id]
    target_ranges = [
        match.span()
        for match in re.finditer(target_pattern, statement, flags=re.IGNORECASE)
    ]
    if not target_ranges:
        return []
    competing_ranges = [
        match.span()
        for other_kpi, pattern in KPI_PATTERNS.items()
        if other_kpi != kpi_id
        for match in re.finditer(pattern, statement, flags=re.IGNORECASE)
    ]
    values: list[dict[str, Any]] = []
    for match in NUMBER_RE.finditer(statement):
        raw = float(match.group("number").replace(",", "."))
        scale = str(match.group("scale") or "").casefold()
        percent = bool(match.group("percent"))
        if (
            not scale
            and not percent
            and not match.group("currency")
            and raw.is_integer()
            and 1900 <= raw <= 2100
        ):
            continue
        target_distance = min(
            _semantic_distance(match.span(), target_range)
            for target_range in target_ranges
        )
        competing_distance = min(
            (
                _semantic_distance(match.span(), competing_range)
                for competing_range in competing_ranges
            ),
            default=10_000,
        )
        if target_distance > 140 or competing_distance < target_distance:
            continue
        multiplier = {
            "billion": 1_000_000_000,
            "bn": 1_000_000_000,
            "million": 1_000_000,
            "mn": 1_000_000,
            "m": 1_000_000,
            "thousand": 1_000,
            "k": 1_000,
        }.get(scale, 1)
        value = raw / 100 if percent else raw * multiplier
        unit = "percent" if percent else "currency" if match.group("currency") else "count"
        values.append(
            {
                "metric_name": f"operating_kpi_{kpi_id}_{len(values) + 1:02d}",
                "value": value,
                "raw_value": raw,
                "unit": unit,
            }
        )
    return values


def _range_distance(left: tuple[int, int], right: tuple[int, int]) -> int:
    if left[1] < right[0]:
        return right[0] - left[1]
    if right[1] < left[0]:
        return left[0] - right[1]
    return 0


def _semantic_distance(number_range: tuple[int, int], label_range: tuple[int, int]) -> int:
    distance = _range_distance(number_range, label_range)
    # In financial prose, a label followed by its value is the dominant form
    # ("paid members were 82.9m"). A following label normally owns the next
    # number, not the number immediately before it.
    return distance + (40 if label_range[0] >= number_range[1] else 0)
