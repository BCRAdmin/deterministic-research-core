
# Layer- und Ownership-Verfassung

Research besitzt L0-L11 sowie alle fachlichen Registries. Product besitzt ausschließlich die
operativen Flächen und führt Renderer erst als nachgelagertes Backend hinter L11 aus. Product
darf keine fachliche Parallelwahrheit erzeugen.

Verbindliche Konfiguration:

```json
{
  "architecture_style": "shadow_strangler",
  "contract_id": "room16.compiler.layer_ownership_constitution",
  "contract_version": 1,
  "effective_wave": "BA0-BA2",
  "foundation_constraints": {
    "authority_bundle_v3_change_allowed": false,
    "ba3_started": false,
    "legacy_output_change_allowed": false,
    "new_archetype_run_allowed": false,
    "new_company_run_allowed": false,
    "new_llm_analysis_run_allowed": false,
    "new_renderer_run_allowed": false
  },
  "product": {
    "executes_compiler_layer": [],
    "may_create_semantic_parallel_truth": false,
    "operational_registries_may_define_compiler_semantics": false,
    "owns_operational_registries": [
      "renderer",
      "canary_archetype",
      "release_interaction"
    ],
    "owns_operations": [
      "runtime",
      "queue",
      "operator_ui",
      "renderer_execution",
      "release_interaction"
    ],
    "registry_access": "hash_verified_read_only_research_mirror",
    "renderer_position": "downstream_backend_after_L11_emit"
  },
  "research": {
    "owns_layers": [
      "L0_compile_intake",
      "L1_source_acquisition",
      "L2_source_snapshot",
      "L3_parse_discover",
      "L4_normalize_reconcile",
      "L5_typed_fact",
      "L6_metric_formula",
      "L7_evidence_graph",
      "L8_claim_graph",
      "L9_decision_graph",
      "L10_verification",
      "L11_emit"
    ],
    "owns_registry_authority": true,
    "owns_semantic_truth": [
      "sources",
      "facts",
      "metrics",
      "evidence",
      "claims",
      "decisions",
      "diagnostics",
      "verdicts"
    ]
  }
}
```
