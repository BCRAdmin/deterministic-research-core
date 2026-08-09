import csv
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from research_agent.calibration.valuation_calibration import (
    ValuationCalibrationSnapshot,
    load_valuation_source_bundles,
)
from research_agent.calibration.valuation_outcome_workbench import (
    build_valuation_outcome_workbench,
    load_normalized_price_csv,
    main,
)


HASH = "sha256:" + "a" * 64


def _snapshot(*, eligible: bool = True) -> ValuationCalibrationSnapshot:
    return ValuationCalibrationSnapshot(
        snapshot_id="sha256:" + "b" * 64,
        ticker="TST",
        as_of_date="2025-01-02",
        sector="Industrials",
        sector_source_sha256=HASH,
        method_id="dcf-v1",
        policy_version="v1",
        sensitivity_status="measured",
        price_series_basis="corporate_action_adjusted",
        price_basis_date="2025-01-02",
        share_basis="listed_share_count",
        current_price=100,
        current_value_position="inside_range",
        reverse_dcf_implied_fcf_growth=0.1,
        bear_upside=-0.2,
        base_upside=0.1,
        bull_upside=0.3,
        metrics_packet_sha256=HASH,
        authority_manifest_sha256=HASH,
        eligible=eligible,
        exclusion_reasons=[] if eligible else ["fixture_ineligible"],
    )


def _write_snapshot(path: Path, *, eligible: bool = True) -> Path:
    path.write_text(_snapshot(eligible=eligible).model_dump_json(), encoding="utf-8")
    return path


def _write_prices(path: Path, *, count: int = 253) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "close"])
        writer.writeheader()
        for index in range(count):
            writer.writerow(
                {
                    "date": (date(2025, 1, 2) + timedelta(days=index)).isoformat(),
                    "close": 100 + index,
                }
            )
    return path


def _verified_inputs(tmp_path: Path) -> dict:
    snapshot = _write_snapshot(tmp_path / "snapshot.json")
    instrument = _write_prices(tmp_path / "instrument.csv")
    benchmark = _write_prices(tmp_path / "benchmark.csv")
    methodology = tmp_path / "methodology.txt"
    rights = tmp_path / "rights.txt"
    verification = tmp_path / "verification.txt"
    methodology.write_text("Provider total-return methodology", encoding="utf-8")
    rights.write_text("Internal calibration use approved", encoding="utf-8")
    verification.write_text("Independent human verification record", encoding="utf-8")
    return {
        "mode": "verified",
        "snapshot_path": snapshot,
        "instrument_series_path": instrument,
        "benchmark_series_path": benchmark,
        "provider_id": "TEST_PROVIDER",
        "provider_dataset_id": "TOTAL_RETURN_DAILY_V1",
        "benchmark": "TEST_TR_INDEX",
        "retrieved_at": "2025-12-31T12:00:00+00:00",
        "instrument_price_series_basis": "total_return_adjusted",
        "benchmark_price_series_basis": "total_return_adjusted",
        "instrument_cash_distributions_included": True,
        "benchmark_cash_distributions_included": True,
        "instrument_corporate_actions_included": True,
        "benchmark_corporate_actions_included": True,
        "provider_methodology_path": methodology,
        "usage_rights_evidence_path": rights,
        "verification_evidence_path": verification,
        "prepared_by": "Room16 preparation workbench",
        "rights_approved_by": "Rights Reviewer",
        "rights_approved_at": "2025-12-31T13:00:00+00:00",
        "verified_by": "Independent Data Reviewer",
        "verified_at": "2026-01-01T12:00:00+00:00",
        "approve_internal_calibration_rights": True,
        "confirm_independent_review": True,
        "output_dir": tmp_path / "outcome",
    }


