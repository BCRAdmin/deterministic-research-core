import json
from pathlib import Path

from research_agent.ops.openjarvis_capability_lab import load_json
from research_agent.ops.openjarvis_decision_gauntlet import (
    DEFAULT_PLAN_PATH,
    OPERATOR_GATE,
    build_decision_gauntlet,
    validate_plan,
    write_decision_gauntlet,
)


def test_decision_gauntlet_plan_is_complete() -> None:
    plan = load_json(DEFAULT_PLAN_PATH)
    tests = [
        test
        for workstream in plan["workstreams"]
        for test in workstream["tests"]
    ]

    assert not validate_plan(plan)
    assert len(plan["workstreams"]) >= 10
    assert len(tests) >= 60
    assert any(test["artifact"] == "operator_gate" for test in tests)
    assert any(test["artifact"] != "operator_gate" for test in tests)


def test_decision_gauntlet_keeps_runtime_gated() -> None:
    report = build_decision_gauntlet()

    assert report["status"] == "PASS"
    assert report["source_of_truth"] is False
    assert report["runtime_action_executed"] is False
    assert report["runtime_execution_attempted"] is False
    assert report["decision_status"] == "ready_for_operator_gated_runtime_github_write_trials"
    assert report["summary"]["fail_count"] == 0
    assert report["summary"]["operator_gate_count"] >= 20


def test_decision_gauntlet_requires_shadow_evidence() -> None:
    report = build_decision_gauntlet()
    arena = report["arena_summary"]

    assert arena["shadow_wins"] >= 10
    assert arena["baseline_wins"] >= 1
    assert arena["shadow_wins"] + arena["baseline_wins"] + arena["ties"] == arena["task_count"]
    assert arena["shadow_fail_count"] == 0
    assert report["adoption_recommendation"].startswith("do_not_rebuild_system")


def test_decision_gauntlet_written_outputs(tmp_path: Path) -> None:
    report = build_decision_gauntlet()

    written = write_decision_gauntlet(report, tmp_path)

    assert written["path"] == str((tmp_path / "OPENJARVIS_DECISION_GAUNTLET.json").resolve())
    assert json.loads((tmp_path / "OPENJARVIS_DECISION_GAUNTLET.json").read_text())["status"] == "PASS"
    assert (tmp_path / "OPENJARVIS_DECISION_GAUNTLET.md").exists()
    matrix = json.loads((tmp_path / "OPENJARVIS_DECISION_TEST_MATRIX.json").read_text())
    assert matrix["tests"]
    assert any(test["status"] == OPERATOR_GATE for test in matrix["tests"])
