from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from research_agent.research_core.models.metrics_packet import MetricsPacket
from research_agent.sources.prices.provider_price_candidate import (
    ProviderPriceCandidateReceipt,
    load_provider_price_candidate,
)


VALUATION_CALIBRATION_SCHEMA = "room16.valuation_calibration_snapshot@1"
VALUATION_SOURCE_BUNDLE_SCHEMA = "room16.valuation_calibration_source_bundle@2"
VALUATION_OUTCOME_SCHEMA = "room16.valuation_calibration_outcome@1"
VALUATION_READINESS_SCHEMA = "room16.valuation_calibration_readiness@1"
VALUATION_REPLAY_SCHEMA = "room16.valuation_calibration_replay@1"
VALUATION_OUTCOME_CALC_VERSION = "valuation-calibration-outcome-v1"
VALUATION_CALIBRATION_HORIZON_TRADING_DAYS = 252
MIN_EFFECTIVE_SAMPLES = 75
MIN_UNIQUE_ISSUERS = 25
MIN_SECTORS = 5
MAX_OBSERVATIONS_PER_ISSUER = 3
AUTOMATION_IDENTITY_PATTERN = re.compile(
    r"^(?:ai|agent|automation|bot|chatgpt|claude|codex|deepseek|gemini|llm|"
    r"model|openai|room\s*16|system|vega|vivi)(?:\b|[-_])",
    re.IGNORECASE,
)


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
    capture_mode: Literal["contemporaneous", "retrospective_replay"] = "contemporaneous"
    base_snapshot_id: Optional[str] = None
    retrospective_replay_manifest_sha256: Optional[str] = None
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
    instrument_max_drawdown: Optional[float] = None
    benchmark_max_drawdown: Optional[float] = None
    instrument_price_series_basis: str = "unknown"
    benchmark_price_series_basis: str = "unknown"
    source_hash: Optional[str] = None
    calc_version: str = VALUATION_OUTCOME_CALC_VERSION
    notes: list[str] = Field(default_factory=list)


