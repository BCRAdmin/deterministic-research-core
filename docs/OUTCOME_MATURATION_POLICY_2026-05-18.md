# Outcome Maturation Policy - 2026-05-18

## Scope

Outcome Maturation beschreibt, wann interne Outcome-Packets zeitlich reif genug sind, um gelesen, verglichen oder spaeter in Calibration-Datensaetze aufgenommen zu werden. Diese Policy ist eine interne Qualitaetsmessung. Sie ist keine Anlageberatung, kein Trading-System, keine Public-Freigabe und kein Datenabrufsystem.

## Horizonte

Die V1-Horizonte bleiben:

- `5D`: fruehes Smoke-Signal nach 5 Kalendertagen.
- `10D`: erstes Stabilitaetssignal nach 10 Kalendertagen.
- `20D`: mittlere Review-Lesart nach 20 Kalendertagen.
- `60D`: Mindestfenster fuer belastbarere Kalibrierung nach 60 Kalendertagen.

Der Maturation Calendar nutzt in V1 bewusst `naive_calendar_days`: `expected_maturity_date = decision_date + horizon_days`. Es werden keine Marktfeiertage, Boersenschliessungen oder externen Kalender geladen. Wenn genauere Handelskalender benoetigt werden, muss spaeter ein eigener fixture-only Calendar Contract entstehen.

## Status

- `pending`: Der erwartete Maturity-Tag ist noch nicht erreicht oder der Outcome-Packet selbst hat noch nicht genug Daten.
- `matured`: Der erwartete Maturity-Tag ist erreicht und der Outcome-Packet hat vollstaendige Instrument- und Benchmark-Daten.
- `data_unavailable`: Der Horizont ist zeitlich oder fachlich pruefbar, aber notwendige Basis-, Instrument- oder Benchmark-Daten fehlen.
- `invalidated`: Der Fixture-Source-Hash oder eine vergleichbare Integritaetspruefung ist gebrochen.

Zeitliche Maturation ersetzt nicht den Packet-Status. Ein Packet kann nach Kalender reif sein und trotzdem `data_unavailable` oder `invalidated` bleiben.

## Mindeststichproben

Kalibrierung darf nicht aus einzelnen guten oder schlechten Faellen abgeleitet werden. Fuer spaetere Regel-/Score-Kalibrierung gilt:

- mindestens `75` Samples pro Regel oder vergleichbarem Bewertungsbucket,
- nur reife `60D`-Outcomes,
- nur High-Confidence-Daten,
- keine `manual_review`-Faelle als automatische Positiv-/Negativsignale,
- keine `data_unavailable`- oder `invalidated`-Packets,
- keine Ableitung aus einem einzelnen Ticker, Sektor oder Archetype-Cluster.

`5D`, `10D` und `20D` duerfen nur Review- und Diagnosesignale liefern. Sie duerfen keine automatische Score-, Rating- oder Policy-Aenderung ausloesen.

## Keine LLM-Schaetzung

Fehlende Kurse, Benchmarks, Source-Hashes oder Maturity-Daten werden nicht durch LLMs geschaetzt. Wenn ein Datum, Kurs oder Benchmark fehlt, bleibt der Status `pending`, `data_unavailable` oder `invalidated`.

## Keine automatische Score-/Rating-Aenderung

Auch bei reifen 60D-Outcomes gilt Shadow Mode:

1. Outcome-Packets sammeln.
2. Datenqualitaet und Sample-Groesse pruefen.
3. Abweichungen intern berichten.
4. Keine automatische Score-, Rating-, Rule-Weight- oder Public-Status-Aenderung.
5. Jede echte Policy-Aenderung braucht separaten Review und Operator-Go.

## Manual Review bleibt bindend

`manual_review` bleibt bindend, auch wenn ein spaeteres Outcome positiv wirkt. Ein positiver 5D/10D/20D/60D-Ausgang hebt keine Audit-, Source-, Non-Advice-, Human-Review- oder Promotion-Gates auf.

Manual-review Outcomes duerfen als Diagnosematerial gelesen werden, aber nicht automatisch in Score-Kalibrierung einfliessen.

## Public- und Financial-Advice-Grenze

Maturation erzeugt nie:

- `public_ready=true`,
- Quellwert-Publish-Go,
- Production-Go,
- Trading-Automation,
- Financial-Advice-Freigabe,
- externe Reports.

Public Gates bleiben getrennt in Room16/Quellwert-Promotion-Contracts und brauchen Operator-Go.

## Naechste echte Datenfenster

Fuer eine Entscheidung am `2026-05-18` sind die naiven Maturity-Daten:

- `5D`: `2026-05-23`
- `10D`: `2026-05-28`
- `20D`: `2026-06-07`
- `60D`: `2026-07-17`

Diese Daten sind Review-Zeitpunkte, keine automatischen Aktionen.
