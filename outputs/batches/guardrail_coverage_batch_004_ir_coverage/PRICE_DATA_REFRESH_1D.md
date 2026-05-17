# Price Data Refresh 1D

- Batch: guardrail_coverage_batch_004_ir_coverage
- Target price date: 2026-05-18
- Current session date: 2026-05-17
- Status: PENDING
- Provider attempted: Yahoo Finance chart API
- Policy: accept only real source OHLCV rows with date >= 2026-05-18; no synthetic fallback rows.
- Ticker latest min after refresh: 2026-05-15
- Benchmark latest min after refresh: 2026-05-15
- Missing ticker closes: 32
- Missing benchmark closes: 3

## Result

1D outcome remains pending because local CSVs do not contain 2026-05-18 ticker and benchmark closes. No alternate end date was used.

## Missing Tickers

AAPL, ACHR, AMD, AMZN, ASTS, AVGO, CRM, CRWD, DDOG, GOOGL, INTC, IONQ, JOBY, LCID, MDB, META, MRVL, MSFT, MU, NET, NFLX, NOW, NVDA, PANW, PLUG, QBTS, QCOM, RGTI, RIVN, RKLB, SNOW, ZS

## Missing Benchmarks

QQQ, SMH, SPY

## Per-Symbol Refresh Status

| Symbol | Role | Latest before | Latest after | Status | Issue |
|---|---:|---:|---:|---|---|
| AAPL | ticker | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| ACHR | ticker | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| AMD | ticker | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| AMZN | ticker | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| ASTS | ticker | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| AVGO | ticker | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| CRM | ticker | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| CRWD | ticker | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| DDOG | ticker | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| GOOGL | ticker | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| INTC | ticker | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| IONQ | ticker | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| JOBY | ticker | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| LCID | ticker | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| MDB | ticker | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| META | ticker | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| MRVL | ticker | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| MSFT | ticker | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| MU | ticker | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| NET | ticker | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| NFLX | ticker | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| NOW | ticker | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| NVDA | ticker | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| PANW | ticker | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| PLUG | ticker | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| QBTS | ticker | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| QCOM | ticker | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| QQQ | benchmark | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| RGTI | ticker | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| RIVN | ticker | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| RKLB | ticker | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| SMH | benchmark | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| SNOW | ticker | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| SPY | benchmark | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |
| ZS | ticker | 2026-05-15 | 2026-05-15 | pending_no_source_data_for_target_date | target date 2026-05-18 is after current session date 2026-05-17; no valid target-date close accepted |

