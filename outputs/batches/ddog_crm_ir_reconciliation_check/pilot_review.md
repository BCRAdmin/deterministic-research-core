# Pilot Review - ddog_crm_ir_reconciliation_check

- As-of date: `2026-05-05`
- Batch status: `completed`
- Tickers: `2`

## Status Summary

- Passed: `2`
- Repaired: `0`
- Manual review: `0`
- Failed: `0`
- Average quality score: `92.0`
- Median quality score: `92.0`
- Lowest quality score: `92.0`
- Repair rate: `0.0%`
- Manual review rate: `0.0%`

## Before / After Reconciliation

- Old `SOURCE_VALUE_DISAGREEMENT`: `not provided`
- New `true_source_disagreements`: `25`
- Ignored frame / period variants: `401`

## Dashboard Counts

- `analyst_claim_count`: `36`
- `audit_errors`: `0`
- `audit_warnings`: `0`
- `canonical_metrics_created`: `2162`
- `company_guidance_available_count`: `0`
- `company_specific_claim_count`: `10`
- `consensus_only_count`: `0`
- `content_completeness_score`: `184`
- `data_bug`: `0`
- `earnings_confirmed_count`: `0`
- `earnings_unavailable_count`: `2`
- `earnings_within_10_trading_days_count`: `0`
- `evidence_mapped_claim_ratio`: `200`
- `evidence_warnings`: `0`
- `financial_sanity_errors`: `0`
- `generic_claim_count`: `2`
- `generic_claim_ratio`: `12`
- `guard_threshold_review`: `0`
- `guidance_consensus_mismatch_count`: `0`
- `hard_claim_evidence_ratio`: `200`
- `hard_claims_without_evidence_count`: `0`
- `ignored_frame_variants`: `401`
- `period_bug`: `0`
- `rating_rationale_claim_count`: `2`
- `reconciliation_warnings`: `25`
- `source_ingestion_post_audit_block_count`: `0`
- `substantive_analyst_claim_count`: `34`
- `substantive_claim_count`: `34`
- `substantive_claim_ratio`: `188`
- `technical_specific_claim_count`: `2`
- `true_anomaly`: `0`
- `true_source_disagreements`: `25`
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

- `MISSING_DATE_FOR_NEWS_EVENT`: `0`
- `VENDOR_SOURCE_USED_AS_PRIMARY`: `0`
- `NO_PRIMARY_EVIDENCE_FOR_HARD_METRIC`: `0`
- `GUIDANCE_CONSENSUS_CONFLATION`: `0`
- `MISSING_EVIDENCE_FOR_METRIC`: `0`

### Reconciliation Warnings / Info

- `PERIOD_TYPE_MISMATCH_IGNORED`: `391`
- `TRUE_SOURCE_VALUE_DISAGREEMENT`: `25`
- `SOURCE_FRAME_VARIANT_IGNORED`: `10`

## Ticker Results

| Ticker | Status | Quality | Rating | True Disagreements | Ignored Variants |
|---|---|---:|---|---:|---:|
| DDOG | passed | 92.0 | Hold | 0 | 65 |
| CRM | passed | 92.0 | Hold | 25 | 336 |

## Best / Worst Result

- Best result: `DDOG, CRM` with quality `92.0`.
- Weakest result: `DDOG, CRM` with quality `92.0`.

## Data Quality Ranking

### Top 5 Weakest Data Quality

- `CRM`: quality `92.0`, true disagreements `25`, validation errors `0`, audit errors `0`
- `DDOG`: quality `92.0`, true disagreements `0`, validation errors `0`, audit errors `0`

### Top 5 Best Data Quality

- `DDOG`: quality `92.0`, true disagreements `0`, validation errors `0`, audit errors `0`
- `CRM`: quality `92.0`, true disagreements `25`, validation errors `0`, audit errors `0`

## Source Ingestion Sufficiency

- Tickers where `source_ingestion_mode` was not sufficient: `none`
- Recommendation: `produktionsreif`

## Production Readiness Assessment

- `source_ingestion_mode` looks production-ready for this universe.
- Remaining production gaps: populate a real EarningsCalendar feed and broaden IR/guidance release coverage; source-ingestion post-audit is wired and counted.

## Artifact Check

- All required dashboard artifact paths are present.
