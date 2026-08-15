# RFC-0002 — Semantic IR Spine and Verification Completion

Status: `IMPLEMENTED_SHADOW_PENDING_INDEPENDENT_REVIEW`

## Entscheidung

Der externe Architekturreview des Semantic-Compiler-Stands `3d3a08a4` wird
übernommen. Foundation `1.0.0`, Registry Foundation `1.1.0`, Authority Bundle v3
und das bestehende Shadow-Gerüst bleiben unverändert. RFC-0002 ergänzt einen
neuen, durchgehenden Compilerpfad oberhalb dieser Baseline.

BA10, Renderer-Cutover, Publication und produktiver Release bleiben gesperrt.

## Root Cause

Der erste BA4–BA9-Stand war deterministisch, aber nicht durchgängig semantisch:
Parser, Tabellen und Graphen liefen teilweise neben bereits akzeptierten
Legacy-Endartefakten. Der fehlende L10-Pass erlaubte außerdem, Aggregate direkt
als erfolgreich zu deklarieren, statt sie aus Diagnostics abzuleiten.

## Additive Contracts

Die neue Spine lautet:

```text
BA3 SourceSnapshotIR
→ SourceInputIR@2
→ ParsedPayloadIR@2 / TableDiscoveryIR@2 / SemanticTableIR@2
→ NormalizedFactRecordIR@2
→ TypedFactSpineIR@2
→ MetricSignatureIR@2 / MetricSpineIR@2 / FormulaEvaluationIR@1
→ EvidenceGraphSpineIR@2
→ ClaimGraphSpineIR@2
→ DecisionGraphSpineIR@2
→ VerificationPlanIR@1
→ DiagnosticIR@1 / CompileVerdictIR@1 / VerificationReportIR@1
```

Authority Bundle v3 wird nur einmal über benannte, hashgebundene
Compatibility-Inputs eingelesen. Danach konsumiert jeder Pass ausschließlich
vorgelagerte IRs. Der Adapter erzeugt den stabilen Diagnostic
`LEGACY_COMPATIBILITY_ADAPTER_USED`; ein unbenannter Bypass ist unzulässig.

## Pass- und Layer-Zuordnung

| Bauabschnitt | Layer | Output |
| --- | --- | --- |
| BA4 | L3 | Parsed Payloads, vollständige Table Discovery |
| BA5 | L4–L5 | normalisierte Records, Typed Facts |
| BA6 | L6 | enge Metric Signatures, Metrics, Formeln |
| BA7 | L7–L8 | Evidence Graph und Claim Graph |
| BA8 | L9 | Decision Graph |
| BA9 | L10 | Verification Plan, Diagnostics, Verdict |

Der additive Passvertrag besitzt zehn nicht überspringbare, seiteneffektfreie,
content-addressed und replay-verifizierte Passes. Der letzte Pass ist
`ba9.l10.verify_semantics`. Das ist BA9 im bereits eingefrorenen Layer L10 und
kein Beginn des nicht autorisierten Bauabschnitts BA10.

## Table Grammar

Die BA4-Grammatik verarbeitet JSON, CSV, HTML und Markdown. Sie modelliert
Multi-Header, Row-/Column-/Period-/Unit-/Scale-Achsen, transponierte und sparse
Tabellen, rowspan/colspan-Merges sowie `zero`, `dash`, `missing` und
`not_applicable`. Jede erkannte Tabelle wird registriert oder mit stabilem Code
ausgeschlossen:

```text
detected = registered + explicitly_excluded
```

Jede Zelle besitzt eine stabile ID und einen hashgebundenen Source-Locator.

## Metric Signatures

Die neun breiten Registry-Foundation-Namespaces bleiben als eingefrorene
Kompatibilität erhalten. Darüber liegt eine Research-owned Signature Authority
mit einem exakten Vertrag je aktiver Instanz:

```text
dimension + fact_kind + fact_subtype + period_role + unit + scale + currency
+ aggregation_behavior + direction_contract + comparison_contract
```

Jeder Vertrag besitzt einen eigenen Expected Contract Hash. 282 Legacy-Metric-
IDs ergeben 283 erlaubte Signaturen. Die Differenz ist ein realer, generisch
aufgelöster Legacy-Alias: derselbe alte Name wurde für Gesamtdividende und
Dividende je Aktie verwendet. Beide sind über die Semantik eindeutig, ohne
Unternehmensregel.

## Graph- und Verification-Regeln

- Unbekannte Source-IDs blockieren; es werden keine `source_reference`-Knoten
  synthetisiert.
- `source_lineage`-Zugangsnummern sind Locator-Tokens, keine Source-IDs.
- Jeder materielle Claim besitzt mindestens einen Evidence→Source→Locator-Pfad.
- Jede Numeric Binding besitzt einen vollständigen
  Claim→Fact→Evidence→Source→Locator-Pfad.
- Alternative Evidence ist nur erlaubt, wenn Metric, Wert, Source und Locator
  semantisch exakt zur Binding passen.
- Das Decision Packet wird ausschließlich aus Object-/Array-/Scalar-Nodes und
  `contains`-Edges rekonstruiert. Es existiert kein eingebettetes Legacy-Payload.
- CompileVerdictIR wird ausschließlich mit `CompileVerdictIR.derive` aus den
  gebundenen Diagnostics erzeugt.

## Risiken und Grenzen

- Der Compatibility Adapter ist sichtbar und entfernbar, aber bis zum späteren
  Source-native Cutover noch notwendig.
- Die vollständige Table Grammar erhöht Replay-Zeit und Bundle-Größe. Dies ist
  im Shadow-Modus akzeptiert; Performanceoptimierung darf Semantik oder
  Evidence nicht verkürzen.
- Die Signature Authority ist Teil von RFC-0002 und darf nach Annahme nur über
  RFC geändert werden.

## Definition of Done

- [x] Source→Verdict-Spine hashgebunden
- [x] L10 Verification und abgeleitete Verdicts
- [x] vollständige Table-Disposition
- [x] enge Signature Authority
- [x] berechnete Cross-Company-Gates
- [x] vollständige Claim-Lineage
- [x] Graph-basierter Decision-Roundtrip
- [x] finding-spezifische Red/Green/Reintroduction-Fixtures
- [x] WM/COST/ABT unverändert und ohne Cross-Company-Regression
- [x] Foundation/Registry/Authority Bundle unverändert
- [ ] unabhängiger Architektur-PASS
- [ ] BA10-Freigabe
