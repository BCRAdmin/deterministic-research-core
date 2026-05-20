"""Local skill and playbook registry.

This is a safe replacement for copying a remote skill hub into runtime. It
discovers local skills/playbooks, classifies risk, and emits review artifacts.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from research_agent.ops.guardrails import GuardrailFinding, highest_severity, scan_text


DEFAULT_SKILL_TARGETS = (
    "docs/skills",
    "docs/automation",
    "docs/memory",
    "docs/media_ingest",
    "docs/documents",
    "docs/pdf",
    "docs/spreadsheets",
    "docs/writing",
    "scripts",
)


@dataclass(frozen=True)
class SkillRecord:
    skill_id: str
    title: str
    path: str
    source_type: str
    risk_class: str
    runtime_decision: str
    operator_gate_required: bool
    highest_guardrail_severity: str
    finding_count: int
    description: str
    triggers: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return cleaned or "untitled"


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ""


def _frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    meta: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" not in line or line.startswith(" "):
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta


def _title_from_text(path: Path, text: str) -> str:
    meta = _frontmatter(text)
    for key in ("title", "name"):
        if meta.get(key):
            return meta[key]
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem.replace("_", " ").replace("-", " ").title()


def _description_from_text(text: str) -> str:
    meta = _frontmatter(text)
    if meta.get("description"):
        return meta["description"]
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("---") and ":" not in stripped[:30]:
            return stripped[:240]
    return ""


def _triggers_from_text(text: str) -> tuple[str, ...]:
    triggers: list[str] = []
    trigger_section = False
    for line in text.splitlines():
        lower = line.lower()
        if "when to use" in lower or "trigger" in lower or "typische trigger" in lower:
            trigger_section = True
            continue
        if trigger_section and line.startswith("#"):
            break
        if trigger_section and line.strip().startswith(("-", "*")):
            triggers.append(line.strip().lstrip("-* ").strip()[:160])
        if len(triggers) >= 5:
            break
    return tuple(triggers)


def discover_candidate_files(root: Path, targets: Sequence[str] = DEFAULT_SKILL_TARGETS) -> list[Path]:
    candidates: list[Path] = []
    for target in targets:
        start = root / target
        if not start.exists():
            continue
        if start.is_file() and start.suffix.lower() in {".md", ".py", ".sh", ".json"}:
            candidates.append(start)
            continue
        if not start.is_dir():
            continue
        for path in start.rglob("*"):
            if "__pycache__" in path.parts:
                continue
            if path.name == "SKILL.md" or path.suffix.lower() in {".md", ".py", ".sh"}:
                candidates.append(path)
    return sorted(set(candidates))


def classify_risk(path: Path, text: str, findings: Sequence[GuardrailFinding]) -> tuple[str, str, bool]:
    categories = {finding.category for finding in findings}
    check_ids = {finding.check_id for finding in findings}
    suffix = path.suffix.lower()

    if "secret_print_guard" in categories:
        return ("R4_credentials_or_secret_risk", "hold_for_operator_review", True)
    if any(check in check_ids for check in ("skill_background_or_self_modify", "auto_runtime_mutation")):
        return ("R6_autonomous_or_background", "hold_for_operator_review", True)
    if "dangerous_command" in categories:
        return ("R5_destructive_or_host_control", "hold_for_operator_review", True)
    if "skill_package" in categories and any("network" in finding.check_id for finding in findings):
        return ("R3_network_or_install", "pattern_only_operator_gate", True)
    if suffix in {".py", ".sh", ".js", ".mjs", ".ts", ".tsx"}:
        if re.search(r"\b(write_text|open\([^)]*['\"]w|subprocess|os\.remove|unlink|rename)\b", text):
            return ("R2_local_write_or_exec_helper", "review_before_runtime_use", True)
        return ("R1_local_read_only_helper", "approved_local_review_helper", False)
    if findings:
        return ("R1_policy_relevant_doc", "approved_playbook_only", any(f.operator_gate_required for f in findings))
    return ("R0_doc_only_pattern", "approved_playbook_only", False)


def build_skill_registry(
    root: Path,
    targets: Sequence[str] = DEFAULT_SKILL_TARGETS,
) -> list[SkillRecord]:
    root = root.resolve()
    records: list[SkillRecord] = []
    for path in discover_candidate_files(root, targets):
        text = _read_text(path)
        if not text:
            continue
        rel = str(path.resolve().relative_to(root))
        scan_type = "skill" if path.name == "SKILL.md" or "skills" in path.parts else "all"
        findings = scan_text(text, file=rel, scan_type=scan_type)
        risk_class, decision, gate = classify_risk(path, text, findings)
        title = _title_from_text(path, text)
        digest = hashlib.sha1(rel.encode("utf-8")).hexdigest()[:8]
        source_type = "skill" if path.name == "SKILL.md" else "playbook_or_helper"
        records.append(
            SkillRecord(
                skill_id=f"{_slug(title)}-{digest}",
                title=title,
                path=rel,
                source_type=source_type,
                risk_class=risk_class,
                runtime_decision=decision,
                operator_gate_required=gate,
                highest_guardrail_severity=highest_severity(findings),
                finding_count=len(findings),
                description=_description_from_text(text),
                triggers=_triggers_from_text(text),
            )
        )
    return sorted(records, key=lambda item: (item.risk_class, item.path))


def render_registry_markdown(records: Sequence[SkillRecord]) -> str:
    counts: dict[str, int] = {}
    for record in records:
        counts[record.runtime_decision] = counts.get(record.runtime_decision, 0) + 1

    lines = [
        "# Local Agent Skill Registry",
        "",
        "This registry is a review surface, not a runtime installer.",
        "",
        f"Records: {len(records)}",
        "",
        "## Decision Counts",
        "",
    ]
    for decision, count in sorted(counts.items()):
        lines.append(f"- `{decision}`: {count}")
    lines.extend(
        [
            "",
            "## Registry",
            "",
            "| Skill ID | Title | Risk | Decision | Gate | Findings | Path |",
            "| --- | --- | --- | --- | ---: | ---: | --- |",
        ]
    )
    for record in records:
        lines.append(
            f"| `{record.skill_id}` | {record.title} | `{record.risk_class}` | "
            f"`{record.runtime_decision}` | {str(record.operator_gate_required).lower()} | "
            f"{record.finding_count} | `{record.path}` |"
        )
    return "\n".join(lines) + "\n"
