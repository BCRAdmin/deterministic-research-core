# Pilot Review - pilot_v1_blind_test_001

- As-of date: `2026-05-05`
- Batch status: `completed_with_issues`
- Tickers: `5`

## Status Summary

- Passed: `0`
- Repaired: `0`
- Manual review: `5`
- Failed: `0`
- Average quality score: `78.0`
- Median quality score: `78.0`
- Lowest quality score: `78.0`
- Repair rate: `0.0%`
- Manual review rate: `100.0%`

## Before / After Reconciliation

- Old `SOURCE_VALUE_DISAGREEMENT`: `not provided`
- New `true_source_disagreements`: `68`
- Ignored frame / period variants: `889`

## Dashboard Counts

- `analyst_claim_count`: `90`
- `audit_errors`: `0`
- `audit_warnings`: `0`
- `canonical_metrics_created`: `5516`
- `company_defined_fcf_mismatch_count`: `0`
- `company_defined_fcf_used`: `0`
- `company_guidance_available_count`: `0`
- `company_specific_claim_count`: `75`
- `consensus_only_count`: `0`
- `content_completeness_score`: `390`
- `current_kpi_appendix_only_count`: `0`
- `current_period_kpi_claim_count`: `75`
- `current_period_kpi_claim_count_main_body`: `5`
- `data_bug`: `0`
- `data_limitation_claim_count`: `0`
- `earnings_confirmed_count`: `0`
- `earnings_unavailable_count`: `5`
- `earnings_within_10_trading_days_count`: `0`
- `evidence_mapped_claim_ratio`: `500`
- `evidence_warnings`: `0`
- `fcf_ocf_inconsistency_count`: `0`
- `fcf_unavailable_block_count`: `0`
- `final_rating_rationale_quality`: `400`
- `financial_sanity_errors`: `0`
- `generic_claim_count`: `0`
- `generic_claim_ratio`: `0`
- `guard_threshold_review`: `0`
- `guidance_consensus_mismatch_count`: `0`
- `hard_claim_evidence_ratio`: `500`
- `hard_claims_without_evidence_count`: `0`
- `ignored_frame_variants`: `889`
- `mechanical_rating_language_count`: `0`
- `mechanical_rating_language_count_main_body`: `0`
- `missing_current_period_context_count`: `0`
- `period_bug`: `0`
- `placeholder_business_context_count`: `0`
- `publish_action_plan_trigger_count`: `20`
- `publish_claim_id_main_body_count`: `0`
- `publish_current_kpi_count`: `75`
- `publish_evidence_appendix_exists`: `5`
- `publish_mechanical_language_count`: `0`
- `publish_report_exists`: `5`
- `publish_report_quality_score`: `500`
- `publish_valuation_sensitivity_present`: `5`
- `rating_rationale_claim_count`: `5`
- `reconciliation_warnings`: `68`
- `sec_derived_fcf_used`: `0`
- `source_ingestion_post_audit_block_count`: `0`
- `substantive_analyst_claim_count`: `65`
- `substantive_claim_count`: `65`
- `substantive_claim_ratio`: `360`
- `technical_specific_claim_count`: `10`
- `ticker_specific_kpi_claim_count`: `5`
- `true_anomaly`: `0`
- `true_source_disagreements`: `68`
- `unsupported_earnings_event_claims`: `0`
- `unsupported_guidance_claims`: `0`
- `validation_errors`: `0`
- `validation_warnings`: `5`
- `valuation_specific_claim_count`: `10`
- `vendor_only_hard_claim_count`: `0`

## Frequent Issues

### Validation Issues

- `EARNINGS_DATE_UNAVAILABLE`: `5`

### Audit Issues

- None

### Evidence Issues

- `NO_PRIMARY_EVIDENCE_FOR_HARD_METRIC`: `0`
- `GUIDANCE_CONSENSUS_CONFLATION`: `0`
- `MISSING_EVIDENCE_FOR_METRIC`: `0`
- `VENDOR_SOURCE_USED_AS_PRIMARY`: `0`
- `MISSING_DATE_FOR_NEWS_EVENT`: `0`

### Reconciliation Warnings / Info

- `PERIOD_TYPE_MISMATCH_IGNORED`: `830`
- `TRUE_SOURCE_VALUE_DISAGREEMENT`: `68`
- `SOURCE_FRAME_VARIANT_IGNORED`: `59`

## Ticker Results

| Ticker | Status | Quality | Rating | True Disagreements | Ignored Variants |
|---|---|---:|---|---:|---:|
| NOW | manual_review | 78.0 | Hold | 15 | 190 |
| ORCL | manual_review | 78.0 | Hold | 3 | 189 |
| ADBE | manual_review | 78.0 | Hold | 22 | 229 |
| UBER | manual_review | 78.0 | Hold | 5 | 68 |
| TSLA | manual_review | 78.0 | Hold | 23 | 213 |

## Best / Worst Result

- Best result: `NOW, ORCL, ADBE, UBER, TSLA` with quality `78.0`.
- Weakest result: `NOW, ORCL, ADBE, UBER, TSLA` with quality `78.0`.

## Data Quality Ranking

### Top 5 Weakest Data Quality

- `TSLA`: quality `78.0`, true disagreements `23`, validation errors `0`, audit errors `0`
- `ADBE`: quality `78.0`, true disagreements `22`, validation errors `0`, audit errors `0`
- `NOW`: quality `78.0`, true disagreements `15`, validation errors `0`, audit errors `0`
- `UBER`: quality `78.0`, true disagreements `5`, validation errors `0`, audit errors `0`
- `ORCL`: quality `78.0`, true disagreements `3`, validation errors `0`, audit errors `0`

### Top 5 Best Data Quality

- `ORCL`: quality `78.0`, true disagreements `3`, validation errors `0`, audit errors `0`
- `UBER`: quality `78.0`, true disagreements `5`, validation errors `0`, audit errors `0`
- `NOW`: quality `78.0`, true disagreements `15`, validation errors `0`, audit errors `0`
- `ADBE`: quality `78.0`, true disagreements `22`, validation errors `0`, audit errors `0`
- `TSLA`: quality `78.0`, true disagreements `23`, validation errors `0`, audit errors `0`

## Source Ingestion Sufficiency

- Tickers where `source_ingestion_mode` was not sufficient: `NOW, ORCL, ADBE, UBER, TSLA`
- Recommendation: `nicht produktionsreif`

## Production Readiness Assessment

- `source_ingestion_mode` still needs manual review before production operation.
- Remaining production gaps: populate a real EarningsCalendar feed and broaden IR/guidance release coverage; source-ingestion post-audit is wired and counted.

## Artifact Check

- All required dashboard artifact paths are present.
