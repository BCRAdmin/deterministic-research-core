# Room16 / Quellwert Roadmap Status

- Stand: `2026-05-27`
- Projekt: `Room16 / Quellwert`
- Status-Wahrheit: `local_verified_operator_gated_not_external_ready`
- Kurzfazit: Der interne Room16-Build ist sehr nah am Abschluss. Die öffentliche Quellwert-Preview ist lokal verifiziert und visuell grün. Externe Veröffentlichung, Payment, Checkout und paid investment-recommendation-like Output bleiben bewusst operator- und compliance-gated.

## Executive Snapshot

Room16 steht nicht mehr in einer groben Build-Phase, sondern in der Abschluss- und Gate-Phase.

- Core / Evidence Engine: `near_final_internal`
- App / Operator Workbench: `near_final_internal`
- German Output / Report Machine: `verified_local`
- Review / Publish Pipeline: `working_as_gated`
- Quellwert Public Preview: `verified_local_operator_gated`
- External Launch: `blocked_until_operator_go`
- Payment / Checkout: `blocked_until_separate_go`
- Compliance-sensitive paid recommendations: `blocked_until_compliance_review`

Interpretation: "Kurz vor Ende" stimmt für den lokalen Build. "100% Perfektion" heißt jetzt nicht, dass alles live geschaltet wird, sondern dass keine öffentliche, bezahlte oder empfehlungsähnliche Oberfläche versehentlich an den Gates vorbei öffnet.

## Status Matrix

| Bereich | Status | Evidenz | Restarbeit |
|---|---|---|---|
| Room16 Core Truth Model | `green` | Python Core Focused Tests: `36 passed` | Keine Architekturarbeit offen; nur Regression bei neuen Regeln |
| Identity / Evidence / Claim Validation | `green` | Focused pytest suite pass | Bei neuen Quellen weiter source-first prüfen |
| QualityDecision Single Source | `green` | Room16 focused tests pass | Keine zweite Quality-Wahrheit einführen |
| Room16 App Verify | `green` | `npm run verify` pass | Recoverable SBX.MU-Job beobachten, nicht als Launch-Blocker behandeln |
| German Output Quality | `green` | `npm run verify:german-output-quality` pass | Keine ASCII-Umlaut-Regressionen zulassen |
| Review Gate | `warn_expected` | 14 Reports, 3 Manual Review, 11 Rejected, 0 Public Ready | Drei Manual-Review-Fälle triagieren |
| Manual Review Packets | `warn_expected` | 3 Packets, 0 missing files | Review-Entscheidung je Packet: release / repair / reject |
| Publish Readiness | `warn_expected` | Promotion readiness blocked, operator gate required | Nicht automatisch publishen |
| Public Gate | `green` | `npm run verify:public-gate` pass | Gate nur mit Operator-Go öffnen |
| Quellwert Catalog Contract | `green` | `npm run verify:quellwert-public-catalog-contract` pass | GOOGL/SNOW/MSFT nur als operator-gated Beispiele |
| Quellwert Membership Preview | `green` | `LIONCOM_BASE_URL=http://127.0.0.1:4107 npm run verify:quellwert-membership-preview` pass | Legal-/Domain-/Robots-Entscheidung offen |
| Quellwert Visual Polish | `green` | `npm run verify:quellwert-visual-polish` pass | Kein aktueller Layout-Blocker |
| LIONCOM Local Preview | `green` | `http://127.0.0.1:4107/membership` HTTP 200, In-App-Browser overflow `0` | Bei jedem Build Standalone-Assets mitsyncen |
| Outcome Tracking 1D/5D | `computed_monitoring` | 37 rows, 0 pending; 5D false-pass candidate `AVGO` | 10D-Fenster am `2026-06-01` abwarten |

## Was Heute Zusätzlich Gefixt Wurde

1. LIONCOM-Startpfad stabilisiert:
   - `package.json` startet jetzt mit `.next/standalone/server.js`.
   - Hintergrund: Der alte `server.cjs`-Startpfad crashte nach frischem Standalone-Build.

2. Next-Standalone-Assets abgesichert:
   - Neues Build-Poststep-Skript `scripts/prepare_next_standalone_assets.mjs`.
   - Kopiert `public` und `.next/static` nach `.next/standalone`.
   - Verhindert den Zustand "Server läuft, Quellwert-Assets 404".

3. Quellwert Landing-Navigation gehärtet:
   - Landing-Primärnav ist jetzt `Analysen | Methodik | Archiv | Lesen`.
   - Verifier bleibt über Footer und Verifier-Seite erreichbar.

4. Quellwert Footer-Overflow behoben:
   - Footer-Nav bricht kontrolliert um und bleibt bei 1120px innerhalb des Viewports.

## Was Wirklich Noch Offen Ist

### P0 - Operator-Go Vor Externer Sichtbarkeit

