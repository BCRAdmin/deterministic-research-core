"""Extract source-bound operating KPI statements from official SEC filings."""

from __future__ import annotations

import re
import hashlib
from calendar import monthrange
from datetime import date, timedelta
from html.parser import HTMLParser
from typing import Any


KPI_PATTERNS = {
    "paid_members": r"\bpaid members(?:hips?)?\b",
    "cardholders": r"\bcardholders?\b",
    "renewal_rate": r"\brenewal rates?\b",
    "comparable_sales": r"\b(?:comparable sales|comp sales)\b",
    "traffic_frequency": r"\b(?:customer traffic|shopping frequency|traffic)\b",
    "average_ticket": r"\b(?:average ticket|ticket|basket)\b",
    "digital_sales": r"\b(?:digital sales|e-?commerce|digitally-enabled comparable sales)\b",
    "collection_disposal_yield": r"\b(?:collection and disposal yield|yield)\b",
    "volume": r"\bvolume\b",
    "operating_ebitda": r"\b(?:operating ebitda|adjusted ebitda|ebitda margin)\b",
    "capital_allocation": (
        r"\b(?:returned?|returning)\b.{0,100}\bshareholders?\b|"
        r"\b(?:share repurchases?|stock repurchases?|cash dividends?|"
        r"capital returned|return of capital)\b"
    ),
    "free_cash_flow_guidance": r"\b(?:free cash flow|fcf)\b.{0,100}\b(?:guidance|outlook|range)\b|\b(?:guidance|outlook|range)\b.{0,100}\b(?:free cash flow|fcf)\b",
    "free_cash_flow_actual": r"^\s*free cash flow\b",
    "internalization": r"\binternalization(?: of waste)?\b",
    "landfill_depletable_tons": r"\blandfill depletable tons?\b",
    "acquired_annualized_revenue": r"\b(?:gross )?annualized revenue acquired\b|\bacquired annualized revenue\b",
    "organic_comparable_growth": r"\b(?:organic|comparable)\b.{0,80}\bgrowth\b|\bgrowth\b.{0,80}\b(?:organic|comparable)\b",
    "segment_growth": r"\bsegment\b.{0,100}\bgrowth\b|\bgrowth\b.{0,100}\bsegment\b",
    "adjusted_eps_guidance": r"\badjusted eps\b.{0,120}\b(?:guidance|outlook|range)\b|\b(?:guidance|outlook|range)\b.{0,120}\badjusted eps\b",
    "transaction_financing": (
        r"\b(?:acquisition|transaction)\b.{0,160}"
        r"\b(?:debt|financ|consideration|purchase price|per (?:common )?share)\b|"
        r"\b(?:debt|financ)\b.{0,160}\b(?:acquisition|transaction)\b"
    ),
    "acquisition_cash": (
        r"\bacquisitions? of businesses(?: and technologies)?(?:, net of cash acquired)?\b|"
        r"\bnet cash paid\b.{0,120}\bacquisitions?\b"
    ),
    "integration_effects": (
        r"\b(?:integration costs?|purchase accounting|acquisition-related amortization)\b|"
        r"\b(?:acquisition|transaction|integration)\b.{0,180}"
        r"\bsynerg(?:y|ies)\b|\bsynerg(?:y|ies)\b.{0,180}"
        r"\b(?:acquisition|transaction|integration)\b"
    ),
    "product_regulatory_catalyst": r"\b(?:approval|clearance|product launch|clinical milestone)\b",
}

NUMBER_RE = re.compile(
    r"(?P<currency>C\$|US\$|A\$|HK\$|S\$|[$€£¥])?\s*"
    r"(?P<number>(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*"
    r"(?P<scale>billion|million|thousand|bn|mn|m|k)?\s*"
    r"(?P<percent>%|percent(?:age points?)?)?",
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
    html_documents: list[str] | None = None,
    source_documents: list[dict[str, Any]] | None = None,
    retrieved_at: str,
    report_date: str | None = None,
    report_period_months: int | None = None,
) -> dict[str, Any]:
    documents = source_documents or [
        {
            "accession_number": accession_number,
            "filing_date": filing_date,
            "primary_document": primary_document,
            "html": html,
            "report_date": report_date,
            "report_period_months": report_period_months,
            "document_role": "financial_filing",
        }
        for html in (html_documents or [])
    ]
    events: list[dict[str, Any]] = []
    dispositions_by_kpi = {kpi_id: 0 for kpi_id in KPI_PATTERNS}
    sources_checked: list[str] = []
    for source_document in documents:
        document_accession = str(source_document["accession_number"])
        document_filing_date = str(source_document["filing_date"])
        document_primary = str(source_document["primary_document"])
        html = str(source_document["html"])
        parser = _BlockParser()
        parser.feed(html)
        blocks = [
            block
            for index, block in enumerate(parser.finish())
            if index == 0 or block != parser.blocks[index - 1]
        ]
        blocks = _merge_split_kpi_table_rows(blocks)
        document_currency_scale = _document_currency_scale(blocks)
        document_events, document_dispositions, document_url = _extract_document_events(
            ticker=ticker,
            cik=cik,
            accession_number=document_accession,
            filing_date=document_filing_date,
            primary_document=document_primary,
            blocks=blocks,
            html=html,
            retrieved_at=retrieved_at,
            report_date=source_document.get("report_date"),
            report_period_months=source_document.get("report_period_months"),
            document_currency_scale=document_currency_scale,
            document_role=str(source_document.get("document_role") or "filing_document"),
            event_offset=len(events),
        )
        events.extend(document_events)
        sources_checked.append(document_url)
        for kpi_id, count in document_dispositions.items():
            dispositions_by_kpi[kpi_id] += count
    dispositions = [
        {
            "kpi_id": kpi_id,
            "status": "found" if dispositions_by_kpi[kpi_id] else "reviewed_not_found",
            "match_count": dispositions_by_kpi[kpi_id],
        }
        for kpi_id in KPI_PATTERNS
    ]
    return {
        "coverage_status": "complete",
        "checked_at": retrieved_at,
        "window_start": min((str(item["filing_date"]) for item in documents), default=filing_date),
        "window_end": max((str(item["filing_date"]) for item in documents), default=filing_date),
        "sources_checked": sources_checked,
        "all_kpis_dispositioned": len(dispositions) == len(KPI_PATTERNS),
        "kpi_dispositions": dispositions,
        "events": events,
    }


