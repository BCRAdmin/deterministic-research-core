from __future__ import annotations

from typing import Any, Optional

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
) -> tuple[dict[str, Any], list[EvidenceItem]]:
    parser = CompanyFactsParser(ticker=ticker, cik=cik, companyfacts_json=companyfacts_json)
    metrics: dict[str, Any] = {
        "quarterly": {},
        "balance_sheet": {},
        "share_data": {},
        "source": "sec_companyfacts",
    }
    evidence_items: list[EvidenceItem] = []

    for metric in SEC_FUNDAMENTAL_METRICS:
        annual = parser.latest_annual_fact(metric)
        if annual:
            metrics[f"{metric}_latest_annual"] = annual.value
            evidence_items.append(parser.to_evidence_item(annual))

        quarterly = parser.latest_quarterly_facts(metric, n=4)
        if quarterly:
            metrics[f"{metric}_latest_4_quarters"] = [fact.value for fact in quarterly]
            evidence_items.extend(parser.to_evidence_item(fact) for fact in quarterly)
            _assign_normalized_metric(
                metrics,
                metric,
                [fact.value for fact in quarterly],
                annual.value if annual else None,
            )

    return metrics, evidence_items


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
