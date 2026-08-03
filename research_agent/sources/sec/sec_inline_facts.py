from __future__ import annotations

import json
import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from research_agent.evidence.evidence_item import EvidenceItem
from research_agent.evidence.source_ranker import rank_source
from research_agent.sources.sec.companyfacts_parser import ParsedFact
from research_agent.sources.sec.sec_filing_risks import SecFilingReference
from research_agent.sources.sec.xbrl_concepts import US_GAAP_CONCEPTS


SEC_INLINE_FACT_SUPPLEMENT_CONTRACT = "room16.sec_inline_fact_supplement.v1"
_NONCURRENT_DEBT_CONCEPT = "us-gaap:LongTermDebtNoncurrent"
_OUTSTANDING_SHARES_CONCEPT = "dei:EntityCommonStockSharesOutstanding"
_STOCK_CLASS_AXIS = "us-gaap:StatementClassOfStockAxis"
_MULTI_CLASS_PRICE_EQUIVALENCE_NOTE = (
    "[MULTI_CLASS_PRICE_EQUIVALENCE_UNVERIFIED]"
)


class _InlineStatementParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.contexts: dict[str, dict[str, Any]] = {}
        self.facts: list[dict[str, Any]] = []
        self.rows: list[dict[str, Any]] = []
        self._context_id: str | None = None
        self._context_instant_parts: list[str] | None = None
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
                    "dimensions": {},
                }
        elif tag == "xbrldi:explicitmember" and self._context_id:
            dimension = attributes.get("dimension")
            if dimension:
                self._member_dimension = dimension
                self._member_parts = []
        elif tag == "xbrli:instant" and self._context_id:
            self._context_instant_parts = []
        elif tag == "tr":
            self._row_parts = []
            self._row_facts = []
        elif tag == "ix:nonfraction":
            self._fact_attrs = attributes
            self._fact_parts = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "xbrli:instant" and self._context_id:
            instant = "".join(self._context_instant_parts or []).strip()
            self.contexts[self._context_id]["instant"] = instant
            self._context_instant_parts = None
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
        elif tag == "ix:nonfraction" and self._fact_attrs is not None:
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
        if self._context_instant_parts is not None:
            self._context_instant_parts.append(data)
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
) -> dict[str, Any] | None:
    """Recover narrowly supported current facts omitted by CompanyFacts."""

    filing_period = _companyfacts_filing_period(companyfacts, filing)
    if filing_period is None or not filing.report_date:
        return None

    parser = _InlineStatementParser()
    parser.feed(html)
    facts: list[dict[str, Any]] = []
    if not _companyfacts_has_current_noncurrent_debt(companyfacts, filing):
        debt = _inline_noncurrent_debt_fact(
            ticker=ticker,
            filing=filing,
            filing_period=filing_period,
            parser=parser,
        )
        if debt is not None:
            facts.append(debt)
    if not _companyfacts_has_current_share_count(companyfacts, filing):
        shares = _inline_economic_share_count_fact(
            ticker=ticker,
            filing=filing,
            filing_period=filing_period,
            parser=parser,
        )
        if shares is not None:
            facts.append(shares)
    if not facts:
        return None
    return {
        "contract_id": SEC_INLINE_FACT_SUPPLEMENT_CONTRACT,
        "ticker": ticker.strip().upper(),
        "retrieved_at": retrieved_at,
        "filing": filing.to_dict(),
        "facts": facts,
    }


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
    filing = payload.get("filing") or {}
    source_id = str(filing.get("source_id") or "")
    if not source_id:
        cik = str(filing.get("cik") or "")
        accession = str(filing.get("accession_number") or "").replace("-", "")
        if cik and accession:
            source_id = f"SEC_CIK{str(int(cik)).zfill(10)}_{accession}"

    parsed_facts: list[ParsedFact] = []
    evidence_items: list[EvidenceItem] = []
    for row in payload.get("facts") or []:
        metric_name = str(row.get("metric_name") or "")
        expected_concept = {
            "debt_noncurrent": _NONCURRENT_DEBT_CONCEPT,
            "economic_share_count": _OUTSTANDING_SHARES_CONCEPT,
        }.get(metric_name)
        if expected_concept is None:
            raise ValueError("SEC inline fact supplement contains unsupported metric")
        fact = ParsedFact(**row)
        if fact.source_type != "sec_filing" or fact.concept != expected_concept:
            raise ValueError("SEC inline fact supplement authority mismatch")
        parsed_facts.append(fact)
        statement = (
            f"{symbol} reported debt_noncurrent of {fact.value} USD for "
            f"{fact.period} in the filed Long-term debt row."
            if metric_name == "debt_noncurrent"
            else f"{symbol} reported {fact.value} economic shares outstanding "
            f"as of {fact.end} in the filed cover-page inline XBRL."
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