def _extract_document_events(
    *,
    ticker: str,
    cik: str,
    accession_number: str,
    filing_date: str,
    primary_document: str,
    blocks: list[str],
    html: str,
    retrieved_at: str,
    report_date: str | None,
    report_period_months: int | None,
    document_currency_scale: str | None,
    document_role: str,
    event_offset: int,
) -> tuple[list[dict[str, Any]], dict[str, int], str]:
    priority_statements = {
        "capital_allocation": set(
            _ranked_capital_allocation_statements(blocks, limit=3)
        ),
        "paid_members": set(_ranked_kpi_statements(blocks, "paid_members", limit=3)),
        "cardholders": set(_ranked_kpi_statements(blocks, "cardholders", limit=3)),
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
    emitted_statements: set[str] = set()
    for block_index, statement in enumerate(blocks):
        if statement in emitted_statements:
            continue
        if _is_forward_looking_boilerplate(statement):
            continue
        if _is_broken_leading_fragment(statement):
            continue
        matched_kpis = [
            kpi_id
            for kpi_id, pattern in KPI_PATTERNS.items()
            if re.search(pattern, statement, flags=re.IGNORECASE)
            and _kpi_statement_is_semantic_match(kpi_id, statement)
            and match_counts[kpi_id] < 3
            and (
                kpi_id not in priority_statements
                or statement in priority_statements[kpi_id]
            )
        ]
        if not matched_kpis:
            continue
        column_labels = _inherited_column_labels(
            blocks,
            block_index,
            filing_year=filing_year,
        )
        if column_labels and not _looks_like_table_value_row(statement):
            column_labels = None
        if re.search(r"\b20\d{2}\s*:\s*(?:C\$|US\$|A\$|HK\$|S\$|[$€£¥])", statement):
            # Inline year/value pairs own their own periods.  A stale table
            # header from a preceding row must never shift the first value to
            # the prior year.
            column_labels = None
        # A row beginning with "Free cash flow" is not automatically an
        # actual-period table.  Issuer guidance tables often use the same row
        # label for a low/high range.  Promote it as an actual only when the
        # surrounding table supplies explicit period columns.
        if "free_cash_flow_actual" in matched_kpis and not column_labels:
            matched_kpis = [
                kpi_id for kpi_id in matched_kpis if kpi_id != "free_cash_flow_actual"
            ]
        if not matched_kpis:
            continue
        table_contract = _table_contract(
            blocks,
            block_index,
            column_labels=column_labels,
            accession_number=accession_number,
        )
        numeric_evidence = _numeric_evidence(
            statement,
            kpi_ids=matched_kpis,
            event_index=event_offset + len(events) + 1,
            context_scale=(
                _inherited_block_scale(blocks, block_index)
                or (table_contract or {}).get("source_scale")
            ),
            column_labels=column_labels,
            table_contract=table_contract,
            filing_date=filing_date,
            report_date=report_date,
            report_period_months=report_period_months,
            document_currency_scale=document_currency_scale,
        )
        if not numeric_evidence:
            continue
        emitted_statements.add(statement)
        for kpi_id in matched_kpis:
            match_counts[kpi_id] += 1
        primary_kpi = matched_kpis[0]
        primary_counts[primary_kpi] += 1
        event_source_id = (
            f"SEC_CIK{cik_digits}_{accession_digits}_KPI_"
            f"{primary_kpi.upper()}_{primary_counts[primary_kpi]:02d}"
        )
        if table_contract:
            table_contract["source_id"] = event_source_id
            table_contract["cells"] = [
                {
                    "cell_id": item["cell_id"],
                    "table_id": item["table_id"],
                    "row_key": item["row_key"],
                    "column_key": item["column_key"],
                    "raw_text": item.get("raw_text") or "",
                    "normalized_value": item.get("value"),
                    "unit": item.get("unit"),
                    "currency": item.get("currency"),
                    "scale": item.get("source_scale"),
                    "period_start": item.get("period_start"),
                    "period_end": item.get("period_end"),
                    "period_kind": item.get("period_kind"),
                    "comparison_period_start": item.get("comparison_period_start"),
                    "comparison_period_end": item.get("comparison_period_end"),
                    "rate_basis": item.get("rate_basis"),
                    "direction": item.get("direction"),
                    "impact": item.get("impact"),
                    "is_zero": item.get("is_zero", False),
                    "is_not_applicable": item.get("is_not_applicable", False),
                    "is_missing": item.get("is_missing", False),
                    "source_locator": item.get("source_locator"),
                }
                for item in numeric_evidence
                if item.get("table_id")
            ]
        events.append(
            {
                "event_type": "operating_kpi",
                "date": filing_date,
                "headline": (
                    "Issuer reported operating KPI context: "
                    + ", ".join(kpi_id.replace("_", " ") for kpi_id in matched_kpis)
                ),
                "summary": _bounded_source_summary(statement),
                "material": True,
                "source_id": event_source_id,
                "source_type": "sec_filing",
                "authority_rank": 1,
                "url": url,
                "source_accession_number": accession_number,
                "source_document": document,
                "source_document_role": document_role,
                "source_snapshot_path": (
                    f"raw_sec_filings/{accession_digits}/{document}"
                ),
                "source_content_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
                "source_content_bytes": len(html.encode("utf-8")),
                "retrieved_at": retrieved_at,
                "content_complete": True,
                "dependency_status": "complete",
                "report_disposition": "included_main_report",
                "report_disposition_reason": (
                    "A current primary-source operating KPI is included in the "
                    "main analytical evidence chain."
                ),
                "materiality_rationale": (
                    "The issuer disclosed a numeric operating KPI matched to the "
                    "active business-model contract."
                ),
                "inventory_filter_reason": "inside_analysis_window",
                "semantic_disposition": "current_operating_kpi",
                "table_contracts": [table_contract] if table_contract else [],
                "numeric_evidence": numeric_evidence,
            }
        )
    return events, match_counts, url


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


def _ranked_kpi_statements(
    statements: list[str],
    kpi_id: str,
    *,
    limit: int,
) -> list[str]:
    pattern = KPI_PATTERNS[kpi_id]
    candidates = [
        statement
        for statement in statements
        if re.search(pattern, statement, re.IGNORECASE)
        and any(
            match.group("currency")
            or match.group("percent")
            or match.group("scale")
            or "," in match.group("number")
            for match in NUMBER_RE.finditer(statement)
        )
    ]
    return sorted(
        candidates,
        key=lambda statement: (
            int(re.search(rf"^\s*(?:total\s+)?{pattern}", statement, re.IGNORECASE) is not None),
            int(len(statement) <= 220),
            len(list(NUMBER_RE.finditer(statement))),
            -len(statement),
        ),
        reverse=True,
    )[:limit]


def _kpi_statement_is_semantic_match(kpi_id: str, statement: str) -> bool:
    """Reject lexical matches that do not assert the requested KPI.

    Broad filing vocabulary such as ``frequency``, ``e-commerce`` and
    ``regulatory approval`` also appears in accounting policies and company
    descriptions.  Those passages are context, not operating KPI evidence.
    """

    folded = statement.casefold()
    if kpi_id == "digital_sales":
        return bool(
            re.search(
                r"\b(?:digital sales|digitally-enabled comparable sales|"
                r"e-?commerce (?:net )?sales|sales for e-?commerce)\b",
                folded,
            )
        )
    if kpi_id == "product_regulatory_catalyst":
        if re.search(
            r"\b(?:intangible assets?|impairment|purchase accounting)\b.{0,180}"
            r"\bregulatory approval\b",
            folded,
        ):
            return False
        return bool(
            re.search(
                r"\b(?:received|granted|obtained|announced|launched|achieved|"
                r"expects?|seeks?)\b.{0,100}"
                r"\b(?:approval|clearance|product launch|clinical milestone)\b|"
                r"\b(?:approval|clearance|product launch|clinical milestone)\b"
                r".{0,100}\b(?:received|granted|obtained|announced|launched)\b",
                folded,
            )
        )
    return True


def _merge_split_kpi_table_rows(blocks: list[str]) -> list[str]:
    """Rejoin SEC rows whose footnote split separates label from values."""

    merged = [
        re.sub(
            r"(20\d{2})(?=20\d{2})",
            r"\1 ",
            re.sub(r"(?<=[A-Za-z])(?=\d{1,3},\d{3}\b)", " ", block),
        )
        for block in blocks
    ]
    for index in range(len(merged) - 1):
        label = merged[index].strip()
        values = merged[index + 1].strip()
        clean_label = re.sub(r"(?<=[A-Za-z)])\d+\s*$", "", label).strip()
        if not any(
            re.search(pattern, clean_label, re.IGNORECASE)
            for pattern in KPI_PATTERNS.values()
        ):
            continue
        value_matches = list(NUMBER_RE.finditer(values))
        if (
            len(label) > 100
            or len(value_matches) < 2
            or not re.match(r"^\s*\d", values)
        ):
            continue
        merged[index] = f"{clean_label} {values}".strip()
    return merged


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
    table_contract: dict[str, Any] | None = None,
    filing_date: str | None = None,
    report_date: str | None = None,
    report_period_months: int | None = None,
    document_currency_scale: str | None = None,
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
    table_positions = _table_numeric_positions(statement, table_contract)
    for number_index, match in enumerate(number_matches):
        raw = float(match.group("number").replace(",", ""))
        if _is_non_metric_number(statement, match):
            continue
        explicit_scale = str(match.group("scale") or "").casefold()
        per_share = _is_per_share_value(statement, match)
        base_currency_value = _is_base_currency_value(statement, match)
        scale = (
            "base"
            if per_share or base_currency_value
            else explicit_scale
            or _inherited_inline_scale(statement, match, number_matches)
            or str(context_scale or "").casefold()
            or (
                str(document_currency_scale or "").casefold()
                if match.group("currency")
                else ""
            )
        )
        percent = bool(match.group("percent"))
        material_count = _is_material_operating_count(statement, match)
        basis_points = bool(
            re.match(
                r"\s*(?:-|–|—)?\s*basis points?\b",
                statement[match.end() :],
                flags=re.IGNORECASE,
            )
        )
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
        if not (
            match.group("currency")
            or percent
            or basis_points
            or scale
            or material_count
        ):
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
        direction, direction_label, impact = _numeric_direction_contract(
            statement,
            match.span(),
        )
        change_prefix = statement[max(0, match.start() - 55) : match.start()]
        explicit_change_amount = re.search(
            r"\b(?:grew|increased?|decreased?|declined?|reduced?|reduction|headwind)\b.{0,30}$",
            change_prefix,
            re.IGNORECASE,
        ) is not None
        if not (percent or basis_points or explicit_change_amount):
            direction = 1.0
            direction_label = "neutral"
            impact = "neutral"
        inherited_currency = _inherits_table_currency(statement, context_scale)
        unit = (
            "basis_points"
            if basis_points
            else "percent"
            if percent
            else "currency_per_share"
            if match.group("currency") and per_share
            else "currency"
            if match.group("currency") or inherited_currency
            else "count"
        )
        currency = {
            "C$": "CAD",
            "US$": "USD",
            "A$": "AUD",
            "HK$": "HKD",
            "S$": "SGD",
            "$": "USD",
            "€": "EUR",
            "£": "GBP",
            "¥": "JPY",
        }.get(str(match.group("currency") or "")) or ("USD" if inherited_currency else None)
        # A table-level monetary scale may surround non-monetary cells.  A
        # percentage or basis-point cell must never inherit that currency.
        if percent or basis_points:
            currency = None
        distance, owner = min(
            (
                _semantic_distance(match.span(), label_range),
                kpi_id,
            )
            for kpi_id, label_range in label_ranges
        )
        metric_owner = owner if distance <= 140 else "statement_context"
        semantic_number_index = number_index - sum(
            1
            for prior in number_matches[:number_index]
            if _is_non_metric_number(statement, prior)
        )
        column_index = table_positions.get(number_index, semantic_number_index)
        column_label = (
            column_labels[column_index]
            if column_labels and column_index < len(column_labels)
            else None
        )
        if table_contract and column_index < len(table_contract.get("column_labels", [])):
            column_label = table_contract["column_labels"][column_index]
        period_contract = _numeric_period_contract(
            statement,
            match=match,
            number_index=column_index,
            column_label=column_label,
            filing_date=filing_date,
            report_date=report_date,
            report_period_months=report_period_months,
        )
        metric_role = _numeric_metric_role(
            statement,
            owner=metric_owner,
            match=match,
            column_label=column_label,
            period_role=period_contract["period_role"],
            number_index=column_index,
        )
        if table_contract and table_contract.get("row_metric"):
            column_metrics = table_contract.get("column_metrics", [])
            if column_index < len(column_metrics):
                metric_role = "_".join(
                    (
                        str(table_contract["row_metric"]),
                        str(period_contract["period_role"]),
                        str(column_metrics[column_index]),
                    )
                )
            semantic_periods = table_contract.get("semantic_periods") or []
            if column_index < len(semantic_periods):
                period_contract.update(semantic_periods[column_index])
        if not (percent or basis_points) and "yoy_change_amount" in metric_role:
            direction, direction_label, impact = _numeric_direction_contract(
                statement,
                match.span(),
            )
        elif not (percent or basis_points) and re.search(
                r"\b(?:decline|declined|decrease|decreased|fell|lower)\b.{0,35}$",
                statement[max(0, match.start() - 70) : match.start()],
                re.IGNORECASE,
            ):
            direction = -1.0
            direction_label = "decrease"
            impact = "adverse"
        if (
            unit in {"currency", "currency_per_share"}
            and re.search(r"\bto\s*$", statement[max(0, match.start() - 20) : match.start()], re.IGNORECASE)
        ):
            # "increased 12% to $69,154": the percentage is the change; the
            # amount following "to" is the reported period total.
            direction = 1.0
            direction_label = "neutral"
            impact = "neutral"

        fact_contract = _semantic_fact_contract(
            statement=statement,
            metric_role=metric_role,
            unit=unit,
            period_contract=period_contract,
            per_share=per_share,
            direction=direction_label,
            impact=impact,
        )
        if (
            fact_contract["fact_type"] in {"year_over_year_change", "contribution_to_change"}
            and period_contract.get("period_kind") == "duration"
            and period_contract.get("period_start")
            and period_contract.get("period_end")
        ):
            current_start = date.fromisoformat(str(period_contract["period_start"]))
            current_end = date.fromisoformat(str(period_contract["period_end"]))
            period_contract.update(
                {
                    "period_kind": "comparison",
                    "presentation_basis": "period_over_period_comparison",
                    "current_period_start": current_start.isoformat(),
                    "current_period_end": current_end.isoformat(),
                    "comparison_period_start": current_start.replace(year=current_start.year - 1).isoformat(),
                    "comparison_period_end": current_end.replace(year=current_end.year - 1).isoformat(),
                }
            )
        if (
            fact_contract["fact_type"] == "year_over_year_change"
            and "yoy_change" not in metric_role
            and str(period_contract.get("period_role") or "") in metric_role
        ):
            period_role = str(period_contract["period_role"])
            metric_role = metric_role.replace(
                period_role,
                f"yoy_change_{period_role}",
                1,
            )
        if fact_contract["fact_type"] in {
            "quarterly_rate",
            "annual_rate",
            "annualized_run_rate",
            "per_share_rate",
        }:
            period_contract.update(
                {
                    "period_kind": "rate",
                    "presentation_basis": (
                        "annualized_run_rate"
                        if fact_contract["fact_type"] == "annualized_run_rate"
                        else "effective_rate"
                    ),
                }
            )
            year_match = re.search(r"(?:^|_)fy(20\d{2})(?:_|$)", metric_role)
            if year_match:
                year = int(year_match.group(1))
                period_contract.update(
                    {
                        "period_start": date(year, 1, 1).isoformat(),
                        "period_end": date(year, 12, 31).isoformat(),
                        "effective_asof_dates": [date(year, 1, 1).isoformat()],
                    }
                )
        elif "prior_period" in metric_role and period_contract.get("period_start") and period_contract.get("period_end"):
            prior_start = date.fromisoformat(str(period_contract["period_start"]))
            prior_end = date.fromisoformat(str(period_contract["period_end"]))
            period_contract.update(
                {
                    "period_start": prior_start.replace(year=prior_start.year - 1).isoformat(),
                    "period_end": prior_end.replace(year=prior_end.year - 1).isoformat(),
                }
            )
        value = (
            direction * raw
            if basis_points
            else direction * raw / 100
            if percent
            else direction * raw * multiplier
        )
        display_unit = (
            f"{currency}/share"
            if unit == "currency_per_share" and currency
            else currency
            if unit == "currency" and currency
            else "basis_points"
            if basis_points
            else "percent"
            if percent
            else "count"
        )
        values.append(
            {
                "metric_name": f"operating_kpi_{metric_role}",
                "metric_role": metric_role,
                "value": value,
                "raw_text": _source_numeric_clause(statement, match.span()),
                "normalized_magnitude": abs(value),
                "signed_value": value,
                "direction": direction_label,
                "impact": impact,
                **fact_contract,
                "raw_value": raw,
                "unit": unit,
                "display_unit": display_unit,
                "dimension": (
                    "per_share"
                    if unit == "currency_per_share"
                    else "basis_points"
                    if basis_points
                    else "percent"
                    if percent
                    else "currency"
                    if currency
                    else "count"
                ),
                "source_scale": (
                    "basis_points"
                    if basis_points
                    else "percent"
                    if percent
                    else scale or "base"
                ),
                "source_unit": unit,
                "source_sign": int(direction),
                "currency": currency,
                "column_label": column_label,
                "row_metric": (table_contract or {}).get("row_metric"),
                "column_metric": (
                    (table_contract or {}).get("column_metrics", [])[column_index]
                    if column_index < len((table_contract or {}).get("column_metrics", []))
                    else None
                ),
                "segment": (
                    (table_contract or {}).get("segments", [])[column_index]
                    if column_index < len((table_contract or {}).get("segments", []))
                    else None
                ),
                "source_cell_status": "reported_value",
                "table_id": (table_contract or {}).get("table_id"),
                "cell_id": (
                    f"{table_contract['table_id']}:r1:c{column_index + 1}"
                    if table_contract
                    else None
                ),
                "row_key": (table_contract or {}).get("row_metric"),
                "column_key": (
                    (table_contract or {}).get("column_metrics", [])[column_index]
                    if column_index < len((table_contract or {}).get("column_metrics", []))
                    else None
                ),
                "source_locator": (
                    f"{table_contract['source_locator']}:r1:c{column_index + 1}"
                    if table_contract
                    else None
                ),
                "is_zero": value == 0,
                "is_not_applicable": False,
                "is_missing": False,
                **{key: value for key, value in period_contract.items() if key != "period_role"},
                "mapping_status": (
                    "unresolved"
                    if re.search(
                        r"\bfor each period\b",
                        statement[match.end() : match.end() + 90],
                        re.IGNORECASE,
                    )
                    else "unmapped"
                    if metric_role.startswith("unmapped_")
                    else "mapped"
                ),
            }
        )
    values.extend(
        _dash_cell_evidence(
            statement=statement,
            table_contract=table_contract,
            column_labels=column_labels,
            context_scale=context_scale,
            filing_date=filing_date,
            report_date=report_date,
            report_period_months=report_period_months,
        )
    )
    metric_totals: dict[str, int] = {}
    for item in values:
        name = str(item["metric_name"])
        metric_totals[name] = metric_totals.get(name, 0) + 1
    for item in values:
        if metric_totals[str(item["metric_name"])] > 1:
            # Ambiguous identities remain visible and fail closed.  Inventing a
            # positional suffix would make them unique without making them true.
            item["mapping_status"] = "unresolved"
    return values


MONTHS = {
    name.casefold(): index
    for index, name in enumerate(
        (
            "",
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        )
    )
    if name
}


def _paired_fiscal_week_duration(statement: str, match: re.Match[str]) -> int | None:
    """Map paired quarter/YTD prose without relying on global number position."""

    left = max(statement.rfind(".", 0, match.start()), statement.rfind(";", 0, match.start()))
    right_candidates = [
        boundary
        for boundary in (statement.find(".", match.end()), statement.find(";", match.end()))
        if boundary >= 0
    ]
    right = min(right_candidates) if right_candidates else len(statement)
    clause = statement[left + 1 : right]
    if not (
        re.search(r"\b(?:first|second|third|fourth) quarter\b", clause, re.IGNORECASE)
        and re.search(r"\b(?:first\s+)?thirty[- ]six weeks\b", clause, re.IGNORECASE)
    ):
        return None
    clause_offset = left + 1
    numeric = [
        item
        for item in NUMBER_RE.finditer(clause)
        if not _is_non_metric_number(clause, item)
        and not (
            not item.group("currency")
            and not item.group("percent")
            and not item.group("scale")
        )
    ]
    local_start = match.start() - clause_offset
    index = next(
        (idx for idx, item in enumerate(numeric) if item.start() == local_start),
        None,
    )
    if index is None:
        return None
    # Amount-plus-percent pairs encode one period per pair. Pure percentage
    # prose encodes one period per value (A and B in metric X).
    if numeric and all(item.group("percent") for item in numeric):
        return 12 if index % 2 == 0 else 36
    return 12 if index < 2 else 36


def _numeric_period_contract(
    statement: str,
    *,
    match: re.Match[str],
    number_index: int,
    column_label: str | None,
    filing_date: str | None,
    report_date: str | None = None,
    report_period_months: int | None = None,
) -> dict[str, Any]:
    economic_event_date = _economic_event_date(statement, match)
    if economic_event_date:
        return {
            "period_kind": "instant",
            "presentation_basis": "point_in_time",
            "period_start": None,
            "period_end": economic_event_date.isoformat(),
            "asof": economic_event_date.isoformat(),
            "period_role": f"event_{economic_event_date.isoformat()}",
        }
    inline_year = re.search(
        r"\b(20\d{2})\s*:\s*(?:C\$|US\$|A\$|HK\$|S\$|[$€£¥])?\s*$",
        statement[max(0, match.start() - 30) : match.start()],
        re.IGNORECASE,
    )
    if inline_year and report_date and report_period_months in {3, 6, 9, 12}:
        year = int(inline_year.group(1))
        reported_end = date.fromisoformat(report_date)
        period_end = reported_end.replace(year=year)
        period_start = _duration_start(period_end, report_period_months)
        return {
            "period_kind": "duration",
            "presentation_basis": "period_total",
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "period_role": f"{report_period_months}m_{period_end.isoformat()}",
        }
    label = str(column_label or "")
    ended_weeks = re.search(
        r"\b(\d+)W\s+ended\s+(20\d{2})-(\d{2})-(\d{2})\b",
        label,
        re.IGNORECASE,
    )
    if ended_weeks:
        weeks = int(ended_weeks.group(1))
        end = date(
            int(ended_weeks.group(2)),
            int(ended_weeks.group(3)),
            int(ended_weeks.group(4)),
        )
        if re.search(r"\btotal\s+(?:paid members|cardholders)\b", statement, re.IGNORECASE):
            return {
                "period_kind": "instant",
                "presentation_basis": "point_in_time",
                "period_start": None,
                "period_end": end.isoformat(),
                "asof": end.isoformat(),
                "period_role": f"asof_{end.isoformat()}",
            }
        start = end - timedelta(days=weeks * 7 - 1)
        return {
            "period_kind": "duration",
            "presentation_basis": "period_total",
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "period_role": f"{weeks}w_{end.isoformat()}",
        }
    ended_label = re.search(
        r"\b(3|6|9|12)M\s+ended\s+(20\d{2})-(\d{2})-(\d{2})\b",
        label,
        re.IGNORECASE,
    )
    if ended_label:
        months = int(ended_label.group(1))
        end = date(
            int(ended_label.group(2)),
            int(ended_label.group(3)),
            int(ended_label.group(4)),
        )
        start_month_index = end.year * 12 + end.month - months
        start_year, month_zero = divmod(start_month_index, 12)
        start = date(start_year, month_zero + 1, 1)
        return {
            "period_kind": "duration",
            "presentation_basis": "period_total",
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "period_role": f"{months}m_{end.isoformat()}",
        }
    quarter = re.search(r"\bQ([1-4])\s*(20\d{2})\b", label, re.IGNORECASE)
    if quarter:
        q, year = int(quarter.group(1)), int(quarter.group(2))
        start_month = (q - 1) * 3 + 1
        end_month = start_month + 2
        start = date(year, start_month, 1).isoformat()
        end = date(year, end_month, monthrange(year, end_month)[1]).isoformat()
        role = f"q{q}_{year}_{_slug(label.replace(quarter.group(0), '')) or 'reported'}"
        return {
            "period_kind": "duration",
            "presentation_basis": "period_total",
            "period_start": start,
            "period_end": end,
            "period_role": role,
        }
    fiscal_year = re.fullmatch(r"FY(20\d{2})", label, re.IGNORECASE)
    if fiscal_year and report_date:
        year = int(fiscal_year.group(1))
        reported_end = date.fromisoformat(report_date)
        period_end = reported_end.replace(year=year)
        period_start = _duration_start(period_end, 12)
        return {
            "period_kind": "duration",
            "presentation_basis": "period_total",
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "period_role": f"fy{year}",
        }

    paired_weeks = _paired_fiscal_week_duration(statement, match)
    if report_date and paired_weeks:
        period_end = date.fromisoformat(report_date)
        period_start = period_end - timedelta(days=paired_weeks * 7 - 1)
        prior_end = period_end.replace(year=period_end.year - 1)
        prior_start = prior_end - timedelta(days=paired_weeks * 7 - 1)
        return {
            "period_kind": "comparison",
            "presentation_basis": "period_over_period_comparison",
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "current_period_start": period_start.isoformat(),
            "current_period_end": period_end.isoformat(),
            "comparison_period_start": prior_start.isoformat(),
            "comparison_period_end": prior_end.isoformat(),
            "period_role": f"yoy_change_{paired_weeks}w_{period_end.isoformat()}",
        }

    ended = re.search(
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s*(20\d{2})\b",
        statement,
        re.IGNORECASE,
    )
    period_end = None
    if ended:
        period_end = date(
            int(ended.group(3)),
            MONTHS[ended.group(1).casefold()],
            int(ended.group(2)),
        )
    nearby = statement[max(0, match.start() - 180) : match.end() + 180].casefold()
    if (
        period_end
        and "as of" in nearby
        and re.search(
            r"\bremaining (?:authorization|(?:share )?repurchase authorization)\b",
            nearby,
        )
    ):
        return {
            "period_kind": "instant",
            "presentation_basis": "point_in_time",
            "period_start": None,
            "period_end": period_end.isoformat(),
            "period_role": f"asof_{period_end.isoformat()}",
        }
    if "last quarter" in nearby:
        if report_date and report_period_months in {3, 6, 9, 12}:
            current_end = date.fromisoformat(report_date)
            current_start = _duration_start(current_end, report_period_months)
            prior_end = current_start - timedelta(days=1)
            prior_start = _duration_start(prior_end, report_period_months)
            return {
                "period_kind": "duration",
                "presentation_basis": "period_total",
                "period_start": prior_start.isoformat(),
                "period_end": prior_end.isoformat(),
                "period_role": "previous_quarter",
            }
        return {
            "period_kind": "unknown",
            "presentation_basis": "period_total",
            "period_start": None,
            "period_end": None,
            "period_role": "previous_quarter",
        }
    if "this quarter" in nearby:
        if report_date and report_period_months in {3, 6, 9, 12}:
            current_end = date.fromisoformat(report_date)
            current_start = _duration_start(current_end, report_period_months)
            return {
                "period_kind": "duration",
                "presentation_basis": "period_total",
                "period_start": current_start.isoformat(),
                "period_end": current_end.isoformat(),
                "period_role": "current_quarter",
            }
        return {
            "period_kind": "unknown",
            "presentation_basis": "period_total",
            "period_start": None,
            "period_end": None,
            "period_role": "current_quarter",
        }
    duration_months = None
    if re.search(r"three and six months ended", nearby):
        paired_amount_and_ratio = re.search(
            r"[$€£¥].{0,40}%\s*,?\s*(?:and|versus|vs\.)\s*[$€£¥].{0,40}%",
            statement,
            re.IGNORECASE,
        )
        period_slot = number_index // 2 if paired_amount_and_ratio else number_index
        duration_months = 3 if period_slot % 2 == 0 else 6
    elif re.search(r"six months ended", nearby):
        duration_months = 6
    elif re.search(r"three months ended|second quarter|first quarter|third quarter|fourth quarter", nearby):
        duration_months = 3
    if period_end and duration_months:
        start_month_index = period_end.year * 12 + period_end.month - duration_months
        start_year, month_zero = divmod(start_month_index, 12)
        start = date(start_year, month_zero + 1, 1)
        if match.group("percent") and re.search(
            r"\b(?:growth|grew|increase|increased|decrease|decreased|decline|declined)\b",
            nearby,
        ):
            prior_end = date(period_end.year - 1, period_end.month, period_end.day)
            prior_start = _duration_start(prior_end, duration_months)
            return {
                "period_kind": "comparison",
                "presentation_basis": "period_over_period_comparison",
                "period_start": start.isoformat(),
                "period_end": period_end.isoformat(),
                "current_period_start": start.isoformat(),
                "current_period_end": period_end.isoformat(),
                "comparison_period_start": prior_start.isoformat(),
                "comparison_period_end": prior_end.isoformat(),
                "period_role": f"yoy_change_{duration_months}m_{period_end.isoformat()}",
            }
        return {
            "period_kind": "duration",
            "presentation_basis": "period_total",
            "period_start": start.isoformat(),
            "period_end": period_end.isoformat(),
            "period_role": f"{duration_months}m_{period_end.isoformat()}",
        }
    guidance_year = re.search(r"\b(?:full[- ]year|FY)\s*(20\d{2})\b", statement, re.IGNORECASE)
    if guidance_year or "outlook" in statement.casefold() or "guidance" in statement.casefold():
        year = int(guidance_year.group(1)) if guidance_year else int((filing_date or "0000")[:4])
        if year >= 1900:
            return {
                "period_kind": "guidance",
                "presentation_basis": "guidance_range",
                "period_start": date(year, 1, 1).isoformat(),
                "period_end": date(year, 12, 31).isoformat(),
                "period_role": f"fy{year}_guidance",
            }
    relational_role = _comparison_number_role(statement, match)
    if report_date and report_period_months in {3, 6, 9, 12} and relational_role:
        current_end = date.fromisoformat(report_date)
        current_start = _duration_start(current_end, report_period_months)
        prior_end = date(current_end.year - 1, current_end.month, current_end.day)
        prior_start = _duration_start(prior_end, report_period_months)
        if relational_role.startswith("prior_year"):
            return {
                "period_kind": "duration",
                "presentation_basis": "period_total",
                "period_start": prior_start.isoformat(),
                "period_end": prior_end.isoformat(),
                "period_role": relational_role,
            }
        if relational_role.startswith("yoy_change"):
            return {
                "period_kind": "comparison",
                "presentation_basis": "period_over_period_comparison",
                "period_start": current_start.isoformat(),
                "period_end": current_end.isoformat(),
                "current_period_start": current_start.isoformat(),
                "current_period_end": current_end.isoformat(),
                "comparison_period_start": prior_start.isoformat(),
                "comparison_period_end": prior_end.isoformat(),
                "period_role": relational_role,
            }
        return {
            "period_kind": "duration",
            "presentation_basis": "period_total",
            "period_start": current_start.isoformat(),
            "period_end": current_end.isoformat(),
            "period_role": relational_role,
        }
    if (
        report_date
        and report_period_months in {3, 6, 9, 12}
        and match.group("percent")
        and re.search(
            r"\b(?:growth|grew|increase|increased|decrease|decreased|decline|declined)\b",
            nearby,
        )
    ):
        current_end = date.fromisoformat(report_date)
        current_start = _duration_start(current_end, report_period_months)
        prior_end = date(current_end.year - 1, current_end.month, current_end.day)
        prior_start = _duration_start(prior_end, report_period_months)
        return {
            "period_kind": "comparison",
            "presentation_basis": "period_over_period_comparison",
            "period_start": current_start.isoformat(),
            "period_end": current_end.isoformat(),
            "current_period_start": current_start.isoformat(),
            "current_period_end": current_end.isoformat(),
            "comparison_period_start": prior_start.isoformat(),
            "comparison_period_end": prior_end.isoformat(),
            "period_role": f"yoy_change_{report_period_months}m_{current_end.isoformat()}",
        }
    if report_date and report_period_months in {3, 6, 9, 12}:
        current_end = date.fromisoformat(report_date)
        fiscal_week_quarter = (
            report_period_months == 3
            and current_end.day != monthrange(current_end.year, current_end.month)[1]
            and re.search(r"\b(?:first|second|third|fourth) quarter\b", nearby, re.IGNORECASE)
        )
        current_start = (
            current_end - timedelta(days=12 * 7 - 1)
            if fiscal_week_quarter
            else _duration_start(current_end, report_period_months)
        )
        return {
            "period_kind": "duration",
            "presentation_basis": "period_total",
            "period_start": current_start.isoformat(),
            "period_end": current_end.isoformat(),
            "period_role": (
                f"12w_{current_end.isoformat()}"
                if fiscal_week_quarter
                else f"{report_period_months}m_{current_end.isoformat()}"
            ),
        }
    return {
        "period_kind": "unknown",
        "presentation_basis": "unknown",
        "period_start": None,
        "period_end": None,
        "period_role": "period_unmapped",
    }


def _numeric_metric_role(
    statement: str,
    *,
    owner: str,
    match: re.Match[str],
    column_label: str | None,
    period_role: str,
    number_index: int,
) -> str:
    context = statement[max(0, match.start() - 130) : match.end() + 90].casefold()
    metric = (
        "free_cash_flow_ex_sustainability_growth_actual"
        if re.search(
            r"free cash flow without sustainability growth investments",
            statement,
            re.IGNORECASE,
        )
        else _statement_metric_base(statement)
    )
    semantic_rules = (
        ("membership_fee_revenue", r"membership fee revenue"),
        ("reported_sales", r"reported sales growth|sales (?:increased|growth).{0,24}reported basis"),
        ("digital_sales", r"digital sales|e-?commerce sales|digitally-enabled comparable sales"),
        ("comparable_sales", r"comparable sales|comp sales"),
        ("traffic_frequency", r"(?:shopping\s+)?frequency|\btraffic\b"),
        ("average_ticket", r"average ticket|average basket"),
        ("net_new_warehouses", r"net new warehouses?|new warehouses?"),
        ("internalization", r"internalization"),
        ("landfill_depletable_tons", r"depletable tons"),
        ("acquired_annualized_revenue", r"annualized revenue"),
        ("pension_contributions", r"(?:defined benefit )?pension plans?"),
        ("free_cash_flow", r"free cash flow|\bfcf\b"),
        ("adjusted_operating_ebitda_margin", r"adjusted operating ebitda margin"),
        ("operating_ebitda_margin", r"operating ebitda margin"),
        ("adjusted_operating_ebitda", r"adjusted operating ebitda"),
        ("operating_ebitda", r"operating ebitda|\bebitda\b"),
        ("share_repurchases", r"share repurchases?|stock repurchases?"),
        ("cash_dividends", r"cash dividends?|dividend payments?"),
        ("shareholder_returns", r"returned?.{0,50}shareholders"),
        ("revenue", r"revenues?|sales"),
        ("operating_income", r"income from operations|operating income"),
        ("operating_expenses", r"operating expenses"),
        ("landfill_average_yield", r"landfill.{0,180}average yield"),
        ("collection_disposal_yield", r"yield"),
        ("core_price", r"core price"),
        ("collection_disposal_volume", r"collection and disposal volume"),
        ("landfill_volume", r"landfill volumes?"),
        ("residential_volume", r"residential volume"),
        ("basis_point_change", r"basis points?"),
        (
            "acquisition_net_cash_paid",
            r"acquisitions? of businesses(?: and technologies)?(?:, net of cash acquired)?|net cash paid",
        ),
    )
    closest_metric = _closest_semantic_metric(statement, match, semantic_rules)
    generic_owners = {
        "capital_allocation",
        "free_cash_flow_guidance",
        "operating_ebitda",
        "segment_growth",
        "statement_context",
        "volume",
    }
    if metric is None:
        if owner not in generic_owners:
            metric = owner
        elif closest_metric and _metric_label_is_local(
            statement,
            match,
            semantic_rules,
            closest_metric,
        ):
            metric = closest_metric
        else:
            metric = owner if owner != "statement_context" else None
    if closest_metric in {
        "reported_sales",
        "comparable_sales",
        "traffic_frequency",
        "average_ticket",
        "net_new_warehouses",
        "digital_sales",
        "internalization",
        "landfill_depletable_tons",
        "acquired_annualized_revenue",
        "pension_contributions",
        "landfill_average_yield",
        "collection_disposal_yield",
        "core_price",
        "acquisition_net_cash_paid",
    } and _metric_label_is_local(statement, match, semantic_rules, closest_metric):
        metric = closest_metric
    component_metric = _component_metric_override(statement, match)
    if component_metric:
        metric = component_metric
    elif _is_per_share_value(statement, match) and re.search(
        r"\bdividends?\b",
        statement,
        re.IGNORECASE,
    ):
        # The governing "per share dividend" label can precede a compact
        # current/prior rate pair by more than the normal local-label window.
        # Both rates still belong to the dividend metric, not to an unresolved
        # statement-context bucket.
        metric = "cash_dividends"
    label_role = _slug(str(column_label or ""))
    if metric is None and owner != "statement_context":
        metric = owner
    if metric is None:
        return f"unmapped_{owner}_{period_role}_{label_role or 'numeric'}"
    if label_role and label_role in period_role:
        label_role = ""
    variant = (
        ""
        if period_role.endswith(("_value", "_ratio", "_amount", "_percent"))
        else _numeric_metric_variant(statement, match, number_index)
    )
    unit_variant = (
        "ratio"
        if match.group("percent")
        else "amount"
        if match.group("currency")
        else ""
    )
    if variant and unit_variant and unit_variant not in variant:
        variant = f"{variant}_{unit_variant}"
    return "_".join(
        part for part in (metric, period_role, label_role, variant) if part
    )


def _statement_metric_base(statement: str) -> str | None:
    normalized = statement.lstrip("•·● ").casefold()
    rules = (
        ("volume_revenue", r"^(?:our\s+)?revenues? from volume\b"),
        ("revenue", r"^(?:our\s+)?revenues?\b"),
        ("revenue", r"^(?:our\s+)?net sales\b"),
        ("operating_expenses", r"^operating expenses\b"),
        ("operating_income", r"^(?:income from operations|operating income)\b"),
    )
    return next((name for name, pattern in rules if re.search(pattern, normalized)), None)


def _comparison_number_role(statement: str, match: re.Match[str]) -> str | None:
    """Name common current/prior/change tuples without positional IDs."""

    compared = re.search(r"\bcompared (?:to|with)\b", statement, re.IGNORECASE)
    if not compared:
        return None
    before = statement[: match.start()].casefold()
    after = statement[match.end() : match.end() + 70].casefold()
    compared_at = max(before.rfind("compared to"), before.rfind("compared with"))
    change_at = max(before.rfind("increase"), before.rfind("decrease"))
    is_percent = bool(match.group("percent"))
    if re.search(r"^\s*(?:million|billion|bn|mn)?\s*(?:increase|decrease)\b", after):
        return "yoy_change_percent" if is_percent else "yoy_change_amount"
    if change_at > compared_at and match.start() - change_at <= 90:
        return "yoy_change_percent" if is_percent else "yoy_change_amount"
    if compared_at >= 0 and match.start() - compared_at <= 170:
        return "prior_year_ratio" if is_percent else "prior_year_value"
    if 0 <= compared.start() - match.end() <= 170:
        return "current_period_ratio" if is_percent else "current_period_value"
    return None


def _duration_start(period_end: date, months: int) -> date:
    month_index = period_end.year * 12 + period_end.month - months
    year, month_zero = divmod(month_index, 12)
    return date(year, month_zero + 1, 1)


def _economic_event_date(statement: str, match: re.Match[str]) -> date | None:
    """Return the nearest preceding transaction date for an economic event."""

    if not re.search(
        r"\b(?:acquisition|acquired|transaction|issued|repaid|redeemed)\b",
        statement,
        re.IGNORECASE,
    ):
        return None
    candidates = list(
        re.finditer(
            r"\b(?:On\s+)?"
            r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
            r"(\d{1,2}),\s*(20\d{2})\b",
            statement[: match.start()],
            re.IGNORECASE,
        )
    )
    if not candidates:
        return None
    selected = candidates[-1]
    return date(
        int(selected.group(3)),
        MONTHS[selected.group(1).casefold()],
        int(selected.group(2)),
    )


def _closest_semantic_metric(
    statement: str,
    match: re.Match[str],
    semantic_rules: tuple[tuple[str, str], ...],
) -> str | None:
    candidates: list[tuple[int, int, str]] = []
    for priority, (name, pattern) in enumerate(semantic_rules):
        for label in re.finditer(pattern, statement, re.IGNORECASE):
            candidates.append(
                (_semantic_distance(match.span(), label.span()), priority, name)
            )
    return min(candidates)[2] if candidates else None


def _metric_label_is_local(
    statement: str,
    match: re.Match[str],
    semantic_rules: tuple[tuple[str, str], ...],
    metric_name: str,
) -> bool:
    """Let a nearby explicit label override a sentence-level metric owner."""

    patterns = [pattern for name, pattern in semantic_rules if name == metric_name]
    distances = [
        _semantic_distance(match.span(), label.span())
        for pattern in patterns
        for label in re.finditer(pattern, statement, re.IGNORECASE)
    ]
    return bool(distances) and min(distances) <= 80


def _numeric_metric_variant(
    statement: str,
    match: re.Match[str],
    number_index: int,
) -> str:
    before = statement[max(0, match.start() - 170) : match.start()].casefold()
    after = statement[match.end() : match.end() + 100].casefold()
    if "renewal rate" in statement.casefold():
        local_after = statement[match.end() : match.end() + 45]
        if re.search(r"\b(?:u\.s\.|united states).{0,20}canada\b", local_after, re.IGNORECASE):
            return "us_canada"
        if re.search(r"\bworldwide\b", local_after, re.IGNORECASE):
            return "worldwide"
    if "between" in before:
        prior_range_values = list(NUMBER_RE.finditer(before.rsplit("between", 1)[-1]))
        if not prior_range_values:
            return "range_low"
        if re.search(r"\b(?:and|to)\s*$", before):
            return "range_high"
    if re.match(
        r"^\s*(?:million|billion|bn|mn)?\s*on an adjusted basis\b",
        after,
    ) or "adjusted basis" in before[-45:]:
        return "adjusted_change"
    if re.match(r"^\s*(?:%|,|or)?\s*(?:when removing|excluding)\b", after):
        return "excluding_adjustment"
    if re.search(r"\bwhen removing\b|\bexcluding\b", after[:70]):
        return "reported"
    if "when removing" in before or "excluding" in before:
        return "excluding_adjustment"
    if re.search(r"\bin\s+20\d{2}\b", after[:35]):
        year = re.search(r"\bin\s+(20\d{2})\b", after[:35])
        return f"fy{year.group(1)}" if year else ""
    if "respectively" in statement.casefold() and re.search(r"20\d{2}\s+and\s+20\d{2}", statement):
        return "current_period" if number_index == 0 else "prior_period" if number_index == 1 else ""
    if match.group("percent"):
        return "ratio"
    trailing = statement[match.end() : match.end() + 35]
    if re.match(r"\s*(?:-|–|—)?\s*basis points?\b", trailing, re.IGNORECASE):
        return "basis_points"
    if match.group("currency"):
        return "amount"
    return ""


def _is_non_metric_number(statement: str, match: re.Match[str]) -> bool:
    before = statement[max(0, match.start() - 24) : match.start()]
    after = statement[match.end() : match.end() + 16]
    if (
        match.start() > 0
        and statement[match.start() - 1] == "("
        and re.match(r"s\)\s*", after, re.IGNORECASE)
        and set(match.group("number").replace(",", "")) == {"0"}
    ):
        # Presentation-scale markers such as ``(000s)`` describe the row;
        # their zeroes are not a table cell and must not shift column binding.
        return True
    if (
        match.start() > 0
        and statement[match.start() - 1] == "("
        and re.match(r"\)\s*", statement[match.end() :])
        and match.start() <= 3
        and "," not in match.group("number")
        and float(match.group("number")) <= 99
        and not match.group("currency")
        and not match.group("scale")
        and not match.group("percent")
    ):
        return True
    if (
        match.start() > 0
        and statement[match.start() - 1] in {"%", ")"}
        and re.match(r"\s*(?:[.,;:]|$)", after)
    ):
        # SEC footnote anchors such as ``7.5%1`` are not standalone facts.
        return True
    if re.search(
        r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)$",
        before.rstrip(),
        re.IGNORECASE,
    ) and re.match(r",\s*20\d{2}\b", after):
        return True
    if re.search(r"\b(?:Note|Item|Form)$", before.rstrip(), re.IGNORECASE):
        return True
    return False


