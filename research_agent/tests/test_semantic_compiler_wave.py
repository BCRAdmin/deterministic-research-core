from __future__ import annotations

import copy
import hashlib
import json
import zipfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.semantic_compiler.registry_foundation.authority import (
    SemanticRegistryAuthority,
    SemanticRegistryError,
)
from research_agent.semantic_compiler.semantic_wave.contracts import DecisionGraphIR
from research_agent.semantic_compiler.semantic_wave.graphs import (
    GraphError,
    build_claim_graph,
    build_decision_graph,
    build_evidence_graph,
    roundtrip_legacy_decision,
)
from research_agent.semantic_compiler.semantic_wave.legacy_replay import (
    replay_semantic_wave_archive,
)
from research_agent.semantic_compiler.semantic_wave.metrics import (
    FormulaEvaluationError,
    build_metrics_and_evaluations,
    evaluate_legacy_formula,
)
from research_agent.semantic_compiler.semantic_wave.parser import ParserError, parse_artifact
from research_agent.semantic_compiler.semantic_wave.pass_protocol import (
    PASS_CONTRACT_PATH,
    SemanticPassProtocolError,
    load_semantic_pass_contracts,
    validate_semantic_pass_contracts,
)
from research_agent.semantic_compiler.semantic_wave.release_gates import (
    SemanticReleaseGateError,
    assert_no_canary_specific_registry_branch,
)
from research_agent.semantic_compiler.semantic_wave.typed_facts import (
    TypedFactError,
    build_typed_facts,
)

RESEARCH_ROOT = Path(__file__).resolve().parents[2]
PRODUCT_ROOT = RESEARCH_ROOT.parent / "company-dossier-lab"
CANARY_ROOT = (
    PRODUCT_ROOT
    / ".runtime/cross-company-release-current"
    / "ROOM16_WM_COST_ABT_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448"
)
EXPECTED_CANARY_HASHES = {
    "WM": "a6b6d15ad7004573a56ad057884563cfbeeb2c3162dae0641a1b361b5e416d72",
    "COST": "b97e6024855c7a772713ff9af4889987e4a9a8e5a3afca0d56a42a1ba8092ea4",
    "ABT": "0926d3cafd312556ec267b2b25214d255ff9352daed77a01b7852addbb48dc45",
}


def _fact(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "fact_id": "fact.fixture.fcf",
        "metric": "free_cash_flow_ttm",
        "value": 70.0,
        "signed_value": 70.0,
        "dimension": "currency",
        "fact_type": "flow_value",
        "display_unit": "USD",
        "currency": "USD",
        "source_scale": "million",
        "period_kind": "trailing_twelve_months",
        "period_start": "2025-07-01",
        "period_end": "2026-06-30",
        "source_ids": ["SEC_FIXTURE"],
        "evidence_ids": ["EVIDENCE_FIXTURE"],
        "formula_id": "cfo_minus_capex",
        "formula_operands": {
            "capex_ttm": 30.0,
            "operating_cash_flow_ttm": 100.0,
        },
    }
    value.update(changes)
    return value


def _decision_packet(ticker: str = "WM") -> dict[str, object]:
    archive = (
        CANARY_ROOT
        / f"ROOM16_{ticker}_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448.zip"
    )
    with zipfile.ZipFile(archive) as bundle:
        name = next(
            value
            for value in bundle.namelist()
            if value.endswith("/authority_bundle/decision_packet.json")
        )
        return json.loads(bundle.read(name))


def test_ba4_json_parser_and_table_discovery_are_deterministic() -> None:
    payload = json.dumps({"rows": [{"amount": 0, "name": "A"}, {"amount": None}]}).encode()
    source_hash = hashlib.sha256(payload).hexdigest()
    first = parse_artifact(
        source_snapshot_sha256="a" * 64,
        snapshot_id="fixture-json",
        artifact_path="fixture.json",
        source_sha256=source_hash,
        media_type="application/json",
        payload=payload,
    )
    second = parse_artifact(
        source_snapshot_sha256="a" * 64,
        snapshot_id="fixture-json",
        artifact_path="fixture.json",
        source_sha256=source_hash,
        media_type="application/json",
        payload=payload,
    )
    assert first == second
    assert len(first[1]) == 1
    states = {cell.value_state for cell in first[1][0].cells}
    assert {"zero", "missing", "value"}.issubset(states)


