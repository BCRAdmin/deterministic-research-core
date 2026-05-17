# Research Agent Deterministic Core

This project keeps LLM agents out of the accounting and calculation layer.

Core rule:

- Python calculates metrics.
- Python validates metrics and logic.
- LLM agents may only interpret validated packets.
- Final reports may use numbers only from `data_packet.json`, `metrics_packet.json`, `validation_report.json`, or explicitly registered sources in `source_registry.json`.

The initial build includes Pydantic packet schemas, technical/fundamental/valuation calculations, source-authority checks, trade/rating/news validation rules, regression tests for known failures, and a pipeline skeleton that stops report generation on blocking validation errors.

## Markdown Report Auditor

The post-generation auditor checks finished Markdown reports against validated packets:

```bash
python -m research_agent.audit.report_linter \
  --report path/to/report.md \
  --metrics path/to/metrics_packet.json \
  --validation path/to/validation_report.json \
  --sources path/to/source_registry.json
```

It emits `audit_report.json`-style output and exits with status `2` when blocking audit errors are found.

## Decision Engine

The final Investment Committee layer receives a deterministic `DecisionPacket` with:

- `allowed_ratings`
- `blocked_ratings`
- `preferred_rating`
- signal scores for fundamentals, technicals, valuation, and risk
- an action policy derived from the preferred rating

The final writer may not output a blocked rating. This keeps tactical trims from becoming accidental `Sell` calls and staged entries from becoming unconstrained `Buy` calls.

## Auto-Repair And Quality Gate

When a Markdown draft fails audit, the repair loop can attempt up to three controlled repairs and then re-run the auditor. Successful repairs can write:

- `repaired_report.md`
- `final_report.md`
- `quality_score.json`

If repair cannot clear blocking issues, the system writes `manual_review_required.md`, `draft_failed_audit.md`, and `audit_report.json` instead.

The quality gate requires a score of at least `85`, no blocking validation errors, no blocking audit errors, and a final rating allowed by `DecisionPacket`.
