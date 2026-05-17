# Financial Sanity Triage After — Pilot 035

Batch: `phase12_real_pilot_035_current_ir_claim_semantics`
Total manual review: `23`

## Summary

- Count by root cause: `{'true_financial_anomaly': 7, 'claim_semantics_gap': 13, 'period_denominator_bug': 2, 'fcf_unavailable_without_ir_support': 1}`
- Count by reason: `{'FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY': 7, 'TRUE_FINANCIAL_ANOMALY': 7, 'MISSING_FCF_SUPPORT_FOR_ACCUMULATE': 1, 'CURRENT_PERIOD_IR_RECONCILIATION_REQUIRED': 3, 'GUARD_THRESHOLD_REVIEW': 2, 'FCF_UNAVAILABLE_WITHOUT_IR_SUPPORT': 1, 'MISSING_CURRENT_PERIOD_CONTEXT': 1}`
- Quick wins: `INTC, QCOM, MRVL, MDB, NET, PANW, ZS, NOW, ORCL, ADBE, INTU, UBER, TSLA, IBM`
- Should remain manual review: `AMZN, NVDA, AMD, MU, ANET, CRWD, PLTR`

## Ticker Detail

| Ticker | Quality | Root Cause | Reason Codes | Key Counts | Recommended Action |
|---|---:|---|---|---|---|
| AMZN | 76.0 | true_financial_anomaly | FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY, TRUE_FINANCIAL_ANOMALY | ticker_specific_kpi_claim_count=4, true_anomaly=1, financial_sanity_errors=2, audit_errors=2 | Keep manual review unless investment committee explicitly accepts the extreme valuation/ratio context. |
| NVDA | 75.0 | true_financial_anomaly | FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY, TRUE_FINANCIAL_ANOMALY | ticker_specific_kpi_claim_count=4, true_anomaly=1, financial_sanity_errors=2, audit_errors=2 | Keep manual review unless investment committee explicitly accepts the extreme valuation/ratio context. |
| AMD | 74.0 | true_financial_anomaly | FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY, TRUE_FINANCIAL_ANOMALY | ticker_specific_kpi_claim_count=1, true_anomaly=1, financial_sanity_errors=2, audit_errors=2 | Keep manual review unless investment committee explicitly accepts the extreme valuation/ratio context. |
| INTC | 78.0 | claim_semantics_gap | none | ticker_specific_kpi_claim_count=1, data_limitation_claim_count=1 | Add current-period company-specific KPI claims; do not count data availability notes as substance. |
| QCOM | 78.0 | claim_semantics_gap | MISSING_FCF_SUPPORT_FOR_ACCUMULATE | ticker_specific_kpi_claim_count=1, data_limitation_claim_count=2, audit_errors=1 | Add current-period company-specific KPI claims; do not count data availability notes as substance. |
| MU | 74.0 | true_financial_anomaly | FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY, TRUE_FINANCIAL_ANOMALY | ticker_specific_kpi_claim_count=1, true_anomaly=1, financial_sanity_errors=2, audit_errors=2 | Keep manual review unless investment committee explicitly accepts the extreme valuation/ratio context. |
| MRVL | 78.0 | claim_semantics_gap | none | ticker_specific_kpi_claim_count=1 | Add current-period company-specific KPI claims; do not count data availability notes as substance. |
| ANET | 74.0 | true_financial_anomaly | FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY, TRUE_FINANCIAL_ANOMALY | ticker_specific_kpi_claim_count=1, true_anomaly=1, financial_sanity_errors=2, audit_errors=2 | Keep manual review unless investment committee explicitly accepts the extreme valuation/ratio context. |
| DDOG | 78.0 | period_denominator_bug | CURRENT_PERIOD_IR_RECONCILIATION_REQUIRED | ticker_specific_kpi_claim_count=1, period_bug=1, audit_errors=2 | Fix compatible denominator/source-period selection before recalculating ratios. |
| MDB | 78.0 | claim_semantics_gap | none | ticker_specific_kpi_claim_count=1 | Add current-period company-specific KPI claims; do not count data availability notes as substance. |
| CRWD | 60.0 | true_financial_anomaly | FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY, TRUE_FINANCIAL_ANOMALY | ticker_specific_kpi_claim_count=1, data_limitation_claim_count=6, true_anomaly=1, financial_sanity_errors=2, audit_errors=2 | Keep manual review unless investment committee explicitly accepts the extreme valuation/ratio context. |
| NET | 78.0 | claim_semantics_gap | GUARD_THRESHOLD_REVIEW | ticker_specific_kpi_claim_count=1, guard_threshold_review=1 | Add current-period company-specific KPI claims; do not count data availability notes as substance. |
| PANW | 62.0 | fcf_unavailable_without_ir_support | FCF_UNAVAILABLE_WITHOUT_IR_SUPPORT, MISSING_CURRENT_PERIOD_CONTEXT | fcf_unavailable_block_count=1, missing_current_period_context_count=1, ticker_specific_kpi_claim_count=1, data_limitation_claim_count=2, audit_errors=2 | Ingest current IR adjusted FCF / FCF-margin support or keep manual review with explicit data limitation. |
| ZS | 78.0 | claim_semantics_gap | none | ticker_specific_kpi_claim_count=1 | Add current-period company-specific KPI claims; do not count data availability notes as substance. |
| CRM | 92.0 | period_denominator_bug | CURRENT_PERIOD_IR_RECONCILIATION_REQUIRED | ticker_specific_kpi_claim_count=6, period_bug=1, audit_errors=1 | Fix compatible denominator/source-period selection before recalculating ratios. |
| NOW | 78.0 | claim_semantics_gap | none | ticker_specific_kpi_claim_count=1 | Add current-period company-specific KPI claims; do not count data availability notes as substance. |
| ORCL | 78.0 | claim_semantics_gap | none | ticker_specific_kpi_claim_count=1 | Add current-period company-specific KPI claims; do not count data availability notes as substance. |
| ADBE | 78.0 | claim_semantics_gap | none | ticker_specific_kpi_claim_count=1 | Add current-period company-specific KPI claims; do not count data availability notes as substance. |
| INTU | 78.0 | claim_semantics_gap | none | ticker_specific_kpi_claim_count=1 | Add current-period company-specific KPI claims; do not count data availability notes as substance. |
| UBER | 78.0 | claim_semantics_gap | none | ticker_specific_kpi_claim_count=1 | Add current-period company-specific KPI claims; do not count data availability notes as substance. |
| TSLA | 78.0 | claim_semantics_gap | none | ticker_specific_kpi_claim_count=1 | Add current-period company-specific KPI claims; do not count data availability notes as substance. |
| PLTR | 74.0 | true_financial_anomaly | FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY, GUARD_THRESHOLD_REVIEW, TRUE_FINANCIAL_ANOMALY | ticker_specific_kpi_claim_count=1, true_anomaly=1, guard_threshold_review=1, financial_sanity_errors=2, audit_errors=2 | Keep manual review unless investment committee explicitly accepts the extreme valuation/ratio context. |
| IBM | 78.0 | claim_semantics_gap | none | ticker_specific_kpi_claim_count=1 | Add current-period company-specific KPI claims; do not count data availability notes as substance. |
