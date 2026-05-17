# Pilot Review - phase12_real_pilot_031

- As-of date: `2026-05-05`
- Batch status: `completed`
- Tickers: `30`

## Status Summary

- Passed: `30`
- Repaired: `0`
- Manual review: `0`
- Failed: `0`
- Average quality score: `97.73333333333333`
- Median quality score: `98.0`
- Lowest quality score: `95.0`
- Repair rate: `0.0%`
- Manual review rate: `0.0%`

## Before / After Reconciliation

- Old `SOURCE_VALUE_DISAGREEMENT`: `370`
- Old ignored frame / period variants: `5299`
- New `true_source_disagreements`: `370`
- Ignored frame / period variants: `5299`

## Dashboard Counts

- `audit_errors`: `0`
- `audit_warnings`: `0`
- `canonical_metrics_created`: `30901`
- `company_guidance_available_count`: `0`
- `consensus_only_count`: `0`
- `earnings_confirmed_count`: `0`
- `earnings_unavailable_count`: `30`
- `earnings_within_10_trading_days_count`: `0`
- `evidence_warnings`: `0`
- `guidance_consensus_mismatch_count`: `0`
- `hard_claims_without_evidence_count`: `0`
- `ignored_frame_variants`: `5299`
- `reconciliation_warnings`: `370`
- `source_ingestion_post_audit_block_count`: `0`
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

- None

### Evidence Issues

- `MISSING_DATE_FOR_NEWS_EVENT`: `0`
- `NO_PRIMARY_EVIDENCE_FOR_HARD_METRIC`: `0`
- `GUIDANCE_CONSENSUS_CONFLATION`: `0`
- `VENDOR_SOURCE_USED_AS_PRIMARY`: `0`
- `MISSING_EVIDENCE_FOR_METRIC`: `0`

### Reconciliation Warnings / Info

- `PERIOD_TYPE_MISMATCH_IGNORED`: `4934`
- `TRUE_SOURCE_VALUE_DISAGREEMENT`: `370`
- `SOURCE_FRAME_VARIANT_IGNORED`: `365`

## Ticker Results

| Ticker | Status | Quality | Rating | True Disagreements | Ignored Variants |
|---|---|---:|---|---:|---:|
| AMZN | passed | 98.0 | Accumulate | 18 | 470 |
| MSFT | passed | 98.0 | Hold | 19 | 324 |
| GOOGL | passed | 98.0 | Hold | 2 | 108 |
| META | passed | 98.0 | Hold | 10 | 140 |
| AAPL | passed | 98.0 | Accumulate | 7 | 245 |
| NVDA | passed | 97.0 | Hold | 29 | 269 |
| AMD | passed | 98.0 | Hold | 14 | 218 |
| AVGO | passed | 98.0 | Hold | 2 | 98 |
| INTC | passed | 98.0 | Hold | 3 | 215 |
| QCOM | passed | 97.0 | Accumulate | 25 | 183 |
| MU | passed | 98.0 | Hold | 9 | 242 |
| MRVL | passed | 98.0 | Hold | 12 | 66 |
| ANET | passed | 98.0 | Hold | 8 | 177 |
| DDOG | passed | 99.0 | Hold | 0 | 65 |
| MDB | passed | 98.0 | Hold | 5 | 83 |
| SNOW | passed | 98.0 | Tactical Underweight | 1 | 62 |
| CRWD | passed | 98.0 | Hold | 2 | 46 |
| NET | passed | 99.0 | Hold | 0 | 62 |
| PANW | passed | 95.0 | Hold | 49 | 198 |
| ZS | passed | 99.0 | Hold | 0 | 76 |
| CRM | passed | 97.0 | Hold | 25 | 336 |
| NOW | passed | 98.0 | Hold | 15 | 190 |
| ORCL | passed | 98.0 | Hold | 3 | 189 |
| ADBE | passed | 97.0 | Hold | 22 | 229 |
| INTU | passed | 95.0 | Hold | 45 | 238 |
| UBER | passed | 98.0 | Hold | 5 | 68 |
| TSLA | passed | 97.0 | Hold | 23 | 213 |
| PLTR | passed | 98.0 | Hold | 1 | 56 |
| IBM | passed | 98.0 | Hold | 9 | 145 |
| NFLX | passed | 98.0 | Hold | 7 | 288 |

## Best / Worst Result

- Best result: `DDOG, NET, ZS` with quality `99.0`.
- Weakest result: `PANW, INTU` with quality `95.0`.

## Data Quality Ranking

### Top 5 Weakest Data Quality

- `PANW`: quality `95.0`, true disagreements `49`, validation errors `0`, audit errors `0`
- `INTU`: quality `95.0`, true disagreements `45`, validation errors `0`, audit errors `0`
- `NVDA`: quality `97.0`, true disagreements `29`, validation errors `0`, audit errors `0`
- `QCOM`: quality `97.0`, true disagreements `25`, validation errors `0`, audit errors `0`
- `CRM`: quality `97.0`, true disagreements `25`, validation errors `0`, audit errors `0`

### Top 5 Best Data Quality

- `DDOG`: quality `99.0`, true disagreements `0`, validation errors `0`, audit errors `0`
- `NET`: quality `99.0`, true disagreements `0`, validation errors `0`, audit errors `0`
- `ZS`: quality `99.0`, true disagreements `0`, validation errors `0`, audit errors `0`
- `SNOW`: quality `98.0`, true disagreements `1`, validation errors `0`, audit errors `0`
- `PLTR`: quality `98.0`, true disagreements `1`, validation errors `0`, audit errors `0`

## Source Ingestion Sufficiency

- Tickers where `source_ingestion_mode` was not sufficient: `none`
- Recommendation: `pilotfaehig`

## Production Readiness Assessment

- `source_ingestion_mode` looks operational for controlled pilots after reconciliation hardening.
- Remaining production gaps: populate a real EarningsCalendar feed and broaden IR/guidance release coverage; source-ingestion post-audit is wired and counted.

## Artifact Check

- All required dashboard artifact paths are present.
