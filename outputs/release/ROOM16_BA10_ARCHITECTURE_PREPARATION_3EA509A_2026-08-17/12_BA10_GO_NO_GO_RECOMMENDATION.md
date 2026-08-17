# BA10 Go / No-Go Recommendation

## Recommendation

`BA10_IMPLEMENTATION_READY`

This means the architecture is sufficiently defined for the operator to
authorize a BA10 implementation RFC. It does not mean BA10 is authorized,
started, complete or ready for renderer/release/publication cutover.

## Evidence supporting readiness

1. The current path and every major Research→Product edge are identifiable.
2. The main architectural gap is bounded: no single compiler bundle, fragmented
   Product contracts and mixed/duplicate Product semantics.
3. Frozen BA0–BA9 need not change. BA10 can add an L11 artifact ABI and
   consumer boundary above the accepted L10 verdict.
4. Authority Bundle v3 can remain stable through an explicit compatibility
   view and dual-read migration.
5. The deterministic Research report renderer is a viable first strangler
   target; it already performs primarily presentation work.
6. Existing Product semantic rules can be retired incrementally only after
   compiler-owned negative fixtures prove equivalent protection.
7. A single Research-owned Python/JavaScript corpus removes the need for a
   second Product semantic implementation.
8. Frozen WM/COST/ABT inputs are sufficient migration canaries; no new company
   or human company audit is necessary for BA10 architecture validation.

## Material risks, all addressed by hard gates

| Risk | Required control |
|---|---|
| Shadow input is Authority v3, not source-native | explicit origin/compatibility mode; never claim native compilation |
| Bundle→v3 bridge appears circular | source-hash and cycle guard; staged bridge states |
| Product builders silently correct semantics | no-new-truth contract; migrate and retire rule-by-rule |
| LLM debate leaks into canonical output | separate annotation ABI with zero rating/release effect |
| Python/JS parse/hash differently | shared byte-level corpus and differential CI |
| Renderer changes numbers or meaning | semantic token inventory, graph-ID lineage and render parity |
| “BA10 complete” is confused with publishable | separate flags; release/publication stay false |

## Conditions before the first implementation change

- explicit operator approval for the BA10 RFC;
- frozen baseline and all canary hashes re-verified;
- ABI/corpus v1 committed in Research as contract authority;
- migration starts with sidecar output and zero existing output changes;
- stop/RFC escalation if a BA0–BA9, Authority-v3 or canary change is required.

## Not authorized by this review

- BA10 implementation or start;
- Foundation, Registry Foundation, semantic pass or schema changes;
- source-native promotion;
- Authority Bundle v4;
- Product semantic authority;
- renderer cutover;
- BA11/BA12;
- new company runs;
- release, publication or sales.

## Proposed next operator decision

Authorize or reject `RFC-0005 — Artifact ABI and Renderer Isolation` with the
phased strangler scope in `08_MIGRATION_PLAN.md`. Until that decision,
`ba10_authorized=false` and `ba10_started=false` remain binding.

