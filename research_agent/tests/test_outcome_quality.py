from __future__ import annotations

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from research_agent.calibration.outcome_quality import (
    CalibrationClassificationOverlay,
    assess_calibration_stability,
    calculate_classification_overlay_sha256,
)
from research_agent.calibration.valuation_calibration import (
    ValuationCalibrationOutcome,
    ValuationCalibrationSnapshot,
    assess_valuation_calibration_readiness,
)


HASH = "sha256:" + "a" * 64


def _sample(size: int = 75):
    snapshots = []
    outcomes = []
    classifications = []
    sectors = ["Technology", "Industrials", "Consumer", "Healthcare", "Energy"]
    phases = ["bull", "bear", "sideways"]
    regimes = ["discount", "neutral", "premium"]
    for index in range(size):
        as_of = date(2023, 1, 2) + timedelta(days=index)
        ticker = f"T{index % 25:02d}"
        snapshot_id = "sha256:" + f"{index + 1:064x}"
        base_upside = 0.2 if index % 2 == 0 else -0.1
        excess_return = 0.08 if index % 4 in {0, 1} else -0.05
        snapshots.append(
            ValuationCalibrationSnapshot(
                snapshot_id=snapshot_id,
                ticker=ticker,
                as_of_date=as_of.isoformat(),
                sector=sectors[index % len(sectors)],
                sector_source_sha256=HASH,
                method_id="dcf-v1",
                policy_version="v1",
                sensitivity_status="measured",
                price_series_basis="corporate_action_adjusted",
                price_basis_date=as_of.isoformat(),
                share_basis="listed_share_count",
                current_price=100,
                current_value_position="inside_range",
                reverse_dcf_implied_fcf_growth=0.1,
                bear_upside=-0.2,
                base_upside=base_upside,
                bull_upside=0.4,
                metrics_packet_sha256=HASH,
                authority_manifest_sha256=HASH,
                eligible=True,
            )
        )
        outcomes.append(
            ValuationCalibrationOutcome(
                snapshot_id=snapshot_id,
                status="matured",
                trading_observation_count=252,
                benchmark="BENCH",
                basis_date=as_of.isoformat(),
                instrument_basis_price=100,
                benchmark_basis_price=100,
                first_observation_date=(as_of + timedelta(days=1)).isoformat(),
                observed_through=(as_of + timedelta(days=370)).isoformat(),
                instrument_return=round(0.1 + excess_return, 12),
                benchmark_return=0.1,
                excess_return=excess_return,
                instrument_max_drawdown=-0.2,
                benchmark_max_drawdown=-0.1,
                instrument_price_series_basis="total_return_adjusted",
                benchmark_price_series_basis="total_return_adjusted",
                source_hash=HASH,
            )
        )
        classifications.append(
            {
                "snapshot_id": snapshot_id,
                "market_phase": phases[index % len(phases)],
                "valuation_regime": regimes[(index // len(phases)) % len(regimes)],
            }
        )
    overlay_payload = {
        "contract_id": "room16.calibration_classification_overlay@1",
        "source_sha256": HASH,
        "methodology_evidence_sha256": HASH,
        "verification_evidence_sha256": HASH,
        "verified_by": "Independent Market Reviewer",
        "independently_verified": True,
        "classifications": classifications,
    }
    overlay_payload["overlay_sha256"] = calculate_classification_overlay_sha256(
        overlay_payload
    )
    overlay = CalibrationClassificationOverlay.model_validate(overlay_payload)
    return snapshots, outcomes, overlay


def test_stability_review_requires_real_sample_and_classification_overlay() -> None:
    snapshots, outcomes, _ = _sample(1)
    readiness = assess_valuation_calibration_readiness(snapshots, outcomes)

    report = assess_calibration_stability(snapshots, outcomes, readiness, None)

    assert report.status == "not_ready"
    assert "classification_overlay_missing" in report.blockers
    assert "valuation_calibration_not_shadow_ready" in report.blockers
    assert all(value is False for value in report.automatic_actions.values())
    assert report.live_activation_allowed is False


def test_complete_stability_sample_reaches_human_review_but_never_activation() -> None:
    snapshots, outcomes, overlay = _sample()
    readiness = assess_valuation_calibration_readiness(snapshots, outcomes)
    assert readiness.status == "shadow_ready"

    report = assess_calibration_stability(snapshots, outcomes, readiness, overlay)

    assert report.status == "human_review_required"
    assert report.blockers == []
    assert report.valid_observation_count == 75
    assert report.unique_issuer_count == 25
    assert report.sector_count == 5
    assert report.market_phase_count == 3
    assert report.valuation_regime_count == 3
    assert report.directional_false_pass_count > 0
    assert report.directional_false_block_count > 0
    assert report.mean_excess_drift is not None
    assert report.live_activation_allowed is False
    assert report.report_sha256.startswith("sha256:")


def test_invalid_drawdown_excludes_outcome_from_stability_review() -> None:
    snapshots, outcomes, overlay = _sample()
    outcomes[0] = outcomes[0].model_copy(update={"instrument_max_drawdown": 0.1})
    readiness = assess_valuation_calibration_readiness(snapshots, outcomes)

    report = assess_calibration_stability(snapshots, outcomes, readiness, overlay)

    assert readiness.status == "not_ready"
    assert report.valid_observation_count == 74
    assert report.status == "not_ready"


def test_classification_overlay_rejects_content_changed_after_hash_binding() -> None:
    _, _, overlay = _sample()
    payload = overlay.model_dump(mode="json")
    payload["classifications"][0]["market_phase"] = "stressed"

    with pytest.raises(ValidationError, match="hash binding"):
        CalibrationClassificationOverlay.model_validate(payload)
