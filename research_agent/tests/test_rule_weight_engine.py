from research_agent.calibration.rule_weight_config import DEFAULT_RULE_WEIGHTS, RuleWeight, RuleWeightConfig
from research_agent.calibration.rule_weight_engine import (
    RuleCalibrationStats,
    build_shadow_weight_config,
    calculate_rule_calibration_stats,
    suggest_weight_delta,
)
from research_agent.outcomes.calibration_dataset import CalibrationRow


def test_weight_delta_is_capped():
    stats = RuleCalibrationStats(
        rule_id="DEATH_CROSS",
        sample_size=100,
        avg_60d_excess_return=-0.20,
        avg_max_drawdown_60d=-0.30,
        suggested_weight_delta=-2.0,
        confidence="high",
        recommendation="decrease",
    )

    delta = suggest_weight_delta(stats)

    assert abs(delta) <= 0.75


def test_rule_calibration_stats_aggregate_outcomes_by_rule():
    rows = [
        CalibrationRow(
            report_id=f"R{i}",
            ticker="T",
            as_of_date="2026-05-01",
            rating="Hold",
            quality_score=90,
            excess_return_20d=-0.01,
            excess_return_60d=-0.08,
            excess_return_90d=-0.04,
            max_drawdown_60d=-0.18,
            triggered_rules=["DEATH_CROSS"],
        )
        for i in range(35)
    ]

    stats = calculate_rule_calibration_stats(rows, "DEATH_CROSS")

    assert stats.sample_size == 35
    assert stats.avg_60d_excess_return == -0.08
    assert stats.suggested_weight_delta < 0
    assert stats.confidence == "medium"


def test_shadow_weight_config_uses_calibrated_weights_only_in_shadow():
    config = RuleWeightConfig(
        version="v1",
        rules={"DEATH_CROSS": RuleWeight(rule_id="DEATH_CROSS", base_weight=-1.0)},
    )
    stats = [
        RuleCalibrationStats(
            rule_id="DEATH_CROSS",
            sample_size=80,
            avg_60d_excess_return=-0.08,
            suggested_weight_delta=-0.25,
            confidence="high",
            recommendation="decrease",
        )
    ]

    shadow = build_shadow_weight_config(config, stats, version="v2_shadow")

    assert shadow.get_weight("DEATH_CROSS", "live") == -1.0
    assert shadow.get_weight("DEATH_CROSS", "shadow") == -1.25
    assert DEFAULT_RULE_WEIGHTS.get_weight("DEATH_CROSS") == -1.0
