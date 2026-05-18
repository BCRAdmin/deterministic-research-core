"""Outcome backtesting and ex-post calibration primitives."""

from research_agent.outcomes.price_outcome import (
    PriceOutcomeReport,
    WindowOutcome,
    calculate_price_outcomes,
)
from research_agent.outcomes.outcome_packet import (
    OUTCOME_PACKET_HORIZONS,
    OutcomeFixture,
    OutcomePacket,
    calculate_outcome_packets,
)
from research_agent.outcomes.report_manifest import ReportManifest

__all__ = [
    "OUTCOME_PACKET_HORIZONS",
    "OutcomeFixture",
    "OutcomePacket",
    "PriceOutcomeReport",
    "ReportManifest",
    "WindowOutcome",
    "calculate_outcome_packets",
    "calculate_price_outcomes",
]
