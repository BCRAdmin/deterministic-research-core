# Pilot Review - guardrail_coverage_batch_003_current_research

- As-of date: `2026-05-17`
- Batch status: `completed_with_issues`
- Tickers: `32`

## Status Summary

- Passed: `10`
- Repaired: `0`
- Manual review: `22`
- Data unavailable: `0`
- Failed: `0`
- Average quality score: `75.3125`
- Median quality score: `74.5`
- Lowest quality score: `54.0`
- Repair rate: `0.0%`
- Manual review rate: `68.8%`

## Before / After Reconciliation

- Old `SOURCE_VALUE_DISAGREEMENT`: `not provided`
- New `true_source_disagreements`: `327`
- Ignored frame / period variants: `4611`

## Dashboard Counts

- `accounting_gain_not_operating_turnaround_count`: `0`
- `analyst_claim_count`: `611`
- `audit_errors`: `27`
- `audit_warnings`: `12`
- `canonical_metrics_created`: `27093`
- `company_archetype_present`: `32`
- `company_defined_fcf_mismatch_count`: `0`
- `company_defined_fcf_used`: `6`
- `company_guidance_available_count`: `0`
- `company_specific_claim_count`: `543`
- `consensus_only_count`: `0`
- `content_completeness_score`: `2492`
- `current_kpi_appendix_only_count`: `2`
- `current_period_kpi_claim_count`: `395`
- `current_period_kpi_claim_count_main_body`: `56`
- `current_report_blocked_by_freshness_count`: `0`
- `data_bug`: `0`
- `data_confidence_score`: `2083`
- `data_limitation_claim_count`: `0`
- `early_commercial_capital_intensive_tech_count`: `1`
- `earnings_confirmed_count`: `0`
- `earnings_unavailable_count`: `32`
- `earnings_within_10_trading_days_count`: `0`
- `evidence_mapped_claim_ratio`: `3200`
- `evidence_warnings`: `0`
- `extreme_valuation_review`: `6`
- `fcf_ocf_inconsistency_count`: `0`
- `fcf_unavailable_block_count`: `1`
- `final_rating_rationale_quality`: `2815`
- `financial_sanity_errors`: `24`
- `generic_claim_count`: `0`
- `generic_claim_ratio`: `0`
- `guard_threshold_review`: `1`
- `guidance_consensus_mismatch_count`: `0`
- `hard_claim_evidence_ratio`: `3200`
- `hard_claims_without_evidence_count`: `0`
- `historical_qa_only_count`: `0`
- `ignored_frame_variants`: `4611`
- `internal_research_quality_score`: `3063`
- `mechanical_rating_language_count`: `0`
- `mechanical_rating_language_count_main_body`: `0`
- `missing_current_period_context_count`: `1`
- `order_materiality_missing_count`: `0`
- `period_bug`: `5`
- `placeholder_business_context_count`: `0`
- `publish_action_plan_trigger_count`: `134`
- `publish_claim_id_main_body_count`: `0`
- `publish_current_kpi_count`: `392`
- `publish_evidence_appendix_exists`: `32`
- `publish_mechanical_language_count`: `5`
- `publish_quality_score`: `2410`
- `publish_report_exists`: `32`
- `publish_report_quality_score`: `3130`
- `publish_valuation_sensitivity_present`: `32`
- `rating_rationale_claim_count`: `32`
- `reconciliation_warnings`: `327`
- `sec_derived_fcf_used`: `0`
- `source_ingestion_post_audit_block_count`: `13`
- `speculative_deep_tech_profile_count`: `5`
- `stale_price_basis_count`: `0`
- `substantive_analyst_claim_count`: `456`
- `substantive_claim_count`: `456`
- `substantive_claim_ratio`: `2384`
- `technical_overweight_in_thesis_count`: `5`
- `technical_specific_claim_count`: `64`
- `ticker_specific_kpi_claim_count`: `99`
- `true_anomaly`: `12`
- `true_source_disagreements`: `327`
- `true_valuation_anomaly`: `0`
- `unsupported_earnings_event_claims`: `0`
- `unsupported_guidance_claims`: `0`
- `validation_errors`: `0`
- `validation_warnings`: `64`
- `valuation_specific_claim_count`: `50`
- `vendor_only_hard_claim_count`: `0`
- `vendor_only_hard_metrics_count`: `0`

## Frequent Issues

### Validation Issues

- `PRICE_DATE_BEFORE_AS_OF_DATE`: `32`
- `EARNINGS_DATE_UNAVAILABLE`: `32`

### Audit Issues

- `PERIOD_DENOMINATOR_BUG`: `7`
- `TRUE_FINANCIAL_ANOMALY`: `6`
- `EXTREME_VALUATION_REQUIRES_REVIEW`: `6`
- `FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY`: `5`
- `SPECULATIVE_DEEP_TECH_MANUAL_REVIEW_PROFILE`: `5`
- `TECHNICAL_OVERWEIGHT_IN_FUNDAMENTAL_THESIS`: `5`
- `MISSING_FCF_SUPPORT_FOR_ACCUMULATE`: `1`
- `FCF_UNAVAILABLE_WITHOUT_IR_SUPPORT`: `1`
- `MISSING_CURRENT_PERIOD_KPI_CONTEXT`: `1`
- `GUARD_THRESHOLD_REVIEW`: `1`

### Evidence Issues

- `MISSING_DATE_FOR_NEWS_EVENT`: `0`
- `NO_PRIMARY_EVIDENCE_FOR_HARD_METRIC`: `0`
- `MISSING_EVIDENCE_FOR_METRIC`: `0`
- `VENDOR_SOURCE_USED_AS_PRIMARY`: `0`
- `GUIDANCE_CONSENSUS_CONFLATION`: `0`

