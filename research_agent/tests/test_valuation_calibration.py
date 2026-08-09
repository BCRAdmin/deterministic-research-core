import hashlib
import json
from datetime import date, timedelta
from typing import Optional

import pytest

from research_agent.calibration.valuation_calibration import (
    MIN_EFFECTIVE_SAMPLES,
    ValuationCalibrationOutcome,
    ValuationCalibrationPricePoint,
    assess_valuation_calibration_readiness,
    build_valuation_calibration_outcome,
    build_valuation_calibration_snapshot,
    file_sha256,
    save_valuation_calibration_snapshot,
    scan_authority_root,
)
from research_agent.research_core.calculations.valuation import (
    calculate_valuation_metrics,
)
from research_agent.research_core.models.metrics_packet import (
    FundamentalMetrics,
    MetricsPacket,
    TechnicalMetrics,
)


HASH = "sha256:" + hashlib.sha256(b"fixture").hexdigest()


def _metrics(
    ticker: str = "TEST",
    as_of_date: str = "2025-01-02",
    price_series_basis: str = "corporate_action_adjusted",
) -> MetricsPacket:
    fundamentals = FundamentalMetrics(
        fiscal_period="FY2024",
        revenue_growth_yoy=0.08,
        revenue_ttm=1_000,
        operating_income_ttm=150,
        net_income_ttm=100,
        operating_cash_flow_ttm=160,
        capex_ttm=40,
        free_cash_flow_ttm=120,
        cash_and_equivalents=200,
        total_debt=100,
        listed_share_count=10,
    )
    return MetricsPacket(
        ticker=ticker,
        as_of_date=as_of_date,
        technical=TechnicalMetrics(
            indicator_date=as_of_date,
            close=100,
            price_series_basis=price_series_basis,
        ),
        fundamentals=fundamentals,
        valuation=calculate_valuation_metrics(100, fundamentals),
    )


def _snapshot(
    ticker: str = "TEST",
    as_of_date: str = "2025-01-02",
    sector: Optional[str] = "Industrials",
):
    return build_valuation_calibration_snapshot(
        _metrics(ticker=ticker, as_of_date=as_of_date),
        metrics_packet_sha256=HASH,
        authority_manifest_sha256=HASH,
        authority_analysis_allowed=True,
        sector=sector,
        sector_source_sha256=HASH,
    )


def _outcome(snapshot, **overrides):
    payload = {
        "snapshot_id": snapshot.snapshot_id,
        "status": "matured",
        "horizon_trading_days": 252,
        "trading_observation_count": 252,
        "benchmark": "BENCH",
        "basis_date": snapshot.price_basis_date,
        "observed_through": (date.fromisoformat(snapshot.as_of_date) + timedelta(days=370)).isoformat(),
        "instrument_return": 0.12,
        "benchmark_return": 0.07,
        "excess_return": 0.05,
        "instrument_price_series_basis": "total_return_adjusted",
        "benchmark_price_series_basis": "total_return_adjusted",
        "source_hash": HASH,
    }
    payload.update(overrides)
    return ValuationCalibrationOutcome(**payload)


def test_snapshot_requires_measured_dcf_but_not_adjusted_historical_technicals():
    eligible = _snapshot()
    unadjusted_technicals = build_valuation_calibration_snapshot(
        _metrics(price_series_basis="unadjusted_or_provider_default"),
        metrics_packet_sha256=HASH,
        authority_manifest_sha256=HASH,
        authority_analysis_allowed=True,
    )

    assert eligible.eligible
    assert eligible.base_upside is not None
    assert unadjusted_technicals.eligible
    assert unadjusted_technicals.price_series_basis == "unadjusted_or_provider_default"


def test_sector_overlay_does_not_rewrite_immutable_snapshot_id():
    metrics = _metrics()
    first = build_valuation_calibration_snapshot(
        metrics,
        metrics_packet_sha256=HASH,
        authority_manifest_sha256=HASH,
        authority_analysis_allowed=True,
        sector="Technology",
        sector_source_sha256=HASH,
    )
    second = build_valuation_calibration_snapshot(
        metrics,
        metrics_packet_sha256=HASH,
        authority_manifest_sha256=HASH,
        authority_analysis_allowed=True,
        sector="Industrials",
        sector_source_sha256="sha256:" + "a" * 64,
    )

    assert first.snapshot_id == second.snapshot_id


def test_scanner_reuses_and_verifies_saved_snapshot(tmp_path):
    bundle = tmp_path / "TEST" / "2025-01-02" / "authority_bundle"
    bundle.mkdir(parents=True)
    metrics_path = bundle / "metrics_packet.json"
    manifest_path = bundle / "authority_manifest.json"
    metrics_path.write_text(
        json.dumps(_metrics().model_dump(mode="json"), sort_keys=True),
        encoding="utf-8",
    )
    manifest_path.write_text('{"analysis_allowed": true}', encoding="utf-8")
    snapshot = build_valuation_calibration_snapshot(
        _metrics(),
        metrics_packet_sha256=file_sha256(metrics_path),
        authority_manifest_sha256=file_sha256(manifest_path),
        authority_analysis_allowed=True,
    )
    snapshot_path = bundle.parent / "valuation_calibration_snapshot.json"
    save_valuation_calibration_snapshot(snapshot, snapshot_path)

    scanned = scan_authority_root(
        tmp_path,
        sectors={"TEST": "Technology"},
        sector_source_sha256=HASH,
    )

    assert scanned[0].snapshot_id == snapshot.snapshot_id
    assert scanned[0].sector == "Technology"

    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    payload["base_upside"] = 99.0
    snapshot_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="does not match its authority bundle"):
        scan_authority_root(tmp_path)


