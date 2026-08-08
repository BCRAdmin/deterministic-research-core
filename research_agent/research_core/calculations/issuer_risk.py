from __future__ import annotations

import re
from typing import Iterable, Optional

from research_agent.evidence.evidence_item import EvidenceItem
from research_agent.research_core.models.metrics_packet import (
    FundamentalMetrics,
    IssuerRiskAssessment,
    RiskComponent,
)


_BUSINESS_RISK_PATTERNS = {
    "competition_and_technology": re.compile(
        r"\b(competition|competitive|technology|artificial intelligence|\bAI\b)\b",
        re.IGNORECASE,
    ),
    "cyber_and_data": re.compile(
        r"\b(cyber|security breach|privacy|personal data)\b",
        re.IGNORECASE,
    ),
    "regulation_and_legal": re.compile(
        r"\b(regulat\w*|legal proceedings|compliance|government polic\w*)\b",
        re.IGNORECASE,
    ),
    "customer_and_contracts": re.compile(
        r"\b(customer concentration|customer contracts?|sales cycle|contract timing)\b",
        re.IGNORECASE,
    ),
    "governance_and_control": re.compile(
        r"\b(multi(?:ple)?[- ]class|voting power|controlled company|governance|founder)\b",
        re.IGNORECASE,
    ),
    "international_and_supply_chain": re.compile(
        r"\b(international|foreign|geopolit\w*|supply chain|third part\w*|vendor)\b",
        re.IGNORECASE,
    ),
    "people_and_execution": re.compile(
        r"\b(personnel|employee|management|key person|retain|recruit|execution)\w*\b",
        re.IGNORECASE,
    ),
}


def calculate_issuer_risk(
    fundamentals: FundamentalMetrics,
    risk_evidence: Iterable[EvidenceItem] = (),
) -> IssuerRiskAssessment:
    """Quantify measured financial risk without pretending to score business risk.

    The numeric score uses only reproducible financial statement inputs. SEC
    risk-factor headings are classified for reviewer coverage, but their count
    never changes the score because disclosure volume is not risk severity.
    """

    components = [
        _financial_resilience_component(fundamentals),
        _cash_flow_component(fundamentals),
        _dilution_component(fundamentals),
        _capital_allocation_component(fundamentals),
    ]
    scorable = [component for component in components if component.score is not None]
    measured_weight = sum(component.effective_weight for component in scorable)
    score = (
        sum(float(component.score) * component.effective_weight for component in scorable)
        / measured_weight
        if measured_weight
        else None
    )
    categories = _classify_disclosed_business_risks(risk_evidence)
    flags = _risk_flags(fundamentals)
    coverage_ratio = measured_weight
    limitations = [
        "The numeric score covers financial statement risk only; competitive, regulatory, governance and execution severity require human review.",
        "Thresholds are a transparent Room16 screening policy, not an empirical probability of loss or a personalized risk-tolerance assessment.",
        "The capital-structure thresholds are an operating-company screen; banks, insurers and other regulated financial institutions require a sector-specific risk adapter.",
    ]
    if not categories:
        limitations.append(
            "No structured primary-source business-risk categories were available in this run."
        )
    if 0 < coverage_ratio < 1:
        limitations.append(
            "The financial screen is incomplete. Its observed score may identify "
            "downside but must not be described as a low-risk conclusion."
        )

    return IssuerRiskAssessment(
        status="partial" if score is not None else "not_measured",
        financial_risk_score=round(score, 2) if score is not None else None,
        financial_risk_band=_risk_band(score, coverage_ratio),
        measured_weight=round(measured_weight, 4),
        coverage_ratio=round(coverage_ratio, 4),
        components=components,
        risk_flags=flags,
        disclosed_business_risk_categories=categories,
        limitations=limitations,
    )


