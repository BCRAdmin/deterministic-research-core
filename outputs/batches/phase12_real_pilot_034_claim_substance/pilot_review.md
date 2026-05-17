# Pilot Review - phase12_real_pilot_034_claim_substance

- As-of date: `2026-05-05`
- Batch status: `completed_with_issues`
- Tickers: `30`

## Status Summary

- Passed: `6`
- Repaired: `0`
- Manual review: `24`
- Failed: `0`
- Average quality score: `71.66666666666667`
- Median quality score: `73.0`
- Lowest quality score: `34.0`
- Repair rate: `0.0%`
- Manual review rate: `80.0%`

## Before / After Reconciliation

- Old `SOURCE_VALUE_DISAGREEMENT`: `not provided`
- New `true_source_disagreements`: `370`
- Ignored frame / period variants: `5299`

## Dashboard Counts

- `analyst_claim_count`: `540`
- `audit_errors`: `44`
- `audit_warnings`: `1`
- `canonical_metrics_created`: `30901`
- `company_guidance_available_count`: `0`
- `company_specific_claim_count`: `70`
- `consensus_only_count`: `0`
- `content_completeness_score`: `2452`
- `earnings_confirmed_count`: `0`
- `earnings_unavailable_count`: `30`
- `earnings_within_10_trading_days_count`: `0`
- `evidence_mapped_claim_ratio`: `3000`
- `evidence_warnings`: `0`
- `financial_sanity_errors`: `28`
- `generic_claim_ratio`: `180`
- `guidance_consensus_mismatch_count`: `0`
- `hard_claim_evidence_ratio`: `3000`
- `hard_claims_without_evidence_count`: `0`
- `ignored_frame_variants`: `5299`
- `rating_rationale_claim_count`: `30`
- `reconciliation_warnings`: `370`
- `source_ingestion_post_audit_block_count`: `24`
- `substantive_analyst_claim_count`: `480`
- `technical_specific_claim_count`: `30`
- `true_source_disagreements`: `370`
- `unsupported_earnings_event_claims`: `0`
- `unsupported_guidance_claims`: `0`
- `validation_errors`: `0`
- `validation_warnings`: `30`
- `valuation_specific_claim_count`: `60`
- `vendor_only_hard_claim_count`: `0`

## Frequent Issues

### Validation Issues

- `EARNINGS_DATE_UNAVAILABLE`: `30`

### Audit Issues

- `NUMERIC_MISMATCH`: `12`
- `FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY`: `9`
- `FINANCIAL_SANITY_EV_SALES_ABSURD`: `8`
- `FINANCIAL_SANITY_FCF_MARGIN_ANOMALY`: `7`
- `FINANCIAL_SANITY_SBC_REVENUE_ANOMALY`: `4`
- `CURRENT_PERIOD_IR_RECONCILIATION_REQUIRED`: `3`
- `MISSING_FCF_SUPPORT_FOR_ACCUMULATE`: `1`
- `UNVERIFIED_HARD_METRIC`: `1`

### Evidence Issues

- `GUIDANCE_CONSENSUS_CONFLATION`: `0`
- `MISSING_EVIDENCE_FOR_METRIC`: `0`
- `VENDOR_SOURCE_USED_AS_PRIMARY`: `0`
- `MISSING_DATE_FOR_NEWS_EVENT`: `0`
- `NO_PRIMARY_EVIDENCE_FOR_HARD_METRIC`: `0`

### Reconciliation Warnings / Info

- `PERIOD_TYPE_MISMATCH_IGNORED`: `4934`
- `TRUE_SOURCE_VALUE_DISAGREEMENT`: `370`
- `SOURCE_FRAME_VARIANT_IGNORED`: `365`

## Ticker Results

