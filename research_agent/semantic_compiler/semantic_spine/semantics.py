"""Connected Normalize→Facts→Metrics→Evidence→Claims→Decision passes for RFC-0002."""

from __future__ import annotations

import math
from typing import Any

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.semantic_compiler.registry_foundation.authority import SemanticRegistryAuthority
from research_agent.semantic_compiler.semantic_wave.contracts import FormulaEvaluationIR
from research_agent.semantic_compiler.semantic_wave.metrics import evaluate_legacy_formula

from .contracts import (
    ClaimGraphSpineIR,
    ClaimLineageIR,
    DecisionGraphSpineIR,
    EvidenceGraphSpineIR,
    MetricSignatureIR,
    MetricSpineIR,
    NormalizedFactRecordIR,
    ParsedPayloadIR,
    PayloadGraphEdgeIR,
    PayloadGraphNodeIR,
    SourceInputIR,
    TypedFactSpineIR,
    create_hashed,
)


class SemanticSpineError(ValueError):
    """Fail-closed semantic spine error."""


def _safe(value: str) -> str:
    cleaned = "".join(character.lower() if character.isalnum() else "." for character in value)
    return ".".join(part for part in cleaned.split(".") if part) or "root"


def _value_state(fact: dict[str, Any]) -> str:
    flags = [bool(fact.get("is_zero")), bool(fact.get("is_missing")), bool(fact.get("is_not_applicable"))]
    if sum(flags) > 1:
        raise SemanticSpineError(f"value_state_collision:{fact.get('fact_id')}")
    if flags[1]:
        return "missing"
    if flags[2]:
        return "not_applicable"
    if flags[0]:
        return "zero"
    return "value"


def _fact_kind(*, dimension: str, fact_type: str, period_kind: str) -> str:
    if fact_type == "guidance_range" or period_kind == "guidance":
        return "guidance_range"
    if dimension in {"multiple", "percent", "basis_points", "per_share"} or period_kind in {"rate", "comparison"}:
        return "ratio"
    if dimension == "text":
        return "qualitative"
    if period_kind == "instant" or fact_type in {"instant_value", "stock_value"}:
        return "instant"
    if fact_type in {"flow_value", "period_total", "reconciliation_component", "contribution_to_change"}:
        return "flow"
    return "duration"


def normalize_fact_ledger(source: SourceInputIR, parsed: ParsedPayloadIR) -> tuple[NormalizedFactRecordIR, ...]:
    if source.compatibility_adapter_id != "authority_bundle_v3.fact_ledger":
        raise SemanticSpineError("fact_normalizer_requires_named_compatibility_adapter")
    if parsed.source_input_sha256 != source.ir_sha256 or parsed.compatibility_adapter_id != source.compatibility_adapter_id:
        raise SemanticSpineError("parsed_fact_ledger_lineage_mismatch")
    payload = parsed.payload
    if not isinstance(payload, dict) or not isinstance(payload.get("claims"), list):
        raise SemanticSpineError("fact_ledger_shape_invalid")
    records: list[NormalizedFactRecordIR] = []
    seen: dict[str, str] = {}
    for fact in sorted(payload["claims"], key=lambda item: str(item.get("fact_id"))):
        fact_id = str(fact.get("fact_id") or "")
        metric_id = str(fact.get("metric") or "")
        if not fact_id or not metric_id:
            raise SemanticSpineError("fact_identity_missing")
        source_ids = tuple(sorted({str(item) for item in (fact.get("source_ids") or [fact.get("source_id")]) if item}))
        evidence_ids = tuple(sorted({str(item) for item in fact.get("evidence_ids") or [] if item}))
        record = create_hashed(
            NormalizedFactRecordIR,
            record_id=f"normalized.{_safe(fact_id)}",
            source_input_sha256=source.ir_sha256,
            parsed_payload_sha256=parsed.ir_sha256,
            compatibility_adapter_id="authority_bundle_v3.fact_ledger",
            fact_id=fact_id,
            metric_id=metric_id,
            value_state=_value_state(fact),
            value=fact.get("value"),
            signed_value=fact.get("signed_value") if isinstance(fact.get("signed_value"), (int, float)) else None,
            dimension=str(fact.get("dimension") or "text"),
            fact_type=str(fact.get("fact_type") or "unknown"),
            unit=str(fact.get("display_unit") or fact.get("unit") or "text"),
            currency=str(fact.get("currency") or "none"),
            scale=str(fact.get("source_scale") or "none"),
            period_kind=str(fact.get("period_kind") or "unknown"),
            period_start=fact.get("period_start"),
            period_end=fact.get("period_end"),
            source_ids=source_ids,
            evidence_ids=evidence_ids,
            source_locator=fact.get("source_locator"),
            table_id=fact.get("table_id"),
            cell_id=fact.get("cell_id"),
            formula_id=str(fact["formula_id"]) if fact.get("formula_id") else None,
            formula_operands=dict(fact.get("formula_operands") or {}),
        )
        previous = seen.get(fact_id)
        if previous and previous != record.ir_sha256:
            raise SemanticSpineError(f"conflicting_duplicate_fact:{fact_id}")
        if not previous:
            records.append(record)
            seen[fact_id] = record.ir_sha256
    return tuple(records)


