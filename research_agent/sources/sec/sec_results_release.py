from __future__ import annotations

import re
import unicodedata
from collections import Counter
from datetime import datetime
from html.parser import HTMLParser
from pathlib import PurePosixPath
from typing import Any, Optional
from urllib.parse import unquote, urlsplit


_RESULT_LINK_LANGUAGE = re.compile(
    r"\b(?:earnings|financial results?|press release|news release|investor release|quarterly results?)\b",
    re.IGNORECASE,
)
_PRIMARY_RESULTS_LINK_LANGUAGE = re.compile(r"\b(?:press|news|investor) release\b", re.IGNORECASE)
_SUPPLEMENTAL_RESULTS_LINK_LANGUAGE = re.compile(
    r"\b(?:infographic|presentation|supplement(?:al)?)\b",
    re.IGNORECASE,
)
_EXHIBIT_99_LABEL = re.compile(
    r"^(?:exhibit\s*)?99(?:[. -]?[0-9]+)?$",
    re.IGNORECASE,
)
_QUARTER_WORDS = {
    "first": "Q1",
    "second": "Q2",
    "third": "Q3",
    "fourth": "Q4",
}
_QUARTER_PATTERNS = (
    re.compile(
        r"\b(first|second|third|fourth)[ -]+(?:fiscal[ -]+)?quarter"
        r".{0,100}?\b(20[0-9]{2})\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bQ([1-4])\s*(?:FY)?\s*(20[0-9]{2})\b", re.IGNORECASE),
    re.compile(r"\b([1-4])Q\s*(20[0-9]{2})\b", re.IGNORECASE),
)
_FISCAL_YEAR_PATTERNS = (
    re.compile(
        r"\b(?:fiscal|full)[ -]+year\s*(20[0-9]{2})\s+(?:financial\s+)?results\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bFY\s*(20[0-9]{2})\s+(?:financial\s+)?results\b", re.IGNORECASE),
)
_PERCENT = re.compile(
    r"(?P<leading>[+-]?)\s*(?P<open>\()?\s*"
    r"(?P<value>[0-9]+(?:\.[0-9]+)?)\s*(?P<close_before>\))?\s*%"
    r"(?P<close_after>\))?"
)
_BARE_PERCENT = re.compile(
    r"^\s*(?P<leading>[+-]?)\s*(?P<open>\()?\s*"
    r"(?P<value>[0-9]+(?:\.[0-9]+)?)\s*(?P<close>\))?\s*$"
)
_GUIDANCE_LABELS = (
    (re.compile(r"\borganic sales growth\b", re.IGNORECASE), "organic_sales_growth"),
    (re.compile(r"\borganic revenue growth\b", re.IGNORECASE), "organic_revenue_growth"),
    (re.compile(r"\bnet sales\b", re.IGNORECASE), "net_sales_growth"),
    (re.compile(r"\brevenue growth\b", re.IGNORECASE), "revenue_growth"),
)
_HEADLINE_RESULT_LABELS = (
    (re.compile(r"^organic sales(?: growth| change)?$", re.IGNORECASE), "organic_sales_growth"),
    (re.compile(r"^organic revenue(?: growth| change)?$", re.IGNORECASE), "organic_revenue_growth"),
    (
        re.compile(r"^comparable sales(?: growth| change)?$", re.IGNORECASE),
        "comparable_sales_growth",
    ),
)


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: Optional[str] = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        self._href = str(dict(attrs).get("href") or "").strip()
        self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._href is None:
            return
        self.links.append((self._href, " ".join("".join(self._parts).split())))
        self._href = None
        self._parts = []


class _ReleaseParser(HTMLParser):
    _BLOCK_TAGS = {"br", "div", "h1", "h2", "h3", "h4", "li", "p", "tr"}

    def __init__(self) -> None:
        super().__init__()
        self.blocks: list[str] = []
        self.tables: list[list[list[str]]] = []
        self._hidden_depth = 0
        self._block_parts: list[str] = []
        self._table_depth = 0
        self._rows: list[list[str]] = []
        self._row: Optional[list[str]] = None
        self._cell_parts: Optional[list[str]] = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._hidden_depth += 1
            return
        if self._hidden_depth:
            return
        if tag in self._BLOCK_TAGS:
            self._flush_block()
        if tag == "table":
            if self._table_depth == 0:
                self._rows = []
            self._table_depth += 1
        elif self._table_depth == 1 and tag == "tr":
            self._row = []
        elif self._table_depth == 1 and tag in {"td", "th"}:
            self._cell_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self._hidden_depth = max(0, self._hidden_depth - 1)
            return
        if self._hidden_depth:
            return
        if tag in self._BLOCK_TAGS:
            self._flush_block()
        if self._table_depth == 1 and tag in {"td", "th"}:
            if self._row is not None and self._cell_parts is not None:
                self._row.append(" ".join("".join(self._cell_parts).split()))
            self._cell_parts = None
        elif self._table_depth == 1 and tag == "tr":
            if self._row is not None and any(self._row):
                self._rows.append(self._row)
            self._row = None
        elif tag == "table" and self._table_depth:
            self._table_depth -= 1
            if self._table_depth == 0:
                if self._rows:
                    self.tables.append(self._rows)
                self._rows = []

    def handle_data(self, data: str) -> None:
        if self._hidden_depth:
            return
        self._block_parts.append(data)
        if self._cell_parts is not None:
            self._cell_parts.append(data)

    def _flush_block(self) -> None:
        text = " ".join("".join(self._block_parts).split())
        if text:
            self.blocks.append(text)
        self._block_parts = []


def select_sec_results_exhibit(primary_html: str) -> str:
    """Select one issuer results exhibit from the Item 2.02 filing body."""

    parser = _LinkParser()
    parser.feed(primary_html)
    labels_by_document: dict[str, list[str]] = {}
    for href, label in parser.links:
        document = _safe_html_document(href)
        if document is None:
            continue
        labels_by_document.setdefault(document, []).append(label)

    candidates: dict[str, int] = {}
    for document, labels in labels_by_document.items():
        # SEC inline-XBRL filing bodies may split one visible exhibit
        # description across many anchors that all target the same document.
        # Score the complete visible description per target rather than the
        # strongest isolated fragment. This preserves the distinction between
        # a primary investor release and a supplemental exhibit without using
        # issuer- or filename-specific exceptions.
        combined_label = " ".join(" ".join(labels).split())
        score = 0
        if _RESULT_LINK_LANGUAGE.search(combined_label):
            score += 5
        if _PRIMARY_RESULTS_LINK_LANGUAGE.search(combined_label):
            score += 3
        if _SUPPLEMENTAL_RESULTS_LINK_LANGUAGE.search(combined_label):
            score -= 2
        if any(_EXHIBIT_99_LABEL.fullmatch(" ".join(label.split())) for label in labels):
            score += 4
        if _RESULT_LINK_LANGUAGE.search(document.replace("_", " ").replace("-", " ")):
            score += 2
        if score:
            candidates[document] = score
    if not candidates:
        raise ValueError("kein eindeutig verlinkter Ergebnis-Anhang gefunden")
    best_score = max(candidates.values())
    best = sorted(document for document, score in candidates.items() if score == best_score)
    if len(best) != 1:
        raise ValueError("mehrere gleichwertige Ergebnis-Anhänge gefunden")
    return best[0]


