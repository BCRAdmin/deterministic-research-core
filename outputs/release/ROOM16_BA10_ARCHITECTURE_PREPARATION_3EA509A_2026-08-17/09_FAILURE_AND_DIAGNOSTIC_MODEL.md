# Failure and Diagnostic Model

DiagnosticIR continues to separate semantic severity from release effect.
Product displays and routes diagnostics but cannot recode or downgrade them.

| Condition | Stable diagnostic code | Severity | Owner | Fail-closed behavior |
|---|---|---|---|---|
| Bundle absent | `ABI_BUNDLE_MISSING` | error | Product intake | no render/API truth; operational error only |
| Manifest hash mismatch | `ABI_MANIFEST_HASH_MISMATCH` | critical | Product intake | quarantine bundle |
| Artifact hash mismatch | `ABI_ARTIFACT_HASH_MISMATCH` | critical | Product intake | quarantine bundle and derived renders |
| Dependency hash mismatch | `ABI_DEPENDENCY_HASH_MISMATCH` | critical | Research contract/Product verification | block consumption |
| Registry mismatch | `ABI_REGISTRY_LOCK_MISMATCH` | critical | Research contract | block; no Product fallback registry |
| Pass manifest mismatch | `ABI_PASS_MANIFEST_MISMATCH` | critical | Research contract | block |
| Unsupported bundle/schema version | `ABI_CONTRACT_VERSION_UNSUPPORTED` | error | Product capability layer | reject before artifact use |
| Unknown required artifact/enum | `ABI_UNKNOWN_REQUIRED_SEMANTIC` | error | Product capability layer | reject |
| Required artifact missing | `ABI_ARTIFACT_MISSING` | critical | Product intake | reject |
| Required graph missing/incomplete | `ABI_REQUIRED_GRAPH_INCOMPLETE` | critical | Research/L10 | compile blocked; no bundle eligibility |
| Compile verdict blocked | `ABI_COMPILE_VERDICT_BLOCKED` | error | Research | allow diagnostic UI only; no report render |
| Compatibility mode misrepresented | `ABI_COMPATIBILITY_STATE_INVALID` | critical | Research ABI | quarantine |
| Consumer capability mismatch | `ABI_CONSUMER_CAPABILITY_MISMATCH` | error | Product | no render; report exact missing capability |
| Authority-v3 bridge mismatch | `ABI_AUTHORITY_V3_BRIDGE_MISMATCH` | critical | Research bridge | legacy adapter unavailable; no fallback |
| Bridge cycle/origin ambiguity | `ABI_COMPATIBILITY_CYCLE_DETECTED` | critical | Research bridge | quarantine |
| Python/JS result divergence | `ABI_CROSS_LANGUAGE_DIVERGENCE` | critical | Shared conformance | block BA10 gate/cutover |
| Renderer input not verified | `RENDERER_INPUT_UNVERIFIED` | critical | Renderer | abort before output |
| New fact/claim/decision | `RENDERER_NEW_TRUTH_DETECTED` | critical | Renderer parity | quarantine output |
| Visible number unbound | `RENDERER_NUMERIC_TOKEN_UNBOUND` | critical | Renderer parity | quarantine output |
| Unit/period/value changed | `RENDERER_SEMANTIC_VALUE_MISMATCH` | critical | Renderer parity | quarantine output |
| Render text/table parity mismatch | `RENDERER_SEMANTIC_PARITY_MISMATCH` | error | Renderer parity | quarantine output |
| Render file hash mismatch | `RENDERER_OUTPUT_HASH_MISMATCH` | critical | Product delivery | quarantine output |
| Product semantic rule detected | `PRODUCT_PARALLEL_TRUTH_DETECTED` | critical | BA10 architecture gate | block retirement/cutover |
| Annotation affects canonical state | `ANNOTATION_AUTHORITY_VIOLATION` | critical | Product | discard annotation, block candidate |

## Ownership and escalation

- Research owns compiler, ABI, registry, semantic diagnostic and bridge faults.
- Product owns transport, capability, renderer execution and operational
  delivery faults.
- Renderers own presentation failures but cannot change compiler eligibility.
- Human/legal/editorial review may add restrictions; it may not clear a
  compiler or ABI block.

Every failure record includes contract version, bundle/artifact IDs, pass/layer
when applicable, subject/source/root-cause/fixture references, semantic severity
and release effect. Unknown diagnostics with an unrecognized release effect
block.

