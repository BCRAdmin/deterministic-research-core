from __future__ import annotations

import re
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
    "sbc_to_fcf": [
        "sbc / fcf",
        "sbc/fcf",
        "sbc to fcf",
        "sbc-to-fcf",
        "sbc of fcf",
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
        "200-sma",
        "200-tage-sma",
        "200 tage durchschnitt",
        "200-day moving average",
        "200 day moving average",
    ],
    "sma_50": [
        "50 sma",
        "50-sma",
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
    "current_ratio": [
        "current ratio",
        "current liquidity ratio",
    ],
}


METRIC_PATHS = {
    "free_cash_flow_ttm": "fundamentals.free_cash_flow_ttm",
    "shareholder_distributions_ttm": (
        "fundamentals.shareholder_distributions_ttm"
    ),
    "shareholder_distributions_minus_fcf_ttm": (
        "fundamentals.shareholder_distributions_minus_fcf_ttm"
    ),
    "shareholder_distributions_current_period": (
        "fundamentals.shareholder_distributions_current_period"
    ),
    "free_cash_flow_current_period": "fundamentals.free_cash_flow_current_period",
    "shareholder_distributions_minus_fcf_current_period": (
        "fundamentals.shareholder_distributions_minus_fcf_current_period"
    ),
    "revenue_ttm": "fundamentals.revenue_ttm",
    "fcf_margin_ttm": "fundamentals.fcf_margin_ttm",
    "operating_income_ttm": "fundamentals.operating_income_ttm",
    "operating_margin_ttm": "fundamentals.operating_margin_ttm",
    "sbc_to_revenue": "fundamentals.sbc_to_revenue",
    "sbc_to_fcf": "fundamentals.sbc_to_fcf",
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
    "current_ratio": "fundamentals.current_ratio",
    "dcf_base_discount_rate": "valuation.sensitivity.scenarios.1.discount_rate",
    "dcf_base_terminal_growth_rate": (
        "valuation.sensitivity.scenarios.1.terminal_growth_rate"
    ),
    "dcf_base_terminal_value_share": (
        "valuation.sensitivity.scenarios.1.terminal_value_share"
    ),
    "reverse_dcf_implied_fcf_growth": (
        "valuation.sensitivity.reverse_dcf_implied_fcf_growth"
    ),
    "financial_risk_coverage": "risk.coverage_ratio",
    "diluted_share_count_yoy": "fundamentals.diluted_share_count_yoy",
    "current_period_revenue_growth_yoy": (
        "fundamentals.current_period_revenue_growth_yoy"
    ),
    "current_period_operating_income_growth_yoy": (
        "fundamentals.current_period_operating_income_growth_yoy"
    ),
    "current_period_net_income_growth_yoy": (
        "fundamentals.current_period_net_income_growth_yoy"
    ),
}


class MappedMetric(BaseModel):
    metric_name: str
    metric_path: str
    validated_value: Optional[float] = None


