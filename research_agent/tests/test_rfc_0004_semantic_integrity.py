from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from research_agent.compiler_foundation.contracts import CompilerLayer, IREnvelope, ProvenanceRef
from research_agent.compiler_foundation.kernel import PassKernel, identity_shadow_pass, load_pass_manifests
from research_agent.compiler_foundation.registry import RegistryAuthority
from research_agent.semantic_compiler.semantic_spine.contracts import SourceInputIR, create_hashed
from research_agent.semantic_compiler.semantic_spine.rfc_0003 import PASS_MANIFEST_PATH, RFC0004_INVARIANTS
from research_agent.semantic_compiler.semantic_spine.rfc_0004_contracts import (
    ExpectedFormulaRoleContractIR,
    FormulaOperandBindingIR,
    SemanticRegistryLockIR,
)
from research_agent.semantic_compiler.semantic_spine.table_grammar import parse_payload


def _lock(*, signature_hash: str) -> SemanticRegistryLockIR:
    return create_hashed(
        SemanticRegistryLockIR,
        semantic_registry_authority_sha256="a" * 64,
        metric_signature_authority_sha256=signature_hash,
        formula_policy_sha256="c" * 64,
        evidence_policy_sha256="d" * 64,
        claim_policy_sha256="e" * 64,
        decision_policy_sha256="f" * 64,
        pass_manifest_sha256="1" * 64,
        compiler_implementation_commit="2" * 40,
        compiler_implementation_version="4.0.0-rfc0004",
        compiler_implementation_sha256="3" * 64,
    )


def test_changed_semantic_registry_lock_invalidates_every_kernel_cache_key() -> None:
    manifests = load_pass_manifests(PASS_MANIFEST_PATH)
    kernel = PassKernel(manifests, RegistryAuthority.load())
    implementations = {item.pass_id: identity_shadow_pass for item in manifests}

    def envelope(lock: SemanticRegistryLockIR) -> IREnvelope:
        return IREnvelope.create(
            ir_type="semantic_compile_state.source_inputs",
            layer=CompilerLayer.L2_SOURCE_SNAPSHOT,
            producer_pass_id="fixture.load",
            payload={"source_inputs": [{"id": "same-source"}], "semantic_registry_lock": lock.model_dump(mode="json")},
        )

    _, first = kernel.execute(envelope(_lock(signature_hash="b" * 64)), implementations)
    _, cached = kernel.execute(envelope(_lock(signature_hash="b" * 64)), implementations)
    _, changed = kernel.execute(envelope(_lock(signature_hash="4" * 64)), implementations)
    assert all(item.status.value == "executed" for item in first)
    assert all(item.status.value == "cache_hit" for item in cached)
    assert all(item.status.value == "executed" for item in changed)
    assert [item.cache_key for item in first] != [item.cache_key for item in changed]


def test_formula_operand_cannot_claim_fact_binding_without_own_provenance() -> None:
    expected = create_hashed(
        ExpectedFormulaRoleContractIR,
        formula_definition_id="formula.current_ratio",
        legacy_formula_id="current_assets_divided_by_current_liabilities",
        role="current_assets", expected_dimension="currency",
        allowed_role_patterns=(r"^(current_assets|current_liabilities)$",),
        required=True, min_cardinality=2, max_cardinality=2,
    )
    body = {
        "operand_id": "operand.current_assets", "formula_instance_id": "formula.fixture",
        "result_fact_id": "FACT_RESULT", "role": "current_assets",
        "expected_role_contract": expected, "operand_fact_or_parameter_id": "FACT_CURRENT_ASSETS",
        "binding_kind": "typed_fact", "value": 10.0, "dimension": "currency", "unit": "USD",
        "currency": "USD", "scale": "ones", "period_kind": "instant",
        "period_start": None, "period_end": "2026-06-30", "source_ids": (),
        "evidence_ids": (), "source_locators": (), "origin_mode": "existing_typed_fact",
    }
    with pytest.raises(ValidationError, match="requires source and evidence lineage"):
        create_hashed(FormulaOperandBindingIR, **body)


def test_parenthesized_percent_is_parsed_as_negative_percent() -> None:
    payload = b"metric,value\nNutrition,(3.6)%\n"
    source = create_hashed(
        SourceInputIR,
        source_input_id="fixture.csv", input_kind="source_snapshot",
        archive_sha256="a" * 64, member_path="fixture.csv", media_type="text/csv",
        payload_sha256=__import__("hashlib").sha256(payload).hexdigest(), payload_size=len(payload),
        compatibility_adapter_id=None,
        provenance=ProvenanceRef(source_id="fixture.csv", artifact_path="fixture.csv", sha256=__import__("hashlib").sha256(payload).hexdigest(), locator="fixture://csv"),
    )
    _, candidates = parse_payload(source, payload)
    from research_agent.semantic_compiler.semantic_spine.table_grammar import discover_tables

    table = discover_tables(source, candidates).tables[0]
    values = [cell.normalized_value for cell in table.cells]
    assert any(isinstance(value, float) and math.isclose(value, -0.036) for value in values)


def test_rfc_0004_verification_contract_has_real_lineage_gates_only() -> None:
    assert {
        "CANONICAL_TABLE_ARTIFACTS_RESOLVABLE",
        "DECLARED_TABLE_CELL_LINEAGE_COMPLETE",
        "EXECUTABLE_FACT_TABLE_LINEAGE_COMPLETE",
        "DECISION_CLAIM_LINEAGE_COMPLETE",
        "DECISION_FACT_LINEAGE_COMPLETE",
        "DECISION_SCORE_INPUTS_BOUND",
        "DECISION_RISK_COUNTEREVIDENCE_BOUND",
    }.issubset(RFC0004_INVARIANTS)
    assert "PASS_KERNEL_EXECUTION_COMPLETE" not in RFC0004_INVARIANTS
    assert "FIXTURE_DIAGNOSTIC_CODES_STABLE" not in RFC0004_INVARIANTS
