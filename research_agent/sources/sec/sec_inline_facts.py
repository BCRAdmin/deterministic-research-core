from __future__ import annotations

import json
import re
from collections import Counter
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from research_agent.evidence.evidence_item import EvidenceItem
from research_agent.evidence.source_ranker import rank_source
from research_agent.sources.sec.companyfacts_parser import ParsedFact
from research_agent.sources.sec.sec_filing_risks import SecFilingReference
from research_agent.sources.sec.xbrl_concepts import DEI_CONCEPTS, US_GAAP_CONCEPTS


SEC_INLINE_FACT_SUPPLEMENT_CONTRACT = "room16.sec_inline_fact_supplement.v1"
_NONCURRENT_DEBT_CONCEPT = "us-gaap:LongTermDebtNoncurrent"
_OUTSTANDING_SHARES_CONCEPT = "dei:EntityCommonStockSharesOutstanding"
_STOCK_CLASS_AXIS = "us-gaap:StatementClassOfStockAxis"
_MULTI_CLASS_PRICE_EQUIVALENCE_NOTE = (
    "[MULTI_CLASS_PRICE_EQUIVALENCE_UNVERIFIED]"
)
_INLINE_EXACT_CASHFLOW_ROW_NOTE = "[INLINE_EXACT_CASHFLOW_ROW]"
_CAPEX_ROW_LABEL = "capital expenditures and investments"


class _InlineStatementParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.contexts: dict[str, dict[str, Any]] = {}
        self.facts: list[dict[str, Any]] = []
        self.rows: list[dict[str, Any]] = []
        self.text_parts: list[str] = []
        self._context_id: str | None = None
        self._context_instant_parts: list[str] | None = None
        self._context_start_parts: list[str] | None = None
        self._context_end_parts: list[str] | None = None
        self._member_dimension: str | None = None
        self._member_parts: list[str] | None = None
        self._row_parts: list[str] | None = None
        self._row_facts: list[dict[str, Any]] | None = None
        self._fact_attrs: dict[str, str] | None = None
        self._fact_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attributes = {
            str(key).lower(): str(value or "")
            for key, value in attrs
        }
        if tag == "xbrli:context":
            self._context_id = attributes.get("id") or None
            if self._context_id:
                self.contexts[self._context_id] = {
                    "instant": None,
                    "start": None,
                    "end": None,
                    "dimensions": {},
                }
        elif tag == "xbrldi:explicitmember" and self._context_id:
            dimension = attributes.get("dimension")
            if dimension:
                self._member_dimension = dimension
                self._member_parts = []
        elif tag == "xbrli:instant" and self._context_id:
            self._context_instant_parts = []
        elif tag == "xbrli:startdate" and self._context_id:
            self._context_start_parts = []
        elif tag == "xbrli:enddate" and self._context_id:
            self._context_end_parts = []
        elif tag == "tr":
            self._row_parts = []
            self._row_facts = []
        elif tag in {"ix:nonfraction", "ix:nonnumeric"}:
            self._fact_attrs = attributes
            self._fact_attrs["_tag"] = tag
            self._fact_parts = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "xbrli:instant" and self._context_id:
            instant = "".join(self._context_instant_parts or []).strip()
            self.contexts[self._context_id]["instant"] = instant
            self._context_instant_parts = None
        elif tag == "xbrli:startdate" and self._context_id:
            start = "".join(self._context_start_parts or []).strip()
            self.contexts[self._context_id]["start"] = start
            self._context_start_parts = None
        elif tag == "xbrli:enddate" and self._context_id:
            end = "".join(self._context_end_parts or []).strip()
            self.contexts[self._context_id]["end"] = end
            self._context_end_parts = None
        elif tag == "xbrldi:explicitmember" and self._context_id:
            member = " ".join("".join(self._member_parts or []).split())
            if self._member_dimension and member:
                self.contexts[self._context_id]["dimensions"][
                    self._member_dimension
                ] = member
            self._member_dimension = None
            self._member_parts = None
        elif tag == "xbrli:context":
            self._context_id = None
            self._context_instant_parts = None
            self._context_start_parts = None
            self._context_end_parts = None
        elif tag in {"ix:nonfraction", "ix:nonnumeric"} and self._fact_attrs is not None:
            fact = {
                **self._fact_attrs,
                "text": " ".join("".join(self._fact_parts or []).split()),
            }
            self.facts.append(fact)
            if self._row_facts is not None:
                self._row_facts.append(fact)
            self._fact_attrs = None
            self._fact_parts = None
        elif tag == "tr" and self._row_parts is not None:
            self.rows.append(
                {
                    "text": " ".join(" ".join(self._row_parts).split()),
                    "facts": list(self._row_facts or []),
                }
            )
            self._row_parts = None
            self._row_facts = None
            self._fact_attrs = None
            self._fact_parts = None

    def handle_data(self, data: str) -> None:
        self.text_parts.append(data)
        if self._context_instant_parts is not None:
            self._context_instant_parts.append(data)
        if self._context_start_parts is not None:
            self._context_start_parts.append(data)
        if self._context_end_parts is not None:
            self._context_end_parts.append(data)
        if self._member_parts is not None:
            self._member_parts.append(data)
        if self._row_parts is not None:
            self._row_parts.append(data)
        if self._fact_parts is not None:
            self._fact_parts.append(data)


