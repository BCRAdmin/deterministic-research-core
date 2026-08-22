# RFC-0007 — BA12 Final Strangler Cutover

Status: `STOPPED — RFC0008_NATIVE_IDENTITY_TRUST_LOCK_CONFLICT`

Date: `2026-08-22`

## 2026-08-22 resume result

RFC-0008 was independently accepted and formally frozen at
`27636f891457a98a790702f8fbba19763e0a8b363978c205c9eca54361a84fb0`.
The authorized BA12 resume then reached a new frozen-boundary conflict during
the first truthful native Bundle@2 probe.

The strict Bundle@2 model accepts the required native state:

```text
compiler_identity.semantic_artifact_origin=source_native
mode=bundle_native
compiler_mode=source_native
source_native_fact_generation=true
native_source_production=true
```

The frozen RFC-0008 Consumer Policy and both frozen Research/Product schema
profiles instead pin:

```text
compiler_identity.semantic_artifact_origin=frozen_v1_migration
```

Both production verifiers require exact equality with that compiler-identity
lock. The truthful native probe therefore fails with
`RFC8_TRUST_POLICY_MISMATCH` before artifact or receipt verification. Claiming
`frozen_v1_migration` for newly generated native semantics would make the
bundle identity untruthful and is not an allowed workaround.

This triggers BA12 Stop Conditions 2, 6, 7 and 8. No frozen policy, schema,
verifier, BA10 or BA11 file was changed. Product was not changed. BA12 was not
self-accepted or frozen, and release/publication/deploy remain false.

Machine evidence:
`docs/compiler_foundation/rfcs/BA12_R2_NATIVE_TRUST_CONFLICT_STOP.json`.

Required follow-up: an independently accepted policy generation or successor
trust root must define and sign a source-native `CompilerIdentityV2` lock while
retaining the existing migration boundary unchanged.

## Decision

The BA12 implementation cannot begin under the currently frozen BA0–BA11
contract set. The required source-native path and full Product renderer cutover
would require a new accepted trust contract above, or a formally approved
revision to, the frozen BA10 consumer boundary.

No frozen contract, hash rule, Registry meaning, CompilerArtifactBundle ABI,
BA10 consumer rule, or BA11 governance semantic was changed.

## Required BA12 end state

The authorized BA12 handoff requires all of the following:

- live acquisition freezes bytes under the native BA3 contracts before parsing;
- BA4–BA9 consume only `SourceSnapshotIR`, never Authority-v3 or legacy fact,
  claim, decision, rating, or report objects;
- BA10 emits a `CompilerArtifactBundle` from the native semantic state;
- Product accepts the Research-issued native bundle and renders every canonical
  report/read surface without legacy truth fallback;
- Authority-v3 survives only as an output-side compatibility view.

## Frozen-boundary conflict

The accepted BA10 boundary currently makes the opposite migration state part of
its verified identity:

1. `research_agent/productization/contracts.py` fixes
   `compiler_mode="compatibility_shadow"`,
   `source_native_fact_generation=False`, and `renderer_cutover=False`.
2. `research_agent/productization/artifact_bundle.py` requires an immutable
   Authority-v3 archive and executes `replay_rfc_0004_archive`; it rejects any
   result whose compiler mode is not `compatibility_shadow`.
3. `research_agent/semantic_compiler/semantic_wave/legacy_replay.py` reads the
   Authority-v3 fact ledger, evidence ledger, analyst claims, decision packet,
   and source registry as semantic inputs.
4. The frozen Research consumer policy pins the BA10 emitter implementation,
   schema, Compatibility-Shadow state, `source_native_fact_generation=false`,
   `full_renderer_cutover=false`, and `renderer_cutover=false`.
5. Product mirrors that exact policy hash and rejects any bundle whose emitter,
   semantic-wave identity, compatibility mode, or migration gates differ.
6. Product accepts only the three Research-issued, hash-pinned WM/COST/ABT
   receipts in the frozen receipt set. A new live native bundle therefore has
   no valid trust path through the frozen Product consumer.

Changing these facts would change the frozen BA10 ABI/consumer boundary.
Bypassing them in an additive BA12 wrapper would create an unapproved parallel
trust path and would not satisfy the required end-to-end authority cutover.

## Triggered contract clauses

- Frozen-boundary rule: BA12 must stop if it requires changing the
  CompilerArtifactBundle ABI or BA10 consumer boundary.
- Stop Condition 2: a frozen BA0–BA11 contract must be changed.
- Stop Condition 5: the canonical native pipeline still requires
  Authority-v3/legacy semantic input.
- Stop Condition 6: canonical Product report surfaces still require legacy
  semantic truth or a frozen receipt set that cannot authorize live native
  bundles.

## Required follow-up authority

An independent RFC decision must define one accepted migration mechanism:

1. a BA10 successor ABI/consumer-policy major version that explicitly supports
   source-native compilation and BA12 renderer cutover; or
2. a Research-owned, independently accepted BA12 trust envelope that can issue
   live native bundle receipts and that Product can verify without weakening or
   impersonating the frozen BA10 emitter identity.

That RFC must also define compatibility and rollback rules, receipt rotation,
Product mirror update semantics, canary migration, and the exact independent
acceptance/freeze sequence. Until then, BA10 and BA11 remain valid and frozen,
BA12 is not implementation-ready, and release/publication/deploy remain false.

## Current result

```text
ready_for_independent_rereview=false
ba12_implementation_ready=false
ba12_frozen=false
release_ready_candidate=false
release_ready=false
release_authorized=false
publication_authorized=false
deploy_authorized=false
stop_condition=FROZEN_BA10_CONSUMER_BOUNDARY_RFC_REQUIRED
```
