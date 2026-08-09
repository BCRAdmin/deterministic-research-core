from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field

from research_agent.research_core.models.metrics_packet import MetricsPacket


VALUATION_CALIBRATION_SCHEMA = "room16.valuation_calibration_snapshot@1"
VALUATION_OUTCOME_SCHEMA = "room16.valuation_calibration_outcome@1"
VALUATION_READINESS_SCHEMA = "room16.valuation_calibration_readiness@1"
VALUATION_CALIBRATION_HORIZON_TRADING_DAYS = 252
MIN_EFFECTIVE_SAMPLES = 75
MIN_UNIQUE_ISSUERS = 25
MIN_SECTORS = 5
MAX_OBSERVATIONS_PER_ISSUER = 3


class ValuationCalibrationSnapshot(BaseModel):
    schema_id: str = VALUATION_CALIBRATION_SCHEMA
    snapshot_id: str
    ticker: str
    as_of_date: str
    sector: Optional[str] = None
    sector_source_sha256: Optional[str] = None
    method_id: str
    policy_version: str
    sensitivity_status: str
    price_series_basis: str
    price_basis_date: str
    share_basis: Optional[str] = None
    current_price: Optional[float] = None
    current_value_position: str
    reverse_dcf_implied_fcf_growth: Optional[float] = None
    bear_upside: Optional[float] = None
    base_upside: Optional[float] = None
    bull_upside: Optional[float] = None
    metrics_packet_sha256: str
    authority_manifest_sha256: Optional[str] = None
    eligible: bool
    exclusion_reasons: list[str] = Field(default_factory=list)


class ValuationCalibrationOutcome(BaseModel):
    schema_id: str = VALUATION_OUTCOME_SCHEMA
    snapshot_id: str
    status: Literal["pending", "matured", "invalidated", "data_unavailable"]
    horizon_trading_days: int = VALUATION_CALIBRATION_HORIZON_TRADING_DAYS
    trading_observation_count: int = 0
    benchmark: Optional[str] = None
    basis_date: Optional[str] = None
    instrument_basis_price: Optional[float] = None
    benchmark_basis_price: Optional[float] = None
    first_observation_date: Optional[str] = None
    observed_through: Optional[str] = None
    instrument_return: Optional[float] = None
    benchmark_return: Optional[float] = None
    excess_return: Optional[float] = None
    instrument_price_series_basis: str = "unknown"
    benchmark_price_series_basis: str = "unknown"
    source_hash: Optional[str] = None
    notes: list[str] = Field(default_factory=list)


class ValuationCalibrationPricePoint(BaseModel):
    date: str
    close: float


class ValuationCalibrationReadiness(BaseModel):
    schema_id: str = VALUATION_READINESS_SCHEMA
    status: Literal["not_ready", "shadow_ready"]
    snapshot_count: int
    eligible_snapshot_count: int
    valid_matured_outcome_count: int
    effective_sample_count: int
    unique_issuer_count: int
    sector_count: int
    excluded_snapshot_reasons: dict[str, int] = Field(default_factory=dict)
    invalid_outcome_reasons: dict[str, int] = Field(default_factory=dict)
    readiness_reasons: list[str] = Field(default_factory=list)
    live_activation_allowed: bool = False
    live_activation_blocker: str = (
        "Independent methodology review and signed operator promotion are required; "
        "readiness never activates valuation scoring automatically."
    )
    policy: dict[str, int] = Field(
        default_factory=lambda: {
            "horizon_trading_days": VALUATION_CALIBRATION_HORIZON_TRADING_DAYS,
            "minimum_effective_samples": MIN_EFFECTIVE_SAMPLES,
            "minimum_unique_issuers": MIN_UNIQUE_ISSUERS,
            "minimum_sectors": MIN_SECTORS,
            "maximum_observations_per_issuer": MAX_OBSERVATIONS_PER_ISSUER,
        }
    )


