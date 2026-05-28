# Room16 / Quellwert Closure Backward Plan

- Stand: `2026-05-27`
- Zeitanker: `Europe/Berlin`
- Zielzustand: `private_soft_launch_ready_after_10d_outcome_and_operator_go`
- Aktueller Build-Status: `local_verified_operator_gated_not_external_ready`
- Wichtigster Satz: Wir sind kurz vor Ende des Builds, aber nicht kurz vor ungegated Launch. Die letzten Arbeiten sind echte Abschluss-Gates, keine Feature-Arbeit.

## 1. Definition von 100 Prozent

100 Prozent perfekt heisst in diesem Kontext nicht "alles ist public und bezahlbar", sondern:

- Core-, App-, Preview-, Content- und Visual-Verifier sind reproduzierbar gruen.
- Erwartete WARNs sind echte Gates und bleiben sichtbar.
- `publicReady`, `memberReady`, `effectivePublic` bleiben `0`, solange keine menschliche Freigabe existiert.
- Manual-Review-Faelle bleiben hidden.
- GOOGL bleibt als Public-Preview-Kandidat sichtbar, aber `sourceReview=needs_review` und `operatorGoRequired=true` bleiben bis zum finalen Source Review erhalten.
- 10D Outcome wird am `2026-06-01` als internes Kalibrierungssignal berechnet, nicht als Public-Marketingbeweis.
- Private Soft Launch startet erst nach Operator-Go.
- Revenue-Test laeuft ohne Checkout, ohne Payment-Automation und ohne Anlageempfehlungs-/Transaktionssprache.

## 2. Rueckwaerts Vom Ziel Gedacht

### Zielbild: Private Soft Launch + Revenue Interest Test

Launch darf erst starten, wenn diese Bedingungen gleichzeitig wahr sind:

| Bedingung | Muss-Zustand |
|---|---|
| URL / Zugang | Externe Preview-URL festgelegt, erreichbar und bewusst nicht breit indexiert |
| Recht / Identitaet | Impressum, Datenschutz, Kontaktweg operator-approved |
| Public Surface | Landing, Methodik, Archiv, Analyse-Seiten, Kontakt sauber erreichbar |
| Content | Keine Kauf-/Verkaufs-/Kursziel-/Portfolio-/Checkout-Sprache |
| GOOGL | Source Review entschieden oder Source-Delta sichtbar als `needs_review` belassen |
| Manual Reviews | 3 Room16-Pakete triagiert und weiterhin hidden, solange kein Operator-Go vorliegt |
| Outcome | 10D am `2026-06-01` berechnet und als intern dokumentiert |
| Revenue | Nur Interessenabfrage, manuelle Gespraeche, Concierge- oder Founding-Circle-Intent; kein Checkout |

### Direkt Vor Launch

1. Ziel-URL pruefen:
   - `curl -I <target>/membership`
   - `curl -I <target>/membership/analysen/alphabet-googl-cloud-ai-capex-pilot`
   - Hidden-Routen muessen `404` bleiben: `nvidia-nvda-ai-fcf-review`, `micron-technology-mu-room16-preview`.

2. Quellwert-Verifier gegen Ziel-URL:
   - `npm run verify:quellwert-public-catalog-contract`
   - `LIONCOM_BASE_URL=<target> npm run verify:quellwert-membership-preview`
   - `npm run verify:quellwert-visual-polish`

3. Content-Scan:
   - Verbotene Tokens: `Buy`, `Sell`, `Hold`, `Overweight`, `Underweight`, `Accumulate`, `Strong Buy`, `Tactical Trim`, `Tactical Underweight`, `Position Sizing`, `Stop Loss`, `Kaufen`, `Verkaufen`, `Kursziel`, `Modellportfolio`, `Checkout`, `Jetzt kaufen`, `Renditegarantie`.
   - Erlaubt: neutrale Research-, Methodik-, Risiko-, Quellen- und Interessenabfrage-Sprache.

4. Operator-Go schriftlich festhalten:
   - `Go fuer private Preview`
   - `Go fuer Founding-Circle-Interessenabfrage`
   - `No-Go fuer Checkout/Payment`
   - `No-Go fuer paid investment-recommendation-like Output`

