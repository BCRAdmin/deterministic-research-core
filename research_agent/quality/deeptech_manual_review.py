from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from research_agent.audit.audit_report import AuditIssue


SPECULATIVE_DEEP_TECH_MANUAL_REVIEW_PROFILE = "SPECULATIVE_DEEP_TECH_MANUAL_REVIEW_PROFILE"
EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH_MANUAL_REVIEW_PROFILE = "EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH_MANUAL_REVIEW_PROFILE"
MANUAL_REVIEW_DISPLAY_RATING = "Manual Review / Preliminary Underweight"
EARLY_COMMERCIAL_CAPITAL_INTENSIVE_DISPLAY_RATING = "Manual Review / Hold Pending FCF and Execution Evidence"
MANUAL_REVIEW_EVIDENCE_INCOMPLETE_DISPLAY_RATING = "Manual Review / Hold Pending Primary Evidence"
ACCOUNTING_GAIN_NOT_OPERATING_TURNAROUND = "ACCOUNTING_GAIN_NOT_OPERATING_TURNAROUND"
EVIDENCE_INCOMPLETE_FOR_GOLD = "EVIDENCE_INCOMPLETE_FOR_GOLD"
VENDOR_ONLY_HARD_METRICS = "VENDOR_ONLY_HARD_METRICS"
ORDER_MATERIALITY_MISSING = "ORDER_MATERIALITY_MISSING"
TECHNICAL_OVERWEIGHT_IN_FUNDAMENTAL_THESIS = "TECHNICAL_OVERWEIGHT_IN_FUNDAMENTAL_THESIS"
CLEAN_BUY_ACCUMULATE_BLOCKED = "CLEAN_BUY_ACCUMULATE_BLOCKED"
CLEAN_HOLD_BLOCKED_FOR_SPECULATIVE_DEEP_TECH = "CLEAN_HOLD_BLOCKED_FOR_SPECULATIVE_DEEP_TECH"
UNKNOWN_OR_LOW_CONFIDENCE_ARCHETYPE = "UNKNOWN_OR_LOW_CONFIDENCE_ARCHETYPE"
BUSINESS_MODEL_KPI_COVERAGE_INCOMPLETE = "BUSINESS_MODEL_KPI_COVERAGE_INCOMPLETE"

BUSINESS_MODEL_KPI_REQUIREMENTS = {
    "WASTE_ENVIRONMENTAL_SERVICES": {
        "price_or_yield": r"\b(?:yield|price(?:ing)?|collection and disposal)\b",
        "volume": r"\bvolume\b",
        "operating_ebitda": r"\b(?:operating ebitda|adjusted ebitda|ebitda margin)\b",
        "free_cash_flow_guidance": r"\b(?:free cash flow|fcf)\b.{0,100}\b(?:guidance|outlook|range)\b|\b(?:guidance|outlook|range)\b.{0,100}\b(?:free cash flow|fcf)\b",
        "capital_allocation": (
            r"\b(?:returned?|returning)\b.{0,100}\bshareholders?\b|"
            r"\b(?:share repurchases?|stock repurchases?|cash dividends?|"
            r"capital returned|return of capital)\b"
        ),
    },
    "MEMBERSHIP_RETAIL": {
        "paid_members": r"\b(?:paid members?|paid memberships?)\b",
        "cardholders": r"\bcardholders?\b",
        "renewal_rate": r"\brenewal rates?\b",
        "comparable_sales": r"\b(?:comparable sales|comp sales)\b",
        "traffic_and_ticket": r"\b(?:traffic|frequency)\b.{0,120}\b(?:ticket|basket)\b|\b(?:ticket|basket)\b.{0,120}\b(?:traffic|frequency)\b",
        "digital_sales": r"\b(?:digital|e-?commerce)\b",
    },
    "DIVERSIFIED_MEDICAL_DEVICES_DIAGNOSTICS": {
        "organic_or_comparable_growth": r"\b(?:organic|comparable)\b.{0,80}\bgrowth\b|\bgrowth\b.{0,80}\b(?:organic|comparable)\b",
        "segment_growth": r"\bsegment\b.{0,100}\bgrowth\b|\bgrowth\b.{0,100}\bsegment\b",
        "adjusted_eps_guidance": r"\badjusted eps\b.{0,120}\b(?:guidance|outlook|range)\b|\b(?:guidance|outlook|range)\b.{0,120}\badjusted eps\b",
        "transaction_financing": r"\b(?:acquisition|transaction)\b.{0,140}\b(?:debt|financ|consideration|purchase price)\b|\b(?:debt|financ)\b.{0,140}\b(?:acquisition|transaction)\b",
        "integration_effects": r"\b(?:integration costs?|amortization|purchase accounting)\b",
        "product_or_regulatory_catalyst": r"\b(?:approval|clearance|regulatory|product launch|clinical)\b",
    },
}


