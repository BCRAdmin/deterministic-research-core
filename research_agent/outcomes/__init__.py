"""Outcome backtesting and ex-post calibration primitives."""

from research_agent.outcomes.price_outcome import (
    PriceOutcomeReport,
    WindowOutcome,
    calculate_price_outcomes,
)
from research_agent.outcomes.report_manifest import ReportManifest

__all__ = [
    "PriceOutcomeReport",
    "ReportManifest",
    "WindowOutcome",
    "calculate_price_outcomes",
]

