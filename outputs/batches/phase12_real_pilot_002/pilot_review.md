# Pilot Review - phase12_real_pilot_002

- As-of date: `2026-05-05`
- Batch status: `completed`
- Tickers: `10`

## Status Summary

- Passed: `10`
- Repaired: `0`
- Manual review: `0`
- Failed: `0`
- Average quality score: `93.5`
- Repair rate: `0.0%`

## Before / After Reconciliation

- Old `SOURCE_VALUE_DISAGREEMENT`: `3687`
- New `true_source_disagreements`: `148`
- Ignored frame / period variants: `1393`

## Dashboard Counts

- `audit_errors`: `0`
- `audit_warnings`: `0`
- `canonical_metrics_created`: `9309`
- `evidence_warnings`: `0`
- `ignored_frame_variants`: `1393`
- `reconciliation_warnings`: `148`
- `true_source_disagreements`: `148`
- `validation_errors`: `0`
- `validation_warnings`: `10`

## Ticker Results

| Ticker | Status | Quality | Rating | True Disagreements | Ignored Variants |
|---|---|---:|---|---:|---:|
| AMZN | passed | 94.0 | Accumulate | 17 | 418 |
| NVDA | passed | 90.0 | Hold | 54 | 192 |
| DDOG | passed | 95.0 | Hold | 0 | 64 |
| MDB | passed | 94.0 | Hold | 11 | 77 |
| MSFT | passed | 92.0 | Hold | 34 | 265 |
| GOOGL | passed | 94.0 | Hold | 7 | 103 |
| META | passed | 94.0 | Hold | 18 | 121 |
| CRWD | passed | 94.0 | Hold | 2 | 46 |
| SNOW | passed | 94.0 | Tactical Underweight | 3 | 52 |
| PLTR | passed | 94.0 | Hold | 2 | 55 |

## Best / Worst Result

- Best result: `DDOG` with quality `95.0`.
- Weakest result: `NVDA` with quality `90.0`.

## Production Readiness Assessment

- `source_ingestion_mode` looks operational for controlled pilots after reconciliation hardening.
- Remaining production gaps: real EarningsCalendar wiring, IR/guidance ingestion coverage, and post-generation Markdown audit in the default source-ingestion path.

## Artifact Check

- All required dashboard artifact paths are present.
