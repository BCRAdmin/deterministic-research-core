from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.semantic_compiler.registry_foundation.authority import (
    AUTHORITY_PATH,
    SemanticRegistryAuthority,
    SemanticRegistryError,
    verify_product_mirror,
)
from research_agent.semantic_compiler.registry_foundation.contracts import (
    ClaimInstance,
    DecisionNodeInstance,
    FormulaInstance,
    MetricInstance,
)
from research_agent.semantic_compiler.registry_foundation.coverage import (
    audit_cross_company,
    formula_instance_from_legacy,
    metric_instance_from_legacy,
)

RESEARCH_ROOT = Path(__file__).resolve().parents[2]
PRODUCT_ROOT = RESEARCH_ROOT.parent / "company-dossier-lab"
CANARY_ROOT = (
    PRODUCT_ROOT
    / ".runtime/cross-company-release-current"
    / "ROOM16_WM_COST_ABT_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448"
)
MIRROR = PRODUCT_ROOT / "config/room16_semantic_registry_mirror_v1_1.json"
LOCK = PRODUCT_ROOT / "config/room16_semantic_registry_mirror_v1_1.lock.json"


def _authority_payload() -> dict[str, object]:
    return json.loads(AUTHORITY_PATH.read_text(encoding="utf-8"))


def _rehash(payload: dict[str, object]) -> dict[str, object]:
    payload["authority_sha256"] = sha256_json(
        {key: value for key, value in payload.items() if key != "authority_sha256"}
    )
    return payload


def _metric_fact(**changes: object) -> dict[str, object]:
    fact: dict[str, object] = {
        "fact_id": "fixture.revenue",
        "metric": "revenue",
        "dimension": "currency",
        "fact_type": "flow_value",
        "display_unit": "USD",
        "period_kind": "duration",
        "source_scale": "million",
        "currency": "USD",
    }
    fact.update(changes)
    return fact


def test_registry_authority_is_research_owned_additive_v1_1() -> None:
    authority = SemanticRegistryAuthority.load()
    assert authority.payload["version"] == "1.1.0"
    assert authority.payload["compatibility"] == "additive_successor_of_1.0.0"
    assert authority.payload["owner"] == "research"
    assert authority.payload["authority_bundle_version"] == 3
    assert len(authority.metric_definitions) == 9
    assert len(authority.formula_definitions) == 23
    assert len(authority.claim_definitions) == 7
    assert len(authority.decision_definitions) == 10


@pytest.mark.parametrize(
    ("legacy_id", "classification"),
    [
        ("revenue", "instance_binding"),
        ("operating_kpi_route_density", "instance_binding"),
        ("event_2026", "quarantined_unknown"),
        ("positional_4", "quarantined_unknown"),
        ("unknown_value", "quarantined_unknown"),
        ("unmapped_value", "quarantined_unknown"),
    ],
)
def test_metric_binding_is_explicit_and_fail_closed(
    legacy_id: str, classification: str
) -> None:
    _, actual = SemanticRegistryAuthority.load().bind_metric(legacy_id)
    assert actual == classification


def test_overlapping_metric_patterns_are_a_semantic_collision() -> None:
    payload = _authority_payload()
    payload["metric_definitions"][1]["instance_patterns"].append("^operating_kpi_.*$")  # type: ignore[index]
    payload["metric_definitions"][1]["instance_patterns"].sort()  # type: ignore[index]
    authority = SemanticRegistryAuthority(_rehash(payload))
    assert authority.bind_metric("operating_kpi_collision")[1] == "semantic_collision"


def test_formula_alias_collision_and_unknown_id_fail_closed() -> None:
    authority = SemanticRegistryAuthority.load()
    with pytest.raises(SemanticRegistryError, match="unknown_formula_id"):
        authority.bind_formula("unknown_formula")
    payload = _authority_payload()
    alias = payload["formula_definitions"][0]["legacy_aliases"][0]  # type: ignore[index]
    payload["formula_definitions"][1]["legacy_aliases"].append(alias)  # type: ignore[index]
    payload["formula_definitions"][1]["legacy_aliases"].sort()  # type: ignore[index]
    payload["formula_definitions"][1]["legacy_operand_contracts"][alias] = copy.deepcopy(  # type: ignore[index]
        payload["formula_definitions"][0]["legacy_operand_contracts"][alias]  # type: ignore[index]
    )
    payload["formula_definitions"][1]["legacy_operand_contracts"] = dict(  # type: ignore[index]
        sorted(payload["formula_definitions"][1]["legacy_operand_contracts"].items())  # type: ignore[index]
    )
    collision = SemanticRegistryAuthority(_rehash(payload))
    with pytest.raises(SemanticRegistryError, match="formula_semantic_collision"):
        collision.bind_formula(alias)


def test_metric_dimension_mismatch_is_blocked() -> None:
    with pytest.raises(SemanticRegistryError, match="metric_contract_mismatch"):
        metric_instance_from_legacy(
            _metric_fact(dimension="duration_weeks"), SemanticRegistryAuthority.load()
        )


