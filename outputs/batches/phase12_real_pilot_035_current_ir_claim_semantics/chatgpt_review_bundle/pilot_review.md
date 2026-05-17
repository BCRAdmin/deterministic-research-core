# Pilot Review - phase12_real_pilot_035_current_ir_claim_semantics

- As-of date: `2026-05-05`
- Batch status: `completed_with_issues`
- Tickers: `30`

## Status Summary

- Passed: `7`
- Repaired: `0`
- Manual review: `23`
- Failed: `0`
- Average quality score: `79.8`
- Median quality score: `78.0`
- Lowest quality score: `60.0`
- Repair rate: `0.0%`
- Manual review rate: `76.7%`

## Before / After Reconciliation

- Old `SOURCE_VALUE_DISAGREEMENT`: `not provided`
- New `true_source_disagreements`: `370`
- Ignored frame / period variants: `5299`

## Dashboard Counts

- `analyst_claim_count`: `547`
- `audit_errors`: `20`
- `audit_warnings`: `3`
- `canonical_metrics_created`: `30911`
- `company_defined_fcf_mismatch_count`: `0`
- `company_defined_fcf_used`: `3`
- `company_guidance_available_count`: `0`
- `company_specific_claim_count`: `199`
- `consensus_only_count`: `0`
- `content_completeness_score`: `2443`
- `data_bug`: `0`
- `data_limitation_claim_count`: `11`
- `earnings_confirmed_count`: `0`
- `earnings_unavailable_count`: `30`
- `earnings_within_10_trading_days_count`: `0`
- `evidence_mapped_claim_ratio`: `3000`
- `evidence_warnings`: `0`
- `fcf_unavailable_block_count`: `1`
- `financial_sanity_errors`: `14`
- `generic_claim_count`: `30`
- `generic_claim_ratio`: `175`
- `guard_threshold_review`: `3`
- `guidance_consensus_mismatch_count`: `0`
- `hard_claim_evidence_ratio`: `3000`
- `hard_claims_without_evidence_count`: `0`
- `ignored_frame_variants`: `5299`
- `missing_current_period_context_count`: `1`
- `period_bug`: `2`
- `rating_rationale_claim_count`: `30`
- `reconciliation_warnings`: `370`
- `sec_derived_fcf_used`: `0`
- `source_ingestion_post_audit_block_count`: `11`
- `substantive_analyst_claim_count`: `493`
- `substantive_claim_count`: `493`
- `substantive_claim_ratio`: `2700`
- `technical_specific_claim_count`: `30`
- `ticker_specific_kpi_claim_count`: `69`
- `true_anomaly`: `7`
- `true_source_disagreements`: `370`
- `unsupported_earnings_event_claims`: `0`
- `unsupported_guidance_claims`: `0`
- `validation_errors`: `0`
- `validation_warnings`: `30`
- `valuation_specific_claim_count`: `56`
- `vendor_only_hard_claim_count`: `0`

## Frequent Issues

### Validation Issues

- `EARNINGS_DATE_UNAVAILABLE`: `30`

### Audit Issues

- `FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY`: `7`
- `TRUE_FINANCIAL_ANOMALY`: `7`
- `GUARD_THRESHOLD_REVIEW`: `3`
- `CURRENT_PERIOD_IR_RECONCILIATION_REQUIRED`: `3`
- `MISSING_FCF_SUPPORT_FOR_ACCUMULATE`: `1`
- `FCF_UNAVAILABLE_WITHOUT_IR_SUPPORT`: `1`
- `MISSING_CURRENT_PERIOD_CONTEXT`: `1`

### Evidence Issues

- `NO_PRIMARY_EVIDENCE_FOR_HARD_METRIC`: `0`
- `VENDOR_SOURCE_USED_AS_PRIMARY`: `0`
- `MISSING_DATE_FOR_NEWS_EVENT`: `0`
- `GUIDANCE_CONSENSUS_CONFLATION`: `0`
- `MISSING_EVIDENCE_FOR_METRIC`: `0`

### Reconciliation Warnings / Info

- `PERIOD_TYPE_MISMATCH_IGNORED`: `4934`
- `TRUE_SOURCE_VALUE_DISAGREEMENT`: `370`
- `SOURCE_FRAME_VARIANT_IGNORED`: `365`

## Ticker Results

