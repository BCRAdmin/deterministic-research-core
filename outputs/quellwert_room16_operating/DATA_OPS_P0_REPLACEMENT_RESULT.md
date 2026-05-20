# DATA_OPS_P0_REPLACEMENT_RESULT

Scope: direct IR/Earnings-/SEC source replacements only. No code, guard, rating-rule, archetype or report-template changes.

- Batch: `data_ops_p0_replacement_check`
- As-of date: `2026-05-17`
- Sources added: 5 direct company/IR sources
- Artifact consistency: `clean` (0 errors)
- Public-ready without promotion: `false` for all five tickers

## Before / After

| Ticker | Status | Display before -> after | Data confidence before -> after | Removed reasons | Remaining key reasons | Publishability changed |
|---|---|---|---:|---|---|---|
| IONQ | manual_review -> manual_review | Manual Review / Hold Pending FCF and Execution Evidence -> Manual Review / Hold Pending FCF and Execution Evidence | 72 -> 75 | TECHNICAL_OVERWEIGHT_IN_FUNDAMENTAL_THESIS | EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH_MANUAL_REVIEW_PROFILE, EARNINGS_DATE_UNAVAILABLE, EXTREME_VALUATION_REQUIRES_REVIEW, PERIOD_TYPE_MISMATCH_IGNORED, SOURCE_FRAME_VARIANT_IGNORED, TRUE_FINANCIAL_ANOMALY | no |
| NVDA | manual_review -> manual_review | Hold -> Accumulate | 60 -> 67 | FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY, TRUE_FINANCIAL_ANOMALY | EARNINGS_DATE_UNAVAILABLE, FINANCIAL_SANITY_FCF_MARGIN_ANOMALY, GUARD_THRESHOLD_REVIEW, PERIOD_TYPE_MISMATCH_IGNORED, SOURCE_FRAME_VARIANT_IGNORED, TRUE_SOURCE_VALUE_DISAGREEMENT | no |
| QBTS | manual_review -> manual_review | Manual Review / Preliminary Underweight -> Manual Review / Preliminary Underweight | 75 -> 75 | TECHNICAL_OVERWEIGHT_IN_FUNDAMENTAL_THESIS | EARNINGS_DATE_UNAVAILABLE, EXTREME_VALUATION_REQUIRES_REVIEW, PERIOD_TYPE_MISMATCH_IGNORED, SPECULATIVE_DEEP_TECH_MANUAL_REVIEW_PROFILE, TRUE_FINANCIAL_ANOMALY | no |
| QCOM | manual_review -> manual_review | Hold Pending FCF Support -> Hold Pending FCF Support | 72 -> 49 | - | EARNINGS_DATE_UNAVAILABLE, MISSING_CURRENT_PERIOD_KPI_CONTEXT, MISSING_FCF_SUPPORT_FOR_ACCUMULATE, PERIOD_TYPE_MISMATCH_IGNORED, SOURCE_FRAME_VARIANT_IGNORED, TRUE_SOURCE_VALUE_DISAGREEMENT | no |
| RGTI | manual_review -> manual_review | Manual Review / Preliminary Underweight -> Manual Review / Preliminary Underweight | 69 -> 69 | - | EARNINGS_DATE_UNAVAILABLE, EXTREME_VALUATION_REQUIRES_REVIEW, PERIOD_TYPE_MISMATCH_IGNORED, SOURCE_FRAME_VARIANT_IGNORED, SPECULATIVE_DEEP_TECH_MANUAL_REVIEW_PROFILE, TECHNICAL_OVERWEIGHT_IN_FUNDAMENTAL_THESIS | no |

## Sources Added

- IONQ: IonQ Q1 2026 earnings release: revenue, adjusted EBITDA loss, OCF/capex, cash/investments, RPO, FY/Q2 revenue guidance.
- NVDA: NVIDIA Q4/FY2026 earnings release: Q4/FY revenue, operating income, Data Center revenue, OCF, company-defined FCF, cash/securities, FY2027 Q1 revenue outlook.
- QBTS: D-Wave Q1 2026 earnings release: revenue, bookings, RPO, gross margin, operating expenses, net loss, adjusted EBITDA loss, cash/securities.
- QCOM: Qualcomm Q2 FY2026 earnings release PDF: revenue, operating income, OCF, capex, calculated cash-flow support, QCT/QTL segment revenue, Q3 guidance.
- RGTI: Rigetti Q1 2026 earnings release PDF: revenue, operating loss, GAAP/non-GAAP income, OCF, capex, cash/securities, no-debt statement, 108-qubit system milestone.

## Sources Still Missing / Remaining Blockers

- IONQ: company-defined FCF; confirmed next earnings date
- NVDA: confirmed next earnings date; latest FY2027 actuals after next report
- QBTS: company-defined FCF; full 10-Q cash-flow detail in direct release fixture; confirmed next earnings date
- QCOM: company-defined FCF label/reconciled TTM FCF; confirmed next earnings date; main-body use of new QCT/QTL/current-period KPIs remains incomplete
- RGTI: company-defined FCF; customer/order materiality beyond disclosed Novera shipments; confirmed next earnings date

## Regression Check

- qcom_not_plain_accumulate_without_fcf_support: True
- ionq_not_standard_growth: True
- rgti_deeptech_manual_review: True
- qbts_deeptech_manual_review: True
- nvda_no_false_pass: True

## QA

- pytest: passed
- compileall: passed
- git diff --check: passed

## Notes

- QCOM remains manual_review / Hold Pending FCF Support because direct OCF/capex evidence is available, but company-defined or reconciled TTM FCF support is still absent.
- NVDA remains manual_review and not public-ready; direct FY2026 company-defined FCF improves data confidence but source disagreement / FCF-margin review remains a manual-review blocker.
- No publish_report.md is copied to ticker roots because all five outputs remain non-publishable; generated pipeline stubs remain inside raw report folders only as manual-review artifacts.