def test_formula_operand_and_result_dimension_mismatches_are_blocked() -> None:
    authority = SemanticRegistryAuthority.load()
    base = _metric_fact(
        fact_id="fixture.ratio",
        metric="sbc_to_revenue",
        formula_id="sbc_ttm_divided_by_revenue_ttm",
        formula_operands={"revenue_ttm": 100, "wrong_role": 5},
        dimension="percent",
        value=0.05,
    )
    with pytest.raises(
        SemanticRegistryError,
        match="formula_(required_operand_missing|operand_role_mismatch)",
    ):
        formula_instance_from_legacy(base, authority)
    base["formula_operands"] = {"revenue_ttm": 100, "sbc_ttm": 5}
    base["dimension"] = "multiple"
    with pytest.raises(SemanticRegistryError, match="formula_result_dimension_mismatch"):
        formula_instance_from_legacy(base, authority)


def test_unknown_claim_and_decision_definition_fail_closed() -> None:
    authority = SemanticRegistryAuthority.load()
    with pytest.raises(SemanticRegistryError, match="unknown_claim_kind"):
        authority.bind_claim_kind("invented")
    with pytest.raises(SemanticRegistryError, match="unknown_decision_node"):
        authority.require_decision_definition("decision.invented")


def test_instance_contract_hashes_detect_tampering() -> None:
    metric = metric_instance_from_legacy(_metric_fact(), SemanticRegistryAuthority.load())
    with pytest.raises(ValidationError, match="binding hash mismatch"):
        MetricInstance.model_validate({**metric.model_dump(mode="json"), "dimension": "percent"})
    formula = FormulaInstance.create(
        formula_instance_id="formula.instance.fixture",
        legacy_formula_id="cfo_minus_capex",
        formula_definition_id="formula.fcf",
        operand_fact_ids=("fact.a", "fact.b"),
        parameter_values={"capex_ttm": 1, "operating_cash_flow_ttm": 2},
        evaluation_period="2026",
        result_metric_id="free_cash_flow_ttm",
    )
    with pytest.raises(ValidationError, match="evaluation hash mismatch"):
        FormulaInstance.model_validate(
            {**formula.model_dump(mode="json"), "result_metric_id": "tampered"}
        )
    claim = ClaimInstance.create(
        claim_id="claim.fixture",
        claim_kind_id="claim.financial_metric",
        fact_ids=("fact.b", "fact.a"),
        evidence_ids=("evidence.a",),
        materiality="material",
    )
    with pytest.raises(ValidationError, match="payload hash mismatch"):
        ClaimInstance.model_validate(
            {**claim.model_dump(mode="json"), "materiality": "tampered"}
        )
    decision = DecisionNodeInstance.create(
        node_id="decision.fixture",
        definition_id="decision.rule",
        subject_refs=("subject.b", "subject.a"),
        payload={"value": 1},
    )
    with pytest.raises(ValidationError, match="decision node hash mismatch"):
        DecisionNodeInstance.model_validate(
            {**decision.model_dump(mode="json"), "payload": {"value": 2}}
        )


def test_registry_version_owner_hash_and_foundation_parent_are_locked() -> None:
    for field, value, expected in (
        ("contract_version", 2, "version_unsupported"),
        ("version", "2.0.0", "version_unsupported"),
        ("owner", "product", "owner_or_abi_invalid"),
        ("authority_bundle_version", 4, "owner_or_abi_invalid"),
    ):
        payload = _rehash(_authority_payload())
        payload[field] = value
        payload = _rehash(payload)
        with pytest.raises(SemanticRegistryError, match=expected):
            SemanticRegistryAuthority(payload)
    payload = _authority_payload()
    payload["parent_registry_authority_sha256"] = "0" * 64
    with pytest.raises(SemanticRegistryError, match="hash_mismatch"):
        SemanticRegistryAuthority(payload)


def test_product_mirror_is_exact_and_tamper_fails(tmp_path: Path) -> None:
    result = verify_product_mirror(
        authority_path=AUTHORITY_PATH, mirror_path=MIRROR, lock_path=LOCK
    )
    assert result["status"] == "pass"
    mirror = json.loads(MIRROR.read_text(encoding="utf-8"))
    mirror["owner"] = "product"
    tampered = tmp_path / "mirror.json"
    tampered.write_text(json.dumps(mirror), encoding="utf-8")
    with pytest.raises(SemanticRegistryError, match="product_mirror_conformance_failed"):
        verify_product_mirror(
            authority_path=AUTHORITY_PATH, mirror_path=tampered, lock_path=LOCK
        )


def test_wm_cost_abt_registry_coverage_is_complete_and_archives_unchanged() -> None:
    archives = [
        CANARY_ROOT
        / f"ROOM16_{ticker}_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448.zip"
        for ticker in ("WM", "COST", "ABT")
    ]
    result = audit_cross_company(archives)
    assert result["status"] == "pass"
    assert result["gates"]["registry_identifier_coverage"] == 100
    assert len(result["metric_coverage"]) == 282
    assert len(result["formula_coverage"]) == 32
    assert len(result["claim_kind_coverage"]) == 7
    assert all(item["archive_unchanged"] for item in result["companies"])
