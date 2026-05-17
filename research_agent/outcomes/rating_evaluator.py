from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from research_agent.outcomes.benchmark_outcome import BenchmarkOutcome
from research_agent.outcomes.price_outcome import WindowOutcome


class RatingEvaluation(BaseModel):
    rating: str
    window: str = "60d"
    success: Optional[bool]
    notes: list[str] = Field(default_factory=list)
    stock_return_pct: Optional[float] = None
    excess_return_pct: Optional[float] = None


def evaluate_rating_success(
    rating: str,
    outcome_20d: Optional[WindowOutcome],
    outcome_60d: Optional[WindowOutcome],
    benchmark_60d: Optional[BenchmarkOutcome] = None,
) -> Optional[bool]:
    evaluation = evaluate_rating(rating, outcome_20d, outcome_60d, benchmark_60d)
    return evaluation.success


def evaluate_rating(
    rating: str,
    outcome_20d: Optional[WindowOutcome],
    outcome_60d: Optional[WindowOutcome],
    benchmark_60d: Optional[BenchmarkOutcome] = None,
) -> RatingEvaluation:
    normalized = rating.strip().lower()
    stock_60d = outcome_60d.return_pct if outcome_60d else None
    excess_60d = benchmark_60d.excess_return_pct if benchmark_60d else None
    notes: list[str] = []

    if stock_60d is None:
        return RatingEvaluation(
            rating=rating,
            success=None,
            notes=["60D stock return is unavailable."],
            stock_return_pct=stock_60d,
            excess_return_pct=excess_60d,
        )

    if normalized in {"strong buy", "buy"}:
        success = stock_60d > 0
        notes.append("Buy ratings require positive absolute 60D performance.")
        if excess_60d is not None:
            success = success and excess_60d > 0
            notes.append("Benchmark-relative outperformance is required when benchmark data exists.")
        return _result(rating, success, notes, stock_60d, excess_60d)

    if normalized == "accumulate":
        max_drawdown = outcome_60d.max_drawdown_pct if outcome_60d else None
        success = max_drawdown is not None and max_drawdown > -0.15
        notes.append("Accumulate can tolerate pullbacks if drawdown stays within the thesis buffer.")
        return _result(rating, success, notes, stock_60d, excess_60d)

    if normalized == "hold":
        success = stock_60d > -0.10
        notes.append("Hold succeeds when severe 60D underperformance is avoided.")
        return _result(rating, success, notes, stock_60d, excess_60d)

    if normalized in {"tactical trim", "tactical underweight", "underweight", "sell", "avoid"}:
        success = stock_60d < 0
        notes.append("Reduction/avoidance ratings succeed when weakness or drawdown materializes.")
        if excess_60d is not None:
            success = success or excess_60d < 0
            notes.append("Relative underperformance versus benchmark also validates defensive ratings.")
        return _result(rating, success, notes, stock_60d, excess_60d)

    return RatingEvaluation(
        rating=rating,
        success=None,
        notes=[f"Unknown rating '{rating}' cannot be evaluated deterministically."],
        stock_return_pct=stock_60d,
        excess_return_pct=excess_60d,
    )


def _result(
    rating: str,
    success: bool,
    notes: list[str],
    stock_return_pct: Optional[float],
    excess_return_pct: Optional[float],
) -> RatingEvaluation:
    return RatingEvaluation(
        rating=rating,
        success=success,
        notes=notes,
        stock_return_pct=stock_return_pct,
        excess_return_pct=excess_return_pct,
    )
