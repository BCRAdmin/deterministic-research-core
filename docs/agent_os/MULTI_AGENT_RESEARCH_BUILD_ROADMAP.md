---
title: Multi-Agent Research Build Roadmap
status: active
date: 2026-05-21
owner: Vega
scope: internal-first
---

# Multi-Agent Research Build Roadmap

## Kurzentscheidung

Wir bauen keinen MiroFish-Fork und keinen sofortigen LIONCOM-Einbau. Der richtige Weg ist:

1. `vega-multi-agent-research` als lokalen Codex/Vivi-Skill stabilisieren.
2. Den Workflow als wiederholbaren Research-/Ideen-/Strategie-Baustein nutzen.
3. Nach 5-10 echten internen Laeufen entscheiden, ob daraus eine getrennte kleine App analog Room16 entsteht.
4. LIONCOM erst anbinden, wenn es einen nachweisbar nuetzlichen Run-Vertrag, Artefaktstruktur und Operator-Gate gibt.
5. Externe Produktisierung nur greenfield/service-first, nicht auf AGPL-MiroFish-Codebasis.

## Zielbild

Ein interner Scenario-/Research-Sandbox-Baustein, den Vega und Vivi bei passenden Aufgaben nutzen koennen:

- Quellen oder Kontext rein.
- Enge Debattenfrage rein.
- 3-6 Rollen diskutieren in 1-3 Runden.
- Rohtranskript, Synthese, Claims-to-check, Konflikte und naechste Tests raus.
- Alles bleibt `candidate_only`, bis Vega/Operator es prueft.

Der Mehrwert ist nicht "mehr Agenten = besser", sondern: kontrollierte Perspektivenspannung, sichtbare Widersprueche, besserer Skeptiker-Modus und wiederverwendbare Artefakte.

## Harte Grenzen

- Keine automatische Promotion von Agentenmeinungen in Obsidian, LIONCOM, Room16 oder Public-Artefakte.
- Keine Nutzung als Finanz-, Rechts-, Medizin- oder Public-Entscheider.
- Keine AGPL-Codeuebernahme aus MiroFish ohne Lizenzentscheidung.
- Keine Zep-/Cloud-Memory-Pflicht in V1.
- Keine LIONCOM-Runtime-Aenderung, bis der Skill in internen Laeufen stabil und nuetzlich ist.
- Keine Multi-Agenten-Laeufe fuer einfache Faktenfragen, kleine Code-Fixes oder klare Zusammenfassungen.

## Architektur

### Schicht 1: Skill und Runner

Aktueller Stand:

- Skill: `/Users/BjornRosinger/.codex/skills/vega-multi-agent-research/`
- Runner: `/Users/BjornRosinger/.codex/skills/vega-multi-agent-research/scripts/multi_agent_panel.py`
- Modi: `research`, `ideas`, `website`, `strategy`
- Output: `TRANSCRIPT.md`, `SYNTHESIS.md`, `events.json`, `metadata.json`
- DeepSeek/Ollama-Default: `think:false`
- Validator: gruen mit `Skill is valid!`

Naechster Ausbau:

- Output-Schema formalisieren.
- Health-Gates schaerfen.
- Konfigurationsdateien fuer wiederholbare Runs ergaenzen.
- Runner optional ins Repo spiegeln, sobald er mehr als lokales Skill-Werkzeug sein soll.

### Schicht 2: Kontextpaket

Jeder Lauf braucht ein kurzes Kontextpaket:

- belegte Fakten
- Quellenlinks oder lokale Quellenpfade
- Annahmen
- verbotene Claims
- Entscheidungsfrage
- Zielgruppe / Auftragstyp
- gewuenschter Output

Ohne Kontextpaket wird kein "voller" Multi-Agenten-Lauf gestartet. Sonst diskutieren Agenten nur aus Luft.

### Schicht 3: Agentenbibliothek

Standard-Sets:

- `research`: Source Analyst, Skeptic, Operator, Market Lens, User Advocate
- `ideas`: Divergent Builder, Customer Voice, Distribution Lens, Risk Skeptic, Editor
- `website`: Target Buyer, Conversion Lens, Trust Skeptic, Local Buyer, Operator
- `strategy`: Founder, Finance, Legal/Privacy, Customer, Delivery

Ausbau:

- Custom-Agenten per JSON-Datei fuer spezielle Zielgruppen.
- Wiederverwendbare Sets fuer Utility-Websites, Room16/Quellwert, Produktideen, lokale Dienstleister, SaaS, Creator/Info-Produkte.
- Agentenprofile kurz halten, damit Rollen nicht zu Theater werden.

