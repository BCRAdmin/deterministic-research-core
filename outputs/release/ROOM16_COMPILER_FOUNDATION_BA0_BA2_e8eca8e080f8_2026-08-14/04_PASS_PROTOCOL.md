
# Pass Protocol

Jeder Pass erklärt Input, Output, Side Effects, Determinismus, Cache, Replay, Failure,
Skip-Verhalten und Registry-Abhängigkeiten. BA1 enthält genau zwölf Shadow-Pässe.

| Prüfung | Ergebnis |
|---|---|
| 0 | `foundation.l0_compile_intake_observe` · L0_compile_intake · legacy.frozen_candidate → shadow.compile_request_ir |
| 1 | `foundation.l1_source_acquisition_observe` · L1_source_acquisition · shadow.compile_request_ir → shadow.source_acquisition_ir |
| 2 | `foundation.l2_source_snapshot_observe` · L2_source_snapshot · shadow.source_acquisition_ir → shadow.source_snapshot_ir |
| 3 | `foundation.l3_parse_discover_observe` · L3_parse_discover · shadow.source_snapshot_ir → shadow.parsed_document_ir |
| 4 | `foundation.l4_normalize_reconcile_observe` · L4_normalize_reconcile · shadow.parsed_document_ir → shadow.normalized_record_ir |
| 5 | `foundation.l5_typed_fact_observe` · L5_typed_fact · shadow.normalized_record_ir → shadow.typed_fact_ir |
| 6 | `foundation.l6_metric_formula_observe` · L6_metric_formula · shadow.typed_fact_ir → shadow.metric_ir |
| 7 | `foundation.l7_evidence_graph_observe` · L7_evidence_graph · shadow.metric_ir → shadow.evidence_graph_ir |
| 8 | `foundation.l8_claim_graph_observe` · L8_claim_graph · shadow.evidence_graph_ir → shadow.claim_graph_ir |
| 9 | `foundation.l9_decision_graph_observe` · L9_decision_graph · shadow.claim_graph_ir → shadow.decision_graph_ir |
| 10 | `foundation.l10_verification_observe` · L10_verification · shadow.decision_graph_ir → shadow.compile_verdict_ir |
| 11 | `foundation.l11_emit_observe` · L11_emit · shadow.compile_verdict_ir → shadow.compiler_artifact_bundle |

Alle Pässe sind side-effect-frei. Der Cache-Key bindet Pass-ID/-Version, Input-Payload-Hash
und Registry-Authority-Hash. Replay berechnet den Pass erneut und vergleicht Input,
Cache-Key und Output-Hash. Die Passkette besitzt keine Legacy-, Queue-, Renderer-, Provider-
oder LLM-Startfunktion.
