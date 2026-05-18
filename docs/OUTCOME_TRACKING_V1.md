# Outcome Tracking V1

## Scope

Outcome Tracking V1 ist eine interne, deterministische Qualitaetsmessung fuer Research-Entscheidungen. Es misst ex-post, ob ein interner Report relativ zum Benchmark besser oder schlechter lag. Es ist keine Anlageberatung, kein Handelssystem und keine Public-Freigabe.

## Harte Grenzen

- Keine Live-Datenabrufe in V1.
- Keine Provider-Secrets, keine externen Datenpfade und keine LLM-only-Zahlen.
- Keine Trading-Automation.
- Kein Public-Report, kein Quellwert-Publish-Go und keine Financial-Advice-Ableitung.
- `manual_review` bleibt bindend, auch wenn ein spaeteres Outcome positiv aussieht.

## Packet-Schema

`research_agent/outcomes/outcome_packet.py` erzeugt `OutcomePacket` fuer die Horizonte:

- `5D`
- `10D`
- `20D`
- `60D`

Kernfelder:

- `instrument`
- `decision_date`
- `decision_type`
- `basis_price`
- `benchmark`
- `horizon`
- `status`: `pending`, `matured`, `invalidated`, `data_unavailable`
- `observed_return`
- `benchmark_return`
- `delta_to_benchmark`
- `source_hash`
- `calc_version`
- `notes`
- `manual_review_reason`

`public_ready` ist in V1 immer `false`. Public-Gates bleiben getrennt in Room16/Quellwert-Promotion-Contracts.

## Fixture-First Engine

Die Engine laedt ausschliesslich JSON-Fixtures aus `research_agent/fixtures/outcomes/`. Ein Fixture enthaelt Basispreis, Benchmark-Basispreis, kuenftige Instrument-/Benchmark-Schlusskurse und erwartete Status je Horizont.

Der Rechner:

1. sortiert nur Beobachtungen nach dem `decision_date`,
2. erzeugt `pending`, solange der Horizont noch nicht genuegend kuenftige Handelstage hat,
3. erzeugt `matured`, wenn Instrument und Benchmark fuer den Horizont vollstaendig sind,
4. erzeugt `data_unavailable`, wenn Basisdaten, Benchmark-Daten oder die komplette Instrument-Historie fehlen,
5. erzeugt `invalidated`, wenn der Fixture-Source-Hash nicht zum deterministischen Payload passt.

`no_live_fetch=False` wirft bewusst einen Fehler. V1 ist kein Datenabrufsystem.

## Mindeststichprobe fuer spaetere Kalibrierung

Outcome-Packets duerfen erst nach echten Kalenderfenstern bewertet werden. Fuer Regel- oder Score-Kalibrierung bleibt die bestehende Shadow-Mode-Grenze fuehrend:

- mindestens `75` Samples pro Regel,
- reifer `60D`-Horizont,
- High-Confidence-Daten,
- keine automatische Gewichtsaenderung aus kleinen Samples.

## Review-Fenster

- `5D`: fruehes Smoke-Signal, keine Policy-Aenderung.
- `10D`: erstes Stabilitaetssignal, weiterhin intern.
- `20D`: mittlere Lesart fuer Report-/Quality-Review.
- `60D`: Mindestfenster fuer belastbarere Kalibrierung.

Diese Horizonte brauchen echte Kalenderzeit. Fehlende Tage werden nicht simuliert und nicht mit LLM-Schaetzungen gefuellt.

## Verifier

`python -m research_agent.outcomes.verify_outcome_schema` prueft:

- alle Pflichtszenarien vorhanden,
- alle Horizonte `5D/10D/20D/60D` erzeugt,
- erwartete Golden-Status stimmen,
- `manual_review` wird nie `public_ready`,
- `calc_version` bleibt `outcome-tracking-v1`,
- Live-Fetch bleibt gesperrt.