def build_sec_inline_fact_supplement_payload(
    *,
    ticker: str,
    filing: SecFilingReference,
    html: str,
    companyfacts: dict[str, Any],
    retrieved_at: str,
    allowed_metrics: set[str] | None = None,
) -> dict[str, Any] | None:
    """Recover narrowly supported current facts omitted by CompanyFacts."""

    filing_period = _companyfacts_filing_period(companyfacts, filing)
    if filing_period is None or not filing.report_date:
        return None

    parser = _InlineStatementParser()
    parser.feed(html)
    facts: list[dict[str, Any]] = []
    metrics = (
        allowed_metrics
        if allowed_metrics is not None
        else {
            "debt_noncurrent",
            "economic_share_count",
            "capex",
            "short_term_investments",
            "marketable_securities",
            "credit_facility_borrowings",
        }
    )
    if (
        "debt_noncurrent" in metrics
        and not _companyfacts_has_current_noncurrent_debt(companyfacts, filing)
    ):
        debt = _inline_noncurrent_debt_fact(
            ticker=ticker,
            filing=filing,
            filing_period=filing_period,
            parser=parser,
        )
        if debt is not None:
            facts.append(debt)
    for metric_name in ("short_term_investments", "marketable_securities"):
        if metric_name not in metrics or _companyfacts_has_current_instant_metric(
            companyfacts, filing, metric_name=metric_name
        ):
            continue
        instant_fact = _inline_instant_metric_fact(
            ticker=ticker,
            filing=filing,
            filing_period=filing_period,
            parser=parser,
            metric_name=metric_name,
        )
        if instant_fact is not None:
            facts.append(instant_fact)
    if (
        "credit_facility_borrowings" in metrics
    ):
        explicit_zero_debt = _inline_explicit_zero_debt_fact(
            ticker=ticker,
            filing=filing,
            filing_period=filing_period,
            parser=parser,
        )
        if explicit_zero_debt is not None:
            facts.append(explicit_zero_debt)
    if (
        "economic_share_count" in metrics
        and not _companyfacts_has_current_share_count(companyfacts, filing)
    ):
        shares = _inline_economic_share_count_fact(
            ticker=ticker,
            filing=filing,
            filing_period=filing_period,
            parser=parser,
        )
        if shares is not None:
            facts.append(shares)
    if (
        "capex" in metrics
        and not _companyfacts_has_current_duration_metric(
            companyfacts,
            filing,
            metric_name="capex",
        )
    ):
        facts.extend(
            _inline_exact_capex_facts(
                ticker=ticker,
                filing=filing,
                filing_period=filing_period,
                parser=parser,
            )
        )
    if not facts:
        return None
    return {
        "contract_id": SEC_INLINE_FACT_SUPPLEMENT_CONTRACT,
        "ticker": ticker.strip().upper(),
        "retrieved_at": retrieved_at,
        "filing": filing.to_dict(),
        "filings": [filing.to_dict()],
        "facts": facts,
    }


