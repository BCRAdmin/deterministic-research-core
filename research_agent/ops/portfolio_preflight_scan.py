"""Local preflight scan for portfolio handoffs and pushes."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_MAX_TEXT_SCAN_BYTES = 1_000_000
DEFAULT_LARGE_FILE_BYTES = 50 * 1024 * 1024

GENERATED_PATH_PARTS = {
    ".next",
    ".runtime",
    "__pycache__",
    "dist-desktop",
    "node_modules",
    "out",
}

BLOCKED_ARCHIVE_SUFFIXES = {
    ".7z",
    ".dmg",
    ".gz",
    ".pkg",
    ".tar",
    ".tgz",
    ".zip",
}

SECRET_PATTERNS = [
    ("private_key_block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |)?PRIVATE KEY-----")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{30,}\b")),
    ("slack_token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{20,}\b")),
    ("openai_style_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    (
        "assigned_secret_value",
        re.compile(
            r"(?i)\b(?:api[_-]?key|token|secret|password|webhook[_-]?secret)"
            r"\s*[:=]\s*[\"']?[A-Za-z0-9_./+=:-]{24,}"
        ),
    ),
]


@dataclass(frozen=True)
class ChangedPath:
    status: str
    path: str


@dataclass(frozen=True)
class PreflightFinding:
    severity: str
    check_id: str
    path: str
    detail: str


@dataclass(frozen=True)
class PreflightReport:
    repo: str
    changed_count: int
    findings: tuple[PreflightFinding, ...]

    @property
    def blocking_findings(self) -> tuple[PreflightFinding, ...]:
        return tuple(finding for finding in self.findings if finding.severity == "block")

    @property
    def review_findings(self) -> tuple[PreflightFinding, ...]:
        return tuple(finding for finding in self.findings if finding.severity == "review")

    @property
    def ok(self) -> bool:
        return not self.blocking_findings


def _run_git_status(repo: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain=v1", "--untracked-files=all"],
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout


def changed_paths(repo: Path) -> tuple[ChangedPath, ...]:
    changes: list[ChangedPath] = []
    for raw_line in _run_git_status(repo).splitlines():
        if not raw_line:
            continue
        status = raw_line[:2]
        path_text = raw_line[3:]
        if " -> " in path_text:
            path_text = path_text.split(" -> ", 1)[1]
        changes.append(ChangedPath(status=status.strip() or "M", path=path_text.strip('"')))
    return tuple(changes)


def _path_parts(relative_path: str) -> tuple[str, ...]:
    return Path(relative_path).parts


def _is_binary(path: Path) -> bool:
    try:
        sample = path.read_bytes()[:4096]
    except OSError:
        return True
    return b"\0" in sample


def _iter_text_lines(path: Path, *, max_bytes: int = DEFAULT_MAX_TEXT_SCAN_BYTES) -> Iterable[tuple[int, str]]:
    if not path.is_file() or path.stat().st_size > max_bytes or _is_binary(path):
        return ()
    try:
        return tuple(enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1))
    except OSError:
        return ()


def _scan_secret_patterns(path: Path, relative_path: str) -> list[PreflightFinding]:
    findings: list[PreflightFinding] = []
    for line_number, line in _iter_text_lines(path):
        for check_id, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append(
                    PreflightFinding(
                        severity="block",
                        check_id=check_id,
                        path=relative_path,
                        detail=f"possible secret pattern near line {line_number}",
                    )
                )
                return findings
    return findings


def scan_changed_paths(
    repo: Path,
    *,
    large_file_bytes: int = DEFAULT_LARGE_FILE_BYTES,
) -> PreflightReport:
    repo = repo.resolve()
    findings: list[PreflightFinding] = []
    changes = changed_paths(repo)
    for change in changes:
        if change.status == "D":
            continue
        relative_path = change.path
        path = repo / relative_path
        if not path.exists():
            continue
        parts = _path_parts(relative_path)
        suffix = path.suffix.lower()

        generated_parts = set(parts).intersection(GENERATED_PATH_PARTS)
        if generated_parts:
            findings.append(
                PreflightFinding(
                    severity="block",
                    check_id="generated_runtime_or_build_path",
                    path=relative_path,
                    detail=f"changed generated path part: {', '.join(sorted(generated_parts))}",
                )
            )

        if suffix in BLOCKED_ARCHIVE_SUFFIXES:
            findings.append(
                PreflightFinding(
                    severity="block",
                    check_id="archive_or_release_artifact",
                    path=relative_path,
                    detail=f"changed archive/release suffix: {suffix}",
                )
            )

        if path.is_file() and path.stat().st_size > large_file_bytes:
            findings.append(
                PreflightFinding(
                    severity="block",
                    check_id="large_changed_file",
                    path=relative_path,
                    detail=f"size={path.stat().st_size} bytes limit={large_file_bytes}",
                )
            )

        if parts and parts[0] == "outputs":
            findings.append(
                PreflightFinding(
                    severity="review",
                    check_id="outputs_tree_changed",
                    path=relative_path,
                    detail="outputs/ changes are evidence or generated state; confirm before commit",
                )
            )

        findings.extend(_scan_secret_patterns(path, relative_path))

    return PreflightReport(repo=str(repo), changed_count=len(changes), findings=tuple(findings))


def report_to_json(report: PreflightReport) -> str:
    return json.dumps(
        {
            "repo": report.repo,
            "ok": report.ok,
            "changed_count": report.changed_count,
            "blocking_count": len(report.blocking_findings),
            "review_count": len(report.review_findings),
            "findings": [asdict(finding) for finding in report.findings],
        },
        indent=2,
        sort_keys=True,
    )


def render_markdown(report: PreflightReport) -> str:
    verdict = "PASS" if report.ok else "BLOCK"
    lines = [
        "# Portfolio Preflight Scan",
        "",
        f"- Repo: `{report.repo}`",
        f"- Verdict: `{verdict}`",
        f"- Changed paths: `{report.changed_count}`",
        f"- Blocking findings: `{len(report.blocking_findings)}`",
        f"- Review findings: `{len(report.review_findings)}`",
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
