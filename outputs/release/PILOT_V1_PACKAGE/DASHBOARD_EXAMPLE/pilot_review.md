# Pilot Review - phase12_current_batch_003

- As-of date: `2026-05-08`
- Batch status: `completed_with_issues`
- Tickers: `12`

## Status Summary

- Passed: `9`
- Repaired: `0`
- Manual review: `3`
- Failed: `0`
- Average quality score: `88.75`
- Median quality score: `91.0`
- Lowest quality score: `74.0`
- Repair rate: `0.0%`
- Manual review rate: `25.0%`

## Before / After Reconciliation

- Old `SOURCE_VALUE_DISAGREEMENT`: `not provided`
- New `true_source_disagreements`: `136`
- Ignored frame / period variants: `2360`

## Dashboard Counts

- `analyst_claim_count`: `243`
- `audit_errors`: `5`
- `audit_warnings`: `1`
- `canonical_metrics_created`: `13577`
- `company_defined_fcf_mismatch_count`: `0`
- `company_defined_fcf_used`: `4`
- `company_guidance_available_count`: `0`
- `company_specific_claim_count`: `230`
- `consensus_only_count`: `0`
- `content_completeness_score`: `1086`
- `current_kpi_appendix_only_count`: `1`
- `current_period_kpi_claim_count`: `126`
- `current_period_kpi_claim_count_main_body`: `33`
- `data_bug`: `0`
- `data_limitation_claim_count`: `0`
- `earnings_confirmed_count`: `0`
- `earnings_unavailable_count`: `12`
- `earnings_within_10_trading_days_count`: `0`
- `evidence_mapped_claim_ratio`: `1200`
- `evidence_warnings`: `0`
- `fcf_ocf_inconsistency_count`: `0`
- `fcf_unavailable_block_count`: `0`
- `final_rating_rationale_quality`: `1160`
- `financial_sanity_errors`: `4`
- `generic_claim_count`: `0`
- `generic_claim_ratio`: `0`
- `guard_threshold_review`: `1`
- `guidance_consensus_mismatch_count`: `0`
- `hard_claim_evidence_ratio`: `1200`
- `hard_claims_without_evidence_count`: `0`
- `ignored_frame_variants`: `2360`
- `mechanical_rating_language_count`: `1`
- `mechanical_rating_language_count_main_body`: `1`
- `missing_current_period_context_count`: `0`
- `period_bug`: `0`
- `placeholder_business_context_count`: `0`
- `publish_action_plan_trigger_count`: `56`
- `publish_claim_id_main_body_count`: `0`
- `publish_current_kpi_count`: `126`
- `publish_evidence_appendix_exists`: `12`
- `publish_mechanical_language_count`: `0`
- `publish_report_exists`: `12`
- `publish_report_quality_score`: `1200`
- `publish_valuation_sensitivity_present`: `12`
- `rating_rationale_claim_count`: `12`
- `reconciliation_warnings`: `136`
- `sec_derived_fcf_used`: `0`
- `source_ingestion_post_audit_block_count`: `3`
- `substantive_analyst_claim_count`: `202`
- `substantive_claim_count`: `202`
- `substantive_claim_ratio`: `996`
- `technical_specific_claim_count`: `24`
- `ticker_specific_kpi_claim_count`: `68`
- `true_anomaly`: `2`
- `true_source_disagreements`: `136`
- `unsupported_earnings_event_claims`: `0`
- `unsupported_guidance_claims`: `0`
- `validation_errors`: `0`
- `validation_warnings`: `12`
- `valuation_specific_claim_count`: `23`
- `vendor_only_hard_claim_count`: `0`

## Frequent Issues

### Validation Issues

- `EARNINGS_DATE_UNAVAILABLE`: `12`

### Audit Issues

- `FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY`: `2`
- `TRUE_FINANCIAL_ANOMALY`: `2`
- `GUARD_THRESHOLD_REVIEW`: `1`
- `MISSING_FCF_SUPPORT_FOR_ACCUMULATE`: `1`

### Evidence Issues

- `GUIDANCE_CONSENSUS_CONFLATION`: `0`
- `VENDOR_SOURCE_USED_AS_PRIMARY`: `0`
- `NO_PRIMARY_EVIDENCE_FOR_HARD_METRIC`: `0`
- `MISSING_EVIDENCE_FOR_METRIC`: `0`
- `MISSING_DATE_FOR_NEWS_EVENT`: `0`

### Reconciliation Warnings / Info

- `PERIOD_TYPE_MISMATCH_IGNORED`: `2187`
- `SOURCE_FRAME_VARIANT_IGNORED`: `173`
- `TRUE_SOURCE_VALUE_DISAGREEMENT`: `136`

## Ticker Results

| Ticker | Status | Quality | External Rating | External Action | True Disagreements | Ignored Variants |
|---|---|---:|---|---|---:|---:|
| GOOGL | passed | 95.0 | Hold |  | 2 | 108 |
| SNOW | passed | 95.0 | Hold with Underweight Bias |  | 1 | 62 |
| MSFT | passed | 92.0 | Hold |  | 19 | 324 |
| AAPL | passed | 92.0 | Accumulate |  | 7 | 245 |
| META | passed | 95.0 | Hold |  | 10 | 140 |
| NFLX | passed | 90.0 | Hold |  | 7 | 288 |
| AVGO | passed | 90.0 | Hold |  | 2 | 98 |
| DDOG | passed | 92.0 | Hold |  | 0 | 65 |
| CRM | passed | 88.0 | Hold |  | 25 | 336 |
| MU | manual_review | 74.0 | Hold |  | 9 | 242 |
| NVDA | manual_review | 75.0 | Hold |  | 29 | 269 |
| QCOM | manual_review | 87.0 | Hold Pending FCF Support | Accumulate only after FCF support | 25 | 183 |

## Best / Worst Result

- Best result: `GOOGL, SNOW, META` with quality `95.0`.
- Weakest result: `MU` with quality `74.0`.

## Data Quality Ranking

### Top 5 Weakest Data Quality

- `MU`: quality `74.0`, true disagreements `9`, validation errors `0`, audit errors `2`
- `NVDA`: quality `75.0`, true disagreements `29`, validation errors `0`, audit errors `2`
- `QCOM`: quality `87.0`, true disagreements `25`, validation errors `0`, audit errors `1`
- `CRM`: quality `88.0`, true disagreements `25`, validation errors `0`, audit errors `0`
- `NFLX`: quality `90.0`, true disagreements `7`, validation errors `0`, audit errors `0`

### Top 5 Best Data Quality

- `SNOW`: quality `95.0`, true disagreements `1`, validation errors `0`, audit errors `0`
- `GOOGL`: quality `95.0`, true disagreements `2`, validation errors `0`, audit errors `0`
- `META`: quality `95.0`, true disagreements `10`, validation errors `0`, audit errors `0`
- `DDOG`: quality `92.0`, true disagreements `0`, validation errors `0`, audit errors `0`
- `AAPL`: quality `92.0`, true disagreements `7`, validation errors `0`, audit errors `0`

## Source Ingestion Sufficiency

- Tickers where `source_ingestion_mode` was not sufficient: `MU, NVDA, QCOM`
- Recommendation: `pilotfaehig`

## Production Readiness Assessment

- `source_ingestion_mode` looks operational for controlled pilots after reconciliation hardening.
- Remaining production gaps: populate a real EarningsCalendar feed and broaden IR/guidance release coverage; source-ingestion post-audit is wired and counted.

## Artifact Check

- All required dashboard artifact paths are present.
