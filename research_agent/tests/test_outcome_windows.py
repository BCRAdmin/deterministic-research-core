from pathlib import Path

import pandas as pd
import pytest

from research_agent.outcomes.outcome_windows import OUTCOME_WINDOWS
from research_agent.outcomes.price_outcome import calculate_price_outcomes
from research_agent.outcomes.report_manifest import (
    build_report_manifest,
    load_report_manifest,
    save_report_manifest,
)


def _manifest():
    return build_report_manifest(
        ticker="TEST",
        as_of_date="2026-05-01",
        price_basis_date="2026-05-01",
        price_basis_close=100.0,
        final_rating="Hold",
        preferred_rating="Hold",
        allowed_ratings=["Hold", "Accumulate"],
        quality_score=91,
        publishable=True,
        decision_packet_path="decision_packet.json",
        metrics_packet_path="metrics_packet.json",
        validation_report_path="validation_report.json",
        final_report_path="final_report.md",
        pipeline_version="test",
    )


def test_outcome_windows_include_required_horizons():
    assert OUTCOME_WINDOWS == {
        "1d": 1,
        "5d": 5,
        "10d": 10,
        "20d": 20,
        "60d": 60,
        "90d": 90,
        "180d": 180,
    }


def test_price_outcomes_calculate_return_stop_and_target():
    price_history = pd.DataFrame(
        [
            {"date": "2026-05-02", "open": 101, "high": 103, "low": 99, "close": 102},
            {"date": "2026-05-03", "open": 102, "high": 112, "low": 101, "close": 110},
            {"date": "2026-05-04", "open": 110, "high": 111, "low": 94, "close": 95},
        ]
    )

    report = calculate_price_outcomes(
        manifest=_manifest(),
        price_history=price_history,
        stop_loss=95,
        target=110,
        windows={"3d": 3},
    )

    outcome = report.outcomes["3d"]
    assert outcome.end_date == "2026-05-04"
    assert outcome.return_pct == pytest.approx(-0.05)
    assert outcome.max_gain_pct == pytest.approx(0.12)
    assert outcome.max_drawdown_pct == pytest.approx(-0.06)
    assert outcome.hit_stop
    assert outcome.hit_target
    assert outcome.days_to_stop == 3
    assert outcome.days_to_target == 2


def test_report_manifest_saves_to_ticker_date_folder(tmp_path):
    manifest_path = save_report_manifest(_manifest(), tmp_path)
    loaded = load_report_manifest(manifest_path)

    assert manifest_path == Path(tmp_path) / "TEST" / "2026-05-01" / "report_manifest.json"
    assert loaded.report_id == "TEST_2026-05-01"
    assert loaded.publishable