def test_draft_materializes_review_packet_but_never_claims_verified_source(tmp_path):
    snapshot = _write_snapshot(tmp_path / "snapshot.json")
    instrument = _write_prices(tmp_path / "instrument.csv", count=2)
    benchmark = _write_prices(tmp_path / "benchmark.csv", count=2)
    target = tmp_path / "draft"

    status = build_valuation_outcome_workbench(
        mode="draft",
        snapshot_path=snapshot,
        instrument_series_path=instrument,
        benchmark_series_path=benchmark,
        provider_id="candidate-provider",
        provider_dataset_id="visible-close-candidate",
        benchmark="candidate-benchmark",
        retrieved_at="2025-01-04T12:00:00+00:00",
        instrument_price_series_basis="split_adjusted_or_raw_close",
        benchmark_price_series_basis="split_adjusted_or_raw_close",
        instrument_cash_distributions_included=False,
        benchmark_cash_distributions_included=False,
        instrument_corporate_actions_included=False,
        benchmark_corporate_actions_included=False,
        provider_methodology_path=None,
        usage_rights_evidence_path=None,
        verification_evidence_path=None,
        prepared_by="Room16 preparation workbench",
        rights_approved_by=None,
        rights_approved_at=None,
        verified_by=None,
        verified_at=None,
        approve_internal_calibration_rights=False,
        confirm_independent_review=False,
        output_dir=target,
    )

    assert status.source_contract_valid is False
    assert status.outcome_status == "invalidated"
    assert "source_bundle_usage_rights_not_approved" in status.source_contract_reasons
    assert "instrument_total_return_adjustment_not_verified" in status.source_contract_reasons
    assert "source_bundle_human_verification_missing" in status.source_contract_reasons
    assert (target / "evidence" / "instrument_series.csv").is_file()
    packet = (target / "valuation_calibration_review_packet.md").read_text(encoding="utf-8")
    assert "Live-Aktivierung erlaubt: `false`" in packet
    assert "nicht geprüft" in packet
    with pytest.raises(FileExistsError, match="already exists and is not empty"):
        build_valuation_outcome_workbench(
            mode="draft",
            snapshot_path=snapshot,
            instrument_series_path=instrument,
            benchmark_series_path=benchmark,
            provider_id="candidate-provider",
            provider_dataset_id="visible-close-candidate",
            benchmark="candidate-benchmark",
            retrieved_at="2025-01-04T12:00:00+00:00",
            instrument_price_series_basis="raw_close",
            benchmark_price_series_basis="raw_close",
            instrument_cash_distributions_included=False,
            benchmark_cash_distributions_included=False,
            instrument_corporate_actions_included=False,
            benchmark_corporate_actions_included=False,
            provider_methodology_path=None,
            usage_rights_evidence_path=None,
            verification_evidence_path=None,
            prepared_by="Room16 preparation workbench",
            rights_approved_by=None,
            rights_approved_at=None,
            verified_by=None,
            verified_at=None,
            approve_internal_calibration_rights=False,
            confirm_independent_review=False,
            output_dir=target,
        )


def test_verified_workbench_builds_self_contained_matured_source_bundle(tmp_path):
    inputs = _verified_inputs(tmp_path)

    status = build_valuation_outcome_workbench(**inputs)

    assert status.source_contract_valid is True
    assert status.source_contract_reasons == []
    assert status.outcome_status == "matured"
    assert status.live_activation_allowed is False
    source_bundles = load_valuation_source_bundles(inputs["output_dir"])
    assert len(source_bundles) == 1
    assert source_bundles[0].schema_id == "room16.valuation_calibration_source_bundle@2"
    assert source_bundles[0].verification_independent_from_preparation is True
    assert (inputs["output_dir"] / "evidence" / "human_verification.txt").is_file()

    (inputs["output_dir"] / "evidence" / "instrument_series.csv").write_text(
        "date,close\n2025-01-02,999\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="instrument_source_artifact_hash_mismatch"):
        load_valuation_source_bundles(inputs["output_dir"])


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"approve_internal_calibration_rights": False}, "rights approval"),
        ({"confirm_independent_review": False}, "independent-review confirmation"),
        ({"verified_by": "DeepSeek reviewer"}, "cannot satisfy human verification"),
        (
            {"prepared_by": "Björn Rösinger", "verified_by": "Bjorn Rosinger"},
            "independent from the preparer",
        ),
        ({"retrieved_at": "2025-12-31T12:00:00"}, "include a timezone"),
        (
            {"instrument_price_series_basis": "split_adjusted"},
            "must be total_return_adjusted",
        ),
    ],
)
def test_verified_workbench_rejects_unproven_gate_claims(tmp_path, override, message):
    inputs = _verified_inputs(tmp_path)
    inputs.update(override)

    with pytest.raises(ValueError, match=message):
        build_valuation_outcome_workbench(**inputs)

    assert not inputs["output_dir"].exists()


