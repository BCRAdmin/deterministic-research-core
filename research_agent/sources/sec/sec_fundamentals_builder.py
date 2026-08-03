from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Iterable, Optional

from research_agent.evidence.evidence_item import EvidenceItem
from research_agent.evidence.source_ranker import rank_source
from research_agent.sources.sec.cik_mapper import CikMapper
from research_agent.sources.sec.companyfacts_parser import CompanyFactsParser
from research_agent.sources.sec.sec_client import SecClient


SEC_FUNDAMENTAL_METRICS = [
    "revenue",
    "gross_profit",
    "operating_income",
    "net_income",
    "operating_cash_flow",
    "capex",
    "cash_and_equivalents",
    "short_term_investments",
    "current_assets",
    "current_liabilities",
    "total_debt",
    "short_term_debt",
    "debt_current",
    "debt_noncurrent",
    "lease_liability_current",
    "lease_liability_noncurrent",
    "equity",
    "sbc",
    "buybacks",
    "dividends_paid",
    "treasury_stock_value",
    "treasury_share_count",
    "depreciation_and_amortization",
    "interest_expense",
    "shares_diluted",
    "listed_share_count",
    "eps_diluted",
]
CURRENT_EVIDENCE_MAX_AGE_DAYS = 550


def build_sec_fundamentals(
    ticker: str,
    cik_mapper: CikMapper,
    sec_client: SecClient,
) -> tuple[dict[str, Any], list[EvidenceItem]]:
    cik = cik_mapper.get_cik(ticker)
    raw = sec_client.get_companyfacts(cik)
    parser = CompanyFactsParser(ticker=ticker, cik=cik, companyfacts_json=raw)
    return build_sec_fundamentals_from_companyfacts(ticker, cik, raw)


def build_sec_fundamentals_from_companyfacts(
    ticker: str,
    cik: str,
    companyfacts_json: dict[str, Any],
    *,
    as_of_date: str | None = None,
) -> tuple[dict[str, Any], list[EvidenceItem]]:
    parser = CompanyFactsParser(ticker=ticker, cik=cik, companyfacts_json=companyfacts_json)
    metrics: dict[str, Any] = {
        "quarterly": {},
        "balance_sheet": {},
        "share_data": {},
        "source": "sec_companyfacts",
    }
    evidence_items: list[EvidenceItem] = []
    seen_evidence_ids: set[str] = set()
    reference_date = (
        date.fromisoformat(as_of_date)
        if as_of_date is not None
        else _latest_financial_end(companyfacts_json)
    )
    current_cutoff = (
        reference_date - timedelta(days=CURRENT_EVIDENCE_MAX_AGE_DAYS)
        if reference_date is not None
        else None
    )

    for metric in SEC_FUNDAMENTAL_METRICS:
        current_facts = [
            fact
            for fact in parser.get_facts_for_metric(metric)
            if _fact_is_current(
                fact,
                current_cutoff,
                reference_date,
                enforce_filed_cutoff=as_of_date is not None,
            )
        ]
        annual_candidates = [
            fact
            for fact in current_facts
            if fact.form == "10-K" and fact.fp in {"FY", "CY"}
        ]
        if not annual_candidates:
            annual_candidates = [
                fact for fact in current_facts if fact.form == "10-K"
            ]
        annual = (
            sorted(
                annual_candidates,
                key=lambda fact: (fact.filed or "", fact.end or ""),
            )[-1]
            if annual_candidates
            else None
        )
        if annual:
            metrics[f"{metric}_latest_annual"] = annual.value
            _append_evidence_once(
                evidence_items,
                seen_evidence_ids,
                parser.to_evidence_item(annual),
            )

        quarterly = sorted(
            [
                fact
                for fact in current_facts
                if fact.form in {"10-Q", "10-K"}
                and fact.fp not in {"FY", "CY"}
            ],
            key=lambda fact: (fact.end or "", fact.filed or ""),
        )[-4:]
        if quarterly:
            metrics[f"{metric}_latest_4_quarters"] = [fact.value for fact in quarterly]
            for fact in quarterly:
                _append_evidence_once(
                    evidence_items,
                    seen_evidence_ids,
                    parser.to_evidence_item(fact),
                )
            _assign_normalized_metric(
                metrics,
                metric,
                [fact.value for fact in quarterly],
                annual.value if annual else None,
            )

    return metrics, evidence_items


def _latest_financial_end(companyfacts_json: dict[str, Any]) -> date | None:
    ends: list[date] = []
    for namespace in (companyfacts_json.get("facts") or {}).values():
        if not isinstance(namespace, dict):
            continue
        for record in namespace.values():
            if not isinstance(record, dict):
                continue
            for rows in (record.get("units") or {}).values():
                for row in rows:
                    if not isinstance(row, dict) or row.get("form") not in {
                        "10-K",
                        "10-K/A",
                        "10-Q",
                        "10-Q/A",
                    }:
                        continue
                    try:
                        ends.append(date.fromisoformat(str(row.get("end") or "")))
                    except ValueError:
                        continue
    return max(ends) if ends else None


