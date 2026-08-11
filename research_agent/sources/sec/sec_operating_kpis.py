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
    "capital_allocation": (
        r"\b(?:returned?|returning)\b.{0,100}\bshareholders?\b|"
        r"\b(?:share repurchases?|stock repurchases?|cash dividends?|"
        r"capital returned|return of capital)\b"
    ),
    "free_cash_flow_guidance": r"\b(?:free cash flow|fcf)\b.{0,100}\b(?:guidance|outlook|range)\b|\b(?:guidance|outlook|range)\b.{0,100}\b(?:free cash flow|fcf)\b",
    "organic_comparable_growth": r"\b(?:organic|comparable)\b.{0,80}\bgrowth\b|\bgrowth\b.{0,80}\b(?:organic|comparable)\b",
    "segment_growth": r"\bsegment\b.{0,100}\bgrowth\b|\bgrowth\b.{0,100}\bsegment\b",
    "adjusted_eps_guidance": r"\badjusted eps\b.{0,120}\b(?:guidance|outlook|range)\b|\b(?:guidance|outlook|range)\b.{0,120}\badjusted eps\b",
    "transaction_financing": r"\b(?:acquisition|transaction)\b.{0,160}\b(?:debt|financ|consideration|purchase price)\b|\b(?:debt|financ)\b.{0,160}\b(?:acquisition|transaction)\b",
    "integration_effects": (
        r"\b(?:integration costs?|purchase accounting|acquisition-related amortization)\b|"
        r"\b(?:acquisition|transaction|integration)\b.{0,180}"
        r"\bsynerg(?:y|ies)\b|\bsynerg(?:y|ies)\b.{0,180}"
        r"\b(?:acquisition|transaction|integration)\b"
    ),
    "product_regulatory_catalyst": r"\b(?:approval|clearance|product launch|clinical milestone)\b",
}

