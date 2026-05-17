# SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL – Internal Report Template

> Interne Manual-Review-Vorlage für frühe Deep-Tech-/Hardware-/Story-Stock-Fälle. Dieses Template erzeugt eine vollständige interne Research-Lesefassung, aber keine Public-Freigabe.

## Template-Regeln

- Kein Clean Buy oder Accumulate bei aktivem Deep-Tech-Profil ohne vollständige SEC/IR-Evidence.
- Manual Review ist bei dieser Klasse der Normalzustand, nicht die Ausnahme.
- `public_rating = null`, wenn `publishable = false`.
- Der interne Report muss trotzdem vollständig, konkret und lesbar sein.
- Technische Analyse darf nur Timing und Risk Management liefern.
- Contract Wins müssen immer auf Materialität geprüft werden.
- Accounting Gains müssen vom operativen Geschäft getrennt werden.
- Cash Runway ist ein Schutzfaktor, kein Bewertungsargument.
- Keine harten Zahlen ohne `source_tier` und `evidence_status`.

## Statusbox

| Feld | Wert |
| --- | --- |
| Unternehmen | `{{company_name}}` |
| Ticker | `{{ticker}}` |
| Status | `manual_review` |
| Internes Rating | `{{internal_rating}}` |
| Externe Anzeige | `{{external_display_rating}}` |
| publishable | `false` |
| Public Rating | `{{public_rating}}` |
| Archetype | `SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL` |
| Wichtigste Gründe | `{{summary_reasons_de}}` |

## Executive Summary

`{{company_name}}` ist keine normale Investmentstory, solange Revenue, Adoption, Cashflow und operative Qualität noch nicht skaliert und primär belegt sind. Der Titel ist als spekulative Deep-Tech-Option zu behandeln, nicht als bewiesener Compounder.

Interne Grundlogik:

- Keine Neuaufnahme ohne vollständige SEC/IR-Evidence und ohne Klärung blockierender Issues.
- Bestehende Kleinstpositionen höchstens als spekulative Optionswette.
- Reduktion in Stärke ist rational, wenn die Position größer ist als die Evidenzbasis.
- Kein Public Rating, solange `publishable = false`.
- Vor realer Investmententscheidung: SEC/IR-Bestätigung, Contract-Materiality, Accounting-Quality-Prüfung und Cash-Runway-Brücke.

## Key Metrics Snapshot

| Kennzahl | Wert | Einordnung | Source Tier / Evidence Status |
| --- | ---: | --- | --- |
| Market Cap | `{{market_cap}}` | Datenstand und Preisbezug angeben | `{{source_tier}} / {{evidence_status}}` |
| Revenue TTM | `{{revenue_ttm}}` | Umsatzbasis und Skalierungsgrad einordnen | `{{source_tier}} / {{evidence_status}}` |
| Latest Quarter Revenue | `{{latest_quarter_revenue}}` | Wachstum nur als belastbar behandeln, wenn wiederholbar | `{{source_tier}} / {{evidence_status}}` |
| Market Cap / Revenue | `{{market_cap_to_revenue}}` | Bewertung relativ zur Umsatzbasis | Berechnung auf `{{source_tier}}`-Basis |
| Operating Income / Loss | `{{operating_income}}` | Operative Qualität, nicht GAAP-Sondereffekte | `{{source_tier}} / {{evidence_status}}` |
| Free Cash Flow / Cashburn | `{{fcf}}` | Mittelabfluss und Runway-Belastung | `{{source_tier}} / {{evidence_status}}` |
| Cash + Investments | `{{cash_and_investments}}` | Stichtag nennen; nicht als aktuelle Zahl verkaufen, wenn alt | `{{source_tier}} / {{evidence_status}}` |
| SBC / Revenue | `{{sbc_to_revenue}}` | Verwässerungsrisiko relativ zur Umsatzbasis | `{{source_tier}} / {{evidence_status}}` |
| Share Dilution | `{{share_dilution}}` | Per-share economics prüfen | `{{source_tier}} / {{evidence_status}}` |

## Technology Reality Check

Technische Meilensteine können relevant sein, sind aber keine Umsatzbeweise. Roadmap, Prototypen, Tests, Demonstrationen, Qubit-Zahlen, Flug-/Robotik-/Space-/Defense-Meilensteine oder AI-Hardware-Claims dürfen die Bewertung nicht alleine tragen.

Zu prüfen:

- Was ist technisch demonstriert?
- Was ist kundenseitig produktiv genutzt?
- Was ist Forschungs-, Prototyp- oder Regierungskontext?
- Was übersetzt sich in wiederholbaren Revenue?
- Welche technischen Hürden bleiben?

## Commercial Adoption

Commercial Adoption ist der Kern der Investmentfrage. Einzelne Kunden, Pilotprojekte oder Meilensteinumsätze sind erst dann belastbar, wenn Wiederholbarkeit, Umsatzrealisierung, Margenlogik und Kundennachfrage sichtbar werden.

Pflichtfragen:

- Ist Revenue wiederkehrend oder einmalig?
- Gibt es Folgeaufträge?
- Wie konzentriert sind Kunden und Projekte?
- Ist die Nachfrage kommerziell, staatlich, forschungsnah oder prototypisch?
- Gibt es Hinweise auf skalierbare Lieferung?

