import csv
import json
import subprocess
from pathlib import Path

import pytest

from research_agent.calibration.retrospective_replay import (
    _git_commit,
    calculate_replay_manifest_sha256,
    promote_retrospective_snapshot,
    sanitize_companyfacts_as_of,
    sanitize_price_csv_as_of,
    verify_replay_manifest,
)
from research_agent.calibration.valuation_calibration import (
    RetrospectiveReplayArtifact,
    ValuationCalibrationReplayManifest,
    ValuationCalibrationSnapshot,
    file_sha256,
    load_retrospective_replay_snapshots,
)


HASH = "sha256:" + "a" * 64


def _companyfacts() -> dict:
    return {
        "facts": {
            "us-gaap": {
                "Revenue": {
                    "units": {
                        "USD": [
                            {"filed": "2025-07-30", "end": "2025-06-30", "val": 1},
                            {"filed": "2025-08-01", "end": "2025-06-30", "val": 2},
                            {"end": "2025-06-30", "val": 3},
                        ]
                    }
                }
            }
        }
    }


def _write_prices(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "close"])
        writer.writeheader()
        writer.writerows(
            [
                {"date": "2025-07-30", "close": "10"},
                {"date": "2025-07-31", "close": "11"},
                {"date": "2025-08-01", "close": "12"},
            ]
        )


def _snapshot() -> ValuationCalibrationSnapshot:
    return ValuationCalibrationSnapshot(
        snapshot_id="sha256:" + "b" * 64,
        ticker="TST",
        as_of_date="2025-07-31",
        method_id="dcf-v1",
        policy_version="v1",
        sensitivity_status="measured",
        price_series_basis="split_adjusted",
        price_basis_date="2025-07-31",
        share_basis="listed_share_count",
        current_price=11,
        current_value_position="inside_range",
        reverse_dcf_implied_fcf_growth=0.1,
        bear_upside=-0.2,
        base_upside=0.1,
        bull_upside=0.3,
        metrics_packet_sha256=HASH,
        authority_manifest_sha256=HASH,
        eligible=True,
    )


def test_companyfacts_and_prices_are_cut_off_without_lookahead(tmp_path: Path):
    sanitized, counts = sanitize_companyfacts_as_of(_companyfacts(), "2025-07-31")
    rows = sanitized["facts"]["us-gaap"]["Revenue"]["units"]["USD"]
    assert [row["val"] for row in rows] == [1]
    assert counts == {
        "companyfacts_rows_kept": 1,
        "companyfacts_future_rows_removed": 1,
        "companyfacts_undated_rows_removed": 1,
    }

    source = tmp_path / "raw.csv"
    target = tmp_path / "sanitized.csv"
    _write_prices(source)
    price_counts = sanitize_price_csv_as_of(source, target, "2025-07-31")
    with target.open("r", encoding="utf-8", newline="") as handle:
        assert [row["date"] for row in csv.DictReader(handle)] == [
            "2025-07-30",
            "2025-07-31",
        ]
    assert price_counts == {"price_rows_kept": 2, "price_future_rows_removed": 1}


