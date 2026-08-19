# Room16 BA11 — BA12 Consumer Boundary

## Erlaubte BA11-Artefakte für BA12

BA12 darf später ausschließlich verifizierte, Frozen Snapshots folgender
BA11-Artefakte konsumieren:

- `room16.canary_registry@1` Registry Snapshot,
- `room16.canary_freeze@2` Records,
- Promotion- und Rejection-Event-Ledger,
- Accepted-Debt-Ledger und Debt-Set-Hashes,
- Stale-Detection-Records,
- Change-Classification-Records,
- Compare-/Regression-Verdicts,
- versionierte Coverage Profiles,
- gebundene Foundation-, Registry-, Semantic-, ABI-, Consumer- und Renderer-
  Locks.

BA12 darf diese Artefakte nicht verändern und keine eigene Canary-Authority
aufbauen.

## Dev/Holdout Freeze

BA12 benötigt zwei getrennte Freeze-Lanes:

- `development_freeze`: alle in Entwicklung, Tuning, Fixture-Auswahl oder
  Root-Cause-Arbeit verwendeten Baselines.
- `holdout_freeze`: vor der Arbeit festgelegte, unveränderte und nicht für
  Entwicklungsentscheidungen verwendete Baselines.

Beide besitzen eigene `canary_id`, Source Hashes, Coverage Profiles und
Freeze-v2-Records. Ein Entry darf nicht gleichzeitig Development und
untouched Holdout sein.

## Coverage Profile

Ein BA12-Coverage-Profile beschreibt generisch:

- Archetype-Fähigkeiten,
- erforderliche Source- und Table-Formen,
- Metric-/Formula-/Evidence-/Claim-/Decision-Abdeckung,
- Diagnostic- und Root-Cause-Abdeckung,
- Consumer-/Renderer-Abdeckung,
- bekannte Debt- und Review-Limitationen.

Coverage wird über Fähigkeiten und Contracts, nicht über Tickerregeln,
bestimmt.

## Same-Lock Rule

Development- und Holdout-Vergleiche sind nur gültig, wenn mindestens folgende
Werte exakt identisch sind:

- Foundation Lock,
- Registry Foundation Lock,
- Semantic Wave Lock,
- IR-Schema- und Pass-Manifest-Hash,
- Artifact ABI/BA10 Freeze Lock,
- Consumer Trust Lock,
- Renderer Contract Lock,
- Source Contract Major Version.

Bei Abweichung ist der Vergleich `stale_or_incomparable`, niemals PASS.

## Untouched Holdout Rule

Ein Holdout gilt nur als untouched, wenn:

- Source Archive und Freeze vor Entwicklungsbeginn feststanden,
- kein Holdout-Artefakt zur Regel-, Fixture-, Prompt-, Registry- oder
  Schwellenwertauswahl genutzt wurde,
- keine Mutation oder Rebuild des Source Archives stattfand,
- Zugriff und Ausführung in einem Audit Ledger erfasst sind,
- der erste Ergebnis-Hash vor der Sichtung unveränderlich gespeichert wird.

ServiceNow/NOW ist im aktuellen Room16-Bestand bereits historisch exponiert
und daher kein ehrlicher untouched Holdout. BA12 muss einen echten Holdout
wählen oder NOW ausdrücklich als exponierten Regression Case klassifizieren.

## No-Company-Patch Rule

BA12 darf keine Unternehmenssonderregel einführen. Verboten sind insbesondere:

- Ticker- oder Company-Name-Verzweigungen,
- canary-spezifische Registry-Namespaces,
- company-spezifische Parser-/Metric-/Formula-/Claim-/Decision-Ausnahmen,
- Holdout-spezifische Expected-Value-Patches,
- Renderer-Sonderfälle zur kosmetischen PASS-Erzeugung.

Ein generischer Code-/Config-Scan und semantischer Registry-Audit müssen
`company_specific_patch_count=0` belegen.

## Nicht erlaubte BA12-Ableitungen

BA12 darf aus BA11-Artefakten nicht ableiten:

- Release-Go,
- Publication-Go,
- rechtliche oder redaktionelle Freigabe,
- automatische Rebaseline,
- Archetype-Implementierung ohne separates Operator-Go.

Diese Vorbereitung implementiert noch keinen Archetype und autorisiert BA12
nicht.
