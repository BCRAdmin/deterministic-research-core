import hashlib
import json
from datetime import date, timedelta
from typing import Optional

import pytest

from research_agent.calibration.valuation_calibration import (
    MIN_EFFECTIVE_SAMPLES,
    ValuationCalibrationOutcome,
    ValuationCalibrationPricePoint,
    ValuationCalibrationSourceBundle,
    assess_valuation_calibration_readiness,
    build_valuation_calibration_outcome,
    build_valuation_calibration_outcomes,
    build_valuation_calibration_snapshot,
    calculate_source_bundle_sha256,
    file_sha256,
    load_valuation_source_bundles,
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
        "instrument_basis_price": 100.0,
        "benchmark_basis_price": 100.0,
        "first_observation_date": (
            date.fromisoformat(snapshot.price_basis_date) + timedelta(days=1)
        ).isoformat(),
        "observed_through": (
            date.fromisoformat(snapshot.as_of_date) + timedelta(days=370)
        ).isoformat(),
        "instrument_return": 0.12,
        "benchmark_return": 0.07,
        "excess_return": 0.05,
        "instrument_price_series_basis": "total_return_adjusted",
        "benchmark_price_series_basis": "total_return_adjusted",
        "source_hash": HASH,
    }
    payload.update(overrides)
    return ValuationCalibrationOutcome(**payload)


def _source_bundle(
    snapshot,
    instrument_prices,
    benchmark_prices,
    **overrides,
):
    retrieval_date = date.fromisoformat(snapshot.price_basis_date) + timedelta(days=370)
    payload = {
        "snapshot_id": snapshot.snapshot_id,
        "provider_id": "TEST_PROVIDER",
        "provider_dataset_id": "TEST_TOTAL_RETURN_DAILY_V1",
        "instrument": snapshot.ticker,
        "benchmark": "BENCH",
        "basis_date": snapshot.price_basis_date,
        "retrieved_at": f"{retrieval_date.isoformat()}T12:00:00+00:00",
        "instrument_price_series_basis": "total_return_adjusted",
        "benchmark_price_series_basis": "total_return_adjusted",
        "instrument_cash_distributions_included": True,
        "benchmark_cash_distributions_included": True,
        "instrument_corporate_actions_included": True,
        "benchmark_corporate_actions_included": True,
        "provider_methodology_sha256": HASH,
        "usage_rights_status": "internal_calibration_allowed",
        "usage_rights_evidence_sha256": HASH,
        "instrument_source_sha256": HASH,
        "benchmark_source_sha256": HASH,
        "verification_status": "human_verified",
        "verified_by": "independent_test_reviewer",
        "verified_at": f"{(retrieval_date + timedelta(days=1)).isoformat()}T12:00:00+00:00",
        "verification_evidence_sha256": HASH,
        "instrument_prices": instrument_prices,
        "benchmark_prices": benchmark_prices,
    }
    payload.update(overrides)
    source_bundle = ValuationCalibrationSourceBundle(**payload)
    return source_bundle.model_copy(
        update={"source_bundle_sha256": calculate_source_bundle_sha256(source_bundle)}
    )


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
    assert (
        readiness.invalid_outcome_reasons["outcome_instrument_series_not_total_return_adjusted"]
        == 1
    )
    assert readiness.invalid_outcome_reasons["outcome_excess_return_mismatch"] == 1


def test_orphan_outcome_is_reported_instead_of_silently_ignored():
    snapshot = _snapshot()
    orphan = _outcome(snapshot, snapshot_id="sha256:" + "f" * 64)

    readiness = assess_valuation_calibration_readiness([snapshot], [orphan])

    assert readiness.invalid_outcome_reasons["outcome_snapshot_missing"] == 1
    assert readiness.invalid_outcome_reasons["matured_outcome_missing"] == 1


def test_same_issuer_date_cannot_be_counted_twice_across_pipeline_replays():
    first = _snapshot()
    second = first.model_copy(
        update={
            "snapshot_id": "sha256:" + "e" * 64,
            "capture_mode": "retrospective_replay",
            "base_snapshot_id": first.snapshot_id,
            "retrospective_replay_manifest_sha256": HASH,
        }
    )

    readiness = assess_valuation_calibration_readiness(
        [first, second], [_outcome(first), _outcome(second)]
    )

    assert readiness.valid_matured_outcome_count == 0
    assert readiness.excluded_snapshot_reasons == {"duplicate_snapshot_observation": 2}
    assert readiness.invalid_outcome_reasons == {"outcome_snapshot_not_eligible": 2}
    assert readiness.capture_mode_counts == {
        "contemporaneous": 1,
        "retrospective_replay": 1,
    }


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

    source_bundle = _source_bundle(snapshot, instrument, benchmark)
    outcome = build_valuation_calibration_outcome(snapshot, source_bundle)

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
        _source_bundle(snapshot, prices, prices),
    )

    assert outcome.status == "pending"
    assert outcome.trading_observation_count == 99
    assert outcome.instrument_return is None