def test_verified_workbench_rejects_ineligible_snapshot_and_reused_verification_file(
    tmp_path,
):
    inputs = _verified_inputs(tmp_path)
    _write_snapshot(inputs["snapshot_path"], eligible=False)
    with pytest.raises(ValueError, match="eligible valuation snapshot"):
        build_valuation_outcome_workbench(**inputs)

    inputs = _verified_inputs(tmp_path)
    inputs["verification_evidence_path"] = inputs["usage_rights_evidence_path"]
    with pytest.raises(ValueError, match="separate artifact"):
        build_valuation_outcome_workbench(**inputs)


def test_verified_workbench_rejects_observations_after_retrieval_without_partial_output(
    tmp_path,
):
    inputs = _verified_inputs(tmp_path)
    inputs["retrieved_at"] = "2025-02-01T12:00:00+00:00"
    inputs["rights_approved_at"] = "2025-02-01T13:00:00+00:00"
    inputs["verified_at"] = "2025-02-02T12:00:00+00:00"

    with pytest.raises(ValueError, match="source_bundle_observation_after_retrieval"):
        build_valuation_outcome_workbench(**inputs)

    assert not inputs["output_dir"].exists()


def test_normalized_price_loader_rejects_duplicates_and_nonpositive_values(tmp_path):
    duplicate = tmp_path / "duplicate.csv"
    duplicate.write_text("date,close\n2025-01-02,100\n2025-01-02,101\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate date"):
        load_normalized_price_csv(duplicate)

    nonpositive = tmp_path / "nonpositive.csv"
    nonpositive.write_text("date,close\n2025-01-02,0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="nonpositive"):
        load_normalized_price_csv(nonpositive)

    noncanonical_date = tmp_path / "noncanonical-date.csv"
    noncanonical_date.write_text("date,close\n2025-1-2,100\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid date"):
        load_normalized_price_csv(noncanonical_date)


def test_cli_materializes_draft_and_returns_machine_readable_status(tmp_path, monkeypatch, capsys):
    snapshot = _write_snapshot(tmp_path / "snapshot.json")
    instrument = _write_prices(tmp_path / "instrument.csv", count=2)
    benchmark = _write_prices(tmp_path / "benchmark.csv", count=2)
    target = tmp_path / "cli-draft"
    monkeypatch.setattr(
        "sys.argv",
        [
            "valuation_outcome_workbench",
            "--mode",
            "draft",
            "--snapshot",
            str(snapshot),
            "--instrument-series",
            str(instrument),
            "--benchmark-series",
            str(benchmark),
            "--provider-id",
            "candidate-provider",
            "--provider-dataset-id",
            "candidate-dataset",
            "--benchmark",
            "BENCH",
            "--retrieved-at",
            "2025-01-04T12:00:00+00:00",
            "--instrument-series-basis",
            "raw-close",
            "--benchmark-series-basis",
            "raw-close",
            "--prepared-by",
            "Room16 workbench",
            "--output-dir",
            str(target),
        ],
    )

    assert main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "draft"
    assert payload["source_contract_valid"] is False
    assert payload["live_activation_allowed"] is False
