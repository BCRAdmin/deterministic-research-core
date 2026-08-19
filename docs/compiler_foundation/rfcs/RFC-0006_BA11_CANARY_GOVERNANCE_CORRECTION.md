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