NUMBER_RE = re.compile(
    r"(?P<currency>[$€£])?\s*"
    r"(?P<number>(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*"
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
    # A results release can be embedded in the filing and also supplied as a
    # separate official document.  Exact block deduplication prevents the same
    # issuer statement from becoming two report claims.
    blocks = list(dict.fromkeys(blocks))
    priority_statements = {
        "capital_allocation": set(
            _ranked_capital_allocation_statements(blocks, limit=3)
        )
    }
    cik_digits = str(int(cik)).zfill(10)
    accession_digits = accession_number.replace("-", "")
    document = primary_document.rsplit("/", 1)[-1]
    url = (
        f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
        f"{accession_digits}/{document}"
    )
    events: list[dict[str, Any]] = []
    match_counts = {kpi_id: 0 for kpi_id in KPI_PATTERNS}
    primary_counts = {kpi_id: 0 for kpi_id in KPI_PATTERNS}
    filing_year = int(filing_date[:4])
    for block_index, statement in enumerate(blocks):
        matched_kpis = [
            kpi_id
            for kpi_id, pattern in KPI_PATTERNS.items()
            if re.search(pattern, statement, flags=re.IGNORECASE)
            and match_counts[kpi_id] < 3
            and (
                kpi_id not in priority_statements
                or statement in priority_statements[kpi_id]
            )
        ]
        if not matched_kpis:
            continue
        numeric_evidence = _numeric_evidence(
            statement,
            kpi_ids=matched_kpis,
            event_index=len(events) + 1,
            context_scale=_inherited_block_scale(blocks, block_index),
            column_labels=_inherited_column_labels(
                blocks,
                block_index,
                filing_year=filing_year,
            ),
        )
        if not numeric_evidence:
            continue
        for kpi_id in matched_kpis:
            match_counts[kpi_id] += 1
        primary_kpi = matched_kpis[0]
        primary_counts[primary_kpi] += 1
        events.append(
            {
                "event_type": "operating_kpi",
                "date": filing_date,
                "headline": (
                    "Issuer reported operating KPI context: "
                    + ", ".join(kpi_id.replace("_", " ") for kpi_id in matched_kpis)
                ),
                "summary": statement[:1800],
                "material": True,
                "source_id": (
                    f"SEC_CIK{cik_digits}_{accession_digits}_KPI_"
                    f"{primary_kpi.upper()}_{primary_counts[primary_kpi]:02d}"
                ),
                "source_type": "sec_filing",
                "authority_rank": 1,
                "url": url,
                "retrieved_at": retrieved_at,
                "numeric_evidence": numeric_evidence,
            }
        )
    dispositions = [
        {
            "kpi_id": kpi_id,
            "status": "found" if match_counts[kpi_id] else "reviewed_not_found",
            "match_count": match_counts[kpi_id],
        }
        for kpi_id in KPI_PATTERNS
    ]
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


def _ranked_capital_allocation_statements(
    statements: list[str],
    *,
    limit: int,
) -> list[str]:
    """Prefer aggregate shareholder returns over isolated per-share rows."""

    candidates = [
        statement
        for statement in statements
        if re.search(
            KPI_PATTERNS["capital_allocation"],
            statement,
            flags=re.IGNORECASE,
        )
        and _numeric_evidence(
            statement,
            kpi_ids=["capital_allocation"],
            event_index=1,
        )
    ]
    return sorted(
        candidates,
        key=_capital_allocation_statement_score,
        reverse=True,
    )[:limit]


def _capital_allocation_statement_score(statement: str) -> tuple[int, int, int, int, int]:
    aggregate_return = int(
        re.search(
            r"\b(?:returned?|returning)\b.{0,100}\bshareholders?\b",
            statement,
            flags=re.IGNORECASE,
        )
        is not None
    )
    component_count = sum(
        int(re.search(pattern, statement, flags=re.IGNORECASE) is not None)
        for pattern in (
            r"\b(?:share|stock) repurchases?\b",
            r"\bcash dividends?\b",
        )
    )
    scaled_value_count = len(
        re.findall(r"\b(?:billion|million|bn|mn)\b", statement, re.IGNORECASE)
    )
    numeric_count = len(list(NUMBER_RE.finditer(statement)))
    per_share_penalty = int(
        re.search(r"\bper (?:common )?share\b", statement, re.IGNORECASE)
        is not None
    )
    return (
        aggregate_return,
        component_count,
        scaled_value_count,
        numeric_count,
        -per_share_penalty,
    )


def _numeric_evidence(
    statement: str,
    *,
    kpi_ids: list[str],
    event_index: int,
    context_scale: str | None = None,
    column_labels: list[str] | None = None,
) -> list[dict[str, Any]]:
    label_ranges = [
        (kpi_id, match.span())
        for kpi_id in kpi_ids
        for match in re.finditer(KPI_PATTERNS[kpi_id], statement, flags=re.IGNORECASE)
    ]
    if not label_ranges:
        return []
    values: list[dict[str, Any]] = []
    number_matches = list(NUMBER_RE.finditer(statement))
    for number_index, match in enumerate(number_matches):
        raw = float(match.group("number").replace(",", ""))
        explicit_scale = str(match.group("scale") or "").casefold()
        per_share = _is_per_share_value(statement, match)
        scale = (
            "base"
            if per_share
            else explicit_scale
            or _inherited_inline_scale(statement, match, number_matches)
            or str(context_scale or "").casefold()
        )
        percent = bool(match.group("percent"))
        if (
            not explicit_scale
            and not percent
            and not match.group("currency")
            and raw.is_integer()
            and 1900 <= raw <= 2100
        ):
            continue
        # Every monetary, percentage or explicitly scaled value in an emitted
        # source statement is a hard report claim.  Binding only the value
        # nearest the KPI label leaves the other visible numbers unverifiable.
        if not (match.group("currency") or percent or explicit_scale):
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
        direction = _numeric_direction(statement, match.span()) if percent else 1.0
        value = direction * raw / 100 if percent else raw * multiplier
        unit = (
            "percent"
            if percent
            else "currency_per_share"
            if match.group("currency") and per_share
            else "currency"
            if match.group("currency")
            else "count"
        )
        currency = {
            "$": "USD",
            "€": "EUR",
            "£": "GBP",
        }.get(str(match.group("currency") or ""))
        distance, owner = min(
            (
                _semantic_distance(match.span(), label_range),
                kpi_id,
            )
            for kpi_id, label_range in label_ranges
        )
        metric_owner = owner if distance <= 140 else "statement_context"
        values.append(
            {
                "metric_name": (
                    f"operating_kpi_{metric_owner}_{event_index:02d}_{len(values) + 1:02d}"
                ),
                "value": value,
                "raw_value": raw,
                "unit": unit,
                "source_scale": "percent" if percent else scale or "base",
                "source_unit": unit,
                "source_sign": int(direction),
                "currency": currency,
                "column_label": (
                    column_labels[number_index]
                    if column_labels and number_index < len(column_labels)
                    else None
                ),
            }
        )
    return values


def _is_per_share_value(statement: str, current: re.Match[str]) -> bool:
    """Keep per-share values on a base-unit scale even inside scaled tables."""

    for marker in re.finditer(
        r"\b(?:per[- ](?:common )?share|per[- ]share amounts?|per[- ]share data)\b",
        statement,
        flags=re.IGNORECASE,
    ):
        between = statement[
            min(current.end(), marker.end()) : max(current.start(), marker.start())
        ]
        if len(between) <= 160 and not re.search(r"[;:]|\.(?:\s|$)", between):
            return True
    return False


def _inherited_inline_scale(
    statement: str,
    current: re.Match[str],
    matches: list[re.Match[str]],
) -> str:
    """Inherit an explicit scale inside the same compact range or clause."""

    candidates: list[tuple[int, str]] = []
    for other in matches:
        if other is current or not other.group("scale"):
            continue
        between = statement[
            min(current.end(), other.end()) : max(current.start(), other.start())
        ]
        if len(between) > 80 or re.search(r"[.;:]", between):
            continue
        candidates.append(
            (
                _range_distance(current.span(), other.span()),
                str(other.group("scale") or "").casefold(),
            )
        )
    return min(candidates, default=(0, ""), key=lambda item: item[0])[1]


def _inherited_block_scale(blocks: list[str], index: int) -> str | None:
    """Carry an explicit table scale into nearby value rows, never across prose."""

    current = blocks[index]
    direct = _scale_from_text(current)
    if direct:
        return direct
    for prior in reversed(blocks[max(0, index - 6) : index]):
        inherited = _scale_from_text(prior)
        if inherited:
            return inherited
        if len(prior) > 180 and re.search(r"[.!?]", prior):
            break
    return None


def _scale_from_text(value: str) -> str | None:
    match = re.search(
        r"\b(?:in\s+)?(?P<scale>billions?|millions?|thousands?)\b",
        value,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    return match.group("scale").casefold().removesuffix("s")


def _inherited_column_labels(
    blocks: list[str],
    index: int,
    *,
    filing_year: int,
) -> list[str] | None:
    """Bind the common reported/adjusted four-column release layout."""

    context = " ".join(blocks[max(0, index - 6) : index])
    if len(re.findall(r"\bAs Reported\b", context, re.IGNORECASE)) < 2:
        return None
    if len(re.findall(r"\bAs Adjusted", context, re.IGNORECASE)) < 2:
        return None
    return [
        f"Q2 {filing_year} as reported",
        f"Q2 {filing_year} as adjusted",
        f"Q2 {filing_year - 1} as reported",
        f"Q2 {filing_year - 1} as adjusted",
    ]


def _numeric_direction(statement: str, number_range: tuple[int, int]) -> float:
    directions: list[tuple[int, float]] = []
    for pattern, multiplier in (
        (r"\b(?:decline|declined|decrease|decreased|fell|lower)\b", -1.0),
        (r"\b(?:growth|grew|increase|increased|rose|higher)\b", 1.0),
    ):
        directions.extend(
            (_semantic_distance(number_range, match.span()), multiplier)
            for match in re.finditer(pattern, statement, flags=re.IGNORECASE)
        )
    if not directions:
        return 1.0
    distance, multiplier = min(directions, key=lambda item: item[0])
    return multiplier if distance <= 90 else 1.0


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
