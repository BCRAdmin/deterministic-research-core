"""Static guardrails for agent operating-system style workflows.

The goal is to make the highest-value policy checks executable without turning
them into an autonomous runtime. All checks are local, deterministic, and
redact evidence before it can be printed.
"""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence


TEXT_SUFFIXES = {
    ".md",
    ".json",
    ".py",
    ".sh",
    ".js",
    ".mjs",
    ".ts",
    ".tsx",
    ".yaml",
    ".yml",
    ".toml",
    ".txt",
}

SKIP_DIRS = {
    ".git",
    ".next",
    ".cache",
    ".ruff_cache",
    ".pytest_cache",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
}

MAX_TEXT_BYTES = 1_000_000


@dataclass(frozen=True)
class GuardrailRule:
    check_id: str
    category: str
    severity: str
    message: str
    pattern: re.Pattern[str]
    operator_gate_required: bool = True


@dataclass(frozen=True)
class GuardrailFinding:
    check_id: str
    category: str
    severity: str
    message: str
    file: str
    line: int
    evidence: str
    operator_gate_required: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


COMMAND_RULES: tuple[GuardrailRule, ...] = (
    GuardrailRule(
        "cmd_recursive_delete_root_or_home",
        "dangerous_command",
        "block",
        "Recursive delete against root or home-like targets must never run without a hard gate.",
        re.compile(r"\brm\s+-[^\n;]*r[^\n;]*(\s/|\s~|\s\$HOME\b|\s\.\.)", re.I),
    ),
    GuardrailRule(
        "cmd_force_git_history_rewrite",
        "dangerous_command",
        "block",
        "Hard resets, forced pushes, branch deletion, or git clean are destructive.",
        re.compile(r"\bgit\s+(reset\s+--hard|clean\s+-[^\n;]*f|push\s+--force|branch\s+-D)\b", re.I),
    ),
    GuardrailRule(
        "cmd_remote_pipe_to_shell",
        "dangerous_command",
        "block",
        "Remote install scripts piped to a shell require explicit source review.",
        re.compile(r"\b(curl|wget)\b[^\n|;]*\|\s*(bash|sh|zsh|python|ruby)\b", re.I),
    ),
    GuardrailRule(
        "cmd_disk_or_system_mutation",
        "dangerous_command",
        "block",
        "Disk formatting, raw device writes, service changes, and machine shutdown are gated.",
        re.compile(r"\b(mkfs|dd\s+[^;\n]*of=/dev/|shutdown|reboot|systemctl\s+(stop|restart)|launchctl\s+unload)\b", re.I),
    ),
    GuardrailRule(
        "cmd_permission_broadening",
        "dangerous_command",
        "high",
        "Broad chmod/chown can expose or damage project files.",
        re.compile(r"\b(chmod|chown)\s+-R\b|chmod\s+777", re.I),
    ),
    GuardrailRule(
        "cmd_sql_destructive",
        "dangerous_command",
        "high",
        "Destructive SQL must be reviewed, especially without an explicit WHERE clause.",
        re.compile(r"\b(DROP\s+TABLE|TRUNCATE\s+TABLE|DELETE\s+FROM(?![^\n;]*\bWHERE\b))", re.I),
    ),
)

CONTEXT_RULES: tuple[GuardrailRule, ...] = (
    GuardrailRule(
        "ctx_prompt_injection_ignore",
        "prompt_injection",
        "high",
        "Context file appears to instruct the agent to ignore higher-priority instructions.",
        re.compile(r"\b(ignore|disregard|override)\b.{0,80}\b(previous|system|developer|instruction)", re.I),
    ),
    GuardrailRule(
        "ctx_secret_exfiltration",
        "prompt_injection",
        "block",
        "Context file appears to request secret or prompt exfiltration.",
        re.compile(r"\b(reveal|print|exfiltrate|dump|send)\b.{0,80}\b(secret|token|api key|system prompt|developer message)", re.I),
    ),
    GuardrailRule(
        "ctx_hidden_instruction",
        "prompt_injection",
        "medium",
        "Hidden or encoded instructions should be reviewed before prompt injection.",
        re.compile(r"\b(base64|rot13|hidden instruction|invisible unicode|zero-width)\b", re.I),
    ),
)

