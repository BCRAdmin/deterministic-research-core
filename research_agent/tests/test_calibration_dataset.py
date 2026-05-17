from research_agent.calibration.agent_performance import aggregate_agent_performance
from research_agent.calibration.rule_performance import aggregate_rule_performance
from research_agent.calibration.score_calibration import summarize_score_calibration
from research_agent.outcomes.calibration_dataset import CalibrationRow, append_calibration_row, load_calibration_rows


def test_calibration_dataset_appends_jsonl_rows(tmp_path):
    row = CalibrationRow(
        report_id="MDB_2026-05-01",
        ticker="MDB",
        as_of_date="2026-05-01",
        rating="Tactical Underweight",
        quality_score=91,
        return_60d=-0.11,
        excess_return_60d=-0.08,
        max_drawdown_60d=-0.16,
        rating_success_60d=True,
        action_success=True,
        triggered_rules=["SBC_TO_REVENUE_GT_20"],
        agent_issue_counts={"news": 2},
    )

    path = append_calibration_row(row, tmp_path / "calibration_dataset.jsonl")
    loaded = load_calibration_rows(path)

    assert len(loaded) == 1
    assert loaded[0].ticker == "MDB"
    assert loaded[0].rating_success_60d


def test_rule_performance_aggregates_triggered_rules():
    rows = [
        CalibrationRow(
            report_id=f"R{i}",
            ticker="T",
            as_of_date="2026-05-01",
            rating="Hold",
            quality_score=90,
            return_60d=-0.02,
            excess_return_60d=-0.03,
            triggered_rules=["SBC_TO_REVENUE_GT_20"],
        )
        for i in range(12)
    ]

    performance = aggregate_rule_performance(rows, "SBC_TO_REVENUE_GT_20")

    assert performance.sample_size == 12
    assert performance.hit_rate_negative_excess == 1
    assert performance.recommendation == "keep_rule"


def test_score_and_agent_performance_summaries():
    rows = [
        CalibrationRow(
            report_id="R1",
            ticker="A",
            as_of_date="2026-05-01",
            rating="Buy",
            quality_score=90,
            return_60d=0.08,
            excess_return_60d=0.02,
            rating_success_60d=True,
            action_success=True,
            agent_issue_counts={"fundamental": 1},
        ),
        CalibrationRow(
            report_id="R2",
            ticker="B",
            as_of_date="2026-05-01",
            rating="Sell",
            quality_score=80,
            return_60d=0.05,
            excess_return_60d=0.01,
            rating_success_60d=False,
            action_success=False,
            agent_issue_counts={"fundamental": 3},
        ),
    ]

    score_summary = summarize_score_calibration(rows)
    agent_summary = aggregate_agent_performance(rows)

    assert score_summary.sample_size == 2
    assert score_summary.avg_quality_score == 85
    assert score_summary.rating_success_rate == 0.5
    assert agent_summary[0].agent == "fundamental"
    assert agent_summary[0].audit_issue_count == 4
