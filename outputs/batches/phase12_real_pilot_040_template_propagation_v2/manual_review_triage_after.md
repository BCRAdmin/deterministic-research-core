# Manual Review Triage After — phase12_real_pilot_040_template_propagation_v2

Total manual_review: 21

## Count By Root Cause

| Root Cause | Count |
|---|---:|
| current_period_or_ticker_kpi_gap | 12 |
| true_anomaly | 7 |
| audit_or_validation_block | 2 |

## Count By Reason

| Reason | Count |
|---|---:|
| ticker_specific_kpi_gap | 19 |
| audit_block_or_warning | 17 |
| financial_sanity | 14 |
| true_anomaly | 7 |
| claim_substance_gap | 2 |
| fcf_unavailable_block | 1 |
| missing_current_period_context | 1 |

## Manual Review Items

| Ticker | Quality | Root Cause | Reason Codes | Next Action |
|---|---:|---|---|---|
| AMZN | 76.0 | true_anomaly | audit_block_or_warning, financial_sanity, true_anomaly | Keep manual_review; do not force publishability until the anomaly is explained by company-specific context or corrected source data. |
| NVDA | 75.0 | true_anomaly | audit_block_or_warning, financial_sanity, true_anomaly | Keep manual_review; do not force publishability until the anomaly is explained by company-specific context or corrected source data. |
| AMD | 74.0 | true_anomaly | audit_block_or_warning, financial_sanity, ticker_specific_kpi_gap, true_anomaly | Keep manual_review; do not force publishability until the anomaly is explained by company-specific context or corrected source data. |
| INTC | 78.0 | current_period_or_ticker_kpi_gap | ticker_specific_kpi_gap | Improve ticker-specific publish template only if evidence-backed current-period KPIs exist. |
| QCOM | 87.0 | audit_or_validation_block | audit_block_or_warning, ticker_specific_kpi_gap | Inspect audit/validation report and repair unsupported hard claims or missing evidence. |
| MU | 74.0 | true_anomaly | audit_block_or_warning, financial_sanity, ticker_specific_kpi_gap, true_anomaly | Keep manual_review; do not force publishability until the anomaly is explained by company-specific context or corrected source data. |
| MRVL | 78.0 | current_period_or_ticker_kpi_gap | ticker_specific_kpi_gap | Improve ticker-specific publish template only if evidence-backed current-period KPIs exist. |
| ANET | 74.0 | true_anomaly | audit_block_or_warning, financial_sanity, ticker_specific_kpi_gap, true_anomaly | Keep manual_review; do not force publishability until the anomaly is explained by company-specific context or corrected source data. |
| MDB | 78.0 | current_period_or_ticker_kpi_gap | ticker_specific_kpi_gap | Improve ticker-specific publish template only if evidence-backed current-period KPIs exist. |
| CRWD | 60.0 | true_anomaly | audit_block_or_warning, claim_substance_gap, financial_sanity, ticker_specific_kpi_gap, true_anomaly | Keep manual_review; do not force publishability until the anomaly is explained by company-specific context or corrected source data. |
| NET | 78.0 | current_period_or_ticker_kpi_gap | ticker_specific_kpi_gap | Improve ticker-specific publish template only if evidence-backed current-period KPIs exist. |
| PANW | 56.0 | audit_or_validation_block | audit_block_or_warning, claim_substance_gap, fcf_unavailable_block, missing_current_period_context, ticker_specific_kpi_gap | Inspect audit/validation report and repair unsupported hard claims or missing evidence. |
| ZS | 78.0 | current_period_or_ticker_kpi_gap | ticker_specific_kpi_gap | Improve ticker-specific publish template only if evidence-backed current-period KPIs exist. |
| NOW | 78.0 | current_period_or_ticker_kpi_gap | ticker_specific_kpi_gap | Improve ticker-specific publish template only if evidence-backed current-period KPIs exist. |
| ORCL | 78.0 | current_period_or_ticker_kpi_gap | ticker_specific_kpi_gap | Improve ticker-specific publish template only if evidence-backed current-period KPIs exist. |
| ADBE | 78.0 | current_period_or_ticker_kpi_gap | ticker_specific_kpi_gap | Improve ticker-specific publish template only if evidence-backed current-period KPIs exist. |
| INTU | 78.0 | current_period_or_ticker_kpi_gap | ticker_specific_kpi_gap | Improve ticker-specific publish template only if evidence-backed current-period KPIs exist. |
| UBER | 78.0 | current_period_or_ticker_kpi_gap | ticker_specific_kpi_gap | Improve ticker-specific publish template only if evidence-backed current-period KPIs exist. |
| TSLA | 78.0 | current_period_or_ticker_kpi_gap | ticker_specific_kpi_gap | Improve ticker-specific publish template only if evidence-backed current-period KPIs exist. |
| PLTR | 74.0 | true_anomaly | audit_block_or_warning, financial_sanity, ticker_specific_kpi_gap, true_anomaly | Keep manual_review; do not force publishability until the anomaly is explained by company-specific context or corrected source data. |
| IBM | 78.0 | current_period_or_ticker_kpi_gap | ticker_specific_kpi_gap | Improve ticker-specific publish template only if evidence-backed current-period KPIs exist. |

## Quick Wins

- INTC: Improve ticker-specific publish template only if evidence-backed current-period KPIs exist.
- MRVL: Improve ticker-specific publish template only if evidence-backed current-period KPIs exist.
- MDB: Improve ticker-specific publish template only if evidence-backed current-period KPIs exist.
- NET: Improve ticker-specific publish template only if evidence-backed current-period KPIs exist.
- ZS: Improve ticker-specific publish template only if evidence-backed current-period KPIs exist.
- NOW: Improve ticker-specific publish template only if evidence-backed current-period KPIs exist.
- ORCL: Improve ticker-specific publish template only if evidence-backed current-period KPIs exist.
- ADBE: Improve ticker-specific publish template only if evidence-backed current-period KPIs exist.

## Should Remain Manual Review

- AMZN: true_anomaly
- NVDA: true_anomaly
- AMD: true_anomaly
- QCOM: audit_or_validation_block
- MU: true_anomaly
- ANET: true_anomaly
- CRWD: true_anomaly
- PANW: audit_or_validation_block
- PLTR: true_anomaly
