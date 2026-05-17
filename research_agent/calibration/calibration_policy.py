from __future__ import annotations

from research_agent.calibration.rule_weight_config import RuleWeight


MIN_SAMPLE_FOR_SHADOW = 20
MIN_SAMPLE_FOR_LIVE = 75
MIN_OBSERVATION_DAYS = 60
MAX_WEIGHT_CHANGE_PER_VERSION = 0.25
MAX_ABSOLUTE_WEIGHT = 3.0


def can_promote_rule_to_live(stats) -> bool:
    if stats.sample_size < MIN_SAMPLE_FOR_LIVE:
        return False
    if stats.confidence != "high":
        return False
    if abs(stats.suggested_weight_delta) > MAX_WEIGHT_CHANGE_PER_VERSION:
        return False
    return True


def can_include_rule_in_shadow(stats) -> bool:
    return stats.sample_size >= MIN_SAMPLE_FOR_SHADOW


def clamp_weight_change(delta: float) -> float:
    return max(-MAX_WEIGHT_CHANGE_PER_VERSION, min(MAX_WEIGHT_CHANGE_PER_VERSION, delta))


def clamp_absolute_weight(weight: float) -> float:
    return max(-MAX_ABSOLUTE_WEIGHT, min(MAX_ABSOLUTE_WEIGHT, weight))


def promote_rule_weight_if_allowed(rule: RuleWeight, stats) -> RuleWeight:
    if not can_promote_rule_to_live(stats):
        return rule
    calibrated_weight = clamp_absolute_weight(rule.base_weight + clamp_weight_change(stats.suggested_weight_delta))
    return rule.model_copy(update={
        "calibrated_weight": calibrated_weight,
        "shadow_only": False,
    }) if hasattr(rule, "model_copy") else rule.copy(update={
        "calibrated_weight": calibrated_weight,
        "shadow_only": False,
    })
