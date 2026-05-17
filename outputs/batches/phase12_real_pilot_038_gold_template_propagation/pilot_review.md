# Pilot Review - phase12_real_pilot_038_gold_template_propagation

- As-of date: `2026-05-05`
- Batch status: `completed_with_issues`
- Tickers: `8`

## Status Summary

- Passed: `3`
- Repaired: `0`
- Manual review: `5`
- Failed: `0`
- Average quality score: `84.625`
- Median quality score: `82.0`
- Lowest quality score: `75.0`
- Repair rate: `0.0%`
- Manual review rate: `62.5%`

## Before / After Reconciliation

- Old `SOURCE_VALUE_DISAGREEMENT`: `not provided`
- New `true_source_disagreements`: `71`
- Ignored frame / period variants: `1568`

## Dashboard Counts

- `analyst_claim_count`: `162`
- `audit_errors`: `4`
- `audit_warnings`: `4`
- `canonical_metrics_created`: `8934`
- `company_defined_fcf_mismatch_count`: `0`
- `company_defined_fcf_used`: `2`
- `company_guidance_available_count`: `0`
- `company_specific_claim_count`: `153`
- `consensus_only_count`: `0`
- `content_completeness_score`: `706`
- `current_kpi_appendix_only_count`: `1`
- `current_period_kpi_claim_count`: `12`
- `current_period_kpi_claim_count_main_body`: `12`
- `data_bug`: `0`
- `data_limitation_claim_count`: `0`
- `earnings_confirmed_count`: `0`
- `earnings_unavailable_count`: `8`
- `earnings_within_10_trading_days_count`: `0`
- `evidence_mapped_claim_ratio`: `800`
- `evidence_warnings`: `0`
- `fcf_ocf_inconsistency_count`: `0`
- `fcf_unavailable_block_count`: `0`
- `final_rating_rationale_quality`: `760`
- `financial_sanity_errors`: `0`
- `generic_claim_count`: `0`
- `generic_claim_ratio`: `0`
- `guard_threshold_review`: `0`
- `guidance_consensus_mismatch_count`: `0`
- `hard_claim_evidence_ratio`: `800`
- `hard_claims_without_evidence_count`: `1`
- `ignored_frame_variants`: `1568`
- `mechanical_rating_language_count`: `0`
- `mechanical_rating_language_count_main_body`: `0`
- `missing_current_period_context_count`: `0`
- `period_bug`: `2`
- `placeholder_business_context_count`: `0`
- `publish_claim_id_main_body_count`: `0`
- `publish_current_kpi_count`: `53`
- `publish_evidence_appendix_exists`: `8`
- `publish_mechanical_language_count`: `0`
- `publish_report_exists`: `8`
- `publish_report_quality_score`: `800`
- `rating_rationale_claim_count`: `8`
- `reconciliation_warnings`: `71`
- `sec_derived_fcf_used`: `0`
- `source_ingestion_post_audit_block_count`: `5`
- `substantive_analyst_claim_count`: `135`
- `substantive_claim_count`: `135`
- `substantive_claim_ratio`: `667`
- `technical_specific_claim_count`: `16`
- `ticker_specific_kpi_claim_count`: `47`
- `true_anomaly`: `0`
- `true_source_disagreements`: `71`
- `unsupported_earnings_event_claims`: `0`
- `unsupported_guidance_claims`: `0`
- `validation_errors`: `0`
- `validation_warnings`: `8`
- `valuation_specific_claim_count`: `16`
- `vendor_only_hard_claim_count`: `0`

## Frequent Issues

### Validation Issues

- `EARNINGS_DATE_UNAVAILABLE`: `8`

### Audit Issues

- `UNVERIFIED_HARD_METRIC`: `4`
- `CURRENT_PERIOD_IR_RECONCILIATION_REQUIRED`: `3`
- `MISSING_EVIDENCE_FOR_HARD_CLAIM`: `1`

### Evidence Issues

- `NO_PRIMARY_EVIDENCE_FOR_HARD_METRIC`: `0`
- `MISSING_DATE_FOR_NEWS_EVENT`: `0`
- `GUIDANCE_CONSENSUS_CONFLATION`: `0`
- `MISSING_EVIDENCE_FOR_METRIC`: `0`
- `VENDOR_SOURCE_USED_AS_PRIMARY`: `0`

### Reconciliation Warnings / Info

- `PERIOD_TYPE_MISMATCH_IGNORED`: `1466`
- `SOURCE_FRAME_VARIANT_IGNORED`: `102`
- `TRUE_SOURCE_VALUE_DISAGREEMENT`: `71`

## Ticker Results

| Ticker | Status | Quality | Rating | True Disagreements | Ignored Variants |
|---|---|---:|---|---:|---:|
| MSFT | passed | 92.0 | Hold | 19 | 324 |
| GOOGL | passed | 95.0 | Hold | 2 | 108 |
| META | manual_review | 78.0 | Hold | 10 | 140 |
| AAPL | manual_review | 75.0 | Accumulate | 7 | 245 |
| DDOG | manual_review | 78.0 | Hold | 0 | 65 |
| SNOW | passed | 95.0 | Tactical Underweight | 1 | 62 |
| CRM | manual_review | 84.0 | Hold | 25 | 336 |
| NFLX | manual_review | 80.0 | Hold | 7 | 288 |

## Best / Worst Result

- Best result: `GOOGL, SNOW` with quality `95.0`.
- Weakest result: `AAPL` with quality `75.0`.

## Data Quality Ranking

### Top 5 Weakest Data Quality

- `AAPL`: quality `75.0`, true disagreements `7`, validation errors `0`, audit errors `0`
- `DDOG`: quality `78.0`, true disagreements `0`, validation errors `0`, audit errors `2`
- `META`: quality `78.0`, true disagreements `10`, validation errors `0`, audit errors `0`
- `NFLX`: quality `80.0`, true disagreements `7`, validation errors `0`, audit errors `1`
- `CRM`: quality `84.0`, true disagreements `25`, validation errors `0`, audit errors `1`

### Top 5 Best Data Quality

- `SNOW`: quality `95.0`, true disagreements `1`, validation errors `0`, audit errors `0`
- `GOOGL`: quality `95.0`, true disagreements `2`, validation errors `0`, audit errors `0`
- `MSFT`: quality `92.0`, true disagreements `19`, validation errors `0`, audit errors `0`
- `CRM`: quality `84.0`, true disagreements `25`, validation errors `0`, audit errors `1`
- `NFLX`: quality `80.0`, true disagreements `7`, validation errors `0`, audit errors `1`

## Source Ingestion Sufficiency

- Tickers where `source_ingestion_mode` was not sufficient: `META, AAPL, DDOG, CRM, NFLX`
- Recommendation: `nicht produktionsreif`

## Production Readiness Assessment

- `source_ingestion_mode` still needs manual review before production operation.
- Remaining production gaps: populate a real EarningsCalendar feed and broaden IR/guidance release coverage; source-ingestion post-audit is wired and counted.

## Artifact Check

- All required dashboard artifact paths are present.
