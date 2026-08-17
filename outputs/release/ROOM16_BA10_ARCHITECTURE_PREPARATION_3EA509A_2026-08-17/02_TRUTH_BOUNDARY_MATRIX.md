# Truth Boundary Matrix

## Classification rule

- `PURE_CONSUMER`: reads verified truth without changing it.
- `PRESENTATION_TRANSFORM`: ordering, localization or layout only.
- `SEMANTIC_TRANSFORM`: derives or rewrites fachliche meaning.
- `DUPLICATE_TRUTH`: independently models a Research-owned rule.
- `LEGACY_BRIDGE`: compatibility surface kept during strangler migration.
- `UNRESOLVED`: mixed component that must be split before cutover.

## Research components

| Component | Class | Finding | BA10 disposition |
|---|---|---|---|
| Current resolver and source adapters | SEMANTIC_TRANSFORM | Correctly Research-owned acquisition truth | Reference only; no BA0–BA9 change |
| Legacy normalization/reconciliation/calculation | SEMANTIC_TRANSFORM | Current live truth path | Preserve during shadow; bundle it transparently |
| Evidence, claims, decision and validation pipeline | SEMANTIC_TRANSFORM | Current live authority | Preserve; compare with frozen semantic IR |
| Authority Bundle v3 builder | LEGACY_BRIDGE | Stable transition ABI | Retain; later emit as bundle compatibility view |
| Legacy Research report composers | UNRESOLVED | Presentation plus reader-facing semantic wording | Carry as explicitly legacy payload first; isolate later |
| Foundation PassKernel | PURE_CONSUMER | Execution authority, no domain inference | Frozen and reused, not modified |
| Semantic L3–L10 passes | SEMANTIC_TRANSFORM | Accepted Research semantic authority in shadow | Frozen; bundle consumes outputs only |
| Registry Authority | SEMANTIC_TRANSFORM | Sole definition authority | Bundle locks exact registry hashes |
| Foundation L11 observe scaffold | LEGACY_BRIDGE | Not the final Artifact ABI | Do not reinterpret as completed BA10 emitter |

## Product and renderer components

| Component / location | Class | Why | Migration requirement |
|---|---|---|---|
| App queue, subprocess orchestration, job lifecycle in `room16-app/server.mjs` | PURE_CONSUMER | Operational state only | Consume bundle verdict/status without re-deriving it |
| JS Authority-v3 validator `server-modules/research-authority-bundle.mjs` | DUPLICATE_TRUTH + LEGACY_BRIDGE | Repeats schema and semantic checks | Replace semantic rules with generic ABI/hash/capability conformance |
| Python Authority-v3 validator `room16/core/research_authority.py` | DUPLICATE_TRUTH + LEGACY_BRIDGE | Second Product interpretation of the same authority | Same; retain only bridge reader until retirement |
| TradingAgents tool graph | UNRESOLVED | Tool nodes exist, but Authority mode blocks tool calls | Keep outside canonical truth; fail if an Authority-bound tool call occurs |
| Authority-bound analyst/debate output | SEMANTIC_TRANSFORM | Produces viewpoints, not reproducible facts | Store only as non-authoritative annotation with zero rating/release effect |
| `room16/core/interpretation_contract.py` | LEGACY_BRIDGE | Restricts tool calls, numeric claims, ratings and personal advice | Preserve until annotation ABI exists; never promote to compiler truth |
| Product domain models in `room16/core/models.py` | DUPLICATE_TRUTH | Product-owned Fact/Claim/Metric/Decision shapes | Retire or reduce to generated/read-only views of bundle contracts |
| `room16/core/metric_definitions.py` | DUPLICATE_TRUTH | Re-defines FCF/OCF/CapEx semantics | Remove from decision path after corpus proves bundle equivalence |
| `room16/core/claim_validators.py` | DUPLICATE_TRUTH | Re-validates identity, formula, source tier, archetype and news | Compiler diagnostic/verdict becomes sole semantic result |
| Quality/decision/status modules | DUPLICATE_TRUTH | Mix semantic quality and Product lifecycle state | Split compiler verdict from operational review/release state |
| Report view-model builders | UNRESOLVED | Useful projection plus semantic status derivation | Accept Research-owned RenderInputIR; keep presentation-only fields |
| `room16_build_complete_dossier.py` | SEMANTIC_TRANSFORM | Selects risk content and rewrites/corrects prose | First shadow-diff target; semantic rewriting forbidden after cutover |
| `room16_build_premium_report.py` | SEMANTIC_TRANSFORM + PRESENTATION_TRANSFORM | Prose assembly/localization mixed with rendering | Split into annotation input and pure renderer; no arbitrary factual LLM prose |
| `room16_render_deterministic_report.py` | PRESENTATION_TRANSFORM + UNRESOLVED | Mostly pure DOCX/PDF layout; specificity gate inspects meaning | Migrate first, then move semantic gate to compiler |
| Deterministic report scanner/snapshot JS | DUPLICATE_TRUTH + LEGACY_BRIDGE | Rechecks claims/coverage and creates snapshot ABI | Replace with bundle verification plus render parity only |
| Canonical/render manifests | PURE_CONSUMER if constrained | Hashes and operational activation are valid Product responsibilities | Must not derive semantic readiness or alter compiler verdict |
| Registry mirror verification | PURE_CONSUMER | Correct hash-verified read-only consumer | Retain; share conformance corpus |
| UI/API | PURE_CONSUMER | Displays data and operational state | Capability-gated read only; no calculations or inferred labels |
| Human/legal/editorial/publication gates | PURE_CONSUMER | Legitimate operational governance | May further restrict release, never override blocked compiler verdict |
| Commerce/delivery | PURE_CONSUMER | Downstream access and fulfillment | Requires separately authorized publishable artifacts |

## Python/JavaScript divergence points

1. Authority v3 is manually interpreted in Research Python, Product Python and
   Product JavaScript.
2. Canonical JSON and hashing are implemented in more than one language.
3. Missing/null/unknown-field and numeric behavior can diverge because the
   validators are handwritten.
4. Product JS report scanning reconstructs claim/evidence expectations already
   owned by Research.
5. Product Python models and validators name overlapping Fact, Metric, Claim,
   Decision and Quality concepts with different lifecycle semantics.

BA10 must not solve this by moving semantic rules into a shared Product
library. Research owns the contract and golden corpus; both languages only
perform generic consumer conformance.

## Required truth boundary after BA10

```text
Research semantic IR + verdict
        |
        v
CompilerArtifactBundle (immutable, verified)
        |
        +--> Authority v3 compatibility view
        +--> Product runtime/UI/API (read only)
        +--> Renderers (presentation only)
        +--> Optional agent annotations (non-authoritative, isolated)
```