def test_ba4_parser_blocks_tamper_and_malformed_input() -> None:
    with pytest.raises(ParserError, match="source_payload_hash_mismatch"):
        parse_artifact(
            source_snapshot_sha256="a" * 64,
            snapshot_id="fixture",
            artifact_path="fixture.json",
            source_sha256="0" * 64,
            media_type="application/json",
            payload=b"{}",
        )
    payload = b"{"
    with pytest.raises(ParserError, match="malformed_json"):
        parse_artifact(
            source_snapshot_sha256="a" * 64,
            snapshot_id="fixture",
            artifact_path="fixture.json",
            source_sha256=hashlib.sha256(payload).hexdigest(),
            media_type="application/json",
            payload=payload,
        )


def test_ba5_typed_fact_ir_is_deterministic_and_definition_bound() -> None:
    first = build_typed_facts([_fact()])
    second = build_typed_facts([_fact()])
    assert first == second
    normalized, typed = first
    assert len(normalized) == 3
    assert len(typed) == 3
    result = next(item for item in typed if item.role == "reported_or_derived")
    assert result.metric_definition_id == "metric.core_financial"
    assert result.normalized_record_sha256


def test_ba5_blocks_value_state_collision_unknown_metric_and_duplicate_fact() -> None:
    with pytest.raises(TypedFactError, match="value_state_collision"):
        build_typed_facts([_fact(is_zero=True, is_missing=True)])
    with pytest.raises(TypedFactError, match="unexecutable_metric"):
        build_typed_facts([_fact(metric="event_unmapped")])
    duplicate = _fact(value=71.0, signed_value=71.0)
    with pytest.raises(TypedFactError, match="conflicting_duplicate_fact"):
        build_typed_facts([_fact(), duplicate])


def test_ba6_formula_engine_reproduces_and_blocks_reintroduced_error() -> None:
    facts = [_fact()]
    _, typed = build_typed_facts(facts)
    metrics, evaluations, markers = build_metrics_and_evaluations(facts, typed)
    assert len(metrics) == 1
    assert len(evaluations) == 1
    assert not markers
    assert evaluations[0].expected_value == evaluations[0].evaluated_value == 70.0
    broken = [_fact(value=71.0, signed_value=71.0)]
    _, broken_typed = build_typed_facts(broken)
    with pytest.raises(FormulaEvaluationError, match="formula_result_mismatch"):
        build_metrics_and_evaluations(broken, broken_typed)
    with pytest.raises(FormulaEvaluationError, match="zero_division"):
        evaluate_legacy_formula(
            "current_assets_divided_by_current_liabilities",
            {"current_assets": 1, "current_liabilities": 0},
            fact_context={},
        )


def test_ba7_evidence_graph_detects_orphan_facts() -> None:
    _, typed = build_typed_facts([_fact(formula_id=None, formula_operands=None)])
    complete = build_evidence_graph(
        ticker="FIX",
        as_of_date="2026-08-15",
        source_registry={"sources": [{"source_id": "SEC_FIXTURE"}]},
        evidence_ledger={
            "evidence_items": [
                {"evidence_id": "EVIDENCE_FIXTURE", "source_id": "SEC_FIXTURE"}
            ]
        },
        typed_facts=typed,
    )
    assert not complete.orphan_fact_ids
    orphan = build_evidence_graph(
        ticker="FIX",
        as_of_date="2026-08-15",
        source_registry={"sources": []},
        evidence_ledger={"evidence_items": []},
        typed_facts=typed,
    )
    assert orphan.orphan_fact_ids == ("fact.fixture.fcf",)


def test_ba8_claim_graph_requires_kind_evidence_and_known_facts() -> None:
    _, typed = build_typed_facts([_fact(formula_id=None, formula_operands=None)])
    base = {
        "claim_id": "CLAIM_FIXTURE",
        "claim_type": "financial_metric",
        "evidence_ids": ["EVIDENCE_FIXTURE"],
        "numeric_bindings": [{"fact_id": "fact.fixture.fcf"}],
    }
    graph = build_claim_graph(
        ticker="FIX",
        as_of_date="2026-08-15",
        claims=[base],
        typed_facts=typed,
        known_evidence_ids={"EVIDENCE_FIXTURE"},
    )
    assert not graph.claims_without_definition
    assert not graph.claims_without_evidence
    unknown_kind = build_claim_graph(
        ticker="FIX",
        as_of_date="2026-08-15",
        claims=[{**base, "claim_type": "invented"}],
        typed_facts=typed,
        known_evidence_ids={"EVIDENCE_FIXTURE"},
    )
    assert unknown_kind.claims_without_definition == ("CLAIM_FIXTURE",)
    missing_evidence = build_claim_graph(
        ticker="FIX",
        as_of_date="2026-08-15",
        claims=[{**base, "evidence_ids": ["UNKNOWN_EVIDENCE"]}],
        typed_facts=typed,
        known_evidence_ids={"EVIDENCE_FIXTURE"},
    )
    assert missing_evidence.claims_without_evidence == ("CLAIM_FIXTURE",)
    with pytest.raises(GraphError, match="claim_references_unknown_fact"):
        build_claim_graph(
            ticker="FIX",
            as_of_date="2026-08-15",
            claims=[{**base, "numeric_bindings": [{"fact_id": "unknown"}]}],
            typed_facts=typed,
            known_evidence_ids={"EVIDENCE_FIXTURE"},
        )