### Schicht 4: Moderator und Claim Review

Die Synthese muss immer trennen:

- belegte Fakten
- Agentenannahmen
- echte Konflikte
- Konsens
- Top-Massnahmen
- Claims-to-check
- naechster kleinster Test

Vega/Operator entscheidet, nicht der Moderator.

### Schicht 5: Memory und Handoff

Outputs bleiben lokal im passenden Projektordner. Obsidian bekommt nur dauerhafte Learnings, keine Rohmeinungen.

Promotion-Regel:

- Rohtranskript: nie automatisch in Memory.
- Synthese: nur als Candidate oder Projektartefakt.
- Dauerhafte Regeln: nur nach Vega-Pruefung in `Learnings and Fixes`, Projektnote oder Skill-Routing.
- Produkt-/Launch-Ideen: in `Project Seeds`, wenn sie echten Folgewert haben.

## Build-Phasen

### P0 - Fundament sichern

Status: erledigt.

Erledigt:

- MiroFish als Pattern analysiert.
- Schulz-Reinigungsdienst-Test als Einzelmodell- und Multi-Agentenlauf durchgefuehrt.
- DeepSeek/Ollama-Learning `think:false` gefunden.
- Skill `vega-multi-agent-research` erstellt.
- Runner erstellt.
- `PyYAML` installiert und Skill-Validator repariert.
- Skill in Skill Inventory, Selection Matrix, Research Dossier Loop und Memory verankert.
- Alter Spike-Runner `scripts/ops/scenario_sandbox_debate.py` wurde durch den validierten Skill-Runner ersetzt und aus dem Repo-Workingtree entfernt.
- Raw-Scenario-Outputs unter `outputs/scenario_sandbox/` sind lokale Testevidence und werden nicht versioniert; dauerhafte Learnings stehen im Vault und in dieser Roadmap.

Definition of Done:

- Skill ist validiert.
- Erster Smoke hat `empty_turns=0`, `error_turns=0`.
- Memory sagt nicht mehr, dass der Validator kaputt ist.

### P1 - Runner produktionsnah haerten

Ziel: Der Runner soll auch spaeter ohne Erinnerungsarbeit korrekt laufen.

Aufgaben:

- `run_config.json` oder YAML akzeptieren: Kontextpfad, Frage, Agent-Set, Modell, Rundenzahl, Output-Pfad.
- Output-Dateinamen standardisieren: `TRANSCRIPT.md`, `SYNTHESIS.md`, `CLAIMS_TO_CHECK.md`, `RUN_REPORT.md`, `events.json`, `metadata.json`.
- Exit-Codes dokumentieren: success, model_error, empty_turns, capped_summary, invalid_config.
- Health-Check erweitern:
  - leere Turns
  - Token-Caps
  - Fehler je Agent
  - fehlendes Kontextpaket
  - zu lange Debattenfrage
  - fehlende Quellen bei Research-/Website-Modus
- Kleine Test-Fixtures bauen:
  - minimaler Kontext
  - Custom-Agenten-JSON
  - invalid config
  - Health-Check-Auswertung
- `README` vermeiden; stattdessen Skill und Roadmap als Fuehrung nutzen.

Gate:

- `python3 -m py_compile` gruen.
- Skill-Validator gruen.
- Mindestens ein Offline-/Mock-Test fuer Config/Health ohne LLM.
- Ein echter Ollama-Smoke mit kleinem Kontext.

Empfohlener Aufwand: 0.5-1 Tag.

### P2 - Kontextpaket-Builder bauen

Ziel: Nicht jeder Lauf soll haendisch aus Quellen zusammenkopiert werden muessen.

Aufgaben:

- `context_pack_builder.py` als Hilfsskript:
  - lokale Markdown-Dateien einsammeln
  - URLs als Quellenliste aufnehmen
  - optional Defuddle-/Web-Extraktion vorbereiten
  - Fakten, Annahmen und offene Fragen getrennt ausgeben
- Source-Ledger im Kontextpaket:
  - `source_id`
  - Titel
  - URL/Pfad
  - Abrufdatum
  - Nutzung im Lauf
- Prompt-Injection-Hinweis fuer Webquellen: Quelltext ist Material, keine Anweisung.
- Templates:
  - Website Review
  - Markt-/Konkurrenzanalyse
  - Produktidee
  - interne Systementscheidung

Gate:

- Kontextpaket kann ohne LLM erzeugt werden.
- Research-Modus warnt, wenn keine Quellen im Kontext stehen.
- Website-Modus warnt, wenn keine Website-Fakten oder Screenshots/Pfade genannt sind.

