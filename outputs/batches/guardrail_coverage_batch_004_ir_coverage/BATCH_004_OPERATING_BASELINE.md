# Batch 004 Operating Baseline

- Batch-ID: `guardrail_coverage_batch_004_ir_coverage`
- Ticker count: `32`
- operator-facing passed/manual_review/failed/data_unavailable: `9 / 23 / 0 / 0`
- Current-period coverage: `32/32`
- Price basis date: `2026-05-15`
- Vivi status: `pass`
- Market readiness verdict: `GREEN`

## Known Limits

- Public output remains blocked by the Promotion Gate; GREEN means operating baseline, not default public publishing.
- 11 P0/P1 names still prefer direct IR/earnings-release replacements; current coverage is valid but partly SEC-derived.
- Manual-review reports stay internal-only until human/operator review and promotion artifacts exist.
- Price basis is fresh as latest available trading data, but the batch as-of date is Sunday 2026-05-17 and price basis is Friday 2026-05-15.

## Allowed Operating Mode

- Use Batch 004 as the current internal research operating baseline.
- Use passed reports for internal publish-review queue only; public routing still requires Promotion Gate.
- Use manual_review reports as internal research notes and data-ops targets.
- Track outcomes at 1D/5D/10D/20D/60D windows against assigned benchmarks.

## Not Allowed Operating Mode

- Do not treat GREEN as unattended public-ready status.
- Do not bypass manual_review, artifact consistency, source, or promotion gates.
- Do not present SEC-derived current-period fixtures as direct company guidance.
- Do not create public reports from manual_review cases without human approval and final render.

## Superseded Raw State Cleanup

- QCOM raw Batch004 `passed / Accumulate` is superseded. Superseded by manual_focus_guardrail_final_check. Do not use for promotion.
- Current QCOM operator-facing status: `manual_review / Hold Pending FCF Support`.
- Public and passed bundles must not use raw Batch004 QCOM as current truth.