### `2026-06-01`: 10D Outcome Gate

Das 10D-Fenster ist der naechste harte Outcome-Zeitpunkt fuer Batch `guardrail_coverage_batch_004_ir_coverage`.

| Element | Stand / Regel |
|---|---|
| Price Basis | `2026-05-15` |
| 5D Ende | `2026-05-22` |
| 10D Evaluation | `2026-06-01` |
| 5D Computed Rows | `37` |
| Pending Rows | `0` |
| 5D False-Pass-Kandidat | `AVGO` |
| 5D False-Block-Watchlist | `NOW`, `RKLB`, `ZS` |
| Positive Monitor | `MDB` |
| Policy | keine Guard-, Rating-, Report- oder Calibration-Aenderung aus 1D/5D allein |

10D-Arbeitslogik:

1. Nach verfuegbaren Schlusskursen fuer `2026-06-01` Preis-CSV aktualisieren:
   - `python3 scripts/outcomes/refresh_price_csvs_yahoo_chart.py --batch-id guardrail_coverage_batch_004_ir_coverage --target-date 2026-06-01 --write-report-json outputs/batches/guardrail_coverage_batch_004_ir_coverage/PRICE_DATA_REFRESH_10D.json`

2. 10D-Artefakt erzeugen:
   - Der aktuelle Script `scripts/outcomes/compute_outcome_5d_artifacts.py` ist explizit 5D. Fuer 10D nicht blind wiederverwenden.
   - Entweder den Outcome-Runner auf `window=10D` generalisieren oder ein eigenes `OUTCOME_10D_REVIEW.{json,md}` erzeugen, das dieselben Felder wie 5D nutzt, aber `ten_day_end_date=2026-06-01` und `window=10D` schreibt.

3. Ergebnis pruefen:
   - alle 37 Rows computed
   - 32 unique tickers mit Benchmark
   - keine fehlenden Preis- oder Benchmark-Ticker
   - keine Forward-Fills, keine synthetischen Preise, keine Ersatz-Enddaten
   - `AVGO`, `NOW`, `RKLB`, `ZS`, `MDB` gesondert dokumentieren

4. Entscheidung nach 10D:
   - `AVGO` nur dann als Guard-Review behandeln, wenn 10D die 5D-Schwäche relativ zum `SMH` bestaetigt.
   - `NOW` und `ZS` nur dann als moegliche zu-harte Review-Gates behandeln, wenn die urspruenglichen Source-/Freshness-Gruende nicht mehr tragen.
   - `RKLB` bleibt selbst bei Outperformance kein einfacher False Block, weil FCF-, Execution- und Early-Commercial-Risiko absichtlich harte Gates sind.
   - `MDB` bleibt positiver Monitor, aber kein automatischer Promote.

## 3. Die 3 Manual-Review-Pakete

Die aktuell offenen 3 Pakete stammen aus der Room16-App-Runtime, nicht aus der breiteren Batch-004-Manual-Review-Menge.

| # | Ticker | Report | Pfad | Status |
|---:|---|---|---|---|
| 1 | `MSFT` | `2026-05-16 Room 16 MSFT DeepSeek V4 Complete Dossier.pdf` | `/Users/BjornRosinger/Documents/Room 16 Reports/Microsoft (MSFT)/2026-05-16 Room 16 MSFT DeepSeek V4 Complete Dossier.pdf` | `manual_review`, hidden |
| 2 | `RGTI` | `2026-05-15 Room 16 RGTI DeepSeek V4 Complete Dossier.pdf` | `/Users/BjornRosinger/Documents/Room 16 Reports/Rigetti Computing (RGTI)/2026-05-15 Room 16 RGTI DeepSeek V4 Complete Dossier.pdf` | `manual_review`, hidden |
| 3 | `RGTI` | `2026-05-15 Room 16 RGTI Internal Manual Review Reading Version.pdf` | `/Users/BjornRosinger/Documents/Room 16 Reports/Rigetti Computing (RGTI)/2026-05-15 Room 16 RGTI Internal Manual Review Reading Version.pdf` | `manual_review`, hidden |