class CompanyArchetype(str, Enum):
    MEGA_CAP_PLATFORM = "MEGA_CAP_PLATFORM"
    SAAS_CONSUMPTION = "SAAS_CONSUMPTION"
    SEMICONDUCTOR_AI_INFRA = "SEMICONDUCTOR_AI_INFRA"
    SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL = "SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL"
    EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH = "EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH"
    WASTE_ENVIRONMENTAL_SERVICES = "WASTE_ENVIRONMENTAL_SERVICES"
    MEMBERSHIP_RETAIL = "MEMBERSHIP_RETAIL"
    DIVERSIFIED_MEDICAL_DEVICES_DIAGNOSTICS = "DIVERSIFIED_MEDICAL_DEVICES_DIAGNOSTICS"
    STANDARD_GROWTH = "STANDARD_GROWTH"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class DeepTechManualReviewAssessment:
    company_archetype: CompanyArchetype
    archetype_confidence: float
    archetype_triggered_rules: list[str]
    active: bool
    trigger_count: int
    triggers: dict[str, bool]
    issues: list[AuditIssue] = field(default_factory=list)
    status: str = "quality_pass"
    publishable: bool = True
    external_display_rating: str | None = None
    quality_score_cap: int | None = None
    counts: dict[str, int] = field(default_factory=dict)
    sec_ir_current_period_evidence_complete: bool = False
    business_model_kpi_coverage_complete: bool = True
    required_business_kpis: list[str] = field(default_factory=list)
    missing_business_kpis: list[str] = field(default_factory=list)

    def to_quality_payload(self) -> dict[str, Any]:
        return {
            "speculative_deep_tech_profile_count": self.counts.get("speculative_deep_tech_profile_count", 0),
            "accounting_gain_not_operating_turnaround_count": self.counts.get("accounting_gain_not_operating_turnaround_count", 0),
            "vendor_only_hard_metrics_count": self.counts.get("vendor_only_hard_metrics_count", 0),
            "order_materiality_missing_count": self.counts.get("order_materiality_missing_count", 0),
            "technical_overweight_in_thesis_count": self.counts.get("technical_overweight_in_thesis_count", 0),
            "early_commercial_capital_intensive_tech_count": self.counts.get("early_commercial_capital_intensive_tech_count", 0),
            "deeptech_sec_ir_current_period_evidence_complete": self.sec_ir_current_period_evidence_complete,
            "deeptech_quality_score_cap": self.quality_score_cap or 0,
            "company_archetype": self.company_archetype.value,
            "archetype_confidence": self.archetype_confidence,
            "archetype_triggered_rules": self.archetype_triggered_rules,
            "business_model_kpi_coverage_complete": self.business_model_kpi_coverage_complete,
            "required_business_kpis": self.required_business_kpis,
            "missing_business_kpis": self.missing_business_kpis,
            "business_model_kpi_gap_count": len(self.missing_business_kpis),
            "unknown_or_low_confidence_archetype_count": int(
                self.company_archetype == CompanyArchetype.UNKNOWN
                or self.archetype_confidence < 0.6
            ),
        }


