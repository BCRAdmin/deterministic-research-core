# Data Availability Root Cause - guardrail_coverage_batch_001

- Generated at: `2026-05-17T01:17:18Z`
- Data unavailable count: `19`
- Count by root cause: `{'local_file_missing': 19}`
- Count by missing input: `{'missing_price_data': 19, 'missing_SEC_companyfacts': 19, 'missing_CIK_mapping': 19, 'missing_IR_fixture': 19, 'missing_earnings_current_period_evidence': 19, 'missing_news_vendor_fallback': 19, 'missing_benchmark_data': 0}`

| Ticker | Bucket | Missing Price | Missing CIK | Missing Companyfacts | Missing IR | Root Cause | Priority | Recommended Fix |
|---|---|---|---|---|---|---|---|---|
| TSM | SEMICONDUCTOR_AI_INFRA OR SEMICONDUCTOR_CYCLICAL | yes | yes | yes | yes | local_file_missing | P2 | Add auditable local price CSV and verify CIK/companyfacts coverage for TSM. |
| ASML | SEMICONDUCTOR_AI_INFRA OR SEMICONDUCTOR_CYCLICAL | yes | yes | yes | yes | local_file_missing | P2 | Add auditable local price CSV and verify CIK/companyfacts coverage for ASML. |
| RGTI | SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL | yes | yes | yes | yes | local_file_missing | P1 | Add auditable price CSV plus SEC/IR or explicit vendor-only current-period evidence before rerun. |
| IONQ | SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL | yes | yes | yes | yes | local_file_missing | P1 | Add auditable price CSV plus SEC/IR or explicit vendor-only current-period evidence before rerun. |
| QBTS | SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL | yes | yes | yes | yes | local_file_missing | P1 | Add auditable price CSV plus SEC/IR or explicit vendor-only current-period evidence before rerun. |
| QUBT | SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL / UNKNOWN MANUAL_REVIEW | yes | yes | yes | yes | local_file_missing | P1 | Add auditable price CSV plus SEC/IR or explicit vendor-only current-period evidence before rerun. |
| SOUN | SPECULATIVE_AI_STORY_STOCK / UNKNOWN MANUAL_REVIEW | yes | yes | yes | yes | local_file_missing | P2 | Add auditable local price CSV and verify CIK/companyfacts coverage for SOUN. |
| BBAI | SPECULATIVE_AI_STORY_STOCK / UNKNOWN MANUAL_REVIEW | yes | yes | yes | yes | local_file_missing | P2 | Add auditable local price CSV and verify CIK/companyfacts coverage for BBAI. |
| RKLB | EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH | yes | yes | yes | yes | local_file_missing | P1 | Add auditable price CSV plus SEC/IR or explicit vendor-only current-period evidence before rerun. |
| ASTS | EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH / DISTRESSED_CAPITAL_INTENSIVE | yes | yes | yes | yes | local_file_missing | P1 | Add auditable price CSV plus SEC/IR or explicit vendor-only current-period evidence before rerun. |
| ACHR | EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH / DISTRESSED_CAPITAL_INTENSIVE | yes | yes | yes | yes | local_file_missing | P1 | Add auditable price CSV plus SEC/IR or explicit vendor-only current-period evidence before rerun. |
| JOBY | EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH / DISTRESSED_CAPITAL_INTENSIVE | yes | yes | yes | yes | local_file_missing | P1 | Add auditable price CSV plus SEC/IR or explicit vendor-only current-period evidence before rerun. |
| RIVN | EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH / DISTRESSED_CAPITAL_INTENSIVE | yes | yes | yes | yes | local_file_missing | P1 | Add auditable price CSV plus SEC/IR or explicit vendor-only current-period evidence before rerun. |
| LCID | EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH / DISTRESSED_CAPITAL_INTENSIVE | yes | yes | yes | yes | local_file_missing | P1 | Add auditable price CSV plus SEC/IR or explicit vendor-only current-period evidence before rerun. |
| PLUG | EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH / DISTRESSED_CAPITAL_INTENSIVE | yes | yes | yes | yes | local_file_missing | P1 | Add auditable price CSV plus SEC/IR or explicit vendor-only current-period evidence before rerun. |
| PYPL | TURNAROUND / BUSINESS_MODEL_PRESSURE / STANDARD_WITH_RISK | yes | yes | yes | yes | local_file_missing | P2 | Add auditable local price CSV and verify CIK/companyfacts coverage for PYPL. |
| SNAP | TURNAROUND / BUSINESS_MODEL_PRESSURE / STANDARD_WITH_RISK | yes | yes | yes | yes | local_file_missing | P2 | Add auditable local price CSV and verify CIK/companyfacts coverage for SNAP. |
| WBA | TURNAROUND / BUSINESS_MODEL_PRESSURE / STANDARD_WITH_RISK | yes | yes | yes | yes | local_file_missing | P2 | Add auditable local price CSV and verify CIK/companyfacts coverage for WBA. |
| PARA | TURNAROUND / BUSINESS_MODEL_PRESSURE / STANDARD_WITH_RISK | yes | yes | yes | yes | local_file_missing | P2 | Add auditable local price CSV and verify CIK/companyfacts coverage for PARA. |