def build_sec_results_release_payload(
    *,
    ticker: str,
    cik: str,
    accession_number: str,
    filing_date: str,
    exhibit_document: str,
    html: str,
    expected_fiscal_year: int,
    expected_fiscal_period: str,
    period_end_date: str,
    retrieved_at: str,
) -> dict[str, Any]:
    """Convert a structurally supported SEC results exhibit into pipeline inputs.

    This adapter intentionally does not rebuild GAAP statements from press-release
    prose. It only accepts an exhibit whose fiscal period is already covered by the
    current 10-Q/10-K CompanyFacts accession and extracts issuer-defined operating
    bridges, division comparisons, and explicit guidance ranges.
    """

    parser = _ReleaseParser()
    parser.feed(html)
    fiscal_year, fiscal_period = _detect_release_period(
        parser.blocks,
        parser.tables,
        expected_fiscal_year=int(expected_fiscal_year),
        expected_fiscal_period=str(expected_fiscal_period or "").upper(),
    )
    expected_period = str(expected_fiscal_period or "").upper()
    if (fiscal_year, fiscal_period) != (int(expected_fiscal_year), expected_period):
        raise ValueError(
            f"Ergebnis-Anhang meldet FY{fiscal_year}_{fiscal_period}, der aktuelle "
            f"CompanyFacts-Bericht endet jedoch bei FY{int(expected_fiscal_year)}_"
            f"{expected_period}"
        )

    values: dict[str, float] = {}
    metric_labels: dict[str, str] = {}
    metric_units: dict[str, str] = {}
    metric_bases: dict[str, str] = {}
    metric_period_buckets: dict[str, str] = {}
    metric_guidance_periods: dict[str, tuple[str, int, str]] = {}
    metric_bound_types: dict[str, str] = {}
    headline_controls: dict[str, float] = {}

    def add_value(
        metric_name: str,
        value: float,
        *,
        display_label: str = "",
        unit: str = "percent",
        basis: str = "company_defined",
        period_bucket: str = "quarterly",
        guidance_period: Optional[tuple[str, int, str]] = None,
        bound_type: Optional[str] = None,
    ) -> None:
        previous = values.get(metric_name)
        if previous is not None and abs(previous - value) > 1e-9:
            raise ValueError(f"widersprüchliche Ergebniswerte für {metric_name}")
        values[metric_name] = value
        if display_label:
            metric_labels[metric_name] = display_label
        metric_units[metric_name] = unit
        metric_bases[metric_name] = basis
        metric_period_buckets[metric_name] = period_bucket
        if guidance_period is not None:
            previous_guidance_period = metric_guidance_periods.get(metric_name)
            if previous_guidance_period is not None and previous_guidance_period != guidance_period:
                raise ValueError(f"widersprüchliche Guidance-Periode für {metric_name}")
            metric_guidance_periods[metric_name] = guidance_period
        if bound_type is not None:
            metric_bound_types[metric_name] = bound_type

    headline_summary_extracted = False
    for table in parser.tables:
        if not headline_summary_extracted:
            headline_summary_extracted = _extract_headline_summary_metrics(
                table,
                add_value,
                headline_controls,
            )
        _extract_headline_operating_metrics(table, add_value)
        _extract_company_bridge_metrics(table, add_value)
        _extract_transposed_segment_bridge_metrics(table, add_value)
        _extract_sectioned_segment_metrics(table, add_value)
        _extract_current_guidance_metrics(table, add_value)
    _extract_headline_block_metrics(parser.blocks, add_value, headline_controls)

    guidance_years: set[int] = set()
    for index, block in enumerate(parser.blocks):
        if "expect" not in block.casefold() and "guid" not in block.casefold():
            continue
        guidance_scope = _forward_guidance_scope(block)
        if not guidance_scope:
            continue
        guidance_year = _nearest_guidance_year(parser.blocks, index, fiscal_year)
        for label_pattern, metric_base in _GUIDANCE_LABELS:
            label_match = label_pattern.search(guidance_scope)
            if label_match is None:
                continue
            range_match = _percentage_range(guidance_scope[label_match.end() :])
            if range_match is None:
                continue
            low, high = sorted(range_match)
            guidance_years.add(guidance_year)
            add_value(f"guidance_{metric_base}_low", low)
            add_value(f"guidance_{metric_base}_high", high)
            break
    guidance_years.update(_extract_block_guidance_metrics(parser.blocks, add_value, fiscal_year))

    supported_operating = [
        metric_name for metric_name in values if not metric_name.startswith("guidance_")
    ]
    supported_guidance = [
        metric_name for metric_name in values if metric_name.startswith("guidance_")
    ]
    cik_digits = str(int(cik))
    accession_digits = accession_number.replace("-", "")
    document = _safe_html_document(exhibit_document)
    if document is None or not accession_digits.isdigit():
        raise ValueError("ungültige SEC-Ergebnisidentität")
    source_id = (
        f"SEC_CIK{cik_digits.zfill(10)}_{accession_digits}_"
        f"{_slug(document.rsplit('.', 1)[0], max_length=36).upper()}"
    )
    source_url = (
        f"https://www.sec.gov/Archives/edgar/data/{cik_digits}/{accession_digits}/{document}"
    )
    result_period = f"FY{fiscal_year}_{fiscal_period}"
    guidance_year = max(guidance_years) if guidance_years else fiscal_year
    metrics: list[dict[str, Any]] = []
    for metric_name, value in sorted(values.items()):
        is_guidance = metric_name.startswith("guidance_")
        guidance_period = metric_guidance_periods.get(metric_name)
        if is_guidance and guidance_period is not None:
            period, metric_fiscal_year, metric_fiscal_period = guidance_period
        elif is_guidance:
            period = f"FY{guidance_year}"
            metric_fiscal_year = guidance_year
            metric_fiscal_period = "FY"
        else:
            period = result_period
            metric_fiscal_year = fiscal_year
            metric_fiscal_period = fiscal_period
        period_bucket = metric_period_buckets.get(metric_name, "quarterly")
        label = _metric_label(metric_name, metric_labels.get(metric_name))
        metric_period = f"FY{fiscal_year}_YTD" if period_bucket == "ytd" else period
        metrics.append(
            {
                "metric_name": metric_name,
                "value": value,
                "unit": metric_units.get(metric_name, "percent"),
                "period": metric_period,
                "period_bucket": "guidance" if is_guidance else period_bucket,
                "fiscal_year": metric_fiscal_year if is_guidance else fiscal_year,
                "fiscal_period": metric_fiscal_period if is_guidance else fiscal_period,
                "end_date": filing_date if is_guidance else period_end_date,
                "date": filing_date if is_guidance else period_end_date,
                "basis": metric_bases.get(metric_name, "company_defined"),
                "statement_type": "guidance" if is_guidance else "income_statement",
                "claim_type": "guidance" if is_guidance else "financial_metric",
                "statement": (
                    f"{ticker.upper()} filed {label} of "
                    f"{_format_metric_value(value, metric_units.get(metric_name, 'percent'))} "
                    f"for {metric_period}."
                ),
                "supports_metrics": [metric_name],
                "reconciliation_note": (
                    "Issuer-defined SEC Item 2.02 result metric; GAAP statement "
                    "figures remain sourced from the matching CompanyFacts filing."
                ),
                "bound_type": metric_bound_types.get(metric_name),
            }
        )

    events: list[dict[str, Any]] = [
        {
            "event_type": "earnings_release",
            "date": filing_date,
            "headline": f"Issuer filed {result_period} financial results",
            "summary": (
                f"The issuer filed results for {result_period} through SEC Form "
                "8-K Item 2.02. GAAP statement figures remain sourced from the "
                "matching 10-Q/10-K filing."
            ),
            "material": True,
            "source_id": source_id,
            "source_type": "sec_filing",
            "authority_rank": 1,
            "url": source_url,
            "retrieved_at": retrieved_at,
        }
    ]
    if any(metric_name.startswith("segment_") for metric_name in values):
        events.append(
            {
                "event_type": "business_context",
                "date": filing_date,
                "headline": "Issuer filed segment- or region-level operating results",
                "summary": (
                    "The issuer disclosed segment- or region-level organic-sales "
                    "performance for the latest reported quarter."
                ),
                "material": True,
                "source_id": source_id,
                "source_type": "sec_filing",
                "authority_rank": 1,
                "url": source_url,
                "retrieved_at": retrieved_at,
            }
        )
    directional = _directional_guidance_events(
        parser.blocks,
        source_id=source_id,
        source_url=source_url,
        filing_date=filing_date,
        retrieved_at=retrieved_at,
    )
    events.extend(directional)
    structured_guidance = _structured_guidance_event(
        metrics,
        parser.blocks,
        source_id=source_id,
        source_url=source_url,
        filing_date=filing_date,
        retrieved_at=retrieved_at,
    )
    if structured_guidance is not None:
        events.append(structured_guidance)
    events.extend(
        _material_result_context_events(
            parser.blocks,
            source_id=source_id,
            source_url=source_url,
            filing_date=filing_date,
            retrieved_at=retrieved_at,
        )
    )
    return {
        "source_id": source_id,
        "source_type": "sec_filing",
        "url": source_url,
        "retrieved_at": retrieved_at,
        "period": result_period,
        "coverage_status": "available",
        "checked_at": retrieved_at,
        "window_start": filing_date,
        "window_end": filing_date,
        "sources_checked": [source_url],
        "metrics": metrics,
        "events": events,
        "result_contract": {
            "form": "8-K",
            "item": "2.02",
            "accession_number": accession_number,
            "filing_date": filing_date,
            "exhibit_document": document,
            "fiscal_year": fiscal_year,
            "fiscal_period": fiscal_period,
            "period_end_date": period_end_date,
            "gaap_basis": "matching_companyfacts_filing",
            "companyfacts_controls": headline_controls,
            "operating_metric_count": len(supported_operating),
            "guidance_metric_count": len(supported_guidance),
        },
    }


def _forward_guidance_scope(block: str) -> str:
    """Ignore historical percentages that appear before forward guidance text."""

    matches = list(re.finditer(r"\b(?:guidance|expect(?:s|ed|ing)?)\b", block, re.IGNORECASE))
    if not matches:
        return ""
    return block[matches[0].start() :]


def _safe_html_document(href: str) -> Optional[str]:
    parsed = urlsplit(str(href or "").strip())
    path = unquote(parsed.path)
    document = PurePosixPath(path).name
    if not document or document in {".", ".."}:
        return None
    if not document.lower().endswith((".htm", ".html")):
        return None
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", document):
        return None
    return document


def _detect_release_period(
    blocks: list[str],
    tables: list[list[list[str]]],
    *,
    expected_fiscal_year: Optional[int] = None,
    expected_fiscal_period: Optional[str] = None,
) -> tuple[int, str]:
    candidates: list[tuple[int, str]] = []
    # Annual releases commonly place the full-year heading after a complete
    # fourth-quarter summary. Keep the scan bounded, but wide enough to reach
    # both period labels before applying the expected CompanyFacts period.
    sources = [*blocks[:160]]
    sources.extend(" ".join(cell for row in table[:4] for cell in row) for table in tables[:16])
    for source in sources:
        for pattern_index, pattern in enumerate(_QUARTER_PATTERNS):
            for match in pattern.finditer(source):
                if pattern_index == 0:
                    fiscal_period = _QUARTER_WORDS[match.group(1).lower()]
                    fiscal_year = int(match.group(2))
                else:
                    fiscal_period = f"Q{int(match.group(1))}"
                    fiscal_year = int(match.group(2))
                candidates.append((fiscal_year, fiscal_period))
        for pattern in _FISCAL_YEAR_PATTERNS:
            for match in pattern.finditer(source):
                candidates.append((int(match.group(1)), "FY"))
    if not candidates:
        raise ValueError("Quartalsperiode des Ergebnis-Anhangs nicht eindeutig erkannt")
    expected_year_candidates = [
        candidate
        for candidate in candidates
        if expected_fiscal_year is not None and candidate[0] == expected_fiscal_year
    ]
    if expected_year_candidates:
        candidates = expected_year_candidates
    expected_period_candidates = [
        candidate
        for candidate in candidates
        if expected_fiscal_period is not None and candidate[1] == expected_fiscal_period
    ]
    if expected_period_candidates:
        candidates = expected_period_candidates
    counts = Counter(candidates)
    best_count = max(counts.values())
    best = sorted(period for period, count in counts.items() if count == best_count)
    if len(best) != 1:
        raise ValueError("mehrere Ergebnisperioden im Anhang gleich stark erkannt")
    return best[0]


