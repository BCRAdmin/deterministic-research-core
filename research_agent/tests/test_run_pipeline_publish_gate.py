from research_agent.run_pipeline import (
    _empty_publish_quality_payload,
    _remove_unapproved_publish_artifacts,
)


def test_unapproved_report_leaves_no_publish_artifact(tmp_path):
    publish_report = tmp_path / "publish_report.md"
    publish_quality = tmp_path / "publish_report_quality_score.json"
    internal_report = tmp_path / "internal_best_report.md"
    publish_report.write_text("not approved", encoding="utf-8")
    publish_quality.write_text("{}", encoding="utf-8")
    internal_report.write_text("internal", encoding="utf-8")

    _remove_unapproved_publish_artifacts(tmp_path)

    assert not publish_report.exists()
    assert not publish_quality.exists()
    assert internal_report.read_text(encoding="utf-8") == "internal"
    assert _empty_publish_quality_payload()["publish_report_exists"] == 0
