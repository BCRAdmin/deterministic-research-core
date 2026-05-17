# Manual Review Deep Triage - phase12_real_pilot_034_period_claim_hardening

## Summary

- Total manual_review: `9`
- Quick wins: `QCOM, DDOG, CRM`
- Should remain manual_review: `NVDA, AMD, MU, ANET, CRWD, PLTR`

### Count By Root Cause

- `true_anomaly`: `6`
- `period_bug`: `2`
- `guard_too_strict`: `1`
- `data_gap`: `0`
- `claim_substance_gap`: `0`

### Count By Reason

- `FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY`: `6`
- `TRUE_FINANCIAL_ANOMALY`: `6`
- `CURRENT_PERIOD_IR_RECONCILIATION_REQUIRED`: `2`
- `MISSING_FCF_SUPPORT_FOR_ACCUMULATE`: `1`
- `GUARD_THRESHOLD_REVIEW`: `1`

### Top 5 Data Coverage Gaps

- `current_period_ir_revenue`: `9`
- `current_period_ir_ocf`: `9`
- `current_period_ir_fcf`: `9`
- `company_guidance`: `9`
- `earnings_context_confirmed`: `9`

### Recommended Fix Order

- 1. Add current-period IR/Earnings Release coverage for DDOG and CRM revenue/OCF/FCF, then rerun reconciliation.
- 2. Tune QCOM decision/rating guard so missing FCF plus overbought/unsupported setup cannot surface as direct Accumulate.
- 3. For true-anomaly tickers, manually verify P/FCF against current company-defined FCF before relaxing any guard.
- 4. Keep earnings/calendar and company guidance coverage backlog visible, but do not block solely for unavailable event dates unless reports make event claims.

## Ticker Triage

### NVDA

- Manual-review reason codes: `FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY, TRUE_FINANCIAL_ANOMALY`
- Status category: `true_anomaly`
- Primary root cause: Valuation/cash-flow multiple remains extreme after period-denominator hardening.
- Secondary root causes: `P/FCF is 102.61x.; EV/Sales is 26.02x.; Earnings calendar context is unavailable/unconfirmed.; Company guidance evidence unavailable.`
- Current-period IR revenue: `False`
- Current-period IR OCF: `False`
- Current-period IR FCF: `False`
- Current-period SBC: `True`
- Company guidance: `False`
- Consensus only: `False`
- Earnings context confirmed: `False`
- Solvable by: `keep manual_review, IR/GUIDANCE data coverage`
- Recommended next action: Keep NVDA manual_review and manually verify whether P/FCF/EV multiples are real valuation outliers versus current IR cash-flow data.

### AMD

- Manual-review reason codes: `FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY, TRUE_FINANCIAL_ANOMALY`
- Status category: `true_anomaly`
- Primary root cause: Valuation/cash-flow multiple remains extreme after period-denominator hardening.
- Secondary root causes: `P/FCF is 246.48x.; EV/Sales is 18.50x.; Earnings calendar context is unavailable/unconfirmed.; Company guidance evidence unavailable.`
- Current-period IR revenue: `False`
- Current-period IR OCF: `False`
- Current-period IR FCF: `False`
- Current-period SBC: `True`
- Company guidance: `False`
- Consensus only: `False`
- Earnings context confirmed: `False`
- Solvable by: `keep manual_review, IR/GUIDANCE data coverage`
- Recommended next action: Keep AMD manual_review and manually verify whether P/FCF/EV multiples are real valuation outliers versus current IR cash-flow data.

### QCOM

- Manual-review reason codes: `MISSING_FCF_SUPPORT_FOR_ACCUMULATE`
- Status category: `guard_too_strict`
- Primary root cause: Decision/rating corridor allows Accumulate-style framing without validated FCF support.
- Secondary root causes: `FCF TTM unavailable in validated packet.; Rating guard should prefer Hold / pullback-only language until cash-flow support is present.; Earnings calendar context is unavailable/unconfirmed.; Company guidance evidence unavailable.`
- Current-period IR revenue: `False`
- Current-period IR OCF: `False`
- Current-period IR FCF: `False`
- Current-period SBC: `True`
- Company guidance: `False`
- Consensus only: `False`
- Earnings context confirmed: `False`
- Solvable by: `decision/rating guard tuning, IR/GUIDANCE data coverage`
- Recommended next action: Keep QCOM in manual review unless DecisionPacket is constrained to Hold / Accumulate-on-pullback or validated FCF support is ingested.

### MU

- Manual-review reason codes: `FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY, TRUE_FINANCIAL_ANOMALY`
- Status category: `true_anomaly`
- Primary root cause: Valuation/cash-flow multiple remains extreme after period-denominator hardening.
- Secondary root causes: `P/FCF is 630.81x.; EV/Sales is 13.19x.; Earnings calendar context is unavailable/unconfirmed.; Company guidance evidence unavailable.`
- Current-period IR revenue: `False`
- Current-period IR OCF: `False`
- Current-period IR FCF: `False`
- Current-period SBC: `True`
- Company guidance: `False`
- Consensus only: `False`
- Earnings context confirmed: `False`
- Solvable by: `keep manual_review, IR/GUIDANCE data coverage`
- Recommended next action: Keep MU manual_review and manually verify whether P/FCF/EV multiples are real valuation outliers versus current IR cash-flow data.