def merge_sec_inline_filing_into_companyfacts(
    *,
    filing: SecFilingReference,
    html: str,
    companyfacts: dict[str, Any],
    required_metrics: set[str],
) -> tuple[dict[str, Any], int]:
    """Backfill one current 10-Q/10-K from its filed inline XBRL.

    The SEC CompanyFacts endpoint can lag behind a newly filed report. This
    adapter reads only canonical US-GAAP/DEI concepts from the exact filing,
    rejects dimensional facts, and requires every caller-declared coverage
    metric before the merged payload can satisfy the current-filing gate.
    """

    parser = _InlineStatementParser()
    parser.feed(html)
    fiscal_year = _inline_document_focus(parser, "dei:DocumentFiscalYearFocus")
    fiscal_period = _inline_document_focus(parser, "dei:DocumentFiscalPeriodFocus").upper()
    try:
        fiscal_year_number = int(fiscal_year)
    except ValueError as exc:
        raise ValueError("inline filing has no unique fiscal-year focus") from exc
    if fiscal_period not in {"Q1", "Q2", "Q3", "FY"}:
        raise ValueError("inline filing has no supported fiscal-period focus")

    concept_metrics: dict[tuple[str, str], set[str]] = {}
    for metric_name, concepts in US_GAAP_CONCEPTS.items():
        for concept in concepts:
            concept_metrics.setdefault(("us-gaap", concept), set()).add(metric_name)
    for metric_name, concepts in DEI_CONCEPTS.items():
        for concept in concepts:
            concept_metrics.setdefault(("dei", concept), set()).add(metric_name)

    rows: list[tuple[str, str, str, dict[str, Any], set[str]]] = []
    seen: set[tuple[Any, ...]] = set()
    covered_metrics: set[str] = set()
    for fact in parser.facts:
        if fact.get("_tag") != "ix:nonfraction":
            continue
        namespace, separator, concept = str(fact.get("name") or "").partition(":")
        if not separator:
            continue
        metrics = concept_metrics.get((namespace.casefold(), concept))
        if not metrics:
            continue
        context = parser.contexts.get(str(fact.get("contextref") or ""), {})
        if context.get("dimensions"):
            continue
        start = str(context.get("start") or "") or None
        end = str(context.get("end") or context.get("instant") or "") or None
        if end != filing.report_date:
            continue
        value = _inline_numeric_value(fact)
        unit = _companyfacts_unit(str(fact.get("unitref") or ""))
        if value is None or unit is None:
            continue
        row = {
            "start": start,
            "end": end,
            "val": value,
            "accn": filing.accession_number,
            "fy": fiscal_year_number,
            "fp": fiscal_period,
            "form": filing.form,
            "filed": filing.filing_date,
        }
        identity = (
            namespace.casefold(),
            concept,
            unit,
            start,
            end,
            value,
            filing.accession_number,
        )
        if identity in seen:
            continue
        seen.add(identity)
        rows.append((namespace.casefold(), concept, unit, row, metrics))
        covered_metrics.update(metrics)

    missing = sorted(required_metrics - covered_metrics)
    if missing:
        raise ValueError(
            "inline filing does not cover required canonical metrics: "
            + ", ".join(missing)
        )

    merged = deepcopy(companyfacts)
    facts_root = merged.setdefault("facts", {})
    for namespace, concept, unit, row, _metrics in rows:
        namespace_root = facts_root.setdefault(namespace, {})
        concept_root = namespace_root.setdefault(
            concept,
            {"label": concept, "description": "Room16 inline-XBRL backfill"},
        )
        unit_rows = concept_root.setdefault("units", {}).setdefault(unit, [])
        if not any(
            existing.get("accn") == row["accn"]
            and existing.get("start") == row["start"]
            and existing.get("end") == row["end"]
            and existing.get("val") == row["val"]
            for existing in unit_rows
            if isinstance(existing, dict)
        ):
            unit_rows.append(row)
    merged.setdefault("room16_inline_filing_backfills", []).append(
        {
            "accession_number": filing.accession_number,
            "filing_date": filing.filing_date,
            "report_date": filing.report_date,
            "form": filing.form,
            "fact_count": len(rows),
            "required_metrics": sorted(required_metrics),
        }
    )
    return merged, len(rows)


def _inline_document_focus(parser: _InlineStatementParser, concept: str) -> str:
    values = {
        " ".join(str(fact.get("text") or "").split())
        for fact in parser.facts
        if str(fact.get("name") or "").casefold() == concept.casefold()
        and str(fact.get("text") or "").strip()
    }
    if len(values) != 1:
        raise ValueError(f"inline filing has ambiguous {concept}")
    return next(iter(values))


def _companyfacts_unit(unit_ref: str) -> str | None:
    normalized = re.sub(r"[^a-z]", "", unit_ref.casefold())
    return {
        "usd": "USD",
        "shares": "shares",
        "usdshares": "USD/shares",
    }.get(normalized)