def _extract_headline_operating_metrics(table, add_value) -> None:
    if _is_guidance_table(table):
        return
    for row in table:
        if len(row) < 2:
            continue
        label = _clean_label(row[0])
        metric_name = next(
            (name for pattern, name in _HEADLINE_RESULT_LABELS if pattern.fullmatch(label)),
            None,
        )
        if metric_name is None:
            continue
        value = next(
            (parsed for cell in row[1:] if (parsed := _percent_value(cell)) is not None),
            None,
        )
        if value is not None:
            add_value(metric_name, value)


def _extract_headline_summary_metrics(table, add_value, controls: dict[str, float]) -> bool:
    """Extract the first consolidated current/prior/change summary table.

    Earnings releases can repeat the same layout for a post-separation or other
    alternative perimeter. Requiring Sales and adjusted EPS, then accepting only
    the first matching table, keeps those perimeters from being combined.
    """

    columns = _result_comparison_columns(table)
    if columns is None:
        return False
    current_column, change_column = columns
    rows = {_clean_result_label(row[0]): row for row in table if row and row[0].strip()}
    sales_row = next(
        (
            rows[label]
            for label in (
                "sales",
                "net sales",
                "revenue",
                "revenues",
                "total revenue",
                "total revenues",
            )
            if label in rows
        ),
        None,
    )
    adjusted_eps_row = next(
        (
            rows[label]
            for label in (
                "adjusted earnings per share",
                "adjusted diluted earnings per share",
                "adjusted diluted eps",
                "adjusted eps",
                "earnings/(loss) per share non gaap",
                "non gaap net income per share diluted",
            )
            if label in rows
        ),
        None,
    )
    if sales_row is None or adjusted_eps_row is None:
        return False

    for label, control_name in (
        ("sales", "current_quarter_revenue"),
        ("net sales", "current_quarter_revenue"),
        ("revenue", "current_quarter_revenue"),
        ("revenues", "current_quarter_revenue"),
        ("total revenue", "current_quarter_revenue"),
        ("total revenues", "current_quarter_revenue"),
        ("operating income", "current_quarter_operating_income"),
        ("segment profit", "current_quarter_segment_profit"),
    ):
        row = rows.get(label)
        if row is None or len(row) <= current_column:
            continue
        value = _result_current_money_value(row, current_column)
        if value is not None:
            controls[control_name] = value

    value = _result_change_percent(sales_row, change_column)
    if value is not None:
        sales_label = _clean_result_label(sales_row[0])
        metric_name = (
            "reported_revenue_growth"
            if sales_label in {"revenue", "revenues", "total revenue", "total revenues"}
            else "reported_sales_growth"
        )
        add_value(
            metric_name,
            value,
            display_label=(
                "reported-revenue growth"
                if metric_name == "reported_revenue_growth"
                else "reported-sales growth"
            ),
        )

    organic_row = next(
        (
            row
            for label, row in rows.items()
            if label in {"organic growth", "organic sales growth", "organic revenue growth"}
        ),
        None,
    )
    if organic_row is not None and len(organic_row) > change_column:
        value = _percent_value(organic_row[change_column])
        if value is not None:
            add_value(
                "organic_revenue_growth"
                if "revenue" in _clean_result_label(organic_row[0])
                else "organic_sales_growth",
                value,
            )

    segment_margin_row = rows.get("segment margin")
    if segment_margin_row is not None:
        if len(segment_margin_row) > current_column:
            margin = _percent_value(segment_margin_row[current_column])
            if margin is not None:
                add_value(
                    "current_period_segment_margin",
                    margin,
                    display_label="segment margin",
                    basis="non_gaap",
                )
        if len(segment_margin_row) > change_column:
            change = _basis_point_change(segment_margin_row[change_column])
            if change is not None:
                add_value(
                    "current_period_segment_margin_change_yoy",
                    change,
                    display_label="segment-margin change",
                    basis="non_gaap",
                )

    if len(adjusted_eps_row) > current_column:
        adjusted_eps = _result_current_money_value(
            adjusted_eps_row,
            current_column,
            allow_bare=True,
        )
        if adjusted_eps is not None:
            add_value(
                "adjusted_eps_diluted",
                adjusted_eps,
                display_label="adjusted diluted EPS",
                unit="USD_per_share",
                basis="non_gaap",
            )
    eps_change = _result_change_percent(adjusted_eps_row, change_column)
    if eps_change is not None:
        add_value(
            "adjusted_eps_growth_yoy",
            eps_change,
            display_label="adjusted diluted-EPS growth",
            basis="non_gaap",
        )
    return True


def _extract_sectioned_segment_metrics(table, add_value) -> None:
    columns = _result_comparison_columns(table)
    if columns is None:
        return
    _, change_column = columns
    current_segment = ""
    for row_index, row in enumerate(table):
        if not row or not row[0].strip():
            continue
        label = _clean_result_label(row[0])
        if row_index == 0 and len(row) > change_column:
            current_segment = _clean_segment_label(row[0])
            continue
        if all(not cell.strip() for cell in row[1:]):
            current_segment = _clean_segment_label(row[0])
            continue
        if label not in {
            "organic growth",
            "organic sales growth",
            "organic revenue growth",
        }:
            continue
        if not current_segment or len(row) <= change_column:
            continue
        value = _percent_value(row[change_column])
        if value is None:
            continue
        metric_name = f"segment_organic_sales_growth_{_slug(current_segment)}"
        add_value(metric_name, value, display_label=current_segment)


def _extract_current_guidance_metrics(table, add_value) -> None:
    guidance_table = _is_guidance_table(table)
    table_heading = " ".join(_clean_result_label(cell) for row in table[:2] for cell in row)
    table_non_gaap = "non gaap" in table_heading
    guidance_column = next(
        (
            column
            for row in table[:3]
            for column, cell in enumerate(row)
            if (
                re.match(
                    r"^(?:current|updated|revised)\b.{0,40}\b(?:guidance|outlook)\b",
                    _clean_result_label(cell),
                )
                or (
                    guidance_table
                    and re.search(
                        r"\b(?:current|updated|revised)\b",
                        _clean_result_label(cell),
                    )
                )
            )
        ),
        None,
    )
    if guidance_column is None:
        return
    prior_column = next(
        (
            column
            for row in table[:3]
            for column, cell in enumerate(row)
            if re.search(
                r"\b(?:prior|previous)\b",
                _clean_result_label(cell),
            )
        ),
        None,
    )
    value_column = (
        guidance_column + 1 if prior_column == 0 and guidance_column == 1 else guidance_column
    )
    guidance_period = _quarterly_guidance_period(table)
    definitions = {
        "sales": ("revenue", "USD", "company_defined"),
        "revenues": ("revenue", "USD", "company_defined"),
        "total revenues (reported & ex fx)": ("revenue", "USD", "company_defined"),
        "total revenues(reported & ex fx)": ("revenue", "USD", "company_defined"),
        "revenues ($ in billions) midpoint": ("revenue", "USD", "company_defined"),
        "qct revenues": ("qct_revenue", "USD", "company_defined"),
        "qtl revenues": ("qtl_revenue", "USD", "company_defined"),
        "reported sales growth": (
            "reported_sales_growth",
            "percent",
            "company_defined",
        ),
        "organic growth": ("organic_sales_growth", "percent", "company_defined"),
        "organic sales growth": ("organic_sales_growth", "percent", "company_defined"),
        "organic revenue growth": ("organic_revenue_growth", "percent", "company_defined"),
        "organic revenues (non gaap)": ("organic_revenue_growth", "percent", "non_gaap"),
        "comparable eps (non gaap)": ("adjusted_eps_growth", "percent", "non_gaap"),
        "comparable currency neutral eps excluding acquisitions and divestitures (non gaap)": (
            "adjusted_currency_neutral_eps_growth",
            "percent",
            "non_gaap",
        ),
        "free cash flow (non gaap)": ("free_cash_flow", "USD", "non_gaap"),
        "segment margin": ("segment_margin", "percent", "non_gaap"),
        "diluted eps": ("eps_diluted", "USD_per_share", "gaap"),
        "gaap diluted eps": ("eps_diluted", "USD_per_share", "gaap"),
        "adjusted earnings per share": ("adjusted_eps", "USD_per_share", "non_gaap"),
        "adjusted diluted eps": ("adjusted_eps", "USD_per_share", "non_gaap"),
        "adjusted eps": ("adjusted_eps", "USD_per_share", "non_gaap"),
        "non gaap diluted eps": ("adjusted_eps", "USD_per_share", "non_gaap"),
        "adjusted earnings growth": ("adjusted_eps_growth", "percent", "non_gaap"),
        "adjusted si&a expenses ($ in billions)": (
            "adjusted_sia_expense",
            "USD",
            "non_gaap",
        ),
        "adjusted r&d expenses ($ in billions)": (
            "adjusted_research_and_development_expense",
            "USD",
            "non_gaap",
        ),
    }
    for row in table:
        if not row or len(row) <= value_column:
            continue
        label = next(
            (
                _clean_result_label(cell)
                for cell in row[:value_column]
                if _clean_result_label(cell) in definitions
            ),
            "",
        )
        definition = definitions.get(label)
        if definition is None:
            continue
        if label == "diluted eps" and table_non_gaap:
            definition = ("adjusted_eps", "USD_per_share", "non_gaap")
        metric_base, unit, basis = definition
        cell = row[value_column]
        range_parser = (
            _percentage_range
            if unit == "percent"
            else lambda value: _labeled_money_range(
                value,
                label=label,
                require_scale=metric_base == "revenue",
            )
        )
        metric_range = range_parser(cell)
        if metric_range is None:
            metric_range = (
                _single_percentage_range(cell)
                if unit == "percent"
                else _single_money_range(
                    cell,
                    label=label,
                    require_scale=metric_base in {"revenue", "free_cash_flow"},
                )
            )
        if metric_range is None:
            metric_range = next(
                (
                    parsed
                    for column in (value_column - 1, value_column + 1)
                    if 0 <= column < len(row) and (parsed := range_parser(row[column])) is not None
                ),
                None,
            )
        if metric_range is None:
            continue
        low, high = sorted(metric_range)
        display_label = label.replace("earnings per share", "EPS")
        add_value(
            f"guidance_{metric_base}_low",
            low,
            display_label=f"{display_label} guidance lower bound",
            unit=unit,
            basis=basis,
            guidance_period=guidance_period,
        )
        add_value(
            f"guidance_{metric_base}_high",
            high,
            display_label=f"{display_label} guidance upper bound",
            unit=unit,
            basis=basis,
            guidance_period=guidance_period,
        )