def build_typed_facts(records: tuple[NormalizedFactRecordIR, ...], authority: SemanticRegistryAuthority) -> tuple[TypedFactSpineIR, ...]:
    facts: list[TypedFactSpineIR] = []
    for record in records:
        definition_id, binding_type = authority.bind_metric(record.metric_id)
        if binding_type in {"quarantined_unknown", "semantic_collision"}:
            raise SemanticSpineError(f"unexecutable_metric:{record.metric_id}")
        facts.append(create_hashed(
            TypedFactSpineIR,
            fact_id=record.fact_id,
            metric_id=record.metric_id,
            metric_definition_id=definition_id,
            fact_kind=_fact_kind(dimension=record.dimension, fact_type=record.fact_type, period_kind=record.period_kind),
            fact_type=record.fact_type,
            value_state=record.value_state,
            value=record.value,
            dimension=record.dimension,
            unit=record.unit,
            currency=record.currency,
            scale=record.scale,
            period_kind=record.period_kind,
            period_start=record.period_start,
            period_end=record.period_end,
            source_ids=record.source_ids,
            evidence_ids=record.evidence_ids,
            source_locator=record.source_locator,
            table_id=record.table_id,
            cell_id=record.cell_id,
            normalized_record_sha256=record.ir_sha256,
        ))
    return tuple(sorted(facts, key=lambda item: item.fact_id))


def _aggregation(fact: TypedFactSpineIR) -> str:
    if fact.fact_kind == "flow" or fact.fact_type in {"period_total", "flow_value"}:
        return "sum_non_overlapping_periods"
    if fact.fact_kind == "instant":
        return "last_observation_only"
    if fact.fact_kind == "ratio":
        return "non_additive"
    if fact.fact_kind == "guidance_range":
        return "bounded_forward_range"
    return "none"


def _direction(fact: TypedFactSpineIR) -> str:
    if fact.fact_type in {"year_over_year_change", "contribution_to_change"} or fact.period_kind == "comparison":
        return "signed_change"
    if fact.dimension in {"currency", "count", "shares", "per_share"}:
        return "absolute_level"
    return "neutral"


def _comparison(fact: TypedFactSpineIR) -> str:
    if fact.period_kind == "comparison" or fact.fact_type == "year_over_year_change":
        return "comparison_period_required"
    if fact.period_kind == "guidance" or fact.fact_kind == "guidance_range":
        return "forward_period_required"
    return "not_comparative"


