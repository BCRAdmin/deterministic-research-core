# Quellwert Current State Summary

- Generated at: `2026-05-27T21:53:31+02:00`
- Status: `launch_pack_ready_for_operator_review`

## Operating Truth

- Batch: `guardrail_coverage_batch_004_ir_coverage`
- Internal operating status: `GREEN Operating Baseline`
- Current-period coverage: `32/32`
- Price basis date: `2026-05-15`
- Public output policy: Promotion-gated; no unattended public release.
- Vivi Review: `pass`

## Outcome Truth

- 1D Outcome: `computed`, `37` rows, `0` pending, false-pass flags `0`.
- 5D Outcome: `computed`, `37` rows, `0` pending.
- 5D false-pass candidate: `AVGO`.
- 5D curated false-block candidates: `NOW`, `RKLB`, `ZS`.
- Positive monitor: `MDB`.
- Next hard outcome window: `10D` on `2026-06-01`.

## Public Surface Truth

- Public preview routes exist for landing, analyses, methodology, archive, verifier, imprint, privacy, contact and three public sample analysis pages.
- Public sample analyses: `GOOGL`, `SNOW`, `MSFT`.
- Hidden review cases remain hidden: `NVDA`, `MU`.
- Current verifier state:
  - `npm run verify:quellwert-public-catalog-contract`: `PASS`
  - `npm run verify:quellwert-softlaunch-readiness`: `PASS`
  - Static hard-signal scan for Buy/Sell/Kursziel/Modellportfolio tokens: no hits.

## Remaining Gates

- `GOOGL` remains externally gated because source review still says `needs_review` and operator go is required.
- `SNOW` and `MSFT` remain pilot drafts, not external publication approvals.
- Founding Circle copy may be used as interest/waitlist draft only, not as investment offer or payment activation.
- Legal pages are preview-grade and need operator/legal review before external launch.
