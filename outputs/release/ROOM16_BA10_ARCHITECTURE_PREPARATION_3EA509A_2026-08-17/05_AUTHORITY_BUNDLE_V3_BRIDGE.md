# Authority Bundle v3 Bridge

## Required direction

The target direction is:

```text
verified CompilerArtifactBundle
        -> deterministic Authority Bundle v3 Compatibility View
        -> unchanged legacy consumer
```

Authority Bundle v3 remains stable. It does not become a second compiler
authority and it does not define new bundle semantics.

## Transitional honesty

Today the accepted semantic compiler replays frozen Authority-v3-bound inputs.
The first BA10 sidecar must therefore declare
`origin_mode=authority_v3_compatibility_shadow`. It may wrap the exact v3
payload and its stronger typed semantic IR, but it must not claim that v3 was
derived source-natively from the new compiler.

Bridge states are explicit:

| State | Input | Product primary | v3 role |
|---|---|---|---|
| `authority_v3_compatibility_shadow` | frozen/current v3 plus semantic replay | existing legacy path | source-bound compatibility payload |
| `bundle_dual_read` | bundle and legacy v3 | legacy operationally | parity oracle |
| `bundle_primary_with_v3_view` | bundle | bundle | deterministic derived view |
| `bundle_native` | future source-native compile | bundle | optional derived legacy adapter |

No consumer may infer a later state from the presence of a bundle.

## Field derivation classes

### Directly derivable from typed bundle artifacts

- contract identity, ticker/instrument identity and as-of date;
- artifact names, hashes, byte lengths and required status;
- source registry and snapshot references;
- fact ledger and typed financial records;
- metric packet and formula results;
- evidence ledger/graph projections;
- claims, decision packet, validation summary and permission corridor;
- compiler diagnostics and pass/fail readiness projection.

### Compatibility-only legacy views

- concatenated `validated_context` strings;
- legacy file/directory layout and legacy artifact filenames;
- report-oriented summary fields that duplicate stronger graph/IR structures;
- legacy status labels whose only purpose is an existing consumer;
- legacy list ordering when order has no semantic meaning.

These fields are marked `compatibility_only=true` and identify the canonical
source artifact/field from which they were projected.

### Stronger typing in the new bundle

- explicit period, unit, dimension and role for formula operands;
- parsed/table/cell/normalized/fact/metric/formula graph nodes;
- claim-to-source locator lineage;
- separate semantic severity and release effect for diagnostics;
- explicit compatibility/source-native mode;
- pass, registry, IR schema and implementation locks;
- renderer and release eligibility as compiler-owned states.

## Bridge artifact

`room16.authority_v3_compatibility_view@1` contains:

- source bundle ID and source artifact hashes;
- exact target contract `room16.research_authority_bundle@3`;
- bridge implementation/version hash;
- mapping-table version;
- canonical v3 manifest and content-addressed v3 artifacts;
- per-field lineage to canonical bundle artifacts;
- byte-parity and semantic-parity results;
- diagnostic list and fail-closed verdict.

## Compatibility tests

1. **Byte parity:** when the frozen v3 payload is embedded unchanged, every
   legacy artifact and manifest byte hash must match the accepted input.
2. **Canonical semantic parity:** when a v3 view is regenerated, normalize
   only contract-declared non-semantic fields and compare all semantic fields,
   artifact hashes, identities and ordering rules.
3. **Round-trip:** bundle → v3 view → legacy consumer must yield the same
   consumer-visible semantic record as the original v3 input.
4. **Negative mapping:** removing or mutating any required source field must
   produce the designated stable diagnostic and block.
5. **Cycle guard:** a `bundle_primary_with_v3_view` bundle may not cite its own
   generated v3 view as the semantic origin. A shadow bundle must explicitly
   identify the original v3 input hash.
6. **Cross-language:** Python and JavaScript verify the same golden v3 views
   and diagnostics.

## Retirement condition

Raw Authority-v3 intake can disappear only when every Product consumer reads
the verified bundle, the bridge has passed the full frozen canary corpus, and
an explicit operator decision authorizes `bundle_primary_with_v3_view`.

