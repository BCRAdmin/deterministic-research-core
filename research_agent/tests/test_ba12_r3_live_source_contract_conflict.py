from __future__ import annotations

import json

import pytest

from scripts.ops.verify_ba12_r3_live_source_contract_conflict import EVIDENCE, verify


TEST_IDS = tuple(f"BA12-R3-STOP-{index:03d}" for index in range(1, 7))


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    return verify()


@pytest.mark.parametrize("test_id", TEST_IDS, ids=TEST_IDS)
def test_live_source_contract_conflict(test_id: str, result: dict[str, object]) -> None:
    assert result["status"] == "PASS"
    checks = result["checks"]
    assert isinstance(checks, dict)
    mapping = {
        "BA12-R3-STOP-001": "compile_policy_live_representable",
        "BA12-R3-STOP-002": "source_plan_live_representable",
        "BA12-R3-STOP-003": "receipt_live_unrepresentable",
        "BA12-R3-STOP-004": "frozen_contract_exact",
        "BA12-R3-STOP-005": "semantic_wave_freeze",
        "BA12-R3-STOP-006": "stop_semantics",
    }
    assert checks[mapping[test_id]] is True


def test_stop_record_preserves_non_action_state() -> None:
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert evidence["status"] == "STOPPED_RFC_TRIGGER_REQUIRED"
    assert evidence["stop_conditions"] == [2, 4]
    assert all(value is False for value in evidence["forbidden_actions_preserved"].values())


def test_no_runtime_or_product_change_is_claimed() -> None:
    result = verify()
    assert result["runtime_code_changed"] is False
    assert result["product_changed"] is False
    assert result["ready_for_independent_rereview"] is False
    assert result["ba12_implementation_ready"] is False
    assert result["ba12_frozen"] is False