def signature_for_fact(fact: TypedFactSpineIR) -> MetricSignatureIR:
    body = {
        "legacy_metric_id": fact.metric_id,
        "metric_definition_id": fact.metric_definition_id,
        "dimension": fact.dimension,
        "fact_kind": fact.fact_kind,
        "fact_subtype": fact.fact_type,
        "period_role": fact.period_kind,
        "unit": fact.unit,
        "scale": fact.scale,
        "currency": fact.currency,
        "aggregation_behavior": _aggregation(fact),
        "direction_contract": _direction(fact),
        "comparison_contract": _comparison(fact),
    }
    expected = sha256_json(body)
    return create_hashed(
        MetricSignatureIR,
        signature_id=f"signature.{_safe(fact.metric_id)}.{expected[:16]}",
        expected_contract_sha256=expected,
        **body,
    )


def build_metrics(facts: tuple[TypedFactSpineIR, ...], signature_authority: Any) -> tuple[tuple[MetricSignatureIR, ...], tuple[MetricSpineIR, ...]]:
    signatures: dict[str, MetricSignatureIR] = {}
    metrics: list[MetricSpineIR] = []
    for fact in facts:
        signature = signature_authority.require_fact_signature(fact)
        signatures.setdefault(signature.signature_id, signature)
        metrics.append(create_hashed(
            MetricSpineIR,
            metric_instance_id=f"metric.instance.{_safe(fact.fact_id)}",
            fact_id=fact.fact_id,
            metric_id=fact.metric_id,
            signature_id=signature.signature_id,
            signature_sha256=signature.ir_sha256,
            typed_fact_sha256=fact.ir_sha256,
            value=fact.value,
        ))
    return tuple(signatures[key] for key in sorted(signatures)), tuple(sorted(metrics, key=lambda item: item.metric_instance_id))


def evaluate_formulas(records: tuple[NormalizedFactRecordIR, ...], authority: SemanticRegistryAuthority) -> tuple[FormulaEvaluationIR, ...]:
    context = {record.metric_id: {"formula_operands": record.formula_operands} for record in records}
    evaluations: list[FormulaEvaluationIR] = []
    for record in records:
        if not record.formula_id or not record.formula_operands:
            continue
        definition_id = authority.bind_formula(record.formula_id)
        evaluated = evaluate_legacy_formula(record.formula_id, record.formula_operands, fact_context=context)
        if not isinstance(record.value, (int, float)) or not math.isclose(float(record.value), evaluated, rel_tol=1e-10, abs_tol=1e-8):
            raise SemanticSpineError(f"formula_result_mismatch:{record.fact_id}")
        definition = authority.formula_definitions[definition_id]
        body = {
            "formula_instance_id": f"formula.instance.{_safe(record.fact_id)}",
            "formula_definition_id": definition_id,
            "operand_fact_ids": tuple(f"{record.fact_id}.operand.{_safe(role)}" for role in sorted(record.formula_operands)),
            "result_fact_id": record.fact_id,
            "expected_value": float(record.value),
            "evaluated_value": evaluated,
            "result_dimension": definition.result_dimension,
            "rounding_policy": definition.rounding_policy,
            "evaluation_status": "verified",
            "evaluation_hash": sha256_json({
                "formula_id": record.formula_id,
                "operands": record.formula_operands,
                "result_fact_id": record.fact_id,
                "evaluated_value": evaluated,
            }),
        }
        draft = FormulaEvaluationIR.model_construct(ir_sha256="0" * 64, **body)
        payload = draft.model_dump(mode="json", exclude={"ir_sha256"})
        evaluations.append(FormulaEvaluationIR.model_validate({**payload, "ir_sha256": sha256_json(payload)}))
    return tuple(sorted(evaluations, key=lambda item: item.formula_instance_id))


def _node(node_id: str, kind: str, subject: str, payload: Any) -> PayloadGraphNodeIR:
    return PayloadGraphNodeIR(node_id=node_id, node_kind=kind, subject_ref=subject, payload=payload, payload_sha256=sha256_json(payload))


