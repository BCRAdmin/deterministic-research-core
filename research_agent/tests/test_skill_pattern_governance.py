import json
from pathlib import Path

from research_agent.ops.skill_pattern_governance import (
    HELPER_PATH,
    HOLD_REGISTER_PATH,
    REQUIRED_HOLD_ITEM_NAMES,
    REQUIRED_NOT_IMPLEMENTED,
    REQUIRED_PLAYBOOK_FILES,
    SUMMARY_PATH,
    check_skill_pattern_governance,
)


def _write_text(path: Path, text: str = "ok\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_valid_contract(root: Path) -> None:
    for relative_path in REQUIRED_PLAYBOOK_FILES:
        _write_text(root / relative_path)

    _write_json(
        root / SUMMARY_PATH,
        {
            "status": "completed",
            "created_playbooks": list(REQUIRED_PLAYBOOK_FILES),
            "helper_scripts": [
                {
                    "path": HELPER_PATH,
                    "mode": "local_read_only",
                    "network": "none",
                    "writes": "none",
                    "secret_printing": False,
                }
            ],
            "not_implemented": sorted(REQUIRED_NOT_IMPLEMENTED),
            "runtime_changes": "none",
        },
    )
    _write_json(
        root / HOLD_REGISTER_PATH,
        {
            "status": "active",
            "runtime_changes": "none",
            "items": [
                {
                    "name": name,
                    "operator_gate_required": True,
                    "forbidden_runtime_behavior": ["runtime_expansion"],
                    "allowed_pattern_extraction": "playbook_only",
                }
                for name in sorted(REQUIRED_HOLD_ITEM_NAMES)
            ],
            "future_sandbox_conditions": [
                "source_verification",
                "explicit_operator_gate",
                "no_credentials_unless_separately_approved",
            ],
        },
    )
    _write_text(
        root / HELPER_PATH,
        "This helper does not import project code, call a network, "
        "write outputs, or print secret values.\n",
    )


def test_skill_pattern_governance_accepts_valid_contract(tmp_path: Path) -> None:
    _write_valid_contract(tmp_path)

    report = check_skill_pattern_governance(tmp_path)

    assert report.ok is True
    assert report.blocking_findings == ()


def test_skill_pattern_governance_blocks_missing_hold_item(tmp_path: Path) -> None:
    _write_valid_contract(tmp_path)
    register_path = tmp_path / HOLD_REGISTER_PATH
    register = json.loads(register_path.read_text(encoding="utf-8"))
    register["items"] = [
        item
        for item in register["items"]
        if item["name"] != "remote skillscan/phone-home scanner"
    ]
    _write_json(register_path, register)

    report = check_skill_pattern_governance(tmp_path)

    assert report.ok is False
    assert any(finding.check_id == "missing_hold_item" for finding in report.findings)


def test_skill_pattern_governance_blocks_runtime_integration(tmp_path: Path) -> None:
    _write_valid_contract(tmp_path)
    summary_path = tmp_path / SUMMARY_PATH
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["runtime_changes"] = "enabled"
    summary["not_implemented"].remove("runtime_integration")
    _write_json(summary_path, summary)

    report = check_skill_pattern_governance(tmp_path)

    assert report.ok is False
    assert any(finding.check_id == "summary_runtime_changed" for finding in report.findings)
    assert any(finding.check_id == "summary_missing_blocked_runtime" for finding in report.findings)
