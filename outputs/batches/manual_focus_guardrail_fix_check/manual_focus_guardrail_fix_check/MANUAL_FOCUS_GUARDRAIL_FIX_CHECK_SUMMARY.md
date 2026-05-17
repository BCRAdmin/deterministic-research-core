# Manual Focus Guardrail Fix Check Summary

- Batch: `manual_focus_guardrail_fix_check`
- Status: `clean`
- Ticker count: `5`
- Counts: `{'accounting_gain_not_operating_turnaround_count': 0, 'analyst_claim_count': 90, 'audit_errors': 9, 'audit_warnings': 6, 'canonical_metrics_created': 3675, 'company_archetype_present': 5, 'company_defined_fcf_mismatch_count': 0, 'company_defined_fcf_used': 0, 'company_guidance_available_count': 0, 'company_specific_claim_count': 80, 'consensus_only_count': 0, 'content_completeness_score': 371, 'current_kpi_appendix_only_count': 0, 'current_period_kpi_claim_count': 46, 'current_period_kpi_claim_count_main_body': 5, 'current_report_blocked_by_freshness_count': 0, 'data_bug': 0, 'data_confidence_score': 332, 'data_limitation_claim_count': 0, 'early_commercial_capital_intensive_tech_count': 1, 'earnings_confirmed_count': 0, 'earnings_unavailable_count': 5, 'earnings_within_10_trading_days_count': 0, 'evidence_mapped_claim_ratio': 500, 'evidence_warnings': 0, 'extreme_valuation_review': 3, 'fcf_ocf_inconsistency_count': 0, 'fcf_unavailable_block_count': 0, 'final_rating_rationale_quality': 440, 'financial_sanity_errors': 8, 'generic_claim_count': 0, 'generic_claim_ratio': 0, 'guard_threshold_review': 0, 'guidance_consensus_mismatch_count': 0, 'hard_claim_evidence_ratio': 500, 'hard_claims_without_evidence_count': 0, 'historical_qa_only_count': 0, 'ignored_frame_variants': 593, 'internal_research_quality_score': 430, 'mechanical_rating_language_count': 0, 'mechanical_rating_language_count_main_body': 0, 'missing_current_period_context_count': 0, 'order_materiality_missing_count': 0, 'period_bug': 2, 'placeholder_business_context_count': 0, 'publish_action_plan_trigger_count': 14, 'publish_claim_id_main_body_count': 0, 'publish_current_kpi_count': 46, 'publish_evidence_appendix_exists': 5, 'publish_mechanical_language_count': 2, 'publish_quality_score': 352, 'publish_report_exists': 5, 'publish_report_quality_score': 405, 'publish_valuation_sensitivity_present': 4, 'rating_rationale_claim_count': 5, 'reconciliation_warnings': 56, 'sec_derived_fcf_used': 4, 'source_ingestion_post_audit_block_count': 5, 'speculative_deep_tech_profile_count': 2, 'stale_price_basis_count': 0, 'substantive_analyst_claim_count': 65, 'substantive_claim_count': 65, 'substantive_claim_ratio': 362, 'technical_overweight_in_thesis_count': 3, 'technical_specific_claim_count': 10, 'ticker_specific_kpi_claim_count': 10, 'true_anomaly': 5, 'true_source_disagreements': 56, 'true_valuation_anomaly': 0, 'unsupported_earnings_event_claims': 0, 'unsupported_guidance_claims': 0, 'validation_errors': 0, 'validation_warnings': 5, 'valuation_specific_claim_count': 6, 'vendor_only_hard_claim_count': 0, 'vendor_only_hard_metrics_count': 0}`

## Results
| Ticker | Status | Publishable | External Display | Archetype | Publish Q | Internal Q | Data Confidence |
|---|---|---:|---|---|---:|---:|---:|
| IONQ | manual_review | false | Manual Review / Hold Pending FCF and Execution Evidence | EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH | 63 | 80 | 64 |
| NVDA | manual_review | false | Hold | SEMICONDUCTOR_AI_INFRA | 75 | 90 | 60 |
| QBTS | manual_review | false | Manual Review / Preliminary Underweight | SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL | 65 | 85 | 75 |
| QCOM | manual_review | false | Hold Pending FCF Support | SEMICONDUCTOR_AI_INFRA | 84 | 90 | 72 |
| RGTI | manual_review | false | Manual Review / Preliminary Underweight | SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL | 65 | 85 | 61 |

## Acceptance Notes
- QCOM FCF-support guard: `True`
- IONQ not STANDARD_GROWTH: `True`
- Weekend freshness warning removed: `True`
- RGTI/QBTS speculative deep-tech preserved: `True`

## Blocking Issues
- None
