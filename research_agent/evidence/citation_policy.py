from __future__ import annotations


HARD_METRIC_CLAIM_TYPES = {
    "financial_metric",
    "valuation_metric",
    "guidance",
    "price_data",
}

PRIMARY_REQUIRED_METRICS = {
    "revenue",
    "revenue_ttm",
    "free_cash_flow",
    "free_cash_flow_ttm",
    "fcf",
    "operating_income",
    "operating_income_ttm",
    "net_income",
    "net_income_ttm",
    "eps",
    "forward_eps",
    "company_guidance_eps",
    "consensus_forward_eps",
    "guidance",
    "sbc",
    "sbc_ttm",
    "cash",
    "cash_and_investments",
    "debt",
    "total_debt",
    "price_data",
    "price_basis",
    "close",
}


def requires_primary_source(metric_name: str, claim_type: str) -> bool:
    normalized = metric_name.strip().lower()
    if claim_type in HARD_METRIC_CLAIM_TYPES:
        return True
    return normalized in PRIMARY_REQUIRED_METRICS


def is_hard_metric(metric_name: str, claim_type: str = "financial_metric") -> bool:
    return requires_primary_source(metric_name, claim_type)