def _edge(edge_id: str, kind: str, source: str, target: str, ordinal: int = 0, payload: dict[str, Any] | None = None) -> PayloadGraphEdgeIR:
    body = payload or {}
    return PayloadGraphEdgeIR(edge_id=edge_id, edge_kind=kind, from_node_id=source, to_node_id=target, ordinal=ordinal, payload=body, payload_sha256=sha256_json(body))


def _json_payload(parsed: ParsedPayloadIR, adapter_id: str) -> Any:
    if parsed.compatibility_adapter_id != adapter_id:
        raise SemanticSpineError(f"compatibility_adapter_mismatch:{adapter_id}")
    return parsed.payload


def build_evidence_graph(*, ticker: str, as_of_date: str, source_registry: ParsedPayloadIR, evidence_ledger: ParsedPayloadIR, facts: tuple[TypedFactSpineIR, ...]) -> EvidenceGraphSpineIR:
    source_payload = _json_payload(source_registry, "authority_bundle_v3.source_registry")
    evidence_payload = _json_payload(evidence_ledger, "authority_bundle_v3.evidence_ledger")
    sources = {str(item["source_id"]): item for item in source_payload.get("sources") or []}
    evidence = {str(item["evidence_id"]): item for item in evidence_payload.get("evidence_items") or []}
    nodes: dict[str, PayloadGraphNodeIR] = {}
    edges: dict[str, PayloadGraphEdgeIR] = {}
    unknown_sources: set[str] = set()
    for source_id, payload in sorted(sources.items()):
        source_node = f"source.{_safe(source_id)}"
        nodes[source_node] = _node(source_node, "source", source_id, payload)
        locator = str(payload.get("url") or payload.get("source_locator") or "")
        if locator:
            locator_node = f"locator.{sha256_json({'source_id': source_id, 'locator': locator})[:24]}"
            nodes[locator_node] = _node(locator_node, "locator", locator, {"locator": locator})
            edges[f"edge.{source_node}.{locator_node}"] = _edge(f"edge.{source_node}.{locator_node}", "locates", source_node, locator_node)
    for evidence_id, payload in sorted(evidence.items()):
        evidence_node = f"evidence.{_safe(evidence_id)}"
        nodes[evidence_node] = _node(evidence_node, "evidence", evidence_id, payload)
        source_id = str(payload.get("source_id") or "")
        if not source_id or source_id not in sources:
            if source_id:
                unknown_sources.add(source_id)
            continue
        source_node = f"source.{_safe(source_id)}"
        edge_id = f"edge.{evidence_node}.{source_node}"
        edges[edge_id] = _edge(edge_id, "originates_from", evidence_node, source_node)
        # source_lineage contains accession/derivation tokens in Authority v3,
        # not additional Source Registry IDs. Preserve them as locators instead
        # of silently inventing source nodes.
        for ordinal, locator in enumerate(sorted({str(item) for item in payload.get("source_lineage") or [] if item})):
            locator_node = f"locator.{sha256_json({'source_id': source_id, 'locator': locator})[:24]}"
            nodes.setdefault(locator_node, _node(locator_node, "locator", locator, {"locator": locator}))
            locator_edge = f"edge.{source_node}.{locator_node}.lineage.{ordinal}"
            edges[locator_edge] = _edge(locator_edge, "locates", source_node, locator_node, ordinal, {"lineage_token": True})
    for fact in facts:
        fact_node = f"fact.{_safe(fact.fact_id)}"
        nodes[fact_node] = _node(fact_node, "typed_fact", fact.fact_id, fact.model_dump(mode="json"))
        for evidence_id in fact.evidence_ids:
            evidence_node = f"evidence.{_safe(evidence_id)}"
            if evidence_node in nodes:
                edge_id = f"edge.{fact_node}.{evidence_node}"
                edges[edge_id] = _edge(edge_id, "supported_by", fact_node, evidence_node)
    return create_hashed(
        EvidenceGraphSpineIR,
        ticker=ticker,
        as_of_date=as_of_date,
        nodes=tuple(nodes[key] for key in sorted(nodes)),
        edges=tuple(edges[key] for key in sorted(edges)),
        unknown_source_ids=tuple(sorted(unknown_sources)),
    )