def build_valuation_calibration_snapshot(
    metrics: MetricsPacket,
    *,
    metrics_packet_sha256: str,
    authority_manifest_sha256: Optional[str] = None,
    sector: Optional[str] = None,
    sector_source_sha256: Optional[str] = None,
) -> ValuationCalibrationSnapshot:
    sensitivity = metrics.valuation.sensitivity
    scenarios = {scenario.name: scenario for scenario in sensitivity.scenarios}
    reasons: list[str] = []
    if sensitivity.status != "measured":
        reasons.append("sensitivity_not_measured")
    if sensitivity.share_basis not in {"listed_share_count", "economic_share_count"}:
        reasons.append("share_basis_not_verified")
    if sensitivity.reverse_dcf_status != "measured":
        reasons.append("reverse_dcf_not_measured")
    if set(scenarios) != {"bear", "base", "bull"}:
        reasons.append("scenario_set_incomplete")
    elif any(scenarios[name].upside_to_current_price is None for name in scenarios):
        reasons.append("scenario_upside_incomplete")
    if not _is_sha256(metrics_packet_sha256):
        reasons.append("metrics_packet_hash_invalid")
    if authority_manifest_sha256 is not None and not _is_sha256(
        authority_manifest_sha256
    ):
        reasons.append("authority_manifest_hash_invalid")
    if sensitivity.current_price is None or sensitivity.current_price <= 0:
        reasons.append("point_in_time_price_unavailable")
    try:
        if date.fromisoformat(metrics.technical.indicator_date) > date.fromisoformat(
            metrics.as_of_date
        ):
            reasons.append("point_in_time_price_lookahead")
    except ValueError:
        reasons.append("point_in_time_price_date_invalid")

    identity_payload = {
        "ticker": metrics.ticker,
        "as_of_date": metrics.as_of_date,
        "method_id": sensitivity.method_id,
        "policy_version": sensitivity.policy_version,
        "metrics_packet_sha256": metrics_packet_sha256,
        "authority_manifest_sha256": authority_manifest_sha256,
        "sector": sector.strip() if sector and sector.strip() else None,
        "sector_source_sha256": sector_source_sha256,
    }
    snapshot_id = "sha256:" + hashlib.sha256(
        json.dumps(identity_payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    return ValuationCalibrationSnapshot(
        snapshot_id=snapshot_id,
        ticker=metrics.ticker,
        as_of_date=metrics.as_of_date,
        sector=sector.strip() if sector and sector.strip() else None,
        sector_source_sha256=sector_source_sha256,
        method_id=sensitivity.method_id,
        policy_version=sensitivity.policy_version,
        sensitivity_status=sensitivity.status,
        price_series_basis=metrics.technical.price_series_basis,
        price_basis_date=metrics.technical.indicator_date,
        share_basis=sensitivity.share_basis,
        current_price=sensitivity.current_price,
        current_value_position=sensitivity.current_value_position,
        reverse_dcf_implied_fcf_growth=sensitivity.reverse_dcf_implied_fcf_growth,
        bear_upside=scenarios.get("bear").upside_to_current_price
        if scenarios.get("bear")
        else None,
        base_upside=scenarios.get("base").upside_to_current_price
        if scenarios.get("base")
        else None,
        bull_upside=scenarios.get("bull").upside_to_current_price
        if scenarios.get("bull")
        else None,
        metrics_packet_sha256=metrics_packet_sha256,
        authority_manifest_sha256=authority_manifest_sha256,
        eligible=not reasons,
        exclusion_reasons=reasons,
    )


def assess_valuation_calibration_readiness(
    snapshots: list[ValuationCalibrationSnapshot],
    outcomes: list[ValuationCalibrationOutcome],
) -> ValuationCalibrationReadiness:
    eligible = [snapshot for snapshot in snapshots if snapshot.eligible]
    excluded_reasons = Counter(
        reason
        for snapshot in snapshots
        for reason in snapshot.exclusion_reasons
    )
    snapshot_id_counts = Counter(snapshot.snapshot_id for snapshot in snapshots)
    duplicate_snapshot_count = sum(
        count for count in snapshot_id_counts.values() if count > 1
    )
    if duplicate_snapshot_count:
        excluded_reasons["duplicate_snapshot_id"] += duplicate_snapshot_count
    snapshots_by_id = {
        snapshot.snapshot_id: snapshot
        for snapshot in eligible
        if snapshot_id_counts[snapshot.snapshot_id] == 1
    }
    outcomes_by_snapshot: dict[str, list[ValuationCalibrationOutcome]] = defaultdict(list)
    for outcome in outcomes:
        outcomes_by_snapshot[outcome.snapshot_id].append(outcome)

    valid_pairs: list[
        tuple[ValuationCalibrationSnapshot, ValuationCalibrationOutcome]
    ] = []
    invalid_outcome_reasons: Counter[str] = Counter()
    all_snapshot_ids = set(snapshot_id_counts)
    for outcome in outcomes:
        if outcome.snapshot_id not in all_snapshot_ids:
            invalid_outcome_reasons["outcome_snapshot_missing"] += 1
        elif outcome.snapshot_id not in snapshots_by_id:
            invalid_outcome_reasons["outcome_snapshot_not_eligible"] += 1
    for snapshot_id, snapshot in snapshots_by_id.items():
        matches = outcomes_by_snapshot.get(snapshot_id, [])
        if not matches:
            invalid_outcome_reasons["matured_outcome_missing"] += 1
            continue
        if len(matches) != 1:
            invalid_outcome_reasons["duplicate_outcome_for_snapshot"] += 1
            continue
        outcome = matches[0]
        reasons = _outcome_invalid_reasons(snapshot, outcome)
        if reasons:
            invalid_outcome_reasons.update(reasons)
            continue
        valid_pairs.append((snapshot, outcome))

    per_issuer = Counter(snapshot.ticker for snapshot, _ in valid_pairs)
    effective_sample_count = sum(
        min(count, MAX_OBSERVATIONS_PER_ISSUER) for count in per_issuer.values()
    )
    unique_issuers = len(per_issuer)
    sectors = {
        snapshot.sector
        for snapshot, _ in valid_pairs
        if snapshot.sector is not None and _is_sha256(snapshot.sector_source_sha256)
    }
    readiness_reasons: list[str] = []
    if effective_sample_count < MIN_EFFECTIVE_SAMPLES:
        readiness_reasons.append("minimum_effective_sample_count_not_met")
    if unique_issuers < MIN_UNIQUE_ISSUERS:
        readiness_reasons.append("minimum_unique_issuer_count_not_met")
    if len(sectors) < MIN_SECTORS:
        readiness_reasons.append("minimum_sector_coverage_not_met")

    return ValuationCalibrationReadiness(
        status="shadow_ready" if not readiness_reasons else "not_ready",
        snapshot_count=len(snapshots),
        eligible_snapshot_count=len(eligible),
        valid_matured_outcome_count=len(valid_pairs),
        effective_sample_count=effective_sample_count,
        unique_issuer_count=unique_issuers,
        sector_count=len(sectors),
        excluded_snapshot_reasons=dict(sorted(excluded_reasons.items())),
        invalid_outcome_reasons=dict(sorted(invalid_outcome_reasons.items())),
        readiness_reasons=readiness_reasons,
    )


def render_valuation_calibration_readiness(
    readiness: ValuationCalibrationReadiness,
) -> str:
    reasons = readiness.readiness_reasons or ["none"]
    return "\n".join(
        [
            "# Room16 Valuation Calibration Readiness",
            "",
            f"- Status: `{readiness.status}`",
            f"- Snapshots: `{readiness.snapshot_count}`",
            f"- Eligible snapshots: `{readiness.eligible_snapshot_count}`",
            f"- Valid matured 252D outcomes: `{readiness.valid_matured_outcome_count}`",
            f"- Effective samples after issuer cap: `{readiness.effective_sample_count}`",
            f"- Unique issuers: `{readiness.unique_issuer_count}`",
            f"- Sectors: `{readiness.sector_count}`",
            f"- Live activation allowed: `{str(readiness.live_activation_allowed).lower()}`",
            "",
            "## Readiness blockers",
            "",
            *[f"- `{reason}`" for reason in reasons],
            "",
            "## Policy",
            "",
            *[
                f"- `{key}`: `{value}`"
                for key, value in readiness.policy.items()
            ],
            "",
            "A shadow-ready dataset is not proof of valuation alpha and never "
            "changes Room16 ratings automatically.",
            "",
        ]
    )


def scan_authority_root(
    authority_root: Union[str, Path],
    *,
    sectors: Optional[dict[str, str]] = None,
    sector_source_sha256: Optional[str] = None,
) -> list[ValuationCalibrationSnapshot]:
    root = Path(authority_root)
    snapshots: list[ValuationCalibrationSnapshot] = []
    for metrics_path in sorted(root.glob("*/*/authority_bundle/metrics_packet.json")):
        metrics_bytes = metrics_path.read_bytes()
        metrics = MetricsPacket(**json.loads(metrics_bytes))
        manifest_path = metrics_path.parent / "authority_manifest.json"
        manifest_hash = (
            "sha256:" + hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            if manifest_path.exists()
            else None
        )
        snapshots.append(
            build_valuation_calibration_snapshot(
                metrics,
                metrics_packet_sha256=(
                    "sha256:" + hashlib.sha256(metrics_bytes).hexdigest()
                ),
                authority_manifest_sha256=manifest_hash,
                sector=(sectors or {}).get(metrics.ticker),
                sector_source_sha256=sector_source_sha256,
            )
        )
    return snapshots


def build_valuation_calibration_outcome(
    snapshot: ValuationCalibrationSnapshot,
    *,
    benchmark: str,
    instrument_prices: list[ValuationCalibrationPricePoint],
    benchmark_prices: list[ValuationCalibrationPricePoint],
    instrument_price_series_basis: str,
    benchmark_price_series_basis: str,
) -> ValuationCalibrationOutcome:
    normalized_instrument = _price_map(instrument_prices)
    normalized_benchmark = _price_map(benchmark_prices)
    basis_date = snapshot.price_basis_date
    future_common_dates = sorted(
        day
        for day in set(normalized_instrument).intersection(normalized_benchmark)
        if day > basis_date
    )
    instrument_basis_price = normalized_instrument.get(basis_date)
    benchmark_basis_price = normalized_benchmark.get(basis_date)
    source_payload = {
        "snapshot_id": snapshot.snapshot_id,
        "benchmark": benchmark,
        "basis_date": basis_date,
        "benchmark_basis_price": benchmark_basis_price,
        "instrument_price_series_basis": instrument_price_series_basis,
        "benchmark_price_series_basis": benchmark_price_series_basis,
        "instrument_prices": [
            [day, normalized_instrument[day]] for day in sorted(normalized_instrument)
        ],
        "benchmark_prices": [
            [day, normalized_benchmark[day]] for day in sorted(normalized_benchmark)
        ],
    }
    source_hash = "sha256:" + hashlib.sha256(
        json.dumps(source_payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    base = {
        "snapshot_id": snapshot.snapshot_id,
        "horizon_trading_days": VALUATION_CALIBRATION_HORIZON_TRADING_DAYS,
        "trading_observation_count": min(
            len(future_common_dates), VALUATION_CALIBRATION_HORIZON_TRADING_DAYS
        ),
        "benchmark": benchmark,
        "basis_date": basis_date,
        "instrument_basis_price": instrument_basis_price,
        "benchmark_basis_price": benchmark_basis_price,
        "first_observation_date": (
            future_common_dates[0] if future_common_dates else None
        ),
        "observed_through": (
            future_common_dates[VALUATION_CALIBRATION_HORIZON_TRADING_DAYS - 1]
            if len(future_common_dates)
            >= VALUATION_CALIBRATION_HORIZON_TRADING_DAYS
            else future_common_dates[-1]
            if future_common_dates
            else None
        ),
        "instrument_price_series_basis": instrument_price_series_basis,
        "benchmark_price_series_basis": benchmark_price_series_basis,
        "source_hash": source_hash,
    }
    if instrument_basis_price is None or instrument_basis_price <= 0:
        return ValuationCalibrationOutcome(
            **base,
            status="data_unavailable",
            notes=["instrument_total_return_basis_price_unavailable"],
        )
    if benchmark_basis_price is None or benchmark_basis_price <= 0:
        return ValuationCalibrationOutcome(
            **base,
            status="data_unavailable",
            notes=["benchmark_total_return_basis_price_unavailable"],
        )
    if (
        instrument_price_series_basis != "total_return_adjusted"
        or benchmark_price_series_basis != "total_return_adjusted"
    ):
        return ValuationCalibrationOutcome(
            **base,
            status="invalidated",
            notes=["total_return_adjustment_not_verified"],
        )
    if len(future_common_dates) < VALUATION_CALIBRATION_HORIZON_TRADING_DAYS:
        return ValuationCalibrationOutcome(
            **base,
            status="pending",
            notes=[
                "needs_252_common_future_trading_observations",
            ],
        )

    end_date = future_common_dates[VALUATION_CALIBRATION_HORIZON_TRADING_DAYS - 1]
    instrument_return = normalized_instrument[end_date] / instrument_basis_price - 1
    benchmark_return = normalized_benchmark[end_date] / benchmark_basis_price - 1
    instrument_return = round(instrument_return, 12)
    benchmark_return = round(benchmark_return, 12)
    return ValuationCalibrationOutcome(
        **base,
        status="matured",
        instrument_return=instrument_return,
        benchmark_return=benchmark_return,
        excess_return=round(instrument_return - benchmark_return, 12),
    )


def load_valuation_outcomes(
    path: Optional[Union[str, Path]],
) -> list[ValuationCalibrationOutcome]:
    if path is None:
        return []
    target = Path(path)
    if not target.exists():
        return []
    return [
        ValuationCalibrationOutcome(**json.loads(line))
        for line in target.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build fail-closed Room16 valuation calibration readiness evidence."
    )
    parser.add_argument("--authority-root", required=True)
    parser.add_argument("--outcomes-jsonl")
    parser.add_argument("--sectors-json")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    sectors = None
    sector_source_sha256 = None
    if args.sectors_json:
        sectors_path = Path(args.sectors_json)
        sectors_bytes = sectors_path.read_bytes()
        sectors = json.loads(sectors_bytes)
        if not isinstance(sectors, dict):
            raise ValueError("sectors JSON must be a ticker-to-sector object")
        sectors = {str(key).upper(): str(value) for key, value in sectors.items()}
        sector_source_sha256 = "sha256:" + hashlib.sha256(sectors_bytes).hexdigest()

    snapshots = scan_authority_root(
        args.authority_root,
        sectors=sectors,
        sector_source_sha256=sector_source_sha256,
    )
    outcomes = load_valuation_outcomes(args.outcomes_jsonl)
    readiness = assess_valuation_calibration_readiness(snapshots, outcomes)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        output_dir / "valuation_calibration_snapshots.json",
        [snapshot.model_dump(mode="json") for snapshot in snapshots],
    )
    _write_json(
        output_dir / "valuation_calibration_readiness.json",
        readiness.model_dump(mode="json"),
    )
    (output_dir / "valuation_calibration_readiness.md").write_text(
        render_valuation_calibration_readiness(readiness),
        encoding="utf-8",
    )
    print(json.dumps(readiness.model_dump(mode="json"), indent=2, ensure_ascii=False))
    return 0


def _outcome_invalid_reasons(
    snapshot: ValuationCalibrationSnapshot,
    outcome: ValuationCalibrationOutcome,
) -> list[str]:
    reasons: list[str] = []
    if outcome.status != "matured":
        reasons.append("outcome_not_matured")
    if outcome.horizon_trading_days != VALUATION_CALIBRATION_HORIZON_TRADING_DAYS:
        reasons.append("outcome_horizon_not_252_trading_days")
    if outcome.trading_observation_count != VALUATION_CALIBRATION_HORIZON_TRADING_DAYS:
        reasons.append("outcome_observation_count_not_252")
    if outcome.instrument_price_series_basis != "total_return_adjusted":
        reasons.append("outcome_instrument_series_not_total_return_adjusted")
    if outcome.benchmark_price_series_basis != "total_return_adjusted":
        reasons.append("outcome_benchmark_series_not_total_return_adjusted")
    if outcome.basis_date != snapshot.price_basis_date:
        reasons.append("outcome_basis_date_mismatch")
    if outcome.observed_through is None:
        reasons.append("outcome_observed_through_missing")
    else:
        try:
            if date.fromisoformat(outcome.observed_through) <= date.fromisoformat(
                snapshot.as_of_date
            ):
                reasons.append("outcome_lookahead_window_invalid")
        except ValueError:
            reasons.append("outcome_observed_through_invalid")
    if not _is_sha256(outcome.source_hash):
        reasons.append("outcome_source_hash_invalid")
    returns = (
        outcome.instrument_return,
        outcome.benchmark_return,
        outcome.excess_return,
    )
    if any(value is None for value in returns):
        reasons.append("outcome_returns_incomplete")
    elif abs(
        float(outcome.instrument_return)
        - float(outcome.benchmark_return)
        - float(outcome.excess_return)
    ) > 1e-9:
        reasons.append("outcome_excess_return_mismatch")
    return reasons


def _is_sha256(value: Optional[str]) -> bool:
    if value is None:
        return False
    normalized = value.removeprefix("sha256:")
    return len(normalized) == 64 and all(
        character in "0123456789abcdef" for character in normalized.lower()
    )


def _price_map(
    prices: list[ValuationCalibrationPricePoint],
) -> dict[str, float]:
    normalized: dict[str, float] = {}
    for point in prices:
        point_date = date.fromisoformat(point.date)
        if point.close <= 0:
            continue
        normalized[point_date.isoformat()] = float(point.close)
    return normalized


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
