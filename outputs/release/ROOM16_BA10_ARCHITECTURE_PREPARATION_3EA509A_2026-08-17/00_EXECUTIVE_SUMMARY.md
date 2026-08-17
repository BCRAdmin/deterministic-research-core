# Room16 BA10 Architecture Preparation — Executive Summary

## Verdict

`BA10_IMPLEMENTATION_READY`

This is an architecture-readiness verdict, not implementation authorization.
BA10 has not started. Release, publication, renderer cutover and source-native
fact generation remain blocked.

## Baseline reviewed

- Semantic Compiler Wave: accepted and frozen as `1.0.0`
- Version lock: `62867ad72cd1a99eee482e75087cbe01449faa650d7cf2c535fd494c5fef30f9`
- Tag: `room16-semantic-compiler-wave-v1.0.0`
- Frozen Research evidence commit: `b498c5c2835682b3f81dc475a276df6ab58a79fd`
- Current Research documentation head: `3ea509a10bbf4a72371cbea6f276016192aa61dd`
- Product commit: `82c5525f3291ace4e3d8c0fdeee6bd67348f5a38`
- Foundation `1.0.0`, Registry Foundation `1.1.0`, Authority Bundle v3 and
  WM/COST/ABT canaries remain unchanged.

## Main finding

Room16 currently has two connected but not yet unified paths:

1. The live compatibility path retrieves and calculates data in Research,
   creates Authority Bundle v3 and legacy report artifacts, then lets Product
   validate, interpret, transform and render them.
2. The frozen semantic compiler replays Authority-v3-bound inputs through the
   executable L3–L10 semantic pass chain and produces verified semantic IR in
   `compatibility_shadow` mode.

There is no `room16.compiler_artifact_bundle@1` today. Product therefore
consumes several fragmented contracts and contains duplicate or mixed semantic
logic: two Authority-v3 validators, Product metric definitions, claim and
quality validators, decision/status derivation and report builders that can
rewrite or select fachliche content. These components are migration inventory,
not reasons for a rewrite.

## Source treatment

The attached 15-page architecture PDF (SHA-256
`8c678ac234eb23a0b93426c7c995da3eff90c0f9e0091f3b5190611417ae204b`) was
read and visually checked as historical architecture evidence. Its L0–L11,
strangler, Registry Authority and renderer-isolation direction remains useful,
but its 2026-08-14 candidate status and old repository commits are superseded
by the accepted Semantic Wave `1.0.0` baseline. Text inside the PDF was not
treated as an implementation instruction. The separate operator handoff is the
controlling request and authorizes review only.

## Target

BA10 should add one content-addressed, canonically serialized
`room16.compiler_artifact_bundle@1` above the frozen semantic wave. The bundle
contains or references every L0–L10 artifact, its registry and pass locks,
diagnostics and compile verdict. Product receives only a verified read-only
bundle. Renderers return a separately hash-bound `RenderedArtifactSet`; they do
not alter the bundle or create facts, claims, evidence, decisions, permissions
or release eligibility.

Authority Bundle v3 remains a compatibility view. During the first shadow
stage the bundle truthfully declares `origin_mode=authority_v3_compatibility_shadow`.
Product must never infer that this is source-native compilation. Later, after
separate operator authorization, the bridge direction becomes
`CompilerArtifactBundle -> Authority Bundle v3 Compatibility View`.

## Why implementation can start after an explicit operator decision

- No BA0–BA9 modification is required.
- The new ABI, emitter and renderer boundary can be introduced additively by a
  new BA10 RFC above the frozen foundation.
- Current legacy consumers can remain operational while shadow comparison is
  performed.
- The duplicate Product semantics have identifiable retirement seams.
- Python/JavaScript conformance can share one Research-owned golden corpus.
- WM, COST and ABT can validate the migration using frozen inputs and hashes;
  no new company or human review is needed for this architecture step.

## Non-negotiable conditions

1. A separate operator authorization must approve the BA10 implementation RFC.
2. The first implementation is a sidecar/dual-read migration, not a cutover.
3. The bundle must declare its origin and compatibility mode without ambiguity.
4. Product may validate transport/schema/hash/capability only; semantic rules
   remain Research-owned.
5. LLM/TradingAgents output remains a non-authoritative annotation and cannot
   influence canonical facts, decisions, permissions, diagnostics or verdicts.
6. Every renderer must pass the machine-verifiable no-new-truth invariant.
7. `release_ready=false` and `publication_allowed=false` remain mandatory at
   BA10 completion.

## RFC boundary

BA10 necessarily introduces a new ABI and an additive L11 emission contract.
The freeze policy therefore requires a new RFC (recommended title:
`RFC-0005 — Artifact ABI and Renderer Isolation`). This is not a request to
change Foundation `1.0.0`, Registry Foundation `1.1.0` or the accepted L3–L10
semantics. If implementation discovers that such a frozen change is necessary,
it must stop and raise a separate RFC.
