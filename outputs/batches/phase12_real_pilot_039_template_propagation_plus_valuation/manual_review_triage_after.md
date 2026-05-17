# Manual Review Triage After - phase12_real_pilot_039_template_propagation_plus_valuation

## Summary
- Total manual_review: 26
- Passed: 4 (MSFT, GOOGL, AVGO, SNOW)
- Failed: 0
- Avg quality: 77.53333333333333

## Count By Reason
- QUALITY_BELOW_PUBLISH_GATE: 26
- LOW_CURRENT_PERIOD_KPI_COUNT: 23
- LOW_TICKER_SPECIFIC_KPI_COUNT: 20
- AUDIT_BLOCKER: 12
- TRUE_FINANCIAL_ANOMALY: 7
- FINANCIAL_SANITY_ERROR: 7
- MECHANICAL_RATING_LANGUAGE: 4
- PERIOD_BUG: 2
- LOW_SUBSTANTIVE_CLAIM_COUNT: 2
- FCF_UNAVAILABLE_BLOCK: 1
- HARD_CLAIMS_WITHOUT_EVIDENCE: 1

## Count By Root Cause
- current_period_kpi_coverage_gap: 12
- true_financial_anomaly: 7
- post_audit_or_evidence_blocker: 3
- quality_gate_or_data_coverage_gap: 2
- period_denominator_or_reconciliation_gap: 2

