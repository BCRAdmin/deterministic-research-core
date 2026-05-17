# Pilot Review - phase12_real_pilot_030

- As-of date: `2026-05-05`
- Batch status: `completed`
- Tickers: `30`

## Status Summary

- Passed: `30`
- Repaired: `0`
- Manual review: `0`
- Failed: `0`
- Average quality score: `93.73333333333333`
- Median quality score: `94.0`
- Lowest quality score: `91.0`
- Repair rate: `0.0%`
- Manual review rate: `0.0%`

## Before / After Reconciliation

- Old `SOURCE_VALUE_DISAGREEMENT`: `not provided`
- New `true_source_disagreements`: `370`
- Ignored frame / period variants: `5299`

## Dashboard Counts

- `audit_errors`: `0`
- `audit_warnings`: `0`
- `canonical_metrics_created`: `30901`
- `evidence_warnings`: `0`
- `ignored_frame_variants`: `5299`
- `reconciliation_warnings`: `370`
- `true_source_disagreements`: `370`
- `validation_errors`: `0`
- `validation_warnings`: `30`

## Frequent Issues

### Validation Issues

- `EARNINGS_DATE_UNAVAILABLE`: `30`

### Audit Issues

- None

### Evidence Issues

- `NO_PRIMARY_EVIDENCE_FOR_HARD_METRIC`: `0`
- `MISSING_DATE_FOR_NEWS_EVENT`: `0`
- `VENDOR_SOURCE_USED_AS_PRIMARY`: `0`
- `GUIDANCE_CONSENSUS_CONFLATION`: `0`
- `MISSING_EVIDENCE_FOR_METRIC`: `0`

### Reconciliation Warnings / Info

- `PERIOD_TYPE_MISMATCH_IGNORED`: `4934`
- `TRUE_SOURCE_VALUE_DISAGREEMENT`: `370`
- `SOURCE_FRAME_VARIANT_IGNORED`: `365`

## Ticker Results

| Ticker | Status | Quality | Rating | True Disagreements | Ignored Variants |
|---|---|---:|---|---:|---:|
| AMZN | passed | 94.0 | Accumulate | 18 | 470 |
| MSFT | passed | 94.0 | Hold | 19 | 324 |
| GOOGL | passed | 94.0 | Hold | 2 | 108 |
| META | passed | 94.0 | Hold | 10 | 140 |
| AAPL | passed | 94.0 | Accumulate | 7 | 245 |
| NVDA | passed | 93.0 | Hold | 29 | 269 |
| AMD | passed | 94.0 | Hold | 14 | 218 |
| AVGO | passed | 94.0 | Hold | 2 | 98 |
| INTC | passed | 94.0 | Hold | 3 | 215 |
| QCOM | passed | 93.0 | Accumulate | 25 | 183 |
| MU | passed | 94.0 | Hold | 9 | 242 |
| MRVL | passed | 94.0 | Hold | 12 | 66 |
| ANET | passed | 94.0 | Hold | 8 | 177 |
| DDOG | passed | 95.0 | Hold | 0 | 65 |
| MDB | passed | 94.0 | Hold | 5 | 83 |
| SNOW | passed | 94.0 | Tactical Underweight | 1 | 62 |
| CRWD | passed | 94.0 | Hold | 2 | 46 |
| NET | passed | 95.0 | Hold | 0 | 62 |
| PANW | passed | 91.0 | Hold | 49 | 198 |
| ZS | passed | 95.0 | Hold | 0 | 76 |
| CRM | passed | 93.0 | Hold | 25 | 336 |
| NOW | passed | 94.0 | Hold | 15 | 190 |
| ORCL | passed | 94.0 | Hold | 3 | 189 |
| ADBE | passed | 93.0 | Hold | 22 | 229 |
| INTU | passed | 91.0 | Hold | 45 | 238 |
| UBER | passed | 94.0 | Hold | 5 | 68 |
| TSLA | passed | 93.0 | Hold | 23 | 213 |
| PLTR | passed | 94.0 | Hold | 1 | 56 |
| IBM | passed | 94.0 | Hold | 9 | 145 |
| NFLX | passed | 94.0 | Hold | 7 | 288 |

## Best / Worst Result

- Best result: `DDOG, NET, ZS` with quality `95.0`.
- Weakest result: `PANW, INTU` with quality `91.0`.

## Data Quality Ranking

### Top 5 Weakest Data Quality

- `PANW`: quality `91.0`, true disagreements `49`, validation errors `0`, audit errors `0`
- `INTU`: quality `91.0`, true disagreements `45`, validation errors `0`, audit errors `0`
- `NVDA`: quality `93.0`, true disagreements `29`, validation errors `0`, audit errors `0`
- `QCOM`: quality `93.0`, true disagreements `25`, validation errors `0`, audit errors `0`
- `CRM`: quality `93.0`, true disagreements `25`, validation errors `0`, audit errors `0`

### Top 5 Best Data Quality

- `DDOG`: quality `95.0`, true disagreements `0`, validation errors `0`, audit errors `0`
- `NET`: quality `95.0`, true disagreements `0`, validation errors `0`, audit errors `0`
- `ZS`: quality `95.0`, true disagreements `0`, validation errors `0`, audit errors `0`
- `SNOW`: quality `94.0`, true disagreements `1`, validation errors `0`, audit errors `0`
- `PLTR`: quality `94.0`, true disagreements `1`, validation errors `0`, audit errors `0`

## Source Ingestion Sufficiency

- Tickers where `source_ingestion_mode` was not sufficient: `none`
- Recommendation: `pilotfaehig`

## Production Readiness Assessment

- `source_ingestion_mode` looks operational for controlled pilots after reconciliation hardening.
- Remaining production gaps: real EarningsCalendar wiring, IR/guidance ingestion coverage, and post-generation Markdown audit in the default source-ingestion path.

## Artifact Check

- All required dashboard artifact paths are present.
