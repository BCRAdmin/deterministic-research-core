import json

from research_agent.outcomes.outcome_report import main
from research_agent.outcomes.report_manifest import build_report_manifest, save_report_manifest


def test_outcome_report_cli_writes_json(tmp_path):
    manifest = build_report_manifest(
        ticker="TEST",
        as_of_date="2026-05-01",
        price_basis_date="2026-05-01",
        price_basis_close=100.0,
        final_rating="Hold",
        preferred_rating="Hold",
        allowed_ratings=["Hold"],
        quality_score=90,
        publishable=True,
        decision_packet_path="decision_packet.json",
        metrics_packet_path="metrics_packet.json",
        validation_report_path="validation_report.json",
        final_report_path="final_report.md",
        pipeline_version="test",
    )
    manifest_path = save_report_manifest(manifest, tmp_path)
    prices_path = tmp_path / "prices.csv"
    prices_path.write_text(
        "date,open,high,low,close\n"
        "2026-05-02,100,102,99,101\n"
        "2026-05-03,101,103,100,102\n",
        encoding="utf-8",
    )
    output_path = tmp_path / "outcome_report.json"

    exit_code = main([
        "--manifest",
        str(manifest_path),
        "--prices",
        str(prices_path),
        "--output",
        str(output_path),
    ])

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["report_id"] == "TEST_2026-05-01"
    assert payload["price_outcomes"]["outcomes"]["1d"]["end_date"] == "2026-05-02"
