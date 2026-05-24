"""Portfolio-Produktoberflächen-Audit.

Diese Schicht prüft die kanonischen Projektkarten gegen den
Deliverable-Swarm-Vertrag. Sie ist absichtlich ein lokaler Review-Output:
keine Runtime-Mutation, keine automatischen Obsidian-Schreibrechte und keine
externen Provider-Aktionen.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional, Sequence


SURFACE_MARKERS = (
    "## Produktoberflächen-Check",
    "## Deliverable-/Produktoberflächen-Check",
    "## Lieferoberfläche",
    "## Produktoberflaechen-Check",
    "## Deliverable-/Produktoberflaechen-Check",
    "## Lieferoberflaeche",
)

REQUIRED_PROJECT_HEADINGS = (
    "## Kurzbild",
    "## Aktueller Stand",
    "## Nächster sinnvoller Schnitt",
)

LEGACY_REQUIRED_PROJECT_HEADINGS = {
    "## Nächster sinnvoller Schnitt": ("## Naechster sinnvoller Schnitt",),
}


@dataclass(frozen=True)
class ProjectSurfaceSpec:
    project_id: str
    title: str
    note_relative_path: str
    expected_statuses: tuple[str, ...]
    owner_lanes: tuple[str, ...]
    visible_surfaces: tuple[str, ...]
    required_terms: tuple[str, ...]
    gate_terms: tuple[str, ...]
    next_safe_action: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SurfaceFinding:
    project_id: str
    severity: str
    check_id: str
    summary: str
    action: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ProjectSurfaceResult:
    project_id: str
    title: str
    note_path: str
    note_present: bool
    declared_status: str
    audit_status: str
    owner_lanes: tuple[str, ...]
    visible_surfaces: tuple[str, ...]
    blocked_gates: tuple[str, ...]
    next_safe_action: str
    findings: tuple[SurfaceFinding, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["findings"] = [finding.to_dict() for finding in self.findings]
        return payload


@dataclass(frozen=True)
class PortfolioSurfaceAudit:
    valid: bool
    vault: str
    results: tuple[ProjectSurfaceResult, ...]
    findings: tuple[SurfaceFinding, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "valid": self.valid,
            "vault": self.vault,
            "results": [result.to_dict() for result in self.results],
            "findings": [finding.to_dict() for finding in self.findings],
        }


def default_project_surface_specs() -> list[ProjectSurfaceSpec]:
    return [
        ProjectSurfaceSpec(
            project_id="lioncom_dashboard",
            title="LIONCOM Dashboard",
            note_relative_path="Project - LIONCOM Dashboard.md",
            expected_statuses=("active",),
            owner_lanes=("orchestrator", "assistant", "docs"),
            visible_surfaces=(
                "Operator-Control-Plane",
                "Portfolio-Control-Tower",
                "Vivi/Vega-Claim- und Gate-Sicht",
            ),
            required_terms=("Operator", "Vivi", "Vega", "Control"),
            gate_terms=("Gate", "Verifier", "Operator-Go"),
            next_safe_action=(
                "Lieferoberflaeche als Reentry-Karte halten: aktive Lane, "
                "Output-Pfad, Verifier, blockiertes Gate und naechste Aktion."
            ),
        ),
        ProjectSurfaceSpec(
            project_id="membership_finanzplattform",
            title="Membership Finanzplattform",
            note_relative_path="Project - Membership Finanzplattform.md",
            expected_statuses=("active",),
            owner_lanes=("research", "docs", "assistant"),
            visible_surfaces=(
                "Proof-first Webseite",
                "Waitlist-/Founder-Funnel",
                "Support-/Activation-Readiness",
            ),
            required_terms=("Proof", "Waitlist", "Provider", "Launch"),
            gate_terms=("Operator-Go", "Provider", "Checkout", "Mail"),
            next_safe_action=(
                "Nur Research-, Readiness- und Preview-Lieferobjekte öffnen, "
                "bis Provider, Geld, Mail und echte externe Sends explizit frei sind."
            ),
        ),
        ProjectSurfaceSpec(
            project_id="utility_wortcluster",
            title="Utility Wortcluster",
            note_relative_path="Project - Utility Wortcluster.md",
            expected_statuses=("waiting", "parked_no_current_intent"),
            owner_lanes=("research", "data", "docs"),
            visible_surfaces=("Wortquelle", "Regelset", "Solver-MVP"),
            required_terms=("Wortquelle", "Regelset", "Solver"),
            gate_terms=("parked_no_current_intent", "Datenquellen-Hold", "Methodik"),
            next_safe_action=(
                "Keine Solverarbeit starten; nur bei ausdruecklicher Reaktivierung "
                "Wortquelle, Regelset und Datenschema neu entscheiden."
            ),
        ),
        ProjectSurfaceSpec(
            project_id="utility_websites_portfolio",
            title="Utility Websites Portfolio",
            note_relative_path="Project - Utility Websites Portfolio.md",
            expected_statuses=("active",),
            owner_lanes=("research", "data", "docs"),
            visible_surfaces=(
                "Materialbedarf-Rechner",
                "Mein Elterngeldrechner",
                "Microtool Starter Kit",
            ),
            required_terms=("Materialbedarf", "Elterngeld", "Microtool"),
            gate_terms=("GSC", "Messvertrag", "Trust"),
            next_safe_action=(
                "Aktive Website-Lanes getrennt vom wartenden Wortcluster fuehren "
                "und jede Folgemassnahme an Mess-, Trust- oder Opportunity-Gates binden."
            ),
        ),
        ProjectSurfaceSpec(
            project_id="quellwert",
            title="Quellwert",
            note_relative_path="Project - Quellwert.md",
            expected_statuses=("local_preview",),
            owner_lanes=("research", "data", "docs"),
            visible_surfaces=(
                "Research-/Archiv-/Methodik-Webseite",
                "Room16-Promotion-Queue",
                "Public-Preview-Gates",
            ),
            required_terms=("Research", "Archiv", "Methodik", "Room16"),
            gate_terms=("Promotion", "public_ready", "Operator-Go", "Non-Advice"),
            next_safe_action=(
                "Research-/Archiv-/Methodik-Vertrauen stärken; Public-Promotion "
                "nur über Source-Ledger, Non-Advice, Human Source Verification und Operator-Go."
            ),
        ),
    ]


def _extract_frontmatter_status(text: str) -> str:
    match = re.match(r"---\n(?P<frontmatter>.*?)\n---", text, flags=re.DOTALL)
    if not match:
        return "unknown"
    status_match = re.search(r"^status:\s*(?P<status>[^\n]+)$", match.group("frontmatter"), re.MULTILINE)
    if not status_match:
        return "unknown"
    return status_match.group("status").strip().strip("'\"")


def _has_any(text: str, terms: Sequence[str]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def _missing_terms(text: str, terms: Sequence[str]) -> tuple[str, ...]:
    lowered = text.lower()
    return tuple(term for term in terms if term.lower() not in lowered)


def _surface_marker_present(text: str) -> bool:
    return _has_any(text, SURFACE_MARKERS)


def _audit_single_project(spec: ProjectSurfaceSpec, vault: Path) -> ProjectSurfaceResult:
    note = vault / spec.note_relative_path
    findings: list[SurfaceFinding] = []
    if not note.exists():
        finding = SurfaceFinding(
            project_id=spec.project_id,
            severity="block",
            check_id="project_note_missing",
            summary=f"Projektkarte fehlt: {note}",
            action="Projektkarte anlegen oder Projekt aus dem aktiven Portfolio entfernen.",
        )
        return ProjectSurfaceResult(
            project_id=spec.project_id,
            title=spec.title,
            note_path=str(note),
            note_present=False,
            declared_status="missing",
            audit_status="blocked",
            owner_lanes=spec.owner_lanes,
            visible_surfaces=spec.visible_surfaces,
            blocked_gates=spec.gate_terms,
            next_safe_action=spec.next_safe_action,
            findings=(finding,),
        )

    text = note.read_text(encoding="utf-8")
    declared_status = _extract_frontmatter_status(text)

    if declared_status not in spec.expected_statuses:
        findings.append(
            SurfaceFinding(
                project_id=spec.project_id,
                severity="high",
                check_id="unexpected_project_status",
                summary=(
                    f"Status `{declared_status}` passt nicht zu erwartet "
                    f"`{', '.join(spec.expected_statuses)}`."
                ),
                action="Status oder Projekt-Routing im Backbone korrigieren.",
            )
        )

    for heading in REQUIRED_PROJECT_HEADINGS:
        accepted_headings = (heading, *LEGACY_REQUIRED_PROJECT_HEADINGS.get(heading, ()))
        if not any(accepted in text for accepted in accepted_headings):
            findings.append(
                SurfaceFinding(
                    project_id=spec.project_id,
                    severity="high",
                    check_id=f"missing_heading:{heading}",
                    summary=f"Führungsheading fehlt: `{heading}`.",
                    action="Projektkarte auf Kurzbild, aktuelle Wahrheit und nächsten Schnitt normalisieren.",
                )
            )

    if not _surface_marker_present(text):
        findings.append(
            SurfaceFinding(
                project_id=spec.project_id,
                severity="high",
                check_id="missing_product_surface_check",
                summary="Expliziter Produktoberflächen-Check fehlt.",
                action=(
                    "Abschnitt `Produktoberflächen-Check` mit sichtbarer "
                    "Oberfläche, Lanes, Gates und nächster sicherer Aktion ergänzen."
                ),
            )
        )

    missing_required = _missing_terms(text, spec.required_terms)
    if missing_required:
        findings.append(
            SurfaceFinding(
                project_id=spec.project_id,
                severity="high",
                check_id="missing_surface_terms",
                summary=f"Pflichtbegriffe fehlen: `{', '.join(missing_required)}`.",
                action="Projektkarte muss die reale sichtbare Lieferoberfläche benennen.",
            )
        )

    if not _has_any(text, spec.gate_terms):
        findings.append(
            SurfaceFinding(
                project_id=spec.project_id,
                severity="high",
                check_id="missing_gate_terms",
                summary=f"Keiner der Gate-Begriffe gefunden: `{', '.join(spec.gate_terms)}`.",
                action="Blockierte Gates explizit eintragen, statt Status implizit zu lassen.",
            )
        )

    if spec.project_id == "utility_wortcluster":
        active_website_terms = ("Materialbedarf", "Elterngeld", "Microtool")
        split_terms = (
            "[[Project - Utility Websites Portfolio]]",
            "Utility-Websites-Portfolio ist eine eigene aktive Projektkarte",
        )
        portfolio_note_exists = (vault / "Project - Utility Websites Portfolio.md").exists()
        if _has_any(text, active_website_terms) and not (_has_any(text, split_terms) and portfolio_note_exists):
            findings.append(
                SurfaceFinding(
                    project_id=spec.project_id,
                    severity="high",
                    check_id="utility_active_lanes_mixed_into_waiting_project",
                    summary=(
                        "Wartender Wortcluster enthaelt aktive Materialbedarf-/Elterngeld-/"
                        "Microtool-Wahrheit ohne eigene Portfolio-Projektkarte."
                    ),
                    action=(
                        "Aktive Utility-Websites in eine eigene Projektkarte routen und "
                        "Wortcluster wieder als wartenden Solver-MVP führen."
                    ),
                )
            )

    if any(finding.severity == "block" for finding in findings):
        audit_status = "blocked"
    elif any(finding.severity == "high" for finding in findings):
        audit_status = "needs_repair"
    else:
        audit_status = "verified_local_surface"

    return ProjectSurfaceResult(
        project_id=spec.project_id,
        title=spec.title,
        note_path=str(note),
        note_present=True,
        declared_status=declared_status,
        audit_status=audit_status,
        owner_lanes=spec.owner_lanes,
        visible_surfaces=spec.visible_surfaces,
        blocked_gates=spec.gate_terms,
        next_safe_action=spec.next_safe_action,
        findings=tuple(findings),
    )


def audit_portfolio_surfaces(
    vault: Path,
    specs: Optional[Sequence[ProjectSurfaceSpec]] = None,
) -> PortfolioSurfaceAudit:
    vault = vault.resolve()
    selected_specs = tuple(specs or default_project_surface_specs())
    results = tuple(_audit_single_project(spec, vault) for spec in selected_specs)
    findings = tuple(finding for result in results for finding in result.findings)
    valid = not any(finding.severity in {"block", "high"} for finding in findings)
    return PortfolioSurfaceAudit(valid=valid, vault=str(vault), results=results, findings=findings)


def render_portfolio_surface_markdown(audit: PortfolioSurfaceAudit) -> str:
    lines = [
        "# Portfolio-Produktoberflächen-Audit",
        "",
        "Dieser Bericht prüft die aktiven Projektkarten einzeln gegen die Frage: "
        "Gibt es eine sichtbare Lieferoberfläche mit Owner-Lane, Output, Verifier, "
        "Gate und nächster sicherer Aktion?",
        "",
        f"Gültig: `{str(audit.valid).lower()}`",
        f"Vault: `{audit.vault}`",
        f"Projektkarten: `{len(audit.results)}`",
        f"Findings: `{len(audit.findings)}`",
        "",
        "## Matrix",
        "",
        "| Projekt | Status | Audit | Lanes | Sichtbare Oberflächen | Gates | Nächste sichere Aktion |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for result in audit.results:
        lines.append(
            f"| {result.title} | `{result.declared_status}` | `{result.audit_status}` | "
            f"`{', '.join(result.owner_lanes)}` | {', '.join(result.visible_surfaces)} | "
            f"`{', '.join(result.blocked_gates)}` | {result.next_safe_action} |"
        )

    lines.extend(["", "## Findings", ""])
    if not audit.findings:
        lines.append("Keine Blocker oder High-Findings.")
    else:
        lines.extend(["| Projekt | Schwere | Check | Befund | Aktion |", "| --- | --- | --- | --- | --- |"])
        for finding in audit.findings:
            lines.append(
                f"| `{finding.project_id}` | `{finding.severity}` | `{finding.check_id}` | "
                f"{finding.summary} | {finding.action} |"
            )

    lines.extend(["", "## Projekt-Details", ""])
    for result in audit.results:
        lines.extend(
            [
                f"### {result.title}",
                "",
                f"- Projekt-ID: `{result.project_id}`",
                f"- Projektkarte: `{result.note_path}`",
                f"- Audit-Status: `{result.audit_status}`",
                f"- Owner-Lanes: `{', '.join(result.owner_lanes)}`",
                f"- Sichtbare Oberflächen: {', '.join(result.visible_surfaces)}",
                f"- Blockierte Gates: `{', '.join(result.blocked_gates)}`",
                f"- Nächste sichere Aktion: {result.next_safe_action}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_portfolio_surface_canvas(audit: PortfolioSurfaceAudit) -> str:
    nodes: list[dict[str, object]] = [
        {
            "id": "portfolio-audit",
            "type": "file",
            "file": "outputs/agent_os_readiness/PORTFOLIO_PRODUCT_SURFACE_AUDIT.md",
            "x": 0,
            "y": 0,
            "width": 520,
            "height": 260,
            "color": "4",
        },
        {
            "id": "deliverable-swarm-contract",
            "type": "file",
            "file": "docs/agent_os/DELIVERABLE_SWARM_CONTRACT.md",
            "x": -680,
            "y": 0,
            "width": 460,
            "height": 220,
            "color": "5",
        },
        {
            "id": "audit-rule",
            "type": "text",
            "text": (
                "Prüfregel\n\nJede Projektkarte braucht sichtbare Oberfläche, "
                "Owner-Lanes, Gate-Begriffe und nächste sichere Aktion. "
                "Wartende und aktive Produkte dürfen nicht in derselben Wahrheit verschwimmen."
            ),
            "x": 680,
            "y": 0,
            "width": 520,
            "height": 260,
            "color": "6",
        },
    ]
    edges: list[dict[str, object]] = [
        {
            "id": "edge-contract-audit",
            "fromNode": "deliverable-swarm-contract",
            "fromSide": "right",
            "toNode": "portfolio-audit",
            "toSide": "left",
            "toEnd": "arrow",
            "label": "liefert Lane-Vertrag",
        },
        {
            "id": "edge-rule-audit",
            "fromNode": "audit-rule",
            "fromSide": "left",
            "toNode": "portfolio-audit",
            "toSide": "right",
            "toEnd": "arrow",
            "label": "prüft",
        },
    ]

    x_positions = (-980, -480, 40, 560, 1080)
    for index, result in enumerate(audit.results):
        node_id = f"project-{result.project_id}"
        findings = len(result.findings)
        text = (
            f"{result.title}\n\n"
            f"Status: {result.declared_status}\n"
            f"Audit: {result.audit_status}\n"
            f"Lanes: {', '.join(result.owner_lanes)}\n"
            f"Findings: {findings}\n\n"
            f"Nächste Aktion: {result.next_safe_action}"
        )
        nodes.append(
            {
                "id": node_id,
                "type": "text",
                "text": text,
                "x": x_positions[index % len(x_positions)],
                "y": 420 + (index // len(x_positions)) * 320,
                "width": 460,
                "height": 260,
                "color": "2" if result.findings else "4",
            }
        )
        edges.append(
            {
                "id": f"edge-audit-{result.project_id}",
                "fromNode": "portfolio-audit",
                "fromSide": "bottom",
                "toNode": node_id,
                "toSide": "top",
                "toEnd": "arrow",
                "label": "Projektcheck",
            }
        )

    return json.dumps({"nodes": nodes, "edges": edges}, indent=2, ensure_ascii=False) + "\n"
