# Pilot Review - data_ops_p0_replacement_check

- As-of date: `2026-05-17`
- Batch status: `completed_with_issues`
- Tickers: `5`

## Status Summary

- Passed: `0`
- Repaired: `0`
- Manual review: `5`
- Data unavailable: `0`
- Failed: `0`
- Average quality score: `70.2`
- Median quality score: `65.0`
- Lowest quality score: `65.0`
- Repair rate: `0.0%`
- Manual review rate: `100.0%`

## Before / After Reconciliation

- Old `SOURCE_VALUE_DISAGREEMENT`: `not provided`
- New `true_source_disagreements`: `56`
- Ignored frame / period variants: `593`

## Dashboard Counts

- `accounting_gain_not_operating_turnaround_count`: `0`
- `analyst_claim_count`: `106`
- `audit_errors`: `8`
- `audit_warnings`: `6`
- `canonical_metrics_created`: `3711`
- `company_archetype_present`: `5`
- `company_defined_fcf_mismatch_count`: `0`
- `company_defined_fcf_used`: `1`
- `company_guidance_available_count`: `1`
- `company_specific_claim_count`: `92`
- `consensus_only_count`: `0`
- `content_completeness_score`: `357`
- `current_kpi_appendix_only_count`: `2`
- `current_period_kpi_claim_count`: `49`
- `current_period_kpi_claim_count_main_body`: `11`
- `current_report_blocked_by_freshness_count`: `0`
- `data_bug`: `0`
- `data_confidence_score`: `335`
- `data_limitation_claim_count`: `0`
- `early_commercial_capital_intensive_tech_count`: `1`
- `earnings_confirmed_count`: `0`
- `earnings_unavailable_count`: `5`
- `earnings_within_10_trading_days_count`: `0`
- `evidence_mapped_claim_ratio`: `500`
- `evidence_warnings`: `0`
- `extreme_valuation_review`: `3`
- `fcf_ocf_inconsistency_count`: `0`
- `fcf_unavailable_block_count`: `0`
- `final_rating_rationale_quality`: `440`
- `financial_sanity_errors`: `7`
- `generic_claim_count`: `0`
- `generic_claim_ratio`: `0`
- `guard_threshold_review`: `1`
- `guidance_consensus_mismatch_count`: `0`
- `hard_claim_evidence_ratio`: `500`
- `hard_claims_without_evidence_count`: `0`
- `historical_qa_only_count`: `0`
- `ignored_frame_variants`: `593`
- `internal_research_quality_score`: `400`
- `mechanical_rating_language_count`: `0`
- `mechanical_rating_language_count_main_body`: `0`
- `missing_current_period_context_count`: `1`
- `order_materiality_missing_count`: `0`
- `period_bug`: `0`
- `placeholder_business_context_count`: `0`
- `publish_action_plan_trigger_count`: `0`
- `publish_claim_id_main_body_count`: `0`
- `publish_current_kpi_count`: `5`
- `publish_evidence_appendix_exists`: `5`
- `publish_mechanical_language_count`: `3`
- `publish_quality_score`: `351`
- `publish_report_exists`: `5`
- `publish_report_quality_score`: `195`
- `publish_valuation_sensitivity_present`: `0`
- `rating_rationale_claim_count`: `5`
- `reconciliation_warnings`: `56`
- `sec_derived_fcf_used`: `0`
- `source_ingestion_post_audit_block_count`: `5`
- `speculative_deep_tech_profile_count`: `2`
- `stale_price_basis_count`: `0`
- `substantive_analyst_claim_count`: `71`
- `substantive_claim_count`: `71`
- `substantive_claim_ratio`: `344`
- `technical_overweight_in_thesis_count`: `1`
- `technical_specific_claim_count`: `10`
- `ticker_specific_kpi_claim_count`: `26`
- `true_anomaly`: `6`
- `true_source_disagreements`: `56`
- `true_valuation_anomaly`: `0`
- `unsupported_earnings_event_claims`: `0`
- `unsupported_guidance_claims`: `0`
- `validation_errors`: `0`
- `validation_warnings`: `5`
- `valuation_specific_claim_count`: `6`
- `vendor_only_hard_claim_count`: `0`
- `vendor_only_hard_metrics_count`: `0`

