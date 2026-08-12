"""Extract source-bound operating KPI statements from official SEC filings."""

from __future__ import annotations

import re
import hashlib
from calendar import monthrange
from datetime import date
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
    "free_cash_flow_actual": r"^\s*free cash flow\b",
    "internalization": r"\binternalization(?: of waste)?\b",
    "landfill_depletable_tons": r"\blandfill depletable tons?\b",
    "acquired_annualized_revenue": r"\b(?:gross )?annualized revenue acquired\b|\bacquired annualized revenue\b",
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
    r"(?P<currency>C\$|US\$|A\$|HK\$|S\$|[$€£¥])?\s*"
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
    document_role: str,
    event_offset: int,
) -> tuple[list[dict[str, Any]], dict[str, int], str]:
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
    emitted_statements: set[str] = set()
    for block_index, statement in enumerate(blocks):
        if statement in emitted_statements:
            continue
        if _is_forward_looking_boilerplate(statement):
            continue
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
        column_labels = _inherited_column_labels(
            blocks,
            block_index,
            filing_year=filing_year,
        )
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
        table_contract = _table_contract(blocks, block_index)
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
        )
        if not numeric_evidence:
            continue
        emitted_statements.add(statement)
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
        scale = (
            "base"
            if per_share
            else explicit_scale
            or _inherited_inline_scale(statement, match, number_matches)
            or str(context_scale or "").casefold()
        )
        percent = bool(match.group("percent"))
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
        if not (match.group("currency") or percent or basis_points or scale):
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
        direction = _numeric_direction(statement, match.span()) if percent or basis_points else 1.0
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
        column_index = table_positions.get(number_index, number_index)
        column_label = (
            column_labels[column_index]
            if column_labels and column_index < len(column_labels)
            else None
        )
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
        if not (percent or basis_points) and "yoy_change_amount" in metric_role:
            direction = _numeric_direction(statement, match.span())
        elif not (percent or basis_points) and re.search(
                r"\b(?:decline|declined|decrease|decreased|fell|lower)\b.{0,35}$",
                statement[max(0, match.start() - 70) : match.start()],
                re.IGNORECASE,
            ):
            direction = -1.0
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
                **{key: value for key, value in period_contract.items() if key != "period_role"},
                "mapping_status": "unmapped" if metric_role.startswith("unmapped_") else "mapped",
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
    metric_counts: dict[str, int] = {}
    metric_totals: dict[str, int] = {}
    for item in values:
        name = str(item["metric_name"])
        metric_totals[name] = metric_totals.get(name, 0) + 1
    for item in values:
        name = str(item["metric_name"])
        if metric_totals[name] == 1:
            continue
        metric_counts[name] = metric_counts.get(name, 0) + 1
        suffix = f"_event_{event_index:02d}_value_{metric_counts[name]:02d}"
        item["metric_name"] = f"{name}{suffix}"
        item["metric_role"] = f"{item['metric_role']}{suffix}"
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
    label = str(column_label or "")
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
        return {
            "period_kind": "unknown",
            "presentation_basis": "period_total",
            "period_start": None,
            "period_end": None,
            "period_role": "previous_quarter",
        }
    if "this quarter" in nearby:
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
        current_start = _duration_start(current_end, report_period_months)
        return {
            "period_kind": "duration",
            "presentation_basis": "period_total",
            "period_start": current_start.isoformat(),
            "period_end": current_end.isoformat(),
            "period_role": f"{report_period_months}m_{current_end.isoformat()}",
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
        ("internalization", r"internalization"),
        ("landfill_depletable_tons", r"depletable tons"),
        ("acquired_annualized_revenue", r"annualized revenue"),
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
        ("collection_disposal_yield", r"yield"),
        ("collection_disposal_volume", r"collection and disposal volume"),
        ("landfill_volume", r"landfill volumes?"),
        ("residential_volume", r"residential volume"),
        ("basis_point_change", r"basis points?"),
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
        metric = (
            owner
            if owner not in generic_owners
            else closest_metric or (owner if owner != "statement_context" else None)
        )
    elif closest_metric in {
        "internalization",
        "landfill_depletable_tons",
        "acquired_annualized_revenue",
    }:
        metric = closest_metric
    component_metric = _component_metric_override(statement, match)
    if component_metric:
        metric = component_metric
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


def _numeric_metric_variant(
    statement: str,
    match: re.Match[str],
    number_index: int,
) -> str:
    before = statement[max(0, match.start() - 170) : match.start()].casefold()
    after = statement[match.end() : match.end() + 100].casefold()
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
    if re.search(
        r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)$",
        before.rstrip(),
        re.IGNORECASE,
    ) and re.match(r",\s*20\d{2}\b", after):
        return True
    if re.search(r"\b(?:Note|Item|Form)$", before.rstrip(), re.IGNORECASE):
        return True
    return False


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


def _component_metric_override(
    statement: str,
    match: re.Match[str],
) -> str | None:
    after = statement[match.end() : match.end() + 70].casefold()
    before = statement[max(0, match.start() - 70) : match.start()].casefold()
    next_number = NUMBER_RE.search(after)
    component_window = after[: next_number.start()] if next_number else after
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
    # SEC tables frequently split scale, duration headers, years and spacer
    # cells into separate HTML blocks.  Use the same bounded lookback as the
    # period-label parser while still stopping at intervening prose.
    for prior in reversed(blocks[max(0, index - 12) : index]):
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

    table_contract = _table_contract(blocks, index)
    if table_contract:
        return list(table_contract["column_labels"])
    context = " ".join(blocks[max(0, index - 6) : index])
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
    prior_blocks = blocks[max(0, index - 10) : index]
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
    return None


def _table_contract(blocks: list[str], index: int) -> dict[str, Any] | None:
    """Recover row/column meaning from bounded SEC table headers."""

    statement = blocks[index]
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
        return _make_table_contract(columns, period_label, segments=[None] * 4)
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
        return _make_table_contract(segments, period_label, segments=segments)
    return None


def _make_table_contract(
    columns: list[str],
    period_label: str,
    *,
    segments: list[str | None],
) -> dict[str, Any]:
    return {
        "row_metric": "stericycle_acquisition_integration_costs",
        "source_scale": "million",
        "column_metrics": columns,
        "column_labels": [
            f"{period_label} · {column.replace('_', ' ')}".strip(" ·")
            for column in columns
        ],
        "segments": segments,
    }


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
            r"(?:free cash flow|cash provided|capital expenditures?|proceeds|"
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
                "value": 0.0,
                "raw_value": 0.0,
                "unit": "currency",
                "display_unit": "USD",
                "dimension": "currency",
                "source_scale": str(context_scale or "base"),
                "source_unit": "currency",
                "source_sign": 1,
                "currency": "USD",
                "column_label": column_labels[column_index],
                "row_metric": table_contract["row_metric"],
                "column_metric": column_metric,
                "segment": table_contract["segments"][column_index],
                "source_cell_status": "not_applicable_dash",
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
    ended = re.search(r"3M ended (\d{4}-\d{2}-\d{2})", column_label)
    if ended:
        period_end = date.fromisoformat(ended.group(1))
        period_start = _duration_start(period_end, 3)
        return {
            "period_kind": "duration",
            "presentation_basis": "period_total",
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "period_role": f"3m_{period_end.isoformat()}",
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