def _fact_is_current(
    fact: Any,
    cutoff: date | None,
    reference_date: date | None,
    *,
    enforce_filed_cutoff: bool,
) -> bool:
    if cutoff is None:
        return True
    try:
        fact_end = date.fromisoformat(str(fact.end or ""))
        fact_filed = date.fromisoformat(str(fact.filed or ""))
    except ValueError:
        return False
    return (
        cutoff <= fact_end <= reference_date
        and (not enforce_filed_cutoff or fact_filed <= reference_date)
    )


def _append_evidence_once(
    evidence_items: list[EvidenceItem],
    seen_evidence_ids: set[str],
    item: EvidenceItem,
) -> None:
    if item.evidence_id in seen_evidence_ids:
        return
    seen_evidence_ids.add(item.evidence_id)
    evidence_items.append(item)


def build_sec_evidence_for_source_ids(
    ticker: str,
    cik: str,
    companyfacts_json: dict[str, Any],
    source_ids: Iterable[str],
) -> list[EvidenceItem]:
    """Materialize only the raw SEC facts used by canonical calculations."""

    accessions = {
        str(source_id).removeprefix("SEC_")
        for source_id in source_ids
        if source_id
    }
    if not accessions:
        return []
    parser = CompanyFactsParser(
        ticker=ticker,
        cik=cik,
        companyfacts_json=companyfacts_json,
    )
    evidence: list[EvidenceItem] = []
    seen: set[str] = set()
    for metric_name in SEC_FUNDAMENTAL_METRICS:
        for fact in parser.get_facts_for_metric(metric_name):
            if fact.accession not in accessions:
                continue
            item = parser.to_evidence_item(fact)
            if item.evidence_id in seen:
                continue
            seen.add(item.evidence_id)
            evidence.append(item)
    return evidence


def _assign_normalized_metric(
    metrics: dict[str, Any],
    metric: str,
    quarterly_values: list[float],
    annual_value: Optional[float],
) -> None:
    if metric in {
        "revenue",
        "gross_profit",
        "operating_income",
        "net_income",
        "operating_cash_flow",
        "capex",
        "sbc",
        "buybacks",
        "dividends_paid",
        "depreciation_and_amortization",
        "interest_expense",
        "eps_diluted",
    }:
        metrics["quarterly"][metric] = quarterly_values
    elif metric in {
        "cash_and_equivalents",
        "short_term_investments",
        "current_assets",
        "current_liabilities",
        "total_debt",
        "short_term_debt",
        "debt_current",
        "debt_noncurrent",
        "lease_liability_current",
        "lease_liability_noncurrent",
        "equity",
        "treasury_stock_value",
    }:
        metrics["balance_sheet"][metric] = (
            quarterly_values[-1] if quarterly_values else annual_value
        )
    elif metric == "shares_diluted":
        metrics["share_data"]["diluted_share_count"] = (
            quarterly_values[-1] if quarterly_values else annual_value
        )
    elif metric == "listed_share_count":
        metrics["share_data"]["listed_share_count"] = (
            quarterly_values[-1] if quarterly_values else annual_value
        )
    elif metric == "treasury_share_count":
        metrics["share_data"]["treasury_share_count"] = (
            quarterly_values[-1] if quarterly_values else annual_value
        )


def _derived_metric_evidence(ticker: str, cik: str, metrics: dict[str, Any]) -> list[EvidenceItem]:
    evidence_items: list[EvidenceItem] = []
    quarterly = metrics.get("quarterly", {})
    revenue_values = quarterly.get("revenue")
    ocf_values = quarterly.get("operating_cash_flow")
    capex_values = quarterly.get("capex")
    sbc_values = quarterly.get("sbc")

    if ocf_values and capex_values and len(ocf_values) == 4 and len(capex_values) == 4:
        fcf = sum(ocf_values) - abs(sum(capex_values))
        evidence_items.append(
            EvidenceItem(
                evidence_id=f"{ticker.upper()}_SEC_DERIVED_FREE_CASH_FLOW_TTM",
                ticker=ticker.upper(),
                claim_type="financial_metric",
                source_id=f"SEC_{str(cik).zfill(10)}_DERIVED_FCF",
                source_type="sec_filing",
                authority_rank=rank_source("sec_filing"),
                statement=f"{ticker.upper()} free_cash_flow_ttm derived from SEC operating cash flow and capex facts.",
                value=fcf,
                unit="USD",
                period="TTM",
                supports_metrics=["free_cash_flow_ttm", "free_cash_flow", "fcf"],
                confidence="high",
            )
        )

    if (
        revenue_values
        and sbc_values
        and len(revenue_values) == 4
        and len(sbc_values) == 4
        and sum(revenue_values) != 0
    ):
        ratio = sum(sbc_values) / sum(revenue_values)
        evidence_items.append(
            EvidenceItem(
                evidence_id=f"{ticker.upper()}_SEC_DERIVED_SBC_TO_REVENUE",
                ticker=ticker.upper(),
                claim_type="financial_metric",
                source_id=f"SEC_{str(cik).zfill(10)}_DERIVED_SBC_TO_REVENUE",
                source_type="sec_filing",
                authority_rank=rank_source("sec_filing"),
                statement=f"{ticker.upper()} sbc_to_revenue derived from SEC SBC and revenue facts.",
                value=ratio,
                unit="percent",
                period="TTM",
                supports_metrics=["sbc_to_revenue"],
                confidence="high",
            )
        )
    return evidence_items