def assess_speculative_deep_tech_manual_review(
    *,
    markdown: str,
    metrics_packet: Any,
    source_registry: Any = None,
    rating_text: str | None = None,
) -> DeepTechManualReviewAssessment:
    text = markdown or ""
    rating_scope = rating_text or text
    has_sec_ir = _has_sec_ir_current_period_evidence(source_registry)
    vendor_only = _has_vendor_only_hard_metrics(metrics_packet, source_registry, has_sec_ir)
    speculative_triggers = {
        "market_cap_revenue_gt_100": _market_cap_to_revenue_over_100(metrics_packet),
        "revenue_ttm_lt_50m": _value_lt(_metric(metrics_packet, "fundamentals", "revenue_ttm"), 50_000_000),
        "operating_income_ttm_lt_0": _value_lt(_metric(metrics_packet, "fundamentals", "operating_income_ttm"), 0),
        "free_cash_flow_ttm_lt_0": _value_lt(_metric(metrics_packet, "fundamentals", "free_cash_flow_ttm"), 0),
        "sbc_to_revenue_gt_050": _value_gt(_metric(metrics_packet, "fundamentals", "sbc_to_revenue"), 0.50),
        "vendor_only_hard_financial_metrics": vendor_only,
        "derivative_warrant_fair_value_effects_detected": _has_derivative_or_warrant_effects(text),
        "no_sec_ir_current_period_evidence": not has_sec_ir,
        "lumpy_revenue_non_scaled_adoption_language": _has_lumpy_or_non_scaled_adoption_language(text),
        "share_dilution_yoy_gt_010": _value_gt(_metric(metrics_packet, "fundamentals", "diluted_share_count_yoy"), 0.10) or _has_share_dilution_over_10(text),
        "technical_milestone_language_dominates_news": _has_technical_milestone_language_dominates_news(text),
        "high_volatility_or_beta_gt_15": _has_high_volatility_or_beta_over_15(text),
    }
    early_triggers = _early_commercial_capital_intensive_triggers(
        text=text,
        metrics_packet=metrics_packet,
        source_registry=source_registry,
        has_sec_ir=has_sec_ir,
    )
    speculative_trigger_count = sum(1 for value in speculative_triggers.values() if value)
    early_trigger_count = sum(1 for value in early_triggers.values() if value)
    frontier_real_revenue_active = _is_frontier_real_revenue_extreme_economics(
        text=text,
        metrics_packet=metrics_packet,
        source_registry=source_registry,
    )
    early_commercial_active = _is_early_commercial_capital_intensive(early_triggers) or frontier_real_revenue_active
    speculative_active = (
        not early_commercial_active
        and speculative_trigger_count >= 3
        and not _large_profitable_scale_blocks_deeptech(metrics_packet)
        and (
            speculative_triggers["revenue_ttm_lt_50m"]
            or speculative_triggers["vendor_only_hard_financial_metrics"]
            or (
                speculative_triggers["no_sec_ir_current_period_evidence"]
                and speculative_triggers["lumpy_revenue_non_scaled_adoption_language"]
            )
        )
    )
    if early_commercial_active:
        archetype = CompanyArchetype.EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH
        triggered_rules = [name for name, value in early_triggers.items() if value]
        if frontier_real_revenue_active:
            triggered_rules.append("frontier_real_revenue_extreme_economics")
        confidence = round((early_trigger_count + int(frontier_real_revenue_active)) / (len(early_triggers) + 1), 3)
    elif speculative_active:
        archetype = CompanyArchetype.SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL
        triggered_rules = [name for name, value in speculative_triggers.items() if value]
        confidence = round(speculative_trigger_count / len(speculative_triggers), 3)
    else:
        archetype = _infer_non_deeptech_archetype(
            text, metrics_packet, source_registry
        )
        triggered_rules = [name for name, value in speculative_triggers.items() if value]
        confidence = _archetype_confidence(archetype, text, metrics_packet, source_registry)
    active = speculative_active
    issues: list[AuditIssue] = []
    if speculative_active:
        issues.append(_issue(SPECULATIVE_DEEP_TECH_MANUAL_REVIEW_PROFILE, "Speculative deep-tech early-commercial company archetype requires manual review."))
    if early_commercial_active:
        issues.append(
            _issue(
                EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH_MANUAL_REVIEW_PROFILE,
                "Early-commercial capital-intensive tech profile requires manual review until FCF path, backlog conversion and execution milestones are evidenced.",
            )
        )
    required_business_kpis, missing_business_kpis = _business_model_kpi_coverage(
        archetype=archetype,
        text=text,
        source_registry=source_registry,
    )
    kpi_coverage_complete = not missing_business_kpis
    low_confidence_archetype = (
        archetype == CompanyArchetype.UNKNOWN or confidence < 0.6
    )
    if low_confidence_archetype:
        issues.append(
            _issue(
                UNKNOWN_OR_LOW_CONFIDENCE_ARCHETYPE,
                "Business-model archetype is unknown or too weakly evidenced for a high-confidence report.",
            )
        )
    if not kpi_coverage_complete:
        issues.append(
            _issue(
                BUSINESS_MODEL_KPI_COVERAGE_INCOMPLETE,
                "Required business-model KPIs are missing: "
                + ", ".join(missing_business_kpis),
            )
        )
    if vendor_only and speculative_active:
        issues.append(_issue(VENDOR_ONLY_HARD_METRICS, "Hard financial metrics rely on vendor/manual evidence without current-period SEC/IR support."))
    elif vendor_only:
        issues.append(_issue(EVIDENCE_INCOMPLETE_FOR_GOLD, "Hard financial metrics need current-period SEC/IR or IR evidence before Gold-v1 publication."))
    if speculative_triggers["derivative_warrant_fair_value_effects_detected"] and _has_net_income_improvement_claim(text) and not _has_operating_turnaround_caveat(text):
        issues.append(_issue(ACCOUNTING_GAIN_NOT_OPERATING_TURNAROUND, "Net income improvement language needs a clear non-operating fair-value caveat."))
    if (speculative_active or early_commercial_active) and _mentions_orders_contracts_or_roadmap(text) and not _has_order_materiality_section(text):
        issues.append(_issue(ORDER_MATERIALITY_MISSING, "Orders/contracts/roadmap milestones need a materiality section."))
    if (speculative_active or early_commercial_active) and _technical_claim_share(rating_scope) > 0.30:
        issues.append(_issue(TECHNICAL_OVERWEIGHT_IN_FUNDAMENTAL_THESIS, "Technical analysis dominates the fundamental rating rationale."))
    if (speculative_active or early_commercial_active) and _has_clean_buy_or_accumulate(rating_scope):
        issues.append(_issue(CLEAN_BUY_ACCUMULATE_BLOCKED, "Clean Buy/Accumulate language is blocked under the manual-review profile."))
    if speculative_active and _has_clean_hold(rating_scope):
        issues.append(_issue(CLEAN_HOLD_BLOCKED_FOR_SPECULATIVE_DEEP_TECH, "Clean Hold language must be reframed as Small Speculative Hold Only or Manual Review / Speculative Hold."))

    caps: list[int] = []
    if speculative_active and not has_sec_ir:
        caps.append(75)
    if early_commercial_active:
        caps.append(84)
    if any(issue.code == ACCOUNTING_GAIN_NOT_OPERATING_TURNAROUND for issue in issues):
        caps.append(70)
    if any(issue.code == ORDER_MATERIALITY_MISSING for issue in issues):
        caps.append(80)
    if any(issue.code == VENDOR_ONLY_HARD_METRICS for issue in issues):
        caps.append(75)
    if any(issue.code == EVIDENCE_INCOMPLETE_FOR_GOLD for issue in issues):
        caps.append(75)
    if low_confidence_archetype:
        caps.append(70)
    if not kpi_coverage_complete:
        caps.append(70)
    blocking_issue_codes = {
        ACCOUNTING_GAIN_NOT_OPERATING_TURNAROUND,
        VENDOR_ONLY_HARD_METRICS,
        EVIDENCE_INCOMPLETE_FOR_GOLD,
        ORDER_MATERIALITY_MISSING,
        TECHNICAL_OVERWEIGHT_IN_FUNDAMENTAL_THESIS,
        CLEAN_BUY_ACCUMULATE_BLOCKED,
        CLEAN_HOLD_BLOCKED_FOR_SPECULATIVE_DEEP_TECH,
        UNKNOWN_OR_LOW_CONFIDENCE_ARCHETYPE,
        BUSINESS_MODEL_KPI_COVERAGE_INCOMPLETE,
    }
    publishable = not speculative_active or (has_sec_ir and not any(issue.code in blocking_issue_codes for issue in issues))
    if early_commercial_active:
        publishable = False
    if any(issue.code in blocking_issue_codes for issue in issues):
        publishable = False
    status = "manual_review" if speculative_active or early_commercial_active or not publishable else "quality_pass"
    counts = {
        "speculative_deep_tech_profile_count": int(speculative_active),
        "early_commercial_capital_intensive_tech_count": int(early_commercial_active),
        "accounting_gain_not_operating_turnaround_count": _count(issues, ACCOUNTING_GAIN_NOT_OPERATING_TURNAROUND),
        "vendor_only_hard_metrics_count": _count(issues, VENDOR_ONLY_HARD_METRICS),
        "order_materiality_missing_count": _count(issues, ORDER_MATERIALITY_MISSING),
        "technical_overweight_in_thesis_count": _count(issues, TECHNICAL_OVERWEIGHT_IN_FUNDAMENTAL_THESIS),
    }
    assessment_triggers = early_triggers if early_commercial_active else speculative_triggers
    assessment_trigger_count = early_trigger_count if early_commercial_active else speculative_trigger_count
    return DeepTechManualReviewAssessment(
        company_archetype=archetype,
        archetype_confidence=confidence,
        archetype_triggered_rules=triggered_rules,
        active=active,
        trigger_count=assessment_trigger_count,
        triggers=assessment_triggers,
        issues=issues,
        status=status,
        publishable=publishable,
        external_display_rating=_external_display_rating(
            status=status,
            speculative_active=speculative_active,
            early_commercial_active=early_commercial_active,
        ),
        quality_score_cap=min(caps) if caps else None,
        counts=counts,
        sec_ir_current_period_evidence_complete=has_sec_ir,
        business_model_kpi_coverage_complete=kpi_coverage_complete,
        required_business_kpis=required_business_kpis,
        missing_business_kpis=missing_business_kpis,
    )


