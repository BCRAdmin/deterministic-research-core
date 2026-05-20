#!/usr/bin/env python3
"""Local read-only inventory scan for internal skill/playbook risk markers.

This helper performs static text checks only. It does not import project code,
execute files, call a network, write outputs, or print secret values.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_TARGETS = (
    "docs/skills",
    "docs/media_ingest",
    "docs/github",
    "scripts",
)

SKIP_DIRS = {
    ".git",
    ".next",
    ".cache",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
}

TEXT_SUFFIXES = {
    ".md",
    ".json",
    ".py",
    ".sh",
    ".mjs",
    ".js",
    ".ts",
    ".tsx",
    ".yaml",
    ".yml",
    ".toml",
    ".txt",
}


@dataclass(frozen=True)
class Rule:
    risk_type: str
    severity: str
    reason: str
    pattern: re.Pattern[str]
    allowed: bool
    operator_gate_needed: bool


@dataclass(frozen=True)
class Finding:
    file: str
    line: int
    risk_type: str
    severity: str
    reason: str
    allowed: bool
    operator_gate_needed: bool


RULES = (
    Rule(
        "network_call",
        "high",
        "Potential network or download behavior requires intake review.",
        re.compile(r"\b(curl|wget|requests\.|fetch\(|axios\.|urllib\.request|http[s]?://)", re.I),
        False,
        True,
    ),
    Rule(
        "filesystem_write",
        "medium",
        "Potential filesystem write or destructive file operation.",
        re.compile(r"\b(write_text|write_bytes|open\([^)]*['\"]w|rm\s+-|mv\s+|cp\s+|apply_patch|mkdir\s+-p|touch\s+)", re.I),
        True,
        True,
    ),
    Rule(
        "credential_reference",
        "high",
        "Credential or secret reference must not expose values and needs review.",
        re.compile(r"\b(secret|token|api[_-]?key|oauth|password|credential|bearer)\b", re.I),
        False,
        True,
    ),
    Rule(
        "environment_variable",
        "medium",
        "Environment variable access may imply configuration or secret handling.",
        re.compile(r"\b(os\.environ|getenv|process\.env|\$[A-Z][A-Z0-9_]{2,})\b"),
        True,
        True,
    ),
    Rule(
        "auto_update_behavior",
        "high",
        "Auto-update behavior is blocked unless explicitly approved.",
        re.compile(r"\b(auto[-_ ]?update|self[-_ ]?update|silent update|update_url|polling)\b", re.I),
        False,
        True,
    ),
    Rule(
        "background_execution",
        "high",
        "Background, daemon or scheduled behavior needs an explicit gate.",
        re.compile(r"\b(cron|daemon|background|launchctl|nohup|systemd|heartbeat|schedule)\b", re.I),
        False,
        True,
    ),
    Rule(
        "obsidian_write",
        "high",
        "Obsidian writes must pass the memory promotion gate.",
        re.compile(r"\b(Obsidian|Human Overview|Backbone|Latest Session Context|vault)\b.*\b(write|update|overwrite|sync)\b", re.I),
        False,
        True,
    ),
    Rule(
        "github_mutation",
        "high",
        "GitHub mutations require explicit Operator-Go.",
        re.compile(r"\b(gh\s+(issue|pr|release)\s+(create|edit|comment|merge|close)|git\s+push|git\s+tag)\b", re.I),
        False,
        True,
    ),
    Rule(
        "api_call",
        "medium",
        "API behavior requires scope review.",
        re.compile(r"\b(api|endpoint|webhook|graphql|rest)\b", re.I),
        True,
        True,
    ),
)


def iter_files(root: Path, targets: Iterable[str]) -> Iterable[Path]:
    for target in targets:
        start = root / target
        if not start.exists():
            continue
        if start.is_file():
            yield start
            continue
        for current_root, dirnames, filenames in os.walk(start):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for filename in filenames:
                path = Path(current_root) / filename
                if path.suffix.lower() in TEXT_SUFFIXES:
                    yield path


def scan_file(path: Path, root: Path) -> list[Finding]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []

    findings: list[Finding] = []
    rel = str(path.relative_to(root))
    is_executable = os.access(path, os.X_OK) or path.suffix.lower() in {".py", ".sh", ".mjs", ".js"}
    if is_executable and rel.startswith("scripts/"):
        findings.append(
            Finding(
                file=rel,
                line=1,
                risk_type="executable_script",
                severity="medium",
                reason="Executable helper requires syntax validation and bounded scope.",
                allowed=True,
                operator_gate_needed=True,
            )
        )

    for lineno, line in enumerate(text.splitlines(), 1):
        for rule in RULES:
            if rule.pattern.search(line):
                findings.append(
                    Finding(
                        file=rel,
                        line=lineno,
                        risk_type=rule.risk_type,
                        severity=rule.severity,
                        reason=rule.reason,
                        allowed=rule.allowed,
                        operator_gate_needed=rule.operator_gate_needed,
                    )
                )
    return findings


def render_markdown(findings: list[Finding]) -> str:
    lines = [
        "# Local Skill Inventory Risk Scan",
        "",
        f"Findings: {len(findings)}",
        "",
        "| File | Line | Risk type | Severity | Allowed | Operator gate | Reason |",
        "| --- | ---: | --- | --- | ---: | ---: | --- |",
    ]
    for item in findings:
        lines.append(
            f"| `{item.file}` | {item.line} | `{item.risk_type}` | `{item.severity}` | "
            f"{str(item.allowed).lower()} | {str(item.operator_gate_needed).lower()} | {item.reason} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a local read-only risk scan over internal playbook files.")
    parser.add_argument("--root", default=".", help="Workspace root. Default: current directory.")
    parser.add_argument("--format", choices=("json", "md"), default="json", help="Output format.")
    parser.add_argument("--target", action="append", help="Additional or replacement target path. Can be repeated.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    targets = tuple(args.target) if args.target else DEFAULT_TARGETS
    findings: list[Finding] = []
    for path in sorted(set(iter_files(root, targets))):
        findings.extend(scan_file(path, root))

    findings.sort(key=lambda f: (f.file, f.line, f.risk_type))
    if args.format == "json":
        print(json.dumps({"status": "completed", "findings": [asdict(f) for f in findings]}, indent=2))
    else:
        print(render_markdown(findings), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
