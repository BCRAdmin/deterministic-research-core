# RGTI Post-Guard Review

Batch: `rgti_deeptech_profile_check`
Regression source: existing RGTI deep-tech regression case

## Guard Outcome

- status = `manual_review`
- publishable = `false`
- external_display_rating = `Manual Review / Preliminary Underweight`
- company_archetype = `SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL`
- archetype_confidence = `1.0`

## Triggered Rules

- `market_cap_revenue_gt_100`
- `revenue_ttm_lt_50m`
- `operating_income_ttm_lt_0`
- `free_cash_flow_ttm_lt_0`
- `sbc_to_revenue_gt_050`
- `vendor_only_hard_financial_metrics`
- `derivative_warrant_fair_value_effects_detected`
- `no_sec_ir_current_period_evidence`
- `lumpy_revenue_non_scaled_adoption_language`
- `share_dilution_yoy_gt_010`
- `technical_milestone_language_dominates_news`
- `high_volatility_or_beta_gt_15`

## Erkannte Issues

- `SPECULATIVE_DEEP_TECH_MANUAL_REVIEW_PROFILE`
- `VENDOR_ONLY_HARD_METRICS`
- `ACCOUNTING_GAIN_NOT_OPERATING_TURNAROUND`
- `ORDER_MATERIALITY_MISSING`
- `TECHNICAL_OVERWEIGHT_IN_FUNDAMENTAL_THESIS`

## Publish Boundary

The historical RGTI report remains available as a regression fixture. It is not treated as a fixed `publish_report.md` and must not be surfaced as a clean publishable report.

Deep-tech post-guard behavior is therefore active: RGTI remains manual-review / preliminary, with clean publication blocked.
