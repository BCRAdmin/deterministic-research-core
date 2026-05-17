# TECHNICAL_ARCHITECTURE

## DataPacket

Preis-, Event- und Grundkontext fuer den Reportlauf.

## MetricsPacket

Technicals, Fundamentals und Valuation aus deterministischen Berechnungen.

## ValidationReport

Fruehe Daten- und Logikpruefung vor dem Report-Audit.

## EvidenceLedger

Claim- und Metric-Evidence mit Source-Typ, Confidence und IDs.

## CanonicalFinancials

Reconciliertes Zielmodell ueber SEC-, IR- und Derived-Facts.

## Reconciliation

Source-Konflikte, Frame-Varianten und Current-Period-Facts werden vor der Publikation sichtbar gemacht.

## Markdown Auditor

Lintet Finaltext gegen MetricsPacket, Evidence und Decision-Grenzen.

## Decision Layer

Erzeugt RatingPermission, Allowed/Blocked Ratings und operativen Rating-Korridor.

## Quality Score

Verdichtet Content-, Evidence-, Logic- und Writing-Qualitaet zu einem Publish-Gate.

## Auto-Repair

Kontrollierte Reparaturschleife fuer fehlerhafte Drafts, ohne Guard-Lockerung.

## Batch/Dashboard

Mehrere Ticker laufen isoliert; Dashboard, Manifest, Manual-Review-Triage und Review-Bundles werden batchweise erzeugt.

## Outcome Backtesting

ReportManifests werden spaeter gegen Forward-Return-Fenster bewertet.

## Calibration Shadow Mode

Kalibrierung bleibt von Live-Ratings getrennt, bis genug Outcome-Zeitfenster reif sind.

## publish_report.md vs final_report.md

`final_report.md` bleibt die interne, claim-nahe Vollspur. `publish_report.md` ist die externere, lesbarere Surface mit Appendix statt Claim-IDs im Haupttext.
