"""Semantic ownership audit for the Vega Obsidian backbone.

The older vault checks were mostly structural: links, presence, and headings.
This layer checks whether active entities still have exactly one leading project
surface and whether old project notes only mention successor lanes historically.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


DEFAULT_VAULT = Path(
    "/Users/BjornRosinger/Documents/Obsidian/Test Vaul Privat/Human Overview"
)

START_SURFACES = (
    "00 DreamFactory Home.md",
    "01 Projects.md",
    "02 Plans and Status.md",
    "03 Features.md",
    "04 Agent Start Here.md",
    "DreamFactory - Projektuebersicht.md",
    "DreamFactory – Projektübersicht.md",
    "DreamFactory - Systemhandbuch.md",
    "DreamFactory – Systemhandbuch.md",
    "Canonical/Canonical Index.md",
)

PRIMARY_PROJECTS_LINE_MARKERS = (
    "Hauptprojekte:",
    "Projektkarten:",
    "fuehrende Projektkarten:",
    "fuehrender Projektkontext:",
    "angrenzende Projekte:",
)

OLD_ACTIVE_ROUTE_PATTERNS = (
    "fuehrende Projektkarte: [[Project - Utility Wortcluster]]",
    "Fuehrendes Projektumfeld: [[Project - Utility Wortcluster]]",
    "Projektkarte: [[Project - Utility Wortcluster]]",
)

HISTORICAL_MARKERS = (
    "historisch",
    "historische",
    "historischer",
    "historische damalige",
    "historisches projektumfeld",
    "historischer ursprung",
    "historische herkunft",
)

WORTCLUSTER_ALLOWED_STATUSES = (
    "status: waiting",
    "status: parked_no_current_intent",
)


@dataclass(frozen=True)
class SemanticFinding:
    severity: str
    check_id: str
    file: str
    line: int
    summary: str
    action: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AuditViewpoint:
    viewpoint_id: str
    title: str
    question: str
    catches: str
    operator_relief: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class VaultSemanticAudit:
    valid: bool
    vault: str
    findings: tuple[SemanticFinding, ...]
    viewpoints: tuple[AuditViewpoint, ...]
    checked_files: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "valid": self.valid,
            "vault": self.vault,
            "findings": [finding.to_dict() for finding in self.findings],
            "viewpoints": [viewpoint.to_dict() for viewpoint in self.viewpoints],
            "checked_files": list(self.checked_files),
        }


def default_viewpoints() -> tuple[AuditViewpoint, ...]:
    return (
        AuditViewpoint(
            viewpoint_id="ownership",
            title="Ownership statt Linkstatus",
            question="Welche Karte fuehrt diese Entitaet heute?",
            catches="Aktive Nachfolge-Lanes in alten Projektkarten.",
            operator_relief="Bjorn muss nicht merken, welche alte Note frueher fuehrend war.",
        ),
        AuditViewpoint(
            viewpoint_id="start_surface_alignment",
            title="Startflaechen-Abgleich",
            question="Zeigen Human-, Agenten-, System- und Canonical-Starts dieselbe aktive Spur?",
            catches="Neue Projektkarten, die nur in einer Detailnote sichtbar sind.",
            operator_relief="Neue Sessions starten richtig, ohne dass der Operator routen muss.",
        ),
        AuditViewpoint(
            viewpoint_id="body_semantics",
            title="Body-Semantik statt Frontmatter",
            question="Widersprechen alte Abschnitte dem Status oben in der Note?",
            catches="Notes mit korrektem `waiting`/`parked` Status, aber aktiv klingenden Body-Abschnitten.",
            operator_relief="Vivi/Vega muessen nicht aus Chronik-Waenden die Fuehrung erraten.",
        ),
        AuditViewpoint(
            viewpoint_id="negative_routing",
            title="Negative Routing-Tests",
            question="Gibt es noch aktive Phrasen, die auf die alte Karte zeigen?",
            catches="Saetze wie `fuehrende Projektkarte: alte Karte`.",
            operator_relief="Alte Gewohnheitsrouten werden maschinell sichtbar.",
        ),
        AuditViewpoint(
            viewpoint_id="status_aging",
            title="Status- und Review-Aging",
            question="Sind alte offene Punkte noch offen oder durch spaetere Wahrheit geschlossen?",
            catches="Review-Queue-Leichen und alte `active` Roadmaps.",
            operator_relief="Der Operator muss nicht alte Warteschlangen mental abgleichen.",
        ),
        AuditViewpoint(
            viewpoint_id="gate_inversion",
            title="Gate-Inversion",
            question="Wird ein lokaler/verifizierter Stand irgendwo als Public-/Production-Go gelesen?",
            catches="Gruene lokale Tests, die als externe Freigabe missverstanden werden.",
            operator_relief="Operator-Gates bleiben sichtbar, statt aus Testgruens zu verschwinden.",
        ),
        AuditViewpoint(
            viewpoint_id="successor_predecessor",
            title="Nachfolger-/Vorgaenger-Spur",
            question="Ist klar, was historischer Ursprung und was aktuelle operative Flaeche ist?",
            catches="Materialbedarf/Elterngeld als aktive Wahrheit unter Wortcluster.",
            operator_relief="Projektwechsel muessen nicht aus Erinnerung rekonstruiert werden.",
        ),
        AuditViewpoint(
            viewpoint_id="operator_intent_extraction",
            title="Operator-Intent-Extraktion",
            question="Welche wiederholte Operator-Sorge steckt hinter dem aktuellen Prompt?",
            catches="Audits, die erst laufen, wenn Bjorn sie exakt benennt.",
            operator_relief="Bjorn muss die Systemklasse nicht jedes Mal selbst formulieren.",
        ),
        AuditViewpoint(
            viewpoint_id="workflow_not_mutation",
            title="Automatic-by-Workflow",
            question="Kann der Check automatisch report-only laufen, ohne kanonisches Memory zu mutieren?",
            catches="Entweder kein wiederholbarer Check oder riskante stille Autowrites.",
            operator_relief="Routinepruefungen laufen mit, aber echte Vault-Aenderungen bleiben bewusst.",
        ),
    )


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _lines(text: str) -> list[str]:
    return text.splitlines()


def _is_historical_line(line: str) -> bool:
    lower = line.lower()
    return any(marker in lower for marker in HISTORICAL_MARKERS)


def _relative(vault: Path, path: Path) -> str:
    try:
        return path.relative_to(vault).as_posix()
    except ValueError:
        return str(path)


def _add_missing_file(findings: list[SemanticFinding], vault: Path, relative_path: str) -> None:
    findings.append(
        SemanticFinding(
            severity="block",
            check_id="required_vault_file_missing",
            file=relative_path,
            line=0,
            summary=f"Erwartete Vault-Datei fehlt: {relative_path}",
            action="Datei anlegen oder Audit-Regel aktualisieren.",
        )
    )


def _line_contains_all(line: str, terms: Sequence[str]) -> bool:
    return all(term in line for term in terms)


def audit_vault_semantic_ownership(vault: Path = DEFAULT_VAULT) -> VaultSemanticAudit:
    vault = vault.resolve()
    findings: list[SemanticFinding] = []
    checked_files: set[str] = set()

    portfolio = vault / "Project - Utility Websites Portfolio.md"
    wortcluster = vault / "Project - Utility Wortcluster.md"
    if not portfolio.exists():
        _add_missing_file(findings, vault, "Project - Utility Websites Portfolio.md")
    if not wortcluster.exists():
        _add_missing_file(findings, vault, "Project - Utility Wortcluster.md")

    portfolio_text = _read(portfolio)
    wortcluster_text = _read(wortcluster)
    if portfolio.exists():
        checked_files.add(_relative(vault, portfolio))
    if wortcluster.exists():
        checked_files.add(_relative(vault, wortcluster))

    for term in ("Materialbedarf", "Elterngeld", "Microtool"):
        if portfolio.exists() and term not in portfolio_text:
            findings.append(
                SemanticFinding(
                    severity="high",
                    check_id="portfolio_missing_active_lane_term",
                    file=_relative(vault, portfolio),
                    line=0,
                    summary=f"Utility Websites Portfolio nennt aktive Lane `{term}` nicht.",
                    action="Aktive Utility-Lanes in der fuehrenden Portfolio-Karte sichtbar halten.",
                )
            )

    if wortcluster.exists():
        if not any(status in wortcluster_text for status in WORTCLUSTER_ALLOWED_STATUSES):
            findings.append(
                SemanticFinding(
                    severity="high",
                    check_id="wortcluster_not_waiting_or_parked",
                    file=_relative(vault, wortcluster),
                    line=0,
                    summary="Utility Wortcluster ist nicht eindeutig `waiting` oder `parked_no_current_intent`.",
                    action="Wortcluster nur bei echter Solver-Reaktivierung auf aktiv stellen; sonst parked/waiting halten.",
                )
            )
        if (
            any(term in wortcluster_text for term in ("Materialbedarf", "Elterngeld", "Microtool"))
            and "Historische Utility-Websites-Migrationsspur" not in wortcluster_text
        ):
            findings.append(
                SemanticFinding(
                    severity="high",
                    check_id="wortcluster_active_terms_without_history_marker",
                    file=_relative(vault, wortcluster),
                    line=0,
                    summary="Wortcluster nennt aktive Website-Lanes ohne historischen Abschnitt.",
                    action="Aktive Lanes ins Portfolio routen und alte Vorkommen historisch markieren.",
                )
            )

    for relative_path in START_SURFACES:
        path = vault / relative_path
        if not path.exists():
            continue
        checked_files.add(_relative(vault, path))
        text = _read(path)
        if "[[Project - Utility Websites Portfolio]]" not in text:
            findings.append(
                SemanticFinding(
                    severity="high",
                    check_id="start_surface_missing_utility_portfolio",
                    file=_relative(vault, path),
                    line=0,
                    summary="Startflaeche nennt Utility Websites Portfolio nicht.",
                    action="Aktive Utility-Websites in allen Startflaechen sichtbar machen.",
                )
            )

    for path in vault.rglob("*.md"):
        relative = _relative(vault, path)
        text = _read(path)
        for line_no, line in enumerate(_lines(text), start=1):
            for pattern in OLD_ACTIVE_ROUTE_PATTERNS:
                if pattern in line and not _is_historical_line(line):
                    findings.append(
                        SemanticFinding(
                            severity="high",
                            check_id="old_active_route_phrase",
                            file=relative,
                            line=line_no,
                            summary=f"Aktive alte Routing-Phrase gefunden: {pattern}",
                            action=(
                                "Als historischen Ursprung markieren oder auf "
                                "[[Project - Utility Websites Portfolio]] umstellen."
                            ),
                        )
                    )
            if any(marker in line for marker in PRIMARY_PROJECTS_LINE_MARKERS):
                old_project_list = _line_contains_all(
                    line,
                    (
                        "[[Project - LIONCOM Dashboard]]",
                        "[[Project - Membership Finanzplattform]]",
                        "[[Project - Utility Wortcluster]]",
                        "[[Project - Quellwert]]",
                    ),
                )
                if old_project_list and "[[Project - Utility Websites Portfolio]]" not in line:
                    findings.append(
                        SemanticFinding(
                            severity="high",
                            check_id="project_list_missing_utility_portfolio",
                            file=relative,
                            line=line_no,
                            summary="Projektliste enthaelt alte Hauptprojekte ohne Utility Websites Portfolio.",
                            action="Projektliste auf aktive und wartende Utility-Spuren nachziehen.",
                        )
                    )

    review_queue = vault / "Review Queue.md"
    if review_queue.exists():
        checked_files.add(_relative(vault, review_queue))
        if "Review Queue Aging Audit" not in _read(review_queue):
            findings.append(
                SemanticFinding(
                    severity="warn",
                    check_id="review_queue_aging_missing",
                    file=_relative(vault, review_queue),
                    line=0,
                    summary="Review Queue hat keinen Aging-Audit-Anker.",
                    action="Aging-Pass mit still_open/closed/historical/operator_gate anlegen.",
                )
            )

    valid = not any(finding.severity in {"block", "high"} for finding in findings)
    return VaultSemanticAudit(
        valid=valid,
        vault=str(vault),
        findings=tuple(findings),
        viewpoints=default_viewpoints(),
        checked_files=tuple(sorted(checked_files)),
    )


def render_vault_semantic_audit_markdown(audit: VaultSemanticAudit) -> str:
    lines = [
        "# Vault Semantic Ownership Audit",
        "",
        "Dieser Bericht prueft semantische Ownership-Drift im Vega/Obsidian-Backbone.",
        "Er ist kein Security-Audit, sondern ein Operator-Entlastungscheck: "
        "Vivi und Vega sollen falsche alte Projektwahrheit finden, bevor Bjorn sie benennen muss.",
        "",
        f"Gueltig: `{str(audit.valid).lower()}`",
        f"Vault: `{audit.vault}`",
        f"Gepruefte Dateien: `{len(audit.checked_files)}`",
        f"Findings: `{len(audit.findings)}`",
        "",
        "## Blickwinkel",
        "",
        "| ID | Blickwinkel | Prueffrage | Findet | Operator-Entlastung |",
        "| --- | --- | --- | --- | --- |",
    ]
    for viewpoint in audit.viewpoints:
        lines.append(
            f"| `{viewpoint.viewpoint_id}` | {viewpoint.title} | {viewpoint.question} | "
            f"{viewpoint.catches} | {viewpoint.operator_relief} |"
        )

    lines.extend(["", "## Findings", ""])
    if not audit.findings:
        lines.append("Keine Blocker oder High-Findings.")
    else:
        lines.extend(["| Schwere | Check | Datei | Zeile | Befund | Aktion |", "| --- | --- | --- | ---: | --- | --- |"])
        for finding in audit.findings:
            lines.append(
                f"| `{finding.severity}` | `{finding.check_id}` | `{finding.file}` | "
                f"{finding.line} | {finding.summary} | {finding.action} |"
            )

    lines.extend(
        [
            "",
            "## Workflow-Regel",
            "",
            "- Vor jedem Claim `Vault ist sauber` oder `Backbone ist aktuell` diesen Audit laufen lassen.",
            "- Der Audit ist report-only: Er schreibt keine kanonischen Obsidian-Notizen.",
            "- Automations duerfen Findings melden und naechste Aktionen vorschlagen, aber nicht automatisch Memory mutieren.",
            "",
            "```bash",
            "python3 scripts/ops/vault_semantic_audit.py --output-dir outputs/vault_semantic_audit",
            "python3 scripts/ops/agent_os_readiness.py",
            "```",
        ]
    )

    lines.extend(["", "## Gepruefte Dateien", ""])
    for file in audit.checked_files:
        lines.append(f"- `{file}`")
    return "\n".join(lines).rstrip() + "\n"


def audit_to_json(audit: VaultSemanticAudit) -> str:
    return json.dumps(audit.to_dict(), indent=2, sort_keys=True) + "\n"
