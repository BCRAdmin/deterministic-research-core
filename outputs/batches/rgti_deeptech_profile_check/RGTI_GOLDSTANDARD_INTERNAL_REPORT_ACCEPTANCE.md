# RGTI Goldstandard Internal Report – Abnahmebericht

## Ergebnis

Der RGTI Internal Best Report wurde zur Goldstandard-Lesefassung für interne Manual-Review-Reports der Klasse `SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL` überarbeitet.

RGTI bleibt ausdrücklich:

- `review_status = manual_review`
- `publishable = false`
- `internal_rating = Preliminary Underweight`
- `external_display_rating = Manual Review / Preliminary Underweight`
- `public_rating = null`
- `company_archetype = SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL`

## Was wurde verbessert?

- Die Lesefassung wurde stärker auf interne Research-Nutzung ausgerichtet.
- Stichtage und Datenstatus wurden präzisiert: Market Cap als Vendor/Media-Level-Datenstand um den 13.–14. Mai 2026; Cash + Investments als 31.12.2025-/Regression-Stand.
- Q1-2026-Cash/Investments und Operating Loss Q1 2026 werden nicht als primär bestätigt verkauft.
- Contract / Order Materiality wurde konkret mit C-DAC Indien und AFRL / U.S. Air Force verarbeitet.
- Financial Reality trennt Umsatzsprung, Operating Loss, Free Cash Flow, Cash Runway, SBC und Accounting-Effekte sauber.
- Valuation Disconnect wurde als zentrale These geschärft: Milliardenbewertung gegen Mini-Umsatz.
- Encoding-QA wurde für Markdown und PDF fest verankert.

## Warum bleibt RGTI manual_review?

RGTI erfüllt mehrere Deep-Tech-Frühphasen-Trigger:

- Revenue deutlich unter institutioneller Skalierung.
- Market Cap / Revenue extrem hoch.
- Operating Loss und Free Cash Flow negativ.
- SBC relativ zu Revenue extrem hoch.
- harte Finanzkennzahlen im aktuellen Case Vendor-/Media-Level.
- keine vollständige SEC/IR-Evidence im Regression-Stand.
- Warrant-/Fair-Value-Effekte können GAAP Net Income verzerren.
- Auftragswerte sind relevant, aber nicht ausreichend materialisiert und nicht als skalierter Umsatzmotor belegt.

Damit darf RGTI nicht als clean publishable durchgehen.

## Warum ist der Report internal best, aber nicht public?

Der Report ist intern vollständig, weil er:

- eine klare interne Bewertung liefert,
- Datenlücken sichtbar macht,
- die stärksten Argumente und Risiken einordnet,
- Follow-up-Schritte definiert,
- keine Public-Freigabe vortäuscht.

Er ist nicht public, weil zentrale harte Daten noch nicht primär bestätigt sind und mehrere Quality Gates weiterhin blockieren.

## Abgeleitete generische Klasse

Aus RGTI wurde das Template `SPECULATIVE_DEEP_TECH_INTERNAL_REPORT_TEMPLATE.md` abgeleitet.

Die Klasse deckt künftig Fälle ab wie:

- Quantum Computing
- frühe Deep-Tech-Hardware
- Space
- eVTOL
- Robotics
- Defense-Tech-Microcaps
- pre-commercial AI/Compute/Hardware Story Stocks
- narrative-driven, pre-profit, high-valuation Unternehmen

## Offene Punkte

- SEC/IR-Filings und Earnings-Unterlagen für den aktuellen Zeitraum ziehen.
- Revenue, Operating Loss, Free Cash Flow, Cash, Debt, SBC und Aktienzahl aus Primärquellen neu aufbauen.
- C-DAC Indien und AFRL / U.S. Air Force mit Originalquelle, Vertragswert, Umsatzzeitpunkt, Wiederholbarkeit und Kundentyp verifizieren.
- Warrant-, Derivat- und Fair-Value-Effekte vom operativen Ergebnis trennen.
- Cash Runway mit realistischem Burn und Verwässerungsszenario aktualisieren.

## Wann darf RGTI neu bewertet werden?

RGTI darf neu bewertet werden, wenn mindestens diese Punkte vorliegen:

1. SEC/IR-bestätigte aktuelle Finanzkennzahlen.
2. wiederholbarer Revenue über mehrere Quartale.
3. materialisierte Contract-Werte mit Timing, Kundentyp und Umsatzrealisierung.
4. sinkender Operating Loss ohne Accounting-Sondereffekte.
5. sinkender Cashburn.
6. kontrollierte SBC und Verwässerung.

## Bewertungsschema

| Kategorie | Ergebnis |
| --- | --- |
| Statuslogik | bestanden: manual_review / publishable=false bleibt erhalten |
| Lesbarkeit | bestanden: interne Research-Lesefassung, kein Debug-Output |
| RGTI-spezifische Analyse | bestanden: Deep-Tech-Option statt normale Investmentstory |
| Contract Materiality | bestanden: C-DAC und AFRL konkret, aber Vendor/Media-Level markiert |
| Financial Reality | bestanden: Operating Loss, Free Cash Flow, Cash Runway, SBC und Accounting getrennt |
| Valuation Disconnect | bestanden: Milliardenbewertung vs. Mini-Umsatz klar herausgearbeitet |
| Encoding/PDF-Reife | bestanden, sofern Export-QA grün bleibt |
| App-Integration | bestanden, sofern Dashboard-Artefakte weiter auf internal_best_report zeigen |

## Verifikation

| Check | Ergebnis |
| --- | --- |
| Room16 pytest | bestanden: 125 passed, 41 subtests passed |
| Room16 compileall | bestanden |
| Research-Core Deep-Tech pytest | bestanden: 7 passed |
| Research-Core compileall | bestanden |
| Room16 verify | bestanden |
| Room16 report-machine verify | bestanden |
| Markdown/PDF Encoding-QA | bestanden: ä ö ü Ä Ö Ü ß € – — „“ |
| Public Library | RGTI bleibt hidden; kein Public Markdown, `public_rating = null` |
| Dashboard-Artefakte | raw_report, internal_best_report, internal_best_report_pdf, quality_report, evidence_report, dashboard_status vorhanden |

## Erzeugte Dateien

- `/Users/BjornRosinger/Documents/New project/company-dossier-lab/reports/room16/runs/20260515-223522-rgti-e63b8cca/RGTI/generated/internal_best_report.md`
- `/Users/BjornRosinger/Documents/New project/company-dossier-lab/reports/room16/runs/20260515-223522-rgti-e63b8cca/RGTI/generated/RGTI_manual_review_reading_version.pdf`
- `/Users/BjornRosinger/Documents/New project/company-dossier-lab/reports/room16/runs/20260515-223522-rgti-e63b8cca/RGTI/generated/internal_best_report_sources.md`
- `/Users/BjornRosinger/Documents/New project/company-dossier-lab/reports/room16/templates/SPECULATIVE_DEEP_TECH_INTERNAL_REPORT_TEMPLATE.md`
- `/Users/BjornRosinger/Documents/New project/company-dossier-lab/reports/room16/runs/20260515-223522-rgti-e63b8cca/RGTI/generated/RGTI_GOLDSTANDARD_INTERNAL_REPORT_ACCEPTANCE.md`
