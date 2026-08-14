# BA3 Source Front-End

Status: implemented as semantic compiler shadow/strangler wave above Compiler
Foundation v1. BA0–BA2 remain unchanged.

## Goal

BA3 turns product resolver output, Research market capabilities, adapter
selection, retrieval receipts and immutable source snapshots into explicit L0,
L1 and L2 compiler contracts. It does not parse tables, create facts, calculate
metrics, generate claims or render reports.

## Contracts

| Layer | Pass | Output |
|---|---|---|
| L0 | `ba3.l0.freeze_compile_request` | `room16.compiler.compile_request_ir@1` |
| L1 | `ba3.l1.plan_source_acquisition` | `room16.compiler.source_acquisition_ir@1` |
| L1 | `ba3.l1.bind_retrieval_receipts` | `room16.compiler.retrieval_receipt_ir@1` |
| L2 | `ba3.l2.freeze_source_snapshot` | `room16.compiler.source_snapshot_ir@1` |

Every pass declares input, output, side effects, determinism, cache, replay,
failure, registry dependencies and non-skippability in
`source_frontend_pass_contracts.json`.

## Authority and ownership

- Product resolves WKN, ISIN, ticker or name and returns one company, listing
  and jurisdiction. Resolver evidence cannot become report evidence.
- Research validates and freezes that identity in `CompileRequestIR@1`.
- The existing Research-owned `room16.market_capability_registry@1` is consumed
  through a hash-bound BA3 adapter binding; it is not duplicated or changed.
- Foundation Registry Authority continues to define the allowed source types.
- Existing SEC, BSE, Nasdaq and Massive implementations are checked against an
  executable method contract without performing a network request.
- Product receives no new semantic registry or truth path.

## Cost and fallback policy

Provider selection is explicit. The default provider must be in the compile
request allowlist. Massive can be selected only when it is both allowed and
listed in `approved_paid_provider_ids`. There is no implicit provider fallback,
automatic paid selection, vendor fundamentals fallback or unsupported-market
analysis.

## Offline execution

The authoritative BA3 execution mode is currently offline receipt replay:

1. Existing adapters or accepted frozen archives provide staged bytes.
2. Each payload receives provider, source type, source ID, locator, timestamps,
   media type, size and SHA-256 in `RetrievalReceiptIR@1`.
3. Normal inputs must prove public availability no later than the as-of cutoff.
4. Accepted Authority-v3 canaries use a separately labelled compatibility basis;
   it is valid only for offline replay and cannot be used for a new source.
5. L2 rehashes the payload and writes it to a content-addressed path.
6. Every receipt and every artifact must have a disposition before the snapshot
   can exist.
7. Parsing cannot receive an unsnapshotted source.

Live network execution remains in the existing current runner until a later
strangler cutover. BA3 does not claim that the old runner already emits native
receipts. It provides the contract and verified offline authority boundary for
that future cutover.

## Canary policy

WM, COST and ABT are read only from the accepted candidate ZIPs. BA3 verifies
every Source Snapshot v4 byte, converts it into SourceSnapshotIR@1 twice and
requires identical hashes. The original ZIP is hashed before and after each
replay and must remain byte-identical.

## Definition of Done

BA3 is complete when:

- CompileRequestIR, SourceAcquisitionIR, RetrievalReceiptIR and SourceSnapshotIR
  are versioned, strict and hash-bound;
- SEC/BSE/Nasdaq/Massive adapter interfaces and cost policies are validated;
- unsupported markets, unknown providers, missing configuration, paid-provider
  use, look-ahead, incomplete acquisition sets and byte tamper fail closed;
- same inputs produce the same request, plan and snapshot hashes;
- Python and Node agree on canonical BA3 hashes;
- WM/COST/ABT shadow replays pass without changing their archives;
- Foundation v1 and Authority Bundle v3 remain unchanged;
- BA4 has not started.