def merge_sec_inline_fact_supplement_payloads(
    primary: dict[str, Any] | None,
    additional: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Merge supplements without losing the filing identity of each fact."""

    if primary is None:
        return additional
    if additional is None:
        return primary
    if (
        primary.get("contract_id") != SEC_INLINE_FACT_SUPPLEMENT_CONTRACT
        or additional.get("contract_id") != SEC_INLINE_FACT_SUPPLEMENT_CONTRACT
        or str(primary.get("ticker") or "").upper()
        != str(additional.get("ticker") or "").upper()
    ):
        raise ValueError("SEC inline fact supplements cannot be merged")

    merged = dict(primary)
    filings_by_accession: dict[str, dict[str, Any]] = {}
    for payload in (primary, additional):
        filings = payload.get("filings") or [payload.get("filing") or {}]
        for filing in filings:
            accession = str(filing.get("accession_number") or "")
            if accession:
                filings_by_accession[accession] = dict(filing)
    facts_by_id: dict[str, dict[str, Any]] = {}
    for payload in (primary, additional):
        for fact in payload.get("facts") or []:
            evidence_id = str(fact.get("evidence_id") or "")
            if evidence_id:
                facts_by_id[evidence_id] = dict(fact)
    merged["filings"] = list(filings_by_accession.values())
    merged["facts"] = list(facts_by_id.values())
    return merged


def build_sec_inline_debt_supplement_payload(
    *,
    ticker: str,
    filing: SecFilingReference,
    html: str,
    companyfacts: dict[str, Any],
    retrieved_at: str,
) -> dict[str, Any] | None:
    """Backward-compatible entry point for the general inline supplement.

    Kept so callers of the original debt-only supplement continue to work.
    """

    return build_sec_inline_fact_supplement_payload(
        ticker=ticker,
        filing=filing,
        html=html,
        companyfacts=companyfacts,
        retrieved_at=retrieved_at,
    )


def _inline_noncurrent_debt_fact(
    *,
    ticker: str,
    filing: SecFilingReference,
    filing_period: tuple[int, str],
    parser: _InlineStatementParser,
) -> dict[str, Any] | None:
    """Recover one exact current noncurrent-debt statement row."""

    current_candidates: list[float] = []
    current_affiliate_values: list[float] = []
    for row in parser.rows:
        label = _row_label(str(row.get("text") or ""))
        if label not in {"long term debt", "long term debt to affiliates"}:
            continue
        for fact in row.get("facts") or []:
            if str(fact.get("name") or "").casefold() != _NONCURRENT_DEBT_CONCEPT.casefold():
                continue
            context = parser.contexts.get(str(fact.get("contextref") or ""), {})
            if context.get("instant") != filing.report_date:
                continue
            if str(fact.get("unitref") or "").casefold() != "usd":
                continue
            value = _inline_numeric_value(fact)
            if value is None:
                continue
            if label == "long term debt to affiliates":
                current_affiliate_values.append(value)
            else:
                current_candidates.append(value)

    if any(value != 0 for value in current_affiliate_values):
        raise ValueError(
            "The filed statement presents non-zero long-term debt to affiliates "
            "separately; the narrow inline-XBRL supplement cannot represent a "
            "consolidated noncurrent-debt value without an explicit formula."
        )
    if not current_candidates:
        return None

    fiscal_year, fiscal_period = filing_period
    value = current_candidates[0]
    symbol = ticker.strip().upper()
    accession = filing.accession_number.replace("-", "")
    period = f"FY{fiscal_year}_{fiscal_period}"
    evidence_id = (
        f"{symbol}_SEC_INLINE_debt_noncurrent_{period}_instant_"
        f"{filing.report_date}_us-gaap_LongTermDebtNoncurrent_{accession}"
    )
    return {
        "metric_name": "debt_noncurrent",
        "value": value,
        "unit": "USD",
        "period": period,
        "fy": fiscal_year,
        "fp": fiscal_period,
        "form": filing.form,
        "filed": filing.filing_date,
        "start": None,
        "end": filing.report_date,
        "accession": filing.accession_number,
        "source_type": "sec_filing",
        "frame": None,
        "concept": _NONCURRENT_DEBT_CONCEPT,
        "raw_value": value,
        "normalization_note": (
            "Recovered from the exact Long-term debt row in the filed inline "
            "XBRL because SEC CompanyFacts omitted the current standard fact."
        ),
        "evidence_id": evidence_id,
    }


def _inline_instant_metric_fact(
    *,
    ticker: str,
    filing: SecFilingReference,
    filing_period: tuple[int, str],
    parser: _InlineStatementParser,
    metric_name: str,
) -> dict[str, Any] | None:
    concepts = {
        concept.casefold(): concept
        for concept in US_GAAP_CONCEPTS[metric_name]
    }
    candidates: list[tuple[int, float, str]] = []
    for fact in parser.facts:
        namespace, separator, concept = str(fact.get("name") or "").partition(":")
        if not separator or namespace.casefold() != "us-gaap":
            continue
        canonical_concept = concepts.get(concept.casefold())
        if canonical_concept is None:
            continue
        context = parser.contexts.get(str(fact.get("contextref") or ""), {})
        if context.get("instant") != filing.report_date or context.get("dimensions"):
            continue
        if str(fact.get("unitref") or "").casefold() != "usd":
            continue
        value = _inline_numeric_value(fact)
        if value is None:
            continue
        priority = len(US_GAAP_CONCEPTS[metric_name]) - US_GAAP_CONCEPTS[
            metric_name
        ].index(canonical_concept)
        candidates.append((priority, value, canonical_concept))
    if not candidates:
        return None
    best_priority = max(item[0] for item in candidates)
    best = {(value, concept) for priority, value, concept in candidates if priority == best_priority}
    if len(best) != 1:
        raise ValueError(f"conflicting current inline values for {metric_name}")
    value, concept = next(iter(best))
    fiscal_year, fiscal_period = filing_period
    symbol = ticker.strip().upper()
    period = f"FY{fiscal_year}_{fiscal_period}"
    accession = filing.accession_number.replace("-", "")
    return {
        "metric_name": metric_name,
        "value": value,
        "unit": "USD",
        "period": period,
        "fy": fiscal_year,
        "fp": fiscal_period,
        "form": filing.form,
        "filed": filing.filing_date,
        "start": None,
        "end": filing.report_date,
        "accession": filing.accession_number,
        "source_type": "sec_filing",
        "frame": None,
        "concept": f"us-gaap:{concept}",
        "raw_value": value,
        "normalization_note": (
            "Recovered an undimensioned current balance-sheet fact from the exact "
            "filed inline XBRL because SEC CompanyFacts omitted the filing value."
        ),
        "evidence_id": (
            f"{symbol}_SEC_INLINE_{metric_name}_{period}_instant_"
            f"{filing.report_date}_us-gaap_{concept}_{accession}"
        ),
    }


def _inline_explicit_zero_debt_fact(
    *,
    ticker: str,
    filing: SecFilingReference,
    filing_period: tuple[int, str],
    parser: _InlineStatementParser,
) -> dict[str, Any] | None:
    document_text = " ".join(" ".join(parser.text_parts).split()).casefold()
    if re.search(r"\bno\b.{0,80}\bborrowings\b", document_text) is None:
        return None
    candidates: list[dict[str, Any]] = []
    for fact in parser.facts:
        if str(fact.get("name") or "").casefold() != "us-gaap:debtinstrumentcarryingamount":
            continue
        context = parser.contexts.get(str(fact.get("contextref") or ""), {})
        if context.get("instant") != filing.report_date:
            continue
        dimensions = context.get("dimensions") or {}
        if not any("creditfacility" in str(key).casefold() for key in dimensions):
            continue
        value = _inline_numeric_value(fact)
        if value == 0:
            candidates.append(fact)
    if len(candidates) != 1:
        return None
    fiscal_year, fiscal_period = filing_period
    symbol = ticker.strip().upper()
    period = f"FY{fiscal_year}_{fiscal_period}"
    accession = filing.accession_number.replace("-", "")
    return {
        "metric_name": "credit_facility_borrowings",
        "value": 0.0,
        "unit": "USD",
        "period": period,
        "fy": fiscal_year,
        "fp": fiscal_period,
        "form": filing.form,
        "filed": filing.filing_date,
        "start": None,
        "end": filing.report_date,
        "accession": filing.accession_number,
        "source_type": "sec_filing",
        "frame": None,
        "concept": "us-gaap:DebtInstrumentCarryingAmount",
        "raw_value": 0.0,
        "normalization_note": (
            "Reported zero: the filing explicitly states no outstanding borrowings "
            "and tags the debt carrying amount with ixt:fixed-zero."
        ),
        "evidence_id": (
            f"{symbol}_SEC_INLINE_credit_facility_borrowings_{period}_instant_"
            f"{filing.report_date}_us-gaap_DebtInstrumentCarryingAmount_{accession}"
        ),
    }


def _inline_economic_share_count_fact(
    *,
    ticker: str,
    filing: SecFilingReference,
    filing_period: tuple[int, str],
    parser: _InlineStatementParser,
) -> dict[str, Any] | None:
    candidates: dict[str, list[tuple[float, dict[str, str]]]] = {}
    for fact in parser.facts:
        if str(fact.get("name") or "").casefold() != _OUTSTANDING_SHARES_CONCEPT.casefold():
            continue
        if str(fact.get("unitref") or "").casefold() != "shares":
            continue
        context = parser.contexts.get(str(fact.get("contextref") or ""), {})
        instant = str(context.get("instant") or "")
        if not (
            filing.report_date <= instant <= filing.filing_date
        ):
            continue
        value = _inline_numeric_value(fact)
        if value is None or value <= 0:
            continue
        candidates.setdefault(instant, []).append(
            (value, dict(context.get("dimensions") or {}))
        )
    if not candidates:
        return None

    instant = max(candidates)
    undimensioned = {
        value for value, dimensions in candidates[instant] if not dimensions
    }
    class_values: dict[str, float] = {}
    for value, dimensions in candidates[instant]:
        if set(dimensions) != {_STOCK_CLASS_AXIS}:
            continue
        member = dimensions[_STOCK_CLASS_AXIS]
        existing = class_values.get(member)
        if existing is not None and existing != value:
            raise ValueError(
                "The filed cover page reports conflicting outstanding-share "
                f"values for stock class {member}."
            )
        class_values[member] = value

    class_total = sum(class_values.values()) if class_values else None
    if len(undimensioned) > 1:
        raise ValueError(
            "The filed cover page reports conflicting undimensioned outstanding-"
            "share values."
        )
    aggregate = next(iter(undimensioned), None)
    if aggregate is not None and class_total is not None:
        scale = max(abs(aggregate), abs(class_total))
        if scale and abs(aggregate - class_total) / scale > 0.001:
            raise ValueError(
                "The filed cover page aggregate outstanding shares do not match "
                "the sum of its stock-class facts."
            )
    value = aggregate if aggregate is not None else class_total
    if value is None:
        return None

    fiscal_year, fiscal_period = filing_period
    symbol = ticker.strip().upper()
    accession = filing.accession_number.replace("-", "")
    period = f"FY{fiscal_year}_{fiscal_period}"
    evidence_id = (
        f"{symbol}_SEC_INLINE_economic_share_count_{period}_instant_"
        f"{instant}_dei_EntityCommonStockSharesOutstanding_{accession}"
    )
    if len(class_values) > 1:
        class_note = (
            f"{_MULTI_CLASS_PRICE_EQUIVALENCE_NOTE} summed across "
            f"{len(class_values)} separately tagged stock classes. The cover-page "
            "facts do not establish that one traded class price can be applied "
            "to every class"
        )
    elif class_values and aggregate is None:
        class_note = "taken from one separately tagged stock class"
    else:
        class_note = "taken from the undimensioned issuer total"
    return {
        "metric_name": "economic_share_count",
        "value": value,
        "unit": "shares",
        "period": period,
        "fy": fiscal_year,
        "fp": fiscal_period,
        "form": filing.form,
        "filed": filing.filing_date,
        "start": None,
        "end": instant,
        "accession": filing.accession_number,
        "source_type": "sec_filing",
        "frame": None,
        "concept": _OUTSTANDING_SHARES_CONCEPT,
        "raw_value": value,
        "normalization_note": (
            "Recovered current economic shares from the filed cover-page inline "
            f"XBRL and {class_note} because SEC CompanyFacts omitted a usable "
            "current point-in-time share count."
        ),
        "evidence_id": evidence_id,
    }


def _inline_exact_capex_facts(
    *,
    ticker: str,
    filing: SecFilingReference,
    filing_period: tuple[int, str],
    parser: _InlineStatementParser,
) -> list[dict[str, Any]]:
    """Recover exact consolidated capex rows when CompanyFacts omits them."""

    candidates: dict[tuple[str, str], list[tuple[float, str]]] = {}
    for row in parser.rows:
        if _row_label(str(row.get("text") or "")) != _CAPEX_ROW_LABEL:
            continue
        for fact in row.get("facts") or []:
            context = parser.contexts.get(str(fact.get("contextref") or ""), {})
            start = str(context.get("start") or "")
            end = str(context.get("end") or "")
            if (
                not start
                or not end
                or end > filing.report_date
                or context.get("dimensions")
                or str(fact.get("unitref") or "").casefold() != "usd"
            ):
                continue
            concept = str(fact.get("name") or "")
            if ":" not in concept:
                continue
            value = _inline_numeric_value(fact)
            if value is None:
                continue
            candidates.setdefault((start, end), []).append((abs(value), concept))

    fiscal_year, fiscal_period = filing_period
    facts: list[dict[str, Any]] = []
    for (start, end), observations in sorted(candidates.items()):
        values = {value for value, _concept in observations}
        if len(values) != 1:
            raise ValueError(
                "The filed statement reports conflicting undimensioned values "
                f"for the exact {_CAPEX_ROW_LABEL!r} row in {start}..{end}."
            )
        value = next(iter(values))
        concept = observations[0][1]
        year_delta = int(end[:4]) - int(filing.report_date[:4])
        fact_fiscal_year = fiscal_year + year_delta
        period = f"FY{fact_fiscal_year}_{fiscal_period}"
        symbol = ticker.strip().upper()
        accession = filing.accession_number.replace("-", "")
        evidence_id = (
            f"{symbol}_SEC_INLINE_capex_{period}_{start}_{end}_"
            f"{concept.replace(':', '_')}_{accession}"
        )
        facts.append(
            {
                "metric_name": "capex",
                "value": value,
                "unit": "USD",
                "period": period,
                "fy": fact_fiscal_year,
                "fp": fiscal_period,
                "form": filing.form,
                "filed": filing.filing_date,
                "start": start,
                "end": end,
                "accession": filing.accession_number,
                "source_type": "sec_filing",
                "frame": None,
                "concept": concept,
                "raw_value": value,
                "normalization_note": (
                    f"{_INLINE_EXACT_CASHFLOW_ROW_NOTE} Recovered from the exact "
                    f"consolidated {_CAPEX_ROW_LABEL!r} row in the filed inline "
                    "XBRL because SEC CompanyFacts omitted the current fact."
                ),
                "evidence_id": evidence_id,
            }
        )
    return facts


def save_sec_inline_fact_supplement(
    path: str | Path,
    payload: dict[str, Any],
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return target


def load_sec_inline_fact_supplement(
    path: str | Path,
    *,
    ticker: str,
) -> tuple[list[ParsedFact], list[EvidenceItem]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    symbol = ticker.strip().upper()
    if payload.get("contract_id") != SEC_INLINE_FACT_SUPPLEMENT_CONTRACT:
        raise ValueError("SEC inline fact supplement contract mismatch")
    if str(payload.get("ticker") or "").upper() != symbol:
        raise ValueError("SEC inline fact supplement ticker mismatch")
    filings = payload.get("filings") or [payload.get("filing") or {}]
    filings_by_accession = {
        str(filing.get("accession_number") or ""): filing
        for filing in filings
        if filing.get("accession_number")
    }

    parsed_facts: list[ParsedFact] = []
    evidence_items: list[EvidenceItem] = []
    for row in payload.get("facts") or []:
        metric_name = str(row.get("metric_name") or "")
        expected_concept = {
            "debt_noncurrent": _NONCURRENT_DEBT_CONCEPT,
            "economic_share_count": _OUTSTANDING_SHARES_CONCEPT,
            "credit_facility_borrowings": "us-gaap:DebtInstrumentCarryingAmount",
        }.get(metric_name)
        if metric_name in {"short_term_investments", "marketable_securities"}:
            candidate = str(row.get("concept") or "")
            allowed = {
                f"us-gaap:{concept}"
                for concept in US_GAAP_CONCEPTS[metric_name]
            }
            if candidate not in allowed:
                raise ValueError("SEC inline instant fact authority mismatch")
            expected_concept = candidate
        if metric_name == "capex":
            expected_concept = str(row.get("concept") or "")
            if (
                ":" not in expected_concept
                or _INLINE_EXACT_CASHFLOW_ROW_NOTE
                not in str(row.get("normalization_note") or "")
            ):
                raise ValueError("SEC inline capex authority mismatch")
        elif expected_concept is None:
            raise ValueError("SEC inline fact supplement contains unsupported metric")
        fact = ParsedFact(**row)
        if fact.source_type != "sec_filing" or fact.concept != expected_concept:
            raise ValueError("SEC inline fact supplement authority mismatch")
        parsed_facts.append(fact)
        filing = filings_by_accession.get(str(fact.accession or "")) or (
            payload.get("filing") or {}
        )
        source_id = str(filing.get("source_id") or "")
        if not source_id:
            cik = str(filing.get("cik") or "")
            accession = str(fact.accession or "").replace("-", "")
            if cik and accession:
                source_id = f"SEC_CIK{str(int(cik)).zfill(10)}_{accession}"
        statement = (
            f"{symbol} reported debt_noncurrent of {fact.value} USD for "
            f"{fact.period} in the filed Long-term debt row."
            if metric_name in {"debt_noncurrent", "credit_facility_borrowings"}
            else (
                f"{symbol} reported capex of {fact.value} USD for {fact.period} "
                f"in the exact filed {_CAPEX_ROW_LABEL} cash-flow row."
                if metric_name == "capex"
                else f"{symbol} reported {fact.value} economic shares outstanding "
                f"as of {fact.end} in the filed cover-page inline XBRL."
            )
        )
        evidence_items.append(
            EvidenceItem(
                evidence_id=str(fact.evidence_id),
                ticker=symbol,
                claim_type="financial_metric",
                source_id=source_id or f"SEC_{fact.accession}",
                source_type="sec_filing",
                authority_rank=rank_source("sec_filing"),
                statement=statement,
                value=fact.value,
                unit=fact.unit,
                period=fact.period,
                date=fact.end,
                period_start=fact.start,
                period_end=fact.end,
                url=filing.get("url"),
                retrieved_at=payload.get("retrieved_at"),
                supports_metrics=[metric_name],
                confidence="high",
                raw_value=fact.raw_value,
                normalized_value=fact.value,
                source_lineage=[fact.accession] if fact.accession else [],
                audited=fact.form == "10-K",
                amendment_status=(
                    "amended" if fact.form in {"10-K/A", "10-Q/A"} else "original"
                ),
            )
        )
    return parsed_facts, evidence_items


def _companyfacts_has_current_instant_metric(
    companyfacts: dict[str, Any],
    filing: SecFilingReference,
    *,
    metric_name: str,
) -> bool:
    us_gaap = companyfacts.get("facts", {}).get("us-gaap", {})
    return any(
        row.get("accn") == filing.accession_number
        and row.get("end") == filing.report_date
        and row.get("form") == filing.form
        and not row.get("start")
        for concept in US_GAAP_CONCEPTS.get(metric_name, [])
        for rows in ((us_gaap.get(concept) or {}).get("units") or {}).values()
        for row in rows
        if isinstance(row, dict)
    )


def _companyfacts_has_current_noncurrent_debt(
    companyfacts: dict[str, Any],
    filing: SecFilingReference,
) -> bool:
    us_gaap = companyfacts.get("facts", {}).get("us-gaap", {})
    return any(
        row.get("accn") == filing.accession_number
        and row.get("end") == filing.report_date
        and row.get("form") == filing.form
        for concept in US_GAAP_CONCEPTS["debt_noncurrent"]
        for rows in ((us_gaap.get(concept) or {}).get("units") or {}).values()
        for row in rows
        if isinstance(row, dict)
    )


def _companyfacts_has_current_share_count(
    companyfacts: dict[str, Any],
    filing: SecFilingReference,
) -> bool:
    rows = (
        companyfacts.get("facts", {})
        .get("dei", {})
        .get("EntityCommonStockSharesOutstanding", {})
        .get("units", {})
        .get("shares", [])
    )
    values = {
        float(row["val"])
        for row in rows
        if isinstance(row, dict)
        and row.get("accn") == filing.accession_number
        and row.get("form") == filing.form
        and filing.report_date <= str(row.get("end") or "") <= filing.filing_date
        and isinstance(row.get("val"), (int, float))
        and float(row["val"]) > 0
    }
    return len(values) == 1


def _companyfacts_has_current_duration_metric(
    companyfacts: dict[str, Any],
    filing: SecFilingReference,
    *,
    metric_name: str,
) -> bool:
    us_gaap = companyfacts.get("facts", {}).get("us-gaap", {})
    return any(
        row.get("accn") == filing.accession_number
        and row.get("end") == filing.report_date
        and row.get("form") == filing.form
        and row.get("start")
        for concept in US_GAAP_CONCEPTS[metric_name]
        for rows in ((us_gaap.get(concept) or {}).get("units") or {}).values()
        for row in rows
        if isinstance(row, dict)
    )


def _companyfacts_filing_period(
    companyfacts: dict[str, Any],
    filing: SecFilingReference,
) -> tuple[int, str] | None:
    identities: Counter[tuple[int, str]] = Counter()
    for namespace in (companyfacts.get("facts") or {}).values():
        if not isinstance(namespace, dict):
            continue
        for record in namespace.values():
            if not isinstance(record, dict):
                continue
            for rows in (record.get("units") or {}).values():
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    if (
                        row.get("accn") != filing.accession_number
                        or row.get("end") != filing.report_date
                        or row.get("form") != filing.form
                    ):
                        continue
                    fy = row.get("fy")
                    fp = str(row.get("fp") or "")
                    if isinstance(fy, int) and fp:
                        identities[(fy, fp)] += 1
    return identities.most_common(1)[0][0] if identities else None


def _row_label(text: str) -> str:
    return " ".join(re.findall(r"[a-z]+", text.casefold()))


def _inline_numeric_value(fact: dict[str, Any]) -> float | None:
    raw = str(fact.get("text") or "").strip()
    format_name = str(fact.get("format") or "").casefold()
    if "fixed-zero" in format_name or (not re.search(r"\d", raw) and raw in {"—", "–", "-"}):
        value = Decimal(0)
    else:
        match = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?", raw)
        if match is None:
            return None
        try:
            value = Decimal(match.group(0).replace(",", ""))
        except InvalidOperation:
            return None
    try:
        scale = int(str(fact.get("scale") or "0"))
    except ValueError:
        return None
    value *= Decimal(10) ** scale
    if str(fact.get("sign") or "") == "-":
        value = -abs(value)
    return float(value)