def _same_value(left: Any, right: Any) -> bool:
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), rel_tol=1e-10, abs_tol=1e-8)
    return left == right


def build_claim_graph(*, ticker: str, as_of_date: str, claims_document: ParsedPayloadIR, evidence_document: ParsedPayloadIR, source_document: ParsedPayloadIR, facts: tuple[TypedFactSpineIR, ...], evidence_graph: EvidenceGraphSpineIR, authority: SemanticRegistryAuthority) -> ClaimGraphSpineIR:
    claims = _json_payload(claims_document, "authority_bundle_v3.analyst_claims")
    evidence_items = _json_payload(evidence_document, "authority_bundle_v3.evidence_ledger").get("evidence_items") or []
    source_items = _json_payload(source_document, "authority_bundle_v3.source_registry").get("sources") or []
    evidence_by_id = {str(item["evidence_id"]): item for item in evidence_items}
    sources = {str(item["source_id"]): item for item in source_items}
    facts_by_id = {item.fact_id: item for item in facts}
    nodes = {item.node_id: item for item in evidence_graph.nodes}
    edges = {item.edge_id: item for item in evidence_graph.edges}
    lineages: list[ClaimLineageIR] = []
    missing_claims: list[str] = []
    missing_bindings: list[str] = []
    for claim in sorted(claims, key=lambda item: str(item.get("claim_id"))):
        claim_id = str(claim.get("claim_id") or "")
        if not claim_id:
            raise SemanticSpineError("claim_identity_missing")
        authority.bind_claim_kind(str(claim.get("claim_type") or ""))
        claim_node = f"claim.{_safe(claim_id)}"
        nodes[claim_node] = _node(claim_node, "claim", claim_id, claim)
        claim_has_lineage = False
        for ordinal, evidence_id in enumerate(sorted({str(item) for item in claim.get("evidence_ids") or []})):
            evidence = evidence_by_id.get(evidence_id)
            if evidence is None:
                continue
            source_id = str(evidence.get("source_id") or "")
            source = sources.get(source_id)
            locator = str(evidence.get("source_locator") or evidence.get("url") or (source or {}).get("url") or "")
            if source and locator:
                evidence_node = f"evidence.{_safe(evidence_id)}"
                edges[f"edge.{claim_node}.{evidence_node}"] = _edge(f"edge.{claim_node}.{evidence_node}", "supported_by", claim_node, evidence_node, ordinal)
                claim_has_lineage = True
        for ordinal, binding in enumerate(claim.get("numeric_bindings") or []):
            span_id = str(binding.get("span_id") or f"{claim_id}:number-{ordinal + 1}")
            fact_id = str(binding.get("fact_id") or "")
            evidence_id = str(binding.get("evidence_id") or "")
            source_id = str(binding.get("source_id") or "")
            fact = facts_by_id.get(fact_id)
            evidence = evidence_by_id.get(evidence_id)
            source = sources.get(source_id)
            locator = str(binding.get("source_locator") or (evidence or {}).get("source_locator") or (evidence or {}).get("url") or (source or {}).get("url") or "")
            declared = bool(fact and evidence_id in fact.evidence_ids)
            evidence_value = None if evidence is None else next((evidence.get(key) for key in ("normalized_value", "value", "signed_value") if evidence.get(key) is not None), None)
            semantic_alternate = bool(
                fact and evidence
                and str(binding.get("metric_id") or "") == fact.metric_id
                and fact.metric_id in {str(item) for item in evidence.get("supports_metrics") or []}
                and _same_value(fact.value, evidence_value)
                and str(evidence.get("source_id") or "") == source_id
            )
            if not (fact and evidence and source and locator and (declared or semantic_alternate)):
                missing_bindings.append(span_id)
                continue
            lineage_kind = "declared" if declared else "semantic_alternate"
            body = {
                "claim_id": claim_id,
                "span_id": span_id,
                "fact_id": fact_id,
                "evidence_id": evidence_id,
                "source_id": source_id,
                "locator": locator,
                "lineage_kind": lineage_kind,
            }
            lineage = ClaimLineageIR(**body, lineage_sha256=sha256_json(body))
            lineages.append(lineage)
            fact_node = f"fact.{_safe(fact_id)}"
            evidence_node = f"evidence.{_safe(evidence_id)}"
            source_node = f"source.{_safe(source_id)}"
            locator_node = f"locator.{sha256_json({'source_id': source_id, 'locator': locator})[:24]}"
            nodes.setdefault(locator_node, _node(locator_node, "locator", locator, {"locator": locator}))
            edges[f"edge.{claim_node}.{fact_node}.{ordinal}"] = _edge(f"edge.{claim_node}.{fact_node}.{ordinal}", "asserts", claim_node, fact_node, ordinal, {"span_id": span_id})
            edges[f"edge.{fact_node}.{evidence_node}.{ordinal}"] = _edge(f"edge.{fact_node}.{evidence_node}.{ordinal}", "supported_by", fact_node, evidence_node, ordinal, {"lineage_kind": lineage_kind})
            edges[f"edge.{evidence_node}.{source_node}.{ordinal}"] = _edge(f"edge.{evidence_node}.{source_node}.{ordinal}", "originates_from", evidence_node, source_node, ordinal)
            edges[f"edge.{source_node}.{locator_node}.{ordinal}"] = _edge(f"edge.{source_node}.{locator_node}.{ordinal}", "locates", source_node, locator_node, ordinal)
            claim_has_lineage = True
        if not claim_has_lineage:
            missing_claims.append(claim_id)
    return create_hashed(
        ClaimGraphSpineIR,
        ticker=ticker,
        as_of_date=as_of_date,
        evidence_graph_sha256=evidence_graph.ir_sha256,
        nodes=tuple(nodes[key] for key in sorted(nodes)),
        edges=tuple(edges[key] for key in sorted(edges)),
        numeric_lineages=tuple(sorted(lineages, key=lambda item: (item.claim_id, item.span_id))),
        claims_without_lineage=tuple(sorted(missing_claims)),
        numeric_bindings_without_lineage=tuple(sorted(missing_bindings)),
    )


