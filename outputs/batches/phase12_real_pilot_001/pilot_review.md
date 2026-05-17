# Phase 12 Real Pilot Review

- Batch ID: `phase12_real_pilot_001`
- As-of / price basis date: `2026-05-05`
- Source mode: `source_ingestion_mode`
- Tickers: `10`
- Price source: Yahoo chart API normalized to CSV under `outputs/source_inputs/phase12_real_pilot_001/prices`
- SEC source: SEC CompanyFacts under `outputs/source_inputs/phase12_real_pilot_001/sec_companyfacts`

## Status Summary

- Passed: `10`
- Repaired: `0`
- Manual review: `0`
- Failed: `0`
- Average quality score: `95.0`
- Repair rate: `0.0%`

## Ticker Results

| Ticker | Status | Quality | Rating | Benchmark | Key Artifacts |
|---|---|---:|---|---|---|
| AMZN | passed | 95.0 | Accumulate | QQQ | 12 files |
| NVDA | passed | 95.0 | Hold | SMH | 12 files |
| DDOG | passed | 95.0 | Accumulate | QQQ | 12 files |
| MDB | passed | 95.0 | Hold | QQQ | 12 files |
| MSFT | passed | 95.0 | Hold | QQQ | 12 files |
| GOOGL | passed | 95.0 | Accumulate | QQQ | 12 files |
| META | passed | 95.0 | Hold | QQQ | 12 files |
| CRWD | passed | 95.0 | Accumulate | QQQ | 12 files |
| SNOW | passed | 95.0 | Hold | QQQ | 12 files |
| PLTR | passed | 95.0 | Hold | QQQ | 12 files |

## Frequent Audit Issues

- none; current generated reports do not run a post-generation Markdown audit in this source-ingestion path

## Frequent Validation Issues

- `EARNINGS_DATE_UNAVAILABLE`: 10

## Frequent Evidence Problems

- none

## Frequent Reconciliation Warnings

- `SOURCE_VALUE_DISAGREEMENT`: 3687

## Best / Worst Result

- Best result: `AMZN, NVDA, DDOG, MDB, MSFT, GOOGL, META, CRWD, SNOW, PLTR` with quality `95.0`.
- Weakest result: `AMZN, NVDA, DDOG, MDB, MSFT, GOOGL, META, CRWD, SNOW, PLTR` with quality `95.0`.

## Production Readiness Assessment

- `source_ingestion_mode` is operational for this controlled pilot: all 10 tickers produced price CSVs, SEC CompanyFacts, report manifests, quality scores, evidence ledgers, reconciliation reports and final reports without breaking the batch.
- It is not production-ready as an unattended public-report path yet. The pilot exposes reconciliation noise and missing event/news/IR adapters that should stay visible in dashboard review.

## Bugs / Missing Data Adapters

- Reconciliation warning volume is too high: `SOURCE_VALUE_DISAGREEMENT` fires thousands of times because SEC CompanyFacts include multiple frames/durations for similar fiscal labels. Period/frame resolution needs tightening before these warnings are decision-grade.
- Earnings calendar is not wired for real source ingestion in this pilot; every ticker has `EARNINGS_DATE_UNAVAILABLE`.
- IR release/guidance extraction was not exercised; pilot used SEC CompanyFacts plus price CSV only.
- Post-generation Markdown audit is not part of the default `run_pipeline.py` source-ingestion path here, so audit issue frequency is empty rather than a true clean-audit signal.
- Price input is CSV generated from Yahoo chart API for the pilot, not a first-class configured production price provider with provenance/cost/rate-limit policy.

## Artifact Check

- All required per-ticker artifacts are present through dashboard artifact paths.