def _is_material_operating_count(statement: str, match: re.Match[str]) -> bool:
    local = statement[max(0, match.start() - 45) : match.end() + 55]
    return re.search(
        r"\b(?:net new warehouses?|new warehouses?|paid members?|cardholders?|"
        r"stores?|locations?|customers?|subscribers?|employees?)\b",
        local,
        re.IGNORECASE,
    ) is not None


def _is_forward_looking_boilerplate(statement: str) -> bool:
    lowered = statement.casefold()
    return (
        "forward-looking statements" in lowered
        or (
            "from time to time" in lowered
            and "estimates or projections" in lowered
            and "future periods" in lowered
        )
    )


def _is_broken_leading_fragment(statement: str) -> bool:
    """Reject page-break tails that begin inside a parenthetical phrase."""

    return re.match(r"^[a-z][a-z-]{2,30}\)\s", statement.strip()) is not None


def _bounded_source_summary(statement: str, *, limit: int = 1800) -> str:
    """Truncate only at a complete sentence boundary."""

    normalized = statement.strip()
    if len(normalized) <= limit:
        return normalized
    candidate = normalized[: limit + 1]
    boundaries = [match.end() for match in re.finditer(r"[.!?](?=\s|$)", candidate)]
    return candidate[: boundaries[-1]].strip() if boundaries else normalized


