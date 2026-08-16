from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

import pytest
from pydantic import ValidationError

from research_agent.compiler_foundation.kernel import load_pass_manifests
from research_agent.semantic_compiler.semantic_spine.negative_fixtures import build_negative_fixture_proofs
from research_agent.semantic_compiler.semantic_spine.rfc_0003 import (
    PASS_MANIFEST_PATH,
    REQUIRED_EVIDENCE_NODE_KINDS,
    RFC0003_INVARIANTS,
    replay_rfc_0003_archive,
)
from research_agent.semantic_compiler.semantic_spine.rfc_0003_contracts import (
    FormulaOperandIR,
    SemanticCompileStateIR,
)

PRODUCT_ROOT = Path(__file__).resolve().parents[3] / "company-dossier-lab"
CANARY_ROOT = PRODUCT_ROOT / ".runtime/cross-company-release-current/ROOM16_WM_COST_ABT_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448"
EXPECTED_CANARY_HASHES = {
    "ROOM16_WM_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448.zip": "a6b6d15ad7004573a56ad057884563cfbeeb2c3162dae0641a1b361b5e416d72",
    "ROOM16_COST_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448.zip": "b97e6024855c7a772713ff9af4889987e4a9a8e5a3afca0d56a42a1ba8092ea4",
    "ROOM16_ABT_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448.zip": "0926d3cafd312556ec267b2b25214d255ff9352daed77a01b7852addbb48dc45",
}


def test_rfc_0003_pass_manifests_are_one_linear_foundation_kernel_chain() -> None:
    manifests = load_pass_manifests(PASS_MANIFEST_PATH)
    assert len(manifests) == 10
    assert [item.ordinal for item in manifests] == list(range(4, 14))
    assert manifests[-1].pass_id == "ba9.l10.verify_semantics"
    assert all(not item.skippable for item in manifests)
    assert all(item.pass_version == 3 for item in manifests)
    for left, right in zip(manifests, manifests[1:], strict=False):
        assert left.output_ir_type in right.input_ir_types


def test_replay_has_no_manual_semantic_orchestrator() -> None:
    source = inspect.getsource(replay_rfc_0003_archive)
    assert ".execute(" in source
    for forbidden in (
        "_parse_sources(", "_discover_tables(", "_normalize(", "_build_facts(",
        "_build_metric_instances(", "_evaluate_formulas(",
        "_build_complete_evidence_graph(", "_build_claims(",
        "_build_semantic_decision(", "\n    _verification(",
    ):
        assert forbidden not in source


def test_all_legacy_negative_fixtures_publish_exact_stable_codes() -> None:
    proofs = build_negative_fixture_proofs()
    assert len(proofs) == 16
    assert all(item["closure_proven"] for item in proofs)
    assert all(item["defective_exact_code_match"] for item in proofs)
    assert all(item["reintroduced_exact_code_match"] for item in proofs)


def test_formula_operand_and_compile_state_hashes_fail_closed_on_tamper() -> None:
    values = {
        "operand_id": "formula.fixture.operand.revenue",
        "formula_instance_id": "formula.fixture",
        "result_fact_id": "FACT_RESULT",
        "role": "revenue",
        "value": 10.0,
        "dimension": "currency",
        "unit": "USD",
        "currency": "USD",
        "scale": "ones",
        "period_kind": "duration",
        "period_start": "2026-01-01",
        "period_end": "2026-06-30",
        "source_ids": ("SOURCE",),
        "evidence_ids": ("EVIDENCE",),
        "source_locator": "fixture://source",
        "source_input_sha256": "a" * 64,
        "parsed_payload_sha256": "b" * 64,
        "normalized_record_sha256": "c" * 64,
        "origin_mode": "compatibility_embedded_operand",
        "ir_sha256": "d" * 64,
    }
    with pytest.raises(ValidationError, match="IR hash mismatch"):
        FormulaOperandIR.model_validate(values)
    state = {
        "stage": "fixture", "ticker": "FIX", "as_of_date": "2026-08-16",
        "archive_name": "fixture.zip", "archive_sha256": "a" * 64,
        "artifacts": {"fixture": {"value": 1}},
        "artifact_sha256s": {"fixture": "b" * 64}, "ir_sha256": "c" * 64,
    }
    with pytest.raises(ValidationError, match="(artifact hash mismatch|IR hash mismatch)"):
        SemanticCompileStateIR.model_validate(state)


def test_invariant_and_graph_node_contracts_cover_rfc_0003_handoff() -> None:
    assert {
        "PASS_KERNEL_EXECUTION_COMPLETE",
        "PARSED_IR_BOUND_IN_VERIFICATION_PLAN",
        "FORMULA_OPERAND_LINEAGE_COMPLETE",
        "EVIDENCE_GRAPH_REQUIRED_NODE_TYPES_COMPLETE",
        "TABLE_FACT_LINEAGE_TRUTHFUL",
        "DECISION_REGISTRY_BINDINGS_COMPLETE",
        "FIXTURE_DIAGNOSTIC_CODES_STABLE",
        "COMPATIBILITY_MODE_STATUS_TRUTHFUL",
    }.issubset(RFC0003_INVARIANTS)
    assert {"parsed_payload", "table", "cell", "normalized_record", "metric", "formula_evaluation"}.issubset(REQUIRED_EVIDENCE_NODE_KINDS)


def test_frozen_canary_archives_are_byte_identical() -> None:
    for name, expected in EXPECTED_CANARY_HASHES.items():
        assert hashlib.sha256((CANARY_ROOT / name).read_bytes()).hexdigest() == expected
