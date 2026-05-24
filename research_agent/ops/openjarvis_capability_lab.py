"""Hardened OpenJarvis capability lab.

The lab is intentionally deterministic and read-only. It prepares a safe
evaluation surface for OpenJarvis-style capabilities without making OpenJarvis
the source of truth or granting mutating runtime permissions.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import importlib.util
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY_PATH = REPO_ROOT / "configs/openjarvis/openjarvis_policy.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs/openjarvis_capability_lab"

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("openai_style_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "secret_assignment",
        re.compile(
            r"(?i)\b(api[_-]?key|token|secret|password|cookie)\s*[:=]\s*['\"]?"
            r"[A-Za-z0-9_./+=-]{12,}"
        ),
    ),
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def normalize_text(value: str) -> str:
    value = value.lower()
    replacements = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9._:/#-]+", " ", value)).strip()


def tokenize(value: str) -> set[str]:
    return {token for token in normalize_text(value).split() if len(token) > 2}


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def match_glob(path: Path, root: Path, patterns: list[str]) -> str | None:
    try:
        rel = path.relative_to(root).as_posix()
    except ValueError:
        rel = path.as_posix()
    abs_posix = path.as_posix()
    name = path.name
    for pattern in patterns:
        if (
            fnmatch.fnmatch(rel, pattern)
            or fnmatch.fnmatch(abs_posix, pattern)
            or fnmatch.fnmatch(name, pattern)
        ):
            return pattern
    return None


@dataclass(frozen=True)
class SourceDocument:
    source_set_id: str
    root: str
    path: str
    relative_path: str
    size_bytes: int
    suffix: str
    text: str

    def to_index_record(self) -> dict[str, Any]:
        return {
            "source_set_id": self.source_set_id,
            "path": self.path,
            "relative_path": self.relative_path,
            "size_bytes": self.size_bytes,
            "suffix": self.suffix,
        }


def validate_policy(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if policy.get("mode") != "shadow_read_only":
        errors.append("policy_mode_must_be_shadow_read_only")
    if policy.get("source_of_truth") is not False:
        errors.append("policy_must_not_be_source_of_truth")
    runtime = policy.get("runtime_permissions", {})
    for field in ("allow_shell", "allow_write", "allow_network", "allow_github_api"):
        if runtime.get(field) is not False:
            errors.append(f"runtime_permission_must_be_false:{field}")
    if not policy.get("kill_switch", {}).get("openjarvis_enabled", False):
        errors.append("openjarvis_lab_disabled_by_kill_switch")
    if not policy.get("source_sets"):
        errors.append("source_sets_missing")
    if not policy.get("benchmark_questions"):
        errors.append("benchmark_questions_missing")
    return errors


def discover_openjarvis_runtime() -> dict[str, Any]:
    executable = shutil.which("jarvis") or shutil.which("openjarvis")
    specs = {
        "jarvis": importlib.util.find_spec("jarvis") is not None,
        "openjarvis": importlib.util.find_spec("openjarvis") is not None,
    }
    return {
        "cli_path": executable,
        "python_imports": specs,
        "runtime_available": bool(executable or any(specs.values())),
        "runtime_execution_attempted": False,
        "runtime_execution_allowed": False,
        "note": "Runtime is detected only. The lab does not execute OpenJarvis in shadow_read_only mode.",
    }


def iter_source_paths(source_set: dict[str, Any]) -> list[Path]:
    root = Path(source_set["root"]).expanduser().resolve()
    paths: list[Path] = []
    for include in source_set.get("include_paths", []):
        target = (root / include).resolve()
        if not target.exists():
            continue
        if target.is_file():
            paths.append(target)
        else:
            paths.extend(path for path in target.rglob("*") if path.is_file())
    return sorted(set(paths))


def scan_secret_text(text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for name, pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            findings.append(
                {
                    "pattern": name,
                    "line": line_no,
                    "redacted": True,
                }
            )
    return findings


def collect_documents(policy: dict[str, Any]) -> tuple[list[SourceDocument], list[dict[str, Any]]]:
    deny_globs = list(policy.get("deny_globs", []))
    allowed_extensions = set(policy.get("allowed_extensions", []))
    max_file_bytes = int(policy.get("max_file_bytes", 200_000))
    documents: list[SourceDocument] = []
    findings: list[dict[str, Any]] = []

    for source_set in policy.get("source_sets", []):
        source_id = source_set.get("id", "unknown")
        root = Path(source_set["root"]).expanduser().resolve()
        if not root.exists():
            findings.append(
                {
                    "severity": "warn",
                    "code": "source_root_missing",
                    "source_set_id": source_id,
                    "path": str(root),
                }
            )
            continue
        for path in iter_source_paths(source_set):
            if not is_relative_to(path, root):
                findings.append(
                    {
                        "severity": "blocker",
                        "code": "path_outside_source_root",
                        "source_set_id": source_id,
                        "path": str(path),
                    }
                )
                continue
            denied_by = match_glob(path, root, deny_globs)
            if denied_by:
                findings.append(
                    {
                        "severity": "info",
                        "code": "denied_by_policy",
                        "source_set_id": source_id,
                        "path": str(path),
                        "pattern": denied_by,
                    }
                )
                continue
            suffix = path.suffix.lower()
            if suffix not in allowed_extensions:
                findings.append(
                    {
                        "severity": "info",
                        "code": "extension_not_allowed",
                        "source_set_id": source_id,
                        "path": str(path),
                        "suffix": suffix,
                    }
                )
                continue
            size = path.stat().st_size
            if size > max_file_bytes:
                findings.append(
                    {
                        "severity": "warn",
                        "code": "file_too_large",
                        "source_set_id": source_id,
                        "path": str(path),
                        "size_bytes": size,
                        "max_file_bytes": max_file_bytes,
                    }
                )
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                findings.append(
                    {
                        "severity": "warn",
                        "code": "not_utf8_text",
                        "source_set_id": source_id,
                        "path": str(path),
                    }
                )
                continue
            secret_findings = scan_secret_text(text)
            if secret_findings:
                findings.append(
                    {
                        "severity": "blocker",
                        "code": "secret_like_content_detected",
                        "source_set_id": source_id,
                        "path": str(path),
                        "findings": secret_findings[:8],
                    }
                )
                continue
            documents.append(
                SourceDocument(
                    source_set_id=source_id,
                    root=str(root),
                    path=str(path),
                    relative_path=path.relative_to(root).as_posix(),
                    size_bytes=size,
                    suffix=suffix,
                    text=text,
                )
            )
    return documents, findings


def retrieve_documents(documents: list[SourceDocument], question: str, *, limit: int = 5) -> list[dict[str, Any]]:
    query_terms = tokenize(question)
    scored: list[tuple[float, SourceDocument]] = []
    for doc in documents:
        text_terms = tokenize(doc.relative_path + " " + doc.text)
        if not text_terms:
            continue
        overlap = query_terms & text_terms
        score = (len(overlap) * 3.0) + sum(1.0 for term in query_terms if term in normalize_text(doc.relative_path))
        if score > 0:
            scored.append((score, doc))
    scored.sort(key=lambda item: (-item[0], item[1].relative_path))
    return [
        {
            **doc.to_index_record(),
            "score": score,
            "snippet": normalize_text(doc.text)[:600],
        }
        for score, doc in scored[:limit]
    ]


def evaluate_question(documents: list[SourceDocument], question: dict[str, Any]) -> dict[str, Any]:
    hits = retrieve_documents(documents, question.get("question", ""), limit=int(question.get("top_k", 5)))
    hit_paths = {hit.get("path") for hit in hits}
    combined = " ".join(
        normalize_text(doc.text)
        for doc in documents
        if doc.path in hit_paths
    )
    combined_paths = " ".join(
        " ".join(
            [
                hit.get("source_set_id", ""),
                hit.get("relative_path", ""),
                hit.get("path", ""),
            ]
        )
        for hit in hits
    )
    missing_terms = [
        term
        for term in question.get("must_terms", [])
        if normalize_text(str(term)) not in combined
    ]
    missing_sources = [
        pattern
        for pattern in question.get("expected_source_patterns", [])
        if normalize_text(str(pattern)) not in normalize_text(combined_paths)
    ]
    status = "PASS" if hits and not missing_terms and not missing_sources else "WARN"
    return {
        "question_id": question.get("id", "unknown"),
        "question": question.get("question", ""),
        "status": status,
        "missing_terms": missing_terms,
        "missing_source_patterns": missing_sources,
        "top_sources": hits,
        "source_precision": 5 if not missing_sources else max(0, 5 - len(missing_sources)),
        "truth_alignment": 5 if not missing_terms else max(0, 5 - len(missing_terms)),
        "gate_awareness": 5 if any("gate" in normalize_text(str(term)) for term in question.get("must_terms", [])) and "gate" in combined else 3,
    }


def run_retrieval_benchmark(policy: dict[str, Any], documents: list[SourceDocument]) -> dict[str, Any]:
    questions = policy.get("benchmark_questions", [])
    results = [evaluate_question(documents, question) for question in questions]
    pass_count = sum(1 for item in results if item["status"] == "PASS")
    return {
        "status": "PASS" if results and pass_count == len(results) else "WARN",
        "question_count": len(results),
        "pass_count": pass_count,
        "warn_count": len(results) - pass_count,
        "results": results,
    }


def run_code_qa_shadow(policy: dict[str, Any]) -> dict[str, Any]:
    projects = []
    for project in policy.get("qa_shadow_projects", []):
        root = Path(project["root"]).expanduser().resolve()
        package_path = root / "package.json"
        pyproject_path = root / "pyproject.toml"
        scripts: dict[str, str] = {}
        if package_path.exists():
            try:
                scripts = load_json(package_path).get("scripts", {})
            except Exception:
                scripts = {}
        expected = project.get("expected_script_keywords", ["lint", "build", "test", "verify", "check"])
        matching = {
            name: command
            for name, command in scripts.items()
            if any(keyword in name or keyword in command for keyword in expected)
        }
        projects.append(
            {
                "project_id": project.get("id", root.name),
                "root": str(root),
                "package_json": str(package_path) if package_path.exists() else None,
                "pyproject_toml": str(pyproject_path) if pyproject_path.exists() else None,
                "matching_script_count": len(matching),
                "matching_scripts": matching,
                "status": "PASS" if matching or pyproject_path.exists() else "WARN",
                "mutations_attempted": False,
                "recommended_mode": "read_only_handoff_only",
            }
        )
    pass_count = sum(1 for item in projects if item["status"] == "PASS")
    return {
        "status": "PASS" if projects and pass_count == len(projects) else "WARN",
        "project_count": len(projects),
        "pass_count": pass_count,
        "projects": projects,
    }


def build_capability_lab(policy_path: Path = DEFAULT_POLICY_PATH) -> dict[str, Any]:
    policy = load_json(policy_path)
    policy_errors = validate_policy(policy)
    documents, preflight_findings = collect_documents(policy)
    blockers = [item for item in preflight_findings if item.get("severity") == "blocker"]
    retrieval = run_retrieval_benchmark(policy, documents) if not blockers else {
        "status": "FAIL",
        "question_count": len(policy.get("benchmark_questions", [])),
        "pass_count": 0,
        "warn_count": len(policy.get("benchmark_questions", [])),
        "results": [],
    }
    code_qa = run_code_qa_shadow(policy)
    runtime = discover_openjarvis_runtime()
    hardening = {
        "mode": policy.get("mode"),
        "source_of_truth": policy.get("source_of_truth"),
        "runtime_permissions": policy.get("runtime_permissions", {}),
        "deny_globs": policy.get("deny_globs", []),
        "secret_scan_enabled": True,
        "mutations_attempted": False,
        "runtime_action_executed": False,
        "operator_go_required_for_runtime_execution": True,
    }
    status = "PASS"
    if policy_errors or blockers:
        status = "FAIL"
    elif retrieval.get("status") != "PASS" or code_qa.get("status") != "PASS":
        status = "WARN"
    recommendation = (
        "fix_policy_or_preflight_before_any_runtime_use"
        if status == "FAIL"
        else "keep_shadow_mode_and_benchmark_retrieval_first"
    )
    if status == "PASS" and runtime["runtime_available"]:
        recommendation = "runtime_detected_but_keep_shadow_mode_until_operator_go"
    return {
        "schema_version": 1,
        "generated_at": utc_now(),
        "status": status,
        "mode": policy.get("mode"),
        "policy_path": str(policy_path),
        "policy_errors": policy_errors,
        "source_of_truth": False,
        "source_document_count": len(documents),
        "source_sets": [
            {
                "id": source_set.get("id"),
                "root": source_set.get("root"),
                "include_paths": source_set.get("include_paths", []),
            }
            for source_set in policy.get("source_sets", [])
        ],
        "preflight": {
            "status": "PASS" if not policy_errors and not blockers else "FAIL",
            "finding_count": len(preflight_findings),
            "blocker_count": len(blockers),
            "findings": preflight_findings[:200],
        },
        "runtime": runtime,
        "retrieval_benchmark": retrieval,
        "code_qa_shadow": code_qa,
        "hardening": hardening,
        "adoption_recommendation": recommendation,
        "next_safe_step": "Compare shadow retrieval answers against PIG/Obsidian before any OpenJarvis runtime execution.",
        "non_actions": [
            "no_openjarvis_runtime_execution",
            "no_shell_exec",
            "no_file_write_by_openjarvis",
            "no_github_api",
            "no_commit_push_release",
            "no_secret_indexing",
        ],
        "indexed_sources": [doc.to_index_record() for doc in documents],
    }


def render_markdown(report: dict[str, Any]) -> str:
    retrieval = report.get("retrieval_benchmark", {})
    code_qa = report.get("code_qa_shadow", {})
    lines = [
        "# OpenJarvis Capability Lab",
        "",
        f"- Status: `{report.get('status')}`",
        f"- Modus: `{report.get('mode')}`",
        f"- Source of Truth: `{report.get('source_of_truth')}`",
        f"- Dokumente im sicheren Index: `{report.get('source_document_count')}`",
        f"- Preflight: `{report.get('preflight', {}).get('status')}` ({report.get('preflight', {}).get('blocker_count', 0)} Blocker)",
        f"- Retrieval Benchmark: `{retrieval.get('status')}` ({retrieval.get('pass_count', 0)}/{retrieval.get('question_count', 0)} PASS)",
        f"- Code-QA Shadow: `{code_qa.get('status')}` ({code_qa.get('pass_count', 0)}/{code_qa.get('project_count', 0)} PASS)",
        f"- OpenJarvis Runtime erkannt: `{report.get('runtime', {}).get('runtime_available')}`",
        f"- Evidence-Pfad: `{report.get('path', 'not_written_yet')}`",
        f"- Empfehlung: `{report.get('adoption_recommendation')}`",
        "",
        "## Härtung",
        "",
        "- OpenJarvis ist nicht die Wahrheitsschicht.",
        "- Runtime-Ausführung bleibt aus.",
        "- Shell, Writes, Netzwerk und GitHub-API bleiben deaktiviert.",
        "- Secret-ähnliche Inhalte blockieren den Lauf vor dem Benchmark.",
        "- Jede Übernahme bleibt Operator-Go.",
        "",
        "## Benchmark-Fragen",
        "",
    ]
    for item in retrieval.get("results", []):
        sources = ", ".join(source.get("relative_path", "") for source in item.get("top_sources", [])[:3])
        lines.extend(
            [
                f"### {item.get('question_id')}",
                "",
                f"- Status: `{item.get('status')}`",
                f"- Fehlende Begriffe: `{', '.join(item.get('missing_terms', [])) or 'none'}`",
                f"- Fehlende Quellenmuster: `{', '.join(item.get('missing_source_patterns', [])) or 'none'}`",
                f"- Top-Quellen: `{sources or 'none'}`",
                "",
            ]
        )
    lines.extend(["## Code-QA Shadow", ""])
    for project in code_qa.get("projects", []):
        lines.append(
            f"- `{project.get('status')}` `{project.get('project_id')}`: "
            f"{project.get('matching_script_count')} passende Scripts, Mutationen `{project.get('mutations_attempted')}`"
        )
    lines.extend(["", "## Nicht-Aktionen", ""])
    for action in report.get("non_actions", []):
        lines.append(f"- `{action}`")
    return "\n".join(lines) + "\n"


def write_report(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        **report,
        "path": str((output_dir / "OPENJARVIS_CAPABILITY_LAB.json").resolve()),
    }
    write_json(output_dir / "OPENJARVIS_CAPABILITY_LAB.json", report)
    write_text(output_dir / "OPENJARVIS_CAPABILITY_LAB.md", render_markdown(report))
    write_json(output_dir / "OPENJARVIS_PREFLIGHT.json", report.get("preflight", {}))
    write_json(output_dir / "OPENJARVIS_BENCHMARK.json", report.get("retrieval_benchmark", {}))
    write_text(
        output_dir / "OPENJARVIS_FILE_LIST.txt",
        "\n".join(item.get("path", "") for item in report.get("indexed_sources", [])) + "\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the hardened OpenJarvis capability lab.")
    parser.add_argument("--policy", default=str(DEFAULT_POLICY_PATH), help="Policy JSON path.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory.")
    parser.add_argument("--json", action="store_true", help="Print JSON report.")
    args = parser.parse_args(argv)
    report = build_capability_lab(Path(args.policy).expanduser().resolve())
    write_report(report, Path(args.output_dir).expanduser().resolve())
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(f"{report['status']} {Path(args.output_dir).expanduser().resolve() / 'OPENJARVIS_CAPABILITY_LAB.md'}")
    return 0 if report["status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
