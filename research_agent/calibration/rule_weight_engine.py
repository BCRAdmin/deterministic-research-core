from __future__ import annotations

import math
from typing import Iterable, Optional

from pydantic import BaseModel

from research_agent.calibration.calibration_policy import MAX_ABSOLUTE_WEIGHT
from research_agent.calibration.rule_weight_config import RuleWeightConfig
from research_agent.outcomes.calibration_dataset import CalibrationRow


class RuleCalibrationStats(BaseModel):
    rule_id: str
    sample_size: int
    avg_20d_excess_return: Optional[float] = None
    avg_60d_excess_return: Optional[float] = None
    avg_90d_excess_return: Optional[float] = None
    hit_rate_positive_excess_60d: Optional[float] = None
    avg_max_drawdown_60d: Optional[float] = None
    suggested_weight_delta: float
    confidence: str
    recommendation: str


def calculate_rule_calibration_stats(
    rows: Iterable[CalibrationRow],
    rule_id: str,
) -> RuleCalibrationStats:
    matched = [row for row in rows if rule_id in row.triggered_rules]
    draft = RuleCalibrationStats(
        rule_id=rule_id,
        sample_size=len(matched),
        avg_20d_excess_return=_avg([row.excess_return_20d for row in matched]),
        avg_60d_excess_return=_avg([row.excess_return_60d for row in matched]),
        avg_90d_excess_return=_avg([row.excess_return_90d for row in matched]),
        hit_rate_positive_excess_60d=_positive_rate([row.excess_return_60d for row in matched]),
        avg_max_drawdown_60d=_avg([row.max_drawdown_60d for row in matched]),
        suggested_weight_delta=0.0,
        confidence=_confidence(len(matched)),
        recommendation="shadow_only",
    )
    delta = suggest_weight_delta(draft)
    return draft.model_copy(update={
        "suggested_weight_delta": delta,
        "recommendation": _recommendation(draft.sample_size, delta),
    }) if hasattr(draft, "model_copy") else draft.copy(update={
        "suggested_weight_delta": delta,
        "recommendation": _recommendation(draft.sample_size, delta),
    })


def calculate_all_rule_calibration_stats(
    rows: Iterable[CalibrationRow],
    config: RuleWeightConfig,
) -> list[RuleCalibrationStats]:
    rows = list(rows)
    return [
        calculate_rule_calibration_stats(rows, rule_id)
        for rule_id in sorted(config.rules)
    ]


def suggest_weight_delta(stats: RuleCalibrationStats) -> float:
    if stats.sample_size < 30:
        return 0.0

    delta = 0.0
    if stats.avg_60d_excess_return is not None:
        if stats.avg_60d_excess_return > 0.05:
            delta += 0.25
        elif stats.avg_60d_excess_return < -0.05:
            delta -= 0.25

    if stats.avg_max_drawdown_60d is not None and stats.avg_max_drawdown_60d < -0.15:
        delta -= 0.25

    return max(-0.75, min(0.75, delta))


def build_shadow_weight_config(
    base_config: RuleWeightConfig,
    stats: Iterable[RuleCalibrationStats],
    version: str,
) -> RuleWeightConfig:
    rules = {
        rule_id: (rule.model_copy() if hasattr(rule, "model_copy") else rule.copy())
        for rule_id, rule in base_config.rules.items()
    }
    for stat in stats:
        rule = rules.get(stat.rule_id)
        if rule is None:
            continue
        calibrated = max(
            -MAX_ABSOLUTE_WEIGHT,
            min(MAX_ABSOLUTE_WEIGHT, rule.base_weight + stat.suggested_weight_delta),
        )
        rules[stat.rule_id] = rule.model_copy(update={
            "calibrated_weight": calibrated,
            "shadow_only": True,
        }) if hasattr(rule, "model_copy") else rule.copy(update={
            "calibrated_weight": calibrated,
            "shadow_only": True,
        })
    return RuleWeightConfig(version=version, rules=rules)


def _avg(values: list[Optional[float]]) -> Optional[float]:
    available = [value for value in values if value is not None]
    return round(math.fsum(available) / len(available), 12) if available else None


def _positive_rate(values: list[Optional[float]]) -> Optional[float]:
    available = [value for value in values if value is not None]
    if not available:
        return None
    return sum(1 for value in available if value > 0) / len(available)


def _confidence(sample_size: int) -> str:
    if sample_size >= 75:
        return "high"
    if sample_size >= 30:
        return "medium"
    return "low"


def _recommendation(sample_size: int, delta: float) -> str:
    if sample_size < 30:
        return "shadow_only"
    if delta > 0:
        return "increase"
    if delta < 0:
        return "decrease"
    return "keep"
