"""Local verifier for the Block 8 skill-pattern governance contract."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Optional


SUMMARY_PATH = "outputs/skill_playbooks/REMAINING_SKILL_PATTERN_IMPLEMENTATION_SUMMARY.json"
HOLD_REGISTER_PATH = "docs/skills/HIGH_RISK_SKILLS_HOLD_REGISTER.json"
HELPER_PATH = "scripts/skills/local_skill_inventory_scan.py"

REQUIRED_PLAYBOOK_FILES = (
    "docs/documents/DOCX_WORKFLOW_PLAYBOOK.md",
    "docs/documents/DOCX_WORKFLOW_PLAYBOOK.json",
    "docs/spreadsheets/XLSX_WORKFLOW_PLAYBOOK.md",
    "docs/spreadsheets/XLSX_WORKFLOW_PLAYBOOK.json",
    "docs/pdf/PDF_RENDER_PLAYBOOK.md",
    "docs/pdf/PDF_RENDER_PLAYBOOK.json",
    "docs/writing/HUMANIZER_LINT_PLAYBOOK.md",
    "docs/writing/HUMANIZER_LINT_PLAYBOOK.json",
    "docs/automation/AUTOMATION_WORKFLOWS_PLAYBOOK.md",
    "docs/automation/AUTOMATION_WORKFLOWS_PLAYBOOK.json",
    "docs/skills/LOCAL_SKILL_INVENTORY_RISK_SCAN.md",
    "docs/skills/LOCAL_SKILL_INVENTORY_RISK_SCAN.json",
    "docs/media_ingest/NEXT_MEDIA_SAMPLE_BACKLOG.md",
    "docs/media_ingest/NEXT_MEDIA_SAMPLE_BACKLOG.json",
    "docs/skills/HIGH_RISK_SKILLS_HOLD_REGISTER.md",
    "docs/skills/HIGH_RISK_SKILLS_HOLD_REGISTER.json",
)

REQUIRED_NOT_IMPLEMENTED = {
    "external_skill_installation",
    "runtime_integration",
    "api_gateway",
    "desktop_control",
    "proactive_agent_full_autonomy",
    "remote_skillscan_phone_home_scanner",
    "auto_updates",
    "obsidian_autowrites",
    "public_or_publishing_action",
    "file_conversion_without_explicit_operator_input",
}

REQUIRED_HOLD_ITEM_NAMES = {
    "api-gateway",
    "desktop-control",
    "proactive-agent full autonomy",
    "external self-improving runtime",
    "remote skillscan/phone-home scanner",
}

REQUIRED_FUTURE_SANDBOX_CONDITIONS = {
    "source_verification",
    "explicit_operator_gate",
    "no_credentials_unless_separately_approved",
}

BLOCKED_HELPER_SOURCE_MARKERS = (
    "import subprocess",
    "requests.",
    "urllib.request",
    ".write_text(",
    ".write_bytes(",
)


@dataclass(frozen=True)
class GovernanceFinding:
    severity: str
    check_id: str
    path: str
    detail: str


@dataclass(frozen=True)
class GovernanceReport:
    repo: str
    checked_files: tuple[str, ...]
    findings: tuple[GovernanceFinding, ...]

    @property
    def blocking_findings(self) -> tuple[GovernanceFinding, ...]:
        return tuple(finding for finding in self.findings if finding.severity == "block")

    @property
    def ok(self) -> bool:
        return not self.blocking_findings


def _finding(check_id: str, path: str, detail: str) -> GovernanceFinding:
    return GovernanceFinding(severity="block", check_id=check_id, path=path, detail=detail)


def _load_json(repo: Path, relative_path: str, findings: list[GovernanceFinding]) -> Optional[Any]:
    path = repo / relative_path
    if not path.exists():
        findings.append(_finding("missing_json", relative_path, "required JSON file is missing"))
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        findings.append(
            _finding("invalid_json", relative_path, f"JSON parse failed at line {exc.lineno}")
        )
        return None


def _require_files(repo: Path, relative_paths: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(path for path in relative_paths if (repo / path).exists()))


def _missing_from(actual: Iterable[str], required: Iterable[str]) -> set[str]:
    return set(required).difference(set(actual))


def _check_required_files(repo: Path, findings: list[GovernanceFinding]) -> tuple[str, ...]:
    checked_files = set(_require_files(repo, REQUIRED_PLAYBOOK_FILES))
    for relative_path in REQUIRED_PLAYBOOK_FILES:
        if not (repo / relative_path).exists():
            findings.append(
                _finding("missing_playbook", relative_path, "required pattern playbook is missing")
            )
    return tuple(sorted(checked_files))


def _check_summary(summary: dict[str, Any], findings: list[GovernanceFinding]) -> None:
    if summary.get("status") != "completed":
        findings.append(
            _finding(
                "summary_status_not_completed",
                SUMMARY_PATH,
                "implementation summary status must be completed",
            )
        )
    if summary.get("runtime_changes") != "none":
        findings.append(
            _finding("summary_runtime_changed", SUMMARY_PATH, "runtime_changes must remain none")
        )

    created_playbooks = summary.get("created_playbooks")
    if not isinstance(created_playbooks, list):
        findings.append(
            _finding(SUMMARY_PATH, SUMMARY_PATH, "created_playbooks must be a list")
        )
    else:
        for missing in sorted(_missing_from(created_playbooks, REQUIRED_PLAYBOOK_FILES)):
            findings.append(
                _finding(
                    "summary_missing_playbook",
                    SUMMARY_PATH,
                    f"created_playbooks does not list {missing}",
                )
            )

    not_implemented = summary.get("not_implemented")
    if not isinstance(not_implemented, list):
        findings.append(
            _finding(SUMMARY_PATH, SUMMARY_PATH, "not_implemented must be a list")
        )
    else:
        for missing in sorted(_missing_from(not_implemented, REQUIRED_NOT_IMPLEMENTED)):
            findings.append(
                _finding(
                    "summary_missing_blocked_runtime",
                    SUMMARY_PATH,
                    f"not_implemented does not list {missing}",
                )
            )

    helper_scripts = summary.get("helper_scripts")
    if not isinstance(helper_scripts, list):
        findings.append(
            _finding(SUMMARY_PATH, SUMMARY_PATH, "helper_scripts must be a list")
        )
        return

    helper = next(
        (item for item in helper_scripts if isinstance(item, dict) and item.get("path") == HELPER_PATH),
        None,
    )
    if helper is None:
        findings.append(
            _finding("summary_missing_helper", SUMMARY_PATH, f"helper_scripts must list {HELPER_PATH}")
        )
        return

    expected = {
        "mode": "local_read_only",
        "network": "none",
        "writes": "none",
        "secret_printing": False,
    }
    for key, value in expected.items():
        if helper.get(key) != value:
            findings.append(
                _finding(
                    "helper_contract_changed",
                    SUMMARY_PATH,
                    f"{HELPER_PATH} must keep {key}={value!r}",
                )
            )


def _check_hold_register(register: dict[str, Any], findings: list[GovernanceFinding]) -> None:
    if register.get("status") != "active":
        findings.append(
            _finding(
                "hold_register_status_not_active",
                HOLD_REGISTER_PATH,
                "hold register status must be active",
            )
        )
    if register.get("runtime_changes") != "none":
        findings.append(
            _finding(
                "hold_register_runtime_changed",
                HOLD_REGISTER_PATH,
                "runtime_changes must remain none",
            )
        )

    conditions = register.get("future_sandbox_conditions")
    if not isinstance(conditions, list):
        findings.append(
            _finding(
                HOLD_REGISTER_PATH,
                HOLD_REGISTER_PATH,
                "future_sandbox_conditions must be a list",
            )
        )
    else:
        for missing in sorted(_missing_from(conditions, REQUIRED_FUTURE_SANDBOX_CONDITIONS)):
            findings.append(
                _finding(
                    "hold_register_missing_condition",
                    HOLD_REGISTER_PATH,
                    f"future_sandbox_conditions does not list {missing}",
                )
            )

    items = register.get("items")
    if not isinstance(items, list):
        findings.append(
            _finding(HOLD_REGISTER_PATH, HOLD_REGISTER_PATH, "items must be a list")
        )
        return

    item_by_name = {
        item.get("name"): item
        for item in items
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    for missing in sorted(REQUIRED_HOLD_ITEM_NAMES.difference(item_by_name)):
        findings.append(
            _finding("missing_hold_item", HOLD_REGISTER_PATH, f"missing hold item {missing}")
        )

    for name in sorted(REQUIRED_HOLD_ITEM_NAMES.intersection(item_by_name)):
        item = item_by_name[name]
        if item.get("operator_gate_required") is not True:
            findings.append(
                _finding("hold_item_missing_operator_gate", HOLD_REGISTER_PATH, f"{name} needs gate")
            )
        forbidden = item.get("forbidden_runtime_behavior")
        if not isinstance(forbidden, list) or not forbidden:
            findings.append(
                _finding(
                    "hold_item_missing_forbidden_runtime",
                    HOLD_REGISTER_PATH,
                    f"{name} needs forbidden runtime behavior",
                )
            )
        if not item.get("allowed_pattern_extraction"):
            findings.append(
                _finding(
                    "hold_item_missing_allowed_pattern",
                    HOLD_REGISTER_PATH,
                    f"{name} needs allowed pattern extraction",
                )
            )


def _check_helper_source(repo: Path, findings: list[GovernanceFinding]) -> tuple[str, ...]:
    helper = repo / HELPER_PATH
    if not helper.exists():
        findings.append(_finding("missing_helper", HELPER_PATH, "local inventory helper is missing"))
        return ()

    text = helper.read_text(encoding="utf-8", errors="ignore")
    for marker in BLOCKED_HELPER_SOURCE_MARKERS:
        if marker in text:
            findings.append(
                _finding(
                    "helper_source_marker_blocked",
                    HELPER_PATH,
                    f"helper source contains blocked marker {marker!r}",
                )
            )
    required_claims = (
        "does not import project code",
        "call a network",
        "write outputs",
        "print secret values",
    )
    for claim in required_claims:
        if claim not in text:
            findings.append(
                _finding(
                    "helper_missing_safety_claim",
                    HELPER_PATH,
                    f"helper source must state safety claim: {claim}",
                )
            )
    return (HELPER_PATH,)


def check_skill_pattern_governance(repo: Path) -> GovernanceReport:
    repo = repo.resolve()
    findings: list[GovernanceFinding] = []
    checked_files = set(_check_required_files(repo, findings))

    summary = _load_json(repo, SUMMARY_PATH, findings)
    if isinstance(summary, dict):
        checked_files.add(SUMMARY_PATH)
        _check_summary(summary, findings)

    register = _load_json(repo, HOLD_REGISTER_PATH, findings)
    if isinstance(register, dict):
        checked_files.add(HOLD_REGISTER_PATH)
        _check_hold_register(register, findings)

    checked_files.update(_check_helper_source(repo, findings))
    findings.sort(key=lambda finding: (finding.path, finding.check_id, finding.detail))
    return GovernanceReport(
        repo=str(repo),
        checked_files=tuple(sorted(checked_files)),
        findings=tuple(findings),
    )


def report_to_json(report: GovernanceReport) -> str:
    return json.dumps(
        {
            "repo": report.repo,
            "ok": report.ok,
            "checked_count": len(report.checked_files),
            "blocking_count": len(report.blocking_findings),
            "checked_files": list(report.checked_files),
            "findings": [asdict(finding) for finding in report.findings],
        },
        indent=2,
        sort_keys=True,
    )


def render_markdown(report: GovernanceReport) -> str:
    verdict = "PASS" if report.ok else "BLOCK"
    lines = [
        "# Skill Pattern Governance Check",
        "",
        f"- Repo: `{report.repo}`",
        f"- Verdict: `{verdict}`",
        f"- Checked files: `{len(report.checked_files)}`",
        f"- Blocking findings: `{len(report.blocking_findings)}`",
        "",
    ]
    if not report.findings:
        lines.append("No findings.")
        return "\n".join(lines) + "\n"

    lines.append("| Severity | Check | Path | Detail |")
    lines.append("| --- | --- | --- | --- |")
    for finding in report.findings:
        lines.append(
            f"| `{finding.severity}` | `{finding.check_id}` | `{finding.path}` | {finding.detail} |"
        )
    return "\n".join(lines) + "\n"
