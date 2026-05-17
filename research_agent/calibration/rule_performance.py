from __future__ import annotations

from typing import Iterable, Optional

from pydantic import BaseModel

from research_agent.outcomes.calibration_dataset import CalibrationRow


class RulePerformance(BaseModel):
    rule: str
    sample_size: int
    avg_60d_return: Optional[float] = None
    avg_excess_return: Optional[float] = None
    hit_rate_negative_excess: Optional[float] = None
    recommendation: str


def aggregate_rule_performance(rows: Iterable[CalibrationRow], rule: str) -> RulePerformance:
    matched = [row for row in rows if rule in row.triggered_rules]
    avg_return = _avg([row.return_60d for row in matched])
    avg_excess = _avg([row.excess_return_60d for row in matched])
    negative_excess_rate = _negative_rate([row.excess_return_60d for row in matched])
    return RulePerformance(
        rule=rule,
        sample_size=len(matched),
        avg_60d_return=avg_return,
        avg_excess_return=avg_excess,
        hit_rate_negative_excess=negative_excess_rate,
        recommendation=_recommendation(len(matched), negative_excess_rate),
    )


def _avg(values: list[Optional[float]]) -> Optional[float]:
    available = [value for value in values if value is not None]
    return sum(available) / len(available) if available else None


def _negative_rate(values: list[Optional[float]]) -> Optional[float]:
    available = [value for value in values if value is not None]
    if not available:
        return None
    return sum(1 for value in available if value < 0) / len(available)


def _recommendation(sample_size: int, hit_rate_negative_excess: Optional[float]) -> str:
    if sample_size < 10:
        return "insufficient_sample"
    if hit_rate_negative_excess is not None and hit_rate_negative_excess >= 0.58:
        return "keep_rule"
    return "review_rule"
