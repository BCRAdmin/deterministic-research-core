"""Finding-specific red/green/reintroduction proofs for RFC-0002."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Callable

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.compiler_foundation.contracts import ProvenanceRef
from research_agent.semantic_compiler.registry_foundation.authority import SemanticRegistryAuthority

from .contracts import ParsedPayloadIR, SourceInputIR, TypedFactSpineIR, create_hashed
from .pass_protocol import load_pass_contracts, validate_pass_contracts
from .semantics import build_claim_graph, build_decision_graph, build_evidence_graph, reconstruct_decision
from .signature_authority import MetricSignatureAuthority
from .table_grammar import discover_tables, parse_payload
from .verification import compute_cross_company_gates


def _fact(signature: Any, **changes: str) -> TypedFactSpineIR:
    values = {
        "fact_id": "FACT_FIXTURE",
        "metric_id": signature.legacy_metric_id,
        "metric_definition_id": signature.metric_definition_id,
        "fact_kind": signature.fact_kind,
        "fact_type": signature.fact_subtype,
        "value_state": "value",
        "value": 1.0,
        "dimension": signature.dimension,
        "unit": signature.unit,
        "currency": signature.currency,
        "scale": signature.scale,
        "period_kind": signature.period_role,
        "period_start": None,
        "period_end": None,
        "source_ids": ("SOURCE_FIXTURE",),
        "evidence_ids": ("EVIDENCE_FIXTURE",),
        "source_locator": "fixture://locator",
        "table_id": None,
        "cell_id": None,
        "normalized_record_sha256": "b" * 64,
    }
    values.update(changes)
    return create_hashed(TypedFactSpineIR, **values)


def _proof(fixture_id: str, finding_id: str, expected_code: str, defective: Any, corrected: Any, evaluator: Callable[[Any], None]) -> dict[str, Any]:
    def run(payload: Any) -> dict[str, Any]:
        try:
            evaluator(payload)
        except Exception as exc:  # fixture evidence intentionally captures the fail-closed surface
            return {"gate_allowed": False, "actual_diagnostic": str(exc), "payload_sha256": sha256_json(payload)}
        return {"gate_allowed": True, "actual_diagnostic": None, "payload_sha256": sha256_json(payload)}

    defective_result = run(defective)
    corrected_result = run(corrected)
    reintroduced_result = run(copy.deepcopy(defective))
    closed = (
        not defective_result["gate_allowed"]
        and corrected_result["gate_allowed"]
        and not reintroduced_result["gate_allowed"]
    )
    return {
        "fixture_id": fixture_id,
        "finding_id": finding_id,
        "expected_diagnostic_code": expected_code,
        "defective": defective,
        "corrected": corrected,
        "reintroduced": copy.deepcopy(defective),
        "defective_result": defective_result,
        "corrected_result": corrected_result,
        "reintroduced_result": reintroduced_result,
        "closure_proven": closed,
    }


def build_negative_fixture_proofs() -> tuple[dict[str, Any], ...]:
    authority = MetricSignatureAuthority.load()
    field_map = {
        "fact_kind": "fact_kind",
        "fact_type": "fact_subtype",
        "period_kind": "period_role",
        "dimension": "dimension",
        "unit": "unit",
        "currency": "currency",
    }
    wrong_cases = {
        "stock_as_period_flow": {"fact_kind": "flow", "fact_type": "period_total", "period_kind": "duration"},
        "absolute_rate_as_yoy_change": {"fact_type": "year_over_year_change", "period_kind": "comparison"},
        "quarterly_rate_as_period_total": {"fact_type": "period_total", "period_kind": "duration"},
        "count_as_currency": {"dimension": "currency", "unit": "USD", "currency": "USD"},
        "guidance_as_historical_actual": {"fact_kind": "guidance_range", "fact_type": "guidance_range", "period_kind": "guidance"},
        "per_share_as_total_cash_flow": {"dimension": "currency", "fact_kind": "flow", "fact_type": "flow_value", "unit": "USD"},
        "percentage_of_total_as_change": {"fact_type": "contribution_to_change", "period_kind": "comparison"},
    }
    proofs: list[dict[str, Any]] = []
    for fixture_id, changes in wrong_cases.items():
        signature = next(
            item for item in authority.signatures.values()
            if any(getattr(item, field_map[key]) != value for key, value in changes.items())
        )
        corrected = _fact(signature).model_dump(mode="json")
        defective = _fact(signature, **changes).model_dump(mode="json")

        def evaluate(payload: dict[str, Any]) -> None:
            authority.require_fact_signature(TypedFactSpineIR.model_validate(payload))

        proofs.append(_proof(
            f"metric.{fixture_id}",
            "SCW-004",
            "METRIC_SIGNATURE_CONTRACT_MISMATCH",
            defective,
            corrected,
            evaluate,
        ))
    pass_payload, _ = load_pass_contracts()
    mutations = {
        "pass.version": lambda value: value.update({"contract_version": 99}),
        "pass.order": lambda value: value["passes"].reverse(),
        "pass.skip": lambda value: value["passes"][0].update({"skippable": True}),
        "pass.ba10": lambda value: value.update({"ba10_authorized": True}),
    }
    for fixture_id, mutate in mutations.items():
        defective = copy.deepcopy(pass_payload)
        mutate(defective)
        proofs.append(_proof(
            fixture_id,
            "SCW-001",
            "PASS_PROTOCOL_CONTRACT_VIOLATION",
            defective,
            pass_payload,
            lambda payload: validate_pass_contracts(payload),
        ))
    source_payload = b"{}"
    source_hash = hashlib.sha256(source_payload).hexdigest()
    source_values = {
        "source_input_id": "compat.fixture",
        "input_kind": "legacy_compatibility",
        "archive_sha256": "a" * 64,
        "member_path": "fixture.json",
        "media_type": "application/json",
        "payload_sha256": source_hash,
        "payload_size": len(source_payload),
        "compatibility_adapter_id": "authority_bundle_v3.fact_ledger",
        "provenance": ProvenanceRef(source_id="compat.fixture", artifact_path="fixture.json", sha256=source_hash, locator="fixture://source").model_dump(mode="json"),
    }
    defective_source = {**source_values, "compatibility_adapter_id": None}
    proofs.append(_proof(
        "spine.unlabelled_legacy_bypass", "SCW-002", "LEGACY_COMPATIBILITY_ADAPTER_REQUIRED",
        defective_source, source_values,
        lambda payload: create_hashed(SourceInputIR, **payload),
    ))

    def evaluate_table(text: str) -> None:
        raw = text.encode()
        digest = hashlib.sha256(raw).hexdigest()
        source = create_hashed(
            SourceInputIR, source_input_id="fixture.table", input_kind="source_snapshot",
            archive_sha256="a" * 64, member_path="fixture.html", media_type="text/html",
            payload_sha256=digest, payload_size=len(raw), compatibility_adapter_id=None,
            provenance=ProvenanceRef(source_id="fixture.table", artifact_path="fixture.html", sha256=digest, locator="fixture://table"),
        )
        discovery = discover_tables(source, parse_payload(source, raw)[1])
        if discovery.registered_count != 1 or discovery.detected_count != discovery.registered_count + discovery.excluded_count:
            raise ValueError("TABLE_GRAMMAR_COVERAGE_INCOMPLETE")

    proofs.append(_proof(
        "table.unregistered_detected_table", "SCW-003", "TABLE_GRAMMAR_COVERAGE_INCOMPLETE",
        "<table><tr><td>only</td></tr></table>",
        "<table><tr><th>Metric</th><th>2026</th></tr><tr><td>Revenue</td><td>10</td></tr></table>",
        evaluate_table,
    ))

    def gate_replay(blocked: bool) -> dict[str, Any]:
        return {
            "metrics": [{"signature_id": "sig.1"}],
            "signatures": [{"signature_id": "sig.1", "legacy_metric_id": "metric.1", "expected_contract_sha256": "a" * 64}],
            "verification_report": {"diagnostics": ([{"code": "BROKEN", "release_effect": "compile_block"}] if blocked else []), "verdict": {"compile_allowed": not blocked}},
            "decision_graph": {"comparison_payload_sha256": "b" * 64, "reconstructed_payload_sha256": "b" * 64},
            "archive_sha256_before": "c" * 64,
            "archive_sha256_after": "c" * 64,
        }

    def evaluate_gate(payload: dict[str, Any]) -> None:
        computed = compute_cross_company_gates(payload["replays"])
        if payload["claimed_status"] != computed["status"] or computed["status"] != "pass":
            raise ValueError("CROSS_COMPANY_GATE_NOT_DERIVED")

    green_replays = {ticker: gate_replay(False) for ticker in ("WM", "COST", "ABT")}
    red_replays = copy.deepcopy(green_replays)
    red_replays["WM"] = gate_replay(True)
    proofs.append(_proof(
        "gates.hardcoded_pass", "SCW-005", "CROSS_COMPANY_GATE_NOT_DERIVED",
        {"replays": red_replays, "claimed_status": "pass"},
        {"replays": green_replays, "claimed_status": "pass"},
        evaluate_gate,
    ))

    def parsed(adapter: str, payload: Any) -> ParsedPayloadIR:
        return create_hashed(
            ParsedPayloadIR, parsed_payload_id=f"parsed.{adapter}", source_input_sha256="d" * 64,
            parser_id="fixture.json@1", payload_kind="json", payload=payload,
            compatibility_adapter_id=adapter,
        )

    fixture_fact = create_hashed(
        TypedFactSpineIR, fact_id="FACT_1", metric_id="close", metric_definition_id="metric.technical",
        fact_kind="instant", fact_type="instant_value", value_state="value", value=10.0,
        dimension="currency", unit="USD", currency="USD", scale="none", period_kind="instant",
        period_start=None, period_end="2026-08-15", source_ids=("SOURCE_1",), evidence_ids=("EVIDENCE_GOOD",),
        source_locator="fixture://source", table_id=None, cell_id=None, normalized_record_sha256="e" * 64,
    )
    source_doc = parsed("authority_bundle_v3.source_registry", {"sources": [{"source_id": "SOURCE_1", "url": "fixture://source"}]})
    evidence_doc = parsed("authority_bundle_v3.evidence_ledger", {"evidence_items": [
        {"evidence_id": "EVIDENCE_GOOD", "source_id": "SOURCE_1", "supports_metrics": ["close"], "value": 10.0, "url": "fixture://source"},
        {"evidence_id": "EVIDENCE_BAD", "source_id": "SOURCE_1", "supports_metrics": ["revenue"], "value": 99.0, "url": "fixture://source"},
    ]})
    evidence_graph = build_evidence_graph(ticker="FIX", as_of_date="2026-08-15", source_registry=source_doc, evidence_ledger=evidence_doc, facts=(fixture_fact,))

    def evaluate_claim(binding_evidence_id: str) -> None:
        claim_doc = parsed("authority_bundle_v3.analyst_claims", [{
            "claim_id": "CLAIM_1", "claim_type": "rating", "evidence_ids": [binding_evidence_id],
            "numeric_bindings": [{"span_id": "CLAIM_1:number-1", "fact_id": "FACT_1", "evidence_id": binding_evidence_id, "source_id": "SOURCE_1", "source_locator": "fixture://source", "metric_id": "close"}],
        }])
        graph = build_claim_graph(
            ticker="FIX", as_of_date="2026-08-15", claims_document=claim_doc,
            evidence_document=evidence_doc, source_document=source_doc, facts=(fixture_fact,),
            evidence_graph=evidence_graph, authority=SemanticRegistryAuthority.load(),
        )
        if graph.numeric_bindings_without_lineage:
            raise ValueError("CLAIM_FACT_EVIDENCE_SOURCE_LOCATOR_LINEAGE_INCOMPLETE")

    proofs.append(_proof(
        "claim.mismatched_evidence", "SCW-006", "CLAIM_FACT_EVIDENCE_SOURCE_LOCATOR_LINEAGE_INCOMPLETE",
        "EVIDENCE_BAD", "EVIDENCE_GOOD", evaluate_claim,
    ))

    decision_good = {
        "ticker": "FIX", "as_of_date": "2026-08-15",
        "action_policy": {"actionability": "none", "reason": "fixture"},
        "decision_inputs": [{"input_id": "risk-1", "input_type": "current_risk", "value": 2}],
        "publication_permission": False,
        "rating_permission": {"allowed_ratings": ["Hold"], "blocked_ratings": ["Buy"], "permission_type": "corridor", "preferred_rating": "Hold", "publication_allowed": False},
    }
    decision_bad = {key: value for key, value in decision_good.items() if key != "rating_permission"}

    def evaluate_decision(payload: dict[str, Any]) -> None:
        raw = json.dumps(payload).encode(); digest = hashlib.sha256(raw).hexdigest()
        source = create_hashed(
            SourceInputIR, source_input_id="compat.decision", input_kind="legacy_compatibility",
            archive_sha256="a" * 64, member_path="decision.json", media_type="application/json",
            payload_sha256=digest, payload_size=len(raw), compatibility_adapter_id="authority_bundle_v3.decision_packet",
            provenance=ProvenanceRef(source_id="compat.decision", artifact_path="decision.json", sha256=digest, locator="fixture://decision"),
        )
        document = parse_payload(source, raw)[0]
        graph = build_decision_graph(document, source, SemanticRegistryAuthority.load())
        if reconstruct_decision(graph) != payload:
            raise ValueError("DECISION_GRAPH_ROUNDTRIP_LOSS")

    proofs.append(_proof(
        "decision.missing_permission_graph", "SCW-007", "DECISION_GRAPH_ROUNDTRIP_LOSS",
        decision_bad, decision_good, evaluate_decision,
    ))
    return tuple(proofs)
