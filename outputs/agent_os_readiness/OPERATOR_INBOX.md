# Operator Inbox

Lokale Review-Inbox fuer Agent-OS-Arbeit. Das ist kein Chat-Gateway.

Gueltig: `true`
Fehler: `keine`
Warnungen: `keine`

| Item | Lane | Prioritaet | Status | Gate | Aktion | Zusammenfassung | Quelle |
| --- | --- | --- | --- | ---: | --- | --- | --- |
| `agent-os-readiness-review` | `operator_review` | `P0` | `ready_for_review` | false | `lesen_oder_bestaetigen` | Faehigkeitsmatrix und OpenClaw-Migrations-Trockenlauf vor jeder Runtime-Erweiterung pruefen. | `/Users/BjornRosinger/Documents/New project 2/outputs/agent_os_readiness/AGENT_OS_READINESS_REPORT.md` |
| `skill-registry-review` | `skill_governance` | `P1` | `ready_for_review` | false | `hold_oder_playbook_entscheidung_pruefen` | 29 lokale Skill-/Playbook-Eintraege klassifiziert; externe Installation bleibt verboten. | `/Users/BjornRosinger/Documents/New project 2/outputs/agent_os_readiness/SKILL_REGISTRY.md` |
| `memory-inbox-review` | `memory_promotion` | `P1` | `candidate_review` | true | `nur_nach_obsidian_routenpruefung_promoten` | 83 Memory-Kandidaten brauchen Promote-/Reject-/Merge-Review. | `/Users/BjornRosinger/Documents/New project 2/outputs/agent_os_readiness/MEMORY_INBOX_CANDIDATES.md` |
| `guardrail-gate-review` | `runtime_gate` | `P1` | `gate_review` | true | `gates_vor_runtime_rechten_klaeren_oder_akzeptieren` | 36 Guardrail-Funde sind als Gates vor Runtime-Erweiterung festgehalten. | `/Users/BjornRosinger/Documents/New project 2/outputs/agent_os_readiness/GUARDRAIL_SCAN.md` |
| `vault-semantic-ownership-review` | `memory_governance` | `P0` | `ready_for_review` | false | `vor_vault_clean_claim_pruefen_oder_findings_fixen` | 0 semantische Vault-Ownership-Funde; prueft aktive Projektwahrheit, Startflaechen und alte Gewohnheitsrouten. | `/Users/BjornRosinger/Documents/New project 2/outputs/agent_os_readiness/VAULT_SEMANTIC_OWNERSHIP_AUDIT.md` |
| `automation-card-review` | `automation_review` | `P2` | `ready_for_review` | true | `echte_automation_nur_nach_operator_go_erstellen` | Automation Cards sind nur Vorschlaege und keine installierten Automationen. | `/Users/BjornRosinger/Documents/New project 2/outputs/agent_os_readiness/AUTOMATION_JOB_CARDS.md` |
| `deliverable-swarm-review` | `deliverable_surface` | `P0` | `ready_for_review` | false | `vor_runtime_erweiterung_als_agenten_team_oberflaeche_nutzen` | 8 Deliverable-Lanes definieren Owner, Output-Pfade, Verifier, Handoffs und Gates. | `/Users/BjornRosinger/Documents/New project 2/outputs/agent_os_readiness/DELIVERABLE_SWARM_CONTRACT.md` |
