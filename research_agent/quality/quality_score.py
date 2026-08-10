from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Union

from research_agent.audit.audit_report import AuditReport
from research_agent.content.claim_generator import claim_coverage_gaps
from research_agent.decision.decision_packet import DecisionPacket
from research_agent.decision.rating_permission import extract_rating_from_text
from research_agent.batch.freshness import STALE_PRICE_BASIS_FOR_CURRENT_REPORT
from research_agent.quality.deeptech_manual_review import (
    ACCOUNTING_GAIN_NOT_OPERATING_TURNAROUND,
    EARLY_COMMERCIAL_CAPITAL_INTENSIVE_DISPLAY_RATING,
    EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH_MANUAL_REVIEW_PROFILE,
    EVIDENCE_INCOMPLETE_FOR_GOLD,
    MANUAL_REVIEW_DISPLAY_RATING,
    MANUAL_REVIEW_EVIDENCE_INCOMPLETE_DISPLAY_RATING,
    ORDER_MATERIALITY_MISSING,
    SPECULATIVE_DEEP_TECH_MANUAL_REVIEW_PROFILE,
    TECHNICAL_OVERWEIGHT_IN_FUNDAMENTAL_THESIS,
    VENDOR_ONLY_HARD_METRICS,
)
from research_agent.quality.quality_report import QualityReport
from research_agent.research_core.models.validation_report import ValidationReport


MISSING_FCF_SUPPORT_FOR_ACCUMULATE = "MISSING_FCF_SUPPORT_FOR_ACCUMULATE"
HOLD_PENDING_FCF_SUPPORT_DISPLAY_RATING = "Hold Pending FCF Support"
BALANCE_SHEET_DATE_MISMATCH_EXCLUDED = "BALANCE_SHEET_DATE_MISMATCH_EXCLUDED"
SEC_OPERATING_INCOME_CONTEXT_MISMATCH_EXCLUDED = (
    "SEC_OPERATING_INCOME_CONTEXT_MISMATCH_EXCLUDED"
)
MISSING_RISK_ANALYSIS = "MISSING_RISK_ANALYSIS"
MISSING_CURRENT_PERIOD_KPI_CONTEXT = "MISSING_CURRENT_PERIOD_KPI_CONTEXT"
MISSING_COMPANY_SPECIFIC_ANALYSIS = "MISSING_COMPANY_SPECIFIC_ANALYSIS"
UNKNOWN_OR_LOW_CONFIDENCE_ARCHETYPE = "UNKNOWN_OR_LOW_CONFIDENCE_ARCHETYPE"
BUSINESS_MODEL_KPI_COVERAGE_INCOMPLETE = "BUSINESS_MODEL_KPI_COVERAGE_INCOMPLETE"