def test_source_bundle_requires_distributions_actions_and_human_evidence():
    snapshot = _snapshot()
    prices = [
        ValuationCalibrationPricePoint(date="2025-01-02", close=100),
        ValuationCalibrationPricePoint(date="2025-01-03", close=101),
    ]
    source_bundle = _source_bundle(
        snapshot,
        prices,
        prices,
        instrument_cash_distributions_included=False,
        benchmark_cash_distributions_included=False,
        instrument_corporate_actions_included=False,
        benchmark_corporate_actions_included=False,
        verification_status="unverified",
        verified_by=None,
        verified_at=None,
        verification_evidence_sha256=None,
        usage_rights_status="unverified",
        usage_rights_evidence_sha256=None,
    )

    outcome = build_valuation_calibration_outcome(snapshot, source_bundle)

    assert outcome.status == "invalidated"
    assert "instrument_cash_distributions_not_verified" in outcome.notes
    assert "benchmark_cash_distributions_not_verified" in outcome.notes
    assert "instrument_corporate_actions_not_verified" in outcome.notes
    assert "benchmark_corporate_actions_not_verified" in outcome.notes
    assert "source_bundle_human_verification_missing" in outcome.notes
    assert "verification_evidence_hash_invalid" in outcome.notes
    assert "source_bundle_usage_rights_not_approved" in outcome.notes
    assert "usage_rights_evidence_hash_invalid" in outcome.notes


def test_source_bundle_tampering_is_detected_before_outcome_calculation():
    snapshot = _snapshot()
    prices = [
        ValuationCalibrationPricePoint(date="2025-01-02", close=100),
        ValuationCalibrationPricePoint(date="2025-01-03", close=101),
    ]
    source_bundle = _source_bundle(snapshot, prices, prices)
    tampered_prices = list(source_bundle.instrument_prices)
    tampered_prices[-1] = ValuationCalibrationPricePoint(
        date="2025-01-03",
        close=999,
    )
    tampered = source_bundle.model_copy(update={"instrument_prices": tampered_prices})

    outcome = build_valuation_calibration_outcome(snapshot, tampered)

    assert outcome.status == "invalidated"
    assert "source_bundle_hash_mismatch" in outcome.notes


def test_conflicting_duplicate_price_observation_is_invalidated():
    snapshot = _snapshot()
    instrument = [
        ValuationCalibrationPricePoint(date="2025-01-02", close=100),
        ValuationCalibrationPricePoint(date="2025-01-03", close=101),
        ValuationCalibrationPricePoint(date="2025-01-03", close=102),
    ]
    benchmark = [
        ValuationCalibrationPricePoint(date="2025-01-02", close=200),
        ValuationCalibrationPricePoint(date="2025-01-03", close=201),
    ]

    outcome = build_valuation_calibration_outcome(
        snapshot,
        _source_bundle(snapshot, instrument, benchmark),
    )

    assert outcome.status == "invalidated"
    assert "conflicting_duplicate_price_observation" in outcome.notes


def test_future_dated_and_nonpositive_source_observations_are_invalidated():
    snapshot = _snapshot()
    prices = [
        ValuationCalibrationPricePoint(date="2025-01-02", close=100),
        ValuationCalibrationPricePoint(date="2027-01-10", close=0),
    ]

    outcome = build_valuation_calibration_outcome(
        snapshot,
        _source_bundle(snapshot, prices, prices),
    )

    assert outcome.status == "invalidated"
    assert "source_bundle_observation_after_retrieval" in outcome.notes
    assert "nonpositive_or_nonfinite_price_observation" in outcome.notes


def test_orphan_source_bundle_builds_visible_invalid_outcome():
    snapshot = _snapshot()
    prices = [ValuationCalibrationPricePoint(date="2025-01-02", close=100)]
    source_bundle = _source_bundle(snapshot, prices, prices).model_copy(
        update={"snapshot_id": "sha256:" + "f" * 64}
    )
    source_bundle = source_bundle.model_copy(
        update={"source_bundle_sha256": calculate_source_bundle_sha256(source_bundle)}
    )

    outcomes = build_valuation_calibration_outcomes([snapshot], [source_bundle])
    readiness = assess_valuation_calibration_readiness([snapshot], outcomes)

    assert outcomes[0].status == "invalidated"
    assert outcomes[0].notes == ["source_bundle_snapshot_missing"]
    assert readiness.invalid_outcome_reasons["outcome_snapshot_missing"] == 1


def test_source_bundle_loader_is_strict_and_missing_root_is_not_silent(tmp_path):
    snapshot = _snapshot()
    prices = [ValuationCalibrationPricePoint(date="2025-01-02", close=100)]
    source_bundle = _source_bundle(snapshot, prices, prices)
    source_root = tmp_path / "sources"
    source_root.mkdir()
    (source_root / "test.json").write_text(
        json.dumps(source_bundle.model_dump(mode="json")),
        encoding="utf-8",
    )

    loaded = load_valuation_source_bundles(source_root)

    assert loaded == [source_bundle]
    with pytest.raises(FileNotFoundError, match="source root does not exist"):
        load_valuation_source_bundles(tmp_path / "missing")

    payload = source_bundle.model_dump(mode="json")
    payload["unsupported_assertion"] = True
    (source_root / "test.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        load_valuation_source_bundles(source_root)
