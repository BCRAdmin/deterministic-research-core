# Agent-OS-Readiness-Bericht

Dieser Bericht sammelt sichere Hermes-/OpenClaw-inspirierte Verbesserungen, ohne externes Runtime-Verhalten zu aktivieren.

## Fähigkeitsmatrix

| Fähigkeit | Status | Evidenz | Nächste Aktion |
| --- | --- | --- | --- |
| `openclaw_runtime_status` | `reference_only_until_preflight` | `/Users/BjornRosinger/Documents/Obsidian/Test Vaul Privat/Human Overview/Canonical/Systems/System - OpenClaw.md = present; /Users/BjornRosinger/.openclaw = missing` | Vor aktiver OpenClaw-Nutzung expliziten Pfad-/Config-/Service-/Smoke-Preflight ausführen. |
| `hermes_pattern_benchmark` | `captured` | `/Users/BjornRosinger/Documents/Obsidian/Test Vaul Privat/Human Overview/DreamFactory System/Agent Stack/Hermes Agent Benchmark - 2026-05-21.md` | Nur als Musterquelle nutzen; keine externe Runtime installieren. |
| `openswarm_deliverable_benchmark` | `captured` | `/Users/BjornRosinger/Documents/Obsidian/Test Vaul Privat/Human Overview/DreamFactory System/Agent Stack/OpenSwarm Benchmark - 2026-05-21.md` | OpenSwarm als Deliverable-Lane-Muster nutzen, nicht als Runtime-Paket. |
| `external_skill_intake` | `active` | `/Users/BjornRosinger/Documents/New project 2/docs/skills/EXTERNAL_SKILL_INTAKE_SOP.md` | Alle externen Skills hinter Quellenprüfung, Risikoklasse und Operator-Gate halten. |
| `skill_registry_v1` | `implemented_local_artifact` | `/Users/BjornRosinger/Documents/New project 2/outputs/agent_os_readiness/SKILL_REGISTRY.md` | Über scripts/ops/agent_os_readiness.py aktualisieren. |
| `memory_inbox_and_search` | `implemented_local_artifact` | `/Users/BjornRosinger/Documents/New project 2/outputs/agent_os_readiness/MEMORY_INBOX_CANDIDATES.md` | Kandidaten manuell in Obsidian-Routen promoten; Index ist nur lokale Suche. |
| `vault_semantic_ownership_audit` | `implemented_local_gate` | `/Users/BjornRosinger/Documents/New project 2/outputs/agent_os_readiness/VAULT_SEMANTIC_OWNERSHIP_AUDIT.md` | Vor jedem Claim 'Vault ist sauber' semantische Ownership-, Startflächen- und Aging-Drift prüfen. |
| `automation_job_cards` | `implemented_proposal_artifact` | `/Users/BjornRosinger/Documents/New project 2/outputs/agent_os_readiness/AUTOMATION_JOB_CARDS.md` | Echte App-Automationen nur nach Operator-Review erstellen. |
| `deliverable_swarm_contract` | `implemented_local_artifact` | `/Users/BjornRosinger/Documents/New project 2/outputs/agent_os_readiness/DELIVERABLE_SWARM_CONTRACT.md` | Vor neuen Runtime-Rechten als sichtbaren Lane-/Output-Vertrag nutzen. |
| `guardrails_as_code` | `implemented_local_scan` | `/Users/BjornRosinger/Documents/New project 2/outputs/agent_os_readiness/GUARDRAIL_SCAN.md` | Block-/High-Funde vor Runtime-Erweiterung als Gates behandeln. |
| `agent_coding_guardrails` | `implemented_local_playbook` | `/Users/BjornRosinger/Documents/New project 2/outputs/agent_os_readiness/AGENT_CODING_GUARDRAILS.md` | Karpathy-Minimalismus und Superpowers-Verification/Debugging als lokale Coding-Checks nutzen; keine Plugin-Installation. |
| `multi_channel_gateway` | `local_operator_inbox_contract_implemented` | `/Users/BjornRosinger/Documents/New project 2/outputs/agent_os_readiness/OPERATOR_INBOX.md` | Zuerst lokale Inbox nutzen, bevor ein externes Chat-Gateway erwogen wird. |
| `terminal_backend_abstraction` | `local_and_docker_contracts_implemented` | `/Users/BjornRosinger/Documents/New project 2/outputs/agent_os_readiness/TERMINAL_BACKENDS.md` | Docker nicht starten und Ausführungsrechte nicht ohne Operator-Gate erweitern. |
| `hermes_home_presence` | `observed_only` | `/Users/BjornRosinger/.hermes = missing` | Hermes-Secrets nicht ohne explizites Operator-Gate lesen oder importieren. |

## OpenClaw-Migrations-Trockenlauf

Dieser Trockenlauf kopiert keine Dateien. Secret-sensitive Quellen werden nur als Manifest geführt.

| Quelle | Ziel | Status | Secret-sensitiv | Aktion |
| --- | --- | --- | ---: | --- |
| `/Users/BjornRosinger/.openclaw/SOUL.md` | `lioncom_agent_os_staging/persona/SOUL.md` | `missing` | false | `no_source_found` |
| `/Users/BjornRosinger/.openclaw/AGENTS.md` | `lioncom_agent_os_staging/workspace/AGENTS.md` | `missing` | false | `no_source_found` |
| `/Users/BjornRosinger/.openclaw/MEMORY.md` | `lioncom_agent_os_staging/memory/imported_MEMORY.md` | `missing` | false | `no_source_found` |
| `/Users/BjornRosinger/.openclaw/USER.md` | `lioncom_agent_os_staging/memory/imported_USER.md` | `missing` | false | `no_source_found` |
| `/Users/BjornRosinger/.openclaw/skills` | `lioncom_agent_os_staging/skills/openclaw-imports` | `missing` | false | `no_source_found` |
| `/Users/BjornRosinger/.openclaw/openclaw.json` | `lioncom_agent_os_staging/config/openclaw.imported.json` | `missing` | true | `no_source_found` |
| `/Users/BjornRosinger/.openclaw/.env` | `lioncom_agent_os_staging/secrets/.env.redacted_manifest_only` | `missing` | true | `no_source_found` |
| `/Users/BjornRosinger/.openclaw/allowlist.json` | `lioncom_agent_os_staging/security/command_allowlist.imported.json` | `missing` | false | `no_source_found` |
