import json
import zipfile

from research_agent.batch.review_bundle import REVIEW_BUNDLE_REQUIRED_FILES, create_chatgpt_review_bundle


def test_review_bundle_requires_extended_artifacts(tmp_path):
    batch = tmp_path / "batch"
    ticker_dir = batch / "AMZN"
    ticker_dir.mkdir(parents=True)
    artifacts = {}
    for name in REVIEW_BUNDLE_REQUIRED_FILES:
        path = ticker_dir / name
        path.write_text("{}", encoding="utf-8")
        artifacts[name] = str(path)
    (batch / "dashboard_status.json").write_text(
        json.dumps({"batch_id": "test", "items": [{"ticker": "AMZN", "artifacts": artifacts}]}),
        encoding="utf-8",
    )
    (batch / "pilot_review.md").write_text("# Review", encoding="utf-8")

    zip_path = create_chatgpt_review_bundle(batch, ["AMZN"])

    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
    assert "chatgpt_review_bundle/AMZN/metrics_packet.json" in names
    assert "chatgpt_review_bundle/AMZN/current_period_reconciliation_summary.md" in names
    assert "chatgpt_review_bundle/bundle_manifest.json" in names