def _component_metric_override(
    statement: str,
    match: re.Match[str],
) -> str | None:
    after = statement[match.end() : match.end() + 70].casefold()
    before = statement[max(0, match.start() - 70) : match.start()].casefold()
    next_number = NUMBER_RE.search(after)
    component_window = after[: next_number.start()] if next_number else after
    local = f"{before} {component_window}"
    transaction_context = statement.casefold()
    if re.search(r"\b(?:net new warehouses?|new warehouses?)\b", local):
        return "net_new_warehouses"
    if _is_per_share_value(statement, match) and re.search(
        r"\b(?:acquisition|purchase price|transaction)\b",
        transaction_context,
    ):
        return "acquisition_purchase_price_per_share"
    if re.search(r"\bassum(?:ed|ption)\b.{0,80}\bdebt\b", local):
        return "acquisition_assumed_debt"
    if re.search(
        r"\b(?:issued|issuance)\b.{0,90}\b(?:debt|notes?)\b|"
        r"\b(?:debt|notes?)\b.{0,90}\b(?:issued|issuance)\b",
        local,
    ) and re.search(r"\b(?:acquisition|transaction)\b", transaction_context):
        return "acquisition_debt_issued"
    if re.search(
        r"\b(?:completed|purchase price|total consideration)\b.{0,100}\b(?:acquisition|transaction)\b|"
        r"\b(?:acquisition|transaction)\b.{0,100}\b(?:completed|purchase price|total consideration)\b",
        local,
    ):
        return "acquisition_total_consideration"
    if match.group("percent") and re.search(r"\breward\b", local):
        return "membership_reward_rate"
    if re.search(r"\b(?:maximum )?reward\b", local) and re.search(r"\bper year\b", after):
        return "membership_reward_cap"
    if re.search(r"\bannual fee\b", local):
        return "membership_annual_fee"
    if re.search(r"\bsales penetration\b", local):
        return "executive_member_sales_penetration"
    # Paired prose often states both values before their label, for example
    # "2% and 3% in shopping frequency".  Bind that compact pair to the
    # following explicit label instead of the preceding metric phrase.
    right_label_window = after[:100]
    if len(list(NUMBER_RE.finditer(right_label_window.split(".", 1)[0]))) <= 1:
        for name, pattern in (
            ("traffic_frequency", r"\bin\s+(?:shopping\s+)?frequency\b"),
            ("average_ticket", r"\bin\s+(?:the\s+)?average ticket\b"),
            ("digital_sales", r"\bin\s+(?:digital|e-?commerce) sales\b"),
        ):
            if re.search(pattern, right_label_window, re.IGNORECASE):
                return name
    if re.search(
        r"\bremaining (?:authorization|(?:share )?repurchase authorization)\b",
        f"{before} {component_window}",
    ):
        return "share_repurchase_authorization_remaining"
    component_rules = (
        ("share_repurchases", r"\b(?:share|stock) repurchases?\b"),
        ("cash_dividends", r"\bcash dividends?\b"),
    )
    for name, pattern in component_rules:
        if re.search(pattern, component_window):
            return name
    if re.search(r"\bexcluding\b", before) and "volume" in before:
        if "landfill" in before:
            return "landfill_volume"
        if "collection" in before:
            return "collection_disposal_volume"
    return None


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


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
        if marker.end() <= current.start() and re.fullmatch(
            r"\s*(?:[-–—]\s*)?(?:20\d{2}\s*:\s*)?",
            between,
        ):
            return True
        if (
            marker.end() <= current.start()
            and len(between) <= 120
            and ")" not in between
            and re.search(r"\b20\d{2}\s*:", between)
        ):
            return True
        if len(between) <= 160 and not re.search(r"[;:]|\.(?:\s|$)", between):
            return True
    return False


