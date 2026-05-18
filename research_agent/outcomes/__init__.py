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
from research_agent.outcomes.maturation_calendar import (
    MATURATION_CALENDAR_MODE,
    MaturationWindow,
    can_enter_shadow_calibration,
    expected_maturity_date,
    maturation_status,
    maturation_window,
)
from research_agent.outcomes.report_manifest import ReportManifest

__all__ = [
    "MATURATION_CALENDAR_MODE",
    "OUTCOME_PACKET_HORIZONS",
    "OutcomeFixture",
    "OutcomePacket",
    "MaturationWindow",
    "PriceOutcomeReport",
    "ReportManifest",
    "WindowOutcome",
    "can_enter_shadow_calibration",
    "calculate_outcome_packets",
    "calculate_price_outcomes",
    "expected_maturity_date",
    "maturation_status",
    "maturation_window",
]
