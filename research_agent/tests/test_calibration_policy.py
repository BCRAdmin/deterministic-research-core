from research_agent.calibration.calibration_policy import (
    can_include_rule_in_shadow,
    can_promote_rule_to_live,
    clamp_weight_change,
)
from research_agent.calibration.rule_weight_engine import RuleCalibrationStats


def test_small_sample_stays_shadow_only():
    stats = RuleCalibrationStats(
        rule_id="RSI_GT_75",
        sample_size=12,
        avg_60d_excess_return=-0.08,
        suggested_weight_delta=-0.25,
        confidence="low",
        recommendation="shadow_only",
    )

    assert not can_include_rule_in_shadow(stats)
    assert not can_promote_rule_to_live(stats)


def test_live_promotion_requires_high_confidence_and_small_delta():
    stats = RuleCalibrationStats(
        rule_id="DEATH_CROSS",
        sample_size=90,
        avg_60d_excess_return=-0.06,
        suggested_weight_delta=-0.25,
        confidence="high",
        recommendation="decrease",
    )

    assert can_promote_rule_to_live(stats)


def test_large_delta_cannot_promote_to_live():
    stats = RuleCalibrationStats(
        rule_id="DEATH_CROSS",
        sample_size=90,
        avg_60d_excess_return=-0.20,
        suggested_weight_delta=-0.50,
        confidence="high",
        recommendation="decrease",
    )

    assert not can_promote_rule_to_live(stats)
    assert clamp_weight_change(stats.suggested_weight_delta) == -0.25
