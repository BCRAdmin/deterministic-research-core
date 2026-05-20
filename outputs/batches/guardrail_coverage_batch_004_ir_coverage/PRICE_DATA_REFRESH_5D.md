# Price Data Refresh 5D

- Batch: `guardrail_coverage_batch_004_ir_coverage`
- Generated at: `2026-05-20T15:18:45+02:00`
- Price basis date: `2026-05-15`
- Target 5D outcome date: `2026-05-22`
- Current session date: `2026-05-20`
- Provider attempted: none; local CSV coverage check only
- Policy: no synthetic prices, no replacement end date, no forward-fill

## Status

- `OUTCOME_5D_REVIEW`: pending
- 5D evaluable: `false`
- Price latest date range: `2026-05-19` to `2026-05-19`
- Benchmark latest date range: `2026-05-19` to `2026-05-19`
- Missing ticker target-date bars: `32`
- Missing benchmark target-date bars: `3`

The local CSVs do not contain source-returned rows dated `2026-05-22`. Because the target date is after the current session date, 5D cannot be computed without inventing prices or using a replacement end date, both of which are disallowed.

## Benchmark Coverage

| Benchmark | Latest local date | Target date present | Status |
|---|---|---|---|
| QQQ | 2026-05-19 | no | not_ready |
| SMH | 2026-05-19 | no | not_ready |
| SPY | 2026-05-19 | no | not_ready |

## Ticker Coverage

| Ticker | Benchmark | Latest local date | Target date present | Status |
|---|---|---|---|---|
| GOOGL | QQQ | 2026-05-19 | no | not_ready |
| SNOW | QQQ | 2026-05-19 | no | not_ready |
| MSFT | QQQ | 2026-05-19 | no | not_ready |
| AAPL | QQQ | 2026-05-19 | no | not_ready |
| META | QQQ | 2026-05-19 | no | not_ready |
| AMZN | QQQ | 2026-05-19 | no | not_ready |
| NFLX | QQQ | 2026-05-19 | no | not_ready |
| CRM | QQQ | 2026-05-19 | no | not_ready |
| DDOG | QQQ | 2026-05-19 | no | not_ready |
| NOW | QQQ | 2026-05-19 | no | not_ready |
| MDB | QQQ | 2026-05-19 | no | not_ready |
| NET | QQQ | 2026-05-19 | no | not_ready |
| ZS | QQQ | 2026-05-19 | no | not_ready |
| CRWD | QQQ | 2026-05-19 | no | not_ready |
| PANW | QQQ | 2026-05-19 | no | not_ready |
| NVDA | SMH | 2026-05-19 | no | not_ready |
| AMD | SMH | 2026-05-19 | no | not_ready |
| AVGO | SMH | 2026-05-19 | no | not_ready |
| QCOM | SMH | 2026-05-19 | no | not_ready |
| MU | SMH | 2026-05-19 | no | not_ready |
| MRVL | SMH | 2026-05-19 | no | not_ready |
| INTC | SMH | 2026-05-19 | no | not_ready |
| RGTI | QQQ | 2026-05-19 | no | not_ready |
| IONQ | QQQ | 2026-05-19 | no | not_ready |
| QBTS | QQQ | 2026-05-19 | no | not_ready |
| RKLB | QQQ | 2026-05-19 | no | not_ready |
| ASTS | QQQ | 2026-05-19 | no | not_ready |
| ACHR | QQQ | 2026-05-19 | no | not_ready |
| JOBY | QQQ | 2026-05-19 | no | not_ready |
| RIVN | QQQ | 2026-05-19 | no | not_ready |
| LCID | QQQ | 2026-05-19 | no | not_ready |
| PLUG | QQQ | 2026-05-19 | no | not_ready |

## Decision

- Do not compute `OUTCOME_5D_REVIEW` yet.
- Do not create watchlist/triage/Vivi 5D review artifacts yet.
- Do not change guards, ratings, calibration, or reports.
- Re-run only after local ticker and benchmark CSVs contain real source-returned closes for `2026-05-22`.
