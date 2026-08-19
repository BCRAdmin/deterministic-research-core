# Room16 BA11 — Release Registry Boundary

## Systemgrenze

```text
Compiler
  → CompilerArtifactBundle
  → Canary Registry
  → Release Registry
  → Human / Legal / Editorial / Public / Paid Gates
```

Jede Stufe konsumiert ausschließlich verifizierte Outputs der vorherigen
Stufe und besitzt eine engere, eigene Authority. Keine frühere Stufe darf
Statusfelder einer späteren Stufe prägen.

## Compiler

Authority:

- Sources, Parsing, Facts, Metrics, Formulae, Evidence, Claims, Decisions,
  Diagnostics und Compile Verdict.

Nicht autorisiert:

- Canary-Promotion,
- Release-Go,
- Publication-Go,
- Paid-/Member-Aktivierung.

## CompilerArtifactBundle

Authority:

- unveränderliche, hashgebundene Übergabe der Compiler-Wahrheit,
- Capability- und Consumer-Trust-Prüfung,
- Renderer-No-New-Truth-Grenze.

Nicht autorisiert:

- neue Facts/Claims/Decisions im Consumer,
- Canary-Rebaseline,
- Release- oder Publication-Go.

## Canary Registry

Authority:

- technische Baseline-Identität,
- Compare- und Regressionsevidenz,
- Stale Detection,
- Accepted-Debt-Carry-Forward,
- Promotion- und Freeze-Historie.

Ein Canary-PASS bedeutet ausschließlich:

> Der geprüfte Candidate entspricht dem definierten Canary-Vertrag unter den
> gebundenen Locks und überschreitet keine akzeptierte Governance-Grenze.

Er bedeutet ausdrücklich nicht:

- `release_ready=true`,
- `publication_allowed=true`,
- rechtliche, redaktionelle oder öffentliche Freigabe,
- Eignung für Verkauf, Membership oder Financial Advice.

## Release Registry

Die spätere Release Registry konsumiert nur:

- Frozen Canary Registry Snapshot,
- vollständige Canary-PASS-Matrix,
- Stale-Status `clear`,
- Release-Candidate-Manifest und Artefakthashes,
- technische Release-Gates,
- offene Debt-/Risk-/Review-Limitationen.

Sie besitzt eine getrennte technische Release-Candidate-Entscheidung. Selbst
ein technisches Release-Registry-PASS darf `publication_allowed` nicht setzen.
Ein künftiges `release_ready=true` braucht einen eigenen expliziten
Release-Approval-Contract und liegt außerhalb BA11.

## Human, Legal, Editorial, Public und Paid Gates

- Human Review: fachliche unabhängige Prüfung des exakten Artefakts.
- Legal: Betreiber-, Disclaimer-, Copyright-, Datenschutz- und
  Financial-Information-Scope.
- Editorial: sichtbare Sprache, Kontext, Quellen und Darstellungsqualität.
- Public: ausdrückliche Sichtbarkeits- und Publikationsentscheidung.
- Paid/Member: getrennte Produkt-, Commerce-, Entitlement- und Support-Gates.

Diese Gates sind nicht aus Canary- oder Release-Status ableitbar.

## Status-Invarianten für BA11

Jeder BA11-Registry-, Compare-, Promotion- und Freeze-Record muss enthalten:

```json
{
  "release_ready": false,
  "publication_allowed": false,
  "release_go_granted": false,
  "public_go_granted": false
}
```

Ein Input, der diese Grenzen verletzt, blockiert fail-closed.

## BA11-Scope

BA11 ist Release Control Preparation, aber kein Release-Go. Es entwirft die
Canary-Seite der Kontrollgrenze; eine Release Registry selbst, Public-Promotion
oder Paid-Aktivierung wird nicht implementiert oder autorisiert.