def _graphify(value: Any, pointer: str, nodes: dict[str, PayloadGraphNodeIR], edges: dict[str, PayloadGraphEdgeIR]) -> str:
    node_id = f"decision.node.{sha256_json(pointer)[:24]}"
    if isinstance(value, dict):
        nodes[node_id] = _node(node_id, "object", pointer, {"container": "object"})
        for ordinal, key in enumerate(sorted(value)):
            child = _graphify(value[key], f"{pointer}/{key}", nodes, edges)
            edge_id = f"decision.edge.{sha256_json([pointer, key])[:24]}"
            edges[edge_id] = _edge(edge_id, "contains", node_id, child, ordinal, {"key": key})
    elif isinstance(value, list):
        nodes[node_id] = _node(node_id, "array", pointer, {"container": "array"})
        for index, item in enumerate(value):
            child = _graphify(item, f"{pointer}/{index}", nodes, edges)
            edge_id = f"decision.edge.{sha256_json([pointer, index])[:24]}"
            edges[edge_id] = _edge(edge_id, "contains", node_id, child, index, {"index": index})
    else:
        nodes[node_id] = _node(node_id, "scalar", pointer, {"value": value})
    return node_id


def build_decision_graph(decision_document: ParsedPayloadIR, source: SourceInputIR, authority: SemanticRegistryAuthority) -> DecisionGraphSpineIR:
    payload = _json_payload(decision_document, "authority_bundle_v3.decision_packet")
    required = {"action_policy", "as_of_date", "decision_inputs", "publication_permission", "rating_permission", "ticker"}
    missing = sorted(required - set(payload)) if isinstance(payload, dict) else sorted(required)
    if missing:
        raise SemanticSpineError(f"decision_packet_fields_missing:{','.join(missing)}")
    permission = payload.get("rating_permission")
    if not isinstance(permission, dict) or not {"allowed_ratings", "blocked_ratings", "permission_type", "preferred_rating", "publication_allowed"}.issubset(permission):
        raise SemanticSpineError("decision_rating_permission_invalid")
    if permission.get("preferred_rating") is not None and permission["preferred_rating"] not in permission["allowed_ratings"]:
        raise SemanticSpineError("decision_preferred_rating_outside_corridor")
    action_policy = payload.get("action_policy")
    if not isinstance(action_policy, dict) or not {"actionability", "reason"}.issubset(action_policy):
        raise SemanticSpineError("decision_non_advice_boundary_missing")
    authority.require_permission_definition("permission.rating_corridor")
    for item in payload.get("decision_inputs") or []:
        authority.bind_decision_input(str(item.get("input_type") or ""))
    nodes: dict[str, PayloadGraphNodeIR] = {}
    edges: dict[str, PayloadGraphEdgeIR] = {}
    root = _graphify(payload, "$", nodes, edges)
    ordered_nodes = tuple(nodes[key] for key in sorted(nodes))
    ordered_edges = tuple(edges[key] for key in sorted(edges))
    reconstructed = _reconstruct_parts(root, ordered_nodes, ordered_edges)
    return create_hashed(
        DecisionGraphSpineIR,
        ticker=str(payload["ticker"]),
        as_of_date=str(payload["as_of_date"]),
        source_input_sha256=source.ir_sha256,
        parsed_payload_sha256=decision_document.ir_sha256,
        root_node_id=root,
        nodes=ordered_nodes,
        edges=ordered_edges,
        comparison_payload_sha256=sha256_json(payload),
        reconstructed_payload_sha256=sha256_json(reconstructed),
    )


