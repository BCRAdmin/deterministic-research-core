"""Coding-agent guardrails distilled from external skill benchmarks.

This module turns the useful parts of Superpowers and Karpathy-style coding
guidelines into a local playbook contract. It deliberately does not install
external plugins, register hooks, create worktrees, or dispatch subagents.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Sequence


REQUIRED_GUARDRAIL_IDS = (
    "state_assumptions_and_tradeoffs",
    "minimal_surgical_change",
    "goal_driven_execution",
    "evidence_before_completion",
    "root_cause_before_fix",
    "explicit_branch_finish",
    "skill_behavior_pressure_test",
)

REQUIRED_BLOCKED_DEFAULTS = (
    "global_session_hook",
    "skill_trigger_before_every_reply",
    "spec_commit_for_small_tasks",
    "auto_worktree_creation",
    "auto_subagent_driven_development",
    "external_plugin_vendoring_without_license_gate",
)


@dataclass(frozen=True)
class CodingGuardrail:
    guardrail_id: str
    title: str
    source_patterns: tuple[str, ...]
    trigger: str
    required_behavior: tuple[str, ...]
    required_evidence: tuple[str, ...]
    gate_level: str
    applies_to: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class CodingGuardrailContract:
    name: str
    status: str
    runtime_policy: str
    source_repos: tuple[str, ...]
    items: tuple[CodingGuardrail, ...]
    situational_transfers: tuple[str, ...]
    blocked_defaults: tuple[str, ...] = REQUIRED_BLOCKED_DEFAULTS

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class CodingGuardrailValidation:
    valid: bool
    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def default_coding_guardrails() -> CodingGuardrailContract:
    items = (
        CodingGuardrail(
            guardrail_id="state_assumptions_and_tradeoffs",
            title="Annahmen und Tradeoffs sichtbar machen",
            source_patterns=("karpathy-guidelines",),
            trigger="unklare Anforderungen, mehrere plausible Loesungen oder riskante implizite Annahmen",
            required_behavior=(
                "relevante Annahmen kurz nennen",
                "bei echter Mehrdeutigkeit Alternativen mit Empfehlung zeigen",
                "bei unklaerbarer Blockade eine konkrete Frage stellen",
            ),
            required_evidence=("assumptions note", "chosen approach or blocker"),
            gate_level="soft",
            applies_to=("planning", "code_change", "review"),
        ),
        CodingGuardrail(
            guardrail_id="minimal_surgical_change",
            title="Minimal und chirurgisch aendern",
            source_patterns=("karpathy-guidelines",),
            trigger="bestehenden Code, Doku oder Konfiguration aendern",
            required_behavior=(
                "nur Zeilen anfassen, die auf den Auftrag einzahlen",
                "lokalen Stil und bestehende Hilfsfunktionen bevorzugen",
                "keine Drive-by-Refactors oder spekulativen Abstraktionen",
            ),
            required_evidence=("changed files trace to request", "unrelated findings reported but not edited"),
            gate_level="soft",
            applies_to=("code_change", "docs_change", "config_change"),
        ),
        CodingGuardrail(
            guardrail_id="goal_driven_execution",
            title="Erfolgskriterien vor Ausfuehrung klaeren",
            source_patterns=("karpathy-guidelines", "superpowers:writing-plans"),
            trigger="mehrschrittige Implementierung, Bugfix oder Review-Auftrag",
            required_behavior=(
                "kleinstes pruefbares Ziel festlegen",
                "Verifikation pro Schritt benennen",
                "bei groesseren Aenderungen Plan oder Taskliste fuehren",
            ),
            required_evidence=("success criteria", "verification command list"),
            gate_level="soft",
            applies_to=("planning", "implementation", "handoff"),
        ),
        CodingGuardrail(
            guardrail_id="evidence_before_completion",
            title="Keine Abschlussbehauptung ohne frische Evidenz",
            source_patterns=("superpowers:verification-before-completion",),
            trigger="vor Erfolgsmeldung, Commit, PR, Handoff oder 'fertig'-Claim",
            required_behavior=(
                "frischen passenden Verify-Befehl ausfuehren",
                "Output und Exit-Code lesen",
                "Status nur so stark formulieren, wie die Evidenz traegt",
            ),
            required_evidence=("fresh verification evidence", "command exit status", "remaining risk if any"),
            gate_level="hard",
            applies_to=("completion", "commit", "handoff", "review"),
        ),
        CodingGuardrail(
            guardrail_id="root_cause_before_fix",
            title="Root Cause vor Fix",
            source_patterns=("superpowers:systematic-debugging",),
            trigger="Bug, Testfehler, Buildfehler, Runtime-Anomalie oder wiederholter Fix-Fail",
            required_behavior=(
                "Fehler komplett lesen und reproduzierbare Spur suchen",
                "aktuelle Diff-/Umgebungsveraenderungen pruefen",
                "Hypothese formulieren und minimal testen",
                "Fix erst nach nachvollziehbarer Ursache setzen",
            ),
            required_evidence=("root cause note", "reproduction or diagnostic evidence", "fix verification"),
            gate_level="hard",
            applies_to=("debugging", "ci_failure", "runtime_failure"),
        ),
        CodingGuardrail(
            guardrail_id="explicit_branch_finish",
            title="Branch-Abschluss explizit machen",
            source_patterns=("superpowers:finishing-a-development-branch", "superpowers:using-git-worktrees"),
            trigger="nach groesserem Branch-/PR- oder Worktree-Task",
            required_behavior=(
                "Tests vor Abschlussoptionen frisch pruefen",
                "Merge, PR, Behalten oder Verwerfen als separate Operator-Entscheidung behandeln",
                "destruktive Branch-/Worktree-Aktionen nie ohne klare Freigabe",
            ),
            required_evidence=("test result before finish", "selected finish option"),
            gate_level="situational",
            applies_to=("git_flow", "pr_flow"),
        ),
        CodingGuardrail(
            guardrail_id="skill_behavior_pressure_test",
            title="Skills gegen Verhalten testen",
            source_patterns=("superpowers:writing-skills",),
            trigger="neue oder geaenderte lokale Vega/Vivi/Codex-Skills und Playbooks",
            required_behavior=(
                "nicht nur Syntax validieren",
                "Druckszenario gegen bekannte Rationalisierungen testen",
                "Vorher/Nachher-Learning dokumentieren",
            ),
            required_evidence=("pressure scenario", "observed failure or pass behavior", "updated skill rule"),
            gate_level="situational",
            applies_to=("skill_authoring", "playbook_governance"),
        ),
    )
    return CodingGuardrailContract(
        name="Agent Coding Guardrails",
        status="active_local_playbook",
        runtime_policy="playbook_only",
        source_repos=(
            "https://github.com/obra/superpowers",
            "https://github.com/multica-ai/andrej-karpathy-skills",
        ),
        items=items,
        situational_transfers=(
            "worktree_finish_menu_for_explicit_git_flows",
            "plan_review_loop_for_large_implementation",
            "skill_pressure_testing_for_local_skill_changes",
        ),
    )


def validate_coding_guardrails(contract: CodingGuardrailContract) -> CodingGuardrailValidation:
    errors: list[str] = []
    warnings: list[str] = []
    seen: set[str] = set()
    by_id: dict[str, CodingGuardrail] = {}
    for item in contract.items:
        if item.guardrail_id in seen:
            errors.append(f"duplicate_guardrail:{item.guardrail_id}")
        seen.add(item.guardrail_id)
        by_id[item.guardrail_id] = item
        if not item.source_patterns:
            errors.append(f"missing_source_pattern:{item.guardrail_id}")
        if not item.required_behavior:
            errors.append(f"missing_required_behavior:{item.guardrail_id}")
        if item.gate_level in {"hard", "situational"} and not item.required_evidence:
            errors.append(f"missing_required_evidence:{item.guardrail_id}")
        if item.gate_level not in {"soft", "hard", "situational"}:
            errors.append(f"invalid_gate_level:{item.guardrail_id}")

    for guardrail_id in REQUIRED_GUARDRAIL_IDS:
        if guardrail_id not in by_id:
            errors.append(f"missing_guardrail:{guardrail_id}")

    for blocked_default in REQUIRED_BLOCKED_DEFAULTS:
        if blocked_default not in contract.blocked_defaults:
            errors.append(f"missing_blocked_default:{blocked_default}")

    if contract.runtime_policy != "playbook_only":
        errors.append("runtime_policy_not_playbook_only")
    if "https://github.com/obra/superpowers" not in contract.source_repos:
        warnings.append("superpowers_source_missing")
    if "https://github.com/multica-ai/andrej-karpathy-skills" not in contract.source_repos:
        warnings.append("karpathy_source_missing")
    if by_id.get("evidence_before_completion", None) and by_id["evidence_before_completion"].gate_level != "hard":
        errors.append("completion_guardrail_not_hard")
    if by_id.get("root_cause_before_fix", None) and by_id["root_cause_before_fix"].gate_level != "hard":
        errors.append("debugging_guardrail_not_hard")

    return CodingGuardrailValidation(valid=not errors, errors=tuple(errors), warnings=tuple(warnings))


def render_coding_guardrails_markdown(
    contract: CodingGuardrailContract,
    validation: CodingGuardrailValidation,
) -> str:
    lines = [
        "# Agent Coding Guardrails",
        "",
        "Kuratierter Transfer aus `obra/superpowers` und `multica-ai/andrej-karpathy-skills`.",
        "Diese Schicht ist ein lokaler Playbook-Vertrag, keine Plugin-Installation und kein Session-Hook.",
        "",
        f"Status: `{contract.status}`",
        f"Runtime-Policy: `{contract.runtime_policy}`",
        f"Gueltig: `{str(validation.valid).lower()}`",
        f"Fehler: `{', '.join(validation.errors) if validation.errors else 'keine'}`",
        f"Warnungen: `{', '.join(validation.warnings) if validation.warnings else 'keine'}`",
        "",
        "## Quellen",
        "",
    ]
    for source in contract.source_repos:
        lines.append(f"- {source}")
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "| ID | Gate | Quellenmuster | Trigger | Verhalten | Evidenz |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in contract.items:
        behavior = "<br>".join(item.required_behavior)
        evidence = "<br>".join(item.required_evidence)
        sources = "<br>".join(f"`{source}`" for source in item.source_patterns)
        lines.append(
            f"| `{item.guardrail_id}` | `{item.gate_level}` | {sources} | "
            f"{item.trigger} | {behavior} | {evidence} |"
        )
    lines.extend(
        [
            "",
            "## Situative Uebernahmen",
            "",
        ]
    )
    for transfer in contract.situational_transfers:
        lines.append(f"- `{transfer}`")
    lines.extend(
        [
            "",
            "## Geblockte Defaults",
            "",
            "Diese Muster bleiben bewusst hinter Operator-, Lizenz- oder Konflikt-Gates:",
            "",
        ]
    )
    for blocked in contract.blocked_defaults:
        lines.append(f"- `{blocked}`")
    lines.extend(
        [
            "",
            "## Nutzungsregel",
            "",
            "- Bei kleinen klaren Aufgaben nur die minimal passende Guardrail anwenden.",
            "- Bei Bugs ist `root_cause_before_fix` hart.",
            "- Vor Abschlussclaims ist `evidence_before_completion` hart.",
            "- Git-/Worktree- und Skill-Test-Patterns sind situativ, nicht global.",
        ]
    )
    return "\n".join(lines) + "\n"