def manual_review_banner(assessment: DeepTechManualReviewAssessment | None = None) -> str:
    display = assessment.external_display_rating if assessment is not None else MANUAL_REVIEW_DISPLAY_RATING
    if assessment is not None and assessment.company_archetype == CompanyArchetype.EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH:
        return (
            f"> **{display}**\n"
            "> This early-commercial capital-intensive tech report is an internal draft. Backlog, contracts and current-period evidence are meaningful, "
            "but negative FCF, valuation intensity and execution milestones prevent clean external publication.\n\n"
        )
    if assessment is not None and assessment.company_archetype not in {
        CompanyArchetype.SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL,
        CompanyArchetype.EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH,
    }:
        return (
            f"> **{display}**\n"
            "> This report remains an internal draft because the business-model "
            "archetype or its required operating KPIs are not sufficiently evidenced.\n\n"
        )
    return (
        f"> **{display}**\n"
        "> This speculative deep-tech report is an internal draft. Vendor-only hard metrics, accounting fair-value effects, "
        "or incomplete SEC/IR evidence prevent clean external publication.\n\n"
    )


def _issue(code: str, message: str) -> AuditIssue:
    return AuditIssue(severity="warning", code=code, message=message)


def _count(issues: list[AuditIssue], code: str) -> int:
    return sum(1 for issue in issues if issue.code == code)


def _metric(packet: Any, group: str, name: str) -> float | None:
    obj = getattr(packet, group, None) if packet is not None else None
    value = getattr(obj, name, None) if obj is not None else None
    return float(value) if value is not None else None


def _value_lt(value: float | None, threshold: float) -> bool:
    return value is not None and value < threshold


