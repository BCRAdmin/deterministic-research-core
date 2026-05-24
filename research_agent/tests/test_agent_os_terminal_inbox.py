from pathlib import Path

from research_agent.ops.operator_inbox import (
    build_operator_inbox_items,
    validate_operator_inbox,
)
from research_agent.ops.terminal_backends import default_backend_specs, validate_backend_specs


def test_terminal_backend_contracts_are_valid(tmp_path: Path) -> None:
    specs = default_backend_specs(tmp_path)
    validations = validate_backend_specs(specs, tmp_path)

    assert [spec.backend_id for spec in specs] == ["local_read_only", "docker_project_sandbox"]
    assert all(validation.valid for validation in validations)
    assert specs[1].operator_gate_required is True
    assert "no_home_or_secret_mounts" in specs[1].verification


def test_operator_inbox_items_are_valid_when_sources_exist(tmp_path: Path) -> None:
    out = tmp_path / "outputs" / "agent_os_readiness"
    out.mkdir(parents=True)
    for name in (
        "AGENT_OS_READINESS_REPORT.md",
        "SKILL_REGISTRY.md",
        "MEMORY_INBOX_CANDIDATES.md",
        "GUARDRAIL_SCAN.md",
        "AGENT_CODING_GUARDRAILS.md",
        "AUTOMATION_JOB_CARDS.md",
        "DELIVERABLE_SWARM_CONTRACT.md",
        "VAULT_SEMANTIC_OWNERSHIP_AUDIT.md",
    ):
        (out / name).write_text("ok", encoding="utf-8")

    items = build_operator_inbox_items(
        tmp_path,
        guardrail_count=2,
        memory_candidate_count=3,
        skill_record_count=4,
        automation_cards_valid=True,
        deliverable_contract_valid=True,
        deliverable_lane_count=8,
        coding_guardrails_valid=True,
        coding_guardrail_count=7,
        vault_semantic_audit_valid=True,
        vault_semantic_findings=0,
    )
    validation = validate_operator_inbox(items)

    assert validation.valid is True
    assert not validation.warnings
    assert any(item.lane == "runtime_gate" and item.operator_gate_required for item in items)
    assert any(item.lane == "deliverable_surface" and item.priority == "P0" for item in items)
    assert any(item.lane == "coding_governance" and item.priority == "P0" for item in items)
    assert any(item.item_id == "vault-semantic-ownership-review" for item in items)