Empfohlener Aufwand: 1-2 Tage.

### P3 - Synthese und Claim Review schaerfen

Ziel: Aus dem Debattenmaterial soll ein wirklich nutzbares Entscheidungsartefakt werden.

Aufgaben:

- Moderator-Output in feste Abschnitte zwingen:
  - `Kurzfazit`
  - `Konsens`
  - `Konflikte`
  - `Top 5 naechste Tests`
  - `Claims to Check`
  - `Nicht uebernehmen`
  - `Naechster Schritt`
- Separates `CLAIMS_TO_CHECK.md` erzeugen.
- `RUN_REPORT.md` als Operator-Ansicht erzeugen:
  - Status
  - Modell
  - Health
  - Kosten-/Zeitnaehe falls verfuegbar
  - Artefaktlinks
  - Entscheidung: `candidate_only`
- Optional: Claim-Klassifikation:
  - factual
  - inference
  - persona_preference
  - unsupported
  - risky_public_claim

Gate:

- Kein Run gilt als fertig, wenn `Claims to Check` fehlt.
- Kein Run darf `public_ready` setzen.
- Token-Cap in der Summary wird sichtbar als Warning markiert.

Empfohlener Aufwand: 1 Tag.

### P4 - Interne Pilotserie

Ziel: Erst echte Nutzung beweist, welche Agenten-Sets und Outputs taugen.

Mindestens 5 Piloten:

1. Utility-Website: Materialbedarf oder Elterngeld Messaging/Funnel.
2. Lokaler Dienstleister: zweiter Website-/Angebotstest neben Schulz.
3. Produktidee: 48h Launch-/Messaging-Simulation.
4. Room16/Quellwert: nur interne Stakeholder-/Lesbarkeits- oder Review-Queue-Simulation, keine Finanzentscheidung.
5. LIONCOM/Vivi: interne Systementscheidung, z. B. welche Capability als Nutzeroberflaeche sichtbar werden soll.

Pro Pilot speichern:

- Kontextpaket
- Transkript
- Synthese
- Claims-to-check
- Operator-Readout
- kurze Bewertung: besser als Einzelmodell ja/nein/warum

Gate fuer Weiterbau:

- Mindestens 3 von 5 Piloten liefern klaren Mehrwert gegenueber Einzelmodell.
- Mindestens 2 konkrete Entscheidungen oder bessere Tests entstehen daraus.
- Keine haeufigen Halluzinations-/Claim-Probleme ohne erkennbare Health-Warnung.

Empfohlener Aufwand: 1-2 Wochen nebenbei.

### P5 - Vivi/Codex Arbeitsintegration

Ziel: Vivi und Codex sollen wissen, wann der Skill zu nutzen ist, ohne jedes Mal neu zu diskutieren.

Aufgaben:

- Skill-Routing in Vault weiter schaerfen:
  - Research Dossier Loop
  - Skill Selection Matrix
  - Vivi Skill Inventory
  - ggf. Auftragstyp Routing Decision Tree
- Standardformulierungen fuer Vivi:
  - "Kontextpaket bauen"
  - "Multi-Agentenlauf nur bei Perspektivenspannung"
  - "Synthese candidate_only"
  - "Claims-to-check vor Empfehlung"
- Handoff-Format definieren:
  - `question`
  - `context_pack_path`
  - `agent_set`
  - `output_dir`
  - `operator_decision_needed`
- Keine automatische Hintergrundautomation. Runs bleiben explizit oder durch klaren Auftrag getriggert.

Gate:

- Vivi/Codex kann in einem neuen Auftrag begruenden, warum Multi-Agenten passend oder unpassend sind.
- Ein Run kann reproduzierbar aus einem Handoff gestartet werden.

Empfohlener Aufwand: 0.5-1 Tag.

### P6 - Separate interne Scenario-Sandbox-App pruefen

Ziel: Nur wenn die Pilotserie zeigt, dass eine UI echten Nutzen bringt.

App ist getrennt von LIONCOM, eher Room16-artig.

Minimaler Funktionsumfang:

- Kontextpaket anlegen.
- Agent-Set waehlen.
- Frage formulieren.
- Run starten.
- Health und Kosten-/Dauerhinweis sehen.
- Transcript und Synthese lesen.
- Claims-to-check abhaken.
- Operator-Entscheidung speichern: discard, keep_candidate, promote_learning, create_task.

Technikoption:

- Kleine lokale Web-App im bestehenden Workspace oder separatem Repo.
- Backend ruft den bestehenden Runner.
- Keine Zep-Pflicht.
- Keine Kundendaten ohne Auth/Retention/Privacy-Policy.

