from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

from research_agent.audit.audit_report import ExtractedNumericClaim


METRIC_ALIASES = {
    "free_cash_flow_ttm": [
        "fcf ttm",
        "free cashflow ttm",
        "free cash flow ttm",
        "ttm free cash flow",
        "freier cashflow ttm",
        "free cashflow",
        "free cash flow",
        "fcf",
    ],
    "revenue_ttm": [
        "revenue ttm",
        "ttm revenue",
        "validated revenue",
        "revenue",
        "umsatz",
    ],
    "fcf_margin_ttm": [
        "fcf margin",
        "free cash flow margin",
        "fcf-marge",
    ],
    "operating_income_ttm": [
        "operating income ttm",
        "ttm operating income",
        "operating income",
        "income from operations",
    ],
    "operating_margin_ttm": [
        "operating margin ttm",
        "operative marge ttm",
        "betriebsmarge ttm",
        "operating margin",
        "operative marge",
    ],
    "sbc_to_revenue": [
        "sbc / revenue",
        "sbc/revenue",
        "sbc / umsatz",
        "sbc zu umsatz",
        "sbc-to-revenue",
    ],
    "net_cash": [
        "net cash",
        "netto-cash",
        "net cash position",
    ],
    "net_debt": [
        "net debt",
        "netto-schulden",
        "nettoverschuldung",
    ],
    "sma_200": [
        "200 sma",
        "200-tage-sma",
        "200 tage durchschnitt",
        "200-day moving average",
        "200 day moving average",
    ],
    "sma_50": [
        "50 sma",
        "50-tage-sma",
        "50 tage durchschnitt",
        "50-day moving average",
        "50 day moving average",
    ],
    "forward_pe_consensus": [
        "forward p/e",
        "forward pe",
        "forward kgv",
        "konsens-kgv",
        "consensus p/e",
        "consensus pe",
    ],
    "forward_pe_guidance": [
        "guidance p/e",
        "guidance pe",
        "guidance kgv",
        "management guidance p/e",
    ],
    "ev_to_sales": [
        "ev/sales",
        "ev / sales",
        "ev-to-sales",
        "enterprise value to sales",
    ],
    "price_to_fcf": [
        "p/fcf",
        "p / fcf",
        "price to fcf",
        "price-to-fcf",
    ],
    "close": [
        "close",
        "frozen close",
        "price basis",
        "schlusskurs",
    ],
    "rsi_14": [
        "rsi",
        "rsi 14",
    ],
}


METRIC_PATHS = {
    "free_cash_flow_ttm": "fundamentals.free_cash_flow_ttm",
    "revenue_ttm": "fundamentals.revenue_ttm",
    "fcf_margin_ttm": "fundamentals.fcf_margin_ttm",
    "operating_income_ttm": "fundamentals.operating_income_ttm",
    "operating_margin_ttm": "fundamentals.operating_margin_ttm",
    "sbc_to_revenue": "fundamentals.sbc_to_revenue",
    "net_cash": "fundamentals.net_cash",
    "net_debt": "fundamentals.net_cash",
    "sma_200": "technical.sma_200",
    "sma_50": "technical.sma_50",
    "forward_pe_consensus": "valuation.forward_pe_consensus",
    "forward_pe_guidance": "valuation.forward_pe_guidance",
    "ev_to_sales": "valuation.ev_to_sales",
    "price_to_fcf": "valuation.price_to_fcf",
    "close": "technical.close",
    "rsi_14": "technical.rsi_14",
}


class MappedMetric(BaseModel):
    metric_name: str
    metric_path: str
    validated_value: Optional[float] = None


def infer_possible_metric(text: str) -> Optional[str]:
    normalized = _normalize_text(text)
    compact = normalized.replace(" / ", "/")
    if "sbc/revenue" in compact or "sbc to revenue" in normalized or "sbc-to-revenue" in normalized:
        return "sbc_to_revenue"
    if "ev/sales" in compact or "ev to sales" in normalized or "ev-to-sales" in normalized:
        return "ev_to_sales"
    if "p/fcf" in compact or "price to fcf" in normalized or "price-to-fcf" in normalized:
        return "price_to_fcf"
    if "fcf margin" in normalized or "free cash flow margin" in normalized:
        return "fcf_margin_ttm"
    tokens = set(normalized.replace("-", " ").split())
    if "rsi" in tokens:
        return "rsi_14"
    if "forward" in normalized and ("kgv" in normalized or "p/e" in normalized or " pe" in normalized):
        if "guidance" in normalized or "management" in normalized:
            return "forward_pe_guidance"
        return "forward_pe_consensus"
    for metric_name, aliases in METRIC_ALIASES.items():
        if any(alias in normalized for alias in aliases):
            return metric_name
    if "stop-loss" in normalized or "stop loss" in normalized:
        return "stop_loss"
    if "entry" in normalized or "einstieg" in normalized:
        return "entry"
    return None


def map_claim_to_metric(
    claim: ExtractedNumericClaim,
    metrics_packet: Any,
) -> Optional[MappedMetric]:
    metric_name = claim.possible_metric or infer_possible_metric(claim.nearby_text)
    if metric_name is None:
        return None
    if metric_name == "forward_pe_consensus" and "guidance" in claim.nearby_text.lower():
        metric_name = "forward_pe_guidance"
    metric_path = METRIC_PATHS.get(metric_name)
    if metric_path is None:
        return None
    return MappedMetric(
        metric_name=metric_name,
        metric_path=metric_path,
        validated_value=_get_nested_value(metrics_packet, metric_path),
    )


def _get_nested_value(payload: Any, path: str) -> Optional[float]:
    value = payload
    for part in path.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            value = getattr(value, part, None)
        if value is None:
            return None
    return float(value)


def _normalize_text(text: str) -> str:
    return " ".join(text.lower().replace("_", " ").split())
