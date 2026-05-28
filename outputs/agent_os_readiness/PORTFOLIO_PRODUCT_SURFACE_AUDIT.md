# Portfolio-Produktoberflächen-Audit

Dieser Bericht prüft die aktiven Projektkarten einzeln gegen die Frage: Gibt es eine sichtbare Lieferoberfläche mit Owner-Lane, Output, Verifier, Gate und nächster sicherer Aktion?

Gültig: `true`
Vault: `/Users/BjornRosinger/Documents/Obsidian/Test Vaul Privat/Human Overview`
Projektkarten: `5`
Findings: `0`

## Matrix

| Projekt | Status | Audit | Lanes | Sichtbare Oberflächen | Gates | Nächste sichere Aktion |
| --- | --- | --- | --- | --- | --- | --- |
| LIONCOM Dashboard | `active` | `verified_local_surface` | `orchestrator, assistant, docs` | Operator-Control-Plane, Portfolio-Control-Tower, Vivi/Vega-Claim- und Gate-Sicht | `Gate, Verifier, Operator-Go` | Lieferoberfläche als Reentry-Karte halten: aktive Lane, Output-Pfad, Verifier, blockiertes Gate und nächste Aktion. |
| Membership Finanzplattform | `active` | `verified_local_surface` | `research, docs, assistant` | Proof-first Webseite, Waitlist-/Founder-Funnel, Support-/Activation-Readiness | `Operator-Go, Provider, Checkout, Mail` | Nur Research-, Readiness- und Preview-Lieferobjekte öffnen, bis Provider, Geld, Mail und echte externe Sends explizit frei sind. |
| Utility Wortcluster | `parked_no_current_intent` | `verified_local_surface` | `research, data, docs` | Wortquelle, Regelset, Solver-MVP | `parked_no_current_intent, Datenquellen-Hold, Methodik` | Keine Solverarbeit starten; nur bei ausdruecklicher Reaktivierung Wortquelle, Regelset und Datenschema neu entscheiden. |
| Utility Websites Portfolio | `active` | `verified_local_surface` | `research, data, docs` | Materialbedarf-Rechner, Mein Elterngeldrechner, Microtool Starter Kit | `GSC, Messvertrag, Trust` | Aktive Website-Lanes getrennt vom wartenden Wortcluster führen und jede Folgemassnahme an Mess-, Trust- oder Opportunity-Gates binden. |
| Quellwert | `frozen_shelf_asset_operator_reopen_required` | `verified_local_surface` | `research, data, docs` | Research-/Archiv-/Methodik-Webseite, Room16-Promotion-Queue, Public-Preview-Gates | `Promotion, public_ready, Operator-Go, Non-Advice` | Keine aktive Quellwert-Produktarbeit ohne Operator-Reopen; bestehende Surface, Gates und Audit-Bausteine als Shelf-Asset erhalten. |

## Findings

Keine Blocker oder High-Findings.

## Projekt-Details

### LIONCOM Dashboard

- Projekt-ID: `lioncom_dashboard`
- Projektkarte: `/Users/BjornRosinger/Documents/Obsidian/Test Vaul Privat/Human Overview/Project - LIONCOM Dashboard.md`
- Audit-Status: `verified_local_surface`
- Owner-Lanes: `orchestrator, assistant, docs`
- Sichtbare Oberflächen: Operator-Control-Plane, Portfolio-Control-Tower, Vivi/Vega-Claim- und Gate-Sicht
- Blockierte Gates: `Gate, Verifier, Operator-Go`
- Nächste sichere Aktion: Lieferoberfläche als Reentry-Karte halten: aktive Lane, Output-Pfad, Verifier, blockiertes Gate und nächste Aktion.

### Membership Finanzplattform

- Projekt-ID: `membership_finanzplattform`
- Projektkarte: `/Users/BjornRosinger/Documents/Obsidian/Test Vaul Privat/Human Overview/Project - Membership Finanzplattform.md`
- Audit-Status: `verified_local_surface`
- Owner-Lanes: `research, docs, assistant`
- Sichtbare Oberflächen: Proof-first Webseite, Waitlist-/Founder-Funnel, Support-/Activation-Readiness
- Blockierte Gates: `Operator-Go, Provider, Checkout, Mail`
- Nächste sichere Aktion: Nur Research-, Readiness- und Preview-Lieferobjekte öffnen, bis Provider, Geld, Mail und echte externe Sends explizit frei sind.

### Utility Wortcluster

- Projekt-ID: `utility_wortcluster`
- Projektkarte: `/Users/BjornRosinger/Documents/Obsidian/Test Vaul Privat/Human Overview/Project - Utility Wortcluster.md`
- Audit-Status: `verified_local_surface`
- Owner-Lanes: `research, data, docs`
- Sichtbare Oberflächen: Wortquelle, Regelset, Solver-MVP
- Blockierte Gates: `parked_no_current_intent, Datenquellen-Hold, Methodik`
- Nächste sichere Aktion: Keine Solverarbeit starten; nur bei ausdruecklicher Reaktivierung Wortquelle, Regelset und Datenschema neu entscheiden.

### Utility Websites Portfolio

- Projekt-ID: `utility_websites_portfolio`
- Projektkarte: `/Users/BjornRosinger/Documents/Obsidian/Test Vaul Privat/Human Overview/Project - Utility Websites Portfolio.md`
- Audit-Status: `verified_local_surface`
- Owner-Lanes: `research, data, docs`
- Sichtbare Oberflächen: Materialbedarf-Rechner, Mein Elterngeldrechner, Microtool Starter Kit
- Blockierte Gates: `GSC, Messvertrag, Trust`
- Nächste sichere Aktion: Aktive Website-Lanes getrennt vom wartenden Wortcluster führen und jede Folgemassnahme an Mess-, Trust- oder Opportunity-Gates binden.

### Quellwert

- Projekt-ID: `quellwert`
- Projektkarte: `/Users/BjornRosinger/Documents/Obsidian/Test Vaul Privat/Human Overview/Project - Quellwert.md`
- Audit-Status: `verified_local_surface`
- Owner-Lanes: `research, data, docs`
- Sichtbare Oberflächen: Research-/Archiv-/Methodik-Webseite, Room16-Promotion-Queue, Public-Preview-Gates
- Blockierte Gates: `Promotion, public_ready, Operator-Go, Non-Advice`
- Nächste sichere Aktion: Keine aktive Quellwert-Produktarbeit ohne Operator-Reopen; bestehende Surface, Gates und Audit-Bausteine als Shelf-Asset erhalten.