| Ticker | Status | Quality | Rating | True Disagreements | Ignored Variants |
|---|---|---:|---|---:|---:|
| AMZN | manual_review | 76.0 | Accumulate | 18 | 470 |
| MSFT | manual_review | 76.0 | Hold | 19 | 324 |
| GOOGL | passed | 92.0 | Hold | 2 | 108 |
| META | passed | 92.0 | Hold | 10 | 140 |
| AAPL | manual_review | 76.0 | Accumulate | 7 | 245 |
| NVDA | manual_review | 34.0 | Hold | 29 | 269 |
| AMD | manual_review | 76.0 | Hold | 14 | 218 |
| AVGO | passed | 92.0 | Hold | 2 | 98 |
| INTC | passed | 92.0 | Hold | 3 | 215 |
| QCOM | manual_review | 92.0 | Accumulate | 25 | 183 |
| MU | manual_review | 76.0 | Hold | 9 | 242 |
| MRVL | manual_review | 76.0 | Hold | 12 | 66 |
| ANET | manual_review | 34.0 | Hold | 8 | 177 |
| DDOG | manual_review | 92.0 | Hold | 0 | 65 |
| MDB | manual_review | 49.0 | Hold | 5 | 83 |
| SNOW | passed | 92.0 | Tactical Underweight | 1 | 62 |
| CRWD | manual_review | 70.0 | Hold | 2 | 46 |
| NET | manual_review | 65.0 | Hold | 0 | 62 |
| PANW | manual_review | 63.0 | Hold | 49 | 198 |
| ZS | manual_review | 70.0 | Hold | 0 | 76 |
| CRM | manual_review | 92.0 | Hold | 25 | 336 |
| NOW | manual_review | 34.0 | Hold | 15 | 190 |
| ORCL | manual_review | 70.0 | Hold | 3 | 189 |
| ADBE | manual_review | 70.0 | Hold | 22 | 229 |
| INTU | manual_review | 46.0 | Hold | 45 | 238 |
| UBER | manual_review | 64.0 | Hold | 5 | 68 |
| TSLA | manual_review | 63.0 | Hold | 23 | 213 |
| PLTR | manual_review | 64.0 | Hold | 1 | 56 |
| IBM | manual_review | 70.0 | Hold | 9 | 145 |
| NFLX | passed | 92.0 | Hold | 7 | 288 |

## Best / Worst Result

- Best result: `GOOGL, META, AVGO, INTC, QCOM, DDOG, SNOW, CRM, NFLX` with quality `92.0`.
- Weakest result: `NVDA, ANET, NOW` with quality `34.0`.

## Data Quality Ranking

### Top 5 Weakest Data Quality

- `NOW`: quality `34.0`, true disagreements `15`, validation errors `0`, audit errors `5`
- `ANET`: quality `34.0`, true disagreements `8`, validation errors `0`, audit errors `5`
- `NVDA`: quality `34.0`, true disagreements `29`, validation errors `0`, audit errors `4`
- `INTU`: quality `46.0`, true disagreements `45`, validation errors `0`, audit errors `3`
- `MDB`: quality `49.0`, true disagreements `5`, validation errors `0`, audit errors `3`

### Top 5 Best Data Quality

- `SNOW`: quality `92.0`, true disagreements `1`, validation errors `0`, audit errors `0`
- `GOOGL`: quality `92.0`, true disagreements `2`, validation errors `0`, audit errors `0`
- `AVGO`: quality `92.0`, true disagreements `2`, validation errors `0`, audit errors `0`
- `INTC`: quality `92.0`, true disagreements `3`, validation errors `0`, audit errors `0`
- `NFLX`: quality `92.0`, true disagreements `7`, validation errors `0`, audit errors `0`

## Source Ingestion Sufficiency

- Tickers where `source_ingestion_mode` was not sufficient: `AMZN, MSFT, AAPL, NVDA, AMD, QCOM, MU, MRVL, ANET, DDOG, MDB, CRWD, NET, PANW, ZS, CRM, NOW, ORCL, ADBE, INTU, UBER, TSLA, PLTR, IBM`
- Recommendation: `nicht produktionsreif`

## Production Readiness Assessment

- `source_ingestion_mode` still needs manual review before production operation.
- Remaining production gaps: populate a real EarningsCalendar feed and broaden IR/guidance release coverage; source-ingestion post-audit is wired and counted.

## Artifact Check

- All required dashboard artifact paths are present.
