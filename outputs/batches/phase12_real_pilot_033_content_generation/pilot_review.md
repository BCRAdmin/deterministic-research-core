# Pilot Review - phase12_real_pilot_033_content_generation

- As-of date: `2026-05-05`
- Batch status: `completed_with_issues`
- Tickers: `30`

## Status Summary

- Passed: `13`
- Repaired: `0`
- Manual review: `17`
- Failed: `0`
- Average quality score: `79.63333333333334`
- Median quality score: `76.0`
- Lowest quality score: `34.0`
- Repair rate: `0.0%`
- Manual review rate: `56.7%`

## Before / After Reconciliation

- Old `SOURCE_VALUE_DISAGREEMENT`: `not provided`
- New `true_source_disagreements`: `370`
- Ignored frame / period variants: `5299`

## Dashboard Counts

- `analyst_claim_count`: `540`
- `audit_errors`: `28`
- `audit_warnings`: `0`
- `canonical_metrics_created`: `30901`
- `company_guidance_available_count`: `0`
- `consensus_only_count`: `0`
- `content_completeness_score`: `2760`
- `earnings_confirmed_count`: `0`
- `earnings_unavailable_count`: `30`
- `earnings_within_10_trading_days_count`: `0`
- `evidence_mapped_claim_ratio`: `3000`
- `evidence_warnings`: `0`
- `financial_sanity_errors`: `28`
- `guidance_consensus_mismatch_count`: `0`
- `hard_claim_evidence_ratio`: `3000`
- `hard_claims_without_evidence_count`: `0`
- `ignored_frame_variants`: `5299`
- `reconciliation_warnings`: `370`
- `source_ingestion_post_audit_block_count`: `17`
- `true_source_disagreements`: `370`
- `unsupported_earnings_event_claims`: `0`
- `unsupported_guidance_claims`: `0`
- `validation_errors`: `0`
- `validation_warnings`: `30`
- `vendor_only_hard_claim_count`: `0`

## Frequent Issues

### Validation Issues

- `EARNINGS_DATE_UNAVAILABLE`: `30`

### Audit Issues

- `FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY`: `9`
- `FINANCIAL_SANITY_EV_SALES_ABSURD`: `8`
- `FINANCIAL_SANITY_FCF_MARGIN_ANOMALY`: `7`
- `FINANCIAL_SANITY_SBC_REVENUE_ANOMALY`: `4`

### Evidence Issues

- `MISSING_DATE_FOR_NEWS_EVENT`: `0`
- `NO_PRIMARY_EVIDENCE_FOR_HARD_METRIC`: `0`
- `MISSING_EVIDENCE_FOR_METRIC`: `0`
- `GUIDANCE_CONSENSUS_CONFLATION`: `0`
- `VENDOR_SOURCE_USED_AS_PRIMARY`: `0`

### Reconciliation Warnings / Info

- `PERIOD_TYPE_MISMATCH_IGNORED`: `4934`
- `TRUE_SOURCE_VALUE_DISAGREEMENT`: `370`
- `SOURCE_FRAME_VARIANT_IGNORED`: `365`

## Ticker Results

| Ticker | Status | Quality | Rating | True Disagreements | Ignored Variants |
|---|---|---:|---|---:|---:|
| AMZN | manual_review | 76.0 | Accumulate | 18 | 470 |
| MSFT | manual_review | 76.0 | Hold | 19 | 324 |
| GOOGL | passed | 98.0 | Hold | 2 | 108 |
| META | passed | 98.0 | Hold | 10 | 140 |
| AAPL | manual_review | 76.0 | Accumulate | 7 | 245 |
| NVDA | manual_review | 34.0 | Hold | 29 | 269 |
| AMD | manual_review | 76.0 | Hold | 14 | 218 |
| AVGO | passed | 98.0 | Hold | 2 | 98 |
| INTC | passed | 98.0 | Hold | 3 | 215 |
| QCOM | passed | 97.0 | Accumulate | 25 | 183 |
| MU | manual_review | 76.0 | Hold | 9 | 242 |
| MRVL | manual_review | 76.0 | Hold | 12 | 66 |
| ANET | manual_review | 34.0 | Hold | 8 | 177 |
| DDOG | passed | 99.0 | Hold | 0 | 65 |
| MDB | manual_review | 54.0 | Hold | 5 | 83 |
| SNOW | passed | 98.0 | Tactical Underweight | 1 | 62 |
| CRWD | manual_review | 76.0 | Hold | 2 | 46 |
| NET | manual_review | 77.0 | Hold | 0 | 62 |
| PANW | manual_review | 73.0 | Hold | 49 | 198 |
| ZS | passed | 99.0 | Hold | 0 | 76 |
| CRM | passed | 97.0 | Hold | 25 | 336 |
| NOW | manual_review | 34.0 | Hold | 15 | 190 |
| ORCL | passed | 98.0 | Hold | 3 | 189 |
| ADBE | passed | 97.0 | Hold | 22 | 229 |
| INTU | manual_review | 51.0 | Hold | 45 | 238 |
| UBER | manual_review | 76.0 | Hold | 5 | 68 |
| TSLA | manual_review | 75.0 | Hold | 23 | 213 |
| PLTR | manual_review | 76.0 | Hold | 1 | 56 |
| IBM | passed | 98.0 | Hold | 9 | 145 |
| NFLX | passed | 98.0 | Hold | 7 | 288 |

## Best / Worst Result

- Best result: `DDOG, ZS` with quality `99.0`.
- Weakest result: `NVDA, ANET, NOW` with quality `34.0`.

## Data Quality Ranking

### Top 5 Weakest Data Quality

- `NVDA`: quality `34.0`, true disagreements `29`, validation errors `0`, audit errors `4`
- `NOW`: quality `34.0`, true disagreements `15`, validation errors `0`, audit errors `4`
- `ANET`: quality `34.0`, true disagreements `8`, validation errors `0`, audit errors `4`
- `INTU`: quality `51.0`, true disagreements `45`, validation errors `0`, audit errors `2`
- `MDB`: quality `54.0`, true disagreements `5`, validation errors `0`, audit errors `2`

### Top 5 Best Data Quality

- `DDOG`: quality `99.0`, true disagreements `0`, validation errors `0`, audit errors `0`
- `ZS`: quality `99.0`, true disagreements `0`, validation errors `0`, audit errors `0`
- `SNOW`: quality `98.0`, true disagreements `1`, validation errors `0`, audit errors `0`
- `GOOGL`: quality `98.0`, true disagreements `2`, validation errors `0`, audit errors `0`
- `AVGO`: quality `98.0`, true disagreements `2`, validation errors `0`, audit errors `0`

## Source Ingestion Sufficiency

- Tickers where `source_ingestion_mode` was not sufficient: `AMZN, MSFT, AAPL, NVDA, AMD, MU, MRVL, ANET, MDB, CRWD, NET, PANW, NOW, INTU, UBER, TSLA, PLTR`
- Recommendation: `nicht produktionsreif`

## Production Readiness Assessment

- `source_ingestion_mode` still needs manual review before production operation.
- Remaining production gaps: populate a real EarningsCalendar feed and broaden IR/guidance release coverage; source-ingestion post-audit is wired and counted.

## Artifact Check

- All required dashboard artifact paths are present.
