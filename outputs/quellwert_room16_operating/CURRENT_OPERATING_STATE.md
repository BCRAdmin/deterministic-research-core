# Current Operating State

- Generated at: `2026-05-20T15:18:45+02:00`
- Batch: `guardrail_coverage_batch_004_ir_coverage`
- Operating status: `GREEN Operating Baseline`
- Current-period coverage: `32/32`
- Price basis date: `2026-05-15`
- Vivi Review: `pass`
- Public output: Promotion-gated; no unattended public release

## Outcome State

- `OUTCOME_1D_REVIEW`: computed
- Computed rows: `37`
- Pending rows: `0`
- False pass flags: `0`
- 1D provisional false-block watchlist: `MDB`, `NOW`, `RKLB`, `ZS`
- 1D policy: watchlist-only; no calibration, guard, rating, or report change
- Next hard outcome window: `5D` on `2026-05-22`
- `OUTCOME_5D_REVIEW`: pending until local CSVs contain source-returned `2026-05-22` ticker and benchmark closes

## Data-Ops P0 Replacement

- Sources added: `IONQ`, `NVDA`, `QBTS`, `QCOM`, `RGTI` direct IR/Earnings sources
- Bundle: `outputs/quellwert_room16_operating/chatgpt_data_ops_p0_replacement_bundle.zip`
- Artifact consistency: `clean` (`0` errors)
- Status changes: none
- Publishability changes: none
- All five remain `manual_review`, `publishable=false`, `public_ready=false`

| Ticker | Data confidence | Status | External display | Remaining source gaps |
|---|---:|---|---|---|
| IONQ | 72 -> 75 | manual_review | Manual Review / Hold Pending FCF and Execution Evidence | company-defined FCF; confirmed next earnings date |
| NVDA | 60 -> 67 | manual_review | Accumulate | confirmed next earnings date; latest FY2027 actuals after next report |
| QBTS | 75 -> 75 | manual_review | Manual Review / Preliminary Underweight | company-defined FCF; full 10-Q cash-flow detail in direct release fixture; confirmed next earnings date |
| QCOM | 72 -> 49 | manual_review | Hold Pending FCF Support | company-defined FCF label/reconciled TTM FCF; confirmed next earnings date; main-body use of new QCT/QTL/current-period KPIs remains incomplete |
| RGTI | 69 -> 69 | manual_review | Manual Review / Preliminary Underweight | company-defined FCF; customer/order materiality beyond disclosed Novera shipments; confirmed next earnings date |

## Ticker Notes

- QCOM remains `manual_review / Hold Pending FCF Support`; `MISSING_FCF_SUPPORT_FOR_ACCUMULATE` remains active because company-defined or reconciled TTM FCF support is still absent, and current-KPI report usage remains incomplete.
- RGTI remains `manual_review / Manual Review / Preliminary Underweight`; Deep-Tech archetype `SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL` is retained.

## Blockers And Gates

- No system-level blockers.
- Remaining blockers are ticker-level evidence gaps.
- Public output remains blocked unless the Promotion Gate is explicitly satisfied.
- No guard, rating, calibration, or report changes are authorized from 1D/5D monitoring alone.
