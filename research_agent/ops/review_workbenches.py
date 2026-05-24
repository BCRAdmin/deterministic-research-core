"""Deterministic review workbenches for Agent-OS governance queues.

These helpers turn raw findings into grouped operator surfaces. They do not
promote memory, change policy, or mutate runtime state.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Sequence

from research_agent.ops.guardrails import GuardrailFinding, highest_severity
from research_agent.ops.memory_inbox import MemoryCandidate


@dataclass(frozen=True)
class MemoryPromotionBatch:
    batch_id: str
    route: str
    kind: str
    candidate_count: int
    source_count: int
    status: str
    gate: str
    next_action: str
    sample_candidates: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class GuardrailPolicyGate:
    gate_id: str
    check_id: str
    category: str
    severity: str
    finding_count: int
    operator_gate_required: bool
    status: str
    next_action: str
    sample_evidence: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _short_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha1("\u241f".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest[:12]}"


def build_memory_promotion_workbench(
    candidates: Sequence[MemoryCandidate],
) -> list[MemoryPromotionBatch]:
    groups: dict[tuple[str, str], list[MemoryCandidate]] = {}
    for candidate in candidates:
        groups.setdefault((candidate.route, candidate.kind), []).append(candidate)
    batches: list[MemoryPromotionBatch] = []
    for (route, kind), items in sorted(groups.items(), key=lambda row: (row[0][0], row[0][1])):
        sources = {item.source_path for item in items}
        if route.startswith("Memory/"):
            next_action = "dedupe_against_target_note_then_promote_or_reject_batch"
        else:
            next_action = "route_to_agent_stack_note_or_reject_if_already_captured"
        batches.append(
            MemoryPromotionBatch(
                batch_id=_short_id("mem-batch", route, kind),
                route=route,
                kind=kind,
                candidate_count=len(items),
                source_count=len(sources),
                status="ready_for_operator_batch_review",
                gate="obsidian_promotion_review_required",
                next_action=next_action,
                sample_candidates=tuple(item.candidate_id for item in items[:5]),
            )
        )
    return batches


def build_guardrail_policy_gate_matrix(
    findings: Sequence[GuardrailFinding],
) -> list[GuardrailPolicyGate]:
    groups: dict[tuple[str, str, str], list[GuardrailFinding]] = {}
    for finding in findings:
        groups.setdefault((finding.check_id, finding.category, finding.severity), []).append(finding)
    gates: list[GuardrailPolicyGate] = []
    for (check_id, category, severity), items in sorted(groups.items(), key=lambda row: row[0]):
        gate_required = any(item.operator_gate_required for item in items)
        status = "report_level_gate_active"
        next_action = "keep_as_report_gate_until_policy_engine_rule_exists"
        if severity in {"block", "high"} and gate_required:
            next_action = "convert_to_policy_engine_rule_before_runtime_expansion"
        gates.append(
            GuardrailPolicyGate(
                gate_id=_short_id("guardrail-gate", check_id, category, severity),
                check_id=check_id,
                category=category,
                severity=severity,
                finding_count=len(items),
                operator_gate_required=gate_required,
                status=status,
                next_action=next_action,
                sample_evidence=tuple(item.evidence for item in items[:3]),
            )
        )
    return gates


def render_memory_promotion_workbench(batches: Sequence[MemoryPromotionBatch]) -> str:
    lines = [
        "# Memory Promotion Workbench",
        "",
        "Batch review surface for memory candidates. This does not write Obsidian.",
        "",
        f"Batches: {len(batches)}",
        "",
        "| Batch | Route | Kind | Candidates | Sources | Gate | Next action | Samples |",
        "| --- | --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    for batch in batches:
        samples = ", ".join(f"`{item}`" for item in batch.sample_candidates)
        lines.append(
            f"| `{batch.batch_id}` | `{batch.route}` | `{batch.kind}` | "
            f"{batch.candidate_count} | {batch.source_count} | `{batch.gate}` | "
            f"`{batch.next_action}` | {samples} |"
        )
    return "\n".join(lines) + "\n"


def render_guardrail_policy_gate_matrix(gates: Sequence[GuardrailPolicyGate]) -> str:
    severity = highest_severity(
        [
            GuardrailFinding(
                check_id=gate.check_id,
                category=gate.category,
                severity=gate.severity,
                message="",
                file="",
                line=0,
                evidence="",
                operator_gate_required=gate.operator_gate_required,
            )
            for gate in gates
        ]
    )
    lines = [
        "# Guardrail Policy Gate Matrix",
        "",
        "Grouped policy surface for Agent-OS guardrail findings. This does not grant runtime rights.",
        "",
        f"Gates: {len(gates)}",
        f"Highest severity: `{severity}`",
        "",
        "| Gate | Check | Category | Severity | Findings | Operator gate | Status | Next action |",
        "| --- | --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for gate in gates:
        lines.append(
            f"| `{gate.gate_id}` | `{gate.check_id}` | `{gate.category}` | "
            f"`{gate.severity}` | {gate.finding_count} | "
            f"{str(gate.operator_gate_required).lower()} | `{gate.status}` | "
            f"`{gate.next_action}` |"
        )
    return "\n".join(lines) + "\n"
