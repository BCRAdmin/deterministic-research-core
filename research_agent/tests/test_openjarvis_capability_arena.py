import json
from pathlib import Path

from research_agent.ops.openjarvis_capability_arena import (
    BASELINE_ENGINE_ID,
    SHADOW_ENGINE_ID,
    build_capability_arena,
    load_jsonl,
    validate_tasks,
    write_arena_report,
)
from research_agent.ops.openjarvis_capability_lab import load_json


def arena_policy(tmp_path: Path) -> tuple[Path, Path]:
    backbone = tmp_path / "backbone"
    backbone.mkdir()
    (backbone / "Latest Session Context.md").write_text(
        "PIG Operator Surface Operator-Go runtime_action_executed false baseline truth",
        encoding="utf-8",
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "OPENJARVIS_CAPABILITY_LAB.md").write_text(
        "OpenJarvis shadow_read_only source_of_truth false Operator-Go Secret Runtime",
        encoding="utf-8",
    )
    tasks_path = tmp_path / "tasks.jsonl"
    rows = []
    for index in range(30):
        rows.append(
            {
                "task_id": f"task_{index}",
                "category": "policy",
                "question": "How should OpenJarvis be used?",
                "retrieval_hints": ["OPENJARVIS_CAPABILITY_LAB", "shadow_read_only"],
                "expected_source_patterns": ["OPENJARVIS_CAPABILITY_LAB"],
                "expected_terms": ["shadow_read_only", "source_of_truth", "Operator-Go"],
                "expected_gate_terms": ["Operator-Go"],
                "forbidden_terms": ["source_of_truth true"],
            }
        )
    tasks_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "mode": "shadow_read_only",
                "source_of_truth": False,
                "kill_switch": {"openjarvis_enabled": True},
                "runtime_permissions": {
                    "allow_shell": False,
                    "allow_write": False,
                    "allow_network": False,
                    "allow_github_api": False,
                },
                "allowed_extensions": [".md", ".json"],
                "max_file_bytes": 10000,
                "deny_globs": ["**/.env", "**/.git/**"],
                "source_sets": [
                    {
                        "id": "vega_backbone",
                        "root": str(backbone),
                        "include_paths": ["Latest Session Context.md"],
                    },
                    {
                        "id": "agent_ops_openjarvis_docs",
                        "root": str(docs),
                        "include_paths": ["OPENJARVIS_CAPABILITY_LAB.md"],
                    },
                ],
                "benchmark_questions": [
                    {
                        "id": "policy",
                        "question": "OpenJarvis policy",
                        "must_terms": ["shadow_read_only"],
                        "expected_source_patterns": ["OPENJARVIS"],
                    }
                ],
                "qa_shadow_projects": [],
            }
        ),
        encoding="utf-8",
    )
    return policy_path, tasks_path


def test_default_arena_tasks_are_parseable() -> None:
    tasks = load_jsonl(Path("configs/openjarvis/openjarvis_capability_arena_tasks.jsonl"))

    assert len(tasks) == 30
    assert not validate_tasks(tasks)


def test_capability_arena_compares_baseline_and_shadow(tmp_path: Path) -> None:
    policy_path, tasks_path = arena_policy(tmp_path)

    report = build_capability_arena(policy_path, tasks_path)

    assert report["status"] == "PASS"
    assert report["source_of_truth"] is False
    assert report["runtime"]["runtime_action_executed"] is False
    assert report["evaluated_task_count"] == 30
    assert report["engine_summary"][SHADOW_ENGINE_ID]["win_count"] >= 1
    assert BASELINE_ENGINE_ID in report["engine_summary"]


def test_written_arena_report_contains_scoreboard_path(tmp_path: Path) -> None:
    policy_path, tasks_path = arena_policy(tmp_path)
    report = build_capability_arena(policy_path, tasks_path)
    out = tmp_path / "arena"

    written = write_arena_report(report, out)

    assert written["path"] == str((out / "CAPABILITY_ARENA_SCOREBOARD.json").resolve())
    assert load_json(out / "CAPABILITY_ARENA_SCOREBOARD.json")["status"] == "PASS"
    assert (out / "CAPABILITY_ARENA_TASK_RESULTS.jsonl").exists()
