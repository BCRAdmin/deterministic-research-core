# RGTI – Quellen- und Encoding-QA

Diese Notiz unterstützt den Goldstandard-Report `internal_best_report.md` im echten Room-16-Run-Verzeichnis. Sie dokumentiert Quellen, Evidenzgrenzen, Statuslogik und Encoding-QA.

## Genutzte lokale Artefakte

| Artefakt | Pfad | Rolle |
| --- | --- | --- |
| Quality Report JSON | `/Users/BjornRosinger/Documents/New project/company-dossier-lab/reports/room16/runs/20260515-223522-rgti-e63b8cca/RGTI/quality/2026-05-15-room16-quality-report.json` | Status, Publishability, Archetype, Issues, Quality Caps |
| Evidence Report | `/Users/BjornRosinger/Documents/New project/company-dossier-lab/reports/room16/runs/20260515-223522-rgti-e63b8cca/RGTI/generated/evidence_report.md` | Evidence-Ledger und Guard-Zusammenfassung |
| Raw Room-16 Output | `/Users/BjornRosinger/Documents/New project/company-dossier-lab/reports/room16/runs/20260515-223522-rgti-e63b8cca/RGTI/generated/raw_room16_report.md` | Unveränderter Rohbericht für Regression-Kontinuität |
| Complete Dossier | `/Users/BjornRosinger/Documents/New project/company-dossier-lab/reports/room16/runs/20260515-223522-rgti-e63b8cca/RGTI/complete/2026-05-15-room16-RGTI-complete-dossier.md` | Lesbarer Aktienreport, nicht Public-freigegeben |
| Batch Copy | `/Users/BjornRosinger/Documents/New project 2/outputs/batches/rgti_deeptech_profile_check/RGTI_internal_best_report.md` | Synchronisierte Kopie für Regression-/Batch-Auswertung |

## Unveränderte Statuswerte

- `review_status = manual_review`
- `publishable = false`
- `internal_rating = Preliminary Underweight`
- `external_display_rating = Manual Review / Preliminary Underweight`
- `public_rating = null`
- `company_archetype = SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL`
- `archetype_confidence = 0.833`
- `quality_score = 70`

## Evidenzgrenzen

- Market Cap ist als Vendor/Media-Level-Datenstand um den 13.–14. Mai 2026 zu lesen, nicht als aktuell bestätigte Live-Marktkapitalisierung.
- Cash + Investments ist als Bilanz-/Regression-Stand per 31.12.2025 zu lesen; Q1-2026-Cash/Investments sind im lokalen Case nicht SEC/IR-primärbestätigt.
- FY2025 Revenue, Q1 2026 Revenue, Free Cash Flow, SBC und Operating-Loss-Angaben sind im Report bewusst als Vendor/Media/Regression-Level markiert.
- C-DAC Indien und AFRL / U.S. Air Force werden als Vendor-/Media-Level-Auftragswerte behandelt, bis Originalquellen vorliegen.
- GAAP-Net-Income-Verbesserungen dürfen nicht als operative Wende interpretiert werden, solange Warrant-, Derivat- oder Fair-Value-Effekte nicht getrennt sind.

## Encoding-QA

Pflicht-Testzeichen für Markdown und PDF:

`ä ö ü Ä Ö Ü ß € – — „“`

QA-Regel: Der PDF-Export gilt nur als erfolgreich, wenn diese Zeichen im Markdown UTF-8-kodiert vorliegen und nach dem PDF-Export aus dem PDF-Text korrekt extrahierbar sind.

## Public Boundary

Diese Fassung ist intern. `public_rating = null`. Der Report darf nur als Manual-Review-Note gelesen werden und ist kein sauber freigegebener Public Report.
