"""Deterministic OpenJarvis capability arena.

The arena compares the current PIG/Obsidian baseline against the broader
OpenJarvis shadow index. It does not execute OpenJarvis, shell commands, network
calls, GitHub API calls or file writes outside the local evidence reports.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from research_agent.ops.openjarvis_capability_lab import (
    DEFAULT_POLICY_PATH,
    SourceDocument,
    collect_documents,
    load_json,
    normalize_text,
    retrieve_documents,
    utc_now,
    validate_policy,
    write_json,
    write_text,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TASKS_PATH = REPO_ROOT / "configs/openjarvis/openjarvis_capability_arena_tasks.jsonl"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs/openjarvis_capability_lab/capability_arena"

BASELINE_SOURCE_SET_IDS = {"vega_backbone", "pig_surface"}
SHADOW_ENGINE_ID = "openjarvis_shadow"
BASELINE_ENGINE_ID = "pig_obsidian_baseline"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSONL row: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_no}: task row must be an object")
        rows.append(row)
    return rows


def validate_tasks(tasks: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    for index, task in enumerate(tasks, start=1):
        task_id = str(task.get("task_id", ""))
        if not task_id:
            errors.append(f"task_{index}_missing_task_id")
        elif task_id in seen_ids:
            errors.append(f"duplicate_task_id:{task_id}")
        seen_ids.add(task_id)
        if not task.get("question"):
            errors.append(f"{task_id or index}_missing_question")
        if not task.get("expected_source_patterns"):
            errors.append(f"{task_id or index}_missing_expected_source_patterns")
        if not task.get("expected_terms"):
            errors.append(f"{task_id or index}_missing_expected_terms")
    if len(tasks) < 30:
        errors.append("arena_requires_at_least_30_tasks")
    return errors


def task_query(task: dict[str, Any]) -> str:
    hints = " ".join(str(item) for item in task.get("retrieval_hints", []))
    return f"{task.get('question', '')} {hints}".strip()


def score_presence(expected: list[str], haystack: str) -> tuple[int, list[str]]:
    if not expected:
        return 100, []
    missing = [item for item in expected if normalize_text(str(item)) not in haystack]
    score = int(round(((len(expected) - len(missing)) / len(expected)) * 100))
    return score, missing


def path_haystack(hits: list[dict[str, Any]]) -> str:
    return normalize_text(
        " ".join(
            " ".join(
                [
                    str(hit.get("source_set_id", "")),
                    str(hit.get("relative_path", "")),
                    str(hit.get("path", "")),
                ]
            )
            for hit in hits
        )
    )


def text_haystack(documents: list[SourceDocument], hits: list[dict[str, Any]]) -> str:
    hit_paths = {str(hit.get("path", "")) for hit in hits}
    return normalize_text(" ".join(doc.text for doc in documents if doc.path in hit_paths))


def evaluate_engine(
    task: dict[str, Any],
    documents: list[SourceDocument],
    *,
    engine_id: str,
) -> dict[str, Any]:
    limit = int(task.get("top_k", 8))
    hits = retrieve_documents(documents, task_query(task), limit=limit)
    paths = path_haystack(hits)
    text = text_haystack(documents, hits)
    source_score, missing_sources = score_presence(
        [str(item) for item in task.get("expected_source_patterns", [])],
        paths,
    )
    term_score, missing_terms = score_presence(
        [str(item) for item in task.get("expected_terms", [])],
        text,
    )
    gate_score, missing_gate_terms = score_presence(
        [str(item) for item in task.get("expected_gate_terms", [])],
        text,
    )
    forbidden_hits = [
        str(item)
        for item in task.get("forbidden_terms", [])
        if normalize_text(str(item)) in text
    ]
    stale_safety_score = 100 if not forbidden_hits else 0
    evidence_depth_score = min(100, len(hits) * 12)
    total_score = round(
        (source_score * 0.35)
        + (term_score * 0.25)
        + (gate_score * 0.20)
        + (stale_safety_score * 0.15)
        + (evidence_depth_score * 0.05),
        2,
    )
    if forbidden_hits:
        status = "FAIL"
    elif total_score >= 80:
        status = "PASS"
    elif total_score >= 55:
        status = "WARN"
    else:
        status = "FAIL"
    return {
        "engine_id": engine_id,
        "status": status,
        "total_score": total_score,
        "source_precision_score": source_score,
        "truth_alignment_score": term_score,
        "gate_awareness_score": gate_score,
        "stale_safety_score": stale_safety_score,
        "evidence_depth_score": evidence_depth_score,
        "missing_source_patterns": missing_sources,
        "missing_terms": missing_terms,
        "missing_gate_terms": missing_gate_terms,
        "forbidden_hits": forbidden_hits,
        "top_sources": hits,
    }


def winner_for(result: dict[str, Any]) -> str:
    baseline = result["engines"][BASELINE_ENGINE_ID]["total_score"]
    shadow = result["engines"][SHADOW_ENGINE_ID]["total_score"]
    if abs(shadow - baseline) < 3:
        return "tie"
    return SHADOW_ENGINE_ID if shadow > baseline else BASELINE_ENGINE_ID


def summarize_engine(results: list[dict[str, Any]], engine_id: str) -> dict[str, Any]:
    scores = [item["engines"][engine_id]["total_score"] for item in results]
    statuses = [item["engines"][engine_id]["status"] for item in results]
    return {
        "engine_id": engine_id,
        "average_score": round(sum(scores) / len(scores), 2) if scores else 0,
        "pass_count": statuses.count("PASS"),
        "warn_count": statuses.count("WARN"),
        "fail_count": statuses.count("FAIL"),
        "win_count": sum(1 for item in results if item.get("winner") == engine_id),
        "loss_count": sum(
            1
            for item in results
            if item.get("winner") not in {engine_id, "tie"}
        ),
        "tie_count": sum(1 for item in results if item.get("winner") == "tie"),
    }


def summarize_categories(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    categories = sorted({str(item.get("category", "uncategorized")) for item in results})
    summary: list[dict[str, Any]] = []
    for category in categories:
        scoped = [item for item in results if item.get("category", "uncategorized") == category]
        shadow_scores = [item["engines"][SHADOW_ENGINE_ID]["total_score"] for item in scoped]
        baseline_scores = [item["engines"][BASELINE_ENGINE_ID]["total_score"] for item in scoped]
        summary.append(
            {
                "category": category,
                "task_count": len(scoped),
                "shadow_average": round(sum(shadow_scores) / len(shadow_scores), 2) if shadow_scores else 0,
                "baseline_average": round(sum(baseline_scores) / len(baseline_scores), 2) if baseline_scores else 0,
                "shadow_wins": sum(1 for item in scoped if item.get("winner") == SHADOW_ENGINE_ID),
                "baseline_wins": sum(1 for item in scoped if item.get("winner") == BASELINE_ENGINE_ID),
                "ties": sum(1 for item in scoped if item.get("winner") == "tie"),
            }
        )
    return summary


def build_capability_arena(
    policy_path: Path = DEFAULT_POLICY_PATH,
    tasks_path: Path = DEFAULT_TASKS_PATH,
) -> dict[str, Any]:
    policy = load_json(policy_path)
    tasks = load_jsonl(tasks_path)
    policy_errors = validate_policy(policy)
    task_errors = validate_tasks(tasks)
    documents, preflight_findings = collect_documents(policy)
    blockers = [item for item in preflight_findings if item.get("severity") == "blocker"]
    baseline_documents = [doc for doc in documents if doc.source_set_id in BASELINE_SOURCE_SET_IDS]
    shadow_documents = documents
    results: list[dict[str, Any]] = []
    if not policy_errors and not task_errors and not blockers:
        for task in tasks:
            result = {
                "task_id": task.get("task_id"),
                "category": task.get("category", "uncategorized"),
                "question": task.get("question"),
                "operator_gate_relevant": bool(task.get("expected_gate_terms")),
                "engines": {
                    BASELINE_ENGINE_ID: evaluate_engine(
                        task,
                        baseline_documents,
                        engine_id=BASELINE_ENGINE_ID,
                    ),
                    SHADOW_ENGINE_ID: evaluate_engine(
                        task,
                        shadow_documents,
                        engine_id=SHADOW_ENGINE_ID,
                    ),
                },
            }
            result["winner"] = winner_for(result)
            result["score_delta_shadow_minus_baseline"] = round(
                result["engines"][SHADOW_ENGINE_ID]["total_score"]
                - result["engines"][BASELINE_ENGINE_ID]["total_score"],
                2,
            )
            results.append(result)
    engine_summary = {
        BASELINE_ENGINE_ID: summarize_engine(results, BASELINE_ENGINE_ID) if results else {},
        SHADOW_ENGINE_ID: summarize_engine(results, SHADOW_ENGINE_ID) if results else {},
    }
    shadow_wins = engine_summary.get(SHADOW_ENGINE_ID, {}).get("win_count", 0)
    baseline_wins = engine_summary.get(BASELINE_ENGINE_ID, {}).get("win_count", 0)
    ties = engine_summary.get(SHADOW_ENGINE_ID, {}).get("tie_count", 0)
    recommendation = "keep_shadow_mode_no_runtime_adoption"
    if shadow_wins > baseline_wins:
        recommendation = "promote_shadow_retrieval_benchmark_to_next_read_only_trial"
    if any(item["engines"][SHADOW_ENGINE_ID]["status"] == "FAIL" for item in results):
        recommendation = "fix_shadow_retrieval_before_any_runtime_trial"
    status = "PASS"
    if policy_errors or task_errors or blockers:
        status = "FAIL"
    elif not results:
        status = "FAIL"
    return {
        "schema_version": 1,
        "generated_at": utc_now(),
        "status": status,
        "mode": policy.get("mode"),
        "source_of_truth": False,
        "task_count": len(tasks),
        "evaluated_task_count": len(results),
        "baseline_source_set_ids": sorted(BASELINE_SOURCE_SET_IDS),
        "shadow_source_set_ids": sorted({doc.source_set_id for doc in shadow_documents}),
        "source_document_count": len(documents),
        "baseline_document_count": len(baseline_documents),
        "shadow_document_count": len(shadow_documents),
        "policy_errors": policy_errors,
        "task_errors": task_errors,
        "preflight": {
            "status": "PASS" if not policy_errors and not task_errors and not blockers else "FAIL",
            "finding_count": len(preflight_findings),
            "blocker_count": len(blockers),
            "findings": preflight_findings[:200],
        },
        "runtime": {
            "runtime_execution_attempted": False,
            "runtime_action_executed": False,
            "runtime_execution_allowed": False,
        },
        "engine_summary": engine_summary,
        "category_summary": summarize_categories(results),
        "winner_summary": {
            SHADOW_ENGINE_ID: shadow_wins,
            BASELINE_ENGINE_ID: baseline_wins,
            "tie": ties,
        },
        "adoption_recommendation": recommendation,
        "next_safe_step": (
            "Keep OpenJarvis in shadow_read_only mode. Promote only the winning read-only "
            "capability slice into a narrower benchmark before any runtime execution."
        ),
        "non_actions": [
            "no_openjarvis_runtime_execution",
            "no_shell_exec",
            "no_file_write_by_openjarvis",
            "no_network",
            "no_github_api",
            "no_commit_push_release",
        ],
        "task_results": results,
    }


def render_markdown(report: dict[str, Any]) -> str:
    shadow = report.get("engine_summary", {}).get(SHADOW_ENGINE_ID, {})
    baseline = report.get("engine_summary", {}).get(BASELINE_ENGINE_ID, {})
    lines = [
        "# OpenJarvis Capability Arena",
        "",
        f"- Status: `{report.get('status')}`",
        f"- Modus: `{report.get('mode')}`",
        f"- Source of Truth: `{report.get('source_of_truth')}`",
        f"- Aufgaben: `{report.get('evaluated_task_count')}/{report.get('task_count')}`",
        f"- Sichere Quellen: `{report.get('source_document_count')}`",
        f"- Baseline-Dokumente: `{report.get('baseline_document_count')}`",
        f"- Shadow-Dokumente: `{report.get('shadow_document_count')}`",
        f"- Runtime-Aktion: `{report.get('runtime', {}).get('runtime_action_executed')}`",
        f"- Empfehlung: `{report.get('adoption_recommendation')}`",
        "",
        "## Scoreboard",
        "",
        f"- `{BASELINE_ENGINE_ID}`: Ø `{baseline.get('average_score', 0)}`, "
        f"PASS `{baseline.get('pass_count', 0)}`, WARN `{baseline.get('warn_count', 0)}`, "
        f"FAIL `{baseline.get('fail_count', 0)}`, Wins `{baseline.get('win_count', 0)}`",
        f"- `{SHADOW_ENGINE_ID}`: Ø `{shadow.get('average_score', 0)}`, "
        f"PASS `{shadow.get('pass_count', 0)}`, WARN `{shadow.get('warn_count', 0)}`, "
        f"FAIL `{shadow.get('fail_count', 0)}`, Wins `{shadow.get('win_count', 0)}`",
        "",
        "## Kategorien",
        "",
    ]
    for item in report.get("category_summary", []):
        lines.append(
            f"- `{item.get('category')}`: Shadow Ø `{item.get('shadow_average')}`, "
            f"Baseline Ø `{item.get('baseline_average')}`, "
            f"Shadow Wins `{item.get('shadow_wins')}`, Baseline Wins `{item.get('baseline_wins')}`, "
            f"Ties `{item.get('ties')}`"
        )
    lines.extend(["", "## Schwächste Shadow-Aufgaben", ""])
    weakest = sorted(
        report.get("task_results", []),
        key=lambda item: item.get("engines", {}).get(SHADOW_ENGINE_ID, {}).get("total_score", 0),
    )[:8]
    for item in weakest:
        engine = item.get("engines", {}).get(SHADOW_ENGINE_ID, {})
        lines.append(
            f"- `{item.get('task_id')}` `{engine.get('status')}` score `{engine.get('total_score')}`: "
            f"missing sources `{', '.join(engine.get('missing_source_patterns', [])) or 'none'}`, "
            f"missing terms `{', '.join(engine.get('missing_terms', [])) or 'none'}`"
        )
    lines.extend(["", "## Nicht-Aktionen", ""])
    for action in report.get("non_actions", []):
        lines.append(f"- `{action}`")
    return "\n".join(lines) + "\n"


def write_arena_report(report: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        **report,
        "path": str((output_dir / "CAPABILITY_ARENA_SCOREBOARD.json").resolve()),
    }
    write_json(output_dir / "CAPABILITY_ARENA_SCOREBOARD.json", report)
    write_text(output_dir / "CAPABILITY_ARENA_SCOREBOARD.md", render_markdown(report))
    write_json(output_dir / "CAPABILITY_ARENA_PREFLIGHT.json", report.get("preflight", {}))
    task_rows = "\n".join(
        json.dumps(item, sort_keys=True, ensure_ascii=False)
        for item in report.get("task_results", [])
    )
    write_text(output_dir / "CAPABILITY_ARENA_TASK_RESULTS.jsonl", task_rows + "\n")
    sources: list[str] = []
    for result in report.get("task_results", []):
        for engine in result.get("engines", {}).values():
            for source in engine.get("top_sources", []):
                path = str(source.get("path", ""))
                if path and path not in sources:
                    sources.append(path)
    write_text(output_dir / "CAPABILITY_ARENA_FILE_LIST.txt", "\n".join(sources) + "\n")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the OpenJarvis capability arena.")
    parser.add_argument("--policy", default=str(DEFAULT_POLICY_PATH), help="Policy JSON path.")
    parser.add_argument("--tasks", default=str(DEFAULT_TASKS_PATH), help="Arena task JSONL path.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory.")
    parser.add_argument("--json", action="store_true", help="Print JSON scoreboard.")
    args = parser.parse_args(argv)
    report = build_capability_arena(
        Path(args.policy).expanduser().resolve(),
        Path(args.tasks).expanduser().resolve(),
    )
    report = write_arena_report(report, Path(args.output_dir).expanduser().resolve())
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(f"{report['status']} {Path(args.output_dir).expanduser().resolve() / 'CAPABILITY_ARENA_SCOREBOARD.md'}")
    return 0 if report["status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
