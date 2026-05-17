# Systemic Fix Plan - guardrail_coverage_batch_001

## Fix 1 - Provider/source data gaps must not inflate pipeline failures

- Priority: `P1`
- Problem: The batch status model can currently represent missing source inputs only as `failed`, even when the pipeline correctly isolates the ticker and the issue is provider/input availability rather than a guardrail, rating, or report-generation failure.
- Affected tickers in this batch universe under the current local deterministic input set: `TSM`, `ASML`, `RGTI`, `IONQ`, `QBTS`, `QUBT`, `SOUN`, `BBAI`, `RKLB`, `ASTS`, `ACHR`, `JOBY`, `RIVN`, `LCID`, `PLUG`, `PYPL`, `SNAP`, `WBA`, `PARA`.
- Root cause: `BatchRunItem.status` and dashboard summaries distinguish `passed`, `repaired`, `manual_review`, and `failed`, but not `data_unavailable`. Exceptions classified as `data_error` or `source_ingestion_error` are always written as `failed`.
- File/module: `research_agent.batch.batch_status`, `research_agent.batch.batch_runner`, `research_agent.batch.dashboard_adapter`, `research_agent.batch.display_policy`, batch-status/dashboard tests.
- Expected behavior: Missing price, SEC/companyfacts, or source-ingestion provider inputs produce terminal status `data_unavailable`, increment dashboard `data_unavailable`, keep `publishable=false`, and keep the batch in `completed_with_issues` rather than aborting or creating a false system failure.
- Acceptance test: A batch runner fixture raising a missing-price/source-data exception records `status=data_unavailable`; dashboard summary includes `data_unavailable=1`; `final_batch_status` returns `completed_with_issues` when at least one ticker is data-unavailable and no pending/running items remain.
- Do-not-touch boundaries: No guard relaxation, no rating/display-rule relaxation, no ticker-specific exceptions, no fabricated data, no source-ingestion architecture change.

## Fix budget

- P0/P1 fixes allowed by sprint: `3`
- P0/P1 fixes planned so far: `2`

## Fix 2 - Specific SaaS/Semiconductor archetype cues must outrank generic "platform" language

- Priority: `P1`
- Problem: `DDOG` was classified as `MEGA_CAP_PLATFORM` in `dashboard_status.json` even though the archetype inference layer already recognizes `DDOG` as a SaaS/consumption company. The generic text token `platform` outranked the more specific SaaS/company cues.
- Affected tickers in this batch: observed `DDOG`; potential spillover to SaaS/security names whose reports use generic "platform" wording.
- Root cause: `_infer_non_deeptech_archetype` checks broad mega-cap/platform text terms before specific SaaS and semiconductor ticker/company indicators.
- File/module: `research_agent.quality.deeptech_manual_review`, archetype tests.
- Expected behavior: Specific ticker/company/sector cues for SaaS and semiconductors are evaluated before generic "platform" text. Generic platform language may still classify unknown platform businesses as `MEGA_CAP_PLATFORM`, but it must not override known SaaS/security/semiconductor cues already present in the taxonomy.
- Acceptance test: A `DDOG`/Datadog SaaS report that contains the word "platform" returns `SAAS_CONSUMPTION`, not `MEGA_CAP_PLATFORM`; existing MSFT/GOOGL mega-cap and semiconductor regression tests stay green.
- Do-not-touch boundaries: No guard relaxation, no new ticker exception outside existing taxonomy sets, no change to publishability thresholds, no rating behavior changes.
