import pandas as pd

from research_agent.outcomes.price_outcome import calculate_price_outcomes
from research_agent.outcomes.report_manifest import build_report_manifest


def test_no_outcome_price_on_or_before_basis_date():
    manifest = build_report_manifest(
        ticker="MDB",
        as_of_date="2026-05-01",
        price_basis_date="2026-05-01",
        price_basis_close=250.83,
        final_rating="Tactical Underweight",
        preferred_rating="Tactical Underweight",
        allowed_ratings=["Hold", "Tactical Trim", "Tactical Underweight"],
        quality_score=91,
        publishable=True,
        decision_packet_path="decision_packet.json",
        metrics_packet_path="metrics_packet.json",
        validation_report_path="validation_report.json",
        final_report_path="final_report.md",
        pipeline_version="test",
    )
    price_history = pd.DataFrame(
        [
            {"date": "2026-04-30", "high": 999, "low": 999, "close": 999},
            {"date": "2026-05-01", "high": 888, "low": 888, "close": 888},
            {"date": "2026-05-02", "high": 252, "low": 245, "close": 246},
            {"date": "2026-05-03", "high": 247, "low": 230, "close": 234},
        ]
    )

    outcomes = calculate_price_outcomes(manifest, price_history, windows={"1d": 1, "2d": 2})

    for outcome in outcomes.outcomes.values():
        assert outcome.end_date > manifest.price_basis_date
        assert outcome.end_price != 888
        assert outcome.end_price != 999