class ValuationCalibrationPricePoint(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    date: str
    close: float


class ValuationCalibrationSourceBundle(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_id: str = VALUATION_SOURCE_BUNDLE_SCHEMA
    snapshot_id: str
    provider_id: str
    provider_dataset_id: str
    instrument: str
    benchmark: str
    basis_date: str
    retrieved_at: str
    bundle_created_at: str
    instrument_price_series_basis: str
    benchmark_price_series_basis: str
    instrument_cash_distributions_included: bool = False
    benchmark_cash_distributions_included: bool = False
    instrument_corporate_actions_included: bool = False
    benchmark_corporate_actions_included: bool = False
    provider_methodology_sha256: Optional[str] = None
    provider_methodology_path: Optional[str] = None
    usage_rights_status: Literal["unverified", "internal_calibration_allowed"] = "unverified"
    usage_rights_evidence_sha256: Optional[str] = None
    usage_rights_evidence_path: Optional[str] = None
    usage_rights_approved_by: Optional[str] = None
    usage_rights_approved_at: Optional[str] = None
    instrument_source_sha256: Optional[str] = None
    instrument_source_path: Optional[str] = None
    benchmark_source_sha256: Optional[str] = None
    benchmark_source_path: Optional[str] = None
    instrument_provider_receipt_sha256: Optional[str] = None
    instrument_provider_receipt_path: Optional[str] = None
    benchmark_provider_receipt_sha256: Optional[str] = None
    benchmark_provider_receipt_path: Optional[str] = None
    prepared_by: Optional[str] = None
    verification_status: Literal["unverified", "human_verified"] = "unverified"
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    verification_independent_from_preparation: bool = False
    verification_evidence_sha256: Optional[str] = None
    verification_evidence_path: Optional[str] = None
    instrument_prices: list[ValuationCalibrationPricePoint] = Field(default_factory=list)
    benchmark_prices: list[ValuationCalibrationPricePoint] = Field(default_factory=list)
    source_bundle_sha256: Optional[str] = None


class RetrospectiveReplayArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    path: str
    sha256: str


class ValuationCalibrationReplayManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_id: str = VALUATION_REPLAY_SCHEMA
    replay_id: str
    ticker: str
    as_of_date: str
    generated_at: str
    replay_mode: Literal["historical_point_in_time"] = "historical_point_in_time"
    publication_allowed: Literal[False] = False
    pipeline_commit_sha: str
    source_cutoff_passed: bool
    cutoff_counts: dict[str, int]
    artifacts: dict[str, RetrospectiveReplayArtifact]
    replay_manifest_sha256: Optional[str] = None


class ValuationCalibrationReadiness(BaseModel):
    schema_id: str = VALUATION_READINESS_SCHEMA
    status: Literal["not_ready", "shadow_ready"]
    snapshot_count: int
    eligible_snapshot_count: int
    valid_matured_outcome_count: int
    effective_sample_count: int
    unique_issuer_count: int
    sector_count: int
    capture_mode_counts: dict[str, int] = Field(default_factory=dict)
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
    authority_analysis_allowed: Optional[bool] = None,
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
    if authority_manifest_sha256 is None:
        reasons.append("authority_manifest_hash_missing")
    elif not _is_sha256(authority_manifest_sha256):
        reasons.append("authority_manifest_hash_invalid")
    if authority_analysis_allowed is not True:
        reasons.append("authority_bundle_not_approved")
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
    }
    snapshot_id = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(identity_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
    )
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
        reason for snapshot in snapshots for reason in snapshot.exclusion_reasons
    )
    snapshot_id_counts = Counter(snapshot.snapshot_id for snapshot in snapshots)
    duplicate_snapshot_count = sum(count for count in snapshot_id_counts.values() if count > 1)
    if duplicate_snapshot_count:
        excluded_reasons["duplicate_snapshot_id"] += duplicate_snapshot_count
    observation_key_counts = Counter(
        (snapshot.ticker, snapshot.as_of_date, snapshot.price_basis_date) for snapshot in snapshots
    )
    duplicate_observation_count = sum(
        count for count in observation_key_counts.values() if count > 1
    )
    if duplicate_observation_count:
        excluded_reasons["duplicate_snapshot_observation"] += duplicate_observation_count
    snapshots_by_id = {
        snapshot.snapshot_id: snapshot
        for snapshot in eligible
        if snapshot_id_counts[snapshot.snapshot_id] == 1
        and observation_key_counts[
            (snapshot.ticker, snapshot.as_of_date, snapshot.price_basis_date)
        ]
        == 1
    }
    outcomes_by_snapshot: dict[str, list[ValuationCalibrationOutcome]] = defaultdict(list)
    for outcome in outcomes:
        outcomes_by_snapshot[outcome.snapshot_id].append(outcome)

    valid_pairs: list[tuple[ValuationCalibrationSnapshot, ValuationCalibrationOutcome]] = []
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
        eligible_snapshot_count=len(snapshots_by_id),
        valid_matured_outcome_count=len(valid_pairs),
        effective_sample_count=effective_sample_count,
        unique_issuer_count=unique_issuers,
        sector_count=len(sectors),
        capture_mode_counts=dict(
            sorted(Counter(snapshot.capture_mode for snapshot in snapshots).items())
        ),
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
            "- Capture modes: `" + json.dumps(readiness.capture_mode_counts, sort_keys=True) + "`",
            f"- Live activation allowed: `{str(readiness.live_activation_allowed).lower()}`",
            "",
            "## Readiness blockers",
            "",
            *[f"- `{reason}`" for reason in reasons],
            "",
            "## Policy",
            "",
            *[f"- `{key}`: `{value}`" for key, value in readiness.policy.items()],
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
        manifest_payload = (
            json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        )
        manifest_hash = file_sha256(manifest_path) if manifest_path.exists() else None
        metrics_hash = "sha256:" + hashlib.sha256(metrics_bytes).hexdigest()
        saved_snapshot_path = metrics_path.parent.parent / "valuation_calibration_snapshot.json"
        if saved_snapshot_path.exists():
            snapshot = ValuationCalibrationSnapshot(
                **json.loads(saved_snapshot_path.read_text(encoding="utf-8"))
            )
            expected = build_valuation_calibration_snapshot(
                metrics,
                metrics_packet_sha256=metrics_hash,
                authority_manifest_sha256=manifest_hash,
                authority_analysis_allowed=(manifest_payload.get("analysis_allowed") is True),
            )
            if snapshot.model_dump(mode="json") != expected.model_dump(mode="json"):
                raise ValueError(
                    "saved valuation calibration snapshot does not match its "
                    f"authority bundle: {saved_snapshot_path}"
                )
            snapshot = snapshot.model_copy(
                update={
                    "sector": (sectors or {}).get(metrics.ticker),
                    "sector_source_sha256": sector_source_sha256,
                }
            )
        else:
            snapshot = build_valuation_calibration_snapshot(
                metrics,
                metrics_packet_sha256=metrics_hash,
                authority_manifest_sha256=manifest_hash,
                authority_analysis_allowed=(manifest_payload.get("analysis_allowed") is True),
                sector=(sectors or {}).get(metrics.ticker),
                sector_source_sha256=sector_source_sha256,
            )
        snapshots.append(snapshot)
    return snapshots