def _quarterly_guidance_period(
    table: list[list[str]],
) -> Optional[tuple[str, int, str]]:
    heading = " ".join(cell for row in table[:3] for cell in row)
    match = re.search(
        r"\bQ(?P<quarter>[1-4])\s*(?:(?:fiscal|FY)\s*)?"
        r"(?P<year>20[0-9]{2}|[0-9]{2})\b",
        heading,
        re.IGNORECASE,
    )
    if match is None:
        match = re.search(
            r"\b(?P<quarter>first|second|third|fourth)\s+(?:fiscal\s+)?quarter"
            r".{0,30}?\b(?P<year>20[0-9]{2}|[0-9]{2})\b",
            heading,
            re.IGNORECASE,
        )
    if match is None:
        return None
    quarter_value = match.group("quarter").casefold()
    quarter = _QUARTER_WORDS.get(quarter_value, f"Q{quarter_value}")
    year = int(match.group("year"))
    if year < 100:
        year += 2000
    return f"FY{year}_{quarter}", year, quarter


def _extract_headline_block_metrics(
    blocks,
    add_value,
    controls: dict[str, float],
) -> None:
    adjusted_eps = re.compile(
        r"\b(?:Base Business|adjusted|non-GAAP)(?: diluted)? EPS(?:\d+)?\b.*?"
        r"\b(increased|decreased)\s+([0-9]+(?:\.[0-9]+)?)%\s+to\s+"
        r"\$([0-9]+(?:\.[0-9]+)?)",
        re.IGNORECASE,
    )
    comparable_sales = re.compile(
        r"\bcomparable sales(?: for the quarter)?\s+"
        r"(?P<direction>increased|decreased)\s+"
        r"(?P<change>[0-9]+(?:\.[0-9]+)?)%",
        re.IGNORECASE,
    )
    margin_result = re.compile(
        r"(?P<label>.{0,100}?gross profit margin.{0,100}?)\s+"
        r"(?P<direction>increased|decreased)\s+"
        r"(?P<bps>[0-9]+(?:\.[0-9]+)?)\s+basis points\s+to\s+"
        r"(?P<margin>[0-9]+(?:\.[0-9]+)?)%",
        re.IGNORECASE,
    )
    market_share = re.compile(
        r"\bleadership in\s+(?P<label>.{2,80}?)\s+continued\s+with\s+"
        r"(?:its|the)\s+global market share at\s+"
        r"(?P<share>[0-9]+(?:\.[0-9]+)?)%",
        re.IGNORECASE,
    )
    comparative_gaap_margin = re.compile(
        r"(?<!adjusted )\bgross(?: profit)? margin was\s+"
        r"(?P<current>[0-9]+(?:\.[0-9]+)?)\s*(?:%|percent)\s+"
        r"compared to\s+(?P<prior>[0-9]+(?:\.[0-9]+)?)\s*(?:%|percent)",
        re.IGNORECASE,
    )
    adjusted_margin_direct = re.compile(
        r"\badjusted gross(?: profit)? margin was\s+"
        r"(?P<margin>[0-9]+(?:\.[0-9]+)?)\s*(?:%|percent).*?"
        r"(?P<direction>down|decreased|up|increased|a decrease of|an increase of)\s+"
        r"(?P<bps>[0-9]+(?:\.[0-9]+)?)\s+basis points",
        re.IGNORECASE,
    )
    adjusted_eps_value_first = re.compile(
        r"\badjusted(?: diluted)? EPS from continuing operations\s+(?:was|were)\s+"
        r"\$(?P<value>[0-9]+(?:\.[0-9]+)?).*?"
        r"(?P<direction>down|declined|a decline of|decreased|up|increased|an increase of)\s+"
        r"(?P<change>[0-9]+(?:\.[0-9]+)?)\s*(?:%|percent)",
        re.IGNORECASE,
    )
    adjusted_eps_value_then_change = re.compile(
        r"\badjusted(?: diluted)? (?:earnings per share|EPS)\b.{0,40}?"
        r"(?:of|was|were)\s+\$(?P<value>[0-9]+(?:\.[0-9]+)?).*?"
        r"(?P<direction>increase|decrease)(?:d)?(?:\s+of)?\s+"
        r"(?P<change>[0-9]+(?:\.[0-9]+)?)\s*(?:%|percent)",
        re.IGNORECASE,
    )
    reported_revenue_result = re.compile(
        r"^[^A-Za-z0-9]*(?:(?:delivers|reports)\s+"
        r"(?:first|second|third|fourth)[ -]+quarter\s+)?"
        r"(?:worldwide\s+)?(?:net\s+)?revenues?\s+(?:of|was|were)\s+"
        r"\$(?P<value>[0-9][0-9,]*(?:\.[0-9]+)?)\s*"
        r"(?P<scale>million|billion)\b.*?"
        r"(?P<direction>increase|decrease)(?:d)?(?:\s+of)?\s+"
        r"(?P<change>[0-9]+(?:\.[0-9]+)?)\s*(?:%|percent)\s+"
        r"on\s+(?:a\s+)?reported\s+basis",
        re.IGNORECASE,
    )
    for block in blocks:
        if match := comparable_sales.search(block):
            direction = -1.0 if match.group("direction").casefold() == "decreased" else 1.0
            add_value(
                "comparable_sales_growth",
                direction * float(match.group("change")) / 100.0,
            )
        if match := adjusted_eps.search(block):
            sign = -1.0 if match.group(1).casefold() == "decreased" else 1.0
            add_value(
                "adjusted_eps_growth_yoy",
                sign * float(match.group(2)) / 100.0,
                display_label="adjusted diluted-EPS growth",
                basis="non_gaap",
            )
            add_value(
                "adjusted_eps_diluted",
                float(match.group(3)),
                display_label="adjusted diluted EPS",
                unit="USD_per_share",
                basis="non_gaap",
            )
        if match := adjusted_eps_value_first.search(block):
            negative = match.group("direction").casefold() in {
                "down",
                "declined",
                "a decline of",
                "decreased",
            }
            add_value(
                "adjusted_eps_growth_yoy",
                (-1.0 if negative else 1.0) * float(match.group("change")) / 100.0,
                display_label="adjusted continuing-operations EPS growth",
                basis="non_gaap",
            )
            add_value(
                "adjusted_eps_diluted",
                float(match.group("value")),
                display_label="adjusted continuing-operations EPS",
                unit="USD_per_share",
                basis="non_gaap",
            )
        if match := adjusted_eps_value_then_change.search(block):
            negative = match.group("direction").casefold().startswith("decrease")
            add_value(
                "adjusted_eps_growth_yoy",
                (-1.0 if negative else 1.0) * float(match.group("change")) / 100.0,
                display_label="adjusted diluted-EPS growth",
                basis="non_gaap",
            )
            add_value(
                "adjusted_eps_diluted",
                float(match.group("value")),
                display_label="adjusted diluted EPS",
                unit="USD_per_share",
                basis="non_gaap",
            )
        if match := reported_revenue_result.search(block):
            negative = match.group("direction").casefold().startswith("decrease")
            add_value(
                "reported_revenue_growth",
                (-1.0 if negative else 1.0) * float(match.group("change")) / 100.0,
                display_label="reported-revenue growth",
            )
            scale = 1_000_000_000.0 if match.group("scale").casefold() == "billion" else 1_000_000.0
            controls["current_quarter_revenue"] = round(
                float(match.group("value").replace(",", "")) * scale, 2
            )
        if match := margin_result.search(block):
            direction = -1.0 if match.group("direction").casefold() == "decreased" else 1.0
            change = direction * float(match.group("bps")) / 10_000.0
            margin = float(match.group("margin")) / 100.0
            label = match.group("label").casefold()
            adjusted_label = "base business" in label or "non-gaap" in label
            gaap_label = label.replace("non-gaap", "").replace("non gaap", "")
            if re.search(r"\bgaap\b", gaap_label):
                add_value(
                    "current_period_gross_margin",
                    margin,
                    display_label="GAAP gross margin",
                    basis="gaap",
                )
                add_value(
                    "current_period_gross_margin_change_yoy",
                    change,
                    display_label="GAAP gross-margin change",
                    basis="gaap",
                )
            if adjusted_label:
                add_value(
                    "adjusted_gross_margin",
                    margin,
                    display_label="adjusted gross margin",
                    basis="non_gaap",
                )
                add_value(
                    "adjusted_gross_margin_change_yoy",
                    change,
                    display_label="adjusted gross-margin change",
                    basis="non_gaap",
                )
        if match := comparative_gaap_margin.search(block):
            current = float(match.group("current")) / 100.0
            prior = float(match.group("prior")) / 100.0
            add_value(
                "current_period_gross_margin",
                current,
                display_label="GAAP gross margin",
                basis="gaap",
            )
            add_value(
                "current_period_gross_margin_change_yoy",
                current - prior,
                display_label="GAAP gross-margin change",
                basis="gaap",
            )
        if match := adjusted_margin_direct.search(block):
            direction = match.group("direction").casefold()
            negative = direction in {"down", "decreased", "a decrease of"}
            add_value(
                "adjusted_gross_margin",
                float(match.group("margin")) / 100.0,
                display_label="adjusted gross margin",
                basis="non_gaap",
            )
            add_value(
                "adjusted_gross_margin_change_yoy",
                (-1.0 if negative else 1.0) * float(match.group("bps")) / 10_000.0,
                display_label="adjusted gross-margin change",
                basis="non_gaap",
            )
        if match := market_share.search(block):
            label = " ".join(match.group("label").split())
            metric_name = f"market_share_{_slug(label)}"
            add_value(
                metric_name,
                float(match.group("share")) / 100.0,
                display_label=f"global {label} market share",
                period_bucket="ytd",
            )


