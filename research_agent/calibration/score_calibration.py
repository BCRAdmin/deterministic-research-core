from __future__ import annotations

from typing import Iterable, Optional

from pydantic import BaseModel

from research_agent.outcomes.calibration_dataset import CalibrationRow


class ScoreCalibrationSummary(BaseModel):
    sample_size: int
    avg_quality_score: Optional[float] = None
    avg_60d_return: Optional[float] = None
    avg_excess_return_60d: Optional[float] = None
    rating_success_rate: Optional[float] = None
    action_success_rate: Optional[float] = None


def summarize_score_calibration(rows: Iterable[CalibrationRow]) -> ScoreCalibrationSummary:
    rows = list(rows)
    return ScoreCalibrationSummary(
        sample_size=len(rows),
        avg_quality_score=_avg([row.quality_score for row in rows]),
        avg_60d_return=_avg([row.return_60d for row in rows]),
        avg_excess_return_60d=_avg([row.excess_return_60d for row in rows]),
        rating_success_rate=_rate([row.rating_success_60d for row in rows]),
        action_success_rate=_rate([row.action_success for row in rows]),
    )


def _avg(values: list[Optional[float]]) -> Optional[float]:
    available = [value for value in values if value is not None]
    if not available:
        return None
    return sum(available) / len(available)


def _rate(values: list[Optional[bool]]) -> Optional[float]:
    available = [value for value in values if value is not None]
    if not available:
        return None
    return sum(1 for value in available if value) / len(available)
