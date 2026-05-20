# Passed Sample Review Selection

> Superseded by manual_focus_guardrail_final_check. Do not use for promotion.
> QCOM was removed from the passed-sample bundle; current operating truth is manual_review / Hold Pending FCF Support.

| Category | Ticker | Publish Q | Internal Q | Data Conf | Archetype | Display | Rationale |
|---|---|---:|---:|---:|---|---|---|
| highest_quality | SNOW | 93 | 100 | 79 | SAAS_CONSUMPTION | Hold with Underweight Bias | Top publish_quality_score with data-confidence tie-break. |
| highest_quality | GOOGL | 93 | 100 | 77 | MEGA_CAP_PLATFORM | Hold | Top publish_quality_score with data-confidence tie-break. |
| highest_quality | META | 93 | 100 | 71 | MEGA_CAP_PLATFORM | Hold | Top publish_quality_score with data-confidence tie-break. |
| lowest_quality | CRM | 88 | 100 | 68 | SAAS_CONSUMPTION | Hold | Lowest passed publish_quality_score; useful for floor check. |
| deterministic_random | NFLX | 90 | 100 | 71 | MEGA_CAP_PLATFORM | Hold | Deterministic random sample using batch id seed. |
| high_risk_high_valuation | AVGO | 90 | 100 | 77 | SEMICONDUCTOR_AI_INFRA | Hold | Highest available valuation/risk multiple among passed reports not already selected where possible. |