def _financial_resilience_component(f: FundamentalMetrics) -> RiskComponent:
    values: list[tuple[str, float, str]] = []
    missing: list[str] = []
    if f.equity is None:
        missing.append("equity")
    else:
        values.append(
            (
                "equity",
                100.0 if f.equity <= 0 else 15.0,
                "Equity is non-positive." if f.equity <= 0 else "Equity is positive.",
            )
        )
    if f.current_ratio is None:
        missing.append("current_ratio")
    else:
        score = 85.0 if f.current_ratio < 1 else 55.0 if f.current_ratio < 1.5 else 20.0
        values.append(("current_ratio", score, f"Current ratio is {f.current_ratio:.2f}x."))
    if f.debt_to_equity is None:
        missing.append("debt_to_equity")
    else:
        score = 85.0 if f.debt_to_equity > 2 else 55.0 if f.debt_to_equity > 1 else 20.0
        values.append(("debt_to_equity", score, f"Debt/equity is {f.debt_to_equity:.2f}x."))
    coverage = f.free_cash_flow_interest_coverage_ttm or f.operating_income_interest_coverage_ttm
    if coverage is None:
        missing.append("interest_coverage")
    else:
        score = 95.0 if coverage < 1.5 else 70.0 if coverage < 3 else 45.0 if coverage < 5 else 15.0
        values.append(("interest_coverage", score, f"Interest coverage is {coverage:.2f}x."))
    if f.net_cash is None or f.revenue_ttm in (None, 0):
        missing.append("net_cash_to_revenue")
    else:
        net_debt_to_revenue = -float(f.net_cash) / float(f.revenue_ttm)
        score = 85.0 if net_debt_to_revenue > 1 else 60.0 if net_debt_to_revenue > 0.5 else 35.0 if net_debt_to_revenue > 0 else 10.0
        values.append(
            (
                "net_cash_to_revenue",
                score,
                f"Net debt/revenue is {net_debt_to_revenue:.2f}x." if net_debt_to_revenue > 0 else f"Net cash/revenue is {-net_debt_to_revenue:.2f}x.",
            )
        )
    return _component("financial_resilience", "Financial resilience", 0.35, values, missing, 2)


def _cash_flow_component(f: FundamentalMetrics) -> RiskComponent:
    values: list[tuple[str, float, str]] = []
    missing: list[str] = []
    if f.free_cash_flow_ttm is None:
        missing.append("free_cash_flow_ttm")
    elif f.free_cash_flow_ttm <= 0:
        values.append(("free_cash_flow_ttm", 95.0, "TTM free cash flow is non-positive."))
    else:
        values.append(("free_cash_flow_ttm", 15.0, "TTM free cash flow is positive."))
    if f.fcf_margin_ttm is None:
        missing.append("fcf_margin_ttm")
    else:
        margin = float(f.fcf_margin_ttm)
        score = 95.0 if margin < 0 else 70.0 if margin < 0.05 else 40.0 if margin < 0.15 else 15.0
        values.append(("fcf_margin_ttm", score, f"FCF margin is {margin:.1%}."))
    if f.free_cash_flow_conversion_ttm is None:
        missing.append("free_cash_flow_conversion_ttm")
    else:
        conversion = float(f.free_cash_flow_conversion_ttm)
        score = 90.0 if conversion < 0 else 65.0 if conversion < 0.5 else 40.0 if conversion < 0.8 else 20.0
        values.append(("free_cash_flow_conversion_ttm", score, f"FCF conversion is {conversion:.2f}x."))
    return _component("cash_flow_durability", "Cash-flow durability", 0.30, values, missing, 2)


def _dilution_component(f: FundamentalMetrics) -> RiskComponent:
    values: list[tuple[str, float, str]] = []
    missing: list[str] = []
    if f.diluted_share_count_yoy is None:
        missing.append("diluted_share_count_yoy")
    else:
        dilution = float(f.diluted_share_count_yoy)
        score = 95.0 if dilution > 0.10 else 75.0 if dilution > 0.05 else 50.0 if dilution > 0.02 else 25.0 if dilution > 0 else 10.0
        values.append(("diluted_share_count_yoy", score, f"Diluted share count changed {dilution:.1%} YoY."))
    if f.sbc_to_revenue is None:
        missing.append("sbc_to_revenue")
    else:
        sbc_ratio = float(f.sbc_to_revenue)
        score = 85.0 if sbc_ratio > 0.20 else 60.0 if sbc_ratio > 0.10 else 35.0 if sbc_ratio > 0.05 else 15.0
        values.append(("sbc_to_revenue", score, f"SBC/revenue is {sbc_ratio:.1%}."))
    return _component("dilution", "Dilution and stock-based compensation", 0.20, values, missing, 1)


