# Obsidian Memory Promotion Map

Status: active draft  
Scope: LIONCOM / Vega / Vivi / Obsidian / Room16  
Created: 2026-05-20

## Goal

Self-improving patterns may improve the system only by flowing through the existing Obsidian-backed memory and review system.

They must not create a second truth layer beside Obsidian, silently mutate behavior, or promote temporary observations into permanent rules without review.

## Existing Truth Layer

Obsidian / Human Overview is the primary long-term memory and orientation layer.

Controlled write targets:

- `Latest Session Context`
- relevant `Project - ...` notes
- `Canonical/...` notes
- `Memory/Learnings and Fixes.md`
- `Review Queue` for unresolved uncertainty

Temporary learnings are not automatically truth.

## Memory Tiers

| Tier | Meaning | Allowed use |
| --- | --- | --- |
| `HOT` | Temporary session/run note or active observation. | Local run artifacts and short-lived handoff context. |
| `WARM` | Recurring pattern candidate, not yet accepted as durable rule. | Review queue, project-note candidate or memory-promotion proposal. |
| `COLD` | Archived, historical or inactive learning. | Reference only; do not route behavior without revalidation. |
| `BACKBONE` | Confirmed durable rule, project truth or canonical fact. | Active routing and future session bootstrap. |

## Promotion Rules

| Evidence | Tier | Action |
| --- | --- | --- |
| 1 observation | `HOT` | Record with evidence and uncertainty. |
| 2 repetitions | `WARM candidate` | Create pattern key and check scope/risk. |
| 3 repetitions plus evidence | `promotion candidate` | Prepare Vivi Review or Operator-Go. |
| Vivi Review or Operator-Go plus evidence | `BACKBONE` | Write the smallest durable rule into Obsidian. |

No automatic Backbone change is allowed without a gate.

## Pattern-Key System

Every recurring learning candidate should use:

```yaml
pattern_key:
recurrence_count:
first_seen:
last_seen:
evidence_artifacts:
affected_project:
proposed_rule:
risk:
promotion_decision:
reviewer:
```

Prefer specific keys such as:

- `vivi.source_research.slug_only_overclaim`
- `lioncom.automation.active_without_success_proof`
- `obsidian.memory.parallel_truth_layer_risk`

## Allowed Writes

Allowed without Backbone promotion:

- temporary run notes
- run-local WAL entries
- project-local learning files with explicit status
- review proposals
- evidence manifests

Allowed only through explicit promotion:

- `Latest Session Context`
- Project Notes
- Canonical Notes
- durable Vivi/Vega behavior rules
- cross-project memory rules

## Forbidden Writes

Forbidden without explicit gate:

- global memory updates
- overwriting existing project truth
- private, secret, credential, token, account or OAuth data in learning files
- self-improving changes to runtime behavior without review
- background memory mutation
- rules that silently relax Operator Gates
- rules that turn temporary evidence into permanent truth

## Verify Implementation, Not Intent

A rule is accepted only when behavior or artifacts prove it.

Text such as "done", "fixed", "patched" or "will remember" is not enough.

Valid evidence includes:

- tests
- parser/checker result
- artifact diff
- reviewed bundle
- dashboard status
- API or browser smoke
- source-verification manifest
- VQG or Vega review result

If a rule changes a workflow, the verifier must check the workflow, not only the wording.

## WAL-lite For Long Runs

Long or multi-step runs may create a local `RUN_WAL.md` beside their artifacts.

Required fields:

```yaml
run_id:
started_at:
scope:
planned_action:
completed_action:
evidence_path:
unresolved:
next_allowed_step:
operator_gate_required:
```

Rules:

- WAL-lite is temporary execution state, not durable truth.
- WAL-lite may point to evidence, not replace it.
- Any durable learning from WAL-lite must use the promotion rules above.

## Acceptance Criteria

- No parallel memory layer is introduced.
- Self-improvement becomes an Obsidian promotion flow.
- Proactive-agent ideas are limited to WAL-lite and verification patterns.
- No autonomous background agent is created.
- Durable rules require evidence and gate.