def _is_base_currency_value(statement: str, current: re.Match[str]) -> bool:
    """Do not apply statement-scale millions to per-member fee/rate caps."""

    nearby = statement[max(0, current.start() - 80) : current.end() + 80]
    return re.search(
        r"\b(?:annual fee|per (?:member|year)|maximum reward)\b",
        nearby,
        re.IGNORECASE,
    ) is not None


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
    # SEC tables frequently split scale, duration headers, years and spacer
    # cells into separate HTML blocks.  Use the same bounded lookback as the
    # period-label parser while still stopping at intervening prose.
    for prior in reversed(blocks[max(0, index - 20) : index]):
        inherited = _scale_from_text(prior)
        if inherited:
            return inherited
        if len(prior) > 180 and re.search(r"[.!?]", prior):
            break
    return None


def _looks_like_table_value_row(statement: str) -> bool:
    """Reject stale inherited headers for ordinary filing prose."""

    normalized = statement.strip()
    if len(normalized.split()) > 22:
        return False
    if re.search(r"\b(?:we|our|company|during|respectively|primarily due)\b", normalized, re.IGNORECASE):
        return False
    return len(list(NUMBER_RE.finditer(normalized))) >= 2


def _scale_from_text(value: str) -> str | None:
    if re.search(r"\(\s*0{3}s\s*\)", value, flags=re.IGNORECASE):
        return "thousand"
    match = re.search(
        r"\b(?:in\s+)?(?P<scale>billions?|millions?|thousands?)\b",
        value,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    return match.group("scale").casefold().removesuffix("s")


def _document_currency_scale(blocks: list[str]) -> str | None:
    """Return an issuer-declared document-wide monetary presentation scale.

    This convention is only used for values carrying an explicit currency
    symbol.  Bare counts and percentages must not inherit it.
    """

    declarations = [
        match.group("scale").casefold().removesuffix("s")
        for block in blocks
        for match in re.finditer(
            r"\bamounts?\s+in\s+(?P<scale>billions?|millions?|thousands?)\b",
            block,
            re.IGNORECASE,
        )
    ]
    if not declarations:
        return None
    unique = set(declarations)
    return declarations[0] if len(unique) == 1 else None


def _inherited_column_labels(
    blocks: list[str],
    index: int,
    *,
    filing_year: int,
) -> list[str] | None:
    """Bind the common reported/adjusted four-column release layout."""

    table_contract = _table_contract(blocks, index)
    if table_contract:
        return list(table_contract["column_labels"])
    context = " ".join(blocks[max(0, index - 20) : index])
    fiscal_week_header = re.search(
        r"(?P<short>\d+)\s+Weeks\s+Ended\s*(?P<long>\d+)\s+Weeks\s+Ended",
        context,
        re.IGNORECASE,
    )
    if fiscal_week_header:
        header_tail = context[fiscal_week_header.start() :]
        dates = [
            date(
                int(match.group(3)),
                MONTHS[match.group(1).casefold()],
                int(match.group(2)),
            )
            for match in re.finditer(
                r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
                r"(\d{1,2}),?\s*(20\d{2})",
                header_tail,
                re.IGNORECASE,
            )
        ]
        if len(dates) >= 4:
            weeks = (
                int(fiscal_week_header.group("short")),
                int(fiscal_week_header.group("short")),
                int(fiscal_week_header.group("long")),
                int(fiscal_week_header.group("long")),
            )
            return [
                f"{week_count}W ended {period_end.isoformat()}"
                for week_count, period_end in zip(weeks, dates[:4])
            ]
    if len(re.findall(r"\bAs Reported\b", context, re.IGNORECASE)) >= 2 and len(
        re.findall(r"\bAs Adjusted", context, re.IGNORECASE)
    ) >= 2:
        return [
            f"Q2 {filing_year} as reported",
            f"Q2 {filing_year} as adjusted",
            f"Q2 {filing_year - 1} as reported",
            f"Q2 {filing_year - 1} as adjusted",
        ]
    duration_header = re.search(
        r"Three Months Ended\s+Six Months Ended.*?"
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}).*?"
        r"(20\d{2})\s+(20\d{2})\s+(20\d{2})\s+(20\d{2})",
        context,
        re.IGNORECASE,
    )
    if duration_header:
        month = MONTHS[duration_header.group(1).casefold()]
        day = int(duration_header.group(2))
        years = [int(duration_header.group(index)) for index in range(3, 7)]
        return [
            f"{months}M ended {date(year, month, day).isoformat()}"
            for months, year in zip((3, 3, 6, 6), years)
        ]
    single_duration_header = re.search(
        r"(Three|Six|Nine|Twelve) Months Ended\s+"
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
        r"(\d{1,2}).*?(20\d{2})\s+(20\d{2})",
        context,
        re.IGNORECASE,
    )
    if single_duration_header and not (
        re.search(r"Three Months Ended", context, re.IGNORECASE)
        and re.search(r"Six Months Ended", context, re.IGNORECASE)
    ):
        duration_months = {
            "three": 3,
            "six": 6,
            "nine": 9,
            "twelve": 12,
        }[single_duration_header.group(1).casefold()]
        month = MONTHS[single_duration_header.group(2).casefold()]
        day = int(single_duration_header.group(3))
        return [
            f"{duration_months}M ended {date(int(year), month, day).isoformat()}"
            for year in single_duration_header.group(4, 5)
        ]
    prior_blocks = blocks[max(0, index - 20) : index]
    if (
        any(re.search(r"Three Months Ended", value, re.IGNORECASE) for value in prior_blocks)
        and any(re.search(r"Six Months Ended", value, re.IGNORECASE) for value in prior_blocks)
    ):
        month_match = next(
            (
                re.search(
                    r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})",
                    value,
                    re.IGNORECASE,
                )
                for value in reversed(prior_blocks)
                if re.search(
                    r"January|February|March|April|May|June|July|August|September|October|November|December",
                    value,
                    re.IGNORECASE,
                )
            ),
            None,
        )
        year_values = next(
            (
                re.findall(r"\b20\d{2}\b", value)
                for value in reversed(prior_blocks)
                if len(re.findall(r"\b20\d{2}\b", value)) >= 4
            ),
            [],
        )
        if month_match and len(year_values) >= 4:
            month = MONTHS[month_match.group(1).casefold()]
            day = int(month_match.group(2))
            return [
                f"{months}M ended {date(int(year), month, day).isoformat()}"
                for months, year in zip((3, 3, 6, 6), year_values[:4])
            ]
    fiscal_years = next(
        (
            re.findall(r"20\d{2}", value)
            for value in reversed(prior_blocks)
            if 2 <= len(re.findall(r"20\d{2}", value)) <= 5
            and len(value) <= 80
        ),
        [],
    )
    if fiscal_years:
        return [f"FY{year}" for year in fiscal_years]
    return None