## Contract / Order Materiality

Alle Contract Wins und Orders müssen materialisiert werden.

| Auftrag / Gegenpartei | Wert | Timing | Wert vs. Revenue | Wert vs. Market Cap | Einordnung |
| --- | ---: | --- | ---: | ---: | --- |
| `{{contract_values}}` | `{{contract_value}}` | `{{delivery_or_revenue_timing}}` | `{{contract_value_vs_revenue}}` | `{{contract_value_vs_market_cap}}` | `{{contract_materiality_assessment}}` |

Pflichtinterpretation:

- Operativ relevant gegenüber kleiner Umsatzbasis?
- Proof-of-Concept oder skalierter Umsatzmotor?
- Wiederkehrend oder einmalig?
- Kommerziell oder staatlich/forschungsnah/prototypisch?
- Stützt der Auftrag die Bewertung tatsächlich oder nur die Technologieoption?

## Financial Reality

Die finanzielle Realität entscheidet, ob aus einer Technologieoption ein operatives Investment werden kann.

Pflichtpunkte:

- Umsatzbasis konkret einordnen.
- Umsatzsprünge von kleiner Basis nicht als Turnaround verkaufen.
- Operating Loss und Free Cash Flow separat prüfen.
- Cashburn und Runway realistisch darstellen.
- SBC und Verwässerung in per-share economics übersetzen.
- Keine harte Kennzahl ohne Quellenstatus.

## Cash Runway

Cash Runway reduziert kurzfristiges Existenz- und Finanzierungsrisiko. Sie rechtfertigt aber nicht automatisch die Bewertung.

Pflichtpunkte:

- Cash + Investments mit Stichtag.
- Burn-Rate und Runway-Sensitivität.
- Finanzierungsbedarf bei verzögerter Kommerzialisierung.
- Verwässerungsrisiko bei künftiger Kapitalaufnahme.

## Dilution / SBC Risk

SBC und Verwässerung sind bei dieser Klasse zentral. Ein Unternehmen kann technisch Fortschritte machen, während Aktionäre pro Aktie wirtschaftlich verlieren.

Pflichtpunkte:

- `sbc_to_revenue`
- `share_dilution`
- Aktienzahlentwicklung
- Finanzierung über Aktien
- Auswirkungen auf per-share economics

## Accounting Quality

Accounting Gains müssen vom operativen Geschäft getrennt werden.

Pflicht-Caveat bei relevanten Warrant-/Derivative-/Fair-Value-Effekten:

> GAAP net income was helped by non-operating fair-value effects and does not indicate an operating turnaround.

Pflichtfragen:

- Ist GAAP Net Income durch nicht-operative Effekte verbessert?
- Bleibt Operating Income negativ?
- Ist Free Cash Flow weiterhin negativ?
- Werden Warrant-, Derivat- oder Fair-Value-Effekte klar getrennt?

## Valuation Disconnect

Bewertung gegen operative Realität stellen.

Pflichtpunkte:

- Market Cap vs. Revenue.
- Market Cap vs. annualisierte Run-Rate, falls sinnvoll.
- Bewertung nur tragbar bei wiederholbarem Umsatzwachstum, sinkendem Cashburn und kontrollierter Verwässerung.
- Explizit sagen, welche Zukunft bereits eingepreist ist.

## Technical Setup

Technische Analyse nur als Timing/Risk Management nutzen.

Erlaubt:

- Reduktionsfenster in Stärke.
- Risikolevels.
- Volatilitätskontext.

Nicht erlaubt:

- Chartstärke als Beweis für Commercial Adoption.
- Technicals als dominante Langfristthese.

## What Would Change the View

Eine bessere Sicht erfordert:

1. SEC/IR-bestätigte aktuelle Zahlen.
2. Wiederholbarer Revenue.
3. Contract-Materiality mit Wert, Timing und Kundentyp.
4. Sinkender Operating Loss ohne Accounting-Sondereffekte.
5. Sinkender Cashburn.
6. Kontrollierte SBC und Verwässerung.

## Final Internal View

`{{external_display_rating}}`. Kein Clean Buy oder Accumulate ohne vollständige Evidence. Bestehende Kleinstpositionen nur als spekulative Optionswette, wenn die Positionsgröße zu den Risiken passt. `{{company_name}}` ist aktuell keine Kernposition und kein bewiesener Compounder.

## Required Follow-Up

- SEC/IR-Filings und Earnings-Unterlagen ziehen.
- Harte Kennzahlen aus Primärquellen neu aufbauen.
- Contract Wins materialisieren.
- Accounting-Effekte vom operativen Geschäft trennen.
- Runway und Verwässerung aktualisieren.
- Public-Freigabe erst nach bestandenen Gates.

## Appendix

### Triggered Rules

`{{triggered_rules}}`

### Ratings

- internal_rating: `{{internal_rating}}`
- external_display_rating: `{{external_display_rating}}`
- public_rating: `{{public_rating}}`
- publishable: `false`

### Source Limitations

- source_tier: `{{source_tier}}`
- evidence_status: `{{evidence_status}}`
- harte Zahlen ohne SEC/IR-Evidence bleiben intern und nicht public-freigabefähig.
