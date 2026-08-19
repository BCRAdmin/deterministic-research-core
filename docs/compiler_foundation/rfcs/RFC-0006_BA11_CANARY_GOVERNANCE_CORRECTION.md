# RFC-0006 — BA11 Canary Governance R1 Correction

Status: implemented correction candidate; independent rereview required.

## Scope

RFC-0006 adds a Research-owned canary-governance layer above the frozen BA0–BA10 stack.
It does not modify compiler, semantic-wave, Artifact ABI, Authority-v3, renderer, release,
publication, or BA12 authority.

## Authority and identity

- Research owns technical baselines, registry events, snapshots, freezes, and debt records.
- Product consumes only byte-identical, hash-verified registry snapshots.
- A Product mirror defect yields `BA11_CONSUMER_MIRROR_INVALID`; it never changes Research state.
- Technical baseline, governance envelope, and immutable freeze are separate identities.
- `room16.canary_freeze@1` is the first contract; no fictional predecessor exists.

## Contracts and canonicalization

The generated catalog under `research_agent/canary_governance/schemas/` is normative.
All contracts reject unknown fields, use `room16.canonical_json@1`, SHA-256, explicit
authority ownership, and stable diagnostics. Source Contract Lock is mandatory.

## State and storage

The append-only Registry Event Ledger is authority. Registry snapshots are deterministic
folds with ordered entries, generation, previous snapshot, and ledger head. Research stores
immutable objects content-addressed and publishes only one `heads/current.json` pointer under
an exclusive lock using compare-and-swap plus atomic rename. A stale writer fails closed.

Normative Research layout:

```text
objects/sha256/<sha256>.json
ledger/events/<sequence>-<event_id>.json
snapshots/<snapshot_sha256>.json
heads/current.json
receipts/<receipt_sha256>.json
```

Normative Product mirror layout:

```text
room16-app/config/canary_registry_mirror/snapshot.json
room16-app/config/canary_registry_mirror/mirror_receipt.json
```

Product must not generate or promote Research truth.

## Approvals

Operator approvals use detached Ed25519 signatures over canonical bytes and bind scope,
subject IDs and hashes, R1 finding-set hash, previous registry head, role, Key ID, nonce,
monotonic counter, issuance, and optional expiry. Trusted-key rotation and revocation are
external operator-controlled inputs. Replay, wrong key, wrong scope, expiry, revocation, or
signature tamper fail closed.

## Debt

Accepted Debt is an append-only event chain. Membership is a separate per-freeze record;
resolution is a separate record. No event is edited or deleted, and current state is replayed.

## Time and archive

Business time is an injected attestation input. Tests use FixedClock. Evidence ZIPs use
lexicographic member order, fixed `SOURCE_DATE_EPOCH`, regular-file mode `0644`, safe relative
paths, and a manifest that explicitly excludes itself. Identical inputs produce identical bytes.

## Change classes and renderer boundary

Semantic/no-new-truth lock, Presentation Contract, and renderer implementation/artifact are
separate. Presentation-only implementation changes are Ordinary only when independent compare
finds zero Fact, Claim, Decision, and Lineage differences and source/semantic locks are unchanged.

The canary type is `technical_release_regression`; `release_candidate` is forbidden because BA11
has no release authority.

## Verification and gate

All BA11 R1 findings `BA11-AR-001` through `BA11-AR-018` require individual Contract Delta,
changed-file, test, negative-fixture, and Evidence references. Full Research and Product
regressions plus the raw BA10 freeze verifier must pass.

Even after successful local correction:

```text
ba11_implementation_ready=false
ba12_authorized=false
release_authorized=false
publication_authorized=false
next_gate=corrected_ba11_architecture_r1_and_independent_rereview
```

## R3 correction after independent R2 rereview

R3 addresses the 14 independent RR2 findings without expanding BA11 authority:

- Product verifies a mirror only against a pinned Research Ed25519 trust policy and a signed
  Research authority receipt. Callers cannot supply an expected Research hash.
- Approval and independent-review signatures have separate verification paths, role/key
  independence, exact decision/scope/subject/finding/head bindings, expiry/revocation checks,
  and transaction-atomic nonce/counter consumption.
- The identity graph is acyclic: a Freeze does not reference the current Registry Snapshot;
  Registry events and entries reference the Freeze, and the transaction/commit receipt binds
  the resulting Snapshot.
- Registry and Debt ledgers persist content-addressed events plus CAS-published head records.
  Expected head and length prevent valid-prefix rollback, truncation, branch, merge, reorder,
  and debt reopen attacks.
- `RegistryStore.commit_transaction` validates the complete governance object graph, writes
  immutable objects and a prepared receipt, performs exactly one atomic current-head swap,
  then read-backs and emits an idempotently recoverable commit receipt.
- Registry Snapshots are normative projections of the exact bound ledger. Arbitrary entries,
  mismatched entry identities, and mismatched ledger heads fail closed.
- `ComparisonResult` and `ChangeClassification` cross-bind counts and locks. Ordinary change
  requires zero Fact, Claim, Decision, and Lineage differences.
- Source Contract bindings use typed SHA-256 values and a unique sorted ID/hash bijection.
  Canary IDs use normative Unicode normalization with a collision gate; SemVer follows the
  validated Change Class; Genesis import has a one-time persisted CAS head.
- Evidence collection and closure verification are separate programs. The collector cannot
  write verdict or closure files. The verifier derives closure only after exact finding/test
  resolution, command-receipt validation, finding-specific file/hash validation, and evidence
  reference resolution.
- Regression receipts bind the complete tracked repository tree, full worktree state, tool
  versions, raw and normalized output hashes, and relative paths. EvidenceManifest and detached
  Package Identity have distinct, machine-readable hash domains.

R3 remains a correction candidate only:

```text
ready_for_independent_rereview=true
ba11_implementation_ready=false
ba12_authorized=false
release_authorized=false
publication_authorized=false
```
