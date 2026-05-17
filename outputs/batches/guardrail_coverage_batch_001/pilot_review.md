# Pilot Review - guardrail_coverage_batch_001

- As-of date: `2026-05-05`
- Batch status: `completed_with_issues`
- Tickers: `41`

## Status Summary

- Passed: `9`
- Repaired: `0`
- Manual review: `13`
- Data unavailable: `19`
- Failed: `0`
- Average quality score: `81.81818181818181`
- Median quality score: `78.0`
- Lowest quality score: `57.0`
- Repair rate: `0.0%`
- Manual review rate: `31.7%`

## Before / After Reconciliation

- Old `SOURCE_VALUE_DISAGREEMENT`: `not provided`
- New `true_source_disagreements`: `254`
- Ignored frame / period variants: `3984`

## Dashboard Counts

- `accounting_gain_not_operating_turnaround_count`: `0`
- `analyst_claim_count`: `423`
- `audit_errors`: `13`
- `audit_warnings`: `2`
- `canonical_metrics_created`: `22669`
- `company_archetype_present`: `22`
- `company_defined_fcf_mismatch_count`: `0`
- `company_defined_fcf_used`: `5`
- `company_guidance_available_count`: `0`
- `company_specific_claim_count`: `388`
- `consensus_only_count`: `0`
- `content_completeness_score`: `1842`
- `current_kpi_appendix_only_count`: `1`
- `current_period_kpi_claim_count`: `265`
- `current_period_kpi_claim_count_main_body`: `43`
- `data_bug`: `0`
- `data_confidence_score`: `1613`
- `data_limitation_claim_count`: `0`
- `early_commercial_capital_intensive_tech_count`: `0`
- `earnings_confirmed_count`: `0`
- `earnings_unavailable_count`: `22`
- `earnings_within_10_trading_days_count`: `0`
- `evidence_mapped_claim_ratio`: `2200`
- `evidence_warnings`: `0`
- `extreme_valuation_review`: `0`
- `fcf_ocf_inconsistency_count`: `0`
- `fcf_unavailable_block_count`: `1`
- `final_rating_rationale_quality`: `2040`
- `financial_sanity_errors`: `10`
- `generic_claim_count`: `0`
- `generic_claim_ratio`: `0`
- `guard_threshold_review`: `2`
- `guidance_consensus_mismatch_count`: `0`
- `hard_claim_evidence_ratio`: `2200`
- `hard_claims_without_evidence_count`: `0`
- `ignored_frame_variants`: `3984`
- `internal_research_quality_score`: `2165`
- `mechanical_rating_language_count`: `0`
- `mechanical_rating_language_count_main_body`: `0`
- `missing_current_period_context_count`: `1`
- `order_materiality_missing_count`: `0`
- `period_bug`: `0`
- `placeholder_business_context_count`: `0`
- `publish_action_plan_trigger_count`: `96`
- `publish_claim_id_main_body_count`: `0`
- `publish_current_kpi_count`: `265`
- `publish_evidence_appendix_exists`: `22`
- `publish_mechanical_language_count`: `0`
- `publish_quality_score`: `1800`
- `publish_report_exists`: `22`
- `publish_report_quality_score`: `2200`
- `publish_valuation_sensitivity_present`: `22`
- `rating_rationale_claim_count`: `22`
- `reconciliation_warnings`: `254`
- `sec_derived_fcf_used`: `0`
- `source_ingestion_post_audit_block_count`: `7`
- `speculative_deep_tech_profile_count`: `0`
- `substantive_analyst_claim_count`: `334`
- `substantive_claim_count`: `334`
- `substantive_claim_ratio`: `1728`
- `technical_overweight_in_thesis_count`: `0`
- `technical_specific_claim_count`: `44`
- `ticker_specific_kpi_claim_count`: `81`
- `true_anomaly`: `5`
- `true_source_disagreements`: `254`
- `true_valuation_anomaly`: `0`
- `unsupported_earnings_event_claims`: `0`
- `unsupported_guidance_claims`: `0`
- `validation_errors`: `0`
- `validation_warnings`: `22`
- `valuation_specific_claim_count`: `40`
- `vendor_only_hard_claim_count`: `0`
- `vendor_only_hard_metrics_count`: `0`

## Frequent Issues

### Validation Issues

- `EARNINGS_DATE_UNAVAILABLE`: `22`

### Audit Issues

- `FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY`: `5`
- `TRUE_FINANCIAL_ANOMALY`: `5`
- `GUARD_THRESHOLD_REVIEW`: `2`
- `FCF_UNAVAILABLE_WITHOUT_IR_SUPPORT`: `1`
- `MISSING_CURRENT_PERIOD_KPI_CONTEXT`: `1`
- `MISSING_FCF_SUPPORT_FOR_ACCUMULATE`: `1`

### Evidence Issues

