from __future__ import annotations

import copy
import json

import pytest

from scripts.ops.verify_ba12_whole_system_freeze import (
    DEFAULT_RECORD,
    freeze_sha256,
    verify,
)

CASES = tuple(f"BA12-F-T-{index:03d}" for index in range(1, 31))


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    return verify()


@pytest.mark.parametrize("test_id", CASES, ids=CASES)
def test_ba12_whole_system_freeze_matrix(
    test_id: str,
    result: dict[str, object],
) -> None:
    assert result["status"] == "PASS"
    checks = result["checks"]
    mapping = {
        "BA12-F-T-001": "r5_package_identity",
        "BA12-F-T-002": "r5_standalone_verifier",
        "BA12-F-T-003": "r5_standalone_verifier",
        "BA12-F-T-004": "research_identity",
        "BA12-F-T-005": "product_identity",
        "BA12-F-T-006": "canonical_launch_graph",
        "BA12-F-T-007": "canonical_launch_graph",
        "BA12-F-T-008": "canonical_launch_graph",
        "BA12-F-T-009": "canonical_launch_graph",
        "BA12-F-T-010": "canonical_launch_graph",
        "BA12-F-T-011": "canonical_launch_graph",
        "BA12-F-T-012": "accepted_ui_runtime",
        "BA12-F-T-013": "accepted_ui_runtime",
        "BA12-F-T-014": "accepted_canaries",
        "BA12-F-T-015": "accepted_canaries",
        "BA12-F-T-016": "accepted_canaries",
        "BA12-F-T-017": "accepted_matrices",
        "BA12-F-T-018": "accepted_matrices",
        "BA12-F-T-019": "accepted_matrices",
        "BA12-F-T-020": "research_identity",
        "BA12-F-T-021": "product_identity",
        "BA12-F-T-022": "semantic_wave_freeze",
        "BA12-F-T-023": "rfc0010_freeze",
        "BA12-F-T-024": "r5_package_identity",
        "BA12-F-T-025": "r5_package_identity",
        "BA12-F-T-026": "r5_package_identity",
        "BA12-F-T-027": "final_status",
        "BA12-F-T-028": "product_runtime_unchanged",
        "BA12-F-T-029": "research_runtime_unchanged",
        "BA12-F-T-030": "freeze_self_hash",
    }
    assert checks[mapping[test_id]] is True


def test_freeze_hash_rejects_operational_gate_escalation() -> None:
    record = json.loads(DEFAULT_RECORD.read_text(encoding="utf-8"))
    assert record["freeze_sha256"] == freeze_sha256(record)
    tampered = copy.deepcopy(record)
    tampered["deploy_authorized"] = True
    assert tampered["freeze_sha256"] != freeze_sha256(tampered)


def test_freeze_has_zero_runtime_semantic_diff() -> None:
    result = verify()
    assert result["research_runtime_committed_diff"] == []
    assert result["research_runtime_worktree_diff"] == []
    assert result["product_runtime_committed_diff"] == []
    assert result["product_runtime_worktree_diff"] == []