SECRET_RULES: tuple[GuardrailRule, ...] = (
    GuardrailRule(
        "secret_private_key",
        "secret_print_guard",
        "block",
        "Private key material must not be printed or committed.",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ),
    GuardrailRule(
        "secret_api_key_assignment",
        "secret_print_guard",
        "high",
        "Possible secret assignment; evidence is redacted.",
        re.compile(
            r"\b([A-Za-z0-9_]*api[_-]?key|secret|token|password|bearer)\b\s*[:=]\s*"
            r"['\"]?[A-Za-z0-9_\-]{16,}",
            re.I,
        ),
    ),
)

AUTOMATION_RULES: tuple[GuardrailRule, ...] = (
    GuardrailRule(
        "auto_runtime_mutation",
        "automation_prompt",
        "high",
        "Automation prompts must not mutate runtime, credentials, launches, or public state.",
        re.compile(
            r"\b(deploy|publish|release|push|git\s+merge|merge\s+(to|into)\s+(main|production)|"
            r"delete|enable ads|affiliate live|"
            r"change dns|rotate secret|oauth|api key|production)\b",
            re.I,
        ),
    ),
    GuardrailRule(
        "auto_scope_drift",
        "automation_prompt",
        "medium",
        "Automation prompt should include no-action and stop-condition language.",
        re.compile(r"\b(keep working|continue indefinitely|whatever is useful|find more tasks)\b", re.I),
    ),
)

SKILL_PACKAGE_RULES: tuple[GuardrailRule, ...] = (
    GuardrailRule(
        "skill_network_or_install",
        "skill_package",
        "high",
        "Skill package mentions network, downloads, installs, or package execution.",
        re.compile(r"\b(curl|wget|pip install|npm install|pnpm add|http[s]?://|requests\.|fetch\()\b", re.I),
    ),
    GuardrailRule(
        "skill_background_or_self_modify",
        "skill_package",
        "high",
        "Background, self-update, or self-modifying behavior must stay gated.",
        re.compile(r"\b(cron|daemon|background|auto[-_ ]?update|self[-_ ]?modify|watcher|scheduler)\b", re.I),
    ),
    GuardrailRule(
        "skill_memory_write",
        "skill_package",
        "high",
        "Memory writes require the Obsidian promotion gate.",
        re.compile(r"\b(memory|obsidian|vault|Human Overview|Backbone)\b.{0,80}\b(write|update|sync|overwrite)\b", re.I),
    ),
)

RULESETS: dict[str, tuple[GuardrailRule, ...]] = {
    "command": COMMAND_RULES,
    "context": CONTEXT_RULES + SECRET_RULES,
    "automation": AUTOMATION_RULES + SECRET_RULES,
    "skill": SKILL_PACKAGE_RULES + SECRET_RULES + CONTEXT_RULES,
    "all": COMMAND_RULES + CONTEXT_RULES + SECRET_RULES + AUTOMATION_RULES + SKILL_PACKAGE_RULES,
}


