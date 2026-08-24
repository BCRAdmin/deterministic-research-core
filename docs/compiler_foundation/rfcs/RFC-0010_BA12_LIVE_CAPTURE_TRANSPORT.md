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

All four contracts use strict unknown-field rejection, canonical JSON,
domain-separated SHA-256 self-hashes and deterministic sorted collections.

## Stage A invariants

Before any parser or semantic consumer can receive provider bytes, the live
executor must:

1. verify the planned provider, adapter and source type;
2. enforce the frozen provider allowlist and explicit paid-provider approval;
3. hash and atomically persist the raw bytes under their content hash;
4. fsync and read back the stored object;
5. reject truncation, path escape, symlink escape and mutable replacement;
6. issue exactly one authoritative receipt per request/acquisition/attempt.

Identical concurrent writes may converge. Conflicting receipts or bytes for the
same attempt fail closed. A retry uses a distinct attempt identity and never
overwrites the prior attempt.

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
item has one terminal state: `captured_bound`, `failed_required`, or
`failed_optional_dispositioned`. Missing, duplicate or unexpected acquisitions
block. Any failed required acquisition makes the set ineligible for native
compile.

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
