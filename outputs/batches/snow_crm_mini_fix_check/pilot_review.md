# Pilot Review - snow_crm_mini_fix_check

- As-of date: `2026-05-08`
- Batch status: `completed`
- Tickers: `2`

## Status Summary

- Passed: `2`
- Repaired: `0`
- Manual review: `0`
- Failed: `0`
- Average quality score: `91.5`
- Median quality score: `91.5`
- Lowest quality score: `88.0`
- Repair rate: `0.0%`
- Manual review rate: `0.0%`

## Before / After Reconciliation

- Old `SOURCE_VALUE_DISAGREEMENT`: `not provided`
- New `true_source_disagreements`: `26`
- Ignored frame / period variants: `398`

## Dashboard Counts

- `analyst_claim_count`: `42`
- `audit_errors`: `0`
- `audit_warnings`: `0`
- `canonical_metrics_created`: `2081`
- `company_defined_fcf_mismatch_count`: `0`
- `company_defined_fcf_used`: `2`
- `company_guidance_available_count`: `0`
- `company_specific_claim_count`: `42`
- `consensus_only_count`: `0`
- `content_completeness_score`: `183`
- `current_kpi_appendix_only_count`: `1`
- `current_period_kpi_claim_count`: `20`
- `current_period_kpi_claim_count_main_body`: `6`
- `data_bug`: `0`
- `data_limitation_claim_count`: `0`
- `earnings_confirmed_count`: `0`
- `earnings_unavailable_count`: `2`
- `earnings_within_10_trading_days_count`: `0`
- `evidence_mapped_claim_ratio`: `200`
- `evidence_warnings`: `0`
- `fcf_ocf_inconsistency_count`: `0`
- `fcf_unavailable_block_count`: `0`
- `final_rating_rationale_quality`: `180`
- `financial_sanity_errors`: `0`
- `generic_claim_count`: `0`
- `generic_claim_ratio`: `0`
- `guard_threshold_review`: `0`
- `guidance_consensus_mismatch_count`: `0`
- `hard_claim_evidence_ratio`: `200`
- `hard_claims_without_evidence_count`: `0`
- `ignored_frame_variants`: `398`
- `mechanical_rating_language_count`: `0`
- `mechanical_rating_language_count_main_body`: `0`
- `missing_current_period_context_count`: `0`
- `period_bug`: `0`
- `placeholder_business_context_count`: `0`
- `publish_action_plan_trigger_count`: `8`
- `publish_claim_id_main_body_count`: `0`
- `publish_current_kpi_count`: `20`
- `publish_evidence_appendix_exists`: `2`
- `publish_mechanical_language_count`: `0`
- `publish_report_exists`: `2`
- `publish_report_quality_score`: `200`
- `publish_valuation_sensitivity_present`: `2`
- `rating_rationale_claim_count`: `2`
- `reconciliation_warnings`: `26`
- `sec_derived_fcf_used`: `0`
- `source_ingestion_post_audit_block_count`: `0`
- `substantive_analyst_claim_count`: `37`
- `substantive_claim_count`: `37`
- `substantive_claim_ratio`: `176`
- `technical_specific_claim_count`: `4`
- `ticker_specific_kpi_claim_count`: `20`
- `true_anomaly`: `0`
- `true_source_disagreements`: `26`
- `unsupported_earnings_event_claims`: `0`
- `unsupported_guidance_claims`: `0`
- `validation_errors`: `0`
- `validation_warnings`: `2`
- `valuation_specific_claim_count`: `4`
- `vendor_only_hard_claim_count`: `0`

## Frequent Issues

### Validation Issues

- `EARNINGS_DATE_UNAVAILABLE`: `2`

### Audit Issues

- None

### Evidence Issues

- `MISSING_EVIDENCE_FOR_METRIC`: `0`
- `VENDOR_SOURCE_USED_AS_PRIMARY`: `0`
- `NO_PRIMARY_EVIDENCE_FOR_HARD_METRIC`: `0`
- `GUIDANCE_CONSENSUS_CONFLATION`: `0`
- `MISSING_DATE_FOR_NEWS_EVENT`: `0`

### Reconciliation Warnings / Info

- `PERIOD_TYPE_MISMATCH_IGNORED`: `388`
- `TRUE_SOURCE_VALUE_DISAGREEMENT`: `26`
- `SOURCE_FRAME_VARIANT_IGNORED`: `10`

## Ticker Results

| Ticker | Status | Quality | External Rating | External Action | True Disagreements | Ignored Variants |
|---|---|---:|---|---|---:|---:|
| SNOW | passed | 95.0 | Hold with Underweight Bias |  | 1 | 62 |
| CRM | passed | 88.0 | Hold |  | 25 | 336 |

## Best / Worst Result

- Best result: `SNOW` with quality `95.0`.
- Weakest result: `CRM` with quality `88.0`.

## Data Quality Ranking

### Top 5 Weakest Data Quality

- `CRM`: quality `88.0`, true disagreements `25`, validation errors `0`, audit errors `0`
- `SNOW`: quality `95.0`, true disagreements `1`, validation errors `0`, audit errors `0`

### Top 5 Best Data Quality

- `SNOW`: quality `95.0`, true disagreements `1`, validation errors `0`, audit errors `0`
- `CRM`: quality `88.0`, true disagreements `25`, validation errors `0`, audit errors `0`

## Source Ingestion Sufficiency

- Tickers where `source_ingestion_mode` was not sufficient: `none`
- Recommendation: `produktionsreif`

## Production Readiness Assessment

- `source_ingestion_mode` looks production-ready for this universe.
- Remaining production gaps: populate a real EarningsCalendar feed and broaden IR/guidance release coverage; source-ingestion post-audit is wired and counted.

## Artifact Check

- All required dashboard artifact paths are present.
