# Agent OS Readiness Report

This report captures safe Hermes/OpenClaw-inspired improvements without enabling external runtime behavior.

## Capability Matrix

| Capability | Status | Evidence | Next action |
| --- | --- | --- | --- |
| `openclaw_runtime_status` | `reference_only_until_preflight` | `/Users/BjornRosinger/Documents/Obsidian/Test Vaul Privat/Human Overview/Canonical/Systems/System - OpenClaw.md = present; /Users/BjornRosinger/.openclaw = missing` | Run explicit path/config/service/smoke preflight before treating OpenClaw as active. |
| `hermes_pattern_benchmark` | `captured` | `/Users/BjornRosinger/Documents/Obsidian/Test Vaul Privat/Human Overview/DreamFactory System/Agent Stack/Hermes Agent Benchmark - 2026-05-21.md` | Use as pattern source only; no external runtime install. |
| `openswarm_deliverable_benchmark` | `captured` | `/Users/BjornRosinger/Documents/Obsidian/Test Vaul Privat/Human Overview/DreamFactory System/Agent Stack/OpenSwarm Benchmark - 2026-05-21.md` | Use OpenSwarm as a deliverable-lane pattern source, not a runtime package. |
| `external_skill_intake` | `active` | `/Users/BjornRosinger/Documents/New project 2/docs/skills/EXTERNAL_SKILL_INTAKE_SOP.md` | Keep all external skills behind source verification, risk class, and operator gate. |
| `skill_registry_v1` | `implemented_local_artifact` | `/Users/BjornRosinger/Documents/New project 2/outputs/agent_os_readiness/SKILL_REGISTRY.md` | Refresh via scripts/ops/agent_os_readiness.py. |
| `memory_inbox_and_search` | `implemented_local_artifact` | `/Users/BjornRosinger/Documents/New project 2/outputs/agent_os_readiness/MEMORY_INBOX_CANDIDATES.md` | Promote candidates manually into Obsidian routes; index is local search only. |
| `automation_job_cards` | `implemented_proposal_artifact` | `/Users/BjornRosinger/Documents/New project 2/outputs/agent_os_readiness/AUTOMATION_JOB_CARDS.md` | Create real app automations only after operator review. |
| `deliverable_swarm_contract` | `implemented_local_artifact` | `/Users/BjornRosinger/Documents/New project 2/outputs/agent_os_readiness/DELIVERABLE_SWARM_CONTRACT.md` | Use as the visible lane/output contract before adding any new runtime rights. |
| `guardrails_as_code` | `implemented_local_scan` | `/Users/BjornRosinger/Documents/New project 2/outputs/agent_os_readiness/GUARDRAIL_SCAN.md` | Treat block/high findings as gates before runtime expansion. |
| `multi_channel_gateway` | `local_operator_inbox_contract_implemented` | `/Users/BjornRosinger/Documents/New project 2/outputs/agent_os_readiness/OPERATOR_INBOX.md` | Use the local inbox before considering any external chat gateway. |
| `terminal_backend_abstraction` | `local_and_docker_contracts_implemented` | `/Users/BjornRosinger/Documents/New project 2/outputs/agent_os_readiness/TERMINAL_BACKENDS.md` | Do not start Docker or expand execution rights without operator gate. |
| `hermes_home_presence` | `observed_only` | `/Users/BjornRosinger/.hermes = missing` | Do not read or import Hermes secrets without explicit operator gate. |

## OpenClaw Migration Dry Run

No files are copied by this dry run. Secret-sensitive sources are manifest-only.

| Source | Target | Status | Secret-sensitive | Action |
| --- | --- | --- | ---: | --- |
| `/Users/BjornRosinger/.openclaw/SOUL.md` | `lioncom_agent_os_staging/persona/SOUL.md` | `missing` | false | `no_source_found` |
| `/Users/BjornRosinger/.openclaw/AGENTS.md` | `lioncom_agent_os_staging/workspace/AGENTS.md` | `missing` | false | `no_source_found` |
| `/Users/BjornRosinger/.openclaw/MEMORY.md` | `lioncom_agent_os_staging/memory/imported_MEMORY.md` | `missing` | false | `no_source_found` |
| `/Users/BjornRosinger/.openclaw/USER.md` | `lioncom_agent_os_staging/memory/imported_USER.md` | `missing` | false | `no_source_found` |
| `/Users/BjornRosinger/.openclaw/skills` | `lioncom_agent_os_staging/skills/openclaw-imports` | `missing` | false | `no_source_found` |
| `/Users/BjornRosinger/.openclaw/openclaw.json` | `lioncom_agent_os_staging/config/openclaw.imported.json` | `missing` | true | `no_source_found` |
| `/Users/BjornRosinger/.openclaw/.env` | `lioncom_agent_os_staging/secrets/.env.redacted_manifest_only` | `missing` | true | `no_source_found` |
| `/Users/BjornRosinger/.openclaw/allowlist.json` | `lioncom_agent_os_staging/security/command_allowlist.imported.json` | `missing` | false | `no_source_found` |