def save_valuation_calibration_snapshot(
    snapshot: ValuationCalibrationSnapshot,
    path: Union[str, Path],
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    _write_json(target, snapshot.model_dump(mode="json"))
    return target


def load_retrospective_replay_snapshots(
    replay_root: Optional[Union[str, Path]],
) -> list[ValuationCalibrationSnapshot]:
    if replay_root is None:
        return []
    from research_agent.calibration.retrospective_replay import (
        promote_retrospective_snapshot,
    )

    root = Path(replay_root)
    if not root.exists():
        raise FileNotFoundError(f"retrospective replay root does not exist: {root}")
    snapshots: list[ValuationCalibrationSnapshot] = []
    for saved_path in sorted(root.glob("**/valuation_calibration_replay_snapshot.json")):
        manifest_path = next(
            (
                parent / "retrospective_replay_manifest.json"
                for parent in saved_path.parents
                if (parent / "retrospective_replay_manifest.json").is_file()
            ),
            None,
        )
        if manifest_path is None:
            raise ValueError(f"replay snapshot has no manifest: {saved_path}")
        manifest = ValuationCalibrationReplayManifest(
            **json.loads(manifest_path.read_text(encoding="utf-8"))
        )
        base_binding = manifest.artifacts.get("base_valuation_snapshot")
        if base_binding is None:
            raise ValueError(f"replay manifest has no base snapshot: {manifest_path}")
        base_path = manifest_path.parent / base_binding.path
        base_snapshot = ValuationCalibrationSnapshot(
            **json.loads(base_path.read_text(encoding="utf-8"))
        )
        expected = promote_retrospective_snapshot(base_snapshot, manifest_path)
        saved = ValuationCalibrationSnapshot(**json.loads(saved_path.read_text(encoding="utf-8")))
        if saved.model_dump(mode="json") != expected.model_dump(mode="json"):
            raise ValueError(
                f"saved retrospective replay snapshot does not match evidence: {saved_path}"
            )
        snapshots.append(saved)
    return snapshots


def file_sha256(path: Union[str, Path]) -> str:
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return "sha256:" + digest


def build_valuation_calibration_outcome(
    snapshot: ValuationCalibrationSnapshot,
    source_bundle: ValuationCalibrationSourceBundle,
) -> ValuationCalibrationOutcome:
    source_hash = calculate_source_bundle_sha256(source_bundle)
    source_reasons = _source_bundle_invalid_reasons(snapshot, source_bundle)
    try:
        normalized_instrument = _price_map(source_bundle.instrument_prices)
        normalized_benchmark = _price_map(source_bundle.benchmark_prices)
    except ValueError as error:
        normalized_instrument = {}
        normalized_benchmark = {}
        source_reasons.append(str(error))
    basis_date = snapshot.price_basis_date
    future_common_dates = sorted(
        day
        for day in set(normalized_instrument).intersection(normalized_benchmark)
        if day > basis_date
    )
    instrument_basis_price = normalized_instrument.get(basis_date)
    benchmark_basis_price = normalized_benchmark.get(basis_date)
    base = {
        "snapshot_id": snapshot.snapshot_id,
        "horizon_trading_days": VALUATION_CALIBRATION_HORIZON_TRADING_DAYS,
        "trading_observation_count": min(
            len(future_common_dates), VALUATION_CALIBRATION_HORIZON_TRADING_DAYS
        ),
        "benchmark": source_bundle.benchmark,
        "basis_date": basis_date,
        "instrument_basis_price": instrument_basis_price,
        "benchmark_basis_price": benchmark_basis_price,
        "first_observation_date": (future_common_dates[0] if future_common_dates else None),
        "observed_through": (
            future_common_dates[VALUATION_CALIBRATION_HORIZON_TRADING_DAYS - 1]
            if len(future_common_dates) >= VALUATION_CALIBRATION_HORIZON_TRADING_DAYS
            else future_common_dates[-1]
            if future_common_dates
            else None
        ),
        "instrument_price_series_basis": source_bundle.instrument_price_series_basis,
        "benchmark_price_series_basis": source_bundle.benchmark_price_series_basis,
        "source_hash": source_hash,
    }
    if source_reasons:
        return ValuationCalibrationOutcome(
            **base,
            status="invalidated",
            notes=sorted(set(source_reasons)),
        )
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
    if len(future_common_dates) < VALUATION_CALIBRATION_HORIZON_TRADING_DAYS:
        return ValuationCalibrationOutcome(
            **base,
            status="pending",
            notes=[
                "needs_252_common_future_trading_observations",
            ],
        )

    end_date = future_common_dates[VALUATION_CALIBRATION_HORIZON_TRADING_DAYS - 1]
    outcome_dates = future_common_dates[:VALUATION_CALIBRATION_HORIZON_TRADING_DAYS]
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
        instrument_max_drawdown=_max_drawdown(
            instrument_basis_price,
            [normalized_instrument[day] for day in outcome_dates],
        ),
        benchmark_max_drawdown=_max_drawdown(
            benchmark_basis_price,
            [normalized_benchmark[day] for day in outcome_dates],
        ),
    )


