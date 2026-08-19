# Room16 BA11 — Definition of Done

BA11 gilt erst als implementiert und acceptance-ready, wenn alle folgenden
Bedingungen erfüllt sind. Dieses Dokument selbst erfüllt oder autorisiert
diese Bedingungen nicht.

## Contracts

- `room16.canary_registry@1` ist schema-, canonicalization- und hashverifiziert.
- `room16.canary_freeze@2` ist append-only und hashverkettet.
- Promotion-, Rejection-, Supersession-, Stale- und Debt-Records sind
  maschinenlesbar und versioniert.
- Research ist alleiniger Owner; Product besitzt nur einen verifizierten
  Read-only-Mirror.

## Genesis Migration

- WM, COST und ABT sind als generische Genesis-Entries importiert.
- Kein `canary_id` steuert über Ticker- oder Unternehmenslogik.
- Alle bestehenden Source-, Bundle-, Renderer-, Stage-A-, Semantic- und BA10-
  Hashes bleiben exakt unverändert.
- `RC1FE5-015` und `RC1FE5-016` sind korrekt vorwärtsgebunden.
- Der Genesis-Import ist ausdrücklich keine Promotion und kein Rebaseline.

## Governance

- Lifecycle `DEVELOPMENT → SHADOW → CANDIDATE → INDEPENDENT_REVIEW →
  OPERATOR_APPROVAL → PROMOTED → FROZEN` ist fail-closed umgesetzt.
- Regression kann niemals automatisch rebaselinen.
- Breaking Changes brauchen RFC, Versionierung, Rereview und Operator-Go.
- Stale blockiert vor Compare und kann nicht als PASS erscheinen.
- Accepted Debt kann nur mit gültiger Resolution Evidence verschwinden.
- Freeze- und Promotion-Historie bleibt vollständig auditierbar.

## Tests und Evidence

- Alle Fälle `BA11-T001` bis `BA11-T022` bestehen.
- Negative Fixtures liefern die zugesagten stabilen Diagnostic Codes.
- WM/COST/ABT Real-Instance-Regression ist vollständig und ungeskippt PASS.
- Foundation-, Registry-, Semantic- und BA10-Freeze-Verifier bleiben PASS.
- Zweiter deterministischer Evidence-Build ist byteidentisch.
- Evidence-Paket enthält vollständige Git-/Blob-/Manifest-/Test-/Hash-
  Nachweise und eine Reproduktionsanweisung.

## Unveränderte Frozen Grenzen

- Keine Änderung an BA0–BA9.
- Keine Änderung an BA10.
- Keine Änderung an Foundation `1.0.0`.
- Keine Änderung an Registry Foundation `1.1.0`.
- Kein Breaking Change an `room16.compiler_artifact_bundle@1` oder Schema
  `1.2.0`.
- Kein Breaking Change an Authority Bundle v3.
- Keine Änderung der akzeptierten WM-/COST-/ABT-Source-Archive.
- Keine ticker-spezifische Governance.

Wenn BA11 eine dieser Grenzen erfordern sollte, lautet der Implementierungs-
Verdict `BA11_BLOCKED` und die Arbeit stoppt.

## Release-Grenzen

- `release_ready=false`
- `publication_allowed=false`
- `ba12_authorized=false`
- kein Public-, Legal-, Editorial-, Paid- oder Member-Go

## Acceptance

- Unabhängiger Review des exakten BA11-Evidence-Hashes ist bestanden.
- Operator hat exakt diesen Candidate zur BA11-Freeze-Operation autorisiert.
- Erst danach darf ein eigener BA11-Freeze-Record oder Tag entstehen.

## Aktueller Status

`architecture_prepared=true`, `implementation_started=false`,
`ba11_authorized=false`.
