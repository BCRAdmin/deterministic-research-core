# Pilot-v1 Release Cut

## 1. Release Name

Pilot-v1 Research Agent

## 2. Aktueller Funktionsumfang

- `source_ingestion_mode`
- SEC/IR/Price ingestion
- Reconciliation
- Metrics validation
- Evidence ledger
- Markdown auditor
- Decision permission layer
- Quality score
- `publish_report.md`
- Batch/dashboard
- Manual-review queue
- Outcome backtesting framework

## 3. Aktuell akzeptierter Betriebsmodus

- Interne Research-Drafts.
- Passed Reports sind nutzbar als interne Grundlage.
- Manual-review Reports dürfen nicht automatisch genutzt werden.
- Wichtige Echtgeld-Reports müssen extern/menschlich geprüft werden.
- Keine unbeaufsichtigte Veröffentlichung.

## 4. Gold-v1 Templates

- `GOOGL`
- `SNOW`

## 5. Near-Gold / Gute Interne Drafts

- `MSFT`
- `AAPL`
- `META`
- `NFLX`
- `DDOG`
- `CRM`
- `AVGO`

## 6. Bekannte Offene Punkte

- SNOW Rating-Wording kann noch inkonsistent sein.
- CRM FCF Evidence Mapping muss bei Gelegenheit geprüft werden.
- Valuation/Sensitivity ist noch ausbaufähig.
- Action Plans könnten konkreter sein.
- Outcome-Daten `5D`/`10D`/`20D`/`60D` müssen noch reifen.
- Nicht unbeaufsichtigt publish-ready.

## 7. Stop Rule

Ab jetzt keine neue Architektur und keine weiteren Fix-Sprints ohne neuen echten Fehler aus:

- `manual_review`
- Outcome backtest
- Menschlicher Review
- Produktionslauf

## 8. Nächster Erlaubter Schritt

Nur Betrieb:

- Fresh Batch laufen lassen.
- Dashboard prüfen.
- `manual_review` prüfen.
- Passed Reports stichprobenartig prüfen.
- Outcome nach `5D`/`10D`/`20D` auswerten.

## 9. Finaler Status

Pilot-v1 ist lauffähig und eingefroren.

Nicht perfekt.

Nicht final publish-ready.

Aber nutzbar als interner Research-Agent mit Review-Gates.