def calculate_quality_score(
    validation_report: ValidationReport,
    audit_report: AuditReport,
    decision_packet: DecisionPacket,
    final_markdown: Optional[str] = None,
    reconciliation_warnings: Optional[list[dict]] = None,
    analyst_claim_count: Optional[int] = None,
    evidence_mapped_claim_ratio: Optional[float] = None,
    hard_claim_evidence_ratio: Optional[float] = None,
    substantive_analyst_claim_count: Optional[int] = None,
    substantive_claim_ratio: Optional[float] = None,
    generic_claim_count: Optional[int] = None,
    generic_claim_ratio: Optional[float] = None,
    data_limitation_claim_count: Optional[int] = None,
    current_period_kpi_claim_count: Optional[int] = None,
    current_period_kpi_metric_count: Optional[int] = None,
    missing_current_period_context_count: Optional[int] = None,
    ticker_specific_kpi_claim_count: Optional[int] = None,
    final_rating_rationale_quality: Optional[int] = None,
    mechanical_rating_language_count: Optional[int] = None,
    company_defined_fcf_used: Optional[int] = None,
    sec_derived_fcf_used: Optional[int] = None,
    company_defined_fcf_mismatch_count: Optional[int] = None,
    fcf_unavailable_block_count: Optional[int] = None,
    company_specific_claim_count: Optional[int] = None,
    valuation_specific_claim_count: Optional[int] = None,
    technical_specific_claim_count: Optional[int] = None,
    rating_rationale_claim_count: Optional[int] = None,
    risk_specific_claim_count: Optional[int] = None,
    publish_report_exists: Optional[int] = None,
    publish_mechanical_language_count: Optional[int] = None,
    publish_current_kpi_count: Optional[int] = None,
    publish_evidence_appendix_exists: Optional[int] = None,
    publish_claim_id_main_body_count: Optional[int] = None,
    publish_valuation_sensitivity_present: Optional[int] = None,
    publish_action_plan_trigger_count: Optional[int] = None,
    fcf_ocf_inconsistency_count: Optional[int] = None,
    speculative_deep_tech_profile_count: Optional[int] = None,
    accounting_gain_not_operating_turnaround_count: Optional[int] = None,
    vendor_only_hard_metrics_count: Optional[int] = None,
    order_materiality_missing_count: Optional[int] = None,
    technical_overweight_in_thesis_count: Optional[int] = None,
    early_commercial_capital_intensive_tech_count: Optional[int] = None,
    deeptech_sec_ir_current_period_evidence_complete: Optional[bool] = None,
    deeptech_quality_score_cap: Optional[int] = None,
    company_archetype: Optional[str] = None,
    archetype_confidence: Optional[float] = None,
    archetype_triggered_rules: Optional[list[str]] = None,
    business_model_kpi_coverage_complete: Optional[bool] = None,
    required_business_kpis: Optional[list[str]] = None,
    missing_business_kpis: Optional[list[str]] = None,
    business_model_kpi_gap_count: Optional[int] = None,
    unknown_or_low_confidence_archetype_count: Optional[int] = None,
    data_freshness_status: Optional[str] = None,
    stale_price_basis: Optional[int] = None,
    current_report_allowed: Optional[bool] = None,
    historical_qa_only: Optional[bool] = None,
    freshness_issue_code: Optional[str] = None,
) -> QualityReport:
    numerical_accuracy = 25
    source_quality = 20
    logic_consistency = 20
    rating_discipline = 15
    event_awareness = 10
    writing_structure = 10
    content_score = 100
    research_incomplete = _is_research_incomplete(final_markdown, analyst_claim_count)
    main_body_kpi_count: Optional[int] = None
    appendix_only_kpi_count = 0
    main_body_mechanical_count = 0
    placeholder_business_context_count = 0
    if final_markdown:
        main_body_kpi_count = _count_main_body_current_period_kpi_claims(final_markdown)
        if current_period_kpi_claim_count is not None:
            appendix_only_kpi_count = max(0, current_period_kpi_claim_count - main_body_kpi_count)
            current_period_kpi_claim_count = main_body_kpi_count
        main_body_mechanical_count = _count_main_body_mechanical_language(final_markdown)
        placeholder_business_context_count = _count_placeholder_business_context(final_markdown)
        if mechanical_rating_language_count is not None:
            mechanical_rating_language_count += main_body_mechanical_count
    if publish_current_kpi_count is not None:
        current_period_kpi_claim_count = max(int(current_period_kpi_claim_count or 0), int(publish_current_kpi_count or 0))
    empty_required_section_count = _empty_required_archetype_section_count(
        final_markdown,
        company_archetype=company_archetype,
        speculative_deep_tech_profile_count=speculative_deep_tech_profile_count,
        early_commercial_capital_intensive_tech_count=early_commercial_capital_intensive_tech_count,
    )
    substantive_claim_ratio_supplied = substantive_claim_ratio is not None
    strict_content_v2 = any(
        value is not None
        for value in {
            substantive_claim_ratio,
            data_limitation_claim_count,
            current_period_kpi_claim_count,
            ticker_specific_kpi_claim_count,
            final_rating_rationale_quality,
            mechanical_rating_language_count,
        }
    )
    coverage_fields = {
        "analyst_claim_count": analyst_claim_count,
        "evidence_mapped_claim_ratio": evidence_mapped_claim_ratio,
        "hard_claim_evidence_ratio": hard_claim_evidence_ratio,
        "generic_claim_ratio": generic_claim_ratio,
        "data_limitation_claim_count": data_limitation_claim_count,
        "current_period_kpi_metric_count": current_period_kpi_metric_count,
        "final_rating_rationale_quality": final_rating_rationale_quality,
        "company_specific_claim_count": company_specific_claim_count,
        "valuation_specific_claim_count": valuation_specific_claim_count,
        "technical_specific_claim_count": technical_specific_claim_count,
        "rating_rationale_claim_count": rating_rationale_claim_count,
    }
    if risk_specific_claim_count is not None:
        coverage_fields["risk_specific_claim_count"] = risk_specific_claim_count
    coverage_gaps: Optional[list[str]] = None
    claim_coverage_complete: Optional[bool] = None
    if all(value is not None for value in coverage_fields.values()):
        coverage_gaps = claim_coverage_gaps(coverage_fields)
        claim_coverage_complete = not coverage_gaps

    for issue in validation_report.issues:
        if issue.code in {"EARNINGS_DATE_UNAVAILABLE", "EARNINGS_DATE_UNCONFIRMED"}:
            # Missing/unconfirmed event data is disclosure-relevant, but not a
            # quality failure unless the report invents event-risk claims.
            event_awareness -= 1
            continue
        if issue.severity == "error":
            logic_consistency -= 8
            source_quality -= 4
        elif issue.severity == "warning":
            logic_consistency -= 3
            source_quality -= 2

    for issue in audit_report.issues:
        if issue.code == "NUMERIC_MISMATCH":
            numerical_accuracy -= 12 if issue.severity == "error" else 4
        elif issue.code in {"PERIOD_MISMATCH", "INVALID_TRADE_LEVEL"}:
            logic_consistency -= 8 if issue.severity == "error" else 4
        elif issue.code in {"RATING_TOO_HARSH_FOR_ACTION", "RATING_ACTION_MISMATCH", "RATING_BLOCKED_BY_DECISION_PACKET"}:
            rating_discipline -= 10 if issue.severity == "error" else 5
        elif issue.code in {"OVERSTATED_CAUSALITY", "WEAK_NEWS_CAUSALITY", "NO_NEWS_WITH_AVAILABLE_SOURCES"}:
            event_awareness -= 6 if issue.severity == "error" else 3
            source_quality -= 4 if issue.code == "NO_NEWS_WITH_AVAILABLE_SOURCES" else 0
        elif issue.code == "UNVERIFIED_HARD_METRIC":
            numerical_accuracy -= 6
            source_quality -= 4
        elif issue.code == "MISSING_EVIDENCE_FOR_HARD_CLAIM":
            numerical_accuracy -= 10
            source_quality -= 8
        elif issue.code in {"VENDOR_SOURCE_USED_AS_PRIMARY", "LOW_AUTHORITY_EVIDENCE_FOR_HARD_CLAIM"}:
            source_quality -= 4
        elif issue.code == "UNSUPPORTED_GUIDANCE_CLAIM":
            source_quality -= 8
            logic_consistency -= 8
        elif issue.code == "UNSUPPORTED_EARNINGS_EVENT_CLAIM":
            event_awareness -= 8
            logic_consistency -= 6
        elif issue.code == "COMPANY_DEFINED_FCF_MISMATCH":
            numerical_accuracy -= 20
            source_quality -= 10
            logic_consistency -= 10
            content_score = min(content_score, 60)
        elif issue.code == "COMPANY_DEFINED_FCF_OCF_INCONSISTENCY":
            numerical_accuracy -= 8 if issue.severity == "error" else 3
            source_quality -= 4 if issue.severity == "error" else 2
            logic_consistency -= 4 if issue.severity == "error" else 2
        elif issue.code in {"FCF_UNAVAILABLE_WITHOUT_IR_SUPPORT", "MISSING_CURRENT_PERIOD_CONTEXT", "MISSING_CURRENT_PERIOD_KPI_CONTEXT", "AVGO_CURRENT_KPI_CONTEXT_REQUIRED"}:
            source_quality -= 6
            logic_consistency -= 6
            content_score = min(content_score, 70)
        elif issue.code.startswith("FINANCIAL_SANITY_") or issue.code in {"EXTREME_VALUATION_REQUIRES_REVIEW", "TRUE_VALUATION_ANOMALY"}:
            numerical_accuracy -= 10 if issue.severity == "error" else 5
            source_quality -= 6 if issue.severity == "error" else 3
            logic_consistency -= 6 if issue.severity == "error" else 3

    true_disagreements = [
        warning for warning in (reconciliation_warnings or [])
        if warning.get("code") == "TRUE_SOURCE_VALUE_DISAGREEMENT"
    ]
    if true_disagreements:
        # Penalize unresolved source conflicts without letting noisy SEC history
        # dominate the whole score once counts are already dashboard-visible.
        source_quality -= min(8, max(1, len(true_disagreements) // 10))

    if decision_packet.rating_permission.preferred_rating not in decision_packet.rating_permission.allowed_ratings:
        rating_discipline -= 15

    if final_markdown:
        final_rating = extract_rating_from_text(final_markdown)
        if final_rating and final_rating in decision_packet.rating_permission.blocked_ratings:
            rating_discipline -= 15
        if len([line for line in final_markdown.splitlines() if line.strip()]) < 4:
            writing_structure -= 4
        missing_sections = _missing_required_sections(final_markdown)
        if missing_sections:
            content_score -= min(60, len(missing_sections) * 8)
    if research_incomplete:
        writing_structure = min(writing_structure, 4)
        content_score = min(content_score, 40)
    elif claim_coverage_complete is False:
        content_score = min(content_score, 60)
        writing_structure -= 3
    if evidence_mapped_claim_ratio is not None and evidence_mapped_claim_ratio < 0.90:
        source_quality -= 8
        content_score = min(content_score, 70)
    if hard_claim_evidence_ratio is not None and hard_claim_evidence_ratio < 1.0:
        numerical_accuracy -= 10
        source_quality -= 8
        content_score = min(content_score, 60)
    if substantive_claim_ratio is None and analyst_claim_count:
        substantive_claim_ratio = (substantive_analyst_claim_count or 0) / analyst_claim_count
    if strict_content_v2 and substantive_claim_ratio is not None and substantive_claim_ratio < 0.70:
        content_score = min(content_score, 65)
        writing_structure -= 2
    if generic_claim_ratio is not None and generic_claim_ratio > 0.50:
        content_score = min(content_score, 60)
        writing_structure -= 3
    if data_limitation_claim_count is not None and analyst_claim_count:
        limitation_ratio = data_limitation_claim_count / max(analyst_claim_count, 1)
        if limitation_ratio > 0.25:
            content_score = min(content_score, 70)
            source_quality -= 4
        elif data_limitation_claim_count:
            content_score -= min(10, data_limitation_claim_count * 2)
    if missing_current_period_context_count:
        content_score = min(content_score, 70)
        event_awareness -= min(6, missing_current_period_context_count * 3)
    if current_period_kpi_metric_count is not None and current_period_kpi_metric_count < 3:
        content_score = min(content_score, 84)
        event_awareness -= 3
    if appendix_only_kpi_count:
        content_score = min(content_score, 88)
    if placeholder_business_context_count:
        content_score = min(content_score, 85)
        writing_structure -= 2
    if empty_required_section_count:
        content_score = min(content_score, 76 if empty_required_section_count >= 3 else 84)
        writing_structure -= min(4, empty_required_section_count)
    if unknown_or_low_confidence_archetype_count:
        content_score = min(content_score, 60)
        logic_consistency -= 6
    if business_model_kpi_coverage_complete is False or business_model_kpi_gap_count:
        content_score = min(content_score, 55)
        event_awareness -= 6
    if company_defined_fcf_mismatch_count:
        content_score = min(content_score, 60)
        numerical_accuracy -= 15
    if fcf_unavailable_block_count:
        content_score = min(content_score, 70)
        source_quality -= 6
    if final_rating_rationale_quality is not None:
        if final_rating_rationale_quality < 50:
            content_score = min(content_score, 82)
            rating_discipline -= 3
        elif final_rating_rationale_quality < 70:
            content_score = min(content_score, 88)
    if mechanical_rating_language_count:
        content_score = min(content_score, 88)
        writing_structure -= min(4, mechanical_rating_language_count)
    if publish_report_exists is not None:
        if not publish_report_exists:
            content_score = min(content_score, 84)
        if not publish_evidence_appendix_exists:
            content_score = min(content_score, 84)
        if publish_current_kpi_count is not None and publish_current_kpi_count < 1:
            content_score = min(content_score, 88)
        if publish_mechanical_language_count:
            content_score = min(content_score, 82)
            writing_structure -= min(4, publish_mechanical_language_count)
        if publish_claim_id_main_body_count:
            content_score = min(content_score, 85)
            writing_structure -= 2
        if publish_valuation_sensitivity_present is not None and not publish_valuation_sensitivity_present:
            content_score = min(content_score, 86)
            writing_structure -= 2
        if publish_action_plan_trigger_count is not None and publish_action_plan_trigger_count < 2:
            content_score = min(content_score, 86)
            rating_discipline -= 2
    if fcf_ocf_inconsistency_count:
        content_score = min(content_score, 88)
    if company_specific_claim_count is not None and company_specific_claim_count < 1:
        content_score = min(content_score, 70)
    if valuation_specific_claim_count is not None and valuation_specific_claim_count < 1:
        content_score = min(content_score, 75)
    if technical_specific_claim_count is not None and technical_specific_claim_count < 1:
        content_score = min(content_score, 75)
    if rating_rationale_claim_count is not None and rating_rationale_claim_count < 1:
        content_score = min(content_score, 75)
    if speculative_deep_tech_profile_count and not deeptech_sec_ir_current_period_evidence_complete:
        content_score = min(content_score, 75)
        source_quality -= 6
    if vendor_only_hard_metrics_count:
        content_score = min(content_score, 75)
        source_quality -= 8
    if accounting_gain_not_operating_turnaround_count:
        content_score = min(content_score, 70)
        logic_consistency -= 8
    if order_materiality_missing_count:
        content_score = min(content_score, 80)
        logic_consistency -= 4
    if technical_overweight_in_thesis_count:
        content_score = min(content_score, 82)
        rating_discipline -= 4
    if early_commercial_capital_intensive_tech_count:
        content_score = min(content_score, 84)
        rating_discipline -= 3
    if current_report_allowed is False and freshness_issue_code == STALE_PRICE_BASIS_FOR_CURRENT_REPORT:
        content_score = min(content_score, 80)
        source_quality -= 4

    category_scores = {
        "numerical_accuracy": _clamp(numerical_accuracy, 25),
        "source_quality": _clamp(source_quality, 20),
        "logic_consistency": _clamp(logic_consistency, 20),
        "rating_discipline": _clamp(rating_discipline, 15),
        "event_awareness": _clamp(event_awareness, 10),
        "writing_structure": _clamp(writing_structure, 10),
    }
    total = sum(category_scores.values())
    if analyst_claim_count is not None or substantive_analyst_claim_count is not None:
        total = min(total, _clamp(content_score, 100))
    if research_incomplete:
        total = min(total, 40)
    quality_cap = _deeptech_quality_cap(
        speculative_deep_tech_profile_count=speculative_deep_tech_profile_count,
        accounting_gain_not_operating_turnaround_count=accounting_gain_not_operating_turnaround_count,
        vendor_only_hard_metrics_count=vendor_only_hard_metrics_count,
        order_materiality_missing_count=order_materiality_missing_count,
        early_commercial_capital_intensive_tech_count=early_commercial_capital_intensive_tech_count,
        deeptech_sec_ir_current_period_evidence_complete=deeptech_sec_ir_current_period_evidence_complete,
    )
    if quality_cap is not None:
        total = min(total, quality_cap)
    publish_quality_score = _publish_quality_score(
        total_score=total,
        audit_report=audit_report,
        evidence_mapped_claim_ratio=evidence_mapped_claim_ratio,
        hard_claim_evidence_ratio=hard_claim_evidence_ratio,
        missing_current_period_context_count=missing_current_period_context_count,
        speculative_deep_tech_profile_count=speculative_deep_tech_profile_count,
        early_commercial_capital_intensive_tech_count=early_commercial_capital_intensive_tech_count,
        vendor_only_hard_metrics_count=vendor_only_hard_metrics_count,
        fcf_unavailable_block_count=fcf_unavailable_block_count,
        company_defined_fcf_mismatch_count=company_defined_fcf_mismatch_count,
        current_report_allowed=current_report_allowed,
        freshness_issue_code=freshness_issue_code,
    )
    publishable = is_publishable(
        total_score=publish_quality_score,
        validation_report=validation_report,
        audit_report=audit_report,
        decision_packet=decision_packet,
        final_markdown=final_markdown,
        analyst_claim_count=analyst_claim_count,
        evidence_mapped_claim_ratio=evidence_mapped_claim_ratio,
        hard_claim_evidence_ratio=hard_claim_evidence_ratio,
        substantive_analyst_claim_count=substantive_analyst_claim_count,
        substantive_claim_ratio=substantive_claim_ratio if substantive_claim_ratio_supplied else None,
        generic_claim_ratio=generic_claim_ratio,
        data_limitation_claim_count=data_limitation_claim_count,
        current_period_kpi_claim_count=current_period_kpi_claim_count,
        current_period_kpi_metric_count=current_period_kpi_metric_count,
        missing_current_period_context_count=missing_current_period_context_count,
        ticker_specific_kpi_claim_count=ticker_specific_kpi_claim_count,
        final_rating_rationale_quality=final_rating_rationale_quality,
        mechanical_rating_language_count=mechanical_rating_language_count,
        company_defined_fcf_mismatch_count=company_defined_fcf_mismatch_count,
        fcf_unavailable_block_count=fcf_unavailable_block_count,
        company_specific_claim_count=company_specific_claim_count,
        valuation_specific_claim_count=valuation_specific_claim_count,
        technical_specific_claim_count=technical_specific_claim_count,
        rating_rationale_claim_count=rating_rationale_claim_count,
        risk_specific_claim_count=risk_specific_claim_count,
        publish_report_exists=publish_report_exists,
        publish_mechanical_language_count=publish_mechanical_language_count,
        publish_current_kpi_count=publish_current_kpi_count,
        publish_evidence_appendix_exists=publish_evidence_appendix_exists,
        publish_claim_id_main_body_count=publish_claim_id_main_body_count,
        publish_valuation_sensitivity_present=publish_valuation_sensitivity_present,
        publish_action_plan_trigger_count=publish_action_plan_trigger_count,
        fcf_ocf_inconsistency_count=fcf_ocf_inconsistency_count,
        speculative_deep_tech_profile_count=speculative_deep_tech_profile_count,
        early_commercial_capital_intensive_tech_count=early_commercial_capital_intensive_tech_count,
        vendor_only_hard_metrics_count=vendor_only_hard_metrics_count,
        deeptech_sec_ir_current_period_evidence_complete=deeptech_sec_ir_current_period_evidence_complete,
        current_report_allowed=current_report_allowed,
        freshness_issue_code=freshness_issue_code,
        claim_coverage_complete=claim_coverage_complete,
    )
    risk_profiles = []
    if speculative_deep_tech_profile_count:
        risk_profiles.append(SPECULATIVE_DEEP_TECH_MANUAL_REVIEW_PROFILE)
    if early_commercial_capital_intensive_tech_count:
        risk_profiles.append(EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH_MANUAL_REVIEW_PROFILE)
    if freshness_issue_code == STALE_PRICE_BASIS_FOR_CURRENT_REPORT:
        risk_profiles.append(STALE_PRICE_BASIS_FOR_CURRENT_REPORT)
    if any(issue.code == MISSING_FCF_SUPPORT_FOR_ACCUMULATE for issue in audit_report.issues):
        risk_profiles.append(MISSING_FCF_SUPPORT_FOR_ACCUMULATE)
    manual_review_reasons = _deeptech_manual_review_reasons(
        speculative_deep_tech_profile_count=speculative_deep_tech_profile_count,
        early_commercial_capital_intensive_tech_count=early_commercial_capital_intensive_tech_count,
        accounting_gain_not_operating_turnaround_count=accounting_gain_not_operating_turnaround_count,
        vendor_only_hard_metrics_count=vendor_only_hard_metrics_count,
        order_materiality_missing_count=order_materiality_missing_count,
        technical_overweight_in_thesis_count=technical_overweight_in_thesis_count,
    )
    if unknown_or_low_confidence_archetype_count:
        manual_review_reasons.append(UNKNOWN_OR_LOW_CONFIDENCE_ARCHETYPE)
    if business_model_kpi_coverage_complete is False or business_model_kpi_gap_count:
        manual_review_reasons.append(BUSINESS_MODEL_KPI_COVERAGE_INCOMPLETE)
    if freshness_issue_code == STALE_PRICE_BASIS_FOR_CURRENT_REPORT:
        manual_review_reasons.append(STALE_PRICE_BASIS_FOR_CURRENT_REPORT)
    manual_review_reasons.extend(
        _audit_manual_review_reasons(
            audit_report=audit_report,
            validation_report=validation_report,
            reconciliation_warnings=reconciliation_warnings,
        )
    )
    coverage_review_reasons = {
        "missing_current_period_context": MISSING_CURRENT_PERIOD_KPI_CONTEXT,
        "missing_company_specific_analysis": MISSING_COMPANY_SPECIFIC_ANALYSIS,
        "missing_risk_analysis": MISSING_RISK_ANALYSIS,
    }
    for gap in coverage_gaps or []:
        reason = coverage_review_reasons.get(gap)
        if reason and reason not in manual_review_reasons:
            manual_review_reasons.append(reason)
    if manual_review_reasons:
        publishable = False
    data_confidence_score = _data_confidence_score(
        source_quality=category_scores["source_quality"],
        validation_report=validation_report,
        audit_report=audit_report,
        reconciliation_warnings=reconciliation_warnings,
        evidence_mapped_claim_ratio=evidence_mapped_claim_ratio,
        hard_claim_evidence_ratio=hard_claim_evidence_ratio,
        current_period_kpi_metric_count=current_period_kpi_metric_count,
        vendor_only_hard_metrics_count=vendor_only_hard_metrics_count,
        speculative_deep_tech_profile_count=speculative_deep_tech_profile_count,
        deeptech_sec_ir_current_period_evidence_complete=deeptech_sec_ir_current_period_evidence_complete,
        company_defined_fcf_mismatch_count=company_defined_fcf_mismatch_count,
        fcf_unavailable_block_count=fcf_unavailable_block_count,
        current_report_allowed=current_report_allowed,
        freshness_issue_code=freshness_issue_code,
    )
    internal_research_quality_score = _internal_research_quality_score(
        content_score=content_score,
        final_markdown=final_markdown,
        research_incomplete=research_incomplete,
        claim_coverage_complete=claim_coverage_complete,
        evidence_mapped_claim_ratio=evidence_mapped_claim_ratio,
        hard_claim_evidence_ratio=hard_claim_evidence_ratio,
        generic_claim_ratio=generic_claim_ratio,
        data_limitation_claim_count=data_limitation_claim_count,
        current_period_kpi_metric_count=current_period_kpi_metric_count,
        missing_current_period_context_count=missing_current_period_context_count,
        ticker_specific_kpi_claim_count=ticker_specific_kpi_claim_count,
        final_rating_rationale_quality=final_rating_rationale_quality,
        mechanical_rating_language_count=mechanical_rating_language_count,
        publish_mechanical_language_count=publish_mechanical_language_count,
        placeholder_business_context_count=placeholder_business_context_count,
        empty_required_section_count=empty_required_section_count,
        company_specific_claim_count=company_specific_claim_count,
        valuation_specific_claim_count=valuation_specific_claim_count,
        technical_specific_claim_count=technical_specific_claim_count,
        rating_rationale_claim_count=rating_rationale_claim_count,
        speculative_deep_tech_profile_count=speculative_deep_tech_profile_count,
        early_commercial_capital_intensive_tech_count=early_commercial_capital_intensive_tech_count,
        vendor_only_hard_metrics_count=vendor_only_hard_metrics_count,
        data_confidence_score=data_confidence_score,
        manual_review_reasons=manual_review_reasons,
        current_report_allowed=current_report_allowed,
        freshness_issue_code=freshness_issue_code,
    )
    score_explanation_short = _score_explanation_short(
        publishable=publishable,
        publish_quality_score=publish_quality_score,
        internal_research_quality_score=internal_research_quality_score,
        data_confidence_score=data_confidence_score,
        company_archetype=str(company_archetype or "UNKNOWN"),
        manual_review_reasons=manual_review_reasons,
        hard_claim_evidence_ratio=hard_claim_evidence_ratio,
        evidence_mapped_claim_ratio=evidence_mapped_claim_ratio,
        missing_current_period_context_count=missing_current_period_context_count,
        vendor_only_hard_metrics_count=vendor_only_hard_metrics_count,
        early_commercial_capital_intensive_tech_count=early_commercial_capital_intensive_tech_count,
        speculative_deep_tech_profile_count=speculative_deep_tech_profile_count,
        current_report_allowed=current_report_allowed,
        freshness_issue_code=freshness_issue_code,
    )
    return QualityReport(
        total_score=total,
        publish_quality_score=publish_quality_score,
        internal_research_quality_score=internal_research_quality_score,
        data_confidence_score=data_confidence_score,
        score_explanation_short=score_explanation_short,
        data_freshness_status=str(data_freshness_status or "not_evaluated"),
        stale_price_basis=int(stale_price_basis or 0),
        current_report_allowed=bool(current_report_allowed is not False),
        historical_qa_only=bool(historical_qa_only),
        freshness_issue_code=freshness_issue_code,
        content_score=_clamp(content_score, 100),
        generated_claim_mapping_complete=bool(claim_coverage_complete),
        generated_claim_mapping_gaps=coverage_gaps or [],
        claim_coverage_complete=bool(claim_coverage_complete),
        claim_coverage_gaps=coverage_gaps or [],
        analyst_claim_count=int(analyst_claim_count or 0),
        substantive_analyst_claim_count=int(substantive_analyst_claim_count or 0),
        substantive_claim_count=int(substantive_analyst_claim_count or 0),
        substantive_claim_ratio=float(substantive_claim_ratio if substantive_claim_ratio is not None else 0.0),
        generic_claim_count=int(generic_claim_count or 0),
        data_limitation_claim_count=int(data_limitation_claim_count or 0),
        current_period_kpi_claim_count=int(current_period_kpi_claim_count or 0),
        current_period_kpi_metric_count=int(current_period_kpi_metric_count or 0),
        current_period_kpi_claim_count_main_body=int(main_body_kpi_count or 0),
        current_kpi_appendix_only_count=int(appendix_only_kpi_count or 0),
        missing_current_period_context_count=int(missing_current_period_context_count or 0),
        ticker_specific_kpi_claim_count=int(ticker_specific_kpi_claim_count or 0),
        final_rating_rationale_quality=int(final_rating_rationale_quality or 0),
        mechanical_rating_language_count=int(mechanical_rating_language_count or 0),
        mechanical_rating_language_count_main_body=int(main_body_mechanical_count or 0),
        placeholder_business_context_count=int(placeholder_business_context_count or 0),
        empty_required_section_count=int(empty_required_section_count or 0),
        company_defined_fcf_used=int(company_defined_fcf_used or 0),
        sec_derived_fcf_used=int(sec_derived_fcf_used or 0),
        company_defined_fcf_mismatch_count=int(company_defined_fcf_mismatch_count or 0),
        fcf_unavailable_block_count=int(fcf_unavailable_block_count or 0),
        evidence_mapped_claim_ratio=float(evidence_mapped_claim_ratio if evidence_mapped_claim_ratio is not None else 0.0),
        hard_claim_evidence_ratio=float(hard_claim_evidence_ratio if hard_claim_evidence_ratio is not None else 0.0),
        generic_claim_ratio=float(generic_claim_ratio if generic_claim_ratio is not None else 0.0),
        company_specific_claim_count=int(company_specific_claim_count or 0),
        valuation_specific_claim_count=int(valuation_specific_claim_count or 0),
        technical_specific_claim_count=int(technical_specific_claim_count or 0),
        rating_rationale_claim_count=int(rating_rationale_claim_count or 0),
        risk_specific_claim_count=int(risk_specific_claim_count or 0),
        speculative_deep_tech_profile_count=int(speculative_deep_tech_profile_count or 0),
        accounting_gain_not_operating_turnaround_count=int(accounting_gain_not_operating_turnaround_count or 0),
        vendor_only_hard_metrics_count=int(vendor_only_hard_metrics_count or 0),
        order_materiality_missing_count=int(order_materiality_missing_count or 0),
        technical_overweight_in_thesis_count=int(technical_overweight_in_thesis_count or 0),
        early_commercial_capital_intensive_tech_count=int(early_commercial_capital_intensive_tech_count or 0),
        deeptech_sec_ir_current_period_evidence_complete=bool(deeptech_sec_ir_current_period_evidence_complete),
        deeptech_quality_score_cap=int(quality_cap or 0),
        risk_profiles=risk_profiles,
        manual_review_reasons=manual_review_reasons,
        external_display_rating=_manual_review_display_rating(manual_review_reasons),
        company_archetype=str(company_archetype or "UNKNOWN"),
        archetype_confidence=float(archetype_confidence or 0.0),
        archetype_triggered_rules=list(archetype_triggered_rules or []),
        business_model_kpi_coverage_complete=bool(
            business_model_kpi_coverage_complete is not False
        ),
        required_business_kpis=list(required_business_kpis or []),
        missing_business_kpis=list(missing_business_kpis or []),
        business_model_kpi_gap_count=int(business_model_kpi_gap_count or 0),
        unknown_or_low_confidence_archetype_count=int(
            unknown_or_low_confidence_archetype_count or 0
        ),
        publish_report_exists=int(publish_report_exists or 0),
        publish_report_quality_score=_publish_report_quality_score(
            publish_report_exists,
            publish_mechanical_language_count,
            publish_current_kpi_count,
            publish_evidence_appendix_exists,
            publish_claim_id_main_body_count,
            publish_valuation_sensitivity_present,
            publish_action_plan_trigger_count,
        ),
        publish_mechanical_language_count=int(publish_mechanical_language_count or 0),
        publish_current_kpi_count=int(publish_current_kpi_count or 0),
        publish_evidence_appendix_exists=int(publish_evidence_appendix_exists or 0),
        publish_claim_id_main_body_count=int(publish_claim_id_main_body_count or 0),
        publish_valuation_sensitivity_present=int(publish_valuation_sensitivity_present or 0),
        publish_action_plan_trigger_count=int(publish_action_plan_trigger_count or 0),
        fcf_ocf_inconsistency_count=int(fcf_ocf_inconsistency_count or 0),
        numerical_accuracy=category_scores["numerical_accuracy"],
        source_quality=category_scores["source_quality"],
        logic_consistency=category_scores["logic_consistency"],
        rating_discipline=category_scores["rating_discipline"],
        event_awareness=category_scores["event_awareness"],
        writing_structure=category_scores["writing_structure"],
        grade=_grade(total),
        status=_status(total),
        publishable=publishable,
    )


def is_publishable(
    total_score: int,
    validation_report: ValidationReport,
    audit_report: AuditReport,
    decision_packet: DecisionPacket,
    final_markdown: Optional[str] = None,
    analyst_claim_count: Optional[int] = None,
    evidence_mapped_claim_ratio: Optional[float] = None,
    hard_claim_evidence_ratio: Optional[float] = None,
    substantive_analyst_claim_count: Optional[int] = None,
    substantive_claim_ratio: Optional[float] = None,
    generic_claim_count: Optional[int] = None,
    generic_claim_ratio: Optional[float] = None,
    data_limitation_claim_count: Optional[int] = None,
    current_period_kpi_claim_count: Optional[int] = None,
    current_period_kpi_metric_count: Optional[int] = None,
    missing_current_period_context_count: Optional[int] = None,
    ticker_specific_kpi_claim_count: Optional[int] = None,
    final_rating_rationale_quality: Optional[int] = None,
    mechanical_rating_language_count: Optional[int] = None,
    company_defined_fcf_mismatch_count: Optional[int] = None,
    fcf_unavailable_block_count: Optional[int] = None,
    company_specific_claim_count: Optional[int] = None,
    valuation_specific_claim_count: Optional[int] = None,
    technical_specific_claim_count: Optional[int] = None,
    rating_rationale_claim_count: Optional[int] = None,
    risk_specific_claim_count: Optional[int] = None,
    publish_report_exists: Optional[int] = None,
    publish_mechanical_language_count: Optional[int] = None,
    publish_current_kpi_count: Optional[int] = None,
    publish_evidence_appendix_exists: Optional[int] = None,
    publish_claim_id_main_body_count: Optional[int] = None,
    publish_valuation_sensitivity_present: Optional[int] = None,
    publish_action_plan_trigger_count: Optional[int] = None,
    fcf_ocf_inconsistency_count: Optional[int] = None,
    speculative_deep_tech_profile_count: Optional[int] = None,
    early_commercial_capital_intensive_tech_count: Optional[int] = None,
    vendor_only_hard_metrics_count: Optional[int] = None,
    deeptech_sec_ir_current_period_evidence_complete: Optional[bool] = None,
    current_report_allowed: Optional[bool] = None,
    freshness_issue_code: Optional[str] = None,
    claim_coverage_complete: Optional[bool] = None,
) -> bool:
    strict_content_v2 = any(
        value is not None
        for value in {
            substantive_claim_ratio,
            data_limitation_claim_count,
            current_period_kpi_claim_count,
            ticker_specific_kpi_claim_count,
            final_rating_rationale_quality,
            mechanical_rating_language_count,
        }
    )
    if current_report_allowed is False and freshness_issue_code == STALE_PRICE_BASIS_FOR_CURRENT_REPORT:
        return False
    if total_score < 85:
        return False
    if _is_research_incomplete(final_markdown, analyst_claim_count):
        return False
    if claim_coverage_complete is False:
        return False
    if substantive_claim_ratio is None and analyst_claim_count:
        substantive_claim_ratio = (substantive_analyst_claim_count or 0) / analyst_claim_count
    if strict_content_v2 and substantive_claim_ratio is not None and substantive_claim_ratio < 0.70:
        return False
    if generic_claim_ratio is not None and generic_claim_ratio > 0.50:
        return False
    if data_limitation_claim_count is not None and analyst_claim_count:
        if data_limitation_claim_count / max(analyst_claim_count, 1) > 0.25:
            return False
    if missing_current_period_context_count:
        return False
    if current_period_kpi_metric_count is not None and current_period_kpi_metric_count < 3:
        return False
    if final_rating_rationale_quality is not None and final_rating_rationale_quality < 50:
        return False
    if mechanical_rating_language_count:
        return False
    if publish_report_exists is not None:
        if not publish_report_exists:
            return False
        if not publish_evidence_appendix_exists:
            return False
        if publish_current_kpi_count is not None and publish_current_kpi_count < 3:
            return False
        if publish_mechanical_language_count:
            return False
        if publish_claim_id_main_body_count:
            return False
        if publish_valuation_sensitivity_present is not None and not publish_valuation_sensitivity_present:
            return False
        if publish_action_plan_trigger_count is not None and publish_action_plan_trigger_count < 2:
            return False
    if final_markdown and _count_placeholder_business_context(final_markdown):
        return False
    if company_defined_fcf_mismatch_count:
        return False
    if fcf_unavailable_block_count:
        return False
    if company_specific_claim_count is not None and company_specific_claim_count < 1:
        return False
    if valuation_specific_claim_count is not None and valuation_specific_claim_count < 1:
        return False
    if technical_specific_claim_count is not None and technical_specific_claim_count < 1:
        return False
    if rating_rationale_claim_count is not None and rating_rationale_claim_count < 1:
        return False
    if risk_specific_claim_count is not None and risk_specific_claim_count < 1:
        return False
    if speculative_deep_tech_profile_count and not deeptech_sec_ir_current_period_evidence_complete:
        return False
    if early_commercial_capital_intensive_tech_count:
        return False
    if vendor_only_hard_metrics_count:
        return False
    if evidence_mapped_claim_ratio is not None and evidence_mapped_claim_ratio < 0.90:
        return False
    if hard_claim_evidence_ratio is not None and hard_claim_evidence_ratio < 1.0:
        return False
    if validation_report.has_blocking_errors or audit_report.has_blocking_errors:
        return False
    if decision_packet.rating_permission.preferred_rating not in decision_packet.rating_permission.allowed_ratings:
        return False
    if final_markdown:
        final_rating = extract_rating_from_text(final_markdown)
        if final_rating and final_rating in decision_packet.rating_permission.blocked_ratings:
            return False
    return True


def _deeptech_quality_cap(
    *,
    speculative_deep_tech_profile_count: Optional[int],
    accounting_gain_not_operating_turnaround_count: Optional[int],
    vendor_only_hard_metrics_count: Optional[int],
    order_materiality_missing_count: Optional[int],
    early_commercial_capital_intensive_tech_count: Optional[int],
    deeptech_sec_ir_current_period_evidence_complete: Optional[bool],
) -> Optional[int]:
    caps: list[int] = []
    if speculative_deep_tech_profile_count and not deeptech_sec_ir_current_period_evidence_complete:
        caps.append(75)
    if accounting_gain_not_operating_turnaround_count:
        caps.append(70)
    if order_materiality_missing_count:
        caps.append(80)
    if vendor_only_hard_metrics_count:
        caps.append(75)
    if early_commercial_capital_intensive_tech_count:
        caps.append(84)
    return min(caps) if caps else None


def _deeptech_manual_review_reasons(
    *,
    speculative_deep_tech_profile_count: Optional[int],
    early_commercial_capital_intensive_tech_count: Optional[int],
    accounting_gain_not_operating_turnaround_count: Optional[int],
    vendor_only_hard_metrics_count: Optional[int],
    order_materiality_missing_count: Optional[int],
    technical_overweight_in_thesis_count: Optional[int],
) -> list[str]:
    reasons: list[str] = []
    if speculative_deep_tech_profile_count:
        reasons.append(SPECULATIVE_DEEP_TECH_MANUAL_REVIEW_PROFILE)
    if early_commercial_capital_intensive_tech_count:
        reasons.append(EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH_MANUAL_REVIEW_PROFILE)
    if vendor_only_hard_metrics_count:
        reasons.append(VENDOR_ONLY_HARD_METRICS)
    if accounting_gain_not_operating_turnaround_count:
        reasons.append(ACCOUNTING_GAIN_NOT_OPERATING_TURNAROUND)
    if order_materiality_missing_count:
        reasons.append(ORDER_MATERIALITY_MISSING)
    if technical_overweight_in_thesis_count:
        reasons.append(TECHNICAL_OVERWEIGHT_IN_FUNDAMENTAL_THESIS)
    return reasons


def _audit_manual_review_reasons(
    *,
    audit_report: AuditReport,
    validation_report: ValidationReport,
    reconciliation_warnings: Optional[list[dict]],
) -> list[str]:
    reasons: list[str] = []
    audit_reason_codes = {
        MISSING_FCF_SUPPORT_FOR_ACCUMULATE,
        "FCF_UNAVAILABLE_WITHOUT_IR_SUPPORT",
        "TRUE_FINANCIAL_ANOMALY",
        "EXTREME_VALUATION_REQUIRES_REVIEW",
        "TRUE_VALUATION_ANOMALY",
        "PERIOD_DENOMINATOR_BUG",
        "CURRENT_PERIOD_IR_RECONCILIATION_REQUIRED",
        "COMPANY_DEFINED_FCF_MISMATCH",
        "COMPANY_DEFINED_FCF_OCF_INCONSISTENCY",
        "GUARD_THRESHOLD_REVIEW",
        "PER_SHARE_BASIS_MISMATCH_EXCLUDED",
        "INSURER_OPERATING_KPI_CONTEXT_REQUIRED",
    }
    validation_reason_codes = {
        "EARNINGS_DATE_UNAVAILABLE",
        "EARNINGS_DATE_UNCONFIRMED",
        "PRICE_DATE_BEFORE_AS_OF_DATE",
    }
    reconciliation_reason_codes = {
        BALANCE_SHEET_DATE_MISMATCH_EXCLUDED,
        SEC_OPERATING_INCOME_CONTEXT_MISMATCH_EXCLUDED,
        "MULTI_CLASS_PRICE_BASIS_UNAVAILABLE",
        "TRUE_SOURCE_VALUE_DISAGREEMENT",
        "SOURCE_FRAME_VARIANT_IGNORED",
        "PERIOD_TYPE_MISMATCH_IGNORED",
        "PER_SHARE_BASIS_MISMATCH_EXCLUDED",
    }
    for issue in audit_report.issues:
        if issue.code in audit_reason_codes and issue.code not in reasons:
            reasons.append(issue.code)
    for issue in validation_report.issues:
        if issue.code in validation_reason_codes and issue.code not in reasons:
            reasons.append(issue.code)
    for warning in reconciliation_warnings or []:
        code = str(warning.get("code") or "")
        if code in reconciliation_reason_codes and code not in reasons:
            reasons.append(code)
    return reasons


def _manual_review_display_rating(reasons: list[str]) -> Optional[str]:
    if MISSING_FCF_SUPPORT_FOR_ACCUMULATE in reasons or "FCF_UNAVAILABLE_WITHOUT_IR_SUPPORT" in reasons:
        return HOLD_PENDING_FCF_SUPPORT_DISPLAY_RATING
    if EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH_MANUAL_REVIEW_PROFILE in reasons:
        return EARLY_COMMERCIAL_CAPITAL_INTENSIVE_DISPLAY_RATING
    if SPECULATIVE_DEEP_TECH_MANUAL_REVIEW_PROFILE in reasons:
        return MANUAL_REVIEW_DISPLAY_RATING
    if EVIDENCE_INCOMPLETE_FOR_GOLD in reasons:
        return MANUAL_REVIEW_EVIDENCE_INCOMPLETE_DISPLAY_RATING
    return None


def save_quality_report(report: QualityReport, path: Union[str, Path]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = report.model_dump(mode="json") if hasattr(report, "model_dump") else report.dict()
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return target


def _clamp(value: int, maximum: int) -> int:
    return max(0, min(maximum, value))


def _grade(total: int) -> str:
    if total >= 95:
        return "A"
    if total >= 90:
        return "A-"
    if total >= 85:
        return "B+"
    if total >= 75:
        return "B"
    if total >= 60:
        return "C"
    return "F"


def _status(total: int) -> str:
    if total >= 90:
        return "Publishable"
    if total >= 85:
        return "Publishable with minor warnings"
    if total >= 75:
        return "Internal only"
    if total >= 60:
        return "Needs manual review"
    return "Reject"


DATA_CONFIDENCE_ISSUE_CODES = {
    "MISSING_EVIDENCE_FOR_HARD_CLAIM",
    "VENDOR_SOURCE_USED_AS_PRIMARY",
    "LOW_AUTHORITY_EVIDENCE_FOR_HARD_CLAIM",
    "UNSUPPORTED_GUIDANCE_CLAIM",
    "UNSUPPORTED_EARNINGS_EVENT_CLAIM",
    "GUIDANCE_CONSENSUS_CONFLATION",
    "FCF_UNAVAILABLE_WITHOUT_IR_SUPPORT",
    "MISSING_CURRENT_PERIOD_CONTEXT",
    "MISSING_CURRENT_PERIOD_KPI_CONTEXT",
    "AVGO_CURRENT_KPI_CONTEXT_REQUIRED",
    "COMPANY_DEFINED_FCF_MISMATCH",
    "CURRENT_PERIOD_IR_RECONCILIATION_REQUIRED",
    "PERIOD_DENOMINATOR_BUG",
}


def _publish_quality_score(
    *,
    total_score: int,
    audit_report: AuditReport,
    evidence_mapped_claim_ratio: Optional[float],
    hard_claim_evidence_ratio: Optional[float],
    missing_current_period_context_count: Optional[int],
    speculative_deep_tech_profile_count: Optional[int],
    early_commercial_capital_intensive_tech_count: Optional[int],
    vendor_only_hard_metrics_count: Optional[int],
    fcf_unavailable_block_count: Optional[int],
    company_defined_fcf_mismatch_count: Optional[int],
    current_report_allowed: Optional[bool] = None,
    freshness_issue_code: Optional[str] = None,
) -> int:
    score = int(total_score)
    if current_report_allowed is False and freshness_issue_code == STALE_PRICE_BASIS_FOR_CURRENT_REPORT:
        score = min(score, 70)
    if early_commercial_capital_intensive_tech_count:
        score = min(score, 70)
    if speculative_deep_tech_profile_count:
        score = min(score, 70)
    if vendor_only_hard_metrics_count:
        score = min(score, 68)
    if missing_current_period_context_count:
        score = min(score, 72)
    if fcf_unavailable_block_count:
        score = min(score, 70)
    if company_defined_fcf_mismatch_count:
        score = min(score, 60)
    if evidence_mapped_claim_ratio is not None and evidence_mapped_claim_ratio < 0.90:
        score = min(score, 65)
    if hard_claim_evidence_ratio is not None and hard_claim_evidence_ratio < 1.0:
        score = min(score, 60)
    if any(issue.code == "MISSING_EVIDENCE_FOR_HARD_CLAIM" for issue in audit_report.issues):
        score = min(score, 55)
    return _clamp(score, 100)


def _data_confidence_score(
    *,
    source_quality: int,
    validation_report: ValidationReport,
    audit_report: AuditReport,
    reconciliation_warnings: Optional[list[dict]],
    evidence_mapped_claim_ratio: Optional[float],
    hard_claim_evidence_ratio: Optional[float],
    current_period_kpi_metric_count: Optional[int],
    vendor_only_hard_metrics_count: Optional[int],
    speculative_deep_tech_profile_count: Optional[int],
    deeptech_sec_ir_current_period_evidence_complete: Optional[bool],
    company_defined_fcf_mismatch_count: Optional[int],
    fcf_unavailable_block_count: Optional[int],
    current_report_allowed: Optional[bool] = None,
    freshness_issue_code: Optional[str] = None,
) -> int:
    source_component = int(round((source_quality / 20) * 100))
    score = 55 + int(round((source_component - 50) * 0.5))
    if evidence_mapped_claim_ratio is not None and evidence_mapped_claim_ratio >= 0.90:
        score += 3
    if hard_claim_evidence_ratio is not None and hard_claim_evidence_ratio >= 1.0:
        score += 3
    if current_period_kpi_metric_count is not None and current_period_kpi_metric_count >= 3:
        score += 3
    if deeptech_sec_ir_current_period_evidence_complete:
        score += 3

    if evidence_mapped_claim_ratio is not None and evidence_mapped_claim_ratio < 0.90:
        score -= min(25, int(round((0.90 - evidence_mapped_claim_ratio) * 40)))
    if hard_claim_evidence_ratio is not None and hard_claim_evidence_ratio < 1.0:
        score -= min(35, int(round((1.0 - hard_claim_evidence_ratio) * 45)))

    data_issue_count = sum(1 for issue in audit_report.issues if issue.code in DATA_CONFIDENCE_ISSUE_CODES)
    score -= min(30, data_issue_count * 8)
    if validation_report.has_blocking_errors:
        score -= 18
    score -= min(10, sum(1 for issue in validation_report.issues if issue.severity == "warning") * 2)

    true_source_disagreement_count = 0
    balance_sheet_mismatch_count = 0
    operating_income_context_mismatch_count = 0
    for warning in reconciliation_warnings or []:
        if warning.get("code") == "TRUE_SOURCE_VALUE_DISAGREEMENT":
            true_source_disagreement_count += int(warning.get("count") or 1)
        elif warning.get("code") == BALANCE_SHEET_DATE_MISMATCH_EXCLUDED:
            balance_sheet_mismatch_count += 1
        elif warning.get("code") == SEC_OPERATING_INCOME_CONTEXT_MISMATCH_EXCLUDED:
            operating_income_context_mismatch_count += 1
    score -= min(10, true_source_disagreement_count * 2)
    score -= min(8, balance_sheet_mismatch_count * 2)
    score -= min(8, operating_income_context_mismatch_count * 4)

    if vendor_only_hard_metrics_count:
        score -= 6
    if speculative_deep_tech_profile_count and not deeptech_sec_ir_current_period_evidence_complete:
        score -= 4
    if company_defined_fcf_mismatch_count:
        score -= 12
    if fcf_unavailable_block_count:
        score -= 10
    if current_report_allowed is False and freshness_issue_code == STALE_PRICE_BASIS_FOR_CURRENT_REPORT:
        score -= 8

    if vendor_only_hard_metrics_count and (evidence_mapped_claim_ratio or 0) >= 0.90 and (hard_claim_evidence_ratio or 0) >= 1.0:
        score = max(score, 55)
    return _clamp(score, 100)


def _internal_research_quality_score(
    *,
    content_score: int,
    final_markdown: Optional[str],
    research_incomplete: bool,
    claim_coverage_complete: Optional[bool],
    evidence_mapped_claim_ratio: Optional[float],
    hard_claim_evidence_ratio: Optional[float],
    generic_claim_ratio: Optional[float],
    data_limitation_claim_count: Optional[int],
    current_period_kpi_metric_count: Optional[int],
    missing_current_period_context_count: Optional[int],
    ticker_specific_kpi_claim_count: Optional[int],
    final_rating_rationale_quality: Optional[int],
    mechanical_rating_language_count: Optional[int],
    publish_mechanical_language_count: Optional[int],
    placeholder_business_context_count: int,
    empty_required_section_count: int,
    company_specific_claim_count: Optional[int],
    valuation_specific_claim_count: Optional[int],
    technical_specific_claim_count: Optional[int],
    rating_rationale_claim_count: Optional[int],
    speculative_deep_tech_profile_count: Optional[int],
    early_commercial_capital_intensive_tech_count: Optional[int],
    vendor_only_hard_metrics_count: Optional[int],
    data_confidence_score: int,
    manual_review_reasons: list[str],
    current_report_allowed: Optional[bool] = None,
    freshness_issue_code: Optional[str] = None,
) -> int:
    score = 50
    score += 5 if not research_incomplete else -20
    if claim_coverage_complete is True:
        score += 12
    elif claim_coverage_complete is False:
        score -= 10
    if current_period_kpi_metric_count is not None and current_period_kpi_metric_count >= 3:
        score += 5
    if ticker_specific_kpi_claim_count is not None and ticker_specific_kpi_claim_count >= 3:
        score += 5
    if company_specific_claim_count:
        score += 4
    if valuation_specific_claim_count:
        score += 3
    if technical_specific_claim_count:
        score += 2
    if rating_rationale_claim_count:
        score += 4
    if final_rating_rationale_quality is not None:
        if final_rating_rationale_quality >= 70:
            score += 6
        elif final_rating_rationale_quality < 50:
            score -= 8
    if mechanical_rating_language_count:
        score -= min(15, mechanical_rating_language_count * 5)
    else:
        score += 4
    if publish_mechanical_language_count:
        score -= min(10, publish_mechanical_language_count * 4)
    else:
        score += 2
    if placeholder_business_context_count:
        score -= 8
    else:
        score += 3
    if empty_required_section_count:
        score -= min(20, empty_required_section_count * 5)
        score = min(score, 70 if empty_required_section_count >= 3 else 75)
    if generic_claim_ratio is not None and generic_claim_ratio > 0.50:
        score -= 12
    if data_limitation_claim_count:
        score += 3
    if missing_current_period_context_count:
        score -= min(12, missing_current_period_context_count * 4)
    if final_markdown:
        lower = _main_body(final_markdown).lower()
        if "follow-up checklist" in lower or "action plan" in lower or "what would improve" in lower:
            score += 4
        if "manual review" in lower or "further review" in lower:
            score += 2
        if "risk" in lower or "risiko" in lower:
            score += 2
    if content_score >= 80:
        score += 4
    elif content_score < 60:
        score -= 8

    if evidence_mapped_claim_ratio is not None and evidence_mapped_claim_ratio < 0.90:
        score -= 8
    if hard_claim_evidence_ratio is not None and hard_claim_evidence_ratio < 1.0:
        score -= 10
        score = min(score, 70)
    if data_confidence_score < 50 and not vendor_only_hard_metrics_count and not data_limitation_claim_count:
        score = min(score, 65)
    if data_confidence_score < 60:
        score = min(score, 85)
    if data_confidence_score < 70:
        score = min(score, 88)
    if _has_manual_review_evidence_or_sanity_reason(manual_review_reasons):
        score = min(score, 90)
    if MISSING_FCF_SUPPORT_FOR_ACCUMULATE in manual_review_reasons or "FCF_UNAVAILABLE_WITHOUT_IR_SUPPORT" in manual_review_reasons:
        score = min(score, 85)
    if "TRUE_SOURCE_VALUE_DISAGREEMENT" in manual_review_reasons:
        score = min(score, 85)
    if "CURRENT_PERIOD_IR_RECONCILIATION_REQUIRED" in manual_review_reasons:
        score = min(score, 85)
    if research_incomplete:
        score = min(score, 45)
    if early_commercial_capital_intensive_tech_count:
        if claim_coverage_complete and (hard_claim_evidence_ratio or 0) >= 1.0:
            score = max(score, 76)
        score = min(score, 80)
    if speculative_deep_tech_profile_count:
        if claim_coverage_complete:
            score = max(score, 78)
        score = min(score, 85)
    if vendor_only_hard_metrics_count:
        score = min(score, 85)
    if current_report_allowed is False and freshness_issue_code == STALE_PRICE_BASIS_FOR_CURRENT_REPORT:
        score = min(score, 75)
    if manual_review_reasons and score < 70 and claim_coverage_complete and (hard_claim_evidence_ratio or 0) >= 1.0:
        score = 70
    if empty_required_section_count:
        score = min(score, 70 if empty_required_section_count >= 3 else 75)
    return _clamp(score, 100)


def _has_manual_review_evidence_or_sanity_reason(manual_review_reasons: list[str]) -> bool:
    cap_reasons = {
        BALANCE_SHEET_DATE_MISMATCH_EXCLUDED,
        SEC_OPERATING_INCOME_CONTEXT_MISMATCH_EXCLUDED,
        "TRUE_SOURCE_VALUE_DISAGREEMENT",
        "SOURCE_FRAME_VARIANT_IGNORED",
        "PERIOD_TYPE_MISMATCH_IGNORED",
        "FCF_UNAVAILABLE_WITHOUT_IR_SUPPORT",
        MISSING_FCF_SUPPORT_FOR_ACCUMULATE,
        "TRUE_FINANCIAL_ANOMALY",
        "EXTREME_VALUATION_REQUIRES_REVIEW",
        "TRUE_VALUATION_ANOMALY",
        "PERIOD_DENOMINATOR_BUG",
        "CURRENT_PERIOD_IR_RECONCILIATION_REQUIRED",
        "COMPANY_DEFINED_FCF_MISMATCH",
        "COMPANY_DEFINED_FCF_OCF_INCONSISTENCY",
        "EARNINGS_DATE_UNAVAILABLE",
        "EARNINGS_DATE_UNCONFIRMED",
        "PER_SHARE_BASIS_MISMATCH_EXCLUDED",
    }
    return any(reason in cap_reasons for reason in manual_review_reasons)


def _score_explanation_short(
    *,
    publishable: bool,
    publish_quality_score: int,
    internal_research_quality_score: int,
    data_confidence_score: int,
    company_archetype: str,
    manual_review_reasons: list[str],
    hard_claim_evidence_ratio: Optional[float],
    evidence_mapped_claim_ratio: Optional[float],
    missing_current_period_context_count: Optional[int],
    vendor_only_hard_metrics_count: Optional[int],
    early_commercial_capital_intensive_tech_count: Optional[int],
    speculative_deep_tech_profile_count: Optional[int],
    current_report_allowed: Optional[bool] = None,
    freshness_issue_code: Optional[str] = None,
) -> str:
    if current_report_allowed is False and freshness_issue_code == STALE_PRICE_BASIS_FOR_CURRENT_REPORT:
        return "Not current-report eligible because the price basis is stale; use only as historical QA until fresh prices are ingested."
    if early_commercial_capital_intensive_tech_count:
        return (
            "Manual review due to negative FCF and extreme valuation; internal report is usable because "
            "backlog, revenue scale, FCF path and execution risks are clearly explained."
        )
    if speculative_deep_tech_profile_count:
        if vendor_only_hard_metrics_count:
            return (
                "Not publishable because hard metrics are vendor-heavy and the archetype requires manual review; "
                "internal report is useful as a speculative deep-tech risk note."
            )
        return "Manual-review speculative deep-tech profile; internal usefulness depends on clearly marked risks and follow-up evidence."
    if publishable and publish_quality_score >= 85 and internal_research_quality_score >= 85:
        return "Gold-v1 report with current-period KPIs, evidence support and coherent rating logic."
    if (hard_claim_evidence_ratio is not None and hard_claim_evidence_ratio < 1.0) or (
        evidence_mapped_claim_ratio is not None and evidence_mapped_claim_ratio < 0.90
    ):
        return "Readable text is not enough for publication because evidence coverage or hard-claim support is incomplete."
    if missing_current_period_context_count:
        return "Manual review because current-period context is incomplete; internal use depends on follow-up evidence."
    if data_confidence_score >= 80 and internal_research_quality_score < 75:
        return "Data support is stronger than the writing; improve thesis clarity, risks and action logic before publication."
    if manual_review_reasons:
        return "Manual-review report; publish quality is gated while internal usefulness depends on the marked follow-up work."
    if company_archetype and company_archetype != "UNKNOWN":
        return "Report score split reflects separate publication readiness, internal research usefulness and data confidence."
    return "Score split reflects separate publication readiness, internal research usefulness and data confidence."


def _publish_report_quality_score(
    exists: Optional[int],
    mechanical_count: Optional[int],
    current_kpi_count: Optional[int],
    appendix_exists: Optional[int],
    claim_id_count: Optional[int],
    valuation_sensitivity_present: Optional[int] = None,
    action_plan_trigger_count: Optional[int] = None,
) -> int:
    if exists is None:
        return 0
    score = 100 if exists else 0
    if not appendix_exists:
        score -= 20
    if current_kpi_count is not None and current_kpi_count < 3:
        score -= 20
    if valuation_sensitivity_present is not None and not valuation_sensitivity_present:
        score -= 20
    if action_plan_trigger_count is not None and action_plan_trigger_count < 2:
        score -= 15
    score -= min(30, int(mechanical_count or 0) * 10)
    score -= min(20, int(claim_id_count or 0) * 5)
    return max(0, min(100, score))


MAIN_BODY_MECHANICAL_PHRASES = {
    "validated packet",
    "rating corridor",
    "committee anchor",
    "decisionpacket",
    "business context is intentionally grounded",
    "segment-specific interpretation should only be expanded",
    "committee text",
    "unconstrained model preference",
    "fundamental score, technical score and risk score",
}

CURRENT_PERIOD_TERMS = {
    "q1", "q2", "q3", "q4", "latest quarter", "latest-quarter",
    "current-period", "fy2026", "fy2027", "guide", "guidance",
}

TICKER_KPI_TERMS = {
    "google cloud", "cloud revenue", "product revenue", "rpo", "nrr",
    "net revenue retention", "customers above", "customers >",
    "adjusted fcf", "adjusted free cash flow", "capex", "other income",
    "operating margin", "ai revenue", "azure", "microsoft cloud",
    "intelligent cloud", "family of apps", "reality labs", "services revenue",
    "iphone", "operating income", "free cash flow", "fcf",
    "revenue", "eps", "operating cash flow", "buyback", "guidance",
    "backlog", "contract backlog", "contracted missions", "launch manifest",
    "electron", "haste", "launch cadence", "neutron", "space systems",
    "launch services", "service revenue", "capital intensity", "execution milestone",
}


def _main_body(markdown: str) -> str:
    lower = markdown.lower()
    marker = lower.find("## evidence appendix")
    if marker == -1:
        return markdown
    return markdown[:marker]


def _count_main_body_current_period_kpi_claims(markdown: str) -> int:
    main = _main_body(markdown)
    count = 0
    for line in main.splitlines():
        lower = line.lower()
        if not any(char.isdigit() for char in line):
            continue
        if not any(term in lower for term in CURRENT_PERIOD_TERMS):
            continue
        if not any(term in lower for term in TICKER_KPI_TERMS):
            continue
        count += 1
    return count


def _count_main_body_mechanical_language(markdown: str) -> int:
    lower = _main_body(markdown).lower()
    return sum(1 for phrase in MAIN_BODY_MECHANICAL_PHRASES if phrase in lower)


def _count_placeholder_business_context(markdown: str) -> int:
    lower = _main_body(markdown).lower()
    return int(
        "business context is intentionally grounded" in lower
        or "segment-specific interpretation should only be expanded" in lower
    )


REQUIRED_REPORT_SECTIONS = {
    "executive summary": ["executive summary", "kurzfazit"],
    "investment thesis": ["investment thesis", "investment-these", "investment these"],
    "key bull points": ["key bull points", "bull points", "bull case", "positive punkte"],
    "key bear points": ["key bear points", "bear points", "bear case", "risiken/gegenargumente"],
    "valuation / multiples": ["valuation", "multiples", "bewertung", "kgv"],
    "technical setup": ["technical setup", "technisches setup", "technik"],
    "risk section": ["risk section", "risiken", "risk"],
    "scenario / triggers": ["scenario", "szenario", "triggers", "trigger"],
    "final rating and action": ["final rating", "rating and action", "finale einschätzung", "operative action"],
}

EARLY_COMMERCIAL_REQUIRED_SECTIONS = [
    "business model reality",
    "revenue scale and backlog",
    "contract / backlog materiality",
    "segment mix",
    "execution milestones",
    "fcf path",
    "capital intensity",
    "valuation vs revenue/backlog",
    "technical setup as timing only",
    "final internal view",
]

SPECULATIVE_DEEP_TECH_REQUIRED_SECTIONS = [
    "business model reality",
    "commercial adoption",
    "contract / order materiality",
    "cash burn and dilution",
    "milestone risk",
    "valuation reality",
    "final internal view",
]

EMPTY_SECTION_MARKERS = (
    "no evidence-backed discussion is available for this section",
    "no evidence-backed claim is available for this section",
    "no evidence available",
)


def _is_research_incomplete(markdown: Optional[str], analyst_claim_count: Optional[int]) -> bool:
    if analyst_claim_count == 0:
        return True
    if not markdown:
        return False
    return "no llm claims attached" in markdown.lower()


def _missing_required_sections(markdown: str) -> list[str]:
    lower = markdown.lower()
    return [
        section
        for section, aliases in REQUIRED_REPORT_SECTIONS.items()
        if not any(alias in lower for alias in aliases)
    ]


def _empty_required_archetype_section_count(
    markdown: Optional[str],
    *,
    company_archetype: Optional[str],
    speculative_deep_tech_profile_count: Optional[int],
    early_commercial_capital_intensive_tech_count: Optional[int],
) -> int:
    if not markdown:
        return 0
    archetype = str(company_archetype or "").upper()
    if early_commercial_capital_intensive_tech_count or archetype == "EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH":
        required_sections = EARLY_COMMERCIAL_REQUIRED_SECTIONS
    elif speculative_deep_tech_profile_count or archetype == "SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL":
        required_sections = SPECULATIVE_DEEP_TECH_REQUIRED_SECTIONS
    else:
        return 0

    empty_count = 0
    for section in required_sections:
        body = _section_body(markdown, section)
        if body is not None and _section_body_is_empty(body):
            empty_count += 1
    return empty_count


def count_empty_required_archetype_sections(
    markdown: Optional[str],
    *,
    company_archetype: Optional[str],
    speculative_deep_tech_profile_count: Optional[int] = None,
    early_commercial_capital_intensive_tech_count: Optional[int] = None,
) -> int:
    return _empty_required_archetype_section_count(
        markdown,
        company_archetype=company_archetype,
        speculative_deep_tech_profile_count=speculative_deep_tech_profile_count,
        early_commercial_capital_intensive_tech_count=early_commercial_capital_intensive_tech_count,
    )


def _section_body(markdown: str, heading: str) -> Optional[str]:
    lines = markdown.splitlines()
    target = heading.strip().lower()
    collecting = False
    body: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            normalized = stripped.lstrip("#").strip().lower()
            if collecting:
                break
            if normalized == target:
                collecting = True
            continue
        if collecting:
            body.append(stripped)
    if not collecting:
        return None
    return "\n".join(body).strip()


def _section_body_is_empty(body: str) -> bool:
    normalized = " ".join(line.strip().lower() for line in body.splitlines() if line.strip())
    if not normalized:
        return True
    if any(marker in normalized for marker in EMPTY_SECTION_MARKERS):
        return True
    return False
