from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field

OutcomeHorizon = Literal["5D", "10D", "20D", "60D"]
OutcomeStatus = Literal["pending", "matured", "invalidated", "data_unavailable"]
DecisionType = Literal["approved_internal", "manual_review", "promotion_blocked"]

OUTCOME_PACKET_HORIZONS: dict[OutcomeHorizon, int] = {
    "5D": 5,
    "10D": 10,
    "20D": 20,
    "60D": 60,
}
OUTCOME_PACKET_CALC_VERSION = "outcome-tracking-v1"


class OutcomePricePoint(BaseModel):
    date: str
    close: float


class OutcomeFixture(BaseModel):
    scenario_id: str
    instrument: str
    decision_date: str
    decision_type: DecisionType
    basis_price: float
    benchmark: str
    benchmark_basis_price: Optional[float] = None
    as_of_date: str
    instrument_prices: list[OutcomePricePoint] = Field(default_factory=list)
    benchmark_prices: list[OutcomePricePoint] = Field(default_factory=list)
    source_hash: Optional[str] = None
    calc_version: str = OUTCOME_PACKET_CALC_VERSION
    manual_review_reason: Optional[str] = None
    expected_status_by_horizon: dict[str, OutcomeStatus] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class OutcomePacket(BaseModel):
    instrument: str
    decision_date: str
    decision_type: DecisionType
    basis_price: float
    benchmark: str
    horizon: OutcomeHorizon
    status: OutcomeStatus
    observed_return: Optional[float] = None
    benchmark_return: Optional[float] = None
    delta_to_benchmark: Optional[float] = None
    source_hash: str
    calc_version: str = OUTCOME_PACKET_CALC_VERSION
    notes: list[str] = Field(default_factory=list)
    manual_review_reason: Optional[str] = None
    public_ready: bool = False


def load_outcome_fixture(path: Union[str, Path]) -> OutcomeFixture:
    return OutcomeFixture(**json.loads(Path(path).read_text(encoding="utf-8")))


def load_outcome_fixtures(directory: Union[str, Path]) -> list[OutcomeFixture]:
    root = Path(directory)
    return [load_outcome_fixture(path) for path in sorted(root.glob("*.json"))]


def calculate_outcome_packets(
    fixture: OutcomeFixture,
    horizons: Optional[dict[OutcomeHorizon, int]] = None,
    no_live_fetch: bool = True,
) -> list[OutcomePacket]:
    if not no_live_fetch:
        raise RuntimeError("Outcome Tracking V1 is fixture-only; live fetch is disabled.")

    horizons = horizons or OUTCOME_PACKET_HORIZONS
    source_hash = calculate_fixture_source_hash(fixture)
    source_valid = fixture.source_hash in {None, source_hash}
    instrument_prices = _future_prices(fixture.instrument_prices, fixture.decision_date)
    benchmark_prices = _future_prices(fixture.benchmark_prices, fixture.decision_date)

    return [
        _calculate_packet_for_horizon(
            fixture=fixture,
            horizon=horizon,
            trading_days=trading_days,
            source_hash=source_hash,
            source_valid=source_valid,
            instrument_prices=instrument_prices,
            benchmark_prices=benchmark_prices,
        )
        for horizon, trading_days in horizons.items()
    ]


def packet_by_horizon(packets: list[OutcomePacket]) -> dict[str, OutcomePacket]:
    return {packet.horizon: packet for packet in packets}


def calculate_fixture_source_hash(fixture: OutcomeFixture) -> str:
    payload = fixture.model_dump(mode="json") if hasattr(fixture, "model_dump") else fixture.dict()
    payload.pop("source_hash", None)
    payload.pop("expected_status_by_horizon", None)
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _calculate_packet_for_horizon(
    fixture: OutcomeFixture,
    horizon: OutcomeHorizon,
    trading_days: int,
    source_hash: str,
    source_valid: bool,
    instrument_prices: list[OutcomePricePoint],
    benchmark_prices: list[OutcomePricePoint],
) -> OutcomePacket:
    notes = list(fixture.notes)
    if fixture.decision_type == "manual_review" and fixture.manual_review_reason:
        notes.append("manual_review_remains_binding")

    if not source_valid:
        return _packet(
            fixture,
            horizon,
            source_hash,
            status="invalidated",
            notes=notes + ["fixture_source_hash_mismatch"],
        )

    if fixture.basis_price <= 0:
        return _packet(
            fixture,
            horizon,
            source_hash,
            status="data_unavailable",
            notes=notes + ["basis_price_unavailable"],
        )

    if not instrument_prices:
        return _packet(
            fixture,
            horizon,
            source_hash,
            status="data_unavailable",
            notes=notes + ["instrument_price_history_unavailable"],
        )

    if len(instrument_prices) < trading_days:
        return _packet(
            fixture,
            horizon,
            source_hash,
            status="pending",
            notes=notes + [f"needs_{trading_days}_future_trading_observations"],
        )

    if fixture.benchmark_basis_price is None or fixture.benchmark_basis_price <= 0:
        return _packet(
            fixture,
            horizon,
            source_hash,
            status="data_unavailable",
            notes=notes + ["benchmark_basis_price_unavailable"],
        )

    if len(benchmark_prices) < trading_days:
        return _packet(
            fixture,
            horizon,
            source_hash,
            status="data_unavailable",
            notes=notes + [f"benchmark_needs_{trading_days}_future_trading_observations"],
        )

    observed_return = _forward_return(fixture.basis_price, instrument_prices[trading_days - 1].close)
    benchmark_return = _forward_return(
        fixture.benchmark_basis_price,
        benchmark_prices[trading_days - 1].close,
    )
    return _packet(
        fixture,
        horizon,
        source_hash,
        status="matured",
        observed_return=observed_return,
        benchmark_return=benchmark_return,
        delta_to_benchmark=round(observed_return - benchmark_return, 6),
        notes=notes,
    )


def _packet(
    fixture: OutcomeFixture,
    horizon: OutcomeHorizon,
    source_hash: str,
    status: OutcomeStatus,
    notes: list[str],
    observed_return: Optional[float] = None,
    benchmark_return: Optional[float] = None,
    delta_to_benchmark: Optional[float] = None,
) -> OutcomePacket:
    return OutcomePacket(
        instrument=fixture.instrument,
        decision_date=fixture.decision_date,
        decision_type=fixture.decision_type,
        basis_price=fixture.basis_price,
        benchmark=fixture.benchmark,
        horizon=horizon,
        status=status,
        observed_return=observed_return,
        benchmark_return=benchmark_return,
        delta_to_benchmark=delta_to_benchmark,
        source_hash=source_hash,
        calc_version=fixture.calc_version,
        notes=notes,
        manual_review_reason=fixture.manual_review_reason,
        public_ready=False,
    )


def _future_prices(prices: list[OutcomePricePoint], decision_date: str) -> list[OutcomePricePoint]:
    return sorted(
        [point for point in prices if point.date > decision_date],
        key=lambda point: point.date,
    )


def _forward_return(start_price: float, end_price: float) -> float:
    return round((end_price / start_price) - 1, 6)