def _value_gt(value: float | None, threshold: float) -> bool:
    return value is not None and value > threshold


def _large_profitable_scale_blocks_deeptech(packet: Any) -> bool:
    revenue = _metric(packet, "fundamentals", "revenue_ttm")
    market_cap = _metric(packet, "valuation", "market_cap")
    operating_income = _metric(packet, "fundamentals", "operating_income_ttm")
    fcf = _metric(packet, "fundamentals", "free_cash_flow_ttm")
    return (
        revenue is not None
        and market_cap is not None
        and operating_income is not None
        and fcf is not None
        and revenue > 1_000_000_000
        and market_cap > 100_000_000_000
        and operating_income > 0
        and fcf > 0
    )


def _external_display_rating(*, status: str, speculative_active: bool, early_commercial_active: bool) -> str | None:
    if status != "manual_review":
        return None
    if early_commercial_active:
        return EARLY_COMMERCIAL_CAPITAL_INTENSIVE_DISPLAY_RATING
    if speculative_active:
        return MANUAL_REVIEW_DISPLAY_RATING
    return MANUAL_REVIEW_EVIDENCE_INCOMPLETE_DISPLAY_RATING


def _market_cap_to_revenue_over_100(packet: Any) -> bool:
    return _market_cap_to_revenue_over(packet, 100)


def _market_cap_to_revenue_over(packet: Any, threshold: float) -> bool:
    market_cap = _metric(packet, "valuation", "market_cap")
    revenue = _metric(packet, "fundamentals", "revenue_ttm")
    return market_cap is not None and revenue not in {None, 0} and market_cap / max(abs(revenue), 1.0) > threshold


def _ev_to_sales_over(packet: Any, threshold: float) -> bool:
    ev_sales = _metric(packet, "valuation", "ev_to_sales")
    return ev_sales is not None and ev_sales > threshold


def _early_commercial_capital_intensive_triggers(
    *,
    text: str,
    metrics_packet: Any,
    source_registry: Any,
    has_sec_ir: bool,
) -> dict[str, bool]:
    return {
        "revenue_ttm_gt_100m": _value_gt(_metric(metrics_packet, "fundamentals", "revenue_ttm"), 100_000_000),
        "revenue_ttm_lt_5b": _value_lt(_metric(metrics_packet, "fundamentals", "revenue_ttm"), 5_000_000_000),
        "operating_income_ttm_lt_0": _value_lt(_metric(metrics_packet, "fundamentals", "operating_income_ttm"), 0),
        "free_cash_flow_ttm_lt_0": _value_lt(_metric(metrics_packet, "fundamentals", "free_cash_flow_ttm"), 0),
        "market_cap_revenue_gt_20": _market_cap_to_revenue_over(metrics_packet, 20),
        "ev_sales_gt_20": _ev_to_sales_over(metrics_packet, 20),
        "backlog_contracts_or_contracted_missions_present": _has_backlog_contracts_or_contracted_missions(text, source_registry),
        "capital_intensive_development_program_present": _has_capital_intensive_development_program(text, source_registry),
        "major_execution_milestone_risk_present": _has_major_execution_milestone_risk(text, source_registry),
        "product_platform_still_scaling": _has_product_or_platform_still_scaling(text, source_registry),
        "beta_high_volatility": _has_high_volatility_or_beta_over_15(text) or _atr_pct_gt(metrics_packet, 0.05),
        "current_period_evidence_exists_but_fcf_path_negative": has_sec_ir and _value_lt(_metric(metrics_packet, "fundamentals", "free_cash_flow_ttm"), 0),
    }


def _is_early_commercial_capital_intensive(triggers: dict[str, bool]) -> bool:
    required = [
        "revenue_ttm_gt_100m",
        "revenue_ttm_lt_5b",
        "operating_income_ttm_lt_0",
        "free_cash_flow_ttm_lt_0",
        "market_cap_revenue_gt_20",
        "ev_sales_gt_20",
        "backlog_contracts_or_contracted_missions_present",
        "capital_intensive_development_program_present",
        "major_execution_milestone_risk_present",
        "product_platform_still_scaling",
        "beta_high_volatility",
        "current_period_evidence_exists_but_fcf_path_negative",
    ]
    return all(triggers.get(name) for name in required)


def _is_frontier_real_revenue_extreme_economics(
    *,
    text: str,
    metrics_packet: Any,
    source_registry: Any,
) -> bool:
    revenue = _metric(metrics_packet, "fundamentals", "revenue_ttm")
    if revenue is None or revenue <= 100_000_000 or revenue >= 5_000_000_000:
        return False
    if not _value_lt(_metric(metrics_packet, "fundamentals", "operating_income_ttm"), 0):
        return False
    if not _value_lt(_metric(metrics_packet, "fundamentals", "free_cash_flow_ttm"), 0):
        return False
    if not (_ev_to_sales_over(metrics_packet, 50) or _market_cap_to_revenue_over(metrics_packet, 50)):
        return False
    if not _value_gt(_metric(metrics_packet, "fundamentals", "sbc_to_revenue"), 0.50):
        return False
    return _has_frontier_context(text, metrics_packet, source_registry) or _ev_to_sales_over(metrics_packet, 100)


