# Compiler Artifact Bundle Design

## Contract role

`room16.compiler_artifact_bundle@1` is the only Research-to-Product transport
unit after BA10 cutover. It is an immutable, content-addressed envelope around
verified compiler artifacts. It is not a report, ZIP layout convention or
Product snapshot.

## Logical structure

```json
{
  "contract_id": "room16.compiler_artifact_bundle",
  "contract_version": "1.0.0",
  "bundle_id": "sha256:<canonical-manifest-hash>",
  "compiler_identity": {},
  "compile_identity": {},
  "instrument_identity": {},
  "registry_lock": {},
  "pass_manifest": {},
  "artifact_index": [],
  "compatibility_views": [],
  "consumer_capabilities": {},
  "eligibility": {},
  "extensions": {}
}
```

## Mandatory embedded metadata

- contract ID and semantic version;
- bundle ID and hash algorithm;
- compiler, Foundation, Registry Foundation and Semantic Wave versions/hashes;
- Research commit and semantic source-set/IR-schema hash;
- compile request identity, instrument identity, jurisdiction and as-of date;
- compiler mode and `source_native_fact_generation` truth;
- registry lock and pass-manifest hash/order;
- complete sorted artifact index with kind, schema version, layer, producer
  pass, content hash, byte size, media type and dependency hashes;
- L10 compile verdict and the complete diagnostic index;
- renderer and release eligibility, always derived from the compiler verdict;
- explicit compatibility state and Authority-v3 bridge mode.

## Required content-addressed artifacts

Large or independently reusable artifacts are referenced by SHA-256 and stable
artifact ID. The bundle archive may physically include them under
`artifacts/sha256/<hash>`; the manifest remains identical whether storage is
inline or external.

- source snapshot and retrieval receipt records;
- parsed payloads, table artifacts and cell mappings;
- normalized record, typed fact, metric and formula-evaluation IR;
- complete Evidence, Claim and Decision graphs;
- Verification Plan and Verification Report;
- full DiagnosticIR set and CompileVerdictIR;
- pass execution records and execution attestation;
- registry/pass/IR schema locks;
- renderer-neutral presentation input or explicitly marked legacy canonical
  report payload during the compatibility stage;
- Authority Bundle v3 compatibility view and its parity record.

## Inline versus referenced

| Data | Storage | Reason |
|---|---|---|
| Identity, locks, eligibility, artifact index | embedded | Needed before any artifact is trusted |
| Compile verdict and diagnostic summary | embedded plus full referenced record | Fail-closed intake without fetching arbitrary content |
| Small IR envelopes | either inline or referenced, policy fixed per artifact kind | Deterministic consumer behavior |
| Source bytes, tables and large graphs | content-addressed reference; may be co-packaged | Avoid manifest bloat while preserving exact lineage |
| PDF/DOCX/rendered Markdown | forbidden as compiler truth; downstream RenderedArtifactSet only | Render output is not semantic authority |
| Optional agent debate | separate non-authoritative annotation artifact | It must never alter canonical graphs or verdict |

## Artifact index record

Every artifact record contains:

- `artifact_id`, `artifact_kind`, `contract_id`, `contract_version`;
- `layer`, `producer_pass_id`, `producer_pass_version`;
- `sha256`, `byte_length`, `media_type`, `canonicalization_profile`;
- `required`, `semantic_role`, `storage_mode`, `uri`;
- sorted `dependency_hashes` and `provenance_refs`;
- `compatibility_only` and `authoritative` flags that cannot both be true for
  a legacy payload;
- optional `visibility_class` and `redaction_policy_id`, defined by Research.

## Compatibility states

1. `authority_v3_compatibility_shadow`: bundle is built from the accepted
   Authority-v3-bound shadow input; no source-native claim.
2. `bundle_dual_read`: Product verifies bundle and legacy input and records
   semantic parity; legacy remains operationally primary.
3. `bundle_primary_with_v3_view`: Product consumes only the bundle; v3 is a
   derived compatibility view inside it.
4. `bundle_native`: reserved for a future separately authorized source-native
   compiler promotion.

Unknown states block consumption.

## Renderer-neutral projection

A future `room16.compiler.render_input_ir@1` may describe section IDs, ordered
claim/decision/source references, display-token IDs, locale-ready canonical
text fragments and permitted omission rules. It may not contain an independent
calculation or free factual rewrite. Because this is a new IR, its addition is
part of the BA10 RFC; it does not modify accepted L3–L10 IR.

In the first compatibility stage, the existing Research Markdown may be
carried as `legacy_canonical_report_markdown` with its exact hash and lineage.
It must be marked `compatibility_only=true`, not presented as native compiler
projection.

## Forbidden content and behavior

- Product-owned facts, metrics, formula definitions or decision rules;
- mutable URLs without a bound snapshot hash;
- unhashed artifact references;
- ambiguous timestamps or environment paths in the semantic hash domain;
- executable scripts, renderer code, remote tracking content or fetched data;
- arbitrary LLM prose presented as canonical compiler output;
- Product quality verdicts that override or replace CompileVerdictIR;
- rendered files declared as semantic authority;
- hidden fallback from a missing bundle to an unverified legacy input.

