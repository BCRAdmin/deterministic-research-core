# Coverage Recovery Plan

- Batch: `guardrail_coverage_batch_003_current_research`
- Short-term repairable: `17`
- Intentionally excluded: `9`
- Highest priority: `RGTI, IONQ, QBTS, RKLB, ASTS, ACHR, JOBY, RIVN, LCID, PLUG`

| Ticker | Bucket | Fixability | Priority | Include 003 | Action |
|---|---|---|---|---|---|
| TSM | SEMICONDUCTOR_AI_INFRA OR SEMICONDUCTOR_CYCLICAL | unsupported_skip | P3 | no | Exclude from Batch 003 until foreign-issuer/ADR support is explicit. |
| ASML | SEMICONDUCTOR_AI_INFRA OR SEMICONDUCTOR_CYCLICAL | unsupported_skip | P3 | no | Exclude from Batch 003 until foreign-issuer/ADR support is explicit. |
| RGTI | SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL | quick_fix | P0 | yes | Fetch fresh price CSV, CIK mapping and SEC CompanyFacts; run with current_research gates active. |
| IONQ | SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL | quick_fix | P0 | yes | Fetch fresh price CSV, CIK mapping and SEC CompanyFacts; run with current_research gates active. |
| QBTS | SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL | quick_fix | P0 | yes | Fetch fresh price CSV, CIK mapping and SEC CompanyFacts; run with current_research gates active. |
| QUBT | SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL / UNKNOWN MANUAL_REVIEW | keep_manual_review | P2 | no | Keep documented for later coverage expansion; exclude from Batch 003 if target universe is already full. |
| SOUN | SPECULATIVE_AI_STORY_STOCK / UNKNOWN MANUAL_REVIEW | keep_manual_review | P2 | no | Keep documented for later coverage expansion; exclude from Batch 003 if target universe is already full. |
| BBAI | SPECULATIVE_AI_STORY_STOCK / UNKNOWN MANUAL_REVIEW | keep_manual_review | P2 | no | Keep documented for later coverage expansion; exclude from Batch 003 if target universe is already full. |
| RKLB | EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH | needs_ir_fixture | P0 | yes | Fetch fresh price/SEC coverage and attach existing sourced RKLB company-IR current-period fixture; keep manual_review if execution/FCF evidence is incomplete. |
| ASTS | EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH / DISTRESSED_CAPITAL_INTENSIVE | needs_ir_fixture | P0 | yes | Fetch fresh price/SEC coverage; run as manual_review/data_gap unless a sourced IR/current-period fixture exists. |
| ACHR | EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH / DISTRESSED_CAPITAL_INTENSIVE | needs_ir_fixture | P0 | yes | Fetch fresh price/SEC coverage; run as manual_review/data_gap unless a sourced IR/current-period fixture exists. |
| JOBY | EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH / DISTRESSED_CAPITAL_INTENSIVE | needs_ir_fixture | P0 | yes | Fetch fresh price/SEC coverage; run as manual_review/data_gap unless a sourced IR/current-period fixture exists. |
| RIVN | EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH / DISTRESSED_CAPITAL_INTENSIVE | quick_fix | P1 | yes | Fetch fresh price CSV, CIK mapping and SEC CompanyFacts; run with current_research gates active. |
| LCID | EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH / DISTRESSED_CAPITAL_INTENSIVE | quick_fix | P1 | yes | Fetch fresh price CSV, CIK mapping and SEC CompanyFacts; run with current_research gates active. |
| PLUG | EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH / DISTRESSED_CAPITAL_INTENSIVE | quick_fix | P1 | yes | Fetch fresh price CSV, CIK mapping and SEC CompanyFacts; run with current_research gates active. |
| PYPL | TURNAROUND / BUSINESS_MODEL_PRESSURE / STANDARD_WITH_RISK | keep_manual_review | P2 | no | Keep documented for later coverage expansion; exclude from Batch 003 if target universe is already full. |
| SNAP | TURNAROUND / BUSINESS_MODEL_PRESSURE / STANDARD_WITH_RISK | keep_manual_review | P2 | no | Keep documented for later coverage expansion; exclude from Batch 003 if target universe is already full. |
| WBA | TURNAROUND / BUSINESS_MODEL_PRESSURE / STANDARD_WITH_RISK | keep_manual_review | P2 | no | Keep documented for later coverage expansion; exclude from Batch 003 if target universe is already full. |
| PARA | TURNAROUND / BUSINESS_MODEL_PRESSURE / STANDARD_WITH_RISK | keep_manual_review | P2 | no | Keep documented for later coverage expansion; exclude from Batch 003 if target universe is already full. |