def _capital_allocation_component(f: FundamentalMetrics) -> RiskComponent:
    missing: list[str] = []
    values: list[tuple[str, float, str]] = []
    distributions_available = f.shareholder_distributions_ttm is not None
    fcf_available = f.free_cash_flow_ttm not in (None, 0)
    if not distributions_available:
        missing.append("shareholder_distributions_ttm")
    if not fcf_available:
        missing.append("free_cash_flow_ttm")
    if distributions_available and fcf_available:
        gap = float(f.shareholder_distributions_minus_fcf_ttm or 0.0)
        ratio = gap / abs(float(f.free_cash_flow_ttm))
        score = 15.0 if ratio <= 0 else 45.0 if ratio <= 0.25 else 65.0 if ratio <= 0.5 else 85.0
        values.append(
            (
                "shareholder_distributions_minus_fcf_ttm",
                score,
                "Shareholder distributions are covered by TTM FCF." if gap <= 0 else f"Distributions exceed TTM FCF by {gap:.2f} in reporting currency.",
            )
        )
    return _component(
        "capital_allocation",
        "Capital-allocation coverage",
        0.15,
        values,
        missing,
        1,
        # The coverage relationship cannot be measured until both the
        # distribution numerator and the FCF denominator are available.
        coverage_ratio=1.0 if distributions_available and fcf_available else 0.0,
    )


def _component(
    component_id: str,
    label: str,
    weight: float,
    values: list[tuple[str, float, str]],
    missing: list[str],
    minimum_inputs: int,
    coverage_ratio: Optional[float] = None,
) -> RiskComponent:
    unique_missing = sorted(set(missing))
    if coverage_ratio is None:
        total_inputs = len(values) + len(unique_missing)
        coverage_ratio = len(values) / total_inputs if total_inputs else 0.0
    coverage_ratio = max(0.0, min(1.0, coverage_ratio))
    effective_weight = weight * coverage_ratio
    if len(values) < minimum_inputs:
        return RiskComponent(
            component_id=component_id,
            label=label,
            weight=weight,
            status="not_measured",
            coverage_ratio=round(coverage_ratio, 4),
            effective_weight=round(effective_weight, 4),
            observations=[item[2] for item in values],
            missing_inputs=unique_missing,
        )
    return RiskComponent(
        component_id=component_id,
        label=label,
        weight=weight,
        status="measured" if coverage_ratio == 1 else "partial",
        score=round(sum(item[1] for item in values) / len(values), 2),
        coverage_ratio=round(coverage_ratio, 4),
        effective_weight=round(effective_weight, 4),
        observations=[item[2] for item in values],
        missing_inputs=unique_missing,
    )


def _risk_flags(f: FundamentalMetrics) -> list[str]:
    flags: list[str] = []
    if f.equity is not None and f.equity <= 0:
        flags.append("non_positive_equity")
    if f.free_cash_flow_ttm is not None and f.free_cash_flow_ttm <= 0:
        flags.append("non_positive_free_cash_flow")
    if f.diluted_share_count_yoy is not None and f.diluted_share_count_yoy > 0.05:
        flags.append("diluted_share_count_growth_above_5pct")
    if f.sbc_to_revenue is not None and f.sbc_to_revenue > 0.10:
        flags.append("sbc_above_10pct_of_revenue")
    if (
        f.shareholder_distributions_minus_fcf_ttm is not None
        and f.shareholder_distributions_minus_fcf_ttm > 0
    ):
        flags.append("shareholder_distributions_exceed_fcf")
    return flags


def _classify_disclosed_business_risks(
    evidence: Iterable[EvidenceItem],
) -> list[str]:
    statements = [
        item.statement
        for item in evidence
        if item.claim_type == "risk" and item.source_type == "sec_filing"
    ]
    return [
        category
        for category, pattern in _BUSINESS_RISK_PATTERNS.items()
        if any(pattern.search(statement) for statement in statements)
    ]


def _risk_band(score: Optional[float], coverage_ratio: float) -> str:
    if score is None:
        return "not_measured"
    if coverage_ratio < 1:
        return "incomplete_financial_screen"
    if score < 25:
        return "low_financial_risk"
    if score < 50:
        return "moderate_financial_risk"
    if score < 75:
        return "elevated_financial_risk"
    return "high_financial_risk"
