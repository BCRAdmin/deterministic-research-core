from typing import Optional

from pydantic import BaseModel, Field


class QualityReport(BaseModel):
    total_score: int
    publish_quality_score: int = 0
    internal_research_quality_score: int = 0
    data_confidence_score: int = 0
    score_explanation_short: str = ""
    data_freshness_status: str = "not_evaluated"
    stale_price_basis: int = 0
    current_report_allowed: bool = True
    historical_qa_only: bool = False
    freshness_issue_code: Optional[str] = None
    content_score: int = 100
    generated_claim_mapping_complete: bool = False
    generated_claim_mapping_gaps: list[str] = Field(default_factory=list)
    source_inventory_complete: bool = False
    material_event_content_complete: bool = False
    unit_normalization_valid: bool = False
    analyst_claim_count: int = 0
    substantive_analyst_claim_count: int = 0
    substantive_claim_count: int = 0
    substantive_claim_ratio: float = 0.0
    generic_claim_count: int = 0
    data_limitation_claim_count: int = 0
    current_period_kpi_claim_count: int = 0
    current_period_kpi_metric_count: int = 0
    current_period_kpi_claim_count_main_body: int = 0
    current_kpi_appendix_only_count: int = 0
    missing_current_period_context_count: int = 0
    ticker_specific_kpi_claim_count: int = 0
    final_rating_rationale_quality: int = 0
    mechanical_rating_language_count: int = 0
    mechanical_rating_language_count_main_body: int = 0
    placeholder_business_context_count: int = 0
    empty_required_section_count: int = 0
    publish_report_exists: int = 0
    publish_report_quality_score: int = 0
    publish_mechanical_language_count: int = 0
    publish_current_kpi_count: int = 0
    canonical_current_kpi_count: int = 0
    canonical_risk_profile_count: int = 0
    canonical_data_limitation_count: int = 0
    publication_artifact_state: str = "not_evaluated"
    quality_metadata_consistent: bool = False
    publish_evidence_appendix_exists: int = 0
    publish_claim_id_main_body_count: int = 0
    publish_valuation_sensitivity_present: int = 0
    publish_action_plan_trigger_count: int = 0
    fcf_ocf_inconsistency_count: int = 0
    company_defined_fcf_used: int = 0
    sec_derived_fcf_used: int = 0
    company_defined_fcf_mismatch_count: int = 0
    company_defined_fcf_definition_difference_count: int = 0
    company_defined_fcf_unresolved_mismatch_count: int = 0
    fcf_unavailable_block_count: int = 0
    evidence_mapped_claim_ratio: float = 0.0
    hard_claim_evidence_ratio: float = 0.0
    generic_claim_ratio: float = 0.0
    company_specific_claim_count: int = 0
    valuation_specific_claim_count: int = 0
    technical_specific_claim_count: int = 0
    rating_rationale_claim_count: int = 0
    risk_specific_claim_count: int = 0
    speculative_deep_tech_profile_count: int = 0
    accounting_gain_not_operating_turnaround_count: int = 0
    vendor_only_hard_metrics_count: int = 0
    order_materiality_missing_count: int = 0
    technical_overweight_in_thesis_count: int = 0
    early_commercial_capital_intensive_tech_count: int = 0
    deeptech_sec_ir_current_period_evidence_complete: bool = False
    deeptech_quality_score_cap: int = 0
    risk_profiles: list[str] = Field(default_factory=list)
    manual_review_reasons: list[str] = Field(default_factory=list)
    external_display_rating: Optional[str] = None
    company_archetype: str = "UNKNOWN"
    archetype_confidence: float = 0.0
    archetype_triggered_rules: list[str] = Field(default_factory=list)
    business_model_kpi_coverage_complete: bool = True
    required_business_kpis: list[str] = Field(default_factory=list)
    missing_business_kpis: list[str] = Field(default_factory=list)
    business_model_kpi_gap_count: int = 0
    unknown_or_low_confidence_archetype_count: int = 0
    numerical_accuracy: int
    source_quality: int
    logic_consistency: int
    rating_discipline: int
    event_awareness: int
    writing_structure: int
    grade: str
    status: str
    publishable: bool
