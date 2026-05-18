from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal, Union

from research_agent.outcomes.outcome_packet import OUTCOME_PACKET_HORIZONS, OutcomeHorizon, OutcomePacket

MaturationStatus = Literal["pending", "matured"]
MaturationMode = Literal["naive_calendar_days"]

MATURATION_CALENDAR_MODE: MaturationMode = "naive_calendar_days"
CALIBRATION_MIN_HORIZON: OutcomeHorizon = "60D"
MIN_CALIBRATION_SAMPLES_PER_RULE = 75

DateLike = Union[str, date]


@dataclass(frozen=True)
class MaturationWindow:
    decision_date: str
    horizon: OutcomeHorizon
    expected_maturity_date: str
    as_of_date: str
    status: MaturationStatus
    mode: MaturationMode = MATURATION_CALENDAR_MODE


def expected_maturity_date(decision_date: DateLike, horizon: OutcomeHorizon) -> date:
    return _to_date(decision_date) + timedelta(days=OUTCOME_PACKET_HORIZONS[horizon])


def maturation_status(
    decision_date: DateLike,
    horizon: OutcomeHorizon,
    as_of_date: DateLike,
) -> MaturationStatus:
    if _to_date(as_of_date) >= expected_maturity_date(decision_date, horizon):
        return "matured"
    return "pending"


def maturation_window(
    decision_date: DateLike,
    horizon: OutcomeHorizon,
    as_of_date: DateLike,
) -> MaturationWindow:
    maturity_date = expected_maturity_date(decision_date, horizon)
    as_of = _to_date(as_of_date)
    return MaturationWindow(
        decision_date=_to_date(decision_date).isoformat(),
        horizon=horizon,
        expected_maturity_date=maturity_date.isoformat(),
        as_of_date=as_of.isoformat(),
        status="matured" if as_of >= maturity_date else "pending",
    )


def packet_maturation_status(packet: OutcomePacket, as_of_date: DateLike) -> MaturationStatus:
    return maturation_status(packet.decision_date, packet.horizon, as_of_date)


def can_enter_shadow_calibration(
    packet: OutcomePacket,
    as_of_date: DateLike,
    sample_count: int,
) -> bool:
    return (
        packet.horizon == CALIBRATION_MIN_HORIZON
        and packet.status == "matured"
        and packet_maturation_status(packet, as_of_date) == "matured"
        and packet.decision_type != "manual_review"
        and sample_count >= MIN_CALIBRATION_SAMPLES_PER_RULE
    )


def _to_date(value: DateLike) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)
