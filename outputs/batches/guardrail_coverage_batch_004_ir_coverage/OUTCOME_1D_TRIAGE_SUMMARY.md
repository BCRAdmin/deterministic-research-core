# Outcome 1D Triage Summary

- Batch: guardrail_coverage_batch_004_ir_coverage
- Source: OUTCOME_1D_REVIEW.md/json
- Window: 1D (2026-05-15 to 2026-05-18)
- Status: computed
- Computed rows: 37 (32 unique tickers)
- Pending rows: 0
- False pass flags: 0 rows / 0 unique tickers
- False block flags: 4 rows / 4 unique tickers (MDB, NOW, RKLB, ZS)
- Benchmark coverage: complete (37/37 computed rows)
- Data quality: complete_for_1d; no missing price tickers; no missing benchmark tickers

Top lists are deduped by ticker and prefer manual_focus_guardrail_final_check where a focus overlay exists. The computed row count preserves the source row count.

## Top 10 Positive Excess Returns

| Ticker | Original status | Rating / external display | 1D return % | Benchmark return % | Excess % | Interpretation |
|---|---|---|---:|---:|---:|---|
| NOW | manual_review | Hold | 8.7830 | -0.4302 | 9.2132 | possible false block |
| ZS | manual_review | Hold | 8.4694 | -0.4302 | 8.8996 | possible false block |
| MDB | manual_review | Hold | 5.7150 | -0.4302 | 6.1452 | possible false block |
| RKLB | manual_review | Manual Review / Hold Pending FCF and Execution Evidence | 5.1214 | -0.4302 | 5.5517 | possible false block |
| SNOW | passed | Hold with Underweight Bias | 4.2992 | -0.4302 | 4.7295 | worth monitoring |
| CRWD | manual_review | Hold | 4.1661 | -0.4302 | 4.5963 | worth monitoring |
| ASTS | manual_review | Manual Review / Preliminary Underweight | 3.7767 | -0.4302 | 4.2070 | worth monitoring |
| CRM | passed | Hold | 3.4407 | -0.4302 | 3.8709 | worth monitoring |
| NFLX | passed | Hold | 3.0223 | -0.4302 | 3.4525 | worth monitoring |
| QCOM | manual_review | Hold Pending FCF Support | 1.0670 | -1.8298 | 2.8969 | normal noise |

## Top 10 Negative Excess Returns

| Ticker | Original status | Rating / external display | 1D return % | Benchmark return % | Excess % | Interpretation |
|---|---|---|---:|---:|---:|---|
| PLUG | manual_review | Hold | -8.7302 | -0.0703 | -8.6598 | worth monitoring |
| RGTI | manual_review | Manual Review / Preliminary Underweight | -6.8908 | -0.4302 | -6.4605 | worth monitoring |
| QBTS | manual_review | Manual Review / Preliminary Underweight | -6.3391 | -0.4302 | -5.9088 | worth monitoring |
| LCID | manual_review | Underweight | -5.1324 | -0.0703 | -5.0621 | worth monitoring |
| IONQ | manual_review | Manual Review / Hold Pending FCF and Execution Evidence | -5.0818 | -0.4302 | -4.6516 | worth monitoring |
| MU | manual_review | Hold | -5.9504 | -1.8298 | -4.1206 | worth monitoring |
| RIVN | manual_review | Underweight | -3.1907 | -0.0703 | -3.1204 | worth monitoring |
| MRVL | manual_review | Hold | -4.5000 | -1.8298 | -2.6701 | normal noise |
| ACHR | manual_review | Manual Review / Preliminary Underweight | -2.1488 | -0.4302 | -1.7185 | normal noise |
| AAPL | passed | Accumulate | -0.7961 | -0.4302 | -0.3658 | normal noise |

## Passed Reports Check

- Strong negative threshold: <= -3.0000% excess.
- Passed tickers with strong negative 1D excess:
- None at threshold <= -3.0000% excess.
- Possible false pass suspicion: no
- Action: no action unless repeated at 5D/10D.

## Manual-Review Missed-Opportunity Watchlist

| Ticker | Why manual_review originally | 1D outcome | Challenges guard? | Recommended action |
|---|---|---|---|---|
| NOW | price date before as-of date; earnings date unavailable; source frame variant ignored; period type mismatch ignored; true-source value disagreement | return 8.7830%, benchmark -0.4302%, excess 9.2132%, missed-opportunity flag true | no; 1D is monitoring-only and cannot challenge the guard alone | monitor until 5D, data-ops needed |
| MDB | price date before as-of date; earnings date unavailable; source frame variant ignored; period type mismatch ignored; true-source value disagreement | return 5.7150%, benchmark -0.4302%, excess 6.1452%, missed-opportunity flag true | no; 1D is monitoring-only and cannot challenge the guard alone | monitor until 5D, data-ops needed |
| ZS | price date before as-of date; earnings date unavailable; period type mismatch ignored; source frame variant ignored | return 8.4694%, benchmark -0.4302%, excess 8.8996%, missed-opportunity flag true | no; 1D is monitoring-only and cannot challenge the guard alone | monitor until 5D, data-ops needed |
| RKLB | extreme valuation requires review; early-commercial capital-intensive tech manual-review profile; price date before as-of date; earnings date unavailable; period type mismatch ignored; true-source value disagreement; source frame variant ignored | return 5.1214%, benchmark -0.4302%, excess 5.5517%, missed-opportunity flag true | no; 1D is monitoring-only and cannot challenge the guard alone | monitor until 10D, possible guard review later |

## No-Change Policy

- No calibration from 1D alone.
- No guard change from 1D alone.
- No rating change from 1D alone.
- No report change from 1D alone.

## Next Outcome Windows

- 5D: 2026-05-22
- 10D: 2026-06-01
- 20D: 2026-06-15
- 60D: 2026-08-12
