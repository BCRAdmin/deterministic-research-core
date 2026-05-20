# Outcome Watchlist Carry-Forward

- Batch: guardrail_coverage_batch_004_ir_coverage
- Source: OUTCOME_1D_TRIAGE_SUMMARY.md/json
- Computed rows: 37
- Pending rows: 0
- False pass flags: 0
- Provisional false block watchlist: MDB, NOW, RKLB, ZS
- Benchmark coverage: complete

## Watchlist Pro Ticker

| Ticker | Original status | Original rating / external display | Original manual_review reason | 1D return % | Benchmark return % | Excess % | Why flagged | 5D confirm | 5D clear | Data needed | Do not change until |
|---|---|---|---|---:|---:|---:|---|---|---|---|---|
| MDB | manual_review | Hold | price date before as-of date; earnings date unavailable; source frame variant ignored; period type mismatch ignored; true-source value disagreement | 5.7150 | -0.4302 | 6.1452 | 1D manual_review_missed_opportunity=true with positive benchmark-adjusted excess return of 6.1452%. | Concern is confirmed for monitoring if benchmark-adjusted outperformance remains meaningfully positive at 5D and the original manual_review reason does not resolve through data freshness or source reconciliation. | Concern is cleared or downgraded if 5D excess normalizes/reverses, or if the original manual_review reason remains a valid evidence/data-quality block despite the 1D move. | 5D close for ticker and benchmark on 2026-05-22; 10D follow-up if 5D remains positive; current-period date/price freshness confirmation; source-frame and true-source reconciliation | 2026-06-01 (10D minimum for any calibration/guard review; no rating/report change from this watchlist) |
| NOW | manual_review | Hold | price date before as-of date; earnings date unavailable; source frame variant ignored; period type mismatch ignored; true-source value disagreement | 8.7830 | -0.4302 | 9.2132 | 1D manual_review_missed_opportunity=true with positive benchmark-adjusted excess return of 9.2132%. | Concern is confirmed for monitoring if benchmark-adjusted outperformance remains meaningfully positive at 5D and the original manual_review reason does not resolve through data freshness or source reconciliation. | Concern is cleared or downgraded if 5D excess normalizes/reverses, or if the original manual_review reason remains a valid evidence/data-quality block despite the 1D move. | 5D close for ticker and benchmark on 2026-05-22; 10D follow-up if 5D remains positive; current-period date/price freshness confirmation; source-frame and true-source reconciliation | 2026-06-01 (10D minimum for any calibration/guard review; no rating/report change from this watchlist) |
| RKLB | manual_review | Manual Review / Hold Pending FCF and Execution Evidence | extreme valuation requires review; early-commercial capital-intensive tech manual-review profile; price date before as-of date; earnings date unavailable; period type mismatch ignored; true-source value disagreement; source frame variant ignored | 5.1214 | -0.4302 | 5.5517 | 1D manual_review_missed_opportunity=true with positive benchmark-adjusted excess return of 5.5517%. | Concern is confirmed for monitoring if benchmark-adjusted outperformance remains meaningfully positive at 5D and the original manual_review reason does not resolve through data freshness or source reconciliation. | Concern is cleared or downgraded if 5D excess normalizes/reverses, or if the original manual_review reason remains a valid evidence/data-quality block despite the 1D move. | 5D close for ticker and benchmark on 2026-05-22; 10D follow-up if 5D remains positive; current-period date/price freshness confirmation; source-frame and true-source reconciliation; FCF/execution evidence and valuation context before any later guard review | 2026-06-01 (10D minimum for any calibration/guard review; no rating/report change from this watchlist) |
| ZS | manual_review | Hold | price date before as-of date; earnings date unavailable; period type mismatch ignored; source frame variant ignored | 8.4694 | -0.4302 | 8.8996 | 1D manual_review_missed_opportunity=true with positive benchmark-adjusted excess return of 8.8996%. | Concern is confirmed for monitoring if benchmark-adjusted outperformance remains meaningfully positive at 5D and the original manual_review reason does not resolve through data freshness or source reconciliation. | Concern is cleared or downgraded if 5D excess normalizes/reverses, or if the original manual_review reason remains a valid evidence/data-quality block despite the 1D move. | 5D close for ticker and benchmark on 2026-05-22; 10D follow-up if 5D remains positive; current-period date/price freshness confirmation; source-frame and true-source reconciliation | 2026-06-01 (10D minimum for any calibration/guard review; no rating/report change from this watchlist) |

## Escalation Rules

- 1D outperformance alone does not justify guard change.
- If still outperforming at 5D: inspect manual_review reason.
- If still outperforming at 10D: classify possible false block.
- If still outperforming at 20D: consider rule/decision calibration review.
- No calibration before 10D minimum.
- No guard change before repeated signal.

## Next Outcome Dates

- 5D: 2026-05-22
- 10D: 2026-06-01
- 20D: 2026-06-15
- 60D: 2026-08-12

## No-Change Policy

- No code change.
- No calibration change.
- No guard change.
- No rating change.
- No report change.