Gemeinsame aktuelle Blocker:

- `manual_review_required`
- `human_source_verification_open`
- `non_advice_confirmation_open`
- `promotion_stack_complete` fehlt
- `operator_visibility_go` fehlt

Erlaubte lokale Entscheidungen:

- `keep_hidden`
- `approved_internal`
- `reject`
- `needs_more_evidence`

Verboten ohne Operator-Go:

- `public`
- `member`
- `publish`
- `rerun`
- `push`

### Meine Einschaetzung Der Pakete

| Paket | Wahrscheinlich sinnvoller Review-Ausgang | Warum |
|---|---|---|
| `MSFT Complete Dossier` | erster Kandidat fuer `approved_internal`, aber nicht public | Groesserer, quellenreicher Mega-Cap; am ehesten geeignet, um die Review-Mechanik sauber zu testen. Trotzdem keine Public-Freigabe ohne Source- und Non-Advice-Abnahme. |
| `RGTI Complete Dossier` | eher `keep_hidden` oder `needs_more_evidence` | Deep-Tech/Quantum, hohe Volatilitaet, fruehe Kommerzialisierung und 5D extreme Bewegung. Das ist ein Guard-Stresstest, kein Softlaunch-Sample. |
| `RGTI Internal Reading Version` | `keep_hidden`, ggf. als Duplikat/Lesefassung markieren | Interne Lesefassung ist kein eigenstaendiges Publish-Artefakt. Review soll klaeren, ob sie nur Evidence fuer die Dossier-Pruefung ist. |

## 4. Manual-Review-Protokoll

Jedes Paket bekommt dieselbe Checkliste. Keine Abkuerzungen.

### Schritt 1: Identitaet Und Artefaktstatus

- Stimmt Ticker, Unternehmen, Datum, Modell, Report-Version?
- Ist die Datei genau die Runtime-Datei aus dem Packet?
- Bei RGTI: sind `Complete Dossier` und `Internal Manual Review Reading Version` inhaltlich Duplikate, abgeleitete Lesefassung oder zwei getrennte Review-Gegenstaende?
- Gibt es einen Source-/Evidence-Bundle-Pfad, der im Report referenziert wird?

Exit:

- `pass`: eindeutiges Artefakt
- `needs_more_evidence`: Artefakt-/Versionsherkunft unklar
- `keep_hidden`: interne Lesefassung oder Duplikat ohne Publish-Funktion

### Schritt 2: Human Source Verification

Fuer jede harte Zahl im Report:

- Claim extrahieren
- Originalquelle identifizieren
- Quelle oeffnen oder lokale Source-Datei lesen
- Zeitraum, Einheit, Segmentdefinition und Rechenweg notieren
- Claim als `verified`, `mismatch`, `unsupported` oder `ambiguous` markieren

Muss geprueft werden:

- Umsatz, Segmentumsatz, Wachstum
- Operating Income / Margin
- Cashflow, Capex, FCF
- SBC / Dilution
- Net cash / debt
- Valuation Multiples
- Price basis und technische Kennzahlen
- Guidance oder Management-Kommentare nur aus direkter Quelle, nicht aus abgeleiteten Daten

Exit:

- `approved_internal` nur bei `verified` oder sauber erklaertem `ambiguous`
- `needs_more_evidence` bei fehlender Originalquelle
- `reject` bei echter falscher Zahl ohne einfache Reparatur

### Schritt 3: Data-Quality Und Reconciliation

Pruefen:

- `price_basis_date` nicht vor `as_of_date`, ausser bewusst dokumentiert
- Earnings-Date verfuegbar oder bewusst als unavailable markiert
- Source-frame-Varianten nicht fälschlich verworfen
- Periodentypen: Q, TTM, FY, LTM nicht vermischt
- True-source disagreement konkret beurteilt
- Keine SEC-derived Fixture als direkte Company Guidance darstellen

Exit:

- Datenluecke darf intern dokumentiert werden.
- Datenluecke darf nicht durch Public-Sprachglättung unsichtbar werden.

### Schritt 4: Non-Advice Review

Pruefen:

- keine direkte Kauf-/Verkaufsaufforderung
- keine Kursziele
- keine Positionsgroessen
- keine Dringlichkeitssprache
- keine Modellportfolio- oder Umsetzungssprache
- keine individuelle Anlegeransprache
- klarer Hinweis: Research-Kontext, keine Anlageberatung, keine persönliche Empfehlung

Strenge Regel: Auch `Hold`, `Accumulate`, `Underweight` etc. bleiben fuer Public Copy maskiert, selbst wenn sie intern als Rating existieren.

### Schritt 5: Promotion Readiness

Nur falls ein Paket irgendwann als Public-Kandidat gedacht ist:

- Public-Copy separat schreiben
- interne Pipeline-Sprache entfernen
- Source-Box sichtbar
- Methodik-Link sichtbar
- Gate-Hinweis sichtbar
- hidden/member/public Routing testen
- Operator-Go dokumentieren

Fuer den jetzigen Closure-Block reicht:

- MSFT maximal `approved_internal`
- RGTI maximal `keep_hidden` / `needs_more_evidence`
- keine Public-/Member-Promotion

### Schritt 6: Decision Log

Jedes Paket braucht eine kurze Entscheidung:

```text
Ticker:
Report:
Reviewer:
Timestamp:
Decision: keep_hidden | approved_internal | reject | needs_more_evidence
Source verification: pass | partial | fail
Non-advice: pass | fail
Promotion: blocked
Reason:
Next action:
```

## 5. GOOGL Source Review

Aktueller Stand:

- `GOOGL` ist Public-Preview-Kandidat.
- `publicPreviewReady=true`
- `externalPublicationReady=false`
- `operatorGoRequired=true`
- `sourceReview=needs_review`
- Offener Punkt: Source-Registry-Delta zwischen lokalem Bundle und expliziter IR/Q1-Release-Quelle.

### Claims, Die Menschlich Geprueft Werden Muessen

| Claim | Pruefung |
|---|---|
| Q1 2026 Umsatz `109.9B USD` | Alphabet Q1 Release / Filing, Einheit und Zeitraum |
| Google Cloud Umsatz `20.0B USD` | Segmentdefinition im Q1 Release |
| Google Cloud Wachstum `63%` | Zeitraum, YoY-Basis, Segmentlogik |
| Operating Margin `36.1%` | Operating income / revenue Rechenweg |
| Other income net gain `37.7B USD` | nicht als operative Wiederholqualitaet darstellen |
| Q1 Capex `35.674B USD` | Cashflow-/Capex-Zeile pruefen |
| TTM FCF `64.429B USD` | CFO minus Capex, TTM Periodenabdeckung |
| EV/Sales und P/FCF | Market-data date `2026-05-08`, Nenner, EV/Market-Cap Basis |
| Kurs / SMA / RSI | Price-CSV und Indikatorrechnung |
| Source Registry | IR Release entweder explizit in Registry ergaenzen oder Gate sichtbar offen lassen |

### GOOGL Decision Tree

- Wenn alle Claims gegen Originalquelle stimmen und Source-Registry-Delta geschlossen ist: `sourceReview=pass` moeglich, aber externer Publish weiterhin Operator-Go.
- Wenn Claims stimmen, aber Registry-Delta offen bleibt: GOOGL darf private Preview bleiben, aber nicht als final source-reviewed external publish verkauft werden.
- Wenn harte Claims mismatchen: Public-Copy reparieren oder GOOGL aus Sample-Auswahl nehmen.
- In keinem Fall: 5D/10D Outcome als Beweis fuer die Analysequalitaet in Public Copy verwenden.

## 6. Operator-Go-Checklist Als Abschlussgate

Vor Soft Launch zu entscheiden:

- [ ] Externe URL/Domain
- [ ] Impressum final
- [ ] Datenschutz final
- [ ] Kontaktweg final
- [ ] Robots/Indexing: private Preview weiter blocken oder bewusst oeffnen
- [ ] Sample-Seite: GOOGL/SNOW/MSFT Auswahl
- [ ] GOOGL Source Review oder sichtbares `needs_review`
- [ ] Founding-Circle-Draft kuerzen/freigeben
- [ ] Keine Payment-/Checkout-Aktivierung
- [ ] Keine paid recommendation-like Leistung ohne gesonderten Compliance-Review