## Frequent Issues

### Validation Issues

- `EARNINGS_DATE_UNAVAILABLE`: `5`

### Audit Issues

- `EXTREME_VALUATION_REQUIRES_REVIEW`: `3`
- `TRUE_FINANCIAL_ANOMALY`: `3`
- `SPECULATIVE_DEEP_TECH_MANUAL_REVIEW_PROFILE`: `2`
- `EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH_MANUAL_REVIEW_PROFILE`: `1`
- `FINANCIAL_SANITY_FCF_MARGIN_ANOMALY`: `1`
- `GUARD_THRESHOLD_REVIEW`: `1`
- `MISSING_FCF_SUPPORT_FOR_ACCUMULATE`: `1`
- `MISSING_CURRENT_PERIOD_KPI_CONTEXT`: `1`
- `TECHNICAL_OVERWEIGHT_IN_FUNDAMENTAL_THESIS`: `1`

### Evidence Issues

- `MISSING_EVIDENCE_FOR_METRIC`: `0`
- `NO_PRIMARY_EVIDENCE_FOR_HARD_METRIC`: `0`
- `MISSING_DATE_FOR_NEWS_EVENT`: `0`
- `VENDOR_SOURCE_USED_AS_PRIMARY`: `0`
- `GUIDANCE_CONSENSUS_CONFLATION`: `0`

### Reconciliation Warnings / Info

- `PERIOD_TYPE_MISMATCH_IGNORED`: `559`
- `TRUE_SOURCE_VALUE_DISAGREEMENT`: `56`
- `SOURCE_FRAME_VARIANT_IGNORED`: `34`

## Ticker Results

| Ticker | Status | Quality | External Rating | External Action | True Disagreements | Ignored Variants |
|---|---|---:|---|---|---:|---:|
| IONQ | manual_review | 65.0 | Manual Review / Hold Pending FCF and Execution Evidence | Hold pending FCF path and execution evidence | 0 | 45 |
| NVDA | manual_review | 86.0 | Accumulate |  | 29 | 269 |
| QBTS | manual_review | 65.0 | Manual Review / Preliminary Underweight | Underweight only as preliminary manual-review view | 0 | 46 |
| QCOM | manual_review | 70.0 | Hold Pending FCF Support | Accumulate only after FCF support | 25 | 183 |
| RGTI | manual_review | 65.0 | Manual Review / Preliminary Underweight | Underweight only as preliminary manual-review view | 2 | 50 |

## Best / Worst Result

- Best result: `NVDA` with quality `86.0`.
- Weakest result: `IONQ, QBTS, RGTI` with quality `65.0`.

## Data Quality Ranking

### Top 5 Weakest Data Quality

- `RGTI`: quality `65.0`, true disagreements `2`, validation errors `0`, audit errors `2`
- `IONQ`: quality `65.0`, true disagreements `0`, validation errors `0`, audit errors `2`
- `QBTS`: quality `65.0`, true disagreements `0`, validation errors `0`, audit errors `2`
- `QCOM`: quality `70.0`, true disagreements `25`, validation errors `0`, audit errors `2`
- `NVDA`: quality `86.0`, true disagreements `29`, validation errors `0`, audit errors `0`

### Top 5 Best Data Quality

- `NVDA`: quality `86.0`, true disagreements `29`, validation errors `0`, audit errors `0`
- `QCOM`: quality `70.0`, true disagreements `25`, validation errors `0`, audit errors `2`
- `IONQ`: quality `65.0`, true disagreements `0`, validation errors `0`, audit errors `2`
- `QBTS`: quality `65.0`, true disagreements `0`, validation errors `0`, audit errors `2`
- `RGTI`: quality `65.0`, true disagreements `2`, validation errors `0`, audit errors `2`

## Source Ingestion Sufficiency

- Tickers where `source_ingestion_mode` was not sufficient: `IONQ, NVDA, QBTS, QCOM, RGTI`
- Recommendation: `nicht produktionsreif`

## Production Readiness Assessment

- `source_ingestion_mode` still needs manual review before production operation.
- Remaining production gaps: populate a real EarningsCalendar feed and broaden IR/guidance release coverage; source-ingestion post-audit is wired and counted.

## Artifact Check

- All required dashboard artifact paths are present.
