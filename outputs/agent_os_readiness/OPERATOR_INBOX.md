# Operator Inbox

Local review inbox for Agent OS work. This is not a chat gateway.

Valid: `true`
Errors: `none`
Warnings: `none`

| Item | Lane | Priority | Status | Gate | Action | Source |
| --- | --- | --- | --- | ---: | --- | --- |
| `agent-os-readiness-review` | `operator_review` | `P0` | `ready_for_review` | false | `read_or_acknowledge` | `/Users/BjornRosinger/Documents/New project 2/outputs/agent_os_readiness/AGENT_OS_READINESS_REPORT.md` |
| `skill-registry-review` | `skill_governance` | `P1` | `ready_for_review` | false | `review_hold_or_playbook_decisions` | `/Users/BjornRosinger/Documents/New project 2/outputs/agent_os_readiness/SKILL_REGISTRY.md` |
| `memory-inbox-review` | `memory_promotion` | `P1` | `candidate_review` | true | `promote_only_after_obsidian_route_check` | `/Users/BjornRosinger/Documents/New project 2/outputs/agent_os_readiness/MEMORY_INBOX_CANDIDATES.md` |
| `guardrail-gate-review` | `runtime_gate` | `P1` | `gate_review` | true | `clear_or_accept_gates_before_runtime_rights` | `/Users/BjornRosinger/Documents/New project 2/outputs/agent_os_readiness/GUARDRAIL_SCAN.md` |
| `automation-card-review` | `automation_review` | `P2` | `ready_for_review` | true | `create_real_automation_only_after_operator_go` | `/Users/BjornRosinger/Documents/New project 2/outputs/agent_os_readiness/AUTOMATION_JOB_CARDS.md` |
| `deliverable-swarm-review` | `deliverable_surface` | `P0` | `ready_for_review` | false | `use_as_primary_agent_team_surface_before_runtime_expansion` | `/Users/BjornRosinger/Documents/New project 2/outputs/agent_os_readiness/DELIVERABLE_SWARM_CONTRACT.md` |
