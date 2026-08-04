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
    r"\b(?:earnings|financial results?|press release|quarterly results?)\b",
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
        r"\b(first|second|third|fourth)\s+(?:fiscal\s+)?quarter"
        r".{0,100}?\b(20[0-9]{2})\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bQ([1-4])\s*(?:FY)?\s*(20[0-9]{2})\b", re.IGNORECASE),
    re.compile(r"\b([1-4])Q\s*(20[0-9]{2})\b", re.IGNORECASE),
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
    (re.compile(r"^comparable sales(?: growth| change)?$", re.IGNORECASE), "comparable_sales_growth"),
)


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: Optional[str] = None
        self._parts: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
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

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
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
    candidates: dict[str, int] = {}
    for href, label in parser.links:
        document = _safe_html_document(href)
        if document is None:
            continue
        score = 0
        if _RESULT_LINK_LANGUAGE.search(label):
            score += 5
        if _EXHIBIT_99_LABEL.fullmatch(" ".join(label.split())):
            score += 4
        if _RESULT_LINK_LANGUAGE.search(document.replace("_", " ").replace("-", " ")):
            score += 2
        if score:
            candidates[document] = max(candidates.get(document, 0), score)
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
    prose. It only accepts an exhibit whose quarter is already covered by the
    current 10-Q/10-K CompanyFacts accession and extracts issuer-defined operating
    bridges, division comparisons, and explicit guidance ranges.
    """

    parser = _ReleaseParser()
    parser.feed(html)
    fiscal_year, fiscal_period = _detect_release_period(parser.blocks, parser.tables)
    expected_period = str(expected_fiscal_period or "").upper()
    if (fiscal_year, fiscal_period) != (int(expected_fiscal_year), expected_period):
        raise ValueError(
            "Ergebnisperiode stimmt nicht mit dem aktuellen CompanyFacts-Bericht überein"
        )

    values: dict[str, float] = {}
    metric_labels: dict[str, str] = {}
    metric_units: dict[str, str] = {}
    metric_bases: dict[str, str] = {}
    metric_period_buckets: dict[str, str] = {}
    headline_controls: dict[str, float] = {}

    def add_value(
        metric_name: str,
        value: float,
        *,
        display_label: str = "",
        unit: str = "percent",
        basis: str = "company_defined",
        period_bucket: str = "quarterly",
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
        _extract_sectioned_segment_metrics(table, add_value)
        _extract_current_guidance_metrics(table, add_value)
    _extract_headline_block_metrics(parser.blocks, add_value)

    guidance_years: set[int] = set()
    for index, block in enumerate(parser.blocks):
        if "expect" not in block.casefold() and "guid" not in block.casefold():
            continue
        guidance_year = _nearest_guidance_year(parser.blocks, index, fiscal_year)
        for label_pattern, metric_base in _GUIDANCE_LABELS:
            label_match = label_pattern.search(block)
            if label_match is None:
                continue
            range_match = _percentage_range(block[label_match.end() :])
            if range_match is None:
                continue
            low, high = sorted(range_match)
            guidance_years.add(guidance_year)
            add_value(f"guidance_{metric_base}_low", low)
            add_value(f"guidance_{metric_base}_high", high)
            break

    supported_operating = [
        metric_name
        for metric_name in values
        if not metric_name.startswith("guidance_")
    ]
    supported_guidance = [
        metric_name for metric_name in values if metric_name.startswith("guidance_")
    ]
    if len(supported_operating) < 2 and len(supported_guidance) < 2:
        raise ValueError(
            "Ergebnis-Anhang enthält keine ausreichend strukturierte operative "
            "Brücke oder explizite Guidance-Spanne"
        )

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
        f"https://www.sec.gov/Archives/edgar/data/{cik_digits}/"
        f"{accession_digits}/{document}"
    )
    result_period = f"FY{fiscal_year}_{fiscal_period}"
    guidance_year = max(guidance_years) if guidance_years else fiscal_year
    metrics: list[dict[str, Any]] = []
    for metric_name, value in sorted(values.items()):
        is_guidance = metric_name.startswith("guidance_")
        period = f"FY{guidance_year}" if is_guidance else result_period
        period_bucket = metric_period_buckets.get(metric_name, "quarterly")
        label = _metric_label(metric_name, metric_labels.get(metric_name))
        metric_period = (
            f"FY{fiscal_year}_YTD"
            if period_bucket == "ytd"
            else period
        )
        metrics.append(
            {
                "metric_name": metric_name,
                "value": value,
                "unit": metric_units.get(metric_name, "percent"),
                "period": metric_period,
                "period_bucket": "guidance" if is_guidance else period_bucket,
                "fiscal_year": guidance_year if is_guidance else fiscal_year,
                "fiscal_period": "FY" if is_guidance else fiscal_period,
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
            }
        )

    events: list[dict[str, Any]] = []
    if any(metric_name.startswith("segment_") for metric_name in values):
        events.append(
            {
                "event_type": "business_context",
                "date": filing_date,
                "headline": "Issuer filed division-level operating results",
                "summary": (
                    "The issuer disclosed division-level organic-sales performance "
                    "for the latest reported quarter."
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
    blocks: list[str], tables: list[list[list[str]]]
) -> tuple[int, str]:
    candidates: list[tuple[int, str]] = []
    sources = [*blocks[:80]]
    sources.extend(
        " ".join(cell for row in table[:4] for cell in row)
        for table in tables[:8]
    )
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
    if not candidates:
        raise ValueError("Quartalsperiode des Ergebnis-Anhangs nicht eindeutig erkannt")
    counts = Counter(candidates)
    best_count = max(counts.values())
    best = sorted(period for period, count in counts.items() if count == best_count)
    if len(best) != 1:
        raise ValueError("mehrere Ergebnisperioden im Anhang gleich stark erkannt")
    return best[0]


def _extract_headline_operating_metrics(table, add_value) -> None:
    for row in table:
        if len(row) < 2:
            continue
        label = _clean_label(row[0])
        metric_name = next(
            (
                name
                for pattern, name in _HEADLINE_RESULT_LABELS
                if pattern.fullmatch(label)
            ),
            None,
        )
        if metric_name is None:
            continue
        value = next(
            (
                parsed
                for cell in row[1:]
                if (parsed := _percent_value(cell)) is not None
            ),
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
    rows = {
        _clean_result_label(row[0]): row
        for row in table
        if row and row[0].strip()
    }
    if "sales" not in rows or "adjusted earnings per share" not in rows:
        return False

    for label, control_name in (
        ("sales", "current_quarter_revenue"),
        ("operating income", "current_quarter_operating_income"),
        ("segment profit", "current_quarter_segment_profit"),
    ):
        row = rows.get(label)
        if row is None or len(row) <= current_column:
            continue
        value = _money_value(row[current_column])
        if value is not None:
            controls[control_name] = value

    sales_row = rows["sales"]
    if len(sales_row) > change_column:
        value = _percent_value(sales_row[change_column])
        if value is not None:
            add_value(
                "reported_sales_growth",
                value,
                display_label="reported-sales growth",
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

    adjusted_eps_row = rows["adjusted earnings per share"]
    if len(adjusted_eps_row) > current_column:
        adjusted_eps = _money_value(adjusted_eps_row[current_column])
        if adjusted_eps is not None:
            add_value(
                "adjusted_eps_diluted",
                adjusted_eps,
                display_label="adjusted diluted EPS",
                unit="USD_per_share",
                basis="non_gaap",
            )
    if len(adjusted_eps_row) > change_column:
        eps_change = _percent_value(adjusted_eps_row[change_column])
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
    guidance_column = next(
        (
            column
            for row in table[:3]
            for column, cell in enumerate(row)
            if _clean_result_label(cell) in {"current guidance", "current outlook"}
        ),
        None,
    )
    if guidance_column is None:
        return
    definitions = {
        "sales": ("revenue", "USD", "company_defined"),
        "organic growth": ("organic_sales_growth", "percent", "company_defined"),
        "organic sales growth": ("organic_sales_growth", "percent", "company_defined"),
        "organic revenue growth": ("organic_revenue_growth", "percent", "company_defined"),
        "segment margin": ("segment_margin", "percent", "non_gaap"),
        "adjusted earnings per share": ("adjusted_eps", "USD_per_share", "non_gaap"),
        "adjusted earnings growth": ("adjusted_eps_growth", "percent", "non_gaap"),
    }
    for row in table:
        if not row or len(row) <= guidance_column:
            continue
        label = _clean_result_label(row[0])
        definition = definitions.get(label)
        if definition is None:
            continue
        metric_base, unit, basis = definition
        cell = row[guidance_column]
        metric_range = (
            _percentage_range(cell)
            if unit == "percent"
            else _money_range(cell, require_scale=metric_base == "revenue")
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
        )
        add_value(
            f"guidance_{metric_base}_high",
            high,
            display_label=f"{display_label} guidance upper bound",
            unit=unit,
            basis=basis,
        )


def _extract_headline_block_metrics(blocks, add_value) -> None:
    adjusted_eps = re.compile(
        r"\b(?:Base Business|adjusted|non-GAAP)(?: diluted)? EPS\b.*?"
        r"\b(increased|decreased)\s+([0-9]+(?:\.[0-9]+)?)%\s+to\s+"
        r"\$([0-9]+(?:\.[0-9]+)?)",
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
    for block in blocks:
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
            continue
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


def _bridge_metric_name(label: str) -> Optional[str]:
    normalized = _clean_label(label)
    aliases = {
        "net sales": "reported_sales_growth",
        "sales change as reported": "reported_sales_growth",
        "organic sales": "organic_sales_growth",
        "organic sales change": "organic_sales_growth",
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
        "currency translation": "foreign_exchange_impact",
        "total": "reported_sales_growth",
        "organic": "organic_sales_growth",
        "fx": "foreign_exchange_impact",
        "foreign exchange": "foreign_exchange_impact",
    }
    return aliases.get(normalized)


def _clean_label(value: str) -> str:
    text = re.sub(r"\([a-z0-9]{1,3}\)", "", str(value or ""), flags=re.IGNORECASE)
    text = text.replace("*", " ")
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
    return " ".join(text.casefold().replace("-", " ").split())


def _clean_result_label(value: str) -> str:
    text = re.sub(
        r"(?<=[A-Za-z])\d+(?:,\d+)*(?=\s|$)",
        "",
        str(value or ""),
    )
    return _clean_label(text)


def _result_comparison_columns(
    table: list[list[str]],
) -> Optional[tuple[int, int]]:
    period_pattern = re.compile(r"^(?:[1-4]q|q[1-4])\s*20[0-9]{2}$", re.IGNORECASE)
    for row in table[:4]:
        period_columns = [
            column
            for column, cell in enumerate(row)
            if period_pattern.fullmatch(_clean_result_label(cell))
        ]
        change_column = next(
            (
                column
                for column, cell in enumerate(row)
                if _clean_result_label(cell) == "change"
            ),
            None,
        )
        if period_columns and change_column is not None:
            return period_columns[0], change_column
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


def _basis_point_change(value: str) -> Optional[float]:
    text = " ".join(str(value or "").split())
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(?:basis points|bps)\b", text, re.IGNORECASE)
    if match is None:
        return None
    number = float(match.group(1)) / 10_000.0
    if text.lstrip().startswith(("-", "(")):
        number = -number
    return number


def _money_value(value: str, *, scale: float = 1.0) -> Optional[float]:
    text = " ".join(str(value or "").split())
    match = re.search(
        r"\$\s*(?P<open>\()?\s*(?P<value>[0-9][0-9,]*(?:\.[0-9]+)?)",
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
) -> Optional[tuple[float, float]]:
    text = " ".join(str(value or "").split())
    matches = list(
        re.finditer(
            r"\$\s*([0-9]+(?:\.[0-9]+)?)\s*([BM])?",
            text,
            flags=re.IGNORECASE,
        )
    )
    if len(matches) < 2:
        return None
    between = text[matches[0].end() : matches[1].start()].casefold()
    if not re.search(r"(?:\bto\b|[-–—])", between):
        return None
    scales = [str(match.group(2) or "").upper() for match in matches[:2]]
    inherited_scale = scales[0] or scales[1]
    if require_scale and not inherited_scale:
        return None
    multipliers = {"": 1.0, "M": 1_000_000.0, "B": 1_000_000_000.0}
    parsed = [
        float(match.group(1)) * multipliers[scale or inherited_scale]
        for match, scale in zip(matches[:2], scales)
    ]
    return parsed[0], parsed[1]


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


def _nearest_guidance_year(
    blocks: list[str], index: int, default_year: int
) -> int:
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
        if "gaap" in gaap_text and "gross profit margin" in normalized and "roughly flat" in normalized:
            summaries.append(
                "Management expects full-year GAAP gross margin to remain roughly flat."
            )
        if "gaap" in gaap_text and "double-digit earnings per share growth" in normalized:
            summaries.append(
                "Management continues to expect double-digit full-year GAAP EPS growth."
            )
        if (
            "non-gaap" in normalized
            and "mid-single-digit earnings per share growth" in normalized
        ):
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
                effective_date = datetime.strptime(
                    date_match.group("date"),
                    "%B %d, %Y",
                ).date().isoformat()
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