def _extract_block_guidance_metrics(blocks, add_value, default_year: int) -> set[int]:
    """Extract explicit ranges from a labeled full-year outlook block."""

    guidance_years: set[int] = set()
    active_until = -1
    for index, block in enumerate(blocks):
        folded = block.casefold()
        explicit_guidance_range = bool(
            "guidance" in folded
            and (
                ("range" in folded and re.search(r"\b20[0-9]{2}\b", block))
                or (
                    block.lstrip().startswith(("•", "●", "▪", "◦", "-"))
                    and ("$" in block or "%" in block or "growth" in folded)
                )
            )
        )
        guidance_heading = re.search(
            r"\b(?:"
            r"(?:full[ -]year|fiscal year)\s+20[0-9]{2}.{0,80}?"
            r"(?:outlook|guidance)|"
            r"20[0-9]{2}\s+full[ -]year.{0,80}?(?:outlook|guidance)|"
            r"20[0-9]{2}\s+(?:outlook|guidance)"
            r")\b",
            block,
            re.IGNORECASE,
        )
        if guidance_heading:
            active_until = index + 15
            guidance_years.add(_nearest_guidance_year(blocks, index, default_year))
            if not explicit_guidance_range:
                continue
        if index > active_until and not explicit_guidance_range:
            continue
        if "conference call" in folded or "forward-looking statements" in folded:
            active_until = -1
            continue
        if not block.lstrip().startswith(("•", "●", "▪", "◦", "-")) and not explicit_guidance_range:
            continue
        is_quarter_only = bool(
            re.search(
                r"\b(?:first|second|third|fourth)[ -]+quarter\b",
                folded,
            )
            and not re.search(r"\b(?:full[ -]year|fiscal year)\b", folded)
        )
        if is_quarter_only:
            continue

        guidance_year = _nearest_guidance_year(blocks, index, default_year)
        definitions: list[tuple[str, str, str, str]] = []
        if "comparable sales" in folded:
            definitions.append(("comparable_sales_growth", "percent", "company_defined", "percent"))
        elif "operating margin" in folded or "operating income as a percentage" in folded:
            definitions.append(
                (
                    "adjusted_operating_margin" if "adjusted" in folded else "operating_margin",
                    "percent",
                    "non_gaap" if "adjusted" in folded else "gaap",
                    "percent",
                )
            )
        elif re.search(
            r"\b(?:diluted (?:earnings per share|eps)|"
            r"adjusted(?: diluted)? (?:earnings per share|eps))\b",
            folded,
        ):
            definitions.append(
                (
                    "adjusted_eps" if "adjusted" in folded else "eps_diluted",
                    "USD_per_share",
                    "non_gaap" if "adjusted" in folded else "gaap",
                    "money",
                )
            )
        elif "free cash flow" in folded:
            definitions.append(("free_cash_flow", "USD", "non_gaap", "money"))
        elif "adjusted income from operations" in folded:
            definitions.append(("adjusted_operating_income", "USD", "non_gaap", "money"))
        elif "u.s. commercial revenue" in folded or "us commercial revenue" in folded:
            definitions.append(("us_commercial_revenue", "USD", "company_defined", "money"))
        elif "commercial revenue" in folded:
            definitions.append(("commercial_revenue", "USD", "company_defined", "money"))
        elif "revenue guidance" in folded:
            definitions.append(("revenue", "USD", "company_defined", "money"))
        elif re.search(r"^[^a-z0-9]*(?:(?:total )?sales|(?:total )?revenue)\b", folded):
            definitions.append(("revenue", "USD", "company_defined", "money"))
            definitions.append(("reported_sales_growth", "percent", "company_defined", "percent"))

        for metric_base, unit, basis, range_type in definitions:
            metric_range = (
                _money_range(
                    block,
                    require_scale=metric_base
                    in {
                        "revenue",
                        "commercial_revenue",
                        "us_commercial_revenue",
                        "adjusted_operating_income",
                        "free_cash_flow",
                    },
                    prefer_last=bool(
                        explicit_guidance_range
                        and re.search(r"\bfrom\b.{0,160}\bto\b", block, re.IGNORECASE)
                    ),
                )
                if range_type == "money"
                else _outlook_percentage_range(block)
            )
            if metric_range is None:
                metric_range = (
                    _single_money_range(
                        block,
                        label=block,
                        require_scale=metric_base
                        in {
                            "revenue",
                            "commercial_revenue",
                            "us_commercial_revenue",
                            "adjusted_operating_income",
                            "free_cash_flow",
                        },
                    )
                    if range_type == "money"
                    else _single_percentage_range(block)
                )
            if metric_range is None:
                continue
            low, high = sorted(metric_range)
            lower_bound = "inclusive"
            upper_bound = "inclusive"
            if range_type == "money" and abs(low - high) <= 1e-12:
                if re.search(r"\b(?:in excess of|more than|greater than|over)\b", folded):
                    lower_bound, upper_bound = "exclusive", "unbounded"
                elif re.search(r"\b(?:at least|minimum of|no less than)\b", folded):
                    lower_bound, upper_bound = "inclusive", "unbounded"
            guidance_years.add(guidance_year)
            display_label = metric_base.replace("_", " ")
            add_value(
                f"guidance_{metric_base}_low",
                low,
                display_label=f"{display_label} guidance lower bound",
                unit=unit,
                basis=basis,
                bound_type=lower_bound,
            )
            add_value(
                f"guidance_{metric_base}_high",
                high,
                display_label=f"{display_label} guidance upper bound",
                unit=unit,
                basis=basis,
                bound_type=upper_bound,
            )
    return guidance_years


def _extract_company_bridge_metrics(table, add_value) -> None:
    for header_index, header in enumerate(table):
        header_map = {
            index: metric_name
            for index, cell in enumerate(header)
            if (metric_name := _bridge_metric_name(cell)) is not None
        }
        if len(header_map) < 2:
            continue
        bare_percent_table = any(
            re.search(r"(?:%|\bpercent\b)", cell, flags=re.IGNORECASE)
            for row in table[: header_index + 1]
            for cell in row
        )
        total_index = next(
            (
                index
                for index in range(header_index + 1, len(table))
                if re.fullmatch(
                    r"(?:total company|company total|consolidated|total)",
                    _clean_label(table[index][0]) if table[index] else "",
                    flags=re.IGNORECASE,
                )
            ),
            None,
        )
        if total_index is None:
            continue
        total_row = table[total_index]
        if len(total_row) != len(header):
            if _extract_sparse_quarter_bridge_metrics(
                table,
                header_index,
                header_map,
                total_index,
                add_value,
            ):
                return
            continue
        header_map = _prefer_current_quarter_bridge_columns(
            table,
            header_index,
            header_map,
        )
        for column, metric_name in header_map.items():
            value = _percent_value(
                total_row[column],
                allow_bare=bare_percent_table,
            )
            if value is not None:
                add_value(metric_name, value)
        segment_metric_column = next(
            (
                column
                for column, metric_name in header_map.items()
                if metric_name
                in {
                    "organic_sales_growth",
                    "organic_revenue_growth",
                    "comparable_sales_growth",
                }
            ),
            None,
        )
        if segment_metric_column is None:
            return
        for row_index, row in enumerate(
            table[header_index + 1 :],
            start=header_index + 1,
        ):
            if row_index == total_index:
                continue
            if len(row) != len(header) or not row[0].strip():
                continue
            label = _clean_segment_label(row[0])
            if not label or label.casefold().startswith("total "):
                continue
            value = _percent_value(
                row[segment_metric_column],
                allow_bare=bare_percent_table,
            )
            if value is None:
                continue
            metric_base = header_map[segment_metric_column]
            metric_name = f"segment_{metric_base}_{_slug(label)}"
            add_value(metric_name, value, display_label=label)
        return


