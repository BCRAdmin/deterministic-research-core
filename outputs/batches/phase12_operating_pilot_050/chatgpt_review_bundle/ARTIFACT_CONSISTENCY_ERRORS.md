# ARTIFACT_CONSISTENCY_ERRORS

- Bundle: `/Users/BjornRosinger/Documents/New project 2/outputs/batches/phase12_operating_pilot_050/chatgpt_review_bundle`
- Status: `artifact_inconsistent`
- Error count: `2`

## Issues

### STALE_MANUAL_REVIEW_REASON

- Ticker: `MSFT`
- Artifact: `pilot_review.md`
- Message: Artifact contains a manual-review reason that is not current.
- Expected: `[]`
- Found: `TRUE_SOURCE_VALUE_DISAGREEMENT`

### STALE_ARTIFACT_ISSUE

- Ticker: `MSFT`
- Artifact: `pilot_review.md`
- Message: Artifact contains an issue code that is not present in current source of truth.
- Expected: `['Hold']`
- Found: `TRUE_SOURCE_VALUE_DISAGREEMENT`