def calculate_source_bundle_sha256(
    source_bundle: ValuationCalibrationSourceBundle,
) -> str:
    payload = source_bundle.model_dump(mode="json")
    payload.pop("source_bundle_sha256", None)
    for field in (
        "instrument_provider_receipt_sha256",
        "instrument_provider_receipt_path",
        "benchmark_provider_receipt_sha256",
        "benchmark_provider_receipt_path",
    ):
        if payload.get(field) is None:
            payload.pop(field, None)
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def load_valuation_source_bundles(
    path: Optional[Union[str, Path]],
) -> list[ValuationCalibrationSourceBundle]:
    if path is None:
        return []
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(f"valuation calibration source root does not exist: {target}")
    if not target.is_dir():
        raise NotADirectoryError(f"valuation calibration source root is not a directory: {target}")
    bundles: list[ValuationCalibrationSourceBundle] = []
    for bundle_path in sorted(target.glob("**/valuation_calibration_source_bundle.json")):
        bundle = ValuationCalibrationSourceBundle(
            **json.loads(bundle_path.read_text(encoding="utf-8"))
        )
        integrity_reasons: list[str] = []
        if bundle.schema_id != VALUATION_SOURCE_BUNDLE_SCHEMA:
            integrity_reasons.append("source_bundle_schema_invalid")
        if not _is_sha256(bundle.source_bundle_sha256):
            integrity_reasons.append("source_bundle_hash_invalid")
        elif bundle.source_bundle_sha256 != calculate_source_bundle_sha256(bundle):
            integrity_reasons.append("source_bundle_hash_mismatch")
        integrity_reasons.extend(source_bundle_artifact_invalid_reasons(bundle, bundle_path))
        if integrity_reasons:
            raise ValueError(
                f"valuation source bundle invalid: {bundle_path}: "
                + ", ".join(sorted(set(integrity_reasons)))
            )
        bundles.append(bundle)
    if not bundles:
        raise ValueError(f"valuation calibration source root contains no bundles: {target}")
    return bundles