## Manual Review Detail
| Ticker | Quality | Root Cause | Reason Codes | Recommended Next Action |
|---|---:|---|---|---|
| AMZN | 73.0 | true_financial_anomaly | AUDIT_BLOCKER, TRUE_FINANCIAL_ANOMALY, FINANCIAL_SANITY_ERROR, LOW_CURRENT_PERIOD_KPI_COUNT, QUALITY_BELOW_PUBLISH_GATE | Keep manual_review until the anomaly is either explained by IR/SEC evidence or the valuation/action stance is explicitly constrained. |
| META | 78.0 | quality_gate_or_data_coverage_gap | QUALITY_BELOW_PUBLISH_GATE | Review data coverage and quality score drivers before promotion. |
| AAPL | 78.0 | quality_gate_or_data_coverage_gap | QUALITY_BELOW_PUBLISH_GATE | Review data coverage and quality score drivers before promotion. |
| NVDA | 72.0 | true_financial_anomaly | AUDIT_BLOCKER, TRUE_FINANCIAL_ANOMALY, FINANCIAL_SANITY_ERROR, LOW_CURRENT_PERIOD_KPI_COUNT, QUALITY_BELOW_PUBLISH_GATE | Keep manual_review until the anomaly is either explained by IR/SEC evidence or the valuation/action stance is explicitly constrained. |
| AMD | 71.0 | true_financial_anomaly | AUDIT_BLOCKER, TRUE_FINANCIAL_ANOMALY, FINANCIAL_SANITY_ERROR, LOW_CURRENT_PERIOD_KPI_COUNT, LOW_TICKER_SPECIFIC_KPI_COUNT, QUALITY_BELOW_PUBLISH_GATE | Keep manual_review until the anomaly is either explained by IR/SEC evidence or the valuation/action stance is explicitly constrained. |
| INTC | 78.0 | current_period_kpi_coverage_gap | LOW_CURRENT_PERIOD_KPI_COUNT, LOW_TICKER_SPECIFIC_KPI_COUNT, MECHANICAL_RATING_LANGUAGE, QUALITY_BELOW_PUBLISH_GATE | Add real current-period IR/KPI coverage and ticker-specific interpretation; keep manual_review if data is unavailable. |
| QCOM | 78.0 | post_audit_or_evidence_blocker | AUDIT_BLOCKER, LOW_CURRENT_PERIOD_KPI_COUNT, LOW_TICKER_SPECIFIC_KPI_COUNT, MECHANICAL_RATING_LANGUAGE, QUALITY_BELOW_PUBLISH_GATE | Map the hard claim to EvidenceItems or remove the hard number from the main report; keep publish blocked until audit is clean. |
| MU | 71.0 | true_financial_anomaly | AUDIT_BLOCKER, TRUE_FINANCIAL_ANOMALY, FINANCIAL_SANITY_ERROR, LOW_CURRENT_PERIOD_KPI_COUNT, LOW_TICKER_SPECIFIC_KPI_COUNT, QUALITY_BELOW_PUBLISH_GATE | Keep manual_review until the anomaly is either explained by IR/SEC evidence or the valuation/action stance is explicitly constrained. |
| MRVL | 78.0 | current_period_kpi_coverage_gap | LOW_CURRENT_PERIOD_KPI_COUNT, LOW_TICKER_SPECIFIC_KPI_COUNT, QUALITY_BELOW_PUBLISH_GATE | Add real current-period IR/KPI coverage and ticker-specific interpretation; keep manual_review if data is unavailable. |
| ANET | 71.0 | true_financial_anomaly | AUDIT_BLOCKER, TRUE_FINANCIAL_ANOMALY, FINANCIAL_SANITY_ERROR, LOW_CURRENT_PERIOD_KPI_COUNT, LOW_TICKER_SPECIFIC_KPI_COUNT, QUALITY_BELOW_PUBLISH_GATE | Keep manual_review until the anomaly is either explained by IR/SEC evidence or the valuation/action stance is explicitly constrained. |
| DDOG | 78.0 | period_denominator_or_reconciliation_gap | AUDIT_BLOCKER, PERIOD_BUG, LOW_CURRENT_PERIOD_KPI_COUNT, LOW_TICKER_SPECIFIC_KPI_COUNT, QUALITY_BELOW_PUBLISH_GATE | Fix current-period denominator and SEC/IR reconciliation before considering publishability; do not loosen guards. |
| MDB | 78.0 | current_period_kpi_coverage_gap | LOW_CURRENT_PERIOD_KPI_COUNT, LOW_TICKER_SPECIFIC_KPI_COUNT, QUALITY_BELOW_PUBLISH_GATE | Add real current-period IR/KPI coverage and ticker-specific interpretation; keep manual_review if data is unavailable. |
| CRWD | 60.0 | true_financial_anomaly | AUDIT_BLOCKER, TRUE_FINANCIAL_ANOMALY, FINANCIAL_SANITY_ERROR, LOW_SUBSTANTIVE_CLAIM_COUNT, LOW_CURRENT_PERIOD_KPI_COUNT, LOW_TICKER_SPECIFIC_KPI_COUNT, MECHANICAL_RATING_LANGUAGE, QUALITY_BELOW_PUBLISH_GATE | Keep manual_review until the anomaly is either explained by IR/SEC evidence or the valuation/action stance is explicitly constrained. |
| NET | 78.0 | current_period_kpi_coverage_gap | LOW_CURRENT_PERIOD_KPI_COUNT, LOW_TICKER_SPECIFIC_KPI_COUNT, QUALITY_BELOW_PUBLISH_GATE | Add real current-period IR/KPI coverage and ticker-specific interpretation; keep manual_review if data is unavailable. |
| PANW | 53.0 | post_audit_or_evidence_blocker | AUDIT_BLOCKER, FCF_UNAVAILABLE_BLOCK, LOW_SUBSTANTIVE_CLAIM_COUNT, LOW_CURRENT_PERIOD_KPI_COUNT, LOW_TICKER_SPECIFIC_KPI_COUNT, MECHANICAL_RATING_LANGUAGE, QUALITY_BELOW_PUBLISH_GATE | Map the hard claim to EvidenceItems or remove the hard number from the main report; keep publish blocked until audit is clean. |
| ZS | 78.0 | current_period_kpi_coverage_gap | LOW_CURRENT_PERIOD_KPI_COUNT, LOW_TICKER_SPECIFIC_KPI_COUNT, QUALITY_BELOW_PUBLISH_GATE | Add real current-period IR/KPI coverage and ticker-specific interpretation; keep manual_review if data is unavailable. |
| CRM | 84.0 | period_denominator_or_reconciliation_gap | AUDIT_BLOCKER, PERIOD_BUG, LOW_CURRENT_PERIOD_KPI_COUNT, QUALITY_BELOW_PUBLISH_GATE | Fix current-period denominator and SEC/IR reconciliation before considering publishability; do not loosen guards. |
| NOW | 78.0 | current_period_kpi_coverage_gap | LOW_CURRENT_PERIOD_KPI_COUNT, LOW_TICKER_SPECIFIC_KPI_COUNT, QUALITY_BELOW_PUBLISH_GATE | Add real current-period IR/KPI coverage and ticker-specific interpretation; keep manual_review if data is unavailable. |
| ORCL | 78.0 | current_period_kpi_coverage_gap | LOW_CURRENT_PERIOD_KPI_COUNT, LOW_TICKER_SPECIFIC_KPI_COUNT, QUALITY_BELOW_PUBLISH_GATE | Add real current-period IR/KPI coverage and ticker-specific interpretation; keep manual_review if data is unavailable. |
| ADBE | 78.0 | current_period_kpi_coverage_gap | LOW_CURRENT_PERIOD_KPI_COUNT, LOW_TICKER_SPECIFIC_KPI_COUNT, QUALITY_BELOW_PUBLISH_GATE | Add real current-period IR/KPI coverage and ticker-specific interpretation; keep manual_review if data is unavailable. |
| INTU | 78.0 | current_period_kpi_coverage_gap | LOW_CURRENT_PERIOD_KPI_COUNT, LOW_TICKER_SPECIFIC_KPI_COUNT, QUALITY_BELOW_PUBLISH_GATE | Add real current-period IR/KPI coverage and ticker-specific interpretation; keep manual_review if data is unavailable. |
| UBER | 78.0 | current_period_kpi_coverage_gap | LOW_CURRENT_PERIOD_KPI_COUNT, LOW_TICKER_SPECIFIC_KPI_COUNT, QUALITY_BELOW_PUBLISH_GATE | Add real current-period IR/KPI coverage and ticker-specific interpretation; keep manual_review if data is unavailable. |
| TSLA | 78.0 | current_period_kpi_coverage_gap | LOW_CURRENT_PERIOD_KPI_COUNT, LOW_TICKER_SPECIFIC_KPI_COUNT, QUALITY_BELOW_PUBLISH_GATE | Add real current-period IR/KPI coverage and ticker-specific interpretation; keep manual_review if data is unavailable. |
| PLTR | 71.0 | true_financial_anomaly | AUDIT_BLOCKER, TRUE_FINANCIAL_ANOMALY, FINANCIAL_SANITY_ERROR, LOW_CURRENT_PERIOD_KPI_COUNT, LOW_TICKER_SPECIFIC_KPI_COUNT, QUALITY_BELOW_PUBLISH_GATE | Keep manual_review until the anomaly is either explained by IR/SEC evidence or the valuation/action stance is explicitly constrained. |
| IBM | 78.0 | current_period_kpi_coverage_gap | LOW_CURRENT_PERIOD_KPI_COUNT, LOW_TICKER_SPECIFIC_KPI_COUNT, QUALITY_BELOW_PUBLISH_GATE | Add real current-period IR/KPI coverage and ticker-specific interpretation; keep manual_review if data is unavailable. |
| NFLX | 80.0 | post_audit_or_evidence_blocker | AUDIT_BLOCKER, HARD_CLAIMS_WITHOUT_EVIDENCE, QUALITY_BELOW_PUBLISH_GATE | Map the hard claim to EvidenceItems or remove the hard number from the main report; keep publish blocked until audit is clean. |

