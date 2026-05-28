# Outcome 5D Triage Summary

- Batch: guardrail_coverage_batch_004_ir_coverage
- Source: OUTCOME_5D_REVIEW.md/json
- Window: 5D (2026-05-15 to 2026-05-22)
- Status: computed
- Computed rows: 37 (32 unique tickers)
- Pending rows: 0
- False pass flags: 1 rows / 1 unique tickers (AVGO)
- False block flags: 3 rows / 3 unique tickers (NOW, RKLB, ZS)
- Benchmark coverage: complete (37/37 computed rows)
- Data quality: complete_for_5d; no missing price tickers; no missing benchmark tickers

Top lists are deduped by ticker and prefer manual_focus_guardrail_final_check where a focus overlay exists. The computed row count preserves the source row count.

## Top 10 Positive Excess Returns

| Ticker | Original status | Rating / external display | 5D return % | Benchmark return % | Excess % | Interpretation |
|---|---|---|---:|---:|---:|---|
| RGTI | manual_review | Manual Review / Preliminary Underweight | 48.0112 | 1.2145 | 46.7967 | worth monitoring |
| QBTS | manual_review | Manual Review / Preliminary Underweight | 44.4717 | 1.2145 | 43.2572 | worth monitoring |
| ASTS | manual_review | Manual Review / Preliminary Underweight | 26.5209 | 1.2145 | 25.3064 | worth monitoring |
| IONQ | manual_review | Manual Review / Hold Pending FCF and Execution Evidence | 22.5024 | 1.2145 | 21.2879 | worth monitoring |
| QCOM | manual_review | Hold Pending FCF Support | 18.1994 | 3.5913 | 14.6081 | worth monitoring |
| ZS | manual_review | Hold | 13.2381 | 1.2145 | 12.0236 | possible false block |
| CRWD | manual_review | Hold | 11.6786 | 1.2145 | 10.4641 | worth monitoring |
| NET | manual_review | Hold | 9.4199 | 1.2145 | 8.2054 | worth monitoring |
| SNOW | passed | Hold with Underweight Bias | 9.3542 | 1.2145 | 8.1397 | worth monitoring |
| RKLB | manual_review | Manual Review / Hold Pending FCF and Execution Evidence | 8.8082 | 1.2145 | 7.5937 | possible false block |

## Top 10 Negative Excess Returns

| Ticker | Original status | Rating / external display | 5D return % | Benchmark return % | Excess % | Interpretation |
|---|---|---|---:|---:|---:|---|
| NVDA | manual_review | Hold | -4.4337 | 3.5913 | -8.0250 | worth monitoring |
| AVGO | passed | Hold | -2.5988 | 3.5913 | -6.1901 | possible false pass |
| GOOGL | passed | Hold | -3.4805 | 1.2145 | -4.6950 | worth monitoring |
| LCID | manual_review | Underweight | -3.3113 | 0.8753 | -4.1866 | worth monitoring |
| MSFT | passed | Hold | -0.7940 | 1.2145 | -2.0085 | normal noise |
| META | passed | Hold | -0.6463 | 1.2145 | -1.8608 | normal noise |
| PLUG | manual_review | Hold | 0.0000 | 0.8753 | -0.8753 | normal noise |
| AMZN | manual_review | Hold | 0.8253 | 1.2145 | -0.3892 | normal noise |
| MU | manual_review | Hold | 3.6348 | 3.5913 | 0.0435 | normal noise |
| NFLX | passed | Hold | 1.8157 | 1.2145 | 0.6012 | normal noise |

## Passed Reports Check

- Strong negative threshold: <= -3.0000% excess.
- Passed tickers with strong negative 5D excess:
- AVGO
- Possible false pass suspicion: yes
- Action: no action unless repeated at 10D/20D.

## Manual-Review Missed-Opportunity Watchlist

| Ticker | 5D excess % | Status | Recommended action |
|---|---:|---|---|
| MDB | 3.2608 | monitor | keep monitoring; confirm again at 10D |
| NOW | 6.2116 | confirmed_outperformance | keep on watchlist; inspect manual_review reason + data ops |
| RKLB | 7.5937 | confirmed_outperformance | keep on watchlist; inspect manual_review reason + data ops |
| ZS | 12.0236 | confirmed_outperformance | keep on watchlist; inspect manual_review reason + data ops |

## No-Change Policy

- No calibration from 5D alone.
- No guard change from 5D alone.
- No rating change from 5D alone.
- No report change from 5D alone.