| Ticker | Status | Quality | Rating | True Disagreements | Ignored Variants |
|---|---|---:|---|---:|---:|
| AMZN | manual_review | 76.0 | Hold | 18 | 470 |
| MSFT | passed | 92.0 | Hold | 19 | 324 |
| GOOGL | passed | 95.0 | Hold | 2 | 108 |
| META | passed | 92.0 | Hold | 10 | 140 |
| AAPL | passed | 90.0 | Accumulate | 7 | 245 |
| NVDA | manual_review | 75.0 | Hold | 29 | 269 |
| AMD | manual_review | 74.0 | Hold | 14 | 218 |
| AVGO | passed | 87.0 | Hold | 2 | 98 |
| INTC | manual_review | 78.0 | Hold | 3 | 215 |
| QCOM | manual_review | 78.0 | Accumulate | 25 | 183 |
| MU | manual_review | 74.0 | Hold | 9 | 242 |
| MRVL | manual_review | 78.0 | Hold | 12 | 66 |
| ANET | manual_review | 74.0 | Hold | 8 | 177 |
| DDOG | manual_review | 78.0 | Hold | 0 | 65 |
| MDB | manual_review | 78.0 | Hold | 5 | 83 |
| SNOW | passed | 95.0 | Tactical Underweight | 1 | 62 |
| CRWD | manual_review | 60.0 | Hold | 2 | 46 |
| NET | manual_review | 78.0 | Hold | 0 | 62 |
| PANW | manual_review | 62.0 | Hold | 49 | 198 |
| ZS | manual_review | 78.0 | Hold | 0 | 76 |
| CRM | manual_review | 92.0 | Hold | 25 | 336 |
| NOW | manual_review | 78.0 | Hold | 15 | 190 |
| ORCL | manual_review | 78.0 | Hold | 3 | 189 |
| ADBE | manual_review | 78.0 | Hold | 22 | 229 |
| INTU | manual_review | 78.0 | Hold | 45 | 238 |
| UBER | manual_review | 78.0 | Hold | 5 | 68 |
| TSLA | manual_review | 78.0 | Hold | 23 | 213 |
| PLTR | manual_review | 74.0 | Hold | 1 | 56 |
| IBM | manual_review | 78.0 | Hold | 9 | 145 |
| NFLX | passed | 90.0 | Hold | 7 | 288 |

## Best / Worst Result

- Best result: `GOOGL, SNOW` with quality `95.0`.
- Weakest result: `CRWD` with quality `60.0`.

## Data Quality Ranking

### Top 5 Weakest Data Quality

- `CRWD`: quality `60.0`, true disagreements `2`, validation errors `0`, audit errors `2`
- `PANW`: quality `62.0`, true disagreements `49`, validation errors `0`, audit errors `2`
- `AMD`: quality `74.0`, true disagreements `14`, validation errors `0`, audit errors `2`
- `MU`: quality `74.0`, true disagreements `9`, validation errors `0`, audit errors `2`
- `ANET`: quality `74.0`, true disagreements `8`, validation errors `0`, audit errors `2`

### Top 5 Best Data Quality

- `SNOW`: quality `95.0`, true disagreements `1`, validation errors `0`, audit errors `0`
- `GOOGL`: quality `95.0`, true disagreements `2`, validation errors `0`, audit errors `0`
- `META`: quality `92.0`, true disagreements `10`, validation errors `0`, audit errors `0`
- `MSFT`: quality `92.0`, true disagreements `19`, validation errors `0`, audit errors `0`
- `CRM`: quality `92.0`, true disagreements `25`, validation errors `0`, audit errors `1`

## Source Ingestion Sufficiency

- Tickers where `source_ingestion_mode` was not sufficient: `AMZN, NVDA, AMD, INTC, QCOM, MU, MRVL, ANET, DDOG, MDB, CRWD, NET, PANW, ZS, CRM, NOW, ORCL, ADBE, INTU, UBER, TSLA, PLTR, IBM`
- Recommendation: `nicht produktionsreif`

## Production Readiness Assessment

- `source_ingestion_mode` still needs manual review before production operation.
- Remaining production gaps: populate a real EarningsCalendar feed and broaden IR/guidance release coverage; source-ingestion post-audit is wired and counted.

## Artifact Check

- All required dashboard artifact paths are present.