- `VENDOR_SOURCE_USED_AS_PRIMARY`: `0`
- `MISSING_DATE_FOR_NEWS_EVENT`: `0`
- `NO_PRIMARY_EVIDENCE_FOR_HARD_METRIC`: `0`
- `MISSING_EVIDENCE_FOR_METRIC`: `0`
- `GUIDANCE_CONSENSUS_CONFLATION`: `0`

### Reconciliation Warnings / Info

- `PERIOD_TYPE_MISMATCH_IGNORED`: `3714`
- `SOURCE_FRAME_VARIANT_IGNORED`: `270`
- `TRUE_SOURCE_VALUE_DISAGREEMENT`: `254`

## Ticker Results

| Ticker | Status | Quality | External Rating | External Action | True Disagreements | Ignored Variants |
|---|---|---:|---|---|---:|---:|
| GOOGL | passed | 95.0 | Hold |  | 2 | 108 |
| SNOW | passed | 95.0 | Tactical Underweight |  | 1 | 62 |
| MSFT | passed | 92.0 | Hold |  | 19 | 324 |
| AAPL | passed | 92.0 | Accumulate |  | 7 | 245 |
| META | passed | 95.0 | Hold |  | 10 | 140 |
| AMZN | manual_review | 76.0 | Hold |  | 18 | 470 |
| NFLX | passed | 90.0 | Hold |  | 7 | 288 |
| CRM | passed | 88.0 | Hold |  | 25 | 336 |
| DDOG | passed | 92.0 | Hold |  | 0 | 65 |
| NOW | manual_review | 78.0 | Hold |  | 15 | 190 |
| MDB | manual_review | 78.0 | Hold |  | 5 | 83 |
| NET | manual_review | 78.0 | Hold |  | 0 | 62 |
| ZS | manual_review | 78.0 | Hold |  | 0 | 76 |
| CRWD | manual_review | 60.0 | Hold |  | 2 | 46 |
| PANW | manual_review | 57.0 | Hold |  | 49 | 198 |
| NVDA | manual_review | 75.0 | Hold |  | 29 | 269 |
| AMD | manual_review | 74.0 | Hold |  | 14 | 218 |
| AVGO | passed | 90.0 | Hold |  | 2 | 98 |
| QCOM | manual_review | 87.0 | Hold Pending FCF Support | Accumulate only after FCF support | 25 | 183 |
| MU | manual_review | 74.0 | Hold |  | 9 | 242 |
| MRVL | manual_review | 78.0 | Hold |  | 12 | 66 |
| INTC | manual_review | 78.0 | Hold |  | 3 | 215 |
| TSM | data_unavailable | None |  |  | 0 | 0 |
| ASML | data_unavailable | None |  |  | 0 | 0 |
| RGTI | data_unavailable | None |  |  | 0 | 0 |
| IONQ | data_unavailable | None |  |  | 0 | 0 |
| QBTS | data_unavailable | None |  |  | 0 | 0 |
| QUBT | data_unavailable | None |  |  | 0 | 0 |
| SOUN | data_unavailable | None |  |  | 0 | 0 |
| BBAI | data_unavailable | None |  |  | 0 | 0 |
| RKLB | data_unavailable | None |  |  | 0 | 0 |
| ASTS | data_unavailable | None |  |  | 0 | 0 |
| ACHR | data_unavailable | None |  |  | 0 | 0 |
| JOBY | data_unavailable | None |  |  | 0 | 0 |
| RIVN | data_unavailable | None |  |  | 0 | 0 |
| LCID | data_unavailable | None |  |  | 0 | 0 |
| PLUG | data_unavailable | None |  |  | 0 | 0 |
| PYPL | data_unavailable | None |  |  | 0 | 0 |
| SNAP | data_unavailable | None |  |  | 0 | 0 |
| WBA | data_unavailable | None |  |  | 0 | 0 |
| PARA | data_unavailable | None |  |  | 0 | 0 |

## Best / Worst Result

- Best result: `GOOGL, SNOW, META` with quality `95.0`.
- Weakest result: `PANW` with quality `57.0`.

## Data Quality Ranking

### Top 5 Weakest Data Quality

- `TSM`: quality `None`, true disagreements `0`, validation errors `0`, audit errors `0`
- `ASML`: quality `None`, true disagreements `0`, validation errors `0`, audit errors `0`
- `RGTI`: quality `None`, true disagreements `0`, validation errors `0`, audit errors `0`
- `IONQ`: quality `None`, true disagreements `0`, validation errors `0`, audit errors `0`
- `QBTS`: quality `None`, true disagreements `0`, validation errors `0`, audit errors `0`

### Top 5 Best Data Quality

- `SNOW`: quality `95.0`, true disagreements `1`, validation errors `0`, audit errors `0`
- `GOOGL`: quality `95.0`, true disagreements `2`, validation errors `0`, audit errors `0`
- `META`: quality `95.0`, true disagreements `10`, validation errors `0`, audit errors `0`
- `DDOG`: quality `92.0`, true disagreements `0`, validation errors `0`, audit errors `0`
- `AAPL`: quality `92.0`, true disagreements `7`, validation errors `0`, audit errors `0`