def _table_contract(
    blocks: list[str],
    index: int,
    *,
    column_labels: list[str] | None = None,
    accession_number: str | None = None,
) -> dict[str, Any] | None:
    """Recover row/column meaning from bounded SEC table headers."""

    statement = blocks[index]
    source_locator = f"{accession_number or 'source'}:block-{index + 1}"
    table_id = "TABLE_" + hashlib.sha256(
        f"{accession_number or ''}|{index}|{statement}".encode("utf-8")
    ).hexdigest()[:16].upper()

    number_matches = [
        match for match in NUMBER_RE.finditer(statement)
        if not _is_non_metric_number(statement, match)
        and (
            match.group("currency")
            or match.group("percent")
            or match.group("scale")
            or re.match(
                r"\s*(?:-|–|—)?\s*basis points?\b",
                statement[match.end() :],
                flags=re.IGNORECASE,
            )
        )
    ]
    if column_labels and all(re.fullmatch(r"FY20\d{2}", label) for label in column_labels):
        all_numbers = [
            match
            for match in NUMBER_RE.finditer(statement)
            if not _is_non_metric_number(statement, match)
        ]
        if len(all_numbers) == len(column_labels):
            row_label = statement[: all_numbers[0].start()].strip(" :-")
            row_metric = _slug(row_label)
            return {
                "table_id": table_id,
                "source_id": None,
                "source_locator": source_locator,
                "title": row_label,
                "subtitle": None,
                "header_rows": [list(column_labels)],
                "row_headers": [row_label],
                "column_headers": list(column_labels),
                "row_dimension": "metric",
                "column_dimension": "fiscal_period",
                "period_axis": list(column_labels),
                "metric_axis": ["reported_value"] * len(column_labels),
                "unit_axis": ["count"] * len(column_labels),
                "currency_axis": [None] * len(column_labels),
                "comparison_axis": [None] * len(column_labels),
                "value_role": ["period_total"] * len(column_labels),
                "table_semantic_type": "fiscal_year_series",
                "row_metric": row_metric,
                "source_scale": _inherited_block_scale(blocks, index),
                "column_metrics": ["reported_value"] * len(column_labels),
                "column_labels": list(column_labels),
                "segments": [None] * len(column_labels),
                "semantic_periods": [],
                "cells": [],
            }
    if column_labels and _is_period_measure_table_row(number_matches, column_labels):
        current_labels = [column_labels[0], column_labels[0], column_labels[2], column_labels[2]]
        periods = [_short_period_label(column_labels[0]), _short_period_label(column_labels[2])]
        metric_axis = ["year_over_year_change_usd", "share_of_total_pct"]
        comparison_periods = []
        for column_index, label in enumerate(current_labels):
            period = _period_contract_for_table_label(
                label,
                filing_date=None,
                report_date=None,
                report_period_months=None,
            )
            if column_index % 2 == 0 and period.get("period_start") and period.get("period_end"):
                start = date.fromisoformat(str(period["period_start"]))
                end = date.fromisoformat(str(period["period_end"]))
                period.update(
                    {
                        "period_kind": "comparison",
                        "presentation_basis": "period_over_period_comparison",
                        "current_period_start": start.isoformat(),
                        "current_period_end": end.isoformat(),
                        "comparison_period_start": start.replace(year=start.year - 1).isoformat(),
                        "comparison_period_end": end.replace(year=end.year - 1).isoformat(),
                    }
                )
            comparison_periods.append(period)
        columns = [metric_axis[0], metric_axis[1], metric_axis[0], metric_axis[1]]
        return {
            "table_id": table_id,
            "source_id": None,
            "source_locator": source_locator,
            "title": statement.split("$", 1)[0].strip(),
            "subtitle": None,
            "header_rows": [list(column_labels), ["Amount", "% of total", "Amount", "% of total"]],
            "row_headers": [statement.split("$", 1)[0].strip()],
            "column_headers": [
                f"{period} {metric}"
                for period in periods
                for metric in metric_axis
            ],
            "row_dimension": "metric",
            "column_dimension": "period_x_measure",
            "period_axis": periods,
            "metric_axis": metric_axis,
            "unit_axis": ["currency", "percent", "currency", "percent"],
            "currency_axis": ["USD", None, "USD", None],
            "comparison_axis": [
                _short_period_label(column_labels[1]),
                None,
                _short_period_label(column_labels[3]),
                None,
            ],
            "value_role": [
                "year_over_year_change",
                "percentage_of_total",
                "year_over_year_change",
                "percentage_of_total",
            ],
            "table_semantic_type": "period_measure_comparison",
            "row_metric": "total_average_yield",
            "source_scale": "million",
            "column_metrics": columns,
            "column_labels": current_labels,
            "segments": [None] * 4,
            "semantic_periods": comparison_periods,
            "cells": [],
        }
    if not re.search(
        r"Stericycle acquisition and integration costs", statement, re.IGNORECASE
    ):
        return None
    context = " ".join(blocks[max(0, index - 10) : index])
    period_matches = re.findall(
        r"Three Months Ended\s+"
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
        r"(\d{1,2}),\s*(20\d{2})",
        context,
        re.IGNORECASE,
    )
    period_label = ""
    if period_matches:
        month_name, day, year = period_matches[-1]
        period_label = (
            "3M ended "
            + date(
                int(year), MONTHS[month_name.casefold()], int(day)
            ).isoformat()
        )
    if re.search(
        r"Income from\s+Pre-tax\s+Tax\s+Net\s+Diluted Per", context, re.IGNORECASE
    ):
        columns = [
            "income_from_operations",
            "pretax_income",
            "tax_expense",
            "net_income",
        ]
        return _make_table_contract(
            columns,
            period_label,
            segments=[None] * 4,
            table_id=table_id,
            source_locator=source_locator,
            header_rows=blocks[max(0, index - 4) : index],
        )
    if re.search(
        r"Collection\s+Processing\s+Renewable\s+Healthcare\s+Corporate\s+Total.*"
        r"and Disposal.*and Sales.*Energy.*Solutions.*and Other.*WM",
        context,
        re.IGNORECASE,
    ):
        segments = [
            "collection_and_disposal",
            "recycling_processing_and_sales",
            "renewable_energy",
            "healthcare_solutions",
            "corporate_and_other",
            "total_wm",
        ]
        return _make_table_contract(
            segments,
            period_label,
            segments=segments,
            table_id=table_id,
            source_locator=source_locator,
            header_rows=blocks[max(0, index - 4) : index],
        )
    return None


