# PILOT_V1_OVERVIEW

## Was ist Quellwert Research Agent?

Quellwert Research Agent ist ein deterministischer Research- und Review-Stack fuer interne Aktienanalysen. Python berechnet Kennzahlen, reconciliert Quellen, validiert Claims und erzwingt Review-Gates; der Publish-Layer formuliert nur auf Basis dieser validierten Pakete.

## Was kann das System?

- SEC-, IR- und Preisquellen in Data-/Metrics-/Evidence-Pakete ueberfuehren.
- Ratings ueber DecisionPacket und Quality Gates begrenzen.
- `final_report.md` und `publish_report.md` mit Evidence Appendix erzeugen.
- Batch-Runs, Dashboard, Manual-Review-Queue und Review-Bundles erzeugen.

## Was kann es nicht?

- Keine unbeaufsichtigte externe Publikation.
- Keine Guard-Bypasses fuer fehlende FCF-, KPI- oder Reconciliation-Supports.
- Keine finale Wahrheit bei True-Anomalien ohne menschliche Pruefung.

## Pipeline-Uebersicht

1. Source ingestion / packet build
2. Canonical reconciliation
3. Validation + audit
4. Decision layer + quality score
5. Publish/final report generation
6. Batch dashboard + manual-review triage

## Kontrollschichten

- ValidationReport
- Markdown Auditor
- Evidence Ledger
- Reconciliation warnings
- DecisionPacket / rating permission
- Quality score / publishability gate

## Beispiel-Output

Siehe `EXAMPLE_REPORTS/` und `DASHBOARD_EXAMPLE/` im Release-Paket.

## Empfohlener Betriebsmodus

Interner Pilotbetrieb mit menschlicher Review-Schicht. Passed Reports sind review-faehige interne Drafts; Manual Review ist ein echter Stop, kein Soft Warning.

## Grenzen

Pilot-v1 ist absichtlich streng. Die Staerke liegt in der Gate-Disziplin und Erklaerbarkeit, nicht in maximaler Pass-Rate.
