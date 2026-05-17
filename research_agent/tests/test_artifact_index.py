from research_agent.batch.artifact_index import build_artifact_index


def test_artifact_index_finds_expected_files(tmp_path):
    (tmp_path / "final_report.md").write_text("ok", encoding="utf-8")
    (tmp_path / "quality_score.json").write_text("{}", encoding="utf-8")

    artifacts = build_artifact_index(tmp_path)

    assert "final_report.md" in artifacts
    assert "quality_score.json" in artifacts
    assert artifacts["final_report.md"].endswith("final_report.md")
