# OpenJarvis Component Adapter

- Status: `PASS`
- Entscheidung: `harvest_and_rebuild_selected_patterns`
- Komponenten: `6`
- Adapt-ready: `4`
- Gated-ready: `1`
- Derzeit abgelehnt: `1`
- Trial-Report: `/Users/BjornRosinger/Documents/DreamFactory/Room16/research-agent-ops/outputs/openjarvis_capability_lab/operator_trials/20260525T005539Z/reports/OPENJARVIS_OPERATOR_TRIALS_REPORT.json`

## Komponenten

| Komponente | Status | Modus | Wert | Risiko | Ziel |
| --- | --- | --- | --- | --- | --- |
| `github_dependabot_digest` | `ADAPT_READY` | `rebuild_locally` | `high` | `low` | PIG/LIONCOM read-only PR and dependency digest |
| `tool_surface_audit` | `ADAPT_READY` | `copy_pattern_then_harden` | `high` | `medium` | Vega/PIG tool-permission matrix and operator gate surface |
| `skill_mining` | `ADAPT_READY` | `mine_read_only_then_rebuild` | `high` | `medium` | Vega skill registry and curated local Codex skills |
| `retrieval_shadow` | `ADAPT_READY` | `keep_benchmark_and_copy_winning_queries` | `medium_high` | `low` | PIG/Obsidian retrieval arena |
| `runtime_sandbox_protocol` | `GATED_READY` | `keep_operator_gated` | `medium` | `medium` | Disposable runtime trial wrapper |
| `write_fix_worker` | `REJECT_CURRENT` | `reject_currently` | `low_current` | `high` | None until a better wrapper exists |

## Read-only Digest

- Status: `PASS`
- Repos: `10`
- Offene PRs: `12`
- Dependabot-PRs: `12`
- Mutationen: `False`

## Skill / Automation

- Skill: `openjarvis-capability-adapter`
- Skill-Pfad: `/Users/BjornRosinger/.codex/skills/openjarvis-capability-adapter`
- Automation-Kandidat: `openjarvis_digest_weekly_review`
- Automation-Status: `proposed_local_review_only`

## Harte Regeln

- `openjarvis_patterns_are_inspiration_not_authority`
- `copy_good_patterns_into_vega_pig_lioncom_before_runtime_adoption`
- `real_repo_writes_require_a_disposable_workspace_wrapper_first`
- `github_digest_is_read_only_until_separate_operator_go`
- `external_skills_are_mined_read_only_before_becoming_local_skills`

## Nächste Build-Ziele

- `wire_component_adapter_into_agent_os_readiness`
- `surface_adapter_summary_in_pig_and_lioncom`
- `keep_weekly_digest_as_local_review_job_card`
- `iterate_skill_mining_against Hermes/OpenClaw sources only through guardrails`
