# GitHub Deep Research Entry - Deterministic Research Core

Stand: 2026-05-17

## Start Here

- `README.md` - core architecture and deterministic rules.
- `research_agent/` - deterministic research engine.
- `outputs/batches/guardrail_coverage_batch_004_ir_coverage/` - latest GREEN operating baseline.
- `outputs/source_inventory/` - source/input coverage.
- `BLOCKING_ISSUES.md` - known blockers and historical issues.

## Current Truth

This project keeps LLMs out of accounting and calculation. Python calculates and validates metrics; LLM agents may only interpret validated packets and registered sources.

Latest key baseline:

- Batch 004 IR Coverage, 2026-05-17.
- Fixture coverage: `32/32`.
- Result: `10 passed`, `22 manual_review`, `0 failed`, `0 data_unavailable`.
- Public output remains promotion-gated.

## Verification Baseline

- `python -m compileall -q research_agent` passed.
- `pytest -q` passed on 2026-05-17.

## Research Boundaries

- Do not treat batch `passed` as public publishing permission.
- Manual review, non-advice, source coverage and promotion gates remain binding.
- Preserve QCOM/Deep-Tech/manual-review display rules unless explicitly changed by the operator.
