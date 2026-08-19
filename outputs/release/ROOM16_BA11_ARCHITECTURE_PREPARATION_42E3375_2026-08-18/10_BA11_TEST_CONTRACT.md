# Room16 BA11 — Test Contract

## Testprinzipien

- Jeder Negativtest muss mit einem stabilen Diagnostic Code blockieren.
- Fixtures sind ticker-neutral; WM/COST/ABT dienen nur der unveränderten
  Genesis-Baseline-Regression.
- Kein Test darf eine Frozen Baseline neu schreiben.
- Jeder PASS bindet Locks, Hashes, Debt, Review-State und negative Release-
  Grenzen.

## Pflichtfälle

| ID | Fall | Mutation/Aktion | Erwartung |
|---|---|---|---|
| `BA11-T001` | Freeze Immutability | Feld eines bestehenden Freeze-v2-Records ändern und neu hashen | blockiert: `CANARY_FREEZE_IMMUTABLE` |
| `BA11-T002` | Unauthorized Rebaseline | neuen Baseline-Hash ohne Review/Operator-Approval eintragen | blockiert: `CANARY_REBASELINE_UNAUTHORIZED` |
| `BA11-T003` | Accepted-Debt Disappearance | einen aktiven Debt Entry ohne Resolution Evidence entfernen | blockiert: `CANARY_ACCEPTED_DEBT_DISAPPEARED` |
| `BA11-T004` | Ordinary Auto-Compare | semantikfreie Änderung bei identischen Locks und Outputs | automatischer Compare PASS; aktive Baseline unverändert |
| `BA11-T005` | Breaking Fail-Closed | eingefrorene Semantic-/ABI-Fläche ändern | blockiert: `CANARY_BREAKING_CHANGE_RFC_REQUIRED` |
| `BA11-T006` | Stale Detection | gebundenen Registry-/Consumer-/Renderer-Lock ändern | `stale_blocked`; niemals PASS |
| `BA11-T007` | Rejected Promotion | Candidate im Review oder durch Operator ablehnen | Rejection-Record; aktive Baseline unverändert |
| `BA11-T008` | Superseded Freeze | gültige Nachfolger-Baseline vollständig freigeben | alter Freeze bleibt bytegleich; beidseitiger Supersession-Record |
| `BA11-T009` | Wrong Semantic Lock | Candidate mit falschem Semantic-Wave-Lock | blockiert: `CANARY_SEMANTIC_LOCK_MISMATCH` |
| `BA11-T010` | Wrong Artifact ABI Lock | Candidate mit falschem BA10-/ABI-Lock | blockiert: `CANARY_ARTIFACT_ABI_LOCK_MISMATCH` |
| `BA11-T011` | Canary Source Tamper | ein Byte im Source Archive ändern | blockiert: `CANARY_SOURCE_TAMPER` |
| `BA11-T012` | WM/COST/ABT Unchanged | Genesis-Import und Compare aus bestehenden Records | alle Source-, Bundle- und Renderer-Hashes exakt unverändert |

## Zusätzliche Architekturtests

| ID | Fall | Erwartung |
|---|---|---|
| `BA11-T013` | Missing Freeze Record | Frozen Entry blockiert als `CANARY_FREEZE_RECORD_MISSING` |
| `BA11-T014` | Debt Resolution Forgery | ungültige Resolution Evidence blockiert |
| `BA11-T015` | Product Mirror Mutation | Product-geprägter Registry Hash blockiert als Authority-Verstoß |
| `BA11-T016` | Ticker-Specific Governance | Regel/Namespace mit Unternehmensbezug blockiert |
| `BA11-T017` | Canary PASS Release Smuggling | `release_ready=true` oder `publication_allowed=true` blockiert |
| `BA11-T018` | Forked Freeze Chain | zwei ungeklärte Nachfolger desselben Freeze blockieren |
| `BA11-T019` | Unknown Change Class | Candidate blockiert statt Default auf Ordinary |
| `BA11-T020` | Renderer New Truth | Facts/Claims/Decisions > 0 blockieren |
| `BA11-T021` | Holdout Same-Lock Violation | für BA12 als `stale_or_incomparable` blockiert |
| `BA11-T022` | No Automatic Golden Update | Regression verändert Registry-/Freeze-Dateien nicht |

## WM/COST/ABT Unchanged Acceptance Oracle

`BA11-T012` muss exakt prüfen:

- Source Archives:
  - WM `a6b6d15ad7004573a56ad057884563cfbeeb2c3162dae0641a1b361b5e416d72`
  - COST `b97e6024855c7a772713ff9af4889987e4a9a8e5a3afca0d56a42a1ba8092ea4`
  - ABT `0926d3cafd312556ec267b2b25214d255ff9352daed77a01b7852addbb48dc45`
- Artifact Bundles:
  - WM `71bc2f1dae367ecfe83f8f84f7a5d4eceffca07954709f2ea4d3caab655ff339`
  - COST `2c6a35f23011faa7ef1b6f1a401fb184d2b0f602766836df05a6ba66f94bbdd4`
  - ABT `48a39cf7537d4ed1f807d3a532173847192d6bfe805cd12fd3f5842b8d26383a`
- Renderer Acceptance für alle drei `true` und No-New-Truth `true`.
- Semantic-Wave-Lock und BA10-Freeze-Lock exakt unverändert.
- Stage-A- und BA10-Research-/Product-Baselines unverändert.
- Accepted Debt `RC1FE5-015` sowie Limitation `RC1FE5-016` sichtbar.
- `release_ready=false`, `publication_allowed=false`.

## Testebenen

1. Schema-/Canonicalization-Unit-Tests.
2. Contract-Fixtures mit vollständigem Rehash.
3. Freeze-/Promotion-State-Machine-Tests.
4. Cross-Repository Authority- und Mirror-Tests.
5. Reale unveränderte WM/COST/ABT-Instance-Tests.
6. Full Regression, Freeze-Verifier und Reproducible Package Build.

Eine Teilmenge oder geskipptes Real-Instance-Gate reicht für BA11-Abnahme
nicht aus.