def build_valuation_calibration_outcomes(
    snapshots: list[ValuationCalibrationSnapshot],
    source_bundles: list[ValuationCalibrationSourceBundle],
) -> list[ValuationCalibrationOutcome]:
    snapshots_by_id = {snapshot.snapshot_id: snapshot for snapshot in snapshots}
    outcomes: list[ValuationCalibrationOutcome] = []
    for source_bundle in source_bundles:
        snapshot = snapshots_by_id.get(source_bundle.snapshot_id)
        if snapshot is None:
            outcomes.append(
                ValuationCalibrationOutcome(
                    snapshot_id=source_bundle.snapshot_id,
                    status="invalidated",
                    benchmark=source_bundle.benchmark,
                    basis_date=source_bundle.basis_date,
                    instrument_price_series_basis=(source_bundle.instrument_price_series_basis),
                    benchmark_price_series_basis=(source_bundle.benchmark_price_series_basis),
                    source_hash=calculate_source_bundle_sha256(source_bundle),
                    notes=["source_bundle_snapshot_missing"],
                )
            )
            continue
        outcomes.append(build_valuation_calibration_outcome(snapshot, source_bundle))
    return outcomes


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build fail-closed Room16 valuation calibration readiness evidence."
    )
    parser.add_argument("--authority-root", required=True)
    parser.add_argument(
        "--outcome-source-root",
        help=(
            "Optional directory containing evidence-bound total-return source "
            "bundles. Free-form outcome JSONL is not accepted."
        ),
    )
    parser.add_argument("--sectors-json")
    parser.add_argument(
        "--retrospective-replay-root",
        help="Optional root containing verified historical point-in-time replay snapshots.",
    )
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
    snapshots.extend(load_retrospective_replay_snapshots(args.retrospective_replay_root))
    source_bundles = load_valuation_source_bundles(args.outcome_source_root)
    outcomes = build_valuation_calibration_outcomes(snapshots, source_bundles)
    readiness = assess_valuation_calibration_readiness(snapshots, outcomes)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        output_dir / "valuation_calibration_snapshots.json",
        [snapshot.model_dump(mode="json") for snapshot in snapshots],
    )
    _write_json(
        output_dir / "valuation_calibration_outcomes.json",
        [outcome.model_dump(mode="json") for outcome in outcomes],
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
    if outcome.calc_version != VALUATION_OUTCOME_CALC_VERSION:
        reasons.append("outcome_calc_version_invalid")
    if outcome.basis_date != snapshot.price_basis_date:
        reasons.append("outcome_basis_date_mismatch")
    if outcome.instrument_basis_price is None or outcome.instrument_basis_price <= 0:
        reasons.append("outcome_instrument_basis_price_invalid")
    if outcome.benchmark_basis_price is None or outcome.benchmark_basis_price <= 0:
        reasons.append("outcome_benchmark_basis_price_invalid")
    if outcome.first_observation_date is None:
        reasons.append("outcome_first_observation_date_missing")
    else:
        try:
            if date.fromisoformat(outcome.first_observation_date) <= date.fromisoformat(
                snapshot.price_basis_date
            ):
                reasons.append("outcome_first_observation_date_invalid")
        except ValueError:
            reasons.append("outcome_first_observation_date_invalid")
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
    elif not all(math.isfinite(float(value)) for value in returns):
        reasons.append("outcome_return_not_finite")
    elif (
        abs(
            float(outcome.instrument_return)
            - float(outcome.benchmark_return)
            - float(outcome.excess_return)
        )
        > 1e-9
    ):
        reasons.append("outcome_excess_return_mismatch")
    for label, value in (
        ("instrument", outcome.instrument_max_drawdown),
        ("benchmark", outcome.benchmark_max_drawdown),
    ):
        if value is None or not math.isfinite(float(value)) or not -1 <= float(value) <= 0:
            reasons.append(f"outcome_{label}_max_drawdown_invalid")
    return reasons


def outcome_invalid_reasons(
    snapshot: ValuationCalibrationSnapshot,
    outcome: ValuationCalibrationOutcome,
) -> list[str]:
    """Expose the canonical matured-outcome validator to P6 diagnostics."""

    return sorted(set(_outcome_invalid_reasons(snapshot, outcome)))


def _source_bundle_invalid_reasons(
    snapshot: ValuationCalibrationSnapshot,
    source_bundle: ValuationCalibrationSourceBundle,
) -> list[str]:
    reasons: list[str] = []
    if source_bundle.schema_id != VALUATION_SOURCE_BUNDLE_SCHEMA:
        reasons.append("source_bundle_schema_invalid")
    if source_bundle.snapshot_id != snapshot.snapshot_id:
        reasons.append("source_bundle_snapshot_mismatch")
    if source_bundle.instrument.strip().upper() != snapshot.ticker.strip().upper():
        reasons.append("source_bundle_instrument_mismatch")
    if not source_bundle.benchmark.strip():
        reasons.append("source_bundle_benchmark_missing")
    if not source_bundle.provider_id.strip():
        reasons.append("source_bundle_provider_missing")
    if not source_bundle.provider_dataset_id.strip():
        reasons.append("source_bundle_dataset_missing")
    if source_bundle.usage_rights_status != "internal_calibration_allowed":
        reasons.append("source_bundle_usage_rights_not_approved")
    rights_approved_at = _parse_aware_timestamp(source_bundle.usage_rights_approved_at)
    if not str(source_bundle.usage_rights_approved_by or "").strip():
        reasons.append("source_bundle_usage_rights_approver_missing")
    elif _appears_automation_identity(source_bundle.usage_rights_approved_by):
        reasons.append("source_bundle_usage_rights_approver_not_human")
    if rights_approved_at is None:
        reasons.append("source_bundle_usage_rights_approved_at_invalid")
    if source_bundle.basis_date != snapshot.price_basis_date:
        reasons.append("source_bundle_basis_date_mismatch")
    else:
        try:
            date.fromisoformat(source_bundle.basis_date)
        except ValueError:
            reasons.append("source_bundle_basis_date_invalid")
    if source_bundle.instrument_price_series_basis != "total_return_adjusted":
        reasons.append("instrument_total_return_adjustment_not_verified")
    if source_bundle.benchmark_price_series_basis != "total_return_adjusted":
        reasons.append("benchmark_total_return_adjustment_not_verified")
    if not source_bundle.instrument_cash_distributions_included:
        reasons.append("instrument_cash_distributions_not_verified")
    if not source_bundle.benchmark_cash_distributions_included:
        reasons.append("benchmark_cash_distributions_not_verified")
    if not source_bundle.instrument_corporate_actions_included:
        reasons.append("instrument_corporate_actions_not_verified")
    if not source_bundle.benchmark_corporate_actions_included:
        reasons.append("benchmark_corporate_actions_not_verified")
    required_hashes = {
        "provider_methodology_hash_invalid": (source_bundle.provider_methodology_sha256),
        "usage_rights_evidence_hash_invalid": (source_bundle.usage_rights_evidence_sha256),
        "instrument_source_hash_invalid": source_bundle.instrument_source_sha256,
        "benchmark_source_hash_invalid": source_bundle.benchmark_source_sha256,
        "verification_evidence_hash_invalid": (source_bundle.verification_evidence_sha256),
    }
    if source_bundle.verification_status == "human_verified":
        required_hashes.update(
            {
                "instrument_provider_receipt_hash_invalid": (
                    source_bundle.instrument_provider_receipt_sha256
                ),
                "benchmark_provider_receipt_hash_invalid": (
                    source_bundle.benchmark_provider_receipt_sha256
                ),
            }
        )
    reasons.extend(reason for reason, value in required_hashes.items() if not _is_sha256(value))
    required_paths = {
        "provider_methodology_artifact_path_invalid": source_bundle.provider_methodology_path,
        "usage_rights_evidence_artifact_path_invalid": (source_bundle.usage_rights_evidence_path),
        "instrument_source_artifact_path_invalid": source_bundle.instrument_source_path,
        "benchmark_source_artifact_path_invalid": source_bundle.benchmark_source_path,
        "verification_evidence_artifact_path_invalid": (source_bundle.verification_evidence_path),
    }
    if source_bundle.verification_status == "human_verified":
        required_paths.update(
            {
                "instrument_provider_receipt_artifact_path_invalid": (
                    source_bundle.instrument_provider_receipt_path
                ),
                "benchmark_provider_receipt_artifact_path_invalid": (
                    source_bundle.benchmark_provider_receipt_path
                ),
            }
        )
    reasons.extend(
        reason
        for reason, value in required_paths.items()
        if not _is_safe_relative_artifact_path(value)
    )
    if source_bundle.verification_evidence_path and source_bundle.verification_evidence_path in {
        source_bundle.provider_methodology_path,
        source_bundle.usage_rights_evidence_path,
    }:
        reasons.append("source_bundle_verification_evidence_not_separate")
    retrieved_at = _parse_aware_timestamp(source_bundle.retrieved_at)
    bundle_created_at = _parse_aware_timestamp(source_bundle.bundle_created_at)
    if bundle_created_at is None:
        reasons.append("source_bundle_created_at_invalid")
    if retrieved_at is None:
        reasons.append("source_bundle_retrieved_at_invalid")
    else:
        if bundle_created_at is not None and retrieved_at > bundle_created_at:
            reasons.append("source_bundle_retrieved_after_bundle_creation")
        try:
            if retrieved_at.date() < date.fromisoformat(snapshot.price_basis_date):
                reasons.append("source_bundle_retrieved_before_basis_date")
        except ValueError:
            reasons.append("source_bundle_basis_date_invalid")
        observation_dates: list[date] = []
        for point in [
            *source_bundle.instrument_prices,
            *source_bundle.benchmark_prices,
        ]:
            try:
                observation_dates.append(date.fromisoformat(point.date))
            except ValueError:
                reasons.append("source_bundle_observation_date_invalid")
        if observation_dates and max(observation_dates) > retrieved_at.date():
            reasons.append("source_bundle_observation_after_retrieval")
    verified_at = _parse_aware_timestamp(source_bundle.verified_at)
    if source_bundle.verification_status != "human_verified":
        reasons.append("source_bundle_human_verification_missing")
    if not str(source_bundle.prepared_by or "").strip():
        reasons.append("source_bundle_prepared_by_missing")
    if not str(source_bundle.verified_by or "").strip():
        reasons.append("source_bundle_verified_by_missing")
    elif _appears_automation_identity(source_bundle.verified_by):
        reasons.append("source_bundle_verified_by_not_human")
    if not source_bundle.verification_independent_from_preparation:
        reasons.append("source_bundle_independent_verification_missing")
    elif _same_identity(source_bundle.prepared_by, source_bundle.verified_by):
        reasons.append("source_bundle_reviewer_matches_preparer")
    if verified_at is None:
        reasons.append("source_bundle_verified_at_invalid")
    elif retrieved_at is not None and verified_at < retrieved_at:
        reasons.append("source_bundle_verified_before_retrieval")
    elif rights_approved_at is not None and verified_at < rights_approved_at:
        reasons.append("source_bundle_verified_before_rights_approval")
    if rights_approved_at is not None and bundle_created_at is not None:
        if rights_approved_at > bundle_created_at:
            reasons.append("source_bundle_rights_approved_after_bundle_creation")
    if verified_at is not None and bundle_created_at is not None:
        if verified_at > bundle_created_at:
            reasons.append("source_bundle_verified_after_bundle_creation")
    if not _is_sha256(source_bundle.source_bundle_sha256):
        reasons.append("source_bundle_hash_invalid")
    elif source_bundle.source_bundle_sha256 != calculate_source_bundle_sha256(source_bundle):
        reasons.append("source_bundle_hash_mismatch")
    return reasons


def source_bundle_invalid_reasons(
    snapshot: ValuationCalibrationSnapshot,
    source_bundle: ValuationCalibrationSourceBundle,
    bundle_path: Optional[Union[str, Path]] = None,
) -> list[str]:
    """Return the canonical fail-closed source reasons for operator workbenches."""

    reasons = _source_bundle_invalid_reasons(snapshot, source_bundle)
    if bundle_path is not None:
        reasons.extend(source_bundle_artifact_invalid_reasons(source_bundle, bundle_path))
    return sorted(set(reasons))


def source_bundle_artifact_invalid_reasons(
    source_bundle: ValuationCalibrationSourceBundle,
    bundle_path: Union[str, Path],
) -> list[str]:
    """Verify that every hash-bound source artifact is present beside the bundle."""

    root = Path(bundle_path).resolve().parent
    artifacts = {
        "provider_methodology": (
            source_bundle.provider_methodology_path,
            source_bundle.provider_methodology_sha256,
        ),
        "usage_rights_evidence": (
            source_bundle.usage_rights_evidence_path,
            source_bundle.usage_rights_evidence_sha256,
        ),
        "instrument_source": (
            source_bundle.instrument_source_path,
            source_bundle.instrument_source_sha256,
        ),
        "benchmark_source": (
            source_bundle.benchmark_source_path,
            source_bundle.benchmark_source_sha256,
        ),
        "verification_evidence": (
            source_bundle.verification_evidence_path,
            source_bundle.verification_evidence_sha256,
        ),
    }
    receipt_artifacts = {
        "instrument_provider_receipt": (
            source_bundle.instrument_provider_receipt_path,
            source_bundle.instrument_provider_receipt_sha256,
        ),
        "benchmark_provider_receipt": (
            source_bundle.benchmark_provider_receipt_path,
            source_bundle.benchmark_provider_receipt_sha256,
        ),
    }
    for label, artifact in receipt_artifacts.items():
        if (
            source_bundle.verification_status == "human_verified"
            or artifact[0] is not None
            or artifact[1] is not None
        ):
            artifacts[label] = artifact
    reasons: list[str] = []
    for label, (relative_path, expected_hash) in artifacts.items():
        if not _is_safe_relative_artifact_path(relative_path):
            reasons.append(f"{label}_artifact_path_invalid")
            continue
        artifact_path = (root / str(relative_path)).resolve()
        try:
            artifact_path.relative_to(root)
        except ValueError:
            reasons.append(f"{label}_artifact_path_invalid")
            continue
        if not artifact_path.is_file():
            reasons.append(f"{label}_artifact_missing")
            continue
        if not _is_sha256(expected_hash) or file_sha256(artifact_path) != expected_hash:
            reasons.append(f"{label}_artifact_hash_mismatch")
    reasons.extend(_provider_receipt_contract_invalid_reasons(source_bundle, root))
    return sorted(set(reasons))


def _provider_receipt_contract_invalid_reasons(
    source_bundle: ValuationCalibrationSourceBundle,
    root: Path,
) -> list[str]:
    specs = {
        "instrument": (
            source_bundle.instrument_provider_receipt_path,
            source_bundle.instrument_source_path,
            source_bundle.instrument,
            source_bundle.instrument_price_series_basis,
            source_bundle.instrument_cash_distributions_included,
            source_bundle.instrument_corporate_actions_included,
        ),
        "benchmark": (
            source_bundle.benchmark_provider_receipt_path,
            source_bundle.benchmark_source_path,
            source_bundle.benchmark,
            source_bundle.benchmark_price_series_basis,
            source_bundle.benchmark_cash_distributions_included,
            source_bundle.benchmark_corporate_actions_included,
        ),
    }
    reasons: list[str] = []
    loaded: dict[str, ProviderPriceCandidateReceipt] = {}
    for label, (
        receipt_relative,
        series_relative,
        expected_ticker,
        expected_basis,
        expected_distributions,
        expected_corporate_actions,
    ) in specs.items():
        if receipt_relative is None and source_bundle.verification_status != "human_verified":
            continue
        if not _is_safe_relative_artifact_path(
            receipt_relative
        ) or not _is_safe_relative_artifact_path(series_relative):
            continue
        receipt_path = (root / str(receipt_relative)).resolve()
        series_path = (root / str(series_relative)).resolve()
        try:
            receipt = load_provider_price_candidate(
                receipt_path,
                expected_series_path=series_path,
            )
        except (OSError, ValueError):
            reasons.append(f"{label}_provider_receipt_contract_invalid")
            continue
        loaded[label] = receipt
        if receipt.provider_id != source_bundle.provider_id:
            reasons.append(f"{label}_provider_receipt_provider_mismatch")
        if receipt.provider_dataset_id != source_bundle.provider_dataset_id:
            reasons.append(f"{label}_provider_receipt_dataset_mismatch")
        if receipt.ticker.strip().upper() != expected_ticker.strip().upper():
            reasons.append(f"{label}_provider_receipt_ticker_mismatch")
        if receipt.series_basis != expected_basis:
            reasons.append(f"{label}_provider_receipt_series_basis_mismatch")
        if receipt.cash_distributions_included is not expected_distributions:
            reasons.append(f"{label}_provider_receipt_distribution_claim_mismatch")
        if receipt.corporate_actions_included is not expected_corporate_actions:
            reasons.append(f"{label}_provider_receipt_corporate_action_claim_mismatch")
        try:
            basis_date = date.fromisoformat(source_bundle.basis_date)
            if not (
                date.fromisoformat(receipt.first_date)
                <= basis_date
                < date.fromisoformat(receipt.last_date)
            ):
                reasons.append(f"{label}_provider_receipt_basis_coverage_invalid")
        except ValueError:
            reasons.append(f"{label}_provider_receipt_basis_coverage_invalid")

    if set(loaded) == {"instrument", "benchmark"}:
        instrument_receipt = loaded["instrument"]
        benchmark_receipt = loaded["benchmark"]
        latest_receipt = max(
            _parse_aware_timestamp(instrument_receipt.created_at),
            _parse_aware_timestamp(benchmark_receipt.created_at),
        )
        if latest_receipt != _parse_aware_timestamp(source_bundle.retrieved_at):
            reasons.append("source_bundle_provider_receipt_retrieved_at_mismatch")
        provenance_fields = (
            "source_url",
            "methodology_url",
            "license_url",
            "pricing_url",
        )
        if any(
            getattr(instrument_receipt, field) != getattr(benchmark_receipt, field)
            for field in provenance_fields
        ):
            reasons.append("source_bundle_provider_receipt_provenance_mismatch")
    return reasons


def _is_safe_relative_artifact_path(value: Optional[str]) -> bool:
    if not str(value or "").strip():
        return False
    path = Path(str(value))
    return not path.is_absolute() and ".." not in path.parts and path != Path(".")


def _appears_automation_identity(value: Optional[str]) -> bool:
    return bool(AUTOMATION_IDENTITY_PATTERN.search(str(value or "").strip()))


def _same_identity(left: Optional[str], right: Optional[str]) -> bool:
    normalized_left = _normalized_identity(left)
    normalized_right = _normalized_identity(right)
    return bool(normalized_left and normalized_left == normalized_right)


def _normalized_identity(value: Optional[str]) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value or "").casefold())
    return re.sub(r"[^a-z0-9]+", "", decomposed.encode("ascii", "ignore").decode())


