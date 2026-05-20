# Deliverable Swarm Contract

Status: active local v1
Runtime changes: none
Source pattern: VRSEN/OpenSwarm, pattern-only

## Purpose

This contract turns the useful OpenSwarm product pattern into a safe local
surface for Vega, Vivi, LIONCOM, and OpenClaw work.

The adopted pattern is simple:

- an orchestrator routes work
- specialists own deliverables
- every deliverable has an output path
- every final artifact has a verifier
- provider, account, scheduled-runner, or publishing behavior must not run without a gate

## Required Lanes

- `orchestrator`: route plan and handoff packet
- `assistant`: operator notes, draft messages, task summaries
- `research`: research briefs, source matrices, decision options
- `data`: analysis reports, chart assets, data quality notes
- `docs`: markdown, DOCX, PDF, change summaries
- `slides`: slide sources, PPTX deck, visual QA
- `images`: image assets and image QC, provider-gated
- `video`: video assets and video QC, provider-gated

## Output Metadata

Every final artifact needs:

- `artifact_id`
- `lane_id`
- `artifact_type`
- `output_path`
- `status`
- `verifier`
- `blocked_gates`
- `next_action`

## Handoff Policy

The orchestrator may route to every specialist lane. Specialist lanes return to
the orchestrator or to a narrow downstream artifact lane. A hidden all-to-all
runtime mesh is not allowed.

## Hard Boundaries

- no auto-install of external runtimes
- no system package installation
- no automatic external account connection
- no secret import
- no public publishing
- no canonical Obsidian write by generated runtime
- no background automation creation
- no unbounded all-to-all handoff runtime

## Command

```bash
python3 scripts/ops/agent_os_readiness.py
```

Generated outputs:

- `outputs/agent_os_readiness/DELIVERABLE_SWARM_CONTRACT.md`
- `outputs/agent_os_readiness/DELIVERABLE_SWARM_CONTRACT.json`