def _has_frontier_context(text: str, metrics_packet: Any, source_registry: Any) -> bool:
    context = _context_text(text, source_registry)
    context = f"{context} {str(getattr(metrics_packet, 'ticker', '') or '').lower()}"
    return bool(
        re.search(
            r"\b(?:quantum|qubit|frontier[- ]?tech|deep[- ]?tech|hardware platform|photonic|ion trap|superconducting|compute story)\b",
            context,
        )
    )


def _registry_terms(source_registry: Any) -> str:
    sources = getattr(source_registry, "sources", []) if source_registry is not None else []
    parts: list[str] = []
    for source in sources:
        source_type = str(getattr(source, "source_type", "") or "")
        parts.append(source_type)
        parts.append(source_type.replace("_", " "))
        for item in getattr(source, "used_for", []) or []:
            term = str(item)
            parts.append(term)
            parts.append(term.replace("_", " "))
    return " ".join(parts).lower()


def _context_text(text: str, source_registry: Any) -> str:
    return f"{text or ''} {_registry_terms(source_registry)}".lower()


def _has_backlog_contracts_or_contracted_missions(text: str, source_registry: Any) -> bool:
    context = _context_text(text, source_registry)
    return bool(
        re.search(
            r"\b(?:backlog|contract backlog|contracted missions|contracted mission|contracts|contract value|remaining performance obligations|rpo|launch manifest|bookings)\b",
            context,
        )
    )


def _has_capital_intensive_development_program(text: str, source_registry: Any) -> bool:
    context = _context_text(text, source_registry)
    return bool(
        re.search(
            r"\b(?:capital[- ]?intensive|capex|development program|launch vehicle|space systems|launch services|manufacturing|factory|hardware platform|neutron|electron|satellite|spacecraft)\b",
            context,
        )
    )


def _has_major_execution_milestone_risk(text: str, source_registry: Any) -> bool:
    context = _context_text(text, source_registry)
    return bool(
        re.search(
            r"\b(?:execution risk|execution milestone|milestone risk|development risk|launch cadence|certification|scale[- ]?up|ramp|delayed|delay|neutron|electron|flight test|contract conversion)\b",
            context,
        )
    )


def _has_product_or_platform_still_scaling(text: str, source_registry: Any) -> bool:
    context = _context_text(text, source_registry)
    return bool(
        re.search(
            r"\b(?:product revenue|service revenue|segment mix|platform still scaling|still scaling|scaling|product platform|space systems|launch services|launch cadence|mission cadence)\b",
            context,
        )
    )


def _atr_pct_gt(packet: Any, threshold: float) -> bool:
    close = _metric(packet, "technical", "close")
    atr = _metric(packet, "technical", "atr_14")
    return close not in {None, 0} and atr is not None and abs(atr) / max(abs(close), 1.0) > threshold


def _has_sec_ir_current_period_evidence(source_registry: Any) -> bool:
    sources = getattr(source_registry, "sources", []) if source_registry is not None else []
    for source in sources:
        source_type = str(getattr(source, "source_type", "")).lower()
        used_for = " ".join(getattr(source, "used_for", []) or []).lower()
        if source_type in {"sec_filing", "company_ir"} and any(term in used_for for term in ["revenue", "financial", "cash", "eps", "fcf", "operating_income"]):
            return True
    return False


def _has_vendor_only_hard_metrics(packet: Any, source_registry: Any, has_sec_ir: bool) -> bool:
    hard_metrics_present = any(
        _metric(packet, "fundamentals", name) is not None
        for name in ["revenue_ttm", "operating_income_ttm", "free_cash_flow_ttm", "sbc_ttm", "cash_and_equivalents", "total_debt"]
    )
    if not hard_metrics_present:
        return False
    if source_registry is None:
        return not has_sec_ir
    sources = getattr(source_registry, "sources", []) or []
    hard_sources = [
        source
        for source in sources
        if any(term in " ".join(getattr(source, "used_for", []) or []).lower() for term in ["revenue", "cash", "fcf", "debt", "eps", "sbc", "operating_income"])
    ]
    if not hard_sources:
        return not has_sec_ir
    return not has_sec_ir and all(str(getattr(source, "source_type", "")).lower() not in {"sec_filing", "company_ir"} for source in hard_sources)


def _has_derivative_or_warrant_effects(text: str) -> bool:
    financial_effect = (
        r"(?:fair[- ]?value|gain|loss|income|expense|liabilit(?:y|ies)|"
        r"accounting|remeasur(?:e|ement)|hedg(?:e|ing)|instrument|"
        r"equity|stock|share|securit(?:y|ies)|dilut(?:ion|ive))"
    )
    derivative_term = r"(?:derivative(?:s)?|derivat\w*|optionsschein\w*)"
    warrant_term = r"(?:stock warrants?|share warrants?|equity warrants?|warrant liabilities?)"
    return bool(
        re.search(
            rf"\b{derivative_term}\b[^.\n]{{0,140}}\b{financial_effect}\b|"
            rf"\b{financial_effect}\b[^.\n]{{0,140}}\b{derivative_term}\b|"
            rf"\b{warrant_term}\b[^.\n]{{0,140}}\b{financial_effect}\b|"
            rf"\b{financial_effect}\b[^.\n]{{0,140}}\b{warrant_term}\b",
            text,
            re.IGNORECASE,
        )
    )