def _prefer_current_quarter_bridge_columns(
    table: list[list[str]],
    header_index: int,
    header_map: dict[int, str],
) -> dict[int, str]:
    """Resolve duplicate bridge metrics in quarter-plus-YTD tables.

    Some issuer releases place a three-month bridge and its cumulative
    six-/nine-/twelve-month bridge in one wide table.  The HTML flattener
    preserves their left-to-right order but not ``colspan`` ownership.  When
    the same metric label therefore appears twice, retain the side belonging
    to the three-month section.  Tables without both time horizons remain
    untouched and fail closed on genuinely contradictory values.
    """

    metric_counts = Counter(header_map.values())
    if not any(count > 1 for count in metric_counts.values()):
        return header_map
    heading = " ".join(
        cell
        for row in table[: header_index + 1]
        for cell in row
        if cell.strip()
    ).casefold()
    quarter_position = heading.find("three months ended")
    cumulative_positions = [
        position
        for phrase in (
            "six months ended",
            "nine months ended",
            "twelve months ended",
            "year ended",
        )
        if (position := heading.find(phrase)) >= 0
    ]
    if quarter_position < 0 or not cumulative_positions:
        return header_map
    quarter_is_left = quarter_position < min(cumulative_positions)
    selected: dict[int, str] = {}
    for metric_name, count in metric_counts.items():
        columns = sorted(
            column
            for column, mapped_metric in header_map.items()
            if mapped_metric == metric_name
        )
        if count == 1:
            selected[columns[0]] = metric_name
            continue
        selected[columns[0] if quarter_is_left else columns[-1]] = metric_name
    return selected


def _extract_transposed_segment_bridge_metrics(table, add_value) -> None:
    """Extract quarter bridge tables with metrics in rows and segments in columns."""

    if not table or "three months ended" not in " ".join(table[0]).casefold():
        return
    header = next(
        (row for row in table[1:3] if len([cell for cell in row[1:] if cell.strip()]) >= 2),
        None,
    )
    if header is None:
        return
    segments = [_clean_segment_label(cell) for cell in header[1:] if cell.strip()]
    if len(segments) < 2:
        return
    if sum(_bridge_metric_name(segment) is not None for segment in segments) >= 2:
        return

    for row in table[2:]:
        if not row or not row[0].strip():
            continue
        metric_base = _bridge_metric_name(row[0])
        if metric_base is None:
            continue
        groups: list[list[str]] = []
        group: list[str] = []
        for cell in row[1:]:
            if cell.strip():
                group.append(cell)
            elif group:
                groups.append(group)
                group = []
        if group:
            groups.append(group)
        if len(groups) != len(segments):
            continue
        for segment, cells in zip(segments, groups):
            value = _percent_value(" ".join(cells))
            if value is None:
                continue
            if segment.casefold() in {"total", "total company", "consolidated"}:
                add_value(metric_base, value)
                continue
            label = f"{segment} {_metric_label(metric_base, None)}"
            add_value(
                f"segment_{metric_base}_{_slug(segment)}",
                value,
                display_label=label,
            )


