# Market Readiness Guardrail Review - guardrail_coverage_batch_001

## Verdict

- `YELLOW`: usable as a controlled internal pilot batch, but not broad unattended market coverage because 19/41 listed tickers lack deterministic source inputs in this lane.

## Robust Enough For Pilot?

- Yes for the covered mega-cap, SaaS/security, and semiconductor subset: no batch abort, no failed tickers, no known false public-ready case, and QCOM display masking remains active.
- No for broad universe automation yet: the Deep-Tech/Space/Turnaround coverage is mostly data-unavailable in the current local provider set.

## Stable Archetypes

- `MEGA_CAP_PLATFORM`: GOOGL, MSFT, AAPL, META, AMZN, NFLX stayed out of deep-tech false positives.
- `SAAS_CONSUMPTION` / `STANDARD_GROWTH`: SNOW, CRM, DDOG and other software names stayed non-deep-tech after the DDOG priority fix.
- `SEMICONDUCTOR_AI_INFRA`: NVDA, AMD, AVGO, QCOM, MU, MRVL, INTC stayed in the semiconductor lane.

## Needs More Work

- Deep-Tech/Quantum, Early-Commercial Capital-Intensive, and Turnaround buckets need source-input coverage before this batch can judge them as a live source-ingestion group.
- PANW needs a focused evidence/data-confidence review because the report generated but data confidence is very low.

## Do Not Public

- Any `manual_review` item.
- Any `data_unavailable` item.
- Any `passed` item without a separate Promotion Gate and final public render.

## Internally Usable

- Passed/internal draft candidates: GOOGL, SNOW, MSFT, AAPL, META, NFLX, CRM, DDOG, AVGO.
- Manual-review research notes: AMZN, NOW, MDB, NET, ZS, CRWD, PANW, NVDA, AMD, QCOM, MU, MRVL, INTC.

## Good Regression Cases

- `GOOGL`, `SNOW`, `MSFT`: Gold/control and not deep-tech.
- `QCOM`: Hold Pending FCF Support display rule.
- `DDOG`: SaaS archetype should outrank generic platform wording.
- `RGTI`, `IONQ`, `QBTS`, `RKLB`: keep archetype sanity fixtures until live source inputs are available.

## Next 5 Systemic Fixes

1. Data-provider preflight by ticker/source artifact.
2. Coverage ingestion for missing Deep-Tech/Space/Turnaround tickers.
3. PANW evidence-confidence triage.
4. Story-stock taxonomy review for SOUN/BBAI after data arrives.
5. Bundle-level public-ready/promotion-status negative assertions for every passed review bundle.

## Next 7 Days

- Day 1-2: add missing source inputs and rerun unavailable tickers.
- Day 3: rerun Vivi batch review and matrix.
- Day 4: inspect PANW evidence/data-confidence failure.
- Day 5: run a smaller Deep-Tech/Space source-ingestion subset.
- Day 6-7: backtest false pass/false block candidates and update regression fixtures only where evidence supports it.
