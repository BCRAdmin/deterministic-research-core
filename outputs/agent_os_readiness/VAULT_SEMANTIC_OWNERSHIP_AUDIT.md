# Vault Semantic Ownership Audit

Dieser Bericht prüft semantische Ownership-Drift im Vega/Obsidian-Backbone.
Er ist kein Security-Audit, sondern ein Operator-Entlastungscheck: Vivi und Vega sollen falsche alte Projektwahrheit finden, bevor Bjorn sie benennen muss.

Gültig: `true`
Vault: `/Users/BjornRosinger/Documents/Obsidian/Test Vaul Privat/Human Overview`
Geprüfte Dateien: `11`
Findings: `0`

## Blickwinkel

| ID | Blickwinkel | Prüffrage | Findet | Operator-Entlastung |
| --- | --- | --- | --- | --- |
| `ownership` | Ownership statt Linkstatus | Welche Karte fuehrt diese Entität heute? | Aktive Nachfolge-Lanes in alten Projektkarten. | Bjorn muss nicht merken, welche alte Note früher führend war. |
| `start_surface_alignment` | Startflächen-Abgleich | Zeigen Human-, Agenten-, System- und Canonical-Starts dieselbe aktive Spur? | Neue Projektkarten, die nur in einer Detailnote sichtbar sind. | Neue Sessions starten richtig, ohne dass der Operator routen muss. |
| `body_semantics` | Body-Semantik statt Frontmatter | Widersprechen alte Abschnitte dem Status oben in der Note? | Notes mit korrektem `waiting`/`parked` Status, aber aktiv klingenden Body-Abschnitten. | Vivi/Vega müssen nicht aus Chronik-Waenden die Führung erraten. |
| `negative_routing` | Negative Routing-Tests | Gibt es noch aktive Phrasen, die auf die alte Karte zeigen? | Sätze wie `fuehrende Projektkarte: alte Karte`. | Alte Gewohnheitsrouten werden maschinell sichtbar. |
| `status_aging` | Status- und Review-Aging | Sind alte offene Punkte noch offen oder durch spätere Wahrheit geschlossen? | Review-Queue-Leichen und alte `active` Roadmaps. | Der Operator muss nicht alte Warteschlangen mental abgleichen. |
| `gate_inversion` | Gate-Inversion | Wird ein lokaler/verifizierter Stand irgendwo als Public-/Production-Go gelesen? | Grüne lokale Tests, die als externe Freigabe missverstanden werden. | Operator-Gates bleiben sichtbar, statt aus Testgrüns zu verschwinden. |
| `successor_predecessor` | Nachfolger-/Vorgänger-Spur | Ist klar, was historischer Ursprung und was aktuelle operative Fläche ist? | Materialbedarf/Elterngeld als aktive Wahrheit unter Wortcluster. | Projektwechsel müssen nicht aus Erinnerung rekonstruiert werden. |
| `operator_intent_extraction` | Operator-Intent-Extraktion | Welche wiederholte Operator-Sorge steckt hinter dem aktuellen Prompt? | Audits, die erst laufen, wenn Bjorn sie exakt benennt. | Bjorn muss die Systemklasse nicht jedes Mal selbst formulieren. |
| `workflow_not_mutation` | Automatic-by-Workflow | Kann der Check automatisch report-only laufen, ohne kanonisches Memory zu mutieren? | Entweder kein wiederholbarer Check oder riskante stille Autowrites. | Routinepruefungen laufen mit, aber echte Vault-Änderungen bleiben bewusst. |

## Findings

Keine Blocker oder High-Findings.

## Workflow-Regel

- Vor jedem Claim `Vault ist sauber` oder `Backbone ist aktuell` diesen Audit laufen lassen.
- Der Audit ist report-only: Er schreibt keine kanonischen Obsidian-Notizen.
- Automations dürfen Findings melden und nächste Aktionen vorschlagen, aber nicht automatisch Memory mutieren.

```bash
python3 scripts/ops/vault_semantic_audit.py --output-dir outputs/vault_semantic_audit
python3 scripts/ops/agent_os_readiness.py
```

## Geprüfte Dateien

- `00 DreamFactory Home.md`
- `01 Projects.md`
- `02 Plans and Status.md`
- `03 Features.md`
- `04 Agent Start Here.md`
- `Canonical/Canonical Index.md`
- `DreamFactory – Projektübersicht.md`
- `DreamFactory – Systemhandbuch.md`
- `Project - Utility Websites Portfolio.md`
- `Project - Utility Wortcluster.md`
- `Review Queue.md`