### ANET

- Manual-review reason codes: `FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY, TRUE_FINANCIAL_ANOMALY`
- Status category: `true_anomaly`
- Primary root cause: Valuation/cash-flow multiple remains extreme after period-denominator hardening.
- Secondary root causes: `P/FCF is 128.58x.; EV/Sales is 25.69x.; Earnings calendar context is unavailable/unconfirmed.; Company guidance evidence unavailable.`
- Current-period IR revenue: `False`
- Current-period IR OCF: `False`
- Current-period IR FCF: `False`
- Current-period SBC: `True`
- Company guidance: `False`
- Consensus only: `False`
- Earnings context confirmed: `False`
- Solvable by: `keep manual_review, IR/GUIDANCE data coverage`
- Recommended next action: Keep ANET manual_review and manually verify whether P/FCF/EV multiples are real valuation outliers versus current IR cash-flow data.

### DDOG

- Manual-review reason codes: `CURRENT_PERIOD_IR_RECONCILIATION_REQUIRED`
- Status category: `period_bug`
- Primary root cause: Current-period company/IR values are not reconciled against canonical SEC/source-ingestion metrics.
- Secondary root causes: `Missing current-period IR revenue evidence.; Missing current-period IR/company-defined FCF evidence.; Earnings calendar context is unavailable/unconfirmed.; Company guidance evidence unavailable.`
- Current-period IR revenue: `False`
- Current-period IR OCF: `False`
- Current-period IR FCF: `False`
- Current-period SBC: `True`
- Company guidance: `False`
- Consensus only: `False`
- Earnings context confirmed: `False`
- Solvable by: `IR/GUIDANCE data coverage, period-denominator fix`
- Recommended next action: Add or verify current-period IR/Earnings Release values for DDOG revenue/OCF/FCF, then rerun reconciliation before changing guards.

### CRWD

- Manual-review reason codes: `FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY, TRUE_FINANCIAL_ANOMALY`
- Status category: `true_anomaly`
- Primary root cause: Valuation/cash-flow multiple remains extreme after period-denominator hardening.
- Secondary root causes: `P/FCF is 115.56x.; Earnings calendar context is unavailable/unconfirmed.; Company guidance evidence unavailable.`
- Current-period IR revenue: `False`
- Current-period IR OCF: `False`
- Current-period IR FCF: `False`
- Current-period SBC: `True`
- Company guidance: `False`
- Consensus only: `False`
- Earnings context confirmed: `False`
- Solvable by: `keep manual_review, IR/GUIDANCE data coverage`
- Recommended next action: Keep CRWD manual_review and manually verify whether P/FCF/EV multiples are real valuation outliers versus current IR cash-flow data.

### CRM

- Manual-review reason codes: `CURRENT_PERIOD_IR_RECONCILIATION_REQUIRED`
- Status category: `period_bug`
- Primary root cause: Current-period company/IR values are not reconciled against canonical SEC/source-ingestion metrics.
- Secondary root causes: `Missing current-period IR revenue evidence.; Missing current-period IR/company-defined FCF evidence.; Earnings calendar context is unavailable/unconfirmed.; Company guidance evidence unavailable.`
- Current-period IR revenue: `False`
- Current-period IR OCF: `False`
- Current-period IR FCF: `False`
- Current-period SBC: `True`
- Company guidance: `False`
- Consensus only: `False`
- Earnings context confirmed: `False`
- Solvable by: `IR/GUIDANCE data coverage, period-denominator fix`
- Recommended next action: Add or verify current-period IR/Earnings Release values for CRM revenue/OCF/FCF, then rerun reconciliation before changing guards.

### PLTR

- Manual-review reason codes: `FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY, GUARD_THRESHOLD_REVIEW, TRUE_FINANCIAL_ANOMALY`
- Status category: `true_anomaly`
- Primary root cause: Valuation/cash-flow multiple remains extreme after period-denominator hardening.
- Secondary root causes: `P/FCF is 232.11x.; EV/Sales is 72.65x.; Earnings calendar context is unavailable/unconfirmed.; Company guidance evidence unavailable.`
- Current-period IR revenue: `False`
- Current-period IR OCF: `False`
- Current-period IR FCF: `False`
- Current-period SBC: `True`
- Company guidance: `False`
- Consensus only: `False`
- Earnings context confirmed: `False`
- Solvable by: `keep manual_review, IR/GUIDANCE data coverage`
- Recommended next action: Keep PLTR manual_review and manually verify whether P/FCF/EV multiples are real valuation outliers versus current IR cash-flow data.
