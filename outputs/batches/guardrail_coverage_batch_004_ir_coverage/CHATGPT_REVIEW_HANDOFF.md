# ChatGPT Review Handoff - Batch 004 Focus Bundles

- Source batch: `guardrail_coverage_batch_004_ir_coverage`
- Generated at: `2026-05-17T03:26:13Z`

## Passed Sample Tickers

SNOW, GOOGL, META, QCOM, CRM, NFLX, AVGO

## Manual Focus Tickers

IONQ, NVDA, QBTS, QCOM, RGTI

## QCOM

QCOM is `passed`, not `manual_review`. It is included in the manual-focus bundle only as a P0 Data-Ops priority. In Batch 004 it has `publish_quality_score=87`, artifact consistency is clean, audit issues are empty, and the decision corridor allows `Accumulate`. The previous FCF-support concern is not active as a manual-review issue in this run, but direct IR/Earnings replacement remains useful because the current FCF view is not a direct company-defined FCF fixture.

## AVGO

AVGO is `passed` with `publish_quality_score=90`, `data_confidence_score=77`, clean artifact consistency, and external display `Hold`. It is selected as the high-risk/high-valuation sample because EV/Sales is about `31.74x` and price/FCF about `91.76x`; the audit treats this as a semiconductor-context review warning, not a blocker, and the rating is not a clean Buy.

## CRM Evidence / Reconciliation Status

CRM is `passed` with `publish_quality_score=88`, `data_confidence_score=68`, clean artifact consistency, and no audit issues. Validation has only prior-close and unavailable-earnings-date warnings. Reconciliation warnings exist as source-frame/period/source-value items, but they are not artifact-consistency blockers.

## Regression Checks

- GOOGL regressed: no. Status `passed`, publish quality `93`, artifact consistency clean.
- SNOW regressed: no. Status `passed`, publish quality `93`, artifact consistency clean.

## Sample Risk Flags

- Artifact consistency errors in selected samples: `none`
- Selected tickers with publish_quality_score below 75: `IONQ, NVDA, QBTS, RGTI`
- Selected tickers with data_confidence_score below 70: `CRM, IONQ, NVDA, QBTS, QCOM, RGTI`

## Bundles

- Passed sample bundle: `outputs/batches/guardrail_coverage_batch_004_ir_coverage/chatgpt_passed_sample_review_bundle.zip`
- Manual focus bundle: `outputs/batches/guardrail_coverage_batch_004_ir_coverage/chatgpt_manual_focus_review_bundle.zip`