def test_snapshot_stays_ineligible_without_approved_authority_bundle():
    missing = build_valuation_calibration_snapshot(
        _metrics(),
        metrics_packet_sha256=HASH,
    )
    rejected = build_valuation_calibration_snapshot(
        _metrics(),
        metrics_packet_sha256=HASH,
        authority_manifest_sha256=HASH,
        authority_analysis_allowed=False,
    )

    assert not missing.eligible
    assert "authority_manifest_hash_missing" in missing.exclusion_reasons
    assert "authority_bundle_not_approved" in missing.exclusion_reasons
    assert not rejected.eligible
    assert rejected.exclusion_reasons == ["authority_bundle_not_approved"]


def test_readiness_stays_closed_without_matured_252d_outcomes():
    readiness = assess_valuation_calibration_readiness([_snapshot()], [])

    assert readiness.status == "not_ready"
    assert readiness.valid_matured_outcome_count == 0
    assert readiness.invalid_outcome_reasons == {"matured_outcome_missing": 1}
    assert not readiness.live_activation_allowed


def test_invalid_outcome_cannot_enter_calibration_sample():
    snapshot = _snapshot()
    invalid = _outcome(
        snapshot,
        instrument_price_series_basis="split_adjusted",
        excess_return=0.04,
    )

    readiness = assess_valuation_calibration_readiness([snapshot], [invalid])

    assert readiness.valid_matured_outcome_count == 0
    assert readiness.invalid_outcome_reasons[
        "outcome_instrument_series_not_total_return_adjusted"
    ] == 1
    assert readiness.invalid_outcome_reasons["outcome_excess_return_mismatch"] == 1


def test_orphan_outcome_is_reported_instead_of_silently_ignored():
    snapshot = _snapshot()
    orphan = _outcome(snapshot, snapshot_id="sha256:" + "f" * 64)

    readiness = assess_valuation_calibration_readiness([snapshot], [orphan])

    assert readiness.invalid_outcome_reasons["outcome_snapshot_missing"] == 1
    assert readiness.invalid_outcome_reasons["matured_outcome_missing"] == 1


def test_sufficient_diverse_sample_enters_shadow_only():
    sectors = ["Industrials", "Technology", "Healthcare", "Consumer", "Energy"]
    snapshots = []
    outcomes = []
    for index in range(MIN_EFFECTIVE_SAMPLES):
        ticker = f"T{index // 3:02d}"
        snapshot = _snapshot(
            ticker=ticker,
            as_of_date=(date(2022, 1, 3) + timedelta(days=index)).isoformat(),
            sector=sectors[index % len(sectors)],
        )
        snapshots.append(snapshot)
        outcomes.append(_outcome(snapshot))

    readiness = assess_valuation_calibration_readiness(snapshots, outcomes)

    assert readiness.status == "shadow_ready"
    assert readiness.effective_sample_count == MIN_EFFECTIVE_SAMPLES
    assert readiness.unique_issuer_count == 25
    assert readiness.sector_count == 5
    assert not readiness.live_activation_allowed


def test_outcome_builder_uses_only_common_future_adjusted_observations():
    snapshot = _snapshot(as_of_date="2025-01-02")
    instrument = [
        ValuationCalibrationPricePoint(
            date=(date(2025, 1, 1) + timedelta(days=index)).isoformat(),
            close=100 + index,
        )
        for index in range(0, 370)
    ]
    benchmark = [
        ValuationCalibrationPricePoint(
            date=(date(2025, 1, 1) + timedelta(days=index)).isoformat(),
            close=200 + index,
        )
        for index in range(0, 370)
    ]

    outcome = build_valuation_calibration_outcome(
        snapshot,
        benchmark="BENCH",
        instrument_prices=instrument,
        benchmark_prices=benchmark,
        instrument_price_series_basis="total_return_adjusted",
        benchmark_price_series_basis="total_return_adjusted",
    )

    assert outcome.status == "matured"
    assert outcome.trading_observation_count == 252
    assert outcome.basis_date == "2025-01-02"
    assert outcome.first_observation_date == "2025-01-03"
    assert outcome.observed_through == "2025-09-11"
    assert outcome.excess_return == round(
        outcome.instrument_return - outcome.benchmark_return,
        12,
    )


def test_outcome_builder_stays_pending_before_252_common_observations():
    snapshot = _snapshot()
    prices = [
        ValuationCalibrationPricePoint(
            date=(date(2025, 1, 2) + timedelta(days=index)).isoformat(),
            close=100 + index,
        )
        for index in range(100)
    ]

    outcome = build_valuation_calibration_outcome(
        snapshot,
        benchmark="BENCH",
        instrument_prices=prices,
        benchmark_prices=prices,
        instrument_price_series_basis="total_return_adjusted",
        benchmark_price_series_basis="total_return_adjusted",
    )

    assert outcome.status == "pending"
    assert outcome.trading_observation_count == 99
    assert outcome.instrument_return is None