## Quick Wins
- INTC: Add real current-period IR/KPI coverage and ticker-specific interpretation; keep manual_review if data is unavailable.
- QCOM: Map the hard claim to EvidenceItems or remove the hard number from the main report; keep publish blocked until audit is clean.
- MRVL: Add real current-period IR/KPI coverage and ticker-specific interpretation; keep manual_review if data is unavailable.
- MDB: Add real current-period IR/KPI coverage and ticker-specific interpretation; keep manual_review if data is unavailable.
- NET: Add real current-period IR/KPI coverage and ticker-specific interpretation; keep manual_review if data is unavailable.
- PANW: Map the hard claim to EvidenceItems or remove the hard number from the main report; keep publish blocked until audit is clean.
- ZS: Add real current-period IR/KPI coverage and ticker-specific interpretation; keep manual_review if data is unavailable.
- NOW: Add real current-period IR/KPI coverage and ticker-specific interpretation; keep manual_review if data is unavailable.

## Should Remain Manual Review
- AMZN: true_financial_anomaly (AUDIT_BLOCKER, TRUE_FINANCIAL_ANOMALY, FINANCIAL_SANITY_ERROR, LOW_CURRENT_PERIOD_KPI_COUNT, QUALITY_BELOW_PUBLISH_GATE)
- NVDA: true_financial_anomaly (AUDIT_BLOCKER, TRUE_FINANCIAL_ANOMALY, FINANCIAL_SANITY_ERROR, LOW_CURRENT_PERIOD_KPI_COUNT, QUALITY_BELOW_PUBLISH_GATE)
- AMD: true_financial_anomaly (AUDIT_BLOCKER, TRUE_FINANCIAL_ANOMALY, FINANCIAL_SANITY_ERROR, LOW_CURRENT_PERIOD_KPI_COUNT, LOW_TICKER_SPECIFIC_KPI_COUNT, QUALITY_BELOW_PUBLISH_GATE)
- MU: true_financial_anomaly (AUDIT_BLOCKER, TRUE_FINANCIAL_ANOMALY, FINANCIAL_SANITY_ERROR, LOW_CURRENT_PERIOD_KPI_COUNT, LOW_TICKER_SPECIFIC_KPI_COUNT, QUALITY_BELOW_PUBLISH_GATE)
- ANET: true_financial_anomaly (AUDIT_BLOCKER, TRUE_FINANCIAL_ANOMALY, FINANCIAL_SANITY_ERROR, LOW_CURRENT_PERIOD_KPI_COUNT, LOW_TICKER_SPECIFIC_KPI_COUNT, QUALITY_BELOW_PUBLISH_GATE)
- DDOG: period_denominator_or_reconciliation_gap (AUDIT_BLOCKER, PERIOD_BUG, LOW_CURRENT_PERIOD_KPI_COUNT, LOW_TICKER_SPECIFIC_KPI_COUNT, QUALITY_BELOW_PUBLISH_GATE)
- CRWD: true_financial_anomaly (AUDIT_BLOCKER, TRUE_FINANCIAL_ANOMALY, FINANCIAL_SANITY_ERROR, LOW_SUBSTANTIVE_CLAIM_COUNT, LOW_CURRENT_PERIOD_KPI_COUNT, LOW_TICKER_SPECIFIC_KPI_COUNT, MECHANICAL_RATING_LANGUAGE, QUALITY_BELOW_PUBLISH_GATE)
- CRM: period_denominator_or_reconciliation_gap (AUDIT_BLOCKER, PERIOD_BUG, LOW_CURRENT_PERIOD_KPI_COUNT, QUALITY_BELOW_PUBLISH_GATE)
- PLTR: true_financial_anomaly (AUDIT_BLOCKER, TRUE_FINANCIAL_ANOMALY, FINANCIAL_SANITY_ERROR, LOW_CURRENT_PERIOD_KPI_COUNT, LOW_TICKER_SPECIFIC_KPI_COUNT, QUALITY_BELOW_PUBLISH_GATE)

## Publish Quality Checks
- False pass candidates: none
- Missing valuation/sensitivity among passed: none
- Missing action triggers among passed: none
- Mechanical/internal language count: 4
