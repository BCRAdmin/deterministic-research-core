from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.compiler_foundation.contracts import CompileVerdictIR, ProvenanceRef
from research_agent.semantic_compiler.registry_foundation.authority import SemanticRegistryAuthority
from research_agent.semantic_compiler.semantic_spine.contracts import (
    SourceInputIR,
    TypedFactSpineIR,
    VerificationReportIR,
    create_hashed,
)
from research_agent.semantic_compiler.semantic_spine.pass_protocol import (
    RFC0002PassProtocolError,
    load_pass_contracts,
    validate_pass_contracts,
)
from research_agent.semantic_compiler.semantic_spine.negative_fixtures import build_negative_fixture_proofs
from research_agent.semantic_compiler.semantic_spine.semantics import (
    build_decision_graph,
    reconstruct_decision,
)
from research_agent.semantic_compiler.semantic_spine.signature_authority import (
    MetricSignatureAuthority,
    MetricSignatureAuthorityError,
)
from research_agent.semantic_compiler.semantic_spine.table_grammar import (
    TableGrammarError,
    discover_tables,
    parse_payload,
)
from research_agent.semantic_compiler.semantic_spine.verification import compute_cross_company_gates


def _source(payload: bytes, *, media_type: str = "text/html", adapter: str | None = None) -> SourceInputIR:
    digest = hashlib.sha256(payload).hexdigest()
    return create_hashed(
        SourceInputIR,
        source_input_id="fixture.source",
        input_kind="legacy_compatibility" if adapter else "source_snapshot",
        archive_sha256="a" * 64,
        member_path="fixture.json" if "json" in media_type else "fixture.html",
        media_type=media_type,
        payload_sha256=digest,
        payload_size=len(payload),
        compatibility_adapter_id=adapter,
        provenance=ProvenanceRef(source_id="fixture.source", artifact_path="fixture", sha256=digest, locator="fixture://source"),
    )


def _fact_for_signature(signature, **changes):
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


def test_rfc_0002_pass_protocol_has_real_l10_and_is_fail_closed() -> None:
    payload, result = load_pass_contracts()
    assert result["pass_count"] == 10
    assert result["pass_ids"][-1] == "ba9.l10.verify_semantics"
    assert result["ba10_authorized"] is False
    for mutation in (
        lambda item: item.update({"ba10_authorized": True}),
        lambda item: item["passes"].reverse(),
        lambda item: item["passes"][0].update({"skippable": True}),
        lambda item: item.update({"contract_version": 99}),
    ):
        defective = copy.deepcopy(payload)
        mutation(defective)
        with pytest.raises(RFC0002PassProtocolError):
            validate_pass_contracts(defective)


def test_ba4_html_grammar_handles_multiheader_merged_sparse_and_value_states() -> None:
    payload = b"""<table><caption>Income Statement USD millions</caption>
    <tr><th rowspan='2'>Metric</th><th colspan='2'>Fiscal year</th></tr>
    <tr><th>2025</th><th>2026</th></tr>
    <tr><th>Revenue</th><td>1,200</td><td>0</td></tr>
    <tr><th>Operating income</th><td>&mdash;</td><td>N/A</td></tr></table>"""
    source = _source(payload)
    parsed, candidates = parse_payload(source, payload)
    discovery = discover_tables(source, candidates)
    assert parsed.payload_kind == "html"
    assert discovery.detected_count == discovery.registered_count + discovery.excluded_count == 1
    table = discovery.tables[0]
    assert table.header_depth == 2
    assert table.merged_cells_expanded is True
    assert table.sparse is False
    assert {cell.value_state for cell in table.cells} >= {"value", "zero", "dash", "not_applicable"}
    assert all(cell.locator.locator for cell in table.cells)


def test_ba4_transposed_and_explicit_exclusion_are_deterministic() -> None:
    payload = json.dumps({"table": [["Period", "Revenue", "Margin"], ["2025", 10, 0.2], ["2026", 12, 0.21]], "tiny": [["x"]]}).encode()
    source = _source(payload, media_type="application/json")
    first = discover_tables(source, parse_payload(source, payload)[1])
    second = discover_tables(source, parse_payload(source, payload)[1])
    assert first == second
    assert first.detected_count == 2
    assert first.registered_count == 1
    assert first.excluded_count == 1
    assert first.tables[0].orientation == "transposed"
    assert first.dispositions[1].exclusion_code == "TABLE_TOO_SMALL"


def test_ba4_tamper_blocks_before_parse() -> None:
    source = _source(b"{}", media_type="application/json")
    with pytest.raises(TableGrammarError, match="source_payload_hash_mismatch"):
        parse_payload(source, b'{"tampered":true}')


