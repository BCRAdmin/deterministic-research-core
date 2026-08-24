# RFC-0010 — BA12 Live Capture Transport

Status: `ACCEPTED_FOR_IMPLEMENTATION`

## Decision

RFC-0010 adds a Research-owned live-capture transport before the frozen BA3
compiler boundary. It does not modify, extend, version-bump or reinterpret
`RetrievalReceiptIR@1`, `SourceSnapshotIR@1`, the 91-schema Semantic Compiler
Wave, or the RFC-0009 native trust contracts.

The two truthful stages are:

```text
Stage A — live network acquisition
provider adapter
-> LiveRetrievalReceipt@1 (transport=live_acquisition)
-> immutable content-addressed capture bytes

Stage B — frozen BA3 compiler ingress
immutable capture bytes
-> RetrievalReceiptIR@1 (transport=offline_replay)
-> SourceSnapshotIR@1
-> frozen BA4–BA9 semantic wave
```

The BA3 receipt describes the immediate replay from immutable capture storage.
The upstream live receipt separately and truthfully records the network URL,
fetch time, provider status, provider identity, adapter identity and actual
variable cost.

## Additive machine contracts

- `room16.ba12.live_retrieval_receipt@1`
- `room16.ba12.live_capture_artifact@1`
- `room16.ba12.live_capture_binding@1`
- `room16.ba12.live_capture_set@1`
- `room16.ba12.live_attempt_record@1`
- `room16.ba12.live_run_closure@1`

All six contracts use strict unknown-field rejection, canonical JSON,
domain-separated SHA-256 self-hashes and deterministic sorted collections.

## Stage A invariants

Before any parser or semantic consumer can receive provider bytes, the live
executor must:

1. verify the planned provider, adapter and source type;
2. normalize the raw provider status and reject every non-success outcome;
3. enforce the frozen provider allowlist and explicit paid-provider approval;
4. persist a self-hashed `prepared_capture` attempt with complete response
   provenance and the expected payload hash;
5. hash and atomically persist the raw bytes under their content hash;
6. fsync and read back the stored object;
7. reject truncation, path escape, symlink escape and mutable replacement;
8. issue exactly one authoritative receipt and terminal attempt record per
   request/acquisition/attempt.

Identical concurrent writes may converge. Conflicting receipts or bytes for the
same attempt fail closed. A retry uses a distinct attempt identity and never
overwrites the prior attempt.

HTTP-backed responses accept only the 2xx family. Bare redirects, auth errors,
rate limits, not-found responses and provider errors persist a terminal failed
attempt with a stable classification; their bodies never become source
evidence. Provider-specific successful statuses (for example Massive `OK` or
`DELAYED`) are normalized before receipt issuance. Both the raw status and
normalized `success` outcome are hash-bound in the live receipt.

## Durable recovery

The attempt journal is append-only/CAS-safe. A process restart can load a
terminal successful attempt, its live receipt and capture artifact using only
persisted objects. If a crash occurs after `prepared_capture`, the payload is
reloaded and verified by its content hash before the same attempt is finalized.
A content-addressed byte object without a prepared attempt record is an orphan
cache object and cannot be guessed into authority; retry requires a new attempt
identity.

Bindings, capture sets, exact frozen BA3 snapshots and final run closures are
stored as content-addressed authority objects. A fresh process revalidates all
self-hashes and cross-stage hash links before it may replay or report native
eligibility.

## Frozen BA3 bridge

The bridge reads only a verified capture artifact. It constructs the existing
`OfflineSourceInput` and invokes the unchanged BA3 offline staging path with:

- `transport=offline_replay`;
- `original_locator=room16-capture://sha256/<payload_sha256>`;
- equal acquisition, provider, source, media type, payload hash and byte count;
- equal availability/publication/filing time where applicable;
- a distinct deterministic capture-to-compiler `retrieved_at` time;
- `variable_cost_incurred=false` for the replay stage.

The external URL and network fetch timestamp remain only in the live receipt.
`LiveCaptureBinding@1` closes over the live receipt, capture artifact, BA3
receipt and final `SourceSnapshotIR@1` hash.

## Run closure

`LiveCaptureSet@1` exactly covers the expected acquisition IDs. Every expected
item has one terminal state. A successful eligible run uses `captured_bound`;
a failed run may retain a successful but unbound receipt as
`captured_unbound`, while failed planned items use `failed_required`. Missing,
duplicate or unexpected acquisitions block. Every frozen BA3 acquisition is
required, so RFC-0010 rejects manufactured optionality and any failed required
acquisition makes the set ineligible for native compile.

The integration harness executes the existing public SEC, Nasdaq, BSE and
Massive adapter methods with injected deterministic transports. Their real
dict/text/data-frame result shapes and raised errors are normalized at the
RFC-0010 boundary without changing production adapter contracts or requiring
credentials/network access.

## Time, cost and authority

Public availability and publication timestamps must not exceed the frozen
compile as-of cutoff. Providers must be explicitly allowed; possible-cost
providers require explicit approval. Actual live cost is recorded upstream,
while BA3 replay remains zero-variable-cost.

The live layer owns acquisition provenance only. It cannot create Facts,
Metrics, Claims, Decisions, Ratings or Product truth. Semantic authority starts
after the unchanged Source Snapshot enters frozen BA4–BA9.

## Current authorization state

```text
ready_for_independent_rereview=true
rfc0010_implementation_ready=false
rfc0010_frozen=false
ba12_resume_authorized=false
ba12_implementation_ready=false
release_authorized=false
publication_authorized=false
deploy_authorized=false
```

RFC-0010 must pass independent acceptance and a separate freeze before BA12 may
resume. This implementation task performs no BA12 canonical cutover and no
Product runtime change.