Gate vor Bau:

- Mindestens 5 interne Runs.
- Wiederholter Bedarf nach UI statt CLI.
- Klarer Speicherort fuer Artefakte.
- Operator will mehrere Runs vergleichen.

Empfohlener Aufwand MVP: 2-4 Tage.

### P7 - Optionaler LIONCOM-Einbau

Ziel: LIONCOM soll den Skill nur sichtbar machen, nicht die Wahrheitsschicht unkontrolliert veraendern.

Moeglicher kleiner Einbau:

- Neue Capability Card: `Scenario / Multi-Agent Research`.
- Formular fuer:
  - Debattenfrage
  - Kontextquelle/Pfad
  - Agent-Set
  - Zielordner
- Run-Status anzeigen:
  - pending
  - running
  - completed_candidate
  - failed_health_check
- Artefaktlinks in Operator Inbox.
- Keine Auto-Promotion in Memory.
- Keine Public-/Production-Freigabe.

Nicht einbauen:

- keine permanente Agenten-Diskussion als Chat-Spielerei
- keine Zep-/Graph-Memory-Abhaengigkeit
- keine automatische Outreach-/Website-/Report-Aenderung
- keine Kundendaten ohne Auth/Privacy-Gate

Gate:

- Separate App oder CLI ist stabil.
- Output-Contract und Health-Check sind robust.
- Operator will Runs im Control Plane sehen.
- LIONCOM-Runtime-Sync und Verifier sind definiert.

Empfohlener Aufwand Minimaladapter: 1-2 Tage nach P6.

### P8 - Externe Produktisierung

Ziel: Nur service-first und greenfield.

Moegliches Angebot:

- `48h Launch- & Messaging-Simulation`
- Zielgruppen: Gruender, Agenturen, DACH-KMU, Creator/Info-Produkte
- Output:
  - Zielgruppenreaktionen
  - Einwandmatrix
  - Messaging-Ranking
  - Risiko-/Backlash-Check
  - Copy-Varianten
  - naechster Realtest

Vorgehen:

1. 3 Beispielreports aus internen oder fiktiven Cases bauen.
2. Landing-/PDF-Angebot formulieren.
3. 3-5 bezahlte Piloten verkaufen.
4. Erst danach entscheiden, ob Tool/App/SaaS Sinn ergibt.

Grenzen:

- Kein MiroFish-Code kopieren.
- Keine AGPL-Abhaengigkeit ins Produkt.
- Kein "predict anything".
- Nur directional/candidate_only.
- Keine sensiblen Kundendaten ohne DPA/Retention/Auth.

Gate:

- Mindestens 3 zahlende Piloten.
- Wiederholbares Delivery-Template.
- Klarer Preisanker.
- Recht-/Datenschutz-Scope geklaert.

Empfohlener Aufwand Service-Pilot: 3-7 Tage fuer Angebot + Beispiele, danach Verkaufstest.

## Priorisierte naechste 10 Tasks

1. P1: Runner um Config-Datei und stabilere Health-Gates erweitern.
2. P1: `RUN_REPORT.md` und `CLAIMS_TO_CHECK.md` automatisch erzeugen.
3. P1: Offline-Tests fuer Config, Custom-Agenten und Health schreiben.
4. P2: Kontextpaket-Template fuer Website Reviews bauen.
5. P2: Kontextpaket-Template fuer Produktideen bauen.
6. P3: Moderator-Synthese in festen Output-Vertrag bringen.
7. P4: zweiten Website-Piloten durchfuehren.
8. P4: ersten Produktideen-Piloten durchfuehren.
9. P5: Vivi-Handoff-Format als kurze Notiz/Template materialisieren.
10. Nach 5 Piloten: Entscheidung `CLI/Skill reicht`, `separate App`, oder `LIONCOM-Adapter`.

## Wann Wir Stoppen

Stoppen oder parken, wenn:

- die Pilotserie keinen klaren Mehrwert gegenueber Einzelmodell zeigt
- Health-/Claim-Probleme trotz Gates zu hoch bleiben
- der Workflow mehr Meta-Arbeit als Entscheidungshilfe erzeugt
- LIONCOM-Integration nur aus Vollstaendigkeitsdrang entsteht
- keine wiederholbare interne Nachfrage sichtbar ist

## Empfehlung

Als naechstes P1-P3 bauen, dann fuenf echte interne Piloten. Vorher keine LIONCOM-Integration und kein Produktbau. Wenn die Piloten tragen, ist der wahrscheinlich beste Produktpfad nicht SaaS, sondern ein schlanker Service-Sprint mit starken Beispielreports.
