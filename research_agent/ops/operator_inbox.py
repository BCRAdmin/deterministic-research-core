"""Local operator inbox contract.

Hermes and OpenClaw make multi-channel work visible. This module gives our
system the useful part first: a single local inbox artifact for review, gates,
and next safe actions. It is not a messaging gateway.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class InboxItem:
    item_id: str
    lane: str
    priority: str
    status: str
    source: str
    summary: str
    required_action: str
    operator_gate_required: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class InboxValidation:
    valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def build_operator_inbox_items(
    root: Path,
    guardrail_count: int,
    memory_candidate_count: int,
    skill_record_count: int,
    automation_cards_valid: bool,
) -> list[InboxItem]:
    root = root.resolve()
    base = root / "outputs/agent_os_readiness"
    items = [
        InboxItem(
            item_id="agent-os-readiness-review",
            lane="operator_review",
            priority="P0",
            status="ready_for_review",
            source=str(base / "AGENT_OS_READINESS_REPORT.md"),
            summary="Review capability matrix and OpenClaw migration dry-run before any runtime expansion.",
            required_action="read_or_acknowledge",
            operator_gate_required=False,
        ),
        InboxItem(
            item_id="skill-registry-review",
            lane="skill_governance",
            priority="P1",
            status="ready_for_review",
            source=str(base / "SKILL_REGISTRY.md"),
            summary=f"{skill_record_count} local skill/playbook records classified; no external install allowed.",
            required_action="review_hold_or_playbook_decisions",
            operator_gate_required=False,
        ),
        InboxItem(
            item_id="memory-inbox-review",
            lane="memory_promotion",
            priority="P1",
            status="candidate_review",
            source=str(base / "MEMORY_INBOX_CANDIDATES.md"),
            summary=f"{memory_candidate_count} memory candidates need promote/reject/merge review.",
            required_action="promote_only_after_obsidian_route_check",
            operator_gate_required=True,
        ),
        InboxItem(
            item_id="guardrail-gate-review",
            lane="runtime_gate",
            priority="P1",
            status="gate_review",
            source=str(base / "GUARDRAIL_SCAN.md"),
            summary=f"{guardrail_count} guardrail findings are recorded as gates before runtime expansion.",
            required_action="clear_or_accept_gates_before_runtime_rights",
            operator_gate_required=True,
        ),
        InboxItem(
            item_id="automation-card-review",
            lane="automation_review",
            priority="P2",
            status="ready_for_review" if automation_cards_valid else "blocked",
            source=str(base / "AUTOMATION_JOB_CARDS.md"),
            summary="Automation job cards are proposals only and are not installed automations.",
            required_action="create_real_automation_only_after_operator_go",
            operator_gate_required=True,
        ),
    ]
    return items


def validate_operator_inbox(items: Sequence[InboxItem]) -> InboxValidation:
    errors: list[str] = []
    warnings: list[str] = []
    ids: set[str] = set()
    for item in items:
        if item.item_id in ids:
            errors.append(f"duplicate_item_id:{item.item_id}")
        ids.add(item.item_id)
        if not item.lane:
            errors.append(f"missing_lane:{item.item_id}")
        if item.status == "blocked" and not item.operator_gate_required:
            errors.append(f"blocked_item_without_gate:{item.item_id}")
        if item.operator_gate_required and item.required_action == "none":
            errors.append(f"gated_item_without_action:{item.item_id}")
        if not Path(item.source).exists():
            warnings.append(f"source_missing:{item.item_id}")
    return InboxValidation(valid=not errors, errors=tuple(errors), warnings=tuple(warnings))


def render_operator_inbox_markdown(items: Sequence[InboxItem], validation: InboxValidation) -> str:
    lines = [
        "# Operator Inbox",
        "",
        "Local review inbox for Agent OS work. This is not a chat gateway.",
        "",
        f"Valid: `{str(validation.valid).lower()}`",
        f"Errors: `{', '.join(validation.errors) if validation.errors else 'none'}`",
        f"Warnings: `{', '.join(validation.warnings) if validation.warnings else 'none'}`",
        "",
        "| Item | Lane | Priority | Status | Gate | Action | Source |",
        "| --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for item in items:
        lines.append(
            f"| `{item.item_id}` | `{item.lane}` | `{item.priority}` | `{item.status}` | "
            f"{str(item.operator_gate_required).lower()} | `{item.required_action}` | `{item.source}` |"
        )
    return "\n".join(lines) + "\n"
