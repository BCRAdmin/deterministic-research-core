# Room16 BA11 — Canary Freeze v2 Design

## Vertragsziel

Vorgeschlagener Vertrag: `room16.canary_freeze@2`.

Freeze v2 ist ein append-only, hashverketteter Governance-Record. Er verhindert,
dass eine akzeptierte Baseline still überschrieben, neu etikettiert oder ohne
vollständige Review- und Approval-Evidence ersetzt wird.

## Record-Modell

```json
{
  "contract_id": "room16.canary_freeze",
  "contract_version": 2,
  "freeze_id": "<content-addressed id>",
  "canary_id": "<stable opaque id>",
  "baseline_version": "1.0.0",
  "immutable_baseline_identity": {},
  "previous_freeze_reference": null,
  "promotion_candidate": {},
  "independent_review_evidence": {},
  "operator_approval": {},
  "new_baseline_hash": "<sha256>",
  "rejected_promotion": null,
  "superseded_state": {},
  "stale_state": {},
  "created_at": "<RFC3339>",
  "freeze_sha256": "<self-hash ohne freeze_sha256>"
}
```

## Immutable Baseline Identity

Die Identität bindet als kanonisches Objekt mindestens:

- `canary_id`
- `baseline_version`
- `immutable_source_sha256`
- `foundation_lock`
- `registry_foundation_lock`
- `semantic_wave_lock`
- `artifact_abi_lock`
- `consumer_trust_lock`
- `renderer_contract_lock`
- `accepted_bundle_sha256`
- `accepted_renderer_state_sha256`
- `accepted_debt_set_sha256`
- `review_evidence_sha256`
- `operator_approval_sha256`

`new_baseline_hash` ist der SHA-256-Hash genau dieses kanonischen Objekts.

## Previous Freeze Reference

- Genesis-Import: `null` plus hashgebundenes `legacy_import_receipt`.
- Jede spätere Baseline: exakte `freeze_id`, `freeze_sha256`,
  `baseline_version` und `new_baseline_hash` des unmittelbaren Vorgängers.
- Ein übersprungener, unbekannter oder mehrfach referenzierter Vorgänger
  blockiert.
- Forks sind nicht still erlaubt. Ein absichtlicher Branch braucht einen
  eigenen Review- und Operator-Entscheidungsrecord.

## Promotion Candidate

Der Candidate bindet:

- Ausgangs-Freeze,
- Change Classification,
- vollständige Diff-Evidence,
- unveränderte oder neu versionierte Locks,
- Candidate Source/Bundle/Renderer Hashes,
- Debt Carry-Forward,
- Test- und Regressionsergebnisse,
- `release_ready=false` und `publication_allowed=false`.

Ein Candidate darf nicht als Frozen gelesen werden.

## Independent Review Evidence

Mindestens erforderlich:

- Review-Vertrags-ID und -Version,
- Reviewer-Unabhängigkeit,
- exakter Candidate- und Diff-Evidence-Hash,
- Finding-Disposition,
- Verdict `accepted`, `changes_required` oder `rejected`,
- Review-Zeitpunkt,
- Manifest- und Archivhash.

Nur `accepted` kann in `OPERATOR_APPROVAL` übergehen.

## Operator Approval

Die Approval-Evidence bindet:

- approver identity/role,
- approved Candidate Hash,
- approved Review Hash,
- Scope ausschließlich Canary-Baseline-Promotion,
- `release_go=false`,
- `publication_go=false`,
- Zeitpunkt und Approval-Record-Hash.

Ein allgemeines „PASS“ ohne Scope-Bindung ist unzureichend.

## Rejected Promotion

Eine Ablehnung erzeugt einen eigenen unveränderlichen Rejection-Record mit:

- Candidate Hash,
- Review-/Operator-Entscheidung,
- Finding-IDs und Begründung,
- `promotion_state=rejected`,
- `baseline_changed=false`.

Der bisherige Freeze bleibt aktiv. Ein abgelehnter Candidate darf weder durch
erneutes Ausführen noch durch Hashänderung automatisch promoted werden.

## Superseded State

Nach erfolgreichem Freeze einer Nachfolger-Baseline erhält der Vorgänger in
der Registry eine abgeleitete, hashgebundene Sicht `superseded`. Der
ursprüngliche Freeze-Record bleibt bytegleich und auditierbar. Der
Supersession-Record referenziert alten und neuen Freeze beidseitig.

`superseded` bedeutet historisch ersetzt, nicht ungültig oder gelöscht.

## Stale State

Staleness ist ein separater Status-Record, der einen Freeze referenziert und
Grund, beobachteten Lock, erwarteten Lock sowie Detection Evidence bindet.
Der ursprüngliche Freeze bleibt unverändert. Solange ein aktiver Stale-Record
existiert:

- `canary_pass=false`
- `promotion_allowed=false`
- `release_registry_eligible=false`

## Verbotene Operationen

- in-place Änderung eines Freeze-Records,
- Wiederverwendung einer `freeze_id`,
- Änderung von Source- oder Bundle-Hash unter gleicher Baseline-Version,
- Entfernen von Accepted Debt ohne Resolution Evidence,
- Promotion ohne unabhängige Review-Evidence,
- Promotion ohne explizite Operator-Approval,
- Rebaseline als Reaktion auf Regression,
- Ableitung von Release- oder Publication-Go aus Freeze-Status.