def _make_table_contract(
    columns: list[str],
    period_label: str,
    *,
    segments: list[str | None],
    table_id: str,
    source_locator: str,
    header_rows: list[str],
) -> dict[str, Any]:
    return {
        "table_id": table_id,
        "source_id": None,
        "source_locator": source_locator,
        "title": "Stericycle acquisition and integration costs",
        "subtitle": None,
        "header_rows": [list(header_rows)],
        "row_headers": ["Stericycle acquisition and integration costs"],
        "column_headers": list(columns),
        "row_dimension": "reconciliation_component",
        "column_dimension": "financial_statement_column",
        "period_axis": [period_label] if period_label else [],
        "metric_axis": list(columns),
        "unit_axis": ["currency"] * len(columns),
        "currency_axis": ["USD"] * len(columns),
        "comparison_axis": [None] * len(columns),
        "value_role": ["reconciliation_component"] * len(columns),
        "table_semantic_type": "reconciliation_table",
        "row_metric": "stericycle_acquisition_integration_costs",
        "source_scale": "million",
        "column_metrics": columns,
        "column_labels": [
            f"{period_label} · {column.replace('_', ' ')}".strip(" ·")
            for column in columns
        ],
        "segments": segments,
        "cells": [],
    }


def _is_period_measure_table_row(
    matches: list[re.Match[str]],
    column_labels: list[str],
) -> bool:
    if len(matches) != 4 or len(column_labels) != 4:
        return False
    cell_types = [
        "percent" if match.group("percent") else "currency" if match.group("currency") else "other"
        for match in matches
    ]
    durations = [re.match(r"(\d+)M", label, re.IGNORECASE) for label in column_labels]
    years = [re.search(r"(20\d{2})", label) for label in column_labels]
    return (
        cell_types == ["currency", "percent", "currency", "percent"]
        and all(durations)
        and all(years)
        and durations[0].group(1) == durations[1].group(1)
        and durations[2].group(1) == durations[3].group(1)
        and years[0].group(1) != years[1].group(1)
        and years[2].group(1) != years[3].group(1)
    )


