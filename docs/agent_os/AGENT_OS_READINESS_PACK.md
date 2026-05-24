# Agent-OS-Readiness-Paket

Status: aktive lokale v1
Scope: LIONCOM / Vega / Vivi / OpenClaw / sichere Hermes-Musteruebernahme
Runtime-Änderungen: keine

## Zweck

Dieses Paket übersetzt die nützlichen Hermes-Agent-Muster in sichere lokale
Arbeitsoberflaechen:

- Readiness- und Migrations-Trockenlauf
- lokale Skill Registry
- Memory Inbox und lokale Suche
- Automation Job Cards
- Deliverable-Swarm-Lanes und Output-Verträge
- Portfolio-Produktoberflächen-Audit für die kanonischen Projektkarten
- Vault Semantic Ownership Audit für Projektwahrheit, Startflächen und alte Gewohnheitsrouten
- Guardrails-as-Code
- Agent Coding Guardrails als kuratierter Superpowers-/Karpathy-Transfer
- Operator-Inbox-Vertrag
- Terminal-Backend-Verträge

Es ist absichtlich kein Gateway, kein externer Skill-Installer, kein
Secret-Importer und kein autonomer Hintergrundagent.

## Befehl

```bash
python3 scripts/ops/agent_os_readiness.py
```

Standard-Outputs werden nach `outputs/agent_os_readiness/` geschrieben.

## Output-Vertrag

- `AGENT_OS_READINESS_REPORT.md/json`: Fähigkeitsmatrix und OpenClaw-Migrations-Trockenlauf.
- `SKILL_REGISTRY.md/json`: lokales Skill-/Playbook-Inventar mit Risikoklasse und Runtime-Entscheidung.
- `MEMORY_INBOX_CANDIDATES.md/json`: Promotionskandidaten für Obsidian-Review.
- `SESSION_SEARCH.sqlite`: lokaler Markdown-Suchindex.
- `SESSION_SEARCH_SAMPLE.json`: Beispiel-Suchergebnisse.
- `AUTOMATION_JOB_CARDS.md/json`: vorgeschlagene sichere Automation Cards, keine installierten Automationen.
- `DELIVERABLE_SWARM_CONTRACT.md/json`: OpenSwarm-inspirierte Lane-Matrix und Output-Vertrag.
- `DELIVERABLE_SWARM_OPERATING_OVERVIEW.md`: Wo-/Wann-/Wie-Nutzungsübersicht für den Vertrag.
- `DELIVERABLE_SWARM_OPERATING_MAP.canvas`: JSON-Canvas-Schaubild.
- `PORTFOLIO_PRODUCT_SURFACE_AUDIT.md/json`: Einzelpruefung der Projektkarten auf sichtbare Lieferoberfläche, Owner-Lanes, Gates und nächste sichere Aktion.
- `PORTFOLIO_PRODUCT_SURFACE_MAP.canvas`: JSON-Canvas-Schaubild für die Projektoberflächen.
- `VAULT_SEMANTIC_OWNERSHIP_AUDIT.md/json`: semantischer Drift-Check für aktive Projektowner, Startflächen, alte Routing-Phrasen, Status-Aging und Gate-Inversion.
- `AGENT_CODING_GUARDRAILS.md/json`: lokale Coding-Agent-Guardrails aus Superpowers-/Karpathy-Patterns, ohne Plugin-Installation.
- `OPERATOR_INBOX.md/json`: lokale Review-Inbox, kein Chat-Gateway.
- `TERMINAL_BACKENDS.md/json`: lokale/Docker-Backend-Verträge, keine laufenden Backends.
- `GUARDRAIL_SCAN.md/json`: lokale statische Guardrail-Funde.
- `RUN_SUMMARY.json`: maschinenlesbare Laufzusammenfassung.

## Harte Grenzen

- Es werden keine externen Skills installiert.
- Es werden keine API-Keys oder Secret-Werte in Outputs gelesen.
- Es wird keine Runtime-Config geändert.
- Das Script aktualisiert keine kanonische Obsidian-Notiz.
- Das Script erstellt keine Automation.
- Es werden keine Netzwerkaufrufe gemacht.

## Übernahmeregel

Hermes ist ein Produktmuster-Benchmark. Jede Funktion, die Netzwerk,
Credentials, Hintergrundausfuehrung, Desktop-/Browser-Control oder kanonische
Memory-Mutation einfuehren wuerde, bleibt hinter External Skill Intake SOP und
Operator-Gate.

OpenSwarm ist ein Deliverable-Surface-Benchmark. Das nützliche Muster sind
sichtbare Spezialisten-Lanes und explizite finale Artefaktvertraege. Auto-
Install-, Composio-weite, Full-Mesh- und Provider-Runtime-Verhalten wird nicht
übernommen.

Superpowers und Karpathy-Skills sind Coding-Verhaltens-Benchmarks. Das
nützliche Muster sind kleine Diffs, Annahmentransparenz, Root-Cause-Debugging
und frische Verifikation vor Abschlussbehauptungen. Globale Session-Hooks,
Skill-Zwang, automatische Worktrees, Spec-Commit-Pflichten für Kleinkram und
Subagent-Defaults werden nicht übernommen.
