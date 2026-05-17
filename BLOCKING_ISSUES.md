# Blocking Issues

## 2026-05-12 - phase12_operating_pilot_050 first attempt

- First attempt used `as_of_date = 2026-05-08`.
- Result: `18 failed`, `3 manual_review`, `9 passed`.
- Root cause: the 18 non-current tickers only had matching source registries on `2026-05-05`, so the run hit `MISSING_PRIMARY_FINANCIAL_SOURCE` and stopped at validation before report generation.
- This was not treated as a guard-loosening candidate.
- Resolution taken in the same session: rerun `phase12_operating_pilot_050` at the common latest available universe date `2026-05-05`.
- Final post-rerun result: `0 failed`, `21 manual_review`, `9 passed`.

## Remaining unresolved blockers

- None for the requested Pilot-v1 package build.