def _is_sha256(value: Optional[str]) -> bool:
    if value is None:
        return False
    normalized = value.removeprefix("sha256:")
    return len(normalized) == 64 and all(
        character in "0123456789abcdef" for character in normalized.lower()
    )


def _parse_aware_timestamp(value: Optional[str]) -> Optional[datetime]:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _price_map(
    prices: list[ValuationCalibrationPricePoint],
) -> dict[str, float]:
    normalized: dict[str, float] = {}
    for point in prices:
        try:
            point_date = date.fromisoformat(point.date)
        except ValueError as error:
            raise ValueError("invalid_price_observation_date") from error
        if not math.isfinite(point.close) or point.close <= 0:
            raise ValueError("nonpositive_or_nonfinite_price_observation")
        key = point_date.isoformat()
        close = float(point.close)
        if key in normalized and normalized[key] != close:
            raise ValueError("conflicting_duplicate_price_observation")
        normalized[key] = close
    return normalized


def _max_drawdown(basis_price: float, future_prices: list[float]) -> float:
    peak = float(basis_price)
    maximum_drawdown = 0.0
    for value in future_prices:
        price = float(value)
        peak = max(peak, price)
        maximum_drawdown = min(maximum_drawdown, price / peak - 1)
    return round(maximum_drawdown, 12)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