- Externe URL / Domain festlegen.
- Impressum final prüfen.
- Datenschutzhinweis final prüfen.
- Kontaktweg final festlegen.
- Robots-/Indexing-Entscheidung treffen.
- Sample-Seiten für private Preview auswählen.
- Founding-Circle-Copy final kürzen und freigeben.
- GOOGL-Quellenreview finalisieren oder GOOGL weiterhin nur als gated Pilot zeigen.

Exit-Kriterium: Quellwert darf nur als private/public preview live, wenn diese Punkte explizit signiert sind. Kein stilles Öffnen.

### P1 - Room16 Manual Review Closure

- Drei Manual-Review-Packets einzeln prüfen.
- Pro Packet Entscheidung dokumentieren: `release_candidate`, `repair_needed` oder `reject_keep_hidden`.
- Bei Repair: konkrete Source-/FCF-/Identity-Lücke schließen.
- Danach Review-Gate erneut laufen lassen.

Exit-Kriterium: Keine Manual-Review-Position wird automatisch public oder member-ready.

### P1 - 10D Outcome Window

- Am `2026-06-01` 10D Outcome berechnen.
- `AVGO` False-Pass-Kandidat prüfen.
- `NOW`, `RKLB`, `ZS` kuratierte False-Block-Kandidaten prüfen.
- `MDB` positiven Monitor weiterbeobachten.
- Keine Guard-, Rating-, Calibration- oder Report-Änderung nur aus 1D/5D ableiten.

Exit-Kriterium: 10D bestätigt oder relativiert die 5D-Signale; erst dann werden Regeln ernsthaft bewertet.

### P1 - Private Soft Launch

- Lokale Preview auf Zielumgebung bringen.
- Vollständige Verifier-Matrix gegen Ziel-URL laufen lassen.
- Nur manuelle Waitlist-/Kontaktlogik, kein Checkout.
- Erste private Lesergruppe einladen.

Exit-Kriterium: Echte Nutzer können lesen und Interesse melden, ohne Payment, ohne Empfehlungssprache, ohne Auto-Publishing.

### P2 - Revenue Test Ohne Compliance-Überschreitung

- Founding Circle als Interessens-/Concierge-Angebot testen.
- Optional 1-3 Custom-Dossier-Gespräche anbieten.
- Zahlungsannahme erst nach separatem Operator-Go.
- Paid Output bleibt research context, nicht persönliche Anlageberatung.

Exit-Kriterium: Zahlungsbereitschaft ist sichtbar, aber keine compliance-sensitive Leistung wird automatisch verkauft.

### P2 - Release Hygiene

- Änderungen commit-fähig zusammenfassen.
- Dirty Worktrees trennen: bestehende fremde Outputs nicht vermischen.
- Finales Audit-Bundle nur nach Operator-Go aktualisieren.
- Deploy-/Push-/Payment-/Indexing-Gates separat halten.

Exit-Kriterium: Ein Reviewer kann Build, Gates, Restblocker und Launch-Grenzen ohne Chat-Kontext nachvollziehen.

## Perfektionsdefinition Für Den Abschluss

100% perfekt heißt für diesen Build:

- Alle lokalen Core-, App-, Preview- und Visual-Verifier sind grün.
- Erwartete WARNs sind echte Gates, keine Bugs.
- Public/member readiness bleibt `0`, solange keine menschliche Freigabe existiert.
- Manual-Review-Fälle bleiben versteckt.
- Quellwert öffnet keine Payment-, Checkout- oder Trading-Sprache.
- LIONCOM-Live-Preview ist nach Build/Sync reproduzierbar erreichbar.
- Jede externe Veröffentlichung hat ein explizites Operator-Go.

## Verifizierter Stand

- `npm run build`: pass
- `npm run desktop:sync-live`: pass
- `http://127.0.0.1:4107/membership`: HTTP 200
- `http://127.0.0.1:4107/membership/verifier`: HTTP 200
- `http://127.0.0.1:4107/membership/quellwert-monolith.svg`: HTTP 200, `image/svg+xml`
- `npm run verify:quellwert-public-catalog-contract`: pass
- `LIONCOM_BASE_URL=http://127.0.0.1:4107 npm run verify:quellwert-membership-preview`: pass
- `npm run verify:quellwert-visual-polish`: pass
- In-App-Browser: H1 `Unternehmen lesen. Klarer denken.`, Nav `Analysen|Methodik|Archiv|Lesen ↗`, Overflow `0`

## Nächster Konkreter Arbeitsblock

Der nächste sinnvolle Block ist kein weiterer Blind-Build, sondern `Operator-Go Closure`:

1. Operator-Go-Checklist final durchgehen.
2. GOOGL Source Review entscheiden.
3. 3 Manual-Review-Packets triagieren.
4. 10D Outcome am `2026-06-01` einplanen.
5. Erst danach External URL / Soft Launch / Revenue-Test öffnen.
