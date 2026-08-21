# RFC-0008 — CompilerArtifactBundle v2 Native Trust Migration

Status: `ACCEPTED_FOR_IMPLEMENTATION`

## Decision

Introduce `room16.compiler_artifact_bundle@2` with schema `2.0.0` as an
additive, native-capable successor. `CompilerArtifactBundle@1` remains frozen,
byte-identical, and canonical during this RFC implementation.

v2 has a distinct emitter and Consumer Policy, uses Research-owned Ed25519
dynamic receipts instead of a mutable per-bundle allowlist, and permits an
explicit dual-read migration window. Verification dispatch is by contract
version and may never silently fall back between versions.

## Native truth contract

`bundle_native` requires:

- `compiler_mode=source_native`;
- `source_native_fact_generation=true`;
- `legacy_semantic_input_allowed=false`;
- `authority_v3_semantic_input_allowed=false`;
- a complete native CompileRequest, SourceAcquisition, RetrievalReceiptSet and
  SourceSnapshot hash binding.

Authority-v3 is either disabled or a one-way
`bundle_to_authority_v3_only` compatibility output. It may never feed a
semantic artifact dependency.

## Migration truth contract

RFC-0008 canaries use `bundle_dual_read` and
`native_source_production=false`. They bind the accepted v1 semantic artifact
set and retain the v1 bundle only as non-authoritative migration evidence.
They do not claim native source production and do not authorize BA12.

## Trust and rotation

Research owns the signing identity. Receipts bind bundle, compile identity,
compiler identity, emitter identity, v2 policy, BA10-v1 freeze, BA11 freeze,
key ID, issuance/expiry, monotonic counter, nonce and Ed25519 signature.
Product receives only public keys and a hash-pinned key policy. Key states are
`active`, `grace_verify_only`, or `revoked`; Product never receives a signing
key or a mutable individual-bundle allowlist.

## Product migration

The v1 verifier accepts only v1. The v2 verifier accepts only v2. The additive
router dispatches by the manifest contract version and does not catch a failed
v2 verification by trying v1. No canonical Product report/server/UI surface is
switched during RFC-0008.

## Acceptance boundary

RFC-0008 stops at `ready_for_independent_rereview=true`. Independent acceptance
and freeze of the v2 contract, Consumer Policy, public key policy, Product v2
verifier, router behavior and WM/COST/ABT migration canaries are required
before `ba12_resume_authorized=true`.

Release, publication and deploy remain unauthorized.