def _bridge_metric_name(label: str) -> Optional[str]:
    normalized = _clean_label(label)
    normalized = re.sub(
        r"\s*\((?:growth|decline|non gaap)\)\s*",
        " ",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = " ".join(normalized.split())
    aliases = {
        "net sales": "reported_sales_growth",
        "sales growth": "reported_sales_growth",
        "reported sales growth": "reported_sales_growth",
        "sales change as reported": "reported_sales_growth",
        "organic sales": "organic_sales_growth",
        "organic sales change": "organic_sales_growth",
        "organic sales growth": "organic_sales_growth",
        "organic revenue": "organic_revenue_growth",
        "comparable sales": "comparable_sales_growth",
        "as reported volume": "reported_volume_growth",
        "reported volume": "reported_volume_growth",
        "volume": "volume_growth",
        "organic volume": "organic_volume_growth",
        "pricing": "pricing_growth",
        "price": "pricing_growth",
        "net price": "pricing_growth",
        "mix/other": "mix_other_impact",
        "mix other": "mix_other_impact",
        "divestitures and business exits": "business_portfolio_impact",
        "divestiture": "business_portfolio_impact",
        "effect of divestiture": "business_portfolio_impact",
        "acquisition impact": "acquisition_impact",
        "currency translation": "foreign_exchange_impact",
        "effect of changes in currency": "foreign_exchange_impact",
        "total": "reported_sales_growth",
        "organic": "organic_sales_growth",
        "fx": "foreign_exchange_impact",
        "foreign exchange": "foreign_exchange_impact",
        "foreign exchange impact": "foreign_exchange_impact",
    }
    return aliases.get(normalized)


def _is_guidance_table(table: list[list[str]]) -> bool:
    heading = " ".join(cell for row in table[:3] for cell in row)
    if re.search(r"\b(?:guidance|outlook)\b", heading, re.IGNORECASE):
        return True
    # Some issuer releases put the "Full Year Guidance" heading in a separate
    # one-row table. The following table is still unambiguous when it has a
    # Current/Prior header and several forward-looking financial labels.
    normalized_rows = [_clean_result_label(row[0]) for row in table if row]
    has_current_prior = bool(
        re.search(r"\bcurrent\b", heading, re.IGNORECASE)
        and re.search(r"\bprior\b", heading, re.IGNORECASE)
    )
    forward_labels = sum(
        1
        for label in normalized_rows
        if any(
            token in label
            for token in (
                "organic revenue",
                "organic sales",
                "comparable eps",
                "diluted eps",
                "free cash flow",
                "operating margin",
                "revenue",
            )
        )
    )
    return has_current_prior and forward_labels >= 2


def _is_current_quarter_bridge(table: list[list[str]], header_index: int) -> bool:
    heading = " ".join(cell for row in table[: header_index + 1] for cell in row).casefold()
    return "three months ended" in heading and "nine months ended" not in heading


def _ordered_percent_cells(row: list[str]) -> list[Optional[float]]:
    """Read visual percent groups when HTML colspans shift physical columns."""

    values: list[Optional[float]] = []
    pending = ""
    for cell in row[1:]:
        text = " ".join(str(cell or "").split())
        if not text:
            continue
        if text in {"%", "%)"}:
            values.append(_percent_value(f"{pending}{text}") if pending else None)
            pending = ""
            continue
        if "%" in text:
            values.append(_percent_value(text))
            pending = ""
            continue
        pending = text
    return values


def _extract_sparse_quarter_bridge_metrics(
    table: list[list[str]],
    header_index: int,
    header_map: dict[int, str],
    total_index: int,
    add_value,
) -> bool:
    """Extract a current-quarter bridge whose HTML uses uneven colspans."""

    if not _is_current_quarter_bridge(table, header_index):
        return False
    ordered_columns = sorted(header_map)
    metric_names = [header_map[column] for column in ordered_columns]
    if len(metric_names) < 2:
        return False
    total_values = _ordered_percent_cells(table[total_index])
    if len(total_values) != len(metric_names):
        return False
    preferred_columns = set(
        _prefer_current_quarter_bridge_columns(
            table,
            header_index,
            header_map,
        )
    )
    selected_indexes = [
        index
        for index, column in enumerate(ordered_columns)
        if column in preferred_columns
    ]
    for index in selected_indexes:
        metric_name = metric_names[index]
        value = total_values[index]
        if value is not None:
            add_value(metric_name, value)

    segment_metric_index = next(
        (
            index for index in selected_indexes
            if metric_names[index]
            in {
                "organic_sales_growth",
                "organic_revenue_growth",
                "comparable_sales_growth",
            }
        ),
        None,
    )
    if segment_metric_index is None:
        return True
    metric_base = metric_names[segment_metric_index]
    for row_index, row in enumerate(
        table[header_index + 1 :],
        start=header_index + 1,
    ):
        if row_index == total_index or not row or not row[0].strip():
            continue
        label = _clean_segment_label(row[0])
        if not label or label.casefold().startswith("total "):
            continue
        row_values = _ordered_percent_cells(row)
        if len(row_values) != len(metric_names):
            continue
        value = row_values[segment_metric_index]
        if value is None:
            continue
        add_value(
            f"segment_{metric_base}_{_slug(label)}",
            value,
            display_label=label,
        )
    return True


def _clean_label(value: str) -> str:
    text = re.sub(r"\([a-z0-9]{1,3}\)", "", str(value or ""), flags=re.IGNORECASE)
    text = text.replace("*", " ")
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
    return " ".join(text.casefold().replace("-", " ").split())


def _clean_result_label(value: str) -> str:
    text = re.sub(
        r"(?<![Qq])(?<=[A-Za-z])\d+(?:,\d+)*(?=\s|$)",
        "",
        str(value or ""),
    )
    return _clean_label(text)


def _result_comparison_columns(
    table: list[list[str]],
) -> Optional[tuple[int, int]]:
    period_pattern = re.compile(r"^(?:[1-4]q|q[1-4])\s*20[0-9]{2}$", re.IGNORECASE)
    for row_index, row in enumerate(table[:4]):
        period_columns = [
            column
            for column, cell in enumerate(row)
            if period_pattern.fullmatch(_clean_result_label(cell))
        ]
        change_column = next(
            (
                column
                for column, cell in enumerate(row)
                if _clean_result_label(cell).strip("% ").replace(" ", "")
                in {"change", "changeyoy", "yoychange"}
            ),
            None,
        )
        if period_columns and change_column is not None:
            return period_columns[0], change_column
        year_columns = [
            column
            for column, cell in enumerate(row)
            if re.fullmatch(r"20[0-9]{2}", _clean_result_label(cell))
        ]
        heading = " ".join(
            _clean_result_label(cell)
            for header_row in table[: row_index + 1]
            for cell in header_row
        )
        if (
            len(year_columns) >= 2
            and change_column is not None
            and re.search(r"\b(?:[1-4]q|q[1-4]|quarter)\b", heading)
        ):
            return year_columns[0], change_column
    return None


def _clean_segment_label(value: str) -> str:
    text = re.sub(r"\([0-9]+\)", "", str(value or ""))
    return " ".join(text.replace("*", " ").split()).strip(" ,;:-")


def _percent_value(value: str, *, allow_bare: bool = False) -> Optional[float]:
    match = _PERCENT.search(str(value or ""))
    if match is None and allow_bare:
        match = _BARE_PERCENT.fullmatch(str(value or ""))
    if match is None:
        return None
    number = float(match.group("value")) / 100.0
    groups = match.groupdict()
    parenthesized = match.group("open") and any(
        groups.get(name) for name in ("close_before", "close_after", "close")
    )
    if match.group("leading") == "-" or parenthesized:
        number = -number
    return number


def _result_change_percent(row: list[str], change_column: int) -> Optional[float]:
    """Read the first disclosed change at or after a sparse HTML header column."""

    window = row[change_column:]
    for index, cell in enumerate(window):
        parsed = _percent_value(cell)
        if parsed is not None:
            return parsed
        if (
            index + 1 < len(window)
            and str(window[index + 1] or "").strip() in {"%", "%)"}
            and (
                parsed := _percent_value(
                    f"{str(cell or '').strip()}{str(window[index + 1] or '').strip()}"
                )
            )
            is not None
        ):
            return parsed
        if re.fullmatch(r"\s*[–—-]\s*%\s*", str(cell or "")):
            return 0.0
    return None


def _result_current_money_value(
    row: list[str],
    current_column: int,
    *,
    allow_bare: bool = False,
) -> Optional[float]:
    """Read the current-period value when currency cells split table columns.

    SEC exhibits often render a visual ``$ 4,291`` cell as two physical HTML
    cells. The quarter header then points at ``$`` rather than the number. Only
    the first populated value at or after the current-period header is accepted;
    scanning stops at a second currency marker so a prior-period value cannot be
    mistaken for the current result.
    """

    currency_seen = False
    for cell in row[current_column:]:
        text = " ".join(str(cell or "").split())
        if not text:
            continue
        if text == "$":
            if currency_seen:
                return None
            currency_seen = True
            continue
        value = _money_value(
            f"${text}" if currency_seen else text,
            allow_bare=allow_bare,
        )
        if value is not None:
            return value
        if currency_seen:
            return None
    return None


def _basis_point_change(value: str) -> Optional[float]:
    text = " ".join(str(value or "").split())
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(?:basis points|bps)\b", text, re.IGNORECASE)
    if match is None:
        return None
    number = float(match.group(1)) / 10_000.0
    if text.lstrip().startswith(("-", "(")):
        number = -number
    return number


def _money_value(
    value: str,
    *,
    scale: float = 1.0,
    allow_bare: bool = False,
) -> Optional[float]:
    text = " ".join(str(value or "").split())
    match = re.search(
        r"\$\s*(?P<open>\()?\s*(?P<value>[0-9][0-9,]*(?:\.[0-9]+)?)",
        text,
    )
    if match is None and allow_bare:
        match = re.fullmatch(
            r"(?P<open>\()?\s*(?P<value>[0-9][0-9,]*(?:\.[0-9]+)?)\s*\)?",
            text,
        )
    if match is None:
        return None
    number = float(match.group("value").replace(",", "")) * scale
    return -number if match.group("open") else number


def _money_range(
    value: str,
    *,
    require_scale: bool = False,
    prefer_last: bool = False,
) -> Optional[tuple[float, float]]:
    text = " ".join(str(value or "").split())
    matches = list(
        re.finditer(
            r"\$\s*(?P<first>[0-9]+(?:\.[0-9]+)?)\s*"
            r"(?P<first_scale>[BM]|million|billion)?"
            r"\s*(?:\bto\b|\band\b|[-–—])\s*\$?\s*"
            r"(?P<second>[0-9]+(?:\.[0-9]+)?)\s*"
            r"(?P<second_scale>[BM]|million|billion)?",
            text,
            flags=re.IGNORECASE,
        )
    )
    if not matches:
        return None
    match = matches[-1] if prefer_last else matches[0]
    scales = [_money_scale(match.group(name)) for name in ("first_scale", "second_scale")]
    inherited_scale = scales[0] or scales[1]
    if require_scale and not inherited_scale:
        return None
    multipliers = {"": 1.0, "M": 1_000_000.0, "B": 1_000_000_000.0}
    parsed = [
        float(number) * multipliers[scale or inherited_scale]
        for number, scale in zip(
            (match.group("first"), match.group("second")),
            scales,
        )
    ]
    return parsed[0], parsed[1]


def _money_scale(value: Optional[str]) -> str:
    folded = str(value or "").casefold()
    if folded in {"b", "billion"}:
        return "B"
    if folded in {"m", "million"}:
        return "M"
    return ""


def _labeled_money_range(
    value: str,
    *,
    label: str,
    require_scale: bool = False,
) -> Optional[tuple[float, float]]:
    label_scale = 1.0
    if re.search(r"\b(?:in\s+)?billions?\b", label, re.IGNORECASE):
        label_scale = 1_000_000_000.0
    elif re.search(r"\b(?:in\s+)?millions?\b", label, re.IGNORECASE):
        label_scale = 1_000_000.0
    cell_has_scale = bool(
        re.search(r"[0-9]\s*(?:[BM]\b|million\b|billion\b)", value, re.IGNORECASE)
    )
    metric_range = _money_range(
        value,
        require_scale=require_scale and label_scale == 1.0,
    )
    if metric_range is None:
        return None
    if label_scale != 1.0 and not cell_has_scale:
        return metric_range[0] * label_scale, metric_range[1] * label_scale
    return metric_range


def _single_money_range(
    value: str,
    *,
    label: str = "",
    require_scale: bool = False,
) -> Optional[tuple[float, float]]:
    """Read one explicitly scaled guidance amount as an equal low/high range."""

    text = " ".join(str(value or "").split())
    match = re.search(
        r"\$\s*(?P<number>[0-9][0-9,]*(?:\.[0-9]+)?)\s*"
        r"(?P<scale>[BM]|million|billion)?\b",
        text,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    explicit_scale = _money_scale(match.group("scale"))
    label_scale = ""
    if re.search(r"\b(?:in\s+)?billions?\b", label, re.IGNORECASE):
        label_scale = "B"
    elif re.search(r"\b(?:in\s+)?millions?\b", label, re.IGNORECASE):
        label_scale = "M"
    scale = explicit_scale or label_scale
    if require_scale and not scale:
        return None
    multiplier = {"": 1.0, "M": 1_000_000.0, "B": 1_000_000_000.0}[scale]
    number = float(match.group("number").replace(",", "")) * multiplier
    return number, number


def _percentage_range(value: str) -> Optional[tuple[float, float]]:
    matches = list(_PERCENT.finditer(value))
    if len(matches) < 2:
        return None
    between = value[matches[0].end() : matches[1].start()].casefold()
    hyphen_consumed_as_sign = (
        not between.strip()
        and matches[0].group("leading") != "-"
        and matches[1].group("leading") == "-"
    )
    if not hyphen_consumed_as_sign and not re.search(
        r"(?:\bto\b|\band\b|[-–—])",
        between,
    ):
        return None
    low = _percent_value(matches[0].group(0))
    high = (
        float(matches[1].group("value")) / 100.0
        if hyphen_consumed_as_sign
        else _percent_value(matches[1].group(0))
    )
    if low is None or high is None:
        return None
    return low, high


def _single_percentage_range(value: str) -> Optional[tuple[float, float]]:
    """Read one clearly labelled forward percentage as an equal range."""

    matches = list(_PERCENT.finditer(str(value or "")))
    if len(matches) != 1:
        return None
    parsed = _percent_value(matches[0].group(0))
    return (parsed, parsed) if parsed is not None else None


def _outlook_percentage_range(value: str) -> Optional[tuple[float, float]]:
    metric_range = _percentage_range(value)
    if metric_range is not None:
        return metric_range
    match = re.search(
        r"\bflat\s+to\s+(?:up|increase(?:d)?)\s+"
        r"(?P<high>[0-9]+(?:\.[0-9]+)?)%",
        value,
        re.IGNORECASE,
    )
    if match is not None:
        return 0.0, float(match.group("high")) / 100.0
    match = re.search(
        r"\bdown\s+(?P<low>[0-9]+(?:\.[0-9]+)?)%\s+to\s+flat\b",
        value,
        re.IGNORECASE,
    )
    if match is not None:
        return -float(match.group("low")) / 100.0, 0.0
    return None


def _nearest_guidance_year(blocks: list[str], index: int, default_year: int) -> int:
    for block in reversed(blocks[max(0, index - 6) : index + 1]):
        match = re.search(
            r"\b(?:full[ -]year|fiscal year|FY)\s*(20[0-9]{2})\b",
            block,
            flags=re.IGNORECASE,
        )
        if match:
            return int(match.group(1))
    return default_year


def _directional_guidance_events(
    blocks: list[str], *, source_id: str, source_url: str, filing_date: str, retrieved_at: str
) -> list[dict[str, Any]]:
    summaries: list[str] = []
    candidates = list(blocks)
    candidates.extend(
        " ".join(blocks[index : index + 4])
        for index, block in enumerate(blocks)
        if "outlook" in block.casefold() or "expect" in block.casefold()
    )
    for block in candidates:
        normalized = block.casefold()
        if "expect" not in normalized:
            continue
        gaap_text = normalized.replace("non-gaap", "").replace("non gaap", "")
        if (
            "gaap" in gaap_text
            and "gross profit margin" in normalized
            and "roughly flat" in normalized
        ):
            summaries.append(
                "Management expects full-year GAAP gross margin to remain roughly flat."
            )
        if "gaap" in gaap_text and "double-digit earnings per share growth" in normalized:
            summaries.append(
                "Management continues to expect double-digit full-year GAAP EPS growth."
            )
        if "non-gaap" in normalized and "mid-single-digit earnings per share growth" in normalized:
            summaries.append(
                "Management now expects mid-single-digit full-year Base Business EPS growth."
            )
        if re.search(
            r"adjusted operating profit is expected to grow at a "
            r"mid-to-high single-digit rate.*?constant-currency basis",
            normalized,
        ):
            summaries.append(
                "Management expects adjusted operating profit to grow at a "
                "mid-to-high single-digit constant-currency rate."
            )
        if re.search(
            r"adjusted earnings per share from continuing operations are expected "
            r"to grow at a double-digit rate.*?constant-currency basis",
            normalized,
        ):
            summaries.append(
                "Management expects adjusted continuing-operations EPS to grow at "
                "a double-digit constant-currency rate."
            )
        if re.search(
            r"adjusted earnings per share attributable to .*? are expected to be "
            r"flat.*?constant-currency basis",
            normalized,
        ):
            summaries.append(
                "Management expects adjusted attributable EPS to remain flat on a "
                "constant-currency basis."
            )
    events = []
    for index, summary in enumerate(dict.fromkeys(summaries), start=1):
        events.append(
            {
                "event_type": "company_outlook",
                "date": filing_date,
                "headline": f"Issuer guidance update {index}",
                "summary": summary,
                "material": True,
                "source_id": source_id,
                "source_type": "sec_filing",
                "authority_rank": 1,
                "url": source_url,
                "retrieved_at": retrieved_at,
            }
        )
    return events


def _structured_guidance_event(
    metrics: list[dict[str, Any]],
    blocks: list[str],
    *,
    source_id: str,
    source_url: str,
    filing_date: str,
    retrieved_at: str,
) -> Optional[dict[str, Any]]:
    guidance = {
        str(item.get("metric_name")): item
        for item in metrics
        if str(item.get("metric_name") or "").startswith("guidance_")
    }
    if not guidance:
        return None
    text = " ".join(blocks[:120]).casefold()
    direction = "updated"
    if re.search(r"\b(?:raises?|raising|increases?|increasing)\b", text):
        direction = "raised"
    elif re.search(r"\b(?:lowers?|lowering|reduces?|reducing)\b", text):
        direction = "lowered"
    elif re.search(r"\b(?:maintains?|maintaining|reaffirms?|reaffirming)\b", text):
        direction = "maintained"

    details: list[str] = []
    bases = sorted(
        {
            name.removeprefix("guidance_").removesuffix("_low").removesuffix("_high")
            for name in guidance
        }
    )
    for base in bases[:6]:
        low = guidance.get(f"guidance_{base}_low")
        high = guidance.get(f"guidance_{base}_high")
        if low is None and high is None:
            continue
        low = low or high
        high = high or low
        assert low is not None and high is not None
        low_value = float(low["value"])
        high_value = float(high["value"])
        unit = str(low.get("unit") or high.get("unit") or "")
        label = base.replace("_", " ")
        if abs(low_value - high_value) <= 1e-12:
            rendered = _format_metric_value(low_value, unit)
        else:
            rendered = (
                f"{_format_metric_value(low_value, unit)} to "
                f"{_format_metric_value(high_value, unit)}"
            )
        details.append(f"{label}: {rendered}")
    summary = f"Management {direction} guidance"
    if details:
        summary += ": " + "; ".join(details)
    summary += ". Forward-looking non-GAAP measures remain separate from GAAP results."
    return {
        "event_type": "company_outlook",
        "date": filing_date,
        "headline": f"Issuer {direction} full-year guidance",
        "summary": summary,
        "material": True,
        "source_id": source_id,
        "source_type": "sec_filing",
        "authority_rank": 1,
        "url": source_url,
        "retrieved_at": retrieved_at,
    }


def _material_result_context_events(
    blocks: list[str],
    *,
    source_id: str,
    source_url: str,
    filing_date: str,
    retrieved_at: str,
) -> list[dict[str, Any]]:
    summaries: list[tuple[str, str, str]] = []
    for block in blocks:
        normalized = block.casefold()
        if "spin-off" in normalized or "spin off" in normalized:
            date_match = re.search(
                r"\bon\s+(?P<date>(?:January|February|March|April|May|June|July|"
                r"August|September|October|November|December)\s+[0-9]{1,2},\s+"
                r"20[0-9]{2})\b",
                block,
                flags=re.IGNORECASE,
            )
            if date_match is not None:
                effective_date = (
                    datetime.strptime(
                        date_match.group("date"),
                        "%B %d, %Y",
                    )
                    .date()
                    .isoformat()
                )
                summaries.append(
                    (
                        effective_date,
                        "corporate_action",
                        "The issuer completed a spin-off during the reported quarter; "
                        "pre- and post-transaction prices require an adjusted or "
                        "date-bounded series.",
                    )
                )
        if (
            ("eps" in normalized or "earnings" in normalized or "net income" in normalized)
            and "one-time gain" in normalized
            and "deconsolidation" in normalized
        ):
            subject_match = re.search(
                r"one-time gain on (?:the )?deconsolidation of "
                r"(?P<subject>[A-Za-z0-9& .'-]{2,80}?)(?:,|;|\band\b|\.)",
                block,
                flags=re.IGNORECASE,
            )
            subject = (
                " ".join(subject_match.group("subject").split())
                if subject_match is not None
                else "a former consolidated business"
            )
            summaries.append(
                (
                    filing_date,
                    "business_context",
                    "Management stated that reported earnings reflected a one-time "
                    f"gain on the deconsolidation of {subject}.",
                )
            )
        impairment_match = re.search(
            r"reported.{0,80}(?:loss per share|earnings|net income).{0,80}"
            r"reflects?.{0,80}(?P<amount>\$[0-9]+(?:\.[0-9]+)?\s+"
            r"(?:million|billion)).{0,80}(?:asset\s+)?impairments?",
            block,
            flags=re.IGNORECASE,
        )
        if impairment_match is not None:
            amount = " ".join(impairment_match.group("amount").split()).lower()
            summaries.append(
                (
                    filing_date,
                    "business_context",
                    "Management stated that reported loss per share reflected "
                    f"{amount} in non-cash intangible asset impairments.",
                )
            )
        if (
            "results refer to" in normalized
            and "only" in normalized
            and "excluding results attributable to" in normalized
        ):
            summaries.append(
                (
                    filing_date,
                    "business_context",
                    "The issuer states that the operating results and guidance use a "
                    "continuing-company perimeter that excludes the separated business.",
                )
            )
    return [
        {
            "event_type": event_type,
            "date": event_date,
            "headline": f"Issuer-filed result context {index}",
            "summary": summary,
            "material": True,
            "source_id": source_id,
            "source_type": "sec_filing",
            "authority_rank": 1,
            "url": source_url,
            "retrieved_at": retrieved_at,
        }
        for index, (event_date, event_type, summary) in enumerate(
            dict.fromkeys(summaries),
            start=1,
        )
    ]


def _metric_label(metric_name: str, display_label: Optional[str]) -> str:
    if display_label:
        if metric_name.startswith("segment_organic_sales_growth_"):
            return f"{display_label} organic-sales growth"
        return display_label
    labels = {
        "organic_sales_growth": "organic-sales growth",
        "organic_revenue_growth": "organic-revenue growth",
        "comparable_sales_growth": "comparable-sales growth",
        "reported_sales_growth": "reported-sales growth",
        "reported_volume_growth": "reported-volume growth",
        "organic_volume_growth": "organic-volume growth",
        "volume_growth": "volume growth",
        "pricing_growth": "pricing contribution",
        "foreign_exchange_impact": "foreign-exchange contribution",
        "mix_other_impact": "mix/other contribution",
        "business_portfolio_impact": "divestiture and business-exit contribution",
    }
    if metric_name.startswith("guidance_"):
        bound = "lower bound" if metric_name.endswith("_low") else "upper bound"
        base = metric_name.removeprefix("guidance_").removesuffix("_low").removesuffix("_high")
        return f"{base.replace('_', '-')} guidance {bound}"
    return labels.get(metric_name, metric_name.replace("_", " "))


def _format_metric_value(value: float, unit: str) -> str:
    if str(unit).casefold() == "percent":
        return f"{value:.1%}"
    if "per_share" in str(unit).casefold():
        return f"${value:.2f}"
    return f"{value:.2f} {unit}"


def _slug(value: str, *, max_length: int = 48) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    ascii_value = re.sub(r"['’]s\b", "s", ascii_value, flags=re.IGNORECASE)
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_value.casefold()).strip("_")
    return slug[:max_length] or "unknown"