@pytest.mark.parametrize(
    "changes",
    [
        {"fact_kind": "flow", "fact_type": "period_total", "period_kind": "duration"},
        {"fact_type": "year_over_year_change", "period_kind": "comparison"},
        {"fact_type": "period_total", "period_kind": "duration"},
        {"dimension": "currency", "unit": "USD", "currency": "USD"},
        {"fact_kind": "guidance_range", "fact_type": "guidance_range", "period_kind": "guidance"},
        {"dimension": "currency", "fact_kind": "flow", "fact_type": "flow_value", "unit": "USD"},
        {"fact_type": "contribution_to_change", "period_kind": "comparison"},
    ],
    ids=[
        "stock_as_flow",
        "absolute_rate_as_yoy_change",
        "quarterly_rate_as_period_total",
        "count_as_currency",
        "historical_actual_as_guidance",
        "per_share_as_total_cash_flow",
        "percentage_of_total_as_change",
    ],
)
def test_valid_but_semantically_wrong_metric_combinations_fail_closed(changes: dict[str, str]) -> None:
    authority = MetricSignatureAuthority.load()
    signature_fields = {
        "fact_kind": "fact_kind",
        "fact_type": "fact_subtype",
        "period_kind": "period_role",
        "dimension": "dimension",
        "unit": "unit",
        "currency": "currency",
    }
    signature = next(
        item for item in authority.signatures.values()
        if any(getattr(item, signature_fields[key]) != value for key, value in changes.items())
    )
    valid = _fact_for_signature(signature)
    assert authority.require_fact_signature(valid) == signature
    defective = _fact_for_signature(signature, **changes)
    with pytest.raises(MetricSignatureAuthorityError, match="metric_signature_contract_mismatch"):
        authority.require_fact_signature(defective)


def test_decision_roundtrip_is_reconstructed_from_nodes_and_edges() -> None:
    payload = {
        "ticker": "FIX",
        "as_of_date": "2026-08-15",
        "action_policy": {"actionability": "none", "reason": "fixture"},
        "decision_inputs": [{"input_id": "risk-1", "input_type": "current_risk", "value": 2}],
        "publication_permission": False,
        "rating_permission": {"allowed_ratings": ["Hold"], "blocked_ratings": ["Buy"], "permission_type": "corridor", "preferred_rating": "Hold", "publication_allowed": False},
    }
    raw = json.dumps(payload).encode()
    source = _source(raw, media_type="application/json", adapter="authority_bundle_v3.decision_packet")
    parsed, _ = parse_payload(source, raw)
    graph = build_decision_graph(parsed, source, SemanticRegistryAuthority.load())
    assert reconstruct_decision(graph) == payload
    assert not hasattr(graph, "legacy_payload")
    defective = graph.model_dump(mode="json")
    defective["edges"][0]["to_node_id"] = "unknown.node"
    defective.pop("ir_sha256")
    defective_graph = type(graph).model_validate({**defective, "ir_sha256": sha256_json(defective)})
    with pytest.raises(ValueError, match="decision_edge_endpoint_unknown"):
        reconstruct_decision(defective_graph)


def test_verification_report_rejects_a_manually_green_verdict() -> None:
    # A report with no diagnostics has a uniquely derivable verdict. Any other
    # manually supplied result must be rejected by the IR contract.
    bad = CompileVerdictIR(
        compile_allowed=False,
        release_allowed=False,
        review_required=True,
        diagnostic_codes=(),
        blocking_codes=(),
        diagnostics_sha256=sha256_json([]),
    )
    with pytest.raises(ValidationError, match="derived only from diagnostics"):
        create_hashed(
            VerificationReportIR,
            ticker="FIX",
            as_of_date="2026-08-15",
            verification_plan_sha256="c" * 64,
            diagnostics=(),
            verdict=bad,
        )


def test_cross_company_gates_are_computed_from_bound_artifacts() -> None:
    def replay(ticker: str, *, blocked: bool = False):
        return {
            "metrics": [{"signature_id": "sig.1"}],
            "signatures": [{"signature_id": "sig.1", "legacy_metric_id": "metric.1", "expected_contract_sha256": "a" * 64}],
            "verification_report": {"diagnostics": ([{"code": "BROKEN", "release_effect": "compile_block"}] if blocked else []), "verdict": {"compile_allowed": not blocked}},
            "decision_graph": {"comparison_payload_sha256": "b" * 64, "reconstructed_payload_sha256": "b" * 64},
            "archive_sha256_before": "c" * 64,
            "archive_sha256_after": "c" * 64,
        }
    green = compute_cross_company_gates({ticker: replay(ticker) for ticker in ("WM", "COST", "ABT")})
    assert green["status"] == "pass"
    red = compute_cross_company_gates({"WM": replay("WM", blocked=True), "COST": replay("COST"), "ABT": replay("ABT")})
    assert red["status"] == "fail"
    assert red["blocking_diagnostic_count"] == 1


def test_finding_specific_fixture_proofs_are_red_green_and_reintroduction_safe() -> None:
    proofs = build_negative_fixture_proofs()
    assert len(proofs) == 16
    for proof in proofs:
        assert proof["defective_result"]["gate_allowed"] is False
        assert proof["corrected_result"]["gate_allowed"] is True
        assert proof["reintroduced_result"]["gate_allowed"] is False
        assert proof["closure_proven"] is True
