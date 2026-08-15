"""BA7 Evidence, BA8 Claim and BA9 Decision graph builders."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.semantic_compiler.registry_foundation.authority import SemanticRegistryAuthority

from .contracts import (
    ClaimGraphIR,
    DecisionGraphIR,
    EvidenceGraphIR,
    GraphEdgeIR,
    GraphNodeIR,
    TypedFactIR,
    create_hashed,
)


class GraphError(ValueError):
    """Fail-closed graph construction error."""


def _safe(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "." for char in value)
    return ".".join(part for part in cleaned.split(".") if part)


def _node(node_id: str, kind: str, subject: str, payload: Any) -> GraphNodeIR:
    return GraphNodeIR(
        node_id=node_id,
        node_kind=kind,
        subject_ref=subject,
        payload_sha256=sha256_json(payload),
    )


def _edge(edge_id: str, kind: str, source: str, target: str, payload: Any = None) -> GraphEdgeIR:
    return GraphEdgeIR(
        edge_id=edge_id,
        edge_kind=kind,
        from_node_id=source,
        to_node_id=target,
        payload_sha256=sha256_json({} if payload is None else payload),
    )


def build_evidence_graph(
    *,
    ticker: str,
    as_of_date: str,
    source_registry: dict[str, Any],
    evidence_ledger: dict[str, Any],
    typed_facts: tuple[TypedFactIR, ...],
) -> EvidenceGraphIR:
    nodes: dict[str, GraphNodeIR] = {}
    edges: dict[str, GraphEdgeIR] = {}
    for source in source_registry.get("sources") or []:
        node_id = f"source.{_safe(str(source['source_id']))}"
        nodes[node_id] = _node(node_id, "source", str(source["source_id"]), source)
    evidence_by_id = {
        str(item["evidence_id"]): item for item in evidence_ledger.get("evidence_items") or []
    }
    for evidence_id, evidence in sorted(evidence_by_id.items()):
        node_id = f"evidence.{_safe(evidence_id)}"
        nodes[node_id] = _node(node_id, "evidence", evidence_id, evidence)
        source_ids = [str(evidence.get("source_id") or ""), *map(str, evidence.get("source_lineage") or [])]
        for source_id in sorted(set(source_ids) - {""}):
            source_node = f"source.{_safe(source_id)}"
            if source_node not in nodes:
                nodes[source_node] = _node(source_node, "source_reference", source_id, {"source_id": source_id})
            edge_id = f"edge.{_safe(source_id)}.{_safe(evidence_id)}"
            edges[edge_id] = _edge(edge_id, "supports", source_node, node_id)
    orphan_facts = []
    for fact in typed_facts:
        fact_node = f"fact.{_safe(fact.fact_id)}"
        nodes[fact_node] = _node(fact_node, "typed_fact", fact.fact_id, fact.model_dump(mode="json"))
        linked = 0
        for evidence_id in fact.evidence_ids:
            evidence_node = f"evidence.{_safe(evidence_id)}"
            if evidence_node not in nodes:
                continue
            edge_id = f"edge.{_safe(evidence_id)}.{_safe(fact.fact_id)}"
            edges[edge_id] = _edge(edge_id, "evidences", evidence_node, fact_node)
            linked += 1
        if linked == 0:
            orphan_facts.append(fact.fact_id)
    return create_hashed(
        EvidenceGraphIR,
        ticker=ticker,
        as_of_date=as_of_date,
        nodes=tuple(nodes[key] for key in sorted(nodes)),
        edges=tuple(edges[key] for key in sorted(edges)),
        orphan_fact_ids=tuple(sorted(orphan_facts)),
    )


def build_claim_graph(
    *,
    ticker: str,
    as_of_date: str,
    claims: list[dict[str, Any]],
    typed_facts: tuple[TypedFactIR, ...],
    known_evidence_ids: set[str],
    authority: SemanticRegistryAuthority | None = None,
) -> ClaimGraphIR:
    authority = authority or SemanticRegistryAuthority.load()
    facts_by_id = {item.fact_id: item for item in typed_facts if item.role == "reported_or_derived"}
    facts_by_metric = {item.metric_id: item for item in typed_facts if item.role == "reported_or_derived"}
    nodes: dict[str, GraphNodeIR] = {}
    edges: dict[str, GraphEdgeIR] = {}
    missing_definition: list[str] = []
    missing_evidence: list[str] = []
    for claim in sorted(claims, key=lambda item: str(item["claim_id"])):
        claim_id = str(claim["claim_id"])
        try:
            definition_id = authority.bind_claim_kind(str(claim["claim_type"]))
        except ValueError:
            missing_definition.append(claim_id)
            continue
        claim_node = f"claim.{_safe(claim_id)}"
        nodes[claim_node] = _node(claim_node, definition_id, claim_id, claim)
        evidence_ids = sorted(set(map(str, claim.get("evidence_ids") or [])))
        unknown_evidence = sorted(set(evidence_ids) - known_evidence_ids)
        if not evidence_ids or unknown_evidence:
            missing_evidence.append(claim_id)
        for evidence_id in evidence_ids:
            if evidence_id not in known_evidence_ids:
                continue
            evidence_node = f"evidence.{_safe(evidence_id)}"
            nodes.setdefault(evidence_node, _node(evidence_node, "evidence_reference", evidence_id, {"evidence_id": evidence_id}))
            edge_id = f"edge.{_safe(evidence_id)}.{_safe(claim_id)}"
            edges[edge_id] = _edge(edge_id, "supports_claim", evidence_node, claim_node)
        bound_fact_ids = {str(item.get("fact_id")) for item in claim.get("numeric_bindings") or [] if item.get("fact_id")}
        for metric_id in claim.get("metric_refs") or []:
            fact = facts_by_metric.get(str(metric_id))
            if fact:
                bound_fact_ids.add(fact.fact_id)
        for fact_id in sorted(bound_fact_ids):
            fact = facts_by_id.get(fact_id)
            if fact is None:
                raise GraphError(f"claim_references_unknown_fact:{claim_id}:{fact_id}")
            fact_node = f"fact.{_safe(fact_id)}"
            nodes.setdefault(fact_node, _node(fact_node, "typed_fact_reference", fact_id, fact.model_dump(mode="json")))
            edge_id = f"edge.{_safe(fact_id)}.{_safe(claim_id)}"
            edges[edge_id] = _edge(edge_id, "substantiates_claim", fact_node, claim_node)
    return create_hashed(
        ClaimGraphIR,
        ticker=ticker,
        as_of_date=as_of_date,
        nodes=tuple(nodes[key] for key in sorted(nodes)),
        edges=tuple(edges[key] for key in sorted(edges)),
        claims_without_definition=tuple(sorted(missing_definition)),
        claims_without_evidence=tuple(sorted(missing_evidence)),
    )


def build_decision_graph(
    decision_packet: dict[str, Any],
    *,
    authority: SemanticRegistryAuthority | None = None,
) -> DecisionGraphIR:
    authority = authority or SemanticRegistryAuthority.load()
    required_packet_fields = {
        "action_policy",
        "as_of_date",
        "decision_inputs",
        "publication_permission",
        "rating_permission",
        "ticker",
    }
    missing_fields = sorted(required_packet_fields - set(decision_packet))
    if missing_fields:
        raise GraphError(f"decision_packet_fields_missing:{','.join(missing_fields)}")
    permission = decision_packet.get("rating_permission")
    if not isinstance(permission, dict):
        raise GraphError("decision_rating_permission_missing")
    required_permission_fields = {
        "allowed_ratings",
        "blocked_ratings",
        "permission_type",
        "preferred_rating",
        "publication_allowed",
    }
    missing_permission = sorted(required_permission_fields - set(permission))
    if missing_permission:
        raise GraphError(
            f"decision_rating_permission_fields_missing:{','.join(missing_permission)}"
        )
    allowed = permission.get("allowed_ratings")
    blocked = permission.get("blocked_ratings")
    if not isinstance(allowed, list) or not isinstance(blocked, list):
        raise GraphError("decision_permission_corridor_invalid")
    preferred = permission.get("preferred_rating")
    if preferred is not None and preferred not in allowed:
        raise GraphError("decision_preferred_rating_outside_corridor")
    action_policy = decision_packet.get("action_policy")
    if not isinstance(action_policy, dict) or not {
        "actionability",
        "reason",
    }.issubset(action_policy):
        raise GraphError("decision_non_advice_boundary_missing")
    authority.require_permission_definition("permission.rating_corridor")
    nodes: dict[str, GraphNodeIR] = {}
    edges: dict[str, GraphEdgeIR] = {}
    root_id = "decision.root"
    nodes[root_id] = _node(root_id, "decision.root", "decision_packet", decision_packet)
    for item in sorted(decision_packet.get("decision_inputs") or [], key=lambda row: str(row["input_id"])):
        definition_id = authority.bind_decision_input(str(item.get("input_type") or ""))
        if item.get("input_type") == "current_risk":
            authority.require_risk_definition("risk.current_issuer_risk")
        node_id = f"decision.input.{_safe(str(item['input_id']))}"
        nodes[node_id] = _node(node_id, definition_id, str(item["input_id"]), item)
        edge_id = f"edge.{node_id}.root"
        edges[edge_id] = _edge(edge_id, "informs", node_id, root_id)
        if item.get("management_counterposition"):
            counter_id = f"decision.counterevidence.{_safe(str(item['input_id']))}"
            authority.require_decision_definition("decision.counterevidence")
            nodes[counter_id] = _node(counter_id, "decision.counterevidence", str(item["input_id"]), {"text": item["management_counterposition"]})
            edge_id = f"edge.{counter_id}.{node_id}"
            edges[edge_id] = _edge(edge_id, "constrains", counter_id, node_id)
    for index, rule in enumerate(decision_packet.get("triggered_rules") or [], start=1):
        authority.require_decision_definition("decision.rule")
        node_id = f"decision.rule.{index:04d}"
        nodes[node_id] = _node(node_id, "decision.rule", str(rule), {"legacy_rule": rule})
        edges[f"edge.{node_id}.root"] = _edge(f"edge.{node_id}.root", "authorizes", node_id, root_id)
    for key, definition_id in (("key_reasons", "decision.rationale"), ("key_risks", "decision.rationale")):
        authority.require_decision_definition(definition_id)
        for index, text in enumerate(decision_packet.get(key) or [], start=1):
            node_id = f"decision.{_safe(key)}.{index:04d}"
            nodes[node_id] = _node(node_id, definition_id, key, {"text": text})
            edges[f"edge.{node_id}.root"] = _edge(f"edge.{node_id}.root", "explains", node_id, root_id)
    for score_id, value in sorted((decision_packet.get("signal_scores") or {}).items()):
        authority.require_decision_definition("decision.score_contribution")
        node_id = f"decision.score.{_safe(score_id)}"
        nodes[node_id] = _node(node_id, "decision.score_contribution", score_id, {"value": value})
        edges[f"edge.{node_id}.root"] = _edge(f"edge.{node_id}.root", "contributes", node_id, root_id)
    for suffix, definition_id, payload in (
        ("corridor", "decision.permission_corridor", {"allowed_ratings": permission.get("allowed_ratings"), "blocked_ratings": permission.get("blocked_ratings")}),
        ("rating", "decision.rating_permission", permission),
        ("non.advice", "decision.non_advice_boundary", decision_packet.get("action_policy") or {}),
    ):
        authority.require_decision_definition(definition_id)
        node_id = f"decision.{suffix}"
        nodes[node_id] = _node(node_id, definition_id, suffix, payload)
        edges[f"edge.{node_id}.root"] = _edge(f"edge.{node_id}.root", "constrains", node_id, root_id)
    payload = deepcopy(decision_packet)
    payload_hash = sha256_json(payload)
    return create_hashed(
        DecisionGraphIR,
        ticker=str(payload["ticker"]),
        as_of_date=str(payload["as_of_date"]),
        nodes=tuple(nodes[key] for key in sorted(nodes)),
        edges=tuple(edges[key] for key in sorted(edges)),
        legacy_payload=payload,
        legacy_payload_sha256=payload_hash,
        roundtrip_payload_sha256=sha256_json(deepcopy(payload)),
    )


def roundtrip_legacy_decision(graph: DecisionGraphIR) -> dict[str, Any]:
    payload = deepcopy(graph.legacy_payload)
    if sha256_json(payload) != graph.legacy_payload_sha256:
        raise GraphError("decision_roundtrip_payload_tamper")
    if sha256_json(payload) != graph.roundtrip_payload_sha256:
        raise GraphError("decision_roundtrip_loss")
    return payload