Go-Kriterien:

- `preview_pass_operator_gated`
- Non-Advice sichtbar
- Hidden Cases hidden
- Keine Hard-Signal-Tokens in Public Copy
- Legal-Seiten mindestens operator-approved fuer Preview
- Kontakt-/Interest-Prozess manuell kontrolliert

No-Go:

- Legal unklar
- Sample liest sich wie Empfehlung
- Checkout oder Payment soll aktiviert werden
- GOOGL Source-Review wird als finaler Pass missverstanden
- Outcome-Signale werden als Rating-/Guard-Evidence in Public Copy genutzt

## 7. Testmatrix

### Room16 App / Gate Tests

Frisch am `2026-05-27` geprueft:

| Command | Erwartung | Aktueller Status |
|---|---|---|
| `npm run verify:review-gate-status` | `WARN` mit 3 Manual Reviews, effective public 0 | `WARN` korrekt |
| `npm run verify:manual-review-packets` | `WARN`, 3 Packets, 0 missing files | `WARN` korrekt |
| `npm run verify:publish-readiness` | `WARN`, promotion blocked | `WARN` korrekt |
| `npm run verify:public-gate` | `pass` | `pass` |

Vor Launch erneut laufen:

```bash
npm run lint
npm run verify
npm run verify:german-output-quality
npm run verify:report-machine
npm run verify:manual-review-workbench
npm run verify:review-gate-status
npm run verify:manual-review-packets
npm run verify:publish-readiness
npm run verify:public-gate
```

Pass/Fail-Interpretation:

- `review-gate-status`, `manual-review-packets`, `publish-readiness` duerfen WARN sein, wenn sie genau die offenen Gates abbilden.
- Jeder `FAIL` ist Blocker.
- Jeder unerwartete Wechsel zu `public_ready > 0`, `member_ready > 0` oder `effective_public > 0` ist Blocker.

### Quellwert Public Surface Tests

Frisch am `2026-05-27` geprueft:

| Command | Status |
|---|---|
| `curl -I http://127.0.0.1:4107/membership` | `200 OK` |
| `npm run verify:quellwert-public-catalog-contract` | `pass` |
| `LIONCOM_BASE_URL=http://127.0.0.1:4107 npm run verify:quellwert-membership-preview` | `pass` |
| `npm run verify:quellwert-visual-polish` | `pass` |

Vor externer Preview gegen Ziel-URL:

```bash
npm run build
npm run desktop:sync-live
curl -I <target>/membership
curl -I <target>/membership/verifier
curl -I <target>/membership/quellwert-monolith.svg
npm run verify:quellwert-public-catalog-contract
LIONCOM_BASE_URL=<target> npm run verify:quellwert-membership-preview
npm run verify:quellwert-visual-polish
```

Manuell im Browser pruefen:

- Desktop `1120`, `1366`, `1728`
- Tablet `768`
- Mobile `390`, `430`
- kein Horizontal-Overflow
- Header/Footer sichtbar
- Detailseiten: GOOGL, SNOW, MSFT sichtbar
- Hidden: NVDA, MU nicht sichtbar und Detailroute `404`
- Source/Gate-Hinweise sichtbar
- Non-Advice sichtbar
- Kontaktweg funktioniert, aber startet keinen Checkout

### Legal / Compliance Copy Tests

Keine Rechtsberatung; finale rechtliche Pruefung bleibt gesondertes Gate.

Pruefen:

- Impressum: Betreiber, Adresse/Kontakt, Verantwortlichkeit, ggf. Umsatzsteuer-/Registerdaten korrekt.
- Datenschutz: Hosting, Logs, Kontaktaufnahme, Tracking, Forms, Newsletter, Cookies realistisch beschrieben.
- Konflikte: eigene Positionen, bezahlte Auftraege, Affiliate-/Issuer-Beziehungen sichtbar oder explizit nicht vorhanden.
- Non-Advice: keine persönliche Empfehlung, keine Aufforderung zu Transaktionen.
- Keine Formulierungen, die faktisch individuelle Anlageberatung versprechen.
- Keine Marktmanipulationsrisiken: keine irrefuehrenden Signale, keine uebertriebenen Kurs-/Renditeclaims.

