# Price Data Refresh 5D

- Batch: `guardrail_coverage_batch_004_ir_coverage`
- Generated at: `2026-06-15T12:16:17Z`
- Price basis date: `2026-05-15`
- Target 5D outcome date: `2026-05-22`
- Current session date: `2026-06-15`
- Provider attempted: Local CSV coverage check (no refresh executed)
- Policy: no synthetic prices, no replacement end date, no forward-fill

## Status

- `OUTCOME_5D_REVIEW`: ready_to_compute
- 5D evaluable: `true`
- Price latest date range: `2026-05-22` to `2026-05-22`
- Benchmark latest date range: `2026-05-22` to `2026-05-22`
- Missing ticker target-date bars: `0`
- Missing benchmark target-date bars: `0`

All local CSVs contain source-returned rows dated `2026-05-22`. 5D outcome is evaluable without synthetic prices, replacement end dates, or forward-fill.

## Benchmark Coverage

| Benchmark | Latest local date | Target date present | Status |
|---|---|---|---|
| QQQ | 2026-05-22 | yes | ready |
| SMH | 2026-05-22 | yes | ready |
| SPY | 2026-05-22 | yes | ready |

## Ticker Coverage

| Ticker | Benchmark | Latest local date | Target date present | Status |
|---|---|---|---|---|
| GOOGL | QQQ | 2026-05-22 | yes | ready |
| SNOW | QQQ | 2026-05-22 | yes | ready |
| MSFT | QQQ | 2026-05-22 | yes | ready |
| AAPL | QQQ | 2026-05-22 | yes | ready |
| META | QQQ | 2026-05-22 | yes | ready |
| AMZN | QQQ | 2026-05-22 | yes | ready |
| NFLX | QQQ | 2026-05-22 | yes | ready |
| CRM | QQQ | 2026-05-22 | yes | ready |
| DDOG | QQQ | 2026-05-22 | yes | ready |
| NOW | QQQ | 2026-05-22 | yes | ready |
| MDB | QQQ | 2026-05-22 | yes | ready |
| NET | QQQ | 2026-05-22 | yes | ready |
| ZS | QQQ | 2026-05-22 | yes | ready |
| CRWD | QQQ | 2026-05-22 | yes | ready |
| PANW | QQQ | 2026-05-22 | yes | ready |
| NVDA | SMH | 2026-05-22 | yes | ready |
| AMD | SMH | 2026-05-22 | yes | ready |
| AVGO | SMH | 2026-05-22 | yes | ready |
| QCOM | SMH | 2026-05-22 | yes | ready |
| MU | SMH | 2026-05-22 | yes | ready |
| MRVL | SMH | 2026-05-22 | yes | ready |
| INTC | SMH | 2026-05-22 | yes | ready |
| RGTI | QQQ | 2026-05-22 | yes | ready |
| IONQ | QQQ | 2026-05-22 | yes | ready |
| QBTS | QQQ | 2026-05-22 | yes | ready |
| RKLB | QQQ | 2026-05-22 | yes | ready |
| ASTS | QQQ | 2026-05-22 | yes | ready |
| ACHR | QQQ | 2026-05-22 | yes | ready |
| JOBY | QQQ | 2026-05-22 | yes | ready |
| RIVN | SPY | 2026-05-22 | yes | ready |
| LCID | SPY | 2026-05-22 | yes | ready |
| PLUG | SPY | 2026-05-22 | yes | ready |

## Decision

- Price prerequisite met; 5D computation may proceed.
- Do not change guards, ratings, calibration, or reports.
