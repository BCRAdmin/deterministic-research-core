# RFC-0007 — BA12 Final Strangler Cutover

Status: `ACCEPTED / FROZEN`

Date: `2026-08-25`

## 2026-08-25 whole-system acceptance and freeze

The external independent R5 verdict is `ACCEPTED` with zero blocking findings.
The accepted Research implementation/evidence identities are
`a92c6d9dcaf9a53f5e20a92898d0c9983b9e35de` and
`ab06096f04573df6e1ddf6913ff864d6f796c208`; the accepted Product identity is
`ed86bb841aab88d878266cf8ed498eabc6fa9029`.

All 30 whole-system freeze rows, the R5 33-row matrix, R4 50-row BA12 matrix,
RFC-0010 14-row delta matrix, full regressions, prior freezes, dependency
audits and Boundary Gate v2 are required to remain PASS. The freeze changes no
accepted Product runtime/source/config and no accepted BA12 Research runtime,
compiler or live-source implementation.

```text
ready_for_independent_rereview=false
ba12_independent_rereview=ACCEPTED
ba12_implementation_ready=true
ba12_frozen=true
ba0_ba12_rebuild_complete=true
release_ready_candidate=false
release_ready=true
release_authorized=false
publication_authorized=false
deploy_authorized=false
commerce_authorized=false
stop_condition=none
```

The architectural roadmap is closed at BA12. Future operational activation
requires separate explicit authorization; future architectural changes require
a new change/RFC decision.

## 2026-08-25 R5 Product runtime activation closure

The independent R4 rereview retained the Research live-source, compiler,
native Bundle@2, signing and Product verification results but rejected the
runtime activation claim. Product `npm start` and `npm run dev` still selected
the frozen legacy `server.mjs`, while the additive native server did not serve
the standard static or Vite UI.

R5 closes only that Product activation gap. The unchanged BA10 `server.mjs`
remains archive evidence. The standard package launchers, the local server
ensurer and the hardening launcher now select the full
`ba12-native-server.mjs` runtime. That runtime serves static and Vite UI,
accepts only RFC-0009 generation-2 native Bundle@2 semantic truth, imports the
native verifier directly, exposes no canonical legacy semantic reader or
fallback edge, and keeps release, publication, deploy and commerce gates
false. The legacy server is reachable only through an explicit loopback-only,
acknowledgement-gated archive launcher.

This is an R5 independent-review candidate, not BA12 acceptance or freeze.

```text
ready_for_independent_rereview=true
ba12_implementation_ready=false
ba12_frozen=false
release_ready_candidate=true
release_ready=false
release_authorized=false
publication_authorized=false
deploy_authorized=false
stop_condition=none
```

## 2026-08-25 implementation resume

RFC-0010 is independently accepted and frozen at
`05f46f421f0da768424c125e39cabb86eb88b6c3fde7201d270a71725705ab6c`.
Its additive live-capture authority truthfully records `live_acquisition`,
durably freezes the provider bytes, and then bridges those immutable bytes to
the unchanged frozen BA3 offline-replay representation. RFC-0009 generation 2
continues to provide the accepted source-native Bundle@2 trust path.

The revalidated Wave-0 inventory has zero unknown runtime-reachable paths and
zero remaining RFC blockers. BA12 Waves 1–7 are therefore authorized above the
frozen BA0–BA11, RFC-0008, RFC-0009 and RFC-0010 boundaries. The historical
stop records below remain preserved as audit history; they are not current
state.

```text
ready_for_independent_rereview=false
ba12_implementation_ready=false
ba12_frozen=false
release_ready_candidate=false
release_ready=false
release_authorized=false
publication_authorized=false
deploy_authorized=false
stop_condition=none
```

## 2026-08-25 implementation result

Waves 1–7 are implemented as an independent-review candidate. The canonical
BA12 entry point is additive above the unchanged BA10 Product server and
accepts only Research-signed, RFC-0009 generation-2 Bundle@2 input. Real
public/free SEC and Nasdaq responses for WM, COST and ABT passed RFC-0010
capture, frozen BA3 replay, source-native compilation, Research signing and
Product verification. The 50-row BA12 matrix and 14-row RFC-0010 resume delta
matrix passed in full; all frozen Foundation, Semantic Wave, BA10, BA11,
RFC-0008, RFC-0009 and RFC-0010 checks remain PASS.

This result is not an acceptance or freeze. Release, publication and deploy
remain operator-gated and false.

```text
ready_for_independent_rereview=true
ba12_implementation_ready=false
ba12_frozen=false
release_ready_candidate=true
release_ready=false
release_authorized=false
publication_authorized=false
deploy_authorized=false
stop_condition=none
```

## 2026-08-24 final-resume result

RFC-0009 R2 was independently accepted and formally frozen at
`e9c9e6e5e5573961207babd66d7c981504d118ed4d14e87f7d6a8ca4180904b9`.
The trust conflict documented below is therefore resolved. Phase A and the
BA12 Wave-0 inventory completed before any BA12 runtime edit.

Wave 1 then reached the next frozen-boundary conflict. The BA12 contract
requires live provider bytes to be represented truthfully by the frozen BA3
`RetrievalReceiptIR`. Its frozen `transport` field accepts only
`offline_replay` and `offline_fixture`; it cannot represent
`live_acquisition`. The surrounding frozen BA3 models already distinguish
live acquisition in `CompilePolicyIR.network_mode` and
`SourceAcquisitionItemIR.retrieval_mode`, so relabelling live bytes as offline
would contradict the contract rather than provide a valid adapter.

This triggers original BA12 Stop Conditions 2 and 4. The Semantic Compiler
Wave v1 verifier remains PASS at version lock
`62867ad72cd1a99eee482e75087cbe01449faa650d7cf2c535fd494c5fef30f9`.
No BA3–BA9 file, Product file, runtime code, frozen policy, or frozen verifier
was changed.

Required follow-up: independently approve a versioned additive live-retrieval
receipt transport contract (or a BA3 contract successor) and bind it into a
new semantic-wave version without weakening the accepted offline replay
meaning. BA12 must remain stopped until that contract is accepted and frozen.

```text
ready_for_independent_rereview=false
ba12_implementation_ready=false
ba12_frozen=false
release_ready_candidate=false
release_ready=false
release_authorized=false
publication_authorized=false
deploy_authorized=false
stop_condition=FROZEN_BA3_LIVE_RECEIPT_TRANSPORT_UNREPRESENTABLE
```

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