def _reconstruct_parts(root_node_id: str, node_items: tuple[PayloadGraphNodeIR, ...], edge_items: tuple[PayloadGraphEdgeIR, ...]) -> Any:
    nodes = {item.node_id: item for item in node_items}
    children: dict[str, list[PayloadGraphEdgeIR]] = {}
    for edge in edge_items:
        if edge.from_node_id not in nodes or edge.to_node_id not in nodes:
            raise SemanticSpineError("decision_edge_endpoint_unknown")
        children.setdefault(edge.from_node_id, []).append(edge)

    def visit(node_id: str) -> Any:
        node = nodes[node_id]
        outgoing = sorted(children.get(node_id, []), key=lambda item: item.ordinal)
        if node.node_kind == "scalar":
            if outgoing:
                raise SemanticSpineError("decision_scalar_has_children")
            return node.payload["value"]
        if node.node_kind == "array":
            indices = [edge.payload.get("index") for edge in outgoing]
            if indices != list(range(len(outgoing))):
                raise SemanticSpineError("decision_array_indices_invalid")
            return [visit(edge.to_node_id) for edge in outgoing]
        if node.node_kind == "object":
            keys = [edge.payload.get("key") for edge in outgoing]
            if any(not isinstance(key, str) for key in keys) or len(keys) != len(set(keys)):
                raise SemanticSpineError("decision_object_keys_invalid")
            return {str(edge.payload["key"]): visit(edge.to_node_id) for edge in outgoing}
        raise SemanticSpineError("decision_node_kind_unknown")

    return visit(root_node_id)


def reconstruct_decision(graph: DecisionGraphSpineIR, *, verify_declared_hash: bool = True) -> Any:
    result = _reconstruct_parts(graph.root_node_id, graph.nodes, graph.edges)
    if verify_declared_hash:
        if sha256_json(result) != graph.reconstructed_payload_sha256:
            raise SemanticSpineError("decision_reconstructed_hash_mismatch")
        if sha256_json(result) != graph.comparison_payload_sha256:
            raise SemanticSpineError("decision_roundtrip_loss")
    return result