Regulatorischer Hintergrund fuer die Gate-Logik:

- BaFin beschreibt fuer Anlage- und Anlagestrategieempfehlungen Mindestanforderungen an Objektivitaet, Sorgfalt, Identitaet und Interessenkonflikte.
- ESMA betont fuer Investment Recommendations, auch auf Social-/Web-Kanaelen, objektive und transparente Darstellung sowie klare Trennung von Fakten und Meinungen.

### Revenue-Test Tests

Erlaubt:

- manuelle Interessenabfrage
- E-Mail/Kontaktformular ohne Zahlungsfluss
- Founding-Circle-Intent mit klarer Scope-Beschreibung
- Concierge-Gespraeche ueber Research-Prozess

Nicht erlaubt vor separatem Go:

- Checkout
- Zahlungslink
- "Jetzt kaufen"
- Preis- oder Renditeversprechen
- personalisierte Portfolio-/Kauf-/Verkaufsantworten
- paid Reports, die als konkrete Empfehlung verstanden werden koennen

Messung:

- Anzahl qualifizierter Rueckmeldungen
- Warum interessiert?
- Welche Inhalte wuerden sie bezahlen?
- Welche Frequenz?
- Welcher Preisanker ohne sofortigen Verkauf?
- Welche Bedenken?

## 8. Reihenfolge Der Verbleibenden Arbeiten

### Jetzt bis `2026-05-31`

1. Operator-Go-Checklist durchgehen und offene Entscheidungen markieren.
2. GOOGL Source Review beginnen, mindestens Source-Registry-Delta entscheiden.
3. 3 Manual-Review-Pakete lesen und Decision Log pro Paket erzeugen.
4. Founding-Circle-Draft auf Interest-only ohne Checkout kuerzen.
5. Legal-Seiten operator-reviewen.
6. Ziel-URL/Robots/Kontaktweg festlegen.

### `2026-06-01`

1. Preis-CSV fuer 10D aktualisieren.
2. 10D Outcome erzeugen.
3. 10D Watchlist dokumentieren.
4. Entscheiden: keine Aenderung / Guard-Review-Backlog / Source-Fix-Backlog.
5. Kein Public-Claim aus Outcome ableiten.

### Nach `2026-06-01`

1. Finaler Operator-Go.
2. Ziel-URL-Smoke.
3. Verifier-Matrix gegen Ziel-URL.
4. Private Soft Launch an kleine Liste.
5. Nur manuelle Interessen-/Gesprächsannahme.
6. Revenue-Learning dokumentieren.

## 9. Harte Stop-Regeln

Sofort stoppen, wenn:

- ein Manual-Review-Paket public/member-ready wird, ohne dokumentierten Operator-Go
- ein Hidden-Case auf Public-Seiten sichtbar ist
- Checkout-/Payment-Sprache in Public Copy auftaucht
- ein Analyseartikel als Kauf-/Verkaufsempfehlung gelesen werden kann
- GOOGL `sourceReview=pass` gesetzt wird, ohne Source-Registry-Delta wirklich zu schliessen
- 10D Outcome als Marketingbeweis genutzt werden soll
- Legal/Datenschutz/Impressum nicht operator-approved sind

## 10. Naechster Konkreter Arbeitsblock

Der naechste sinnvolle Block ist `Manual + Source Closure`:

1. MSFT Manual Review lesen und Decision Log schreiben.
2. RGTI Complete Dossier als Guard-Stresstest lesen und Entscheidung `keep_hidden` / `needs_more_evidence` begruenden.
3. RGTI Internal Reading Version als interne Lesefassung / Duplikat klassifizieren.
4. GOOGL Source-Registry-Delta entscheiden.
5. Danach `npm run verify:review-gate-status`, `npm run verify:manual-review-packets`, `npm run verify:publish-readiness` erneut laufen lassen.

Erst danach lohnt die finale Softlaunch-URL-Arbeit.