def _has_lumpy_or_non_scaled_adoption_language(text: str) -> bool:
    terms = ["lumpy revenue", "early commercial", "limited commercial adoption", "non-scaled", "not scaled", "begrenzte kommerzielle adoption", "nicht skaliert"]
    lowered = text.lower()
    return any(term in lowered for term in terms)


def _has_high_volatility_or_beta_over_15(text: str) -> bool:
    for match in re.finditer(r"\bbeta[^0-9]{0,20}([0-9]+(?:[.,][0-9]+)?)", text, re.IGNORECASE):
        if float(match.group(1).replace(",", ".")) > 1.5:
            return True
    return bool(re.search(r"\b(?:high[- ]?volatility|hochvolatil)\b", text, re.IGNORECASE))


def _has_share_dilution_over_10(text: str) -> bool:
    for match in re.finditer(r"(?:share(?:s)?|diluted share count|dilution|aktienzahl|verwässerung|verwaesserung)[^%\n]{0,80}([0-9]+(?:[.,][0-9]+)?)\s*%", text, re.IGNORECASE):
        if float(match.group(1).replace(",", ".")) > 10:
            return True
    return False


def _has_technical_milestone_language_dominates_news(text: str) -> bool:
    lowered = text.lower()
    milestone_terms = re.findall(r"\b(?:milestone|roadmap|prototype|qubit|quantum|flight test|launch window|certification|robotics demo|technical milestone|meilenstein|prototyp|zertifizierung)\b", lowered)
    revenue_terms = re.findall(r"\b(?:revenue|umsatz|bookings|contract value|auftragswert|delivery revenue|commercial revenue)\b", lowered)
    return len(milestone_terms) >= 3 and len(milestone_terms) > max(2 * len(revenue_terms), 2)


def _has_net_income_improvement_claim(text: str) -> bool:
    return bool(re.search(r"\b(?:loss narrowed|net income improved|profitability improved|turnaround|verlust.*verring|nettoergebnis.*verbess)\b", text, re.IGNORECASE))


def _has_operating_turnaround_caveat(text: str) -> bool:
    lowered = text.lower()
    exact = "gaap net income was helped by non-operating fair-value effects and does not indicate an operating turnaround"
    return exact in lowered or bool(re.search(r"\b(?:fair[- ]?value|derivat|warrant)[^.\n]{0,180}(?:kein|nicht|does not indicate)[^.\n]{0,80}(?:operating turnaround|operativer turnaround|operative profitabilit)", lowered))


def _mentions_orders_contracts_or_roadmap(text: str) -> bool:
    return bool(re.search(r"\b(?:contract|contracts|auftrag|order|orders|roadmap|milestone|meilenstein|defense|quantum|afrl|c-dac)\b", text, re.IGNORECASE))


def _has_order_materiality_section(text: str) -> bool:
    lowered = text.lower()
    groups = [
        ["contract value", "auftragswert"],
        ["delivery", "revenue timing", "umsatzzeit", "liefer"],
        ["market cap", "marktkapitalisierung"],
        ["annual revenue", "jahresumsatz"],
        ["recurring", "one-off", "one off", "non-recurring", "wiederkehrend", "einmalig"],
        ["commercial", "government", "research", "prototype", "kommerziell", "staatlich", "forschung", "prototyp"],
        ["valuation support", "stützt die bewertung", "stutzt die bewertung"],
    ]
    return all(any(term in lowered for term in group) for group in groups)


def _technical_claim_share(text: str) -> float:
    sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+|\n+", text) if len(sentence.strip()) > 30]
    if not sentences:
        return 0.0
    rationale = [
        sentence for sentence in sentences
        if re.search(r"\b(?:rating|rationale|decision|thesis|underweight|buy|sell|hold|investment|entscheidung|these)\b", sentence, re.IGNORECASE)
    ] or sentences[:12]
    technical = re.compile(r"\b(?:technical|chart|sma|rsi|macd|support|resistance|momentum|trend|technisch|charttechnik)\b", re.IGNORECASE)
    return sum(1 for sentence in rationale if technical.search(sentence)) / max(len(rationale), 1)


def _has_clean_buy_or_accumulate(text: str) -> bool:
    lowered = text.lower()
    if "manual review" in lowered or "preliminary" in lowered:
        return False
    return bool(re.search(r"\b(?:rating|recommendation|action|empfehlung)\s*[:=-]\s*(?:buy|accumulate|kaufen|aufstocken)\b", lowered))