### Reconciliation Warnings / Info

- `PERIOD_TYPE_MISMATCH_IGNORED`: `4292`
- `TRUE_SOURCE_VALUE_DISAGREEMENT`: `327`
- `SOURCE_FRAME_VARIANT_IGNORED`: `319`

## Ticker Results

| Ticker | Status | Quality | External Rating | External Action | True Disagreements | Ignored Variants |
|---|---|---:|---|---|---:|---:|
| GOOGL | passed | 93.0 | Hold |  | 2 | 108 |
| SNOW | passed | 93.0 | Hold with Underweight Bias |  | 1 | 62 |
| MSFT | passed | 92.0 | Hold |  | 19 | 324 |
| AAPL | passed | 92.0 | Accumulate |  | 7 | 245 |
| META | passed | 93.0 | Hold |  | 10 | 140 |
| AMZN | manual_review | 71.0 | Hold |  | 18 | 470 |
| NFLX | passed | 90.0 | Hold |  | 7 | 288 |
| CRM | passed | 88.0 | Hold |  | 25 | 336 |
| DDOG | passed | 92.0 | Hold |  | 0 | 65 |
| NOW | manual_review | 78.0 | Hold |  | 15 | 190 |
| MDB | manual_review | 78.0 | Hold |  | 5 | 83 |
| NET | manual_review | 78.0 | Hold |  | 0 | 62 |
| ZS | manual_review | 78.0 | Hold |  | 0 | 76 |
| CRWD | manual_review | 60.0 | Hold |  | 2 | 46 |
| PANW | manual_review | 54.0 | Hold Pending FCF Support | Accumulate only after FCF support | 49 | 198 |
| NVDA | manual_review | 70.0 | Hold |  | 29 | 269 |
| AMD | manual_review | 69.0 | Hold |  | 14 | 219 |
| AVGO | passed | 90.0 | Hold |  | 2 | 98 |
| QCOM | passed | 87.0 | Accumulate |  | 25 | 183 |
| MU | manual_review | 69.0 | Hold |  | 9 | 242 |
| MRVL | manual_review | 78.0 | Hold |  | 12 | 66 |
| INTC | manual_review | 78.0 | Hold |  | 3 | 215 |
| RGTI | manual_review | 62.0 | Manual Review / Preliminary Underweight | Underweight only as preliminary manual-review view | 2 | 50 |
| IONQ | manual_review | 65.0 | Hold |  | 0 | 45 |
| QBTS | manual_review | 63.0 | Manual Review / Preliminary Underweight | Underweight only as preliminary manual-review view | 0 | 46 |
| RKLB | manual_review | 65.0 | Manual Review / Hold Pending FCF and Execution Evidence | Hold pending FCF path and execution evidence | 2 | 53 |
| ASTS | manual_review | 65.0 | Manual Review / Preliminary Underweight | Underweight only as preliminary manual-review view | 6 | 45 |
| ACHR | manual_review | 62.0 | Manual Review / Preliminary Underweight | Underweight only as preliminary manual-review view | 3 | 35 |
| JOBY | manual_review | 62.0 | Manual Review / Preliminary Underweight | Underweight only as preliminary manual-review view | 3 | 37 |
| RIVN | manual_review | 65.0 | Underweight |  | 0 | 48 |
| LCID | manual_review | 65.0 | Underweight |  | 2 | 58 |
| PLUG | manual_review | 65.0 | Hold |  | 55 | 209 |

## Best / Worst Result

- Best result: `GOOGL, SNOW, META` with quality `93.0`.
- Weakest result: `PANW` with quality `54.0`.

## Data Quality Ranking

### Top 5 Weakest Data Quality

- `PANW`: quality `54.0`, true disagreements `49`, validation errors `0`, audit errors `3`
- `CRWD`: quality `60.0`, true disagreements `2`, validation errors `0`, audit errors `2`
- `ACHR`: quality `62.0`, true disagreements `3`, validation errors `0`, audit errors `2`
- `JOBY`: quality `62.0`, true disagreements `3`, validation errors `0`, audit errors `2`
- `RGTI`: quality `62.0`, true disagreements `2`, validation errors `0`, audit errors `2`

### Top 5 Best Data Quality

- `SNOW`: quality `93.0`, true disagreements `1`, validation errors `0`, audit errors `0`
- `GOOGL`: quality `93.0`, true disagreements `2`, validation errors `0`, audit errors `0`
- `META`: quality `93.0`, true disagreements `10`, validation errors `0`, audit errors `0`
- `DDOG`: quality `92.0`, true disagreements `0`, validation errors `0`, audit errors `0`
- `AAPL`: quality `92.0`, true disagreements `7`, validation errors `0`, audit errors `0`

## Source Ingestion Sufficiency

- Tickers where `source_ingestion_mode` was not sufficient: `AMZN, NOW, MDB, NET, ZS, CRWD, PANW, NVDA, AMD, MU, MRVL, INTC, RGTI, IONQ, QBTS, RKLB, ASTS, ACHR, JOBY, RIVN, LCID, PLUG`
- Recommendation: `nicht produktionsreif`

## Production Readiness Assessment

- `source_ingestion_mode` still needs manual review before production operation.
- Remaining production gaps: populate a real EarningsCalendar feed and broaden IR/guidance release coverage; source-ingestion post-audit is wired and counted.

## Artifact Check

- All required dashboard artifact paths are present.