## Source Ingestion Sufficiency

- Tickers where `source_ingestion_mode` was not sufficient: `AMZN, NOW, MDB, NET, ZS, CRWD, PANW, NVDA, AMD, QCOM, MU, MRVL, INTC, TSM, ASML, RGTI, IONQ, QBTS, QUBT, SOUN, BBAI, RKLB, ASTS, ACHR, JOBY, RIVN, LCID, PLUG, PYPL, SNAP, WBA, PARA`
- Recommendation: `nicht produktionsreif`

## Production Readiness Assessment

- `source_ingestion_mode` still needs manual review before production operation.
- Remaining production gaps: populate a real EarningsCalendar feed and broaden IR/guidance release coverage; source-ingestion post-audit is wired and counted.

## Artifact Check

- TSM missing report_manifest.json
- TSM missing quality_score.json
- TSM missing evidence_ledger.json
- TSM missing reconciliation_report.md
- TSM missing final_report.md or manual_review_required.md
- ASML missing report_manifest.json
- ASML missing quality_score.json
- ASML missing evidence_ledger.json
- ASML missing reconciliation_report.md
- ASML missing final_report.md or manual_review_required.md
- RGTI missing report_manifest.json
- RGTI missing quality_score.json
- RGTI missing evidence_ledger.json
- RGTI missing reconciliation_report.md
- RGTI missing final_report.md or manual_review_required.md
- IONQ missing report_manifest.json
- IONQ missing quality_score.json
- IONQ missing evidence_ledger.json
- IONQ missing reconciliation_report.md
- IONQ missing final_report.md or manual_review_required.md
- QBTS missing report_manifest.json
- QBTS missing quality_score.json
- QBTS missing evidence_ledger.json
- QBTS missing reconciliation_report.md
- QBTS missing final_report.md or manual_review_required.md
- QUBT missing report_manifest.json
- QUBT missing quality_score.json
- QUBT missing evidence_ledger.json
- QUBT missing reconciliation_report.md
- QUBT missing final_report.md or manual_review_required.md
- SOUN missing report_manifest.json
- SOUN missing quality_score.json
- SOUN missing evidence_ledger.json
- SOUN missing reconciliation_report.md
- SOUN missing final_report.md or manual_review_required.md
- BBAI missing report_manifest.json
- BBAI missing quality_score.json
- BBAI missing evidence_ledger.json
- BBAI missing reconciliation_report.md
- BBAI missing final_report.md or manual_review_required.md
- RKLB missing report_manifest.json
- RKLB missing quality_score.json
- RKLB missing evidence_ledger.json
- RKLB missing reconciliation_report.md
- RKLB missing final_report.md or manual_review_required.md
- ASTS missing report_manifest.json
- ASTS missing quality_score.json
- ASTS missing evidence_ledger.json
- ASTS missing reconciliation_report.md
- ASTS missing final_report.md or manual_review_required.md
- ACHR missing report_manifest.json
- ACHR missing quality_score.json
- ACHR missing evidence_ledger.json
- ACHR missing reconciliation_report.md
- ACHR missing final_report.md or manual_review_required.md
- JOBY missing report_manifest.json
- JOBY missing quality_score.json
- JOBY missing evidence_ledger.json
- JOBY missing reconciliation_report.md
- JOBY missing final_report.md or manual_review_required.md
- RIVN missing report_manifest.json
- RIVN missing quality_score.json
- RIVN missing evidence_ledger.json
- RIVN missing reconciliation_report.md
- RIVN missing final_report.md or manual_review_required.md
- LCID missing report_manifest.json
- LCID missing quality_score.json
- LCID missing evidence_ledger.json
- LCID missing reconciliation_report.md
- LCID missing final_report.md or manual_review_required.md
- PLUG missing report_manifest.json
- PLUG missing quality_score.json
- PLUG missing evidence_ledger.json
- PLUG missing reconciliation_report.md
- PLUG missing final_report.md or manual_review_required.md
- PYPL missing report_manifest.json
- PYPL missing quality_score.json
- PYPL missing evidence_ledger.json
- PYPL missing reconciliation_report.md
- PYPL missing final_report.md or manual_review_required.md
- SNAP missing report_manifest.json
- SNAP missing quality_score.json
- SNAP missing evidence_ledger.json
- SNAP missing reconciliation_report.md
- SNAP missing final_report.md or manual_review_required.md
- WBA missing report_manifest.json
- WBA missing quality_score.json
- WBA missing evidence_ledger.json
- WBA missing reconciliation_report.md
- WBA missing final_report.md or manual_review_required.md
- PARA missing report_manifest.json
- PARA missing quality_score.json
- PARA missing evidence_ledger.json
- PARA missing reconciliation_report.md
- PARA missing final_report.md or manual_review_required.md
