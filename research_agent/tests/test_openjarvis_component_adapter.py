import json
from pathlib import Path

from research_agent.ops.openjarvis_component_adapter import (
    build_component_adapter,
    build_component_matrix,
    is_dependabot_pr,
    write_component_adapter,
)


def test_component_matrix_rejects_current_write_worker() -> None:
    config = json.loads(Path("configs/openjarvis/openjarvis_component_adapter.json").read_text())
    trial = {
        "write_fix_sandbox": {
            "status": "FAIL_FOR_OPENJARVIS_ADOPTION",
            "openjarvis_patch_created": False,
            "codex_baseline_tests": "4 passed",
        },
        "github_dependabot_digest": {
            "status": "PASS",
            "open_dependabot_pr_count": 12,
            "mutations_attempted": False,
        },
    }

    matrix = build_component_matrix(config, trial)
    write_worker = next(item for item in matrix if item["id"] == "write_fix_worker")

    assert write_worker["status"] == "REJECT_CURRENT"
    assert write_worker["adoption_mode"] == "reject_currently"


def test_component_adapter_uses_latest_trial_evidence() -> None:
    report = build_component_adapter()

    assert report["status"] == "PASS"
    assert report["overall_decision"] == "harvest_and_rebuild_selected_patterns"
    assert report["component_count"] >= 6
    assert report["adapt_ready_count"] >= 3
    assert report["rejected_current_count"] >= 1
    assert report["github_digest"]["mutations_attempted"] is False


def test_component_adapter_written_outputs(tmp_path: Path) -> None:
    report = build_component_adapter()

    written = write_component_adapter(report, tmp_path)

    assert written["path"] == str((tmp_path / "OPENJARVIS_COMPONENT_ADAPTER.json").resolve())
    assert json.loads((tmp_path / "OPENJARVIS_COMPONENT_ADAPTER.json").read_text())["status"] == "PASS"
    assert (tmp_path / "OPENJARVIS_COMPONENT_ADAPTER.md").exists()
    assert (tmp_path / "OPENJARVIS_COMPONENT_MATRIX.json").exists()
    assert "mutations_attempted=false" in (
        tmp_path / "OPENJARVIS_COMPONENT_ADAPTER_VALIDATION.txt"
    ).read_text()


def test_dependabot_detection_accepts_bot_and_title() -> None:
    assert is_dependabot_pr({"author": {"login": "app/dependabot"}, "title": "anything"})
    assert is_dependabot_pr({"author": {"login": "alice"}, "title": "Dependabot bump"})
    assert not is_dependabot_pr({"author": {"login": "alice"}, "title": "feature"})