def infer_possible_metric(text: str, unit: Optional[str] = None) -> Optional[str]:
    normalized = _normalize_text(text)
    compact = normalized.replace(" / ", "/")
    current_period = any(
        marker in normalized
        for marker in (
            "same-period",
            "same period",
            "current-period",
            "current period",
            "period-matched",
            "period matched",
            "not a ttm claim",
        )
    )
    if current_period:
        if re.search(
            r"(?:covered by|below) same[- ]period fcf.{0,40}"
            r"metricvalueanchor.{0,20}remaining|"
            r"above same[- ]period fcf by.{0,20}metricvalueanchor",
            normalized,
        ):
            return "shareholder_distributions_minus_fcf_current_period"
        current_metric = _nearest_labeled_metric(
            normalized,
            {
                "shareholder distributions": "shareholder_distributions_current_period",
                "same-period fcf": "free_cash_flow_current_period",
                "same period fcf": "free_cash_flow_current_period",
                "free cash flow": "free_cash_flow_current_period",
                "fcf": "free_cash_flow_current_period",
                "remaining": "shareholder_distributions_minus_fcf_current_period",
                "above same-period fcf": (
                    "shareholder_distributions_minus_fcf_current_period"
                ),
                "above same period fcf": (
                    "shareholder_distributions_minus_fcf_current_period"
                ),
            },
            prefer_preceding=True,
        )
        if current_metric is not None:
            return current_metric
    if str(unit or "").lower() == "percent":
        assumption_metric = _nearest_labeled_metric(
            normalized,
            {
                "financial input coverage": "financial_risk_coverage",
                "financial-input coverage": "financial_risk_coverage",
                "terminal growth": "dcf_base_terminal_growth_rate",
                "terminal value": "dcf_base_terminal_value_share",
                "discount rate": "dcf_base_discount_rate",
                **(
                    {"fcf growth rate": "reverse_dcf_implied_fcf_growth"}
                    if "reverse dcf" in normalized
                    else {}
                ),
            },
        )
        if assumption_metric is not None:
            return assumption_metric
    if (
        str(unit or "").lower() == "percent"
        and "share count" in normalized
        and any(
            marker in normalized
            for marker in (
                "share count change",
                "share count changed",
                "share count increase",
                "share count increased",
                "share count decrease",
                "share count decreased",
                "share count unchanged",
            )
        )
    ):
        return "diluted_share_count_yoy"
    if (
        "distributions-minus-fcf" in normalized
        or "distributions minus fcf" in normalized
    ):
        return "shareholder_distributions_minus_fcf_ttm"
    if "shareholder distributions" in normalized:
        return "shareholder_distributions_ttm"
    if "sbc/revenue" in compact or "sbc to revenue" in normalized or "sbc-to-revenue" in normalized:
        return "sbc_to_revenue"
    if str(unit or "").lower() == "percent" and (
        "sbc/fcf" in compact
        or "sbc to fcf" in normalized
        or "sbc-to-fcf" in normalized
        or (
            "sbc" in normalized
            and "fcf" in normalized
            and any(marker in normalized for marker in ("equals", "of that", "of fcf"))
        )
    ):
        return "sbc_to_fcf"
    if "ev/sales" in compact or "ev to sales" in normalized or "ev-to-sales" in normalized:
        return "ev_to_sales"
    if "p/fcf" in compact or "price to fcf" in normalized or "price-to-fcf" in normalized:
        return "price_to_fcf"
    if "fcf margin" in normalized or "free cash flow margin" in normalized:
        return "fcf_margin_ttm"
    if str(unit or "").lower() == "percent":
        growth_metric = _nearest_growth_metric(normalized)
        if growth_metric is not None:
            return growth_metric
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
    metric_name = claim.possible_metric or infer_possible_metric(
        claim.nearby_text,
        unit=claim.unit,
    )
    if metric_name is None:
        return None
    if metric_name == "forward_pe_consensus" and "guidance" in claim.nearby_text.lower():
        metric_name = "forward_pe_guidance"
    metric_path = METRIC_PATHS.get(metric_name)
    if metric_path is None:
        return None
    validated_value = _get_nested_value(metrics_packet, metric_path)
    if metric_name == "net_debt" and validated_value is not None:
        validated_value = max(-validated_value, 0.0)
    return MappedMetric(
        metric_name=metric_name,
        metric_path=metric_path,
        validated_value=validated_value,
    )


def _get_nested_value(payload: Any, path: str) -> Optional[float]:
    value = payload
    for part in path.split("."):
        if isinstance(value, (list, tuple)) and part.isdigit():
            index = int(part)
            value = value[index] if index < len(value) else None
        elif isinstance(value, dict):
            value = value.get(part)
        else:
            value = getattr(value, part, None)
        if value is None:
            return None
    return float(value)


def _normalize_text(text: str) -> str:
    return " ".join(text.lower().replace("_", " ").split())


def _nearest_growth_metric(text: str) -> Optional[str]:
    semantic = text.replace("-", " ")
    markers = {
        "current_period_revenue_growth_yoy": (
            "revenue growth",
            "revenue changed",
            "revenue increase",
            "revenue increased",
            "revenue decline",
            "revenue declined",
            "revenue unchanged",
            "revenue by",
        ),
        "current_period_operating_income_growth_yoy": (
            "operating income growth",
            "operating income changed",
            "operating income increase",
            "operating income increased",
            "operating income decline",
            "operating income declined",
            "operating income unchanged",
            "operating income by",
        ),
        "current_period_net_income_growth_yoy": (
            "net income growth",
            "net income changed",
            "net income increase",
            "net income increased",
            "net income decline",
            "net income declined",
            "net income unchanged",
            "net income by",
        ),
    }
    return _nearest_labeled_metric(
        semantic,
        {
            marker: metric_name
            for metric_name, metric_markers in markers.items()
            for marker in metric_markers
        },
        prefer_preceding=True,
    )


def _nearest_labeled_metric(
    text: str,
    markers: dict[str, str],
    *,
    prefer_preceding: bool = False,
) -> Optional[str]:
    anchor = text.find("metricvalueanchor")
    anchor_end = anchor + len("metricvalueanchor") if anchor >= 0 else anchor
    candidates: list[tuple[int, int, str]] = []
    for marker, metric_name in markers.items():
        start = text.find(marker)
        while start >= 0:
            end = start + len(marker)
            if anchor < 0:
                distance = start
            elif end <= anchor:
                distance = anchor - end
            elif start >= anchor_end:
                distance = start - anchor_end
            else:
                distance = 0
            # Prefer a preceding label on an exact tie.
            follows_value = int(anchor >= 0 and start >= anchor_end)
            candidates.append((distance, follows_value, metric_name))
            start = text.find(marker, start + 1)
    if not candidates:
        return None
    if prefer_preceding:
        nearby_preceding = [
            item for item in candidates if item[1] == 0 and item[0] <= 32
        ]
        if nearby_preceding:
            return min(nearby_preceding)[2]
    return min(candidates)[2]
