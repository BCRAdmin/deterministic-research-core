from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
from collections import defaultdict
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from research_agent.calibration.valuation_calibration import (
    MIN_EFFECTIVE_SAMPLES,
    MIN_SECTORS,
    MIN_UNIQUE_ISSUERS,
    ValuationCalibrationOutcome,
    ValuationCalibrationReadiness,
    ValuationCalibrationSnapshot,
    outcome_invalid_reasons,
)


CONTRACT_ID = "room16.calibration_stability_review@1"
MIN_STRATUM_SAMPLES = 5
_HUMAN_BLOCKLIST = re.compile(
    r"^(?:ai|agent|automation|bot|chatgpt|claude|codex|deepseek|gemini|llm|"
    r"model|openai|room\s*16|system|vega|vivi)(?:\b|[-_])",
    re.IGNORECASE,
)


class CalibrationClassification(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    snapshot_id: str
    market_phase: Literal["bull", "bear", "sideways", "stressed"]
    valuation_regime: Literal["discount", "neutral", "premium"]


class CalibrationClassificationOverlay(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    contract_id: Literal["room16.calibration_classification_overlay@1"] = (
        "room16.calibration_classification_overlay@1"
    )
    source_sha256: str
    methodology_evidence_sha256: str
    verification_evidence_sha256: str
    verified_by: str
    independently_verified: Literal[True]
    classifications: list[CalibrationClassification] = Field(min_length=1)
    overlay_sha256: str

    @field_validator(
        "source_sha256",
        "methodology_evidence_sha256",
        "verification_evidence_sha256",
    )
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not _is_sha256(value):
            raise ValueError("classification overlay hash is invalid")
        return value

    @field_validator("verified_by")
    @classmethod
    def validate_human_reviewer(cls, value: str) -> str:
        identity = value.strip()
        if not identity or _HUMAN_BLOCKLIST.search(identity):
            raise ValueError("classification overlay requires an identified human reviewer")
        return identity

    @model_validator(mode="after")
    def validate_overlay_binding(self) -> "CalibrationClassificationOverlay":
        if self.overlay_sha256 != calculate_classification_overlay_sha256(self):
            raise ValueError("classification overlay hash binding is invalid")
        return self


class StabilityStratum(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    dimension: Literal["sector", "market_phase", "valuation_regime"]
    value: str
    sample_count: int
    mean_excess_return: float
    median_excess_return: float
    positive_excess_rate: float
    worst_instrument_drawdown: float
    minimum_sample_met: bool


class CalibrationStabilityReview(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    contract_id: Literal["room16.calibration_stability_review@1"] = CONTRACT_ID
    status: Literal["not_ready", "human_review_required"]
    valid_observation_count: int
    unique_issuer_count: int
    sector_count: int
    market_phase_count: int
    valuation_regime_count: int
    directional_false_pass_count: int
    directional_false_pass_rate: Optional[float]
    directional_false_block_count: int
    directional_false_block_rate: Optional[float]
    early_mean_excess_return: Optional[float]
    late_mean_excess_return: Optional[float]
    mean_excess_drift: Optional[float]
    strata: list[StabilityStratum]
    blockers: list[str]
    definitions: dict[str, str]
    automatic_actions: dict[str, Literal[False]]
    live_activation_allowed: Literal[False] = False
    report_sha256: str


def assess_calibration_stability(
    snapshots: list[ValuationCalibrationSnapshot],
    outcomes: list[ValuationCalibrationOutcome],
    readiness: ValuationCalibrationReadiness,
    overlay: Optional[CalibrationClassificationOverlay],
) -> CalibrationStabilityReview:
    snapshots_by_id = {snapshot.snapshot_id: snapshot for snapshot in snapshots}
    outcomes_by_id = {outcome.snapshot_id: outcome for outcome in outcomes}
    classifications: dict[str, CalibrationClassification] = {}
    blockers: list[str] = []
    if overlay is None:
        blockers.append("classification_overlay_missing")
    else:
        for item in overlay.classifications:
            if item.snapshot_id in classifications:
                blockers.append("classification_overlay_duplicate_snapshot")
            classifications[item.snapshot_id] = item

    rows: list[tuple[ValuationCalibrationSnapshot, ValuationCalibrationOutcome, CalibrationClassification]] = []
    for snapshot_id, snapshot in snapshots_by_id.items():
        outcome = outcomes_by_id.get(snapshot_id)
        classification = classifications.get(snapshot_id)
        if not snapshot.eligible or outcome is None or outcome_invalid_reasons(snapshot, outcome):
            continue
        if classification is None:
            blockers.append("classification_missing_for_valid_outcome")
            continue
        rows.append((snapshot, outcome, classification))
    orphan_classifications = set(classifications) - set(snapshots_by_id)
    if orphan_classifications:
        blockers.append("classification_snapshot_missing")
    if readiness.status != "shadow_ready":
        blockers.append("valuation_calibration_not_shadow_ready")
    if len(rows) < MIN_EFFECTIVE_SAMPLES:
        blockers.append("stability_minimum_effective_sample_count_not_met")
    issuers = {snapshot.ticker for snapshot, _, _ in rows}
    sectors = {snapshot.sector for snapshot, _, _ in rows if snapshot.sector}
    phases = {classification.market_phase for _, _, classification in rows}
    regimes = {classification.valuation_regime for _, _, classification in rows}
    if len(issuers) < MIN_UNIQUE_ISSUERS:
        blockers.append("stability_minimum_unique_issuer_count_not_met")
    if len(sectors) < MIN_SECTORS:
        blockers.append("stability_minimum_sector_count_not_met")
    if len(phases) < 2:
        blockers.append("stability_market_phase_coverage_not_met")
    if len(regimes) < 2:
        blockers.append("stability_valuation_regime_coverage_not_met")

    strata = _build_strata(rows)
    for dimension in ("sector", "market_phase", "valuation_regime"):
        if any(
            item.dimension == dimension and not item.minimum_sample_met
            for item in strata
        ):
            blockers.append(f"stability_{dimension}_stratum_too_small")
    favorable = [row for row in rows if float(row[0].base_upside or 0) > 0]
    blocked = [row for row in rows if float(row[0].base_upside or 0) <= 0]
    false_pass = sum(float(row[1].excess_return or 0) <= 0 for row in favorable)
    false_block = sum(float(row[1].excess_return or 0) > 0 for row in blocked)
    ordered = sorted(rows, key=lambda row: (row[0].as_of_date, row[0].ticker, row[0].snapshot_id))
    early_mean = None
    late_mean = None
    drift = None
    if len(ordered) >= 20:
        midpoint = len(ordered) // 2
        early_mean = _mean_excess(ordered[:midpoint])
        late_mean = _mean_excess(ordered[midpoint:])
        drift = round(late_mean - early_mean, 12)
    else:
        blockers.append("calibration_drift_sample_too_small")
    blockers = sorted(set(blockers))
    payload: dict[str, Any] = {
        "contract_id": CONTRACT_ID,
        "status": "not_ready" if blockers else "human_review_required",
        "valid_observation_count": len(rows),
        "unique_issuer_count": len(issuers),
        "sector_count": len(sectors),
        "market_phase_count": len(phases),
        "valuation_regime_count": len(regimes),
        "directional_false_pass_count": false_pass,
        "directional_false_pass_rate": _rate(false_pass, len(favorable)),
        "directional_false_block_count": false_block,
        "directional_false_block_rate": _rate(false_block, len(blocked)),
        "early_mean_excess_return": early_mean,
        "late_mean_excess_return": late_mean,
        "mean_excess_drift": drift,
        "strata": [item.model_dump(mode="json") for item in strata],
        "blockers": blockers,
        "definitions": {
            "directional_false_pass": (
                "DCF base upside was positive, but the verified 252-day excess return was not."
            ),
            "directional_false_block": (
                "DCF base upside was non-positive, but the verified 252-day excess return was positive."
            ),
            "mean_excess_drift": (
                "Late-half mean verified excess return minus early-half mean; interpretation is human-only."
            ),
        },
        "automatic_actions": {
            "ratingChange": False,
            "weightChange": False,
            "methodChange": False,
            "modelRun": False,
            "reportPublish": False,
        },
        "live_activation_allowed": False,
    }
    payload["report_sha256"] = _payload_sha256(payload)
    return CalibrationStabilityReview.model_validate(payload)


def calculate_classification_overlay_sha256(value: Any) -> str:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)
    payload.pop("overlay_sha256", None)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def calculate_stability_review_sha256(value: Any) -> str:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)
    return _payload_sha256(payload)


def _build_strata(
    rows: list[tuple[ValuationCalibrationSnapshot, ValuationCalibrationOutcome, CalibrationClassification]],
) -> list[StabilityStratum]:
    grouped: dict[tuple[str, str], list[tuple[ValuationCalibrationSnapshot, ValuationCalibrationOutcome, CalibrationClassification]]] = defaultdict(list)
    for row in rows:
        snapshot, _, classification = row
        grouped[("sector", snapshot.sector or "unclassified")].append(row)
        grouped[("market_phase", classification.market_phase)].append(row)
        grouped[("valuation_regime", classification.valuation_regime)].append(row)
    strata = []
    for (dimension, value), items in sorted(grouped.items()):
        returns = [float(item[1].excess_return) for item in items]
        drawdowns = [float(item[1].instrument_max_drawdown) for item in items]
        strata.append(
            StabilityStratum(
                dimension=dimension,
                value=value,
                sample_count=len(items),
                mean_excess_return=round(statistics.fmean(returns), 12),
                median_excess_return=round(statistics.median(returns), 12),
                positive_excess_rate=round(sum(value > 0 for value in returns) / len(items), 12),
                worst_instrument_drawdown=round(min(drawdowns), 12),
                minimum_sample_met=len(items) >= MIN_STRATUM_SAMPLES,
            )
        )
    return strata


def _mean_excess(rows: list[tuple[Any, ValuationCalibrationOutcome, Any]]) -> float:
    return round(statistics.fmean(float(row[1].excess_return) for row in rows), 12)


def _rate(count: int, denominator: int) -> Optional[float]:
    return round(count / denominator, 12) if denominator else None


def _payload_sha256(payload: dict[str, Any]) -> str:
    normalized = {key: value for key, value in payload.items() if key != "report_sha256"}
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _is_sha256(value: str) -> bool:
    normalized = str(value or "").removeprefix("sha256:")
    return len(normalized) == 64 and all(character in "0123456789abcdef" for character in normalized)