def test_replay_manifest_is_hash_bound_and_promotes_a_distinct_snapshot(tmp_path: Path):
    raw_companyfacts = tmp_path / "inputs" / "raw_companyfacts.json"
    raw_prices = tmp_path / "inputs" / "raw_prices.csv"
    cik_records = tmp_path / "inputs" / "cik_records.json"
    sanitized_companyfacts = tmp_path / "sanitized" / "TST.json"
    sanitized_prices = tmp_path / "sanitized" / "TST.csv"
    authority_manifest = tmp_path / "outputs" / "authority_manifest.json"
    fact_ledger = tmp_path / "outputs" / "fact_ledger.json"
    base_snapshot_path = tmp_path / "outputs" / "valuation_calibration_snapshot.json"
    for path in (
        raw_companyfacts,
        raw_prices,
        cik_records,
        sanitized_companyfacts,
        sanitized_prices,
        authority_manifest,
        fact_ledger,
        base_snapshot_path,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
    raw_companyfacts.write_text(json.dumps(_companyfacts()), encoding="utf-8")
    _write_prices(raw_prices)
    sanitized_payload, _ = sanitize_companyfacts_as_of(_companyfacts(), "2025-07-31")
    sanitized_companyfacts.write_text(json.dumps(sanitized_payload), encoding="utf-8")
    sanitize_price_csv_as_of(raw_prices, sanitized_prices, "2025-07-31")
    cik_records.write_text('[{"ticker":"TST","cik":"1"}]', encoding="utf-8")
    authority_manifest.write_text(
        json.dumps(
            {
                "ticker": "TST",
                "as_of_date": "2025-07-31",
                "analysis_allowed": True,
            }
        ),
        encoding="utf-8",
    )
    fact_ledger.write_text(json.dumps({"claims": [{"asof": "2025-06-30"}]}), encoding="utf-8")
    base_snapshot = _snapshot()
    base_snapshot_path.write_text(base_snapshot.model_dump_json(), encoding="utf-8")
    paths = {
        "raw_companyfacts": raw_companyfacts,
        "raw_prices": raw_prices,
        "cik_records": cik_records,
        "sanitized_companyfacts": sanitized_companyfacts,
        "sanitized_prices": sanitized_prices,
        "authority_manifest": authority_manifest,
        "fact_ledger": fact_ledger,
        "base_valuation_snapshot": base_snapshot_path,
    }
    manifest = ValuationCalibrationReplayManifest(
        replay_id="sha256:" + "c" * 64,
        ticker="TST",
        as_of_date="2025-07-31",
        generated_at="2026-08-09T00:00:00+00:00",
        publication_allowed=False,
        pipeline_commit_sha="d" * 40,
        source_cutoff_passed=True,
        cutoff_counts={"companyfacts_future_rows_removed": 1},
        artifacts={
            name: RetrospectiveReplayArtifact(
                path=str(path.relative_to(tmp_path)), sha256=file_sha256(path)
            )
            for name, path in paths.items()
        },
    )
    manifest.replay_manifest_sha256 = calculate_replay_manifest_sha256(manifest)
    manifest_path = tmp_path / "retrospective_replay_manifest.json"
    manifest_path.write_text(manifest.model_dump_json(), encoding="utf-8")

    valid, reasons, _ = verify_replay_manifest(manifest_path)
    assert valid is True
    assert reasons == []
    promoted = promote_retrospective_snapshot(base_snapshot, manifest_path)
    assert promoted.eligible is True
    assert promoted.capture_mode == "retrospective_replay"
    assert promoted.base_snapshot_id == base_snapshot.snapshot_id
    assert promoted.snapshot_id != base_snapshot.snapshot_id
    assert promoted.retrospective_replay_manifest_sha256 == file_sha256(manifest_path)
    promoted_path = tmp_path / "outputs" / "valuation_calibration_replay_snapshot.json"
    promoted_path.write_text(promoted.model_dump_json(), encoding="utf-8")
    loaded = load_retrospective_replay_snapshots(tmp_path)
    assert [snapshot.snapshot_id for snapshot in loaded] == [promoted.snapshot_id]

    fact_ledger.write_text(json.dumps({"claims": [{"asof": "2025-08-01"}]}), encoding="utf-8")
    manifest.artifacts["fact_ledger"].sha256 = file_sha256(fact_ledger)
    manifest.replay_manifest_sha256 = calculate_replay_manifest_sha256(manifest)
    manifest_path.write_text(manifest.model_dump_json(), encoding="utf-8")
    valid, reasons, _ = verify_replay_manifest(manifest_path)
    assert valid is False
    assert "replay_fact_claim_after_cutoff" in reasons

    fact_ledger.write_text(json.dumps({"claims": [{"asof": "2025-06-30"}]}), encoding="utf-8")
    manifest.artifacts["fact_ledger"].sha256 = file_sha256(fact_ledger)
    manifest.replay_manifest_sha256 = calculate_replay_manifest_sha256(manifest)
    manifest_path.write_text(manifest.model_dump_json(), encoding="utf-8")
    sanitized_prices.write_text("date,close\n2025-07-31,999\n", encoding="utf-8")
    valid, reasons, _ = verify_replay_manifest(manifest_path)
    assert valid is False
    assert "replay_artifact_hash_mismatch:sanitized_prices" in reasons
    invalid = promote_retrospective_snapshot(base_snapshot, manifest_path)
    assert invalid.eligible is False
    assert "replay_artifact_hash_mismatch:sanitized_prices" in invalid.exclusion_reasons


def test_replay_pipeline_identity_requires_a_clean_git_commit(tmp_path: Path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "room16-test@example.invalid"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Room16 Test"], cwd=tmp_path, check=True)
    tracked = tmp_path / "pipeline.py"
    tracked.write_text("VERSION = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "pipeline.py"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=tmp_path, check=True)

    assert len(_git_commit(tmp_path)) == 40
    tracked.write_text("VERSION = 2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="clean committed pipeline worktree"):
        _git_commit(tmp_path)
