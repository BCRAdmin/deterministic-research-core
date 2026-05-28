# 10D Outcome Runner Readiness - 2026-05-28

Status: `runner_built_pending_price_data`

## Decision

The 10D outcome block is technically ready, but not computable before the real evaluation date `2026-06-01`. The current local price CSVs end at `2026-05-22`, so the correct state is `pending_price_data`.

## Runner

Command for the real 10D run:

```bash
python3 scripts/outcomes/compute_outcome_window_artifacts.py --window 10D --batch-id guardrail_coverage_batch_004_ir_coverage --focus-batch-id manual_focus_guardrail_final_check
```

Readiness command used today:

```bash
python3 scripts/outcomes/compute_outcome_window_artifacts.py --window 10D --readiness-only --readiness-output outputs/quellwert_room16_operating/closure_sprint_2026-05-28/10D_OUTCOME_RUNNER_READINESS.json
```

## Guardrails

- No synthetic prices.
- No forward-fill.
- No replacement end date.
- No calibration from 10D alone.
- No rating, report, or guard change from one outcome window alone.

## Expected Artifacts On 2026-06-01

- `OUTCOME_10D_REVIEW.json`
- `OUTCOME_10D_REVIEW.md`
- `OUTCOME_10D_TRIAGE_SUMMARY.json`
- `OUTCOME_10D_TRIAGE_SUMMARY.md`
- `OUTCOME_10D_WATCHLIST_REVIEW.json`
- `OUTCOME_10D_WATCHLIST_REVIEW.md`
- `VIVI_OUTCOME_10D_REVIEW.json`
