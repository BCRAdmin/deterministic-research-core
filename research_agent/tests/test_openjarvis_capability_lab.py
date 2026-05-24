from pathlib import Path

from research_agent.ops.openjarvis_capability_lab import (
    build_capability_lab,
    collect_documents,
    load_json,
    render_markdown,
    scan_secret_text,
    validate_policy,
    write_report,
)


def minimal_policy(tmp_path: Path) -> dict:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "OPENJARVIS.md").write_text(
        "shadow_read_only source_of_truth Operator-Go Secret Planning Quality PIG Operator Surface",
        encoding="utf-8",
    )
    (tmp_path / "package.json").write_text(
        '{"scripts":{"verify":"echo ok","build":"echo ok"}}',
        encoding="utf-8",
    )
    return {
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
                "id": "tmp",
                "root": str(tmp_path),
                "include_paths": ["docs"],
            }
        ],
        "benchmark_questions": [
            {
                "id": "policy",
                "question": "OpenJarvis policy",
                "must_terms": ["shadow_read_only", "source_of_truth", "Operator-Go", "Secret"],
                "expected_source_patterns": ["OPENJARVIS"],
            }
        ],
        "qa_shadow_projects": [
            {
                "id": "tmp_project",
                "root": str(tmp_path),
                "expected_script_keywords": ["verify", "build"],
            }
        ],
    }


def test_policy_blocks_mutating_permissions(tmp_path: Path) -> None:
    policy = minimal_policy(tmp_path)
    policy["runtime_permissions"]["allow_write"] = True

    errors = validate_policy(policy)

    assert "runtime_permission_must_be_false:allow_write" in errors


def test_secret_scan_redacts_findings() -> None:
    findings = scan_secret_text("OPENAI_API_KEY=" + "sk-" + "abc123456789012345678901")

    assert findings
    assert findings[0]["redacted"] is True
    assert "sk-" not in str(findings[0])


def test_collect_documents_blocks_secret_files(tmp_path: Path) -> None:
    policy = minimal_policy(tmp_path)
    (tmp_path / "docs" / "secret.md").write_text(
        "TOKEN=" + "abcdefghijklmnopqrstuvwxyz",
        encoding="utf-8",
    )

    docs, findings = collect_documents(policy)

    assert docs
    assert any(finding["code"] == "secret_like_content_detected" for finding in findings)


def test_capability_lab_passes_in_shadow_mode(tmp_path: Path) -> None:
    policy = minimal_policy(tmp_path)
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(__import__("json").dumps(policy), encoding="utf-8")

    report = build_capability_lab(policy_path)
    markdown = render_markdown(report)

    assert report["status"] == "PASS"
    assert report["source_of_truth"] is False
    assert report["hardening"]["runtime_action_executed"] is False
    assert report["runtime"]["runtime_execution_attempted"] is False
    assert "OpenJarvis Capability Lab" in markdown


def test_default_policy_file_is_json_parseable() -> None:
    policy = load_json(Path("configs/openjarvis/openjarvis_policy.json"))

    assert policy["mode"] == "shadow_read_only"
    assert policy["source_of_truth"] is False


def test_written_report_contains_evidence_path(tmp_path: Path) -> None:
    report = build_capability_lab(Path("configs/openjarvis/openjarvis_policy.json"))
    out = tmp_path / "lab"

    write_report(report, out)
    written = load_json(out / "OPENJARVIS_CAPABILITY_LAB.json")

    assert written["path"] == str((out / "OPENJARVIS_CAPABILITY_LAB.json").resolve())
    assert "Evidence-Pfad" in (out / "OPENJARVIS_CAPABILITY_LAB.md").read_text(encoding="utf-8")
