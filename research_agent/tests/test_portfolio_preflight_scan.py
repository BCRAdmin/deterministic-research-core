import subprocess
from pathlib import Path

from research_agent.ops.portfolio_preflight_scan import (
    render_markdown,
    scan_changed_paths,
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def test_preflight_flags_secret_without_printing_value(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    secret_value = "ghp_" + ("a" * 36)
    (tmp_path / "notes.md").write_text(f"GITHUB_TOKEN={secret_value}\n", encoding="utf-8")

    report = scan_changed_paths(tmp_path)
    markdown = render_markdown(report)

    assert report.ok is False
    assert any(finding.check_id == "github_token" for finding in report.findings)
    assert secret_value not in markdown


def test_preflight_marks_outputs_as_review_not_block(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    output = tmp_path / "outputs" / "run" / "REPORT.md"
    output.parent.mkdir(parents=True)
    output.write_text("local evidence\n", encoding="utf-8")

    report = scan_changed_paths(tmp_path)

    assert report.ok is True
    assert any(finding.check_id == "outputs_tree_changed" for finding in report.review_findings)


def test_preflight_blocks_build_artifacts(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    build_file = tmp_path / ".next" / "cache" / "artifact.bin"
    build_file.parent.mkdir(parents=True)
    build_file.write_text("generated\n", encoding="utf-8")

    report = scan_changed_paths(tmp_path)

    assert report.ok is False
    assert any(
        finding.check_id == "generated_runtime_or_build_path"
        for finding in report.blocking_findings
    )