def test_ba9_decision_graph_roundtrip_and_permission_corridor_are_fail_closed() -> None:
    packet = _decision_packet()
    graph = build_decision_graph(packet)
    assert roundtrip_legacy_decision(graph) == packet
    assert graph.permission_corridor_preserved
    assert graph.rating_permission_preserved
    assert graph.non_advice_boundary_preserved
    broken = copy.deepcopy(packet)
    del broken["rating_permission"]["allowed_ratings"]
    with pytest.raises(GraphError, match="rating_permission_fields_missing"):
        build_decision_graph(broken)
    broken = copy.deepcopy(packet)
    broken["decision_inputs"][0]["input_type"] = "invented"
    with pytest.raises(SemanticRegistryError, match="unknown_decision_input_kind"):
        build_decision_graph(broken)
    broken = copy.deepcopy(packet)
    broken["action_policy"] = {}
    with pytest.raises(GraphError, match="non_advice_boundary_missing"):
        build_decision_graph(broken)
    tampered = DecisionGraphIR.model_construct(
        **{
            **graph.model_dump(mode="python"),
            "legacy_payload": {**packet, "ticker": "TAMPERED"},
        }
    )
    with pytest.raises(GraphError, match="decision_roundtrip_payload_tamper"):
        roundtrip_legacy_decision(tampered)


def test_semantic_pass_protocol_order_version_skip_registry_and_ba10_fail_closed() -> None:
    payload, result = load_semantic_pass_contracts()
    assert result["status"] == "pass"
    assert result["pass_count"] == 9
    mutations = [
        ("version", lambda value: value.update(contract_version=2), "version"),
        ("order", lambda value: value["passes"].reverse(), "order"),
        ("skip", lambda value: value["passes"][0].update(skippable=True), "skip"),
        (
            "unknown-registry",
            lambda value: value["passes"][0]["registry_dependencies"].append(
                "product.parallel.truth"
            ),
            "unknown_registry",
        ),
        ("tamper", lambda value: value["passes"][0].update(side_effect_contract="write"), "side_effect"),
        ("ba10", lambda value: value.update(ba10_authorized=True), "ba10_not_authorized"),
    ]
    for _, mutate, message in mutations:
        candidate = copy.deepcopy(payload)
        mutate(candidate)
        with pytest.raises(SemanticPassProtocolError, match=message):
            validate_semantic_pass_contracts(candidate)
    assert sha256_json(json.loads(PASS_CONTRACT_PATH.read_text())) == result["pass_contracts_sha256"]


def test_canary_specific_registry_branch_is_blocked() -> None:
    authority = SemanticRegistryAuthority.load()
    assert_no_canary_specific_registry_branch(authority.payload)
    candidate = copy.deepcopy(authority.payload)
    candidate["metric_definitions"][0]["definition_id"] = "metric.wm.special_case"
    with pytest.raises(SemanticReleaseGateError, match="canary_specific_registry_branch"):
        assert_no_canary_specific_registry_branch(candidate)


@pytest.mark.parametrize("ticker", ["WM", "COST", "ABT"])
def test_wm_cost_abt_semantic_wave_shadow_replay_passes_without_output_change(
    ticker: str, tmp_path: Path
) -> None:
    archive = (
        CANARY_ROOT
        / f"ROOM16_{ticker}_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448.zip"
    )
    result = replay_semantic_wave_archive(archive=archive, work_root=tmp_path / ticker)
    assert result["archive_sha256_before"] == EXPECTED_CANARY_HASHES[ticker]
    assert result["archive_sha256_after"] == EXPECTED_CANARY_HASHES[ticker]
    assert all(result["gates"].values())
    assert result["ba9"]["roundtrip_sha256"] == result["ba9"]["legacy_payload_sha256"]
    assert result["gates"]["ba10_not_started"] is True
