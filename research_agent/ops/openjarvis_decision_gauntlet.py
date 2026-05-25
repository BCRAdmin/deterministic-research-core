"""OpenJarvis decision gauntlet.

The gauntlet is the decision layer above the capability lab and arena. It turns
the question "Should we use Jarvis?" into a complete, repeatable test matrix.
Local checks run deterministically. Runtime, GitHub, network and write tests are
kept as explicit Operator-Gates until a separate approval exists.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from research_agent.ops.openjarvis_capability_arena import build_capability_arena
from research_agent.ops.openjarvis_capability_lab import (
    DEFAULT_POLICY_PATH,
    build_capability_lab,
    load_json,
    utc_now,
    write_json,
    write_text,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PLAN_PATH = REPO_ROOT / "configs/openjarvis/openjarvis_decision_gauntlet_plan.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs/openjarvis_capability_lab/decision_gauntlet"

PASS = "PASS"
FAIL = "FAIL"
OPERATOR_GATE = "OPERATOR_GATE"


def resolve_path(payload: Any, dotted_path: str) -> Any:
    current = payload
    for part in dotted_path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        return None
    return current


def coerce_file(path: str) -> Path:
    raw = Path(path).expanduser()
    if raw.is_absolute():
        return raw
    return (REPO_ROOT / raw).resolve()


def validate_plan(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1:
        errors.append("schema_version_must_be_1")
    if not plan.get("gauntlet_id"):
        errors.append("gauntlet_id_missing")
    workstreams = plan.get("workstreams", [])
    if len(workstreams) < 10:
        errors.append("at_least_10_workstreams_required")
    seen_tests: set[str] = set()
    test_count = 0
    for workstream in workstreams:
        if not workstream.get("id"):
            errors.append("workstream_missing_id")
        tests = workstream.get("tests", [])
        if not tests:
            errors.append(f"{workstream.get('id', 'unknown')}:tests_missing")
        for test in tests:
            test_count += 1
            test_id = str(test.get("id", ""))
            if not test_id:
                errors.append(f"{workstream.get('id', 'unknown')}:test_missing_id")
            elif test_id in seen_tests:
                errors.append(f"duplicate_test_id:{test_id}")
            seen_tests.add(test_id)
            for required in ("title", "artifact", "assert"):
                if required not in test:
                    errors.append(f"{test_id or 'unknown'}:missing_{required}")
    if test_count < 60:
        errors.append("at_least_60_tests_required_for_decision_gauntlet")
    return errors


def evaluate_assertion(test: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    artifact = str(test.get("artifact", ""))
    assertion = str(test.get("assert", ""))

    if artifact == "operator_gate" or assertion == "operator_gate":
        return {
            "status": OPERATOR_GATE,
            "actual": "not_executed",
            "detail": f"Blocked until explicit Operator-Go: {test.get('operator_gate', test.get('id'))}",
            "runtime_action_executed": False,
        }

    if artifact == "file":
        path = coerce_file(str(test.get("file", "")))
        if assertion == "exists":
            exists = path.exists()
            return {
                "status": PASS if exists else FAIL,
                "actual": exists,
                "detail": str(path),
            }
        if assertion == "contains_text":
            exists = path.exists()
            text = path.read_text(encoding="utf-8", errors="replace") if exists else ""
            expected = str(test.get("expected", ""))
            found = expected in text
            return {
                "status": PASS if found else FAIL,
                "actual": found,
                "detail": str(path),
            }

    if artifact == "json_file":
        path = coerce_file(str(test.get("file", "")))
        if not path.exists():
            return {"status": FAIL, "actual": "missing_file", "detail": str(path)}
        payload = json.loads(path.read_text(encoding="utf-8"))
        actual = resolve_path(payload, str(test.get("path", "")))
    else:
        payload = context.get(artifact, {})
        actual = resolve_path(payload, str(test.get("path", ""))) if test.get("path") else payload

    if assertion == "equals":
        expected = test.get("expected")
        return {
            "status": PASS if actual == expected else FAIL,
            "actual": actual,
            "expected": expected,
        }
    if assertion == "min":
        minimum = test.get("minimum", 0)
        valid = isinstance(actual, (int, float)) and actual >= minimum
        return {
            "status": PASS if valid else FAIL,
            "actual": actual,
            "minimum": minimum,
        }
    if assertion == "contains":
        expected = test.get("expected")
        valid = expected in actual if isinstance(actual, (list, tuple, set, str)) else False
        return {
            "status": PASS if valid else FAIL,
            "actual": actual,
            "expected": expected,
        }
    if assertion == "not_empty":
        valid = bool(actual)
        return {
            "status": PASS if valid else FAIL,
            "actual": actual,
        }

    return {
        "status": FAIL,
        "actual": "unsupported_assertion",
        "detail": f"Unsupported assertion for test {test.get('id')}: {artifact}.{assertion}",
    }


def evaluate_workstreams(plan: dict[str, Any], context: dict[str, Any]) -> list[dict[str, Any]]:
    evaluated: list[dict[str, Any]] = []
    for workstream in plan.get("workstreams", []):
        test_results = []
        for test in workstream.get("tests", []):
            result = evaluate_assertion(test, context)
            test_results.append(
                {
                    **test,
                    **result,
                }
            )
        statuses = [item["status"] for item in test_results]
        local_failures = statuses.count(FAIL)
        evaluated.append(
            {
                "id": workstream.get("id"),
                "title": workstream.get("title"),
                "goal": workstream.get("goal"),
                "required_outcome": workstream.get("required_outcome"),
                "status": FAIL if local_failures else PASS,
                "pass_count": statuses.count(PASS),
                "fail_count": local_failures,
                "operator_gate_count": statuses.count(OPERATOR_GATE),
                "test_count": len(test_results),
                "tests": test_results,
            }
        )
    return evaluated


def summarize_workstreams(workstreams: list[dict[str, Any]]) -> dict[str, Any]:
    tests = [test for workstream in workstreams for test in workstream.get("tests", [])]
    return {
        "workstream_count": len(workstreams),
        "test_count": len(tests),
        "pass_count": sum(1 for test in tests if test.get("status") == PASS),
        "fail_count": sum(1 for test in tests if test.get("status") == FAIL),
        "operator_gate_count": sum(1 for test in tests if test.get("status") == OPERATOR_GATE),
        "local_executable_count": sum(1 for test in tests if test.get("status") != OPERATOR_GATE),
    }


def decision_status(summary: dict[str, Any], arena: dict[str, Any], lab: dict[str, Any]) -> str:
    if summary["fail_count"]:
        return "fix_local_gauntlet_before_decision"
    if lab.get("status") != PASS or arena.get("status") != PASS:
        return "fix_lab_or_arena_before_decision"
    if summary["operator_gate_count"]:
        return "ready_for_operator_gated_runtime_github_write_trials"
    return "ready_for_final_adoption_decision"


def adoption_recommendation(status: str) -> str:
    if status == "fix_local_gauntlet_before_decision":
        return "fix_failed_local_tests_before_any_jarvis_runtime_trial"
    if status == "fix_lab_or_arena_before_decision":
        return "fix_shadow_lab_and_arena_before_any_runtime_or_connector_trial"
    if status == "ready_for_operator_gated_runtime_github_write_trials":
        return "do_not_rebuild_system; run_only_the_gated_runtime_github_write_trials_needed_for_final_decision"
    return "decide_between_shadow_only_component_adoption_or_rejection"


def build_decision_gauntlet(
    policy_path: Path = DEFAULT_POLICY_PATH,
    plan_path: Path = DEFAULT_PLAN_PATH,
) -> dict[str, Any]:
    plan = load_json(plan_path)
    policy = load_json(policy_path)
    lab = build_capability_lab(policy_path)
    arena = build_capability_arena(policy_path)
    plan_errors = validate_plan(plan)
    workstreams = evaluate_workstreams(
        plan,
        {
            "plan": plan,
            "policy": policy,
            "lab": lab,
            "arena": arena,
        },
    )
    summary = summarize_workstreams(workstreams)
    if plan_errors:
        summary["fail_count"] += len(plan_errors)
    status = decision_status(summary, arena, lab)
    local_status = PASS if not summary["fail_count"] and not plan_errors else FAIL
    return {
        "schema_version": 1,
        "generated_at": utc_now(),
        "gauntlet_id": plan.get("gauntlet_id"),
        "title": plan.get("title"),
        "status": local_status,
        "decision_status": status,
        "adoption_recommendation": adoption_recommendation(status),
        "mode": policy.get("mode"),
        "source_of_truth": False,
        "runtime_action_executed": False,
        "runtime_execution_attempted": False,
        "plan_path": str(plan_path),
        "policy_path": str(policy_path),
        "plan_errors": plan_errors,
        "summary": summary,
        "minimum_local_requirements": plan.get("minimum_local_requirements", {}),
        "final_decision_options": plan.get("final_decision_options", []),
        "lab_summary": {
            "status": lab.get("status"),
            "source_documents": lab.get("source_document_count", 0),
            "retrieval_status": lab.get("retrieval_benchmark", {}).get("status"),
            "retrieval_pass_count": lab.get("retrieval_benchmark", {}).get("pass_count", 0),
            "code_qa_status": lab.get("code_qa_shadow", {}).get("status"),
            "runtime_available": lab.get("runtime", {}).get("runtime_available", False),
            "runtime_action_executed": lab.get("hardening", {}).get("runtime_action_executed", False),
        },
        "arena_summary": {
            "status": arena.get("status"),
            "task_count": arena.get("evaluated_task_count", 0),
            "source_documents": arena.get("source_document_count", 0),
            "shadow_average": arena.get("engine_summary", {}).get("openjarvis_shadow", {}).get("average_score", 0),
            "baseline_average": arena.get("engine_summary", {}).get("pig_obsidian_baseline", {}).get("average_score", 0),
            "shadow_pass_count": arena.get("engine_summary", {}).get("openjarvis_shadow", {}).get("pass_count", 0),
            "shadow_fail_count": arena.get("engine_summary", {}).get("openjarvis_shadow", {}).get("fail_count", 0),
            "shadow_wins": arena.get("winner_summary", {}).get("openjarvis_shadow", 0),
            "baseline_wins": arena.get("winner_summary", {}).get("pig_obsidian_baseline", 0),
            "ties": arena.get("winner_summary", {}).get("tie", 0),
            "runtime_action_executed": arena.get("runtime", {}).get("runtime_action_executed", False),
        },
        "workstreams": workstreams,
        "non_actions": [
            "no_openjarvis_runtime_execution",
            "no_openjarvis_shell",
            "no_openjarvis_writes",
            "no_openjarvis_network",
            "no_github_api",
            "no_pat_or_oauth",
            "no_commit_push_release",
        ],
        "next_safe_step": (
            "Use this gauntlet as the final decision checklist. Run no Jarvis runtime, "
            "GitHub or write-sandbox trial until the specific Operator-Gate is approved."
        ),
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    arena = report.get("arena_summary", {})
    lab = report.get("lab_summary", {})
    lines = [
        "# OpenJarvis Decision Gauntlet",
        "",
        f"- Status: `{report.get('status')}`",
        f"- Decision Status: `{report.get('decision_status')}`",
        f"- Empfehlung: `{report.get('adoption_recommendation')}`",
        f"- Workstreams: `{summary.get('workstream_count', 0)}`",
        f"- Tests: `{summary.get('test_count', 0)}`",
        f"- Lokal PASS: `{summary.get('pass_count', 0)}`",
        f"- Lokal FAIL: `{summary.get('fail_count', 0)}`",
        f"- Operator-Gates: `{summary.get('operator_gate_count', 0)}`",
        f"- Runtime-Aktion: `{report.get('runtime_action_executed')}`",
        "",
        "## Lab / Arena",
        "",
        f"- Lab: `{lab.get('status')}`, Retrieval `{lab.get('retrieval_pass_count')}`, Code-QA `{lab.get('code_qa_status')}`, Runtime-Aktion `{lab.get('runtime_action_executed')}`",
        f"- Arena: `{arena.get('status')}`, Aufgaben `{arena.get('task_count')}`, Shadow Wins `{arena.get('shadow_wins')}`, Baseline Wins `{arena.get('baseline_wins')}`, Shadow FAIL `{arena.get('shadow_fail_count')}`",
        "",
        "## Entscheidung",
        "",
        "Aktuell ist das System bereit für die operator-gated Runtime-, GitHub- und Write-Sandbox-Trials. "
        "Das ist bewusst noch keine finale Jarvis-Adoption.",
        "",
        "## Workstreams",
        "",
    ]
    for workstream in report.get("workstreams", []):
        lines.extend(
            [
                f"### {workstream.get('title')}",
                "",
                f"- Status: `{workstream.get('status')}`",
                f"- Ziel: {workstream.get('goal')}",
                f"- Outcome: {workstream.get('required_outcome')}",
                f"- Tests: `{workstream.get('test_count')}`, PASS `{workstream.get('pass_count')}`, FAIL `{workstream.get('fail_count')}`, Gates `{workstream.get('operator_gate_count')}`",
                "",
            ]
        )
        for test in workstream.get("tests", []):
            lines.append(
                f"- `{test.get('status')}` `{test.get('id')}`: {test.get('title')}"
            )
        lines.append("")
    lines.extend(["## Nicht-Aktionen", ""])
    for item in report.get("non_actions", []):
        lines.append(f"- `{item}`")
    return "\n".join(lines) + "\n"


def write_decision_gauntlet(report: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        **report,
        "path": str((output_dir / "OPENJARVIS_DECISION_GAUNTLET.json").resolve()),
    }
    write_json(output_dir / "OPENJARVIS_DECISION_GAUNTLET.json", report)
    write_text(output_dir / "OPENJARVIS_DECISION_GAUNTLET.md", render_markdown(report))
    matrix = [
        {
            "workstream_id": workstream.get("id"),
            "workstream_title": workstream.get("title"),
            **test,
        }
        for workstream in report.get("workstreams", [])
        for test in workstream.get("tests", [])
    ]
    write_json(output_dir / "OPENJARVIS_DECISION_TEST_MATRIX.json", {"tests": matrix})
    work_items = [
        "# OpenJarvis Decision Work Items",
        "",
        "Diese Liste ist die komplette Arbeitsliste für die finale Jarvis-Entscheidung.",
        "",
    ]
    for workstream in report.get("workstreams", []):
        work_items.extend(
            [
                f"## {workstream.get('title')}",
                "",
                f"- Status: `{workstream.get('status')}`",
                f"- Ziel: {workstream.get('goal')}",
                f"- Outcome: {workstream.get('required_outcome')}",
                "",
            ]
        )
        for test in workstream.get("tests", []):
            work_items.append(f"- `{test.get('status')}` `{test.get('id')}`: {test.get('title')}")
        work_items.append("")
    write_text(output_dir / "OPENJARVIS_DECISION_WORK_ITEMS.md", "\n".join(work_items))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the OpenJarvis decision gauntlet.")
    parser.add_argument("--policy", default=str(DEFAULT_POLICY_PATH), help="Policy JSON path.")
    parser.add_argument("--plan", default=str(DEFAULT_PLAN_PATH), help="Decision gauntlet plan JSON path.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory.")
    parser.add_argument("--json", action="store_true", help="Print JSON report.")
    args = parser.parse_args(argv)
    report = build_decision_gauntlet(
        Path(args.policy).expanduser().resolve(),
        Path(args.plan).expanduser().resolve(),
    )
    report = write_decision_gauntlet(report, Path(args.output_dir).expanduser().resolve())
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(f"{report['status']} {report['decision_status']} {report['path']}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
