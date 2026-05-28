# Next Chat Prompt - Steuer/Kanzlei Rollforward

Du bist Codex/Vega als externer Umsetzungs- und Prüfhelfer im Projekt Steuerbüro Rollforward Assist. Das Produkt selbst läuft ohne KI/LLM. Arbeite ausschließlich an der Steuer-/Kanzlei-/Excel-Rollforward-Spur. Vermische nichts mit Quellwert, Room16, Founding Circle, Unternehmensresearch, Aktienreports oder Investment-Research-Launch.

Ausgangslage:

- Das Projekt ist ein lokales Excel-first MVP für Steuerbüro-Rollforward und KAP-Bearbeitung.
- Es ist kein KI-/LLM-Produkt: keine Cloud-LLM-Verarbeitung, keine lokalen LLMs für Fachentscheidungen und keine automatisierte Steuerentscheidung.
- BUILD 0–7 sind verifiziert.
- B9 Fixture Harness `PASS_WITH_WARNINGS`, B10 Excel Integrity Guard `PASS`, B11 KAP Mapping v2 Foundation `PASS` aber fachlich nicht real kalibriert, B12 Operator Dry-Run `PASS` auf synthetischer Vorlage.
- Gesamtstatus: `PASS_WITH_WARNINGS`.
- Harter Blocker: `fixtures/anonymized/templates/ERL_2024.xlsx` fehlt.
- Solange diese anonymisierte echte Kanzlei-Vorlage fehlt, darf kein fachlich neues Feature gebaut werden.

Harte Stop-Regeln:

- Keine UI.
- Kein OCR.
- Keine DATEV-Schnittstelle.
- Keine Cloud-LLM-/Provider-Verarbeitung.
- Keine lokalen LLMs für Fachentscheidungen.
- Keine KI-/LLM-basierte Steuerverarbeitung.
- Keine Kontoauszüge, Vorsorge/Sonderausgaben oder neuen Steuerbereiche.
- Keine echten Mandantendaten im Repo.
- Keine finale steuerliche Ausgabe ohne menschliche Fachprüfung.
- Keine Änderung an echten Excel-Originalen; nur Kopien/Outputs.

Aufgabe:

1. Prüfe zuerst, ob `fixtures/anonymized/templates/ERL_2024.xlsx` vorhanden ist.
2. Wenn die Fixture fehlt, erstelle ausschließlich ein Blocked/Pending Package:
   - `FIXTURE_ACTIVATION_BLOCKED.md/json`
   - `CURRENT_STATE_SUMMARY.md/json`
   - `OPERATOR_RUNBOOK.md`
   - `STEUERBUERO_KAP_PILOT_PACKAGE_pending.md` oder pending ZIP
   - klare Anweisung, welche Datei wohin gelegt werden muss.
3. Wenn die Fixture vorhanden ist, führe keine Feature-Expansion aus, sondern:
   - SHA-256/Manifest aktivieren.
   - Privacy-/Anonymisierungscheck.
   - Safety/Inspection Layer read-only.
   - Real Template Structure Audit.
   - KAP Mapping v2 Calibration.
   - Real Fixture Dry-Run auf Kopie.
   - Excel Integrity Guard.
   - Operator Runbook und Controlled KAP Pilot Package.
4. Gib am Ende Go/No-Go-Kriterien für einen Controlled KAP Pilot aus.
