"""Lokaler Operator-Inbox-Vertrag.

Hermes und OpenClaw machen Mehrkanal-Arbeit sichtbar. Dieses Modul uebernimmt
zuerst den nuetzlichen Teil fuer unser System: ein lokales Inbox-Artefakt fuer
Review, Gates und sichere naechste Aktionen. Es ist kein Messaging-Gateway.
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
    deliverable_contract_valid: bool = True,
    deliverable_lane_count: int = 0,
    vault_semantic_audit_valid: bool = True,
    vault_semantic_findings: int = 0,
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
            summary="Faehigkeitsmatrix und OpenClaw-Migrations-Trockenlauf vor jeder Runtime-Erweiterung pruefen.",
            required_action="lesen_oder_bestaetigen",
            operator_gate_required=False,
        ),
        InboxItem(
            item_id="skill-registry-review",
            lane="skill_governance",
            priority="P1",
            status="ready_for_review",
            source=str(base / "SKILL_REGISTRY.md"),
            summary=f"{skill_record_count} lokale Skill-/Playbook-Eintraege klassifiziert; externe Installation bleibt verboten.",
            required_action="hold_oder_playbook_entscheidung_pruefen",
            operator_gate_required=False,
        ),
        InboxItem(
            item_id="memory-inbox-review",
            lane="memory_promotion",
            priority="P1",
            status="candidate_review",
            source=str(base / "MEMORY_INBOX_CANDIDATES.md"),
            summary=f"{memory_candidate_count} Memory-Kandidaten brauchen Promote-/Reject-/Merge-Review.",
            required_action="nur_nach_obsidian_routenpruefung_promoten",
            operator_gate_required=True,
        ),
        InboxItem(
            item_id="guardrail-gate-review",
            lane="runtime_gate",
            priority="P1",
            status="gate_review",
            source=str(base / "GUARDRAIL_SCAN.md"),
            summary=f"{guardrail_count} Guardrail-Funde sind als Gates vor Runtime-Erweiterung festgehalten.",
            required_action="gates_vor_runtime_rechten_klaeren_oder_akzeptieren",
            operator_gate_required=True,
        ),
        InboxItem(
            item_id="vault-semantic-ownership-review",
            lane="memory_governance",
            priority="P0",
            status="ready_for_review" if vault_semantic_audit_valid else "blocked",
            source=str(base / "VAULT_SEMANTIC_OWNERSHIP_AUDIT.md"),
            summary=(
                f"{vault_semantic_findings} semantische Vault-Ownership-Funde; "
                "prueft aktive Projektwahrheit, Startflaechen und alte Gewohnheitsrouten."
            ),
            required_action="vor_vault_clean_claim_pruefen_oder_findings_fixen",
            operator_gate_required=not vault_semantic_audit_valid,
        ),
        InboxItem(
            item_id="automation-card-review",
            lane="automation_review",
            priority="P2",
            status="ready_for_review" if automation_cards_valid else "blocked",
            source=str(base / "AUTOMATION_JOB_CARDS.md"),
            summary="Automation Cards sind nur Vorschlaege und keine installierten Automationen.",
            required_action="echte_automation_nur_nach_operator_go_erstellen",
            operator_gate_required=True,
        ),
        InboxItem(
            item_id="deliverable-swarm-review",
            lane="deliverable_surface",
            priority="P0",
            status="ready_for_review" if deliverable_contract_valid else "blocked",
            source=str(base / "DELIVERABLE_SWARM_CONTRACT.md"),
            summary=(
                f"{deliverable_lane_count} Deliverable-Lanes definieren Owner, Output-Pfade, "
                "Verifier, Handoffs und Gates."
            ),
            required_action="vor_runtime_erweiterung_als_agenten_team_oberflaeche_nutzen",
            operator_gate_required=not deliverable_contract_valid,
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
        "Lokale Review-Inbox fuer Agent-OS-Arbeit. Das ist kein Chat-Gateway.",
        "",
        f"Gueltig: `{str(validation.valid).lower()}`",
        f"Fehler: `{', '.join(validation.errors) if validation.errors else 'keine'}`",
        f"Warnungen: `{', '.join(validation.warnings) if validation.warnings else 'keine'}`",
        "",
        "| Item | Lane | Prioritaet | Status | Gate | Aktion | Zusammenfassung | Quelle |",
        "| --- | --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for item in items:
        lines.append(
            f"| `{item.item_id}` | `{item.lane}` | `{item.priority}` | `{item.status}` | "
            f"{str(item.operator_gate_required).lower()} | `{item.required_action}` | "
            f"{item.summary} | `{item.source}` |"
        )
    return "\n".join(lines) + "\n"
