"""Documents-root hygiene checks for Vega/Vivi workspaces."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re


LEGACY_WORKSPACE_NAMES = {
    "New project": "legacy_active_pig_lioncom_room16_workspace",
}

MIGRATED_COMPATIBILITY_LINKS = {
    "New project 2": (
        "legacy_research_agent_ops_compatibility_symlink",
        "research_agent_ops",
    ),
}

FORBIDDEN_ROOT_DIRS = {
    "New%20project": "url_encoded_bug_leftover",
    "docs": "root_runtime_leak",
    "dashboard": "root_runtime_leak",
    "prompts": "root_runtime_leak",
}

KNOWN_RENAME_REVIEW_DIRS = {
    "Midjurney": "documented_project_but_misspelled_name",
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
        "room16_reports": documents_root / "DreamFactory" / "Room16" / "Reports",
        "research_agent_ops": documents_root
        / "DreamFactory"
        / "Room16"
        / "research-agent-ops",
        "client_prototypes": documents_root / "BCR Ventures" / "client-prototypes",
        "path_hygiene_quarantine": documents_root
        / "Codex"
        / "path-hygiene-quarantine"
        / "2026-05-28"
        / "root-leaks",
    }


def _is_generic_forbidden_name(name: str) -> bool:
    return any(pattern.match(name) for pattern in GENERIC_NAME_PATTERNS)


def scan_documents_root(documents_root: Path) -> dict[str, object]:
    root = documents_root.expanduser().resolve()
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

    for child in sorted(root.iterdir(), key=lambda path: path.name.lower()):
        if not child.is_dir() and not child.is_symlink():
            continue
        name = child.name
        if name in LEGACY_WORKSPACE_NAMES:
            findings.append(
                DocumentsRootFinding(
                    "warning",
                    str(child),
                    LEGACY_WORKSPACE_NAMES[name],
                    "Legacy workspace remains allowed only because it is already referenced.",
                    "Do not create more generic `New project` workspaces; migrate this one formally later.",
                )
            )
            continue
        if name in MIGRATED_COMPATIBILITY_LINKS:
            code, canonical_key = MIGRATED_COMPATIBILITY_LINKS[name]
            canonical_path = paths[canonical_key]
            if child.is_symlink() and child.resolve() == canonical_path.resolve():
                findings.append(
                    DocumentsRootFinding(
                        "warning",
                        str(child),
                        code,
                        "Migrated legacy workspace root link exists for compatibility only.",
                        f"Use canonical workspace `{canonical_path}` for new work.",
                    )
                )
            else:
                findings.append(
                    DocumentsRootFinding(
                        "error",
                        str(child),
                        "migrated_workspace_must_be_symlink",
                        "New project 2 was migrated and must not be a real Documents-root workspace anymore.",
                        f"Move the real workspace to `{canonical_path}` and leave only a compatibility symlink.",
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
        if name in KNOWN_RENAME_REVIEW_DIRS:
            findings.append(
                DocumentsRootFinding(
                    "warning",
                    str(child),
                    KNOWN_RENAME_REVIEW_DIRS[name],
                    "Known project folder remains usable but has a spelling/name issue.",
                    "Migrate it with Vault-link updates instead of creating another root folder.",
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

    reports_link = root / "Room 16 Reports"
    canonical_reports = paths["room16_reports"]
    if reports_link.exists() or reports_link.is_symlink():
        if reports_link.is_symlink() and reports_link.resolve() == canonical_reports.resolve():
            findings.append(
                DocumentsRootFinding(
                    "warning",
                    str(reports_link),
                    "legacy_compatibility_symlink",
                    "Legacy Room 16 Reports root link exists for compatibility only.",
                    f"Write new Room16 reports to `{canonical_reports}`.",
                )
            )
        else:
            findings.append(
                DocumentsRootFinding(
                    "error",
                    str(reports_link),
                    "room16_reports_root_folder",
                    "Room 16 Reports must not be a real root folder anymore.",
                    f"Move data to `{canonical_reports}` and leave only a compatibility symlink if needed.",
                )
            )
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

    prototype_link = root / "wp-stb-roesinger-redesign"
    canonical_prototype = paths["client_prototypes"] / "wp-stb-roesinger-redesign"
    if prototype_link.exists() or prototype_link.is_symlink():
        if prototype_link.is_symlink() and prototype_link.resolve() == canonical_prototype.resolve():
            findings.append(
                DocumentsRootFinding(
                    "warning",
                    str(prototype_link),
                    "legacy_client_prototype_symlink",
                    "Legacy wp-stb root link exists for compatibility only.",
                    f"Write new prototype files to `{canonical_prototype}`.",
                )
            )
        else:
            findings.append(
                DocumentsRootFinding(
                    "error",
                    str(prototype_link),
                    "client_prototype_must_live_under_bcr_ventures",
                    "Client prototype material must not be a real root folder.",
                    f"Move it to `{canonical_prototype}` and leave only a compatibility symlink if needed.",
                )
            )
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