def redact_evidence(text: str) -> str:
    """Return a one-line evidence snippet without exposing likely secret values."""

    snippet = " ".join(text.strip().split())
    snippet = re.sub(
        r"(?i)(api[_-]?key|secret|token|password|bearer)(\s*[:=]\s*['\"]?)[A-Za-z0-9_\-./+=]{8,}",
        r"\1\2[REDACTED]",
        snippet,
    )
    snippet = re.sub(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*", "[REDACTED_PRIVATE_KEY]", snippet)
    return snippet[:220]


def _is_policy_negation(line: str) -> bool:
    lower = line.lower()
    negation_markers = (
        "do not",
        "does not",
        "must not",
        "should not",
        "not ",
        " no ",
        "no_",
        "never",
        "without gate",
        "without explicit",
        "blocked",
        "forbidden",
        "hold",
        "reject",
        "kein",
        "keine",
        "nicht",
    )
    return any(marker in f" {lower} " for marker in negation_markers)


def _is_schema_reference(line: str) -> bool:
    return '"$schema"' in line or "'$schema'" in line


def iter_text_files(root: Path, targets: Sequence[str]) -> Iterable[Path]:
    for target in targets:
        start = (root / target).resolve() if not Path(target).is_absolute() else Path(target)
        if not start.exists():
            continue
        if start.is_file() and start.suffix.lower() in TEXT_SUFFIXES:
            yield start
            continue
        if not start.is_dir():
            continue
        for current_root, dirnames, filenames in os.walk(start):
            dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
            for filename in filenames:
                path = Path(current_root) / filename
                if path.suffix.lower() in TEXT_SUFFIXES:
                    yield path


def scan_text(text: str, *, file: str = "<text>", scan_type: str = "all") -> list[GuardrailFinding]:
    rules = RULESETS.get(scan_type)
    if rules is None:
        raise ValueError(f"unknown scan_type: {scan_type}")

    findings: list[GuardrailFinding] = []
    previous_line = ""
    for line_number, line in enumerate(text.splitlines() or [text], 1):
        for rule in rules:
            if _is_schema_reference(line) and rule.check_id == "skill_network_or_install":
                continue
            if rule.pattern.search(line):
                policy_context = f"{previous_line} {line}".strip()
                if rule.check_id != "secret_private_key" and _is_policy_negation(policy_context):
                    continue
                findings.append(
                    GuardrailFinding(
                        check_id=rule.check_id,
                        category=rule.category,
                        severity=rule.severity,
                        message=rule.message,
                        file=file,
                        line=line_number,
                        evidence=redact_evidence(line),
                        operator_gate_required=rule.operator_gate_required,
                    )
                )
        previous_line = line
    return findings


def scan_command(command: str) -> list[GuardrailFinding]:
    return scan_text(command, file="<command>", scan_type="command")


def scan_paths(root: Path, targets: Sequence[str], scan_type: str = "all") -> list[GuardrailFinding]:
    root = root.resolve()
    findings: list[GuardrailFinding] = []
    for path in sorted(set(iter_text_files(root, targets))):
        try:
            if path.stat().st_size > MAX_TEXT_BYTES:
                continue
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            file_label = str(path.resolve().relative_to(root))
        except ValueError:
            file_label = str(path)
        findings.extend(scan_text(text, file=file_label, scan_type=scan_type))
    findings.sort(key=lambda item: (item.file, item.line, item.check_id))
    return findings


def highest_severity(findings: Sequence[GuardrailFinding]) -> str:
    order = {"none": 0, "low": 1, "medium": 2, "high": 3, "block": 4}
    severity = "none"
    for finding in findings:
        if order.get(finding.severity, 0) > order[severity]:
            severity = finding.severity
    return severity


def render_findings_markdown(title: str, findings: Sequence[GuardrailFinding]) -> str:
    lines = [
        f"# {title}",
        "",
        f"Findings: {len(findings)}",
        f"Highest severity: `{highest_severity(findings)}`",
        "",
        "| File | Line | Check | Severity | Gate | Evidence |",
        "| --- | ---: | --- | --- | ---: | --- |",
    ]
    for finding in findings:
        lines.append(
            f"| `{finding.file}` | {finding.line} | `{finding.check_id}` | "
            f"`{finding.severity}` | {str(finding.operator_gate_required).lower()} | "
            f"{finding.evidence} |"
        )
    return "\n".join(lines) + "\n"
