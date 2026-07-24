"""Documents-root hygiene checks for Vega/Vivi workspaces."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re


RETIRED_ROOT_NAMES = {
    "New project": (
        "retired_new_project_root_present",
        "project_intelligence_graph",
    ),
    "New project 2": (
        "retired_new_project_2_root_present",
        "research_agent_ops",
    ),
    "Room 16 Reports": (
        "retired_room16_reports_root_present",
        "room16_reports",
    ),
    "wp-stb-roesinger-redesign": (
        "retired_wp_stb_root_present",
        "client_prototype_wp_stb",
    ),
    "LIONCOM Vivi Ablage": (
        "retired_lioncom_vivi_ablag_root_present",
        "lioncom_runtime",
    ),
    "System optimization": (
        "retired_system_optimization_root_present",
        "dreamfactory_tools",
    ),
}

FORBIDDEN_ROOT_DIRS = {
    "New%20project": "url_encoded_bug_leftover",
    "docs": "root_runtime_leak",
    "dashboard": "root_runtime_leak",
    "prompts": "root_runtime_leak",
}

ALLOWED_OPERATOR_APP_ROOTS = {
    "Midjurney",
}

GENERIC_NAME_PATTERNS = (
    re.compile(r"^new project(?:\s+\d+)?$", re.IGNORECASE),
    re.compile(r"^new folder(?:\s+\d+)?$", re.IGNORECASE),
    re.compile(r"^untitled folder(?:\s+\d+)?$", re.IGNORECASE),
    re.compile(r"^neuer ordner(?:\s+\d+)?$", re.IGNORECASE),
    re.compile(r"^project(?:\s+\d+)?$", re.IGNORECASE),
    re.compile(r"^projekt(?:\s+\d+)?$", re.IGNORECASE),
)


@dataclass(frozen=True)
class DocumentsRootFinding:
    severity: str
    path: str
    code: str
    message: str
    recommendation: str


def canonical_paths(documents_root: Path) -> dict[str, Path]:
    return {
        "project_intelligence_graph": documents_root
        / "DreamFactory"
        / "Project-Intelligence-Graph",
        "room16_reports": documents_root / "DreamFactory" / "Room16" / "Reports",
        "research_agent_ops": documents_root
        / "DreamFactory"
        / "Room16"
        / "research-agent-ops",
        "client_prototypes": documents_root / "BCR Ventures" / "client-prototypes",
        "client_prototype_wp_stb": documents_root
        / "BCR Ventures"
        / "client-prototypes"
        / "wp-stb-roesinger-redesign",
        "lioncom_runtime": documents_root / "DreamFactory" / "LIONCOM" / ".runtime",
        "dreamfactory_tools": documents_root / "DreamFactory" / "Tools",
        "root_compatibility_links_archive": documents_root
        / "Codex"
        / "path-hygiene-compatibility-links"
        / "2026-05-28"
        / "root-links",
        "path_hygiene_quarantine": documents_root
        / "Codex"
        / "path-hygiene-quarantine"
        / "2026-05-28"
        / "root-leaks",
    }


def _is_generic_forbidden_name(name: str) -> bool:
    return any(pattern.match(name) for pattern in GENERIC_NAME_PATTERNS)


def scan_documents_root(documents_root: Path, desktop_root: Path | None = None) -> dict[str, object]:
    root = documents_root.expanduser().resolve()
    desktop = (
        desktop_root.expanduser().resolve()
        if desktop_root is not None
        else root.parent / "Desktop"
    )
    paths = canonical_paths(root)
    findings: list[DocumentsRootFinding] = []

    if not root.exists():
        findings.append(
            DocumentsRootFinding(
                "error",
                str(root),
                "documents_root_missing",
                "Documents root does not exist.",
                "Use an existing Documents root before creating project folders.",
            )
        )
        return _payload(root, findings)

    if desktop.exists():
        for markdown_file in sorted(
            [
                *desktop.glob("*.md"),
                *desktop.glob("*.markdown"),
            ],
            key=lambda path: path.name.lower(),
        ):
            findings.append(
                DocumentsRootFinding(
                    "error",
                    str(markdown_file),
                    "desktop_markdown_output_present",
                    "Markdown files must not be left on the Desktop.",
                    "Move durable notes into the active Obsidian vault, BCR Ventures, DreamFactory, Codex pending-placement, or another approved namespace.",
                )
            )

    for child in sorted(root.iterdir(), key=lambda path: path.name.lower()):
        if not child.is_dir() and not child.is_symlink():
            continue
        name = child.name
        if name in ALLOWED_OPERATOR_APP_ROOTS:
            continue
        if name in RETIRED_ROOT_NAMES:
            code, canonical_key = RETIRED_ROOT_NAMES[name]
            canonical_path = paths[canonical_key]
            findings.append(
                DocumentsRootFinding(
                    "error",
                    str(child),
                    code,
                    "Retired legacy root path must not exist directly under Documents.",
                    f"Use canonical path `{canonical_path}`. Historical root links, if needed, belong under `{paths['root_compatibility_links_archive']}`.",
                )
            )
            continue
        if name in FORBIDDEN_ROOT_DIRS:
            findings.append(
                DocumentsRootFinding(
                    "error",
                    str(child),
                    FORBIDDEN_ROOT_DIRS[name],
                    "Project or runtime material is misplaced directly under Documents.",
                    "Move it into an approved namespace such as DreamFactory, BCR Ventures, Codex, or Obsidian.",
                )
            )
            continue
        if _is_generic_forbidden_name(name):
            findings.append(
                DocumentsRootFinding(
                    "error",
                    str(child),
                    "generic_project_folder_name",
                    "Generic project folder names are forbidden at Documents root.",
                    "Choose an explicit namespace and project slug before creating files.",
                )
            )

    canonical_pig = paths["project_intelligence_graph"]
    if not canonical_pig.exists():
        findings.append(
            DocumentsRootFinding(
                "error",
                str(canonical_pig),
                "canonical_project_intelligence_graph_missing",
                "Canonical Project Intelligence Graph workspace is missing.",
                "Restore it before running Vega/PIG/LIONCOM/Room16 control flows.",
            )
        )

    canonical_reports = paths["room16_reports"]
    if not canonical_reports.exists():
        findings.append(
            DocumentsRootFinding(
                "error",
                str(canonical_reports),
                "canonical_room16_reports_missing",
                "Canonical Room16 reports folder is missing.",
                "Create it before running Room16 shelf/report flows.",
            )
        )

    canonical_research_agent_ops = paths["research_agent_ops"]
    if not canonical_research_agent_ops.exists():
        findings.append(
            DocumentsRootFinding(
                "error",
                str(canonical_research_agent_ops),
                "canonical_research_agent_ops_missing",
                "Canonical Room16 research-agent ops workspace is missing.",
                "Restore it before running Quellwert/Room16/Agent-OS verifier flows.",
            )
        )

    canonical_prototype = paths["client_prototype_wp_stb"]
    if not canonical_prototype.exists():
        findings.append(
            DocumentsRootFinding(
                "error",
                str(canonical_prototype),
                "canonical_client_prototype_missing",
                "Canonical wp-stb client prototype folder is missing.",
                "Restore it under BCR Ventures before continuing client-prototype work.",
            )
        )

    legacy_bcr_ventures = root / "BCR Group" / "BCR Ventures"
    if legacy_bcr_ventures.exists():
        findings.append(
            DocumentsRootFinding(
                "error",
                str(legacy_bcr_ventures),
                "duplicate_bcr_ventures_root_present",
                "BCR Ventures must not exist in two Documents namespaces.",
                f"Use only `{root / 'BCR Ventures'}`.",
            )
        )

    return _payload(root, findings)


def _payload(root: Path, findings: list[DocumentsRootFinding]) -> dict[str, object]:
    errors = [finding for finding in findings if finding.severity == "error"]
    warnings = [finding for finding in findings if finding.severity == "warning"]
    return {
        "ok": not errors,
        "documents_root": str(root),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "findings": [asdict(finding) for finding in findings],
        "canonical_paths": {key: str(value) for key, value in canonical_paths(root).items()},
    }


def render_markdown(payload: dict[str, object]) -> str:
    lines = [
        "# Documents Root Hygiene Check",
        "",
        f"- Status: `{'PASS' if payload['ok'] else 'FAIL'}`",
        f"- Documents root: `{payload['documents_root']}`",
        f"- Errors: `{payload['error_count']}`",
        f"- Warnings: `{payload['warning_count']}`",
        "",
        "## Findings",
        "",
    ]
    findings = payload.get("findings", [])
    if not findings:
        lines.append("- No findings.")
    else:
        for finding in findings:
            lines.append(
                "- `{severity}` `{path}` - {code}: {message} Recommendation: {recommendation}".format(
                    **finding
                )
            )
    lines.extend(["", "## Canonical Paths", ""])
    for key, value in payload["canonical_paths"].items():
        lines.append(f"- `{key}`: `{value}`")
    return "\n".join(lines) + "\n"
