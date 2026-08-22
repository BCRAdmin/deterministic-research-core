# RFC-0009 — BA12 Native Trust Epoch 2

Status: `ACCEPTED_FOR_IMPLEMENTATION`

## Decision

RFC-0008 remains byte-identical and frozen. Its Research-owned Ed25519 trust
root remains the only Bundle@2 bootstrap root. RFC-0009 adds a root-signed
Consumer Policy Generation 2 for truthful `source_native` bundles.

```text
RFC-0008 root
├── Consumer Policy Generation 1 -> frozen_v1_migration
└── Consumer Policy Generation 2 -> source_native
```

Generation 2 is chained to the exact Generation-1 envelope hash. It changes
only the semantic origin, the hash-pinned native manifest profile, and the
trusted emitter identity. Foundation, Registry Foundation, Semantic Wave,
BA10, BA11, Bundle major, canonicalization, key policy, release, publication,
and deploy locks remain unchanged.

## Native trust profile

The native profile preserves the strict Bundle@2 field model and pins:

- `semantic_artifact_origin=source_native`;
- `emitter_id=room16.compiler_artifact_bundle_builder_v2_native`;
- `emitter_version=2.1.0-ba12`;
- `producer_pass_id=ba12.l11.emit_native_bundle_v2`;
- `mode=bundle_native` and `compiler_mode=source_native`;
- native source flags true and all legacy semantic input flags false;
- release, publication, and deploy false.

The existing leaf receipt key policy is reused byte-identically.

## Product boundary

Product receives additive, byte-exact mirrors of the Generation-2 envelope
and native profile. A new native verifier loads only fixed configuration
paths, verifies the full Gen1→Gen2 root-signed chain, and verifies the unchanged
leaf-key policy and signed receipt. A successor router dispatches from immutable
manifest semantics. It never retries a weaker verifier after failure.

RFC-0009 does not switch any canonical Product report or UI route.

## Gate status

Until an independent rereview accepts and freezes this implementation:

```text
ready_for_independent_rereview=true
rfc0009_implementation_ready=false
rfc0009_frozen=false
ba12_resume_authorized=false
ba12_implementation_ready=false
release_authorized=false
publication_authorized=false
deploy_authorized=false
```