def _has_clean_hold(text: str) -> bool:
    lowered = text.lower()
    if "manual review" in lowered or "speculative hold" in lowered or "small speculative hold only" in lowered:
        return False
    return bool(re.search(r"\b(?:rating|recommendation|action|empfehlung)\s*[:=-]\s*(?:hold|halten)\b", lowered))


def _infer_non_deeptech_archetype(
    text: str,
    metrics_packet: Any,
    source_registry: Any,
) -> CompanyArchetype:
    lowered = _context_text(text, source_registry)
    if _contains_archetype_term(
        lowered,
        [
            "solid waste",
            "waste collection",
            "landfill",
            "recycling operations",
            "environmental services",
        ],
    ):
        return CompanyArchetype.WASTE_ENVIRONMENTAL_SERVICES
    if _contains_archetype_term(
        lowered,
        [
            "membership warehouse",
            "membership retail",
            "paid members",
            "renewal rate",
            "warehouse clubs",
        ],
    ):
        return CompanyArchetype.MEMBERSHIP_RETAIL
    if _contains_archetype_term(
        lowered,
        [
            "medical devices",
            "medical device",
            "diagnostics",
            "diagnostic products",
            "medtech",
        ],
    ):
        return CompanyArchetype.DIVERSIFIED_MEDICAL_DEVICES_DIAGNOSTICS
    if _contains_archetype_term(
        lowered,
        ["alphabet", "google", "microsoft", "amazon", "meta", "mega-cap", "mega cap"],
    ):
        return CompanyArchetype.MEGA_CAP_PLATFORM
    if _contains_archetype_term(
        lowered,
        ["snowflake", "datadog", "mongodb", "saas", "consumption"],
    ):
        return CompanyArchetype.SAAS_CONSUMPTION
    if _contains_archetype_term(
        lowered,
        ["semiconductor", "nvidia", "broadcom", "qcom", "micron", "ai infra", "gpu"],
    ):
        return CompanyArchetype.SEMICONDUCTOR_AI_INFRA
    revenue = _metric(metrics_packet, "fundamentals", "revenue_ttm")
    operating_income = _metric(metrics_packet, "fundamentals", "operating_income_ttm")
    market_cap = _metric(metrics_packet, "valuation", "market_cap")
    if (
        revenue is not None
        and revenue >= 50_000_000_000
        and market_cap is not None
        and market_cap >= 250_000_000_000
        and operating_income is not None
        and operating_income > 0
        and _contains_archetype_term(
            lowered,
            ["platform", "cloud", "digital advertising", "mega-cap", "large-cap"],
        )
    ):
        return CompanyArchetype.MEGA_CAP_PLATFORM
    if _contains_archetype_term(
        lowered,
        [
            "high-growth",
            "high growth",
            "growth company",
            "commercial expansion",
        ],
    ):
        return CompanyArchetype.STANDARD_GROWTH
    return CompanyArchetype.UNKNOWN


def _archetype_confidence(
    archetype: CompanyArchetype,
    text: str,
    metrics_packet: Any,
    source_registry: Any,
) -> float:
    if archetype == CompanyArchetype.UNKNOWN:
        return 0.0
    context = _context_text(text, source_registry)
    if archetype in {
        CompanyArchetype.WASTE_ENVIRONMENTAL_SERVICES,
        CompanyArchetype.MEMBERSHIP_RETAIL,
        CompanyArchetype.DIVERSIFIED_MEDICAL_DEVICES_DIAGNOSTICS,
    }:
        requirement_count = len(
            BUSINESS_MODEL_KPI_REQUIREMENTS.get(archetype.value, {})
        )
        matched = sum(
            1
            for pattern in BUSINESS_MODEL_KPI_REQUIREMENTS.get(
                archetype.value, {}
            ).values()
            if re.search(pattern, context, flags=re.IGNORECASE)
        )
        return round(0.7 + 0.3 * (matched / max(requirement_count, 1)), 3)
    if archetype == CompanyArchetype.MEGA_CAP_PLATFORM:
        return 0.75
    if archetype in {
        CompanyArchetype.SAAS_CONSUMPTION,
        CompanyArchetype.SEMICONDUCTOR_AI_INFRA,
    }:
        return 0.8
    if archetype == CompanyArchetype.STANDARD_GROWTH:
        return 0.6
    return 0.7


def _business_model_kpi_coverage(
    *,
    archetype: CompanyArchetype,
    text: str,
    source_registry: Any,
) -> tuple[list[str], list[str]]:
    requirements = BUSINESS_MODEL_KPI_REQUIREMENTS.get(archetype.value, {})
    if not requirements:
        return [], []
    context = _context_text(text, source_registry)
    required = sorted(requirements)
    missing = sorted(
        name
        for name, pattern in requirements.items()
        if re.search(pattern, context, flags=re.IGNORECASE) is None
    )
    return required, missing


def _contains_archetype_term(text: str, terms: list[str]) -> bool:
    return any(
        re.search(
            rf"(?<![\w]){re.escape(term)}(?![\w])",
            text,
            re.IGNORECASE,
        )
        for term in terms
    )