def _short_period_label(label: str) -> str:
    match = re.search(r"(\d+)M ended (20\d{2})", label, re.IGNORECASE)
    return f"{match.group(1)}M {match.group(2)}" if match else label


def _table_numeric_positions(
    statement: str,
    table_contract: dict[str, Any] | None,
) -> dict[int, int]:
    if not table_contract:
        return {}
    label = re.search(
        r"Stericycle acquisition and integration costs", statement, re.IGNORECASE
    )
    tail = statement[label.end() :] if label else statement
    tokens = re.findall(r"(?:\(?\d[\d,.]*\)?|—|–)", tail)
    positions: dict[int, int] = {}
    numeric_index = 0
    for column_index, token in enumerate(tokens):
        if token in {"—", "–"}:
            continue
        positions[numeric_index] = column_index
        numeric_index += 1
    return positions


def _inherits_table_currency(statement: str, context_scale: str | None) -> bool:
    return bool(
        context_scale
        and re.search(
            r"(?:free cash flow|cash provided|acquisitions? of businesses|capital expenditures?|proceeds|"
            r"consideration|revenue|income|expense|costs?|ebitda)",
            statement,
            re.IGNORECASE,
        )
    )


def _dash_cell_evidence(
    *,
    statement: str,
    table_contract: dict[str, Any] | None,
    column_labels: list[str] | None,
    context_scale: str | None,
    filing_date: str | None,
    report_date: str | None,
    report_period_months: int | None,
) -> list[dict[str, Any]]:
    if not table_contract or not column_labels:
        return []
    label = re.search(
        r"Stericycle acquisition and integration costs", statement, re.IGNORECASE
    )
    tail = statement[label.end() :] if label else statement
    tokens = re.findall(r"(?:\(?\d[\d,.]*\)?|—|–)", tail)
    rows: list[dict[str, Any]] = []
    for column_index, token in enumerate(tokens):
        if token not in {"—", "–"} or column_index >= len(column_labels):
            continue
        period = _period_contract_for_table_label(
            column_labels[column_index],
            filing_date=filing_date,
            report_date=report_date,
            report_period_months=report_period_months,
        )
        column_metric = table_contract["column_metrics"][column_index]
        metric_role = "_".join(
            (
                table_contract["row_metric"],
                period["period_role"],
                column_metric,
            )
        )
        rows.append(
            {
                "metric_name": f"operating_kpi_{metric_role}",
                "metric_role": metric_role,
                "value": None,
                "raw_value": None,
                "raw_text": token,
                "normalized_magnitude": None,
                "signed_value": None,
                "direction": "neutral",
                "impact": "neutral",
                "fact_type": "reconciliation_component",
                "rate_basis": None,
                "unit": None,
                "display_unit": None,
                "dimension": "text",
                "source_scale": None,
                "source_unit": None,
                "source_sign": None,
                "currency": None,
                "column_label": column_labels[column_index],
                "row_metric": table_contract["row_metric"],
                "column_metric": column_metric,
                "segment": table_contract["segments"][column_index],
                "source_cell_status": "not_applicable_dash",
                "table_id": table_contract.get("table_id"),
                "cell_id": f"{table_contract['table_id']}:r1:c{column_index + 1}",
                "row_key": table_contract["row_metric"],
                "column_key": column_metric,
                "source_locator": f"{table_contract['source_locator']}:r1:c{column_index + 1}",
                "is_zero": False,
                "is_not_applicable": True,
                "is_missing": False,
                **{key: value for key, value in period.items() if key != "period_role"},
                "mapping_status": "mapped",
            }
        )
    return rows


def _period_contract_for_table_label(
    column_label: str,
    *,
    filing_date: str | None,
    report_date: str | None,
    report_period_months: int | None,
) -> dict[str, Any]:
    ended_weeks = re.search(r"(\d+)W ended (\d{4}-\d{2}-\d{2})", column_label)
    if ended_weeks:
        weeks = int(ended_weeks.group(1))
        period_end = date.fromisoformat(ended_weeks.group(2))
        period_start = period_end - timedelta(days=weeks * 7 - 1)
        return {
            "period_kind": "duration",
            "presentation_basis": "period_total",
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "period_role": f"{weeks}w_{period_end.isoformat()}",
        }
    ended = re.search(r"(3|6|9|12)M ended (\d{4}-\d{2}-\d{2})", column_label)
    if ended:
        months = int(ended.group(1))
        period_end = date.fromisoformat(ended.group(2))
        period_start = _duration_start(period_end, months)
        return {
            "period_kind": "duration",
            "presentation_basis": "period_total",
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "period_role": f"{months}m_{period_end.isoformat()}",
        }
    if report_date and report_period_months in {3, 6, 9, 12}:
        period_end = date.fromisoformat(report_date)
        period_start = _duration_start(period_end, report_period_months)
        return {
            "period_kind": "duration",
            "presentation_basis": "period_total",
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "period_role": f"{report_period_months}m_{period_end.isoformat()}",
        }
    return {
        "period_kind": "unknown",
        "presentation_basis": "unknown",
        "period_start": None,
        "period_end": filing_date,
        "period_role": "period_unmapped",
    }


def _numeric_direction(statement: str, number_range: tuple[int, int]) -> float:
    return _numeric_direction_contract(statement, number_range)[0]


def _numeric_direction_contract(
    statement: str,
    number_range: tuple[int, int],
) -> tuple[float, str, str]:
    immediate_after = statement[number_range[1] : number_range[1] + 35]
    if re.search(r"\b(?:headwind|adverse)\b", immediate_after, re.IGNORECASE):
        return -1.0, "decrease", "adverse"
    directions: list[tuple[int, float]] = []
    for pattern, multiplier in (
        (
            r"\b(?:decline|declined|decrease|decreased|fell|lower|lowered|"
            r"reduce|reduced|reduction|headwind|adverse)\b",
            -1.0,
        ),
        (r"\b(?:growth|grew|increase|increased|rose|higher)\b", 1.0),
    ):
        directions.extend(
            (_semantic_distance(number_range, match.span()), multiplier)
            for match in re.finditer(pattern, statement, flags=re.IGNORECASE)
        )
    if not directions:
        return 1.0, "neutral", "neutral"
    distance, multiplier = min(directions, key=lambda item: item[0])
    if distance > 90:
        return 1.0, "neutral", "neutral"
    return (
        (multiplier, "decrease", "adverse")
        if multiplier < 0
        else (multiplier, "increase", "positive")
    )


def _source_numeric_clause(
    statement: str,
    number_range: tuple[int, int],
) -> str:
    """Keep the source wording governing one number, not unrelated clauses."""

    left = max(statement.rfind(mark, 0, number_range[0]) for mark in (".", ";", ","))
    prior_numbers = [
        match for match in NUMBER_RE.finditer(statement, 0, number_range[0])
    ]
    if prior_numbers:
        conjunctions = list(
            re.finditer(
                r"\b(?:and|but|while|whereas)\b",
                statement[prior_numbers[-1].end() : number_range[0]],
                re.IGNORECASE,
            )
        )
        if conjunctions:
            left = max(left, prior_numbers[-1].end() + conjunctions[0].end())
    right_candidates = [
        position
        for mark in (".", ";", ",")
        if (position := statement.find(mark, number_range[1])) >= 0
    ]
    right = min(right_candidates) if right_candidates else len(statement)
    following_numbers = list(NUMBER_RE.finditer(statement, number_range[1]))
    if following_numbers:
        conjunction = re.search(
            r"\b(?:and|but|while|whereas)\b",
            statement[number_range[1] : following_numbers[0].start()],
            re.IGNORECASE,
        )
        if conjunction:
            right = min(right, number_range[1] + conjunction.start())
    return statement[left + 1 : right].strip()


def _semantic_fact_contract(
    *,
    statement: str,
    metric_role: str,
    unit: str,
    period_contract: dict[str, Any],
    per_share: bool,
    direction: str,
    impact: str,
) -> dict[str, Any]:
    lowered = statement.casefold()
    role = metric_role.casefold()
    if per_share and re.search(r"\b(?:acquisition|purchase price|transaction)\b", lowered):
        return {"fact_type": "stock_value", "rate_basis": None}
    if "annualized_revenue" in role or "annualized revenue" in lowered:
        return {
            "fact_type": "annualized_run_rate",
            "rate_basis": "annualized_at_acquisition_window",
        }
    if per_share and "quarterly" in lowered:
        return {
            "fact_type": "quarterly_rate",
            "rate_basis": "per_share_per_quarter",
        }
    if per_share:
        return {"fact_type": "per_share_rate", "rate_basis": "per_share"}
    if period_contract.get("period_kind") == "guidance":
        if direction == "decrease" or re.search(r"\b(?:increase|raised|higher)\b", lowered):
            return {"fact_type": "guidance_change", "rate_basis": None}
        if "range_low" in role or "range_high" in role:
            return {"fact_type": "guidance_range", "rate_basis": None}
    if "share_of_total" in role or "% of total" in lowered:
        return {"fact_type": "percentage_of_total", "rate_basis": None}
    if unit == "basis_points":
        return {
            "fact_type": (
                "contribution_to_change"
                if "headwind" in lowered or "tailwind" in lowered
                else "basis_point_change"
            ),
            "rate_basis": None,
        }
    if period_contract.get("period_kind") == "comparison" or direction in {"increase", "decrease"}:
        return {"fact_type": "year_over_year_change", "rate_basis": None}
    if period_contract.get("period_kind") == "instant":
        return {"fact_type": "instant_value", "rate_basis": None}
    return {"fact_type": "period_total", "rate_basis": None}


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
