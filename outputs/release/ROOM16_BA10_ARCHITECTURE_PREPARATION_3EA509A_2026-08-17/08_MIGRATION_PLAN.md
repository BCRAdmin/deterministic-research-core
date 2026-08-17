# BA10 Strangler Migration Plan

## Governing rule

No big-bang cutover, no current output change at the first phase, no company
special case and no modification of frozen BA0–BA9. Each phase has a reversible
read-path switch and a fail-closed evidence gate.

## Phase 0 — BA10 RFC and baseline lock

- Approve an explicit BA10 implementation RFC.
- Bind Foundation, Registry, Semantic Wave, pass manifest, IR schema, Product
  commit and frozen WM/COST/ABT hashes.
- Freeze the ABI proposal and conformance corpus v1.
- Record all existing Product semantic components before changing them.

Exit: operator authorization exists; no code has crossed a freeze boundary.

## Phase 1 — Bundle sidecar

- Add an L11 bundle emission contract above verified L10 outputs.
- Emit `room16.compiler_artifact_bundle@1` beside existing artifacts.
- Declare `authority_v3_compatibility_shadow` and keep all release flags false.
- Build twice and prove byte-identical bundle manifest/archive.

Exit: existing report and Authority-v3 hashes unchanged; Product untouched.

## Phase 2 — Authority-v3 compatibility view

- Package the exact current v3 payload as a compatibility view.
- Add field-lineage and byte/semantic parity records.
- Prove bundle→v3 view round-trip against both current Product readers.

Exit: all v3 consumers receive identical semantics; bridge mismatch blocks.

## Phase 3 — Product dual reader

- Add a generic Product bundle verifier in shadow.
- Run legacy v3 intake and bundle intake side by side.
- Record structured semantic diffs; do not alter operator-visible output.
- Use one Research-owned Python/JS corpus.

Exit: zero unexplained differences for all frozen canaries and negative
fixtures.

## Phase 4 — First pure renderer

- Migrate the deterministic Markdown→DOCX/PDF renderer first because it is
  closest to presentation-only behavior.
- Remove/move its semantic specificity gate to compiler diagnostics.
- Emit `room16.rendered_artifact_set@1` and run visual/text/table parity.

Exit: zero renderer-generated fact/claim/decision and unchanged accepted
render meaning. Legacy renderer remains reversible.

## Phase 5 — Remaining renderer/API/UI consumers

- Migrate JSON/API/UI projections, then other Markdown/DOCX/PDF paths.
- Separate optional TradingAgents annotations from canonical report input.
- Make Product lifecycle and human/legal/release states consume the compiler
  verdict without overriding it.

Exit: every surface reads only verified bundle/projection IDs.

## Phase 6 — Retire Product parallel truth

- For each duplicate Product metric, claim, evidence, decision and quality
  rule, prove a compiler diagnostic/contract replacement.
- Disable one family at a time behind a rollback switch.
- Delete only after negative reintroduction fixtures and canary parity pass.

Exit: `product_parallel_truth=0`; Product retains only operational governance.

## Phase 7 — Bundle primary, v3 adapter only

- With separate operator approval, switch Product to bundle-primary intake.
- Keep v3 solely as a generated compatibility adapter for remaining legacy
  consumers.
- Retain rollback to the last proven dual-read state.

Exit: one canonical Research-to-Product transport. This is still not a public
release or source-native promotion.

## Stop conditions

Stop and raise a new RFC if implementation requires:

- a Foundation `1.0.0`, Registry Foundation `1.1.0`, L3–L10 IR or PassKernel
  change;
- an Authority Bundle v3 breaking change;
- a WM/COST/ABT archive modification;
- Product semantic authority;
- ticker/company-specific logic;
- a source-native or renderer/publication cutover outside the approved phase.

## Rollback

Every phase preserves the previous verified read path until the next phase is
explicitly accepted. Rollback changes only Product routing; it never mutates a
bundle, compiler artifact or frozen canary.

