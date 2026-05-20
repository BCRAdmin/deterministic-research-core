# DATA_OPS_P0_REPLACEMENT_PLAN

Scope: direct IR/Earnings-/SEC source replacements only. No guard, rating, archetype, architecture or report-polish changes.

- Batch config: `outputs/batches/data_ops_p0_replacement_check_config.json`
- Source input root: `outputs/source_inputs/data_ops_p0_replacement_check`
- Generated at: 2026-05-20T00:00:00+02:00
- As-of date for comparable mini-rerun: `2026-05-17`
- SourceRegistry note: direct company releases are registered as `company_ir` authority while fixture payloads retain `source_type=earnings_release`.

| Ticker | Current source status | Desired direct source | Missing fields | Expected manual-review impact | Expected publishability impact | Required source type | Priority | Vega fetch/process | Operator action |
|---|---|---|---|---|---|---|---|---|---|
| IONQ | Batch004 had SEC CompanyFacts current-period support but no direct Q1 2026 IR release fixture; manual-focus corrected archetype to EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH. | https://investors.ionq.com/news/news-details/2026/IonQ-Announces-First-Quarter-2026-Financial-Results/default.aspx | company-defined free cash flow, confirmed next earnings date | Improves current-period revenue, RPO/guidance, cash-burn and SBC evidence; does not remove valuation/FCF/execution manual-review requirement. | No public publishability expected; keep Manual Review / Hold Pending FCF and Execution Evidence. | earnings release, 10-Q / 10-K | P0 | yes | no |
| NVDA | Batch004/manual-focus had SEC CompanyFacts and stale/no direct FY2026 company-defined FCF fixture, causing source disagreement and financial sanity review. | https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Announces-Financial-Results-for-Fourth-Quarter-and-Fiscal-2026/ | latest Q1 FY2027 actuals after next report date, confirmed next earnings date | Should improve direct FCF, annual revenue, Data Center and guidance evidence; valuation/source-disagreement review may remain. | Could become a stronger internal candidate, but no public-ready without promotion. | earnings release, IR presentation | P0 | yes | no |
| QBTS | Batch004/manual-focus had SEC CompanyFacts and no direct Q1 2026 D-Wave release fixture. | https://www.dwavequantum.com/company/newsroom/press-release/d-wave-reports-first-quarter-2026-results/ | company-defined free cash flow, cash-flow statement detail from 10-Q, confirmed next earnings date | Adds current revenue, bookings, RPO, cash and roadmap evidence; deep-tech manual review should remain. | No public publishability expected; speculative deep-tech remains manual review. | earnings release, 10-Q / 10-K | P0 | yes | no |
| QCOM | Manual-focus baseline correctly shows manual_review / Hold Pending FCF Support because FCF support was not reconciled as primary/company-defined evidence. | https://s204.q4cdn.com/645488518/files/doc_financials/2026/q2/FY2026-2nd-Quarter-Earnings-Release.pdf | company-defined FCF label, confirmed next earnings date | Adds direct OCF, capex, QCT/QTL segment and guidance evidence; keeps Hold Pending FCF Support unless FCF is explicitly reconciled. | No publishability change expected in this pass; no plain Accumulate without FCF support. | earnings release, 10-Q / 10-K | P0 | yes | no |
| RGTI | Batch004/manual-focus had SEC CompanyFacts but no direct Q1 2026 Rigetti earnings-release fixture. | https://investors.rigetti.com/node/11041/pdf | company-defined free cash flow, customer/order materiality beyond disclosed Novera shipments, confirmed next earnings date | Improves direct revenue, operating loss, cash burn, cash/securities and execution evidence; deep-tech manual review should remain. | No public publishability expected; speculative deep-tech remains manual review. | earnings release, 10-Q / 10-K | P0 | yes | no |

## Summary

- P0 direct-source replacements prepared for all five tickers.
- QCOM is intentionally not mapped to company-defined FCF because the release provides OCF/capex but no explicit company-defined FCF label.
- No publishability changes are expected without promotion and reconciled support.
