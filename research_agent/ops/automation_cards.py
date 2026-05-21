"""Automation job cards with explicit gates and lifecycle metadata."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Sequence

from research_agent.ops.guardrails import scan_text


DEFAULT_FORBIDDEN_ACTIONS = (
    "automatically_change_code",
    "automatically_release_reports",
    "automatically_enable_ads_or_affiliate",
    "automatically_loosen_guards",
    "automatically_update_obsidian_backbone",
    "automatically_publish",
    "automatically_create_runtime_rights_api_keys_or_background_agents",
)

DEFAULT_OUTPUT_CONTRACT = (
    "status",
    "missing_data",
    "allowed_next_action",
    "blocked_gates",
    "no_action_if_not_mature",
)


@dataclass(frozen=True)
class AutomationJobCard:
    job_id: str
    name: str
    status: str
    schedule: str
    prompt: str
    workdir: str
    profile: str
    allowed_toolsets: tuple[str, ...]
    skills: tuple[str, ...]
    context_from: tuple[str, ...]
    delivery: str
    stop_conditions: tuple[str, ...]
    output_contract: tuple[str, ...] = DEFAULT_OUTPUT_CONTRACT
    forbidden_actions: tuple[str, ...] = DEFAULT_FORBIDDEN_ACTIONS
    risk_class: str = "R6_scheduled_review_constrained"
    operator_gate_required: bool = False
    no_action_if_not_mature: bool = True

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class JobCardValidation:
    job_id: str
    valid: bool
    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def make_job_id(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
    return f"{slug}-{digest}"


def validate_job_card(card: AutomationJobCard, root: Path) -> JobCardValidation:
    errors: list[str] = []
    warnings: list[str] = []

    workdir = Path(card.workdir)
    if not workdir.is_absolute():
        errors.append("workdir_must_be_absolute")
    elif not workdir.exists():
        errors.append("workdir_missing")

    if not card.stop_conditions:
        errors.append("missing_stop_conditions")
    if "no_action_if_not_mature" not in card.output_contract:
        errors.append("output_contract_missing_no_action_if_not_mature")
    if not card.no_action_if_not_mature:
        warnings.append("no_action_if_not_mature_disabled")

    prompt_findings = scan_text(card.prompt, file=f"automation:{card.job_id}", scan_type="automation")
    if any(f.severity == "block" for f in prompt_findings):
        errors.append("prompt_contains_blocked_guardrail")
    if any(f.severity == "high" for f in prompt_findings) and not card.operator_gate_required:
        errors.append("high_risk_prompt_requires_operator_gate")
    if prompt_findings:
        warnings.extend(f"guardrail:{finding.check_id}" for finding in prompt_findings)

    forbidden_prompt_terms = ("deploy", "publish", "git merge", "git push", "delete", "api key")
    if any(term in card.prompt.lower() for term in forbidden_prompt_terms) and not card.operator_gate_required:
        errors.append("mutation_or_secret_term_without_operator_gate")

    for item in card.context_from:
        path = (root / item).resolve() if not Path(item).is_absolute() else Path(item)
        if not path.exists():
            warnings.append(f"context_missing:{item}")

    return JobCardValidation(
        job_id=card.job_id,
        valid=not errors,
        errors=tuple(errors),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def default_job_cards(root: Path) -> list[AutomationJobCard]:
    root = root.resolve()
    workdir = str(root)
    return [
        AutomationJobCard(
            job_id=make_job_id("Agent-OS-Readiness woechentlich pruefen"),
            name="Agent-OS-Readiness woechentlich pruefen",
            status="proposed_local_review_only",
            schedule="woechentlich, manuelle Erstellung erforderlich",
            workdir=workdir,
            profile="default",
            allowed_toolsets=("read_file", "search_files", "terminal_read_only"),
            skills=("agent-os-readiness",),
            context_from=(
                "docs/agent_os/AGENT_OS_READINESS_PACK.md",
                "outputs/agent_os_readiness/AGENT_OS_READINESS_REPORT.md",
            ),
            delivery="local_file_only",
            stop_conditions=(
                "stop_if_repo_has_unrelated_dirty_work",
                "stop_if_external_install_would_be_required",
                "stop_if_operator_gate_required",
            ),
            prompt=(
                "Pruefe lokale Agent-OS-Readiness-Artefakte. Berichte fehlende Daten, "
                "veraltete Outputs, blockierte Gates und sichere naechste Aktionen. Keinen "
                "Code und kein kanonisches Memory aendern."
            ),
        ),
        AutomationJobCard(
            job_id=make_job_id("Memory-Inbox-Promotion pruefen"),
            name="Memory-Inbox-Promotion pruefen",
            status="proposed_local_review_only",
            schedule="woechentlich, manuelle Erstellung erforderlich",
            workdir=workdir,
            profile="default",
            allowed_toolsets=("read_file", "search_files"),
            skills=("obsidian-memory-promotion",),
            context_from=("outputs/agent_os_readiness/MEMORY_INBOX_CANDIDATES.md",),
            delivery="local_file_only",
            stop_conditions=(
                "stop_before_writing_obsidian",
                "stop_if_candidate_route_is_unclear",
                "stop_if_duplicate_memory_exists",
            ),
            prompt=(
                "Pruefe Memory-Inbox-Kandidaten und klassifiziere jeden als promoten, "
                "ablehnen, mergen oder operatorbeduerftig. Nicht direkt nach Obsidian schreiben."
            ),
        ),
        AutomationJobCard(
            job_id=make_job_id("Vault Semantic Ownership pruefen"),
            name="Vault Semantic Ownership pruefen",
            status="proposed_local_review_only",
            schedule="woechentlich und vor jedem Claim 'Vault ist sauber'",
            workdir=workdir,
            profile="default",
            allowed_toolsets=("read_file", "search_files", "terminal_read_only"),
            skills=("vega-obsidian-memory", "semantic-ownership-audit"),
            context_from=(
                "outputs/agent_os_readiness/VAULT_SEMANTIC_OWNERSHIP_AUDIT.md",
                "outputs/vault_semantic_audit/VAULT_SEMANTIC_OWNERSHIP_AUDIT.md",
            ),
            delivery="local_file_only",
            stop_conditions=(
                "stop_before_writing_obsidian",
                "stop_if_active_project_owner_is_ambiguous",
                "stop_if_start_surfaces_disagree",
                "stop_if_operator_gate_required",
            ),
            prompt=(
                "Fuehre den lokalen Vault Semantic Ownership Audit aus. Pruefe Blickwinkel "
                "Ownership, Startflaechen, Body-Semantik, Negative Routing, Aging, Gate-"
                "Inversion und Nachfolger-/Vorgaenger-Spuren. Berichte Findings und sichere "
                "naechste Aktionen. Kein kanonisches Memory automatisch aendern."
            ),
        ),
        AutomationJobCard(
            job_id=make_job_id("Skill-Registry-Drift pruefen"),
            name="Skill-Registry-Drift pruefen",
            status="proposed_local_review_only",
            schedule="woechentlich, manuelle Erstellung erforderlich",
            workdir=workdir,
            profile="default",
            allowed_toolsets=("read_file", "search_files", "terminal_read_only"),
            skills=("skill-pattern-governance",),
            context_from=("outputs/agent_os_readiness/SKILL_REGISTRY.md",),
            delivery="local_file_only",
            stop_conditions=(
                "stop_if_external_skill_install_is_suggested",
                "stop_if_runtime_rights_change_is_needed",
                "stop_if_risk_class_R3_or_higher_without_operator_gate",
            ),
            prompt=(
                "Pruefe lokalen Skill-Registry-Drift. Schlage nur Playbook-Updates und "
                "Hold-Register-Eintraege vor. Keine externen Skills installieren."
            ),
        ),
        AutomationJobCard(
            job_id=make_job_id("Guardrail-Coverage-Smoke pruefen"),
            name="Guardrail-Coverage-Smoke pruefen",
            status="proposed_local_review_only",
            schedule="bei Bedarf vor Agent-OS-Runtime-Aenderungen",
            workdir=workdir,
            profile="default",
            allowed_toolsets=("read_file", "search_files", "terminal_read_only"),
            skills=("guardrails-as-code",),
            context_from=("outputs/agent_os_readiness/GUARDRAIL_SCAN.md",),
            delivery="local_file_only",
            stop_conditions=(
                "stop_if_block_finding_exists",
                "stop_if_secret_evidence_would_be_printed",
                "stop_if_context_injection_is_detected",
            ),
            prompt=(
                "Fuehre den lokalen Guardrail-Scan aus und fasse Block-/High-Funde mit "
                "Dateipfaden zusammen. Keine Secret-Werte ausgeben."
            ),
        ),
        AutomationJobCard(
            job_id=make_job_id("Deliverable-Swarm-Vertrag pruefen"),
            name="Deliverable-Swarm-Vertrag pruefen",
            status="proposed_local_review_only",
            schedule="bei Bedarf vor neuen sichtbaren Agentenoberflaechen",
            workdir=workdir,
            profile="default",
            allowed_toolsets=("read_file", "search_files", "terminal_read_only"),
            skills=("deliverable-swarm-contract", "agent-os-readiness"),
            context_from=(
                "docs/agent_os/DELIVERABLE_SWARM_CONTRACT.md",
                "outputs/agent_os_readiness/DELIVERABLE_SWARM_CONTRACT.md",
            ),
            delivery="local_file_only",
            stop_conditions=(
                "stop_if_external_runtime_install_is_required",
                "stop_if_media_provider_or_account_gate_is_needed",
                "stop_if_output_contract_lacks_verifier",
            ),
            prompt=(
                "Pruefe die Deliverable-Swarm-Lane-Matrix und Output-Vertraege. Berichte "
                "Luecken bei Ownern, Output-Pfaden, Verifiern, Gates oder Handoffs. Keine "
                "Konten erstellen, keine Runtimes installieren und kein kanonisches Memory "
                "mutieren."
            ),
        ),
    ]


def render_job_cards_markdown(
    cards: Sequence[AutomationJobCard],
    validations: Sequence[JobCardValidation],
) -> str:
    validation_by_id = {item.job_id: item for item in validations}
    lines = [
        "# Automation Job Cards",
        "",
        "Das sind vorgeschlagene sichere Automation Cards. Sie sind keine installierten Automationen.",
        "",
        "| Job | Status | Gueltig | Zeitplan | Lieferung | Toolsets |",
        "| --- | --- | ---: | --- | --- | --- |",
    ]
    for card in cards:
        validation = validation_by_id.get(card.job_id)
        valid = validation.valid if validation else False
        lines.append(
            f"| `{card.name}` | `{card.status}` | {str(valid).lower()} | "
            f"{card.schedule} | `{card.delivery}` | `{', '.join(card.allowed_toolsets)}` |"
        )
    lines.extend(["", "## Validierungsdetails", ""])
    for validation in validations:
        lines.append(f"### {validation.job_id}")
        lines.append("")
        lines.append(f"- gueltig: `{str(validation.valid).lower()}`")
        lines.append(f"- fehler: `{', '.join(validation.errors) if validation.errors else 'keine'}`")
        lines.append(f"- warnungen: `{', '.join(validation.warnings) if validation.warnings else 'keine'}`")
        lines.append("")
    return "\n".join(lines)
