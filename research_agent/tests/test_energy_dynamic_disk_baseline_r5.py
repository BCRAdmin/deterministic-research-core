from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest

from scripts.ops import run_energy_recovery_sec_suffix_r3 as runner


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _write_result(
    path: Path,
    *,
    measured: list[object] | None = None,
    comparators: list[object] | None = None,
    events: list[dict[str, object]] | None = None,
    include_disk: bool = True,
    include_run: bool = True,
    guard_sequence: int = 1,
    guard_ticker: str = "STT",
    guard_decision: str = "PASS",
) -> str:
    disk = {
        "cases": [
            {
                "sequence": guard_sequence,
                "ticker": guard_ticker,
                "decision": guard_decision,
                "measured_case_peaks": measured if measured is not None else [11, 13, 17],
                "comparator_peaks": comparators if comparators is not None else [19],
            }
        ]
    }
    run = {
        "events": events
        if events is not None
        else [{"sequence": 1, "ticker": "STT", "status": "COMPLETE", "actual_peak_bytes": 23}]
    }
    payloads: dict[str, bytes] = {}
    if include_disk:
        payloads[runner.DYNAMIC_DISK_LEDGER_MEMBER] = json.dumps(disk).encode()
    if include_run:
        payloads[runner.RECOVERY4_RUN_LEDGER_MEMBER] = json.dumps(run).encode()
    manifest_body: dict[str, Any] = {
        "files": [
            {"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in sorted(payloads.items())
        ]
    }
    manifest = {**manifest_body, "manifest_sha256": runner.sha256_json(manifest_body)}
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in payloads.items():
            archive.writestr(name, data)
        archive.writestr("MANIFEST.json", json.dumps(manifest))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bind_fixture(monkeypatch: pytest.MonkeyPatch, path: Path) -> dict[str, Any]:
    outer_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("MANIFEST.json"))
    monkeypatch.setattr(runner, "PRIOR_RESULT_SHA256", outer_sha)
    monkeypatch.setattr(runner, "PRIOR_RESULT_MANIFEST", manifest["manifest_sha256"])
    disk = json.loads(zipfile.ZipFile(path).read(runner.DYNAMIC_DISK_LEDGER_MEMBER))
    run = json.loads(zipfile.ZipFile(path).read(runner.RECOVERY4_RUN_LEDGER_MEMBER))
    measured = disk["cases"][0]["measured_case_peaks"]
    comparators = disk["cases"][0]["comparator_peaks"]
    actual = next(
        (
            item["actual_peak_bytes"]
            for item in run.get("events", [])
            if "actual_peak_bytes" in item
        ),
        23,
    )
    body = {
        "contract_id": "room16.dynamic_disk_baseline_evidence@1",
        "source_result_sha256": outer_sha,
        "source_result_manifest_sha256": manifest["manifest_sha256"],
        "source_files": [runner.DYNAMIC_DISK_LEDGER_MEMBER, runner.RECOVERY4_RUN_LEDGER_MEMBER],
        "baseline_measured_case_peaks": [*measured, actual],
        "baseline_comparator_peaks": comparators,
        "stt_actual_peak_bytes": actual,
        "derivation": {
            "recovery8_measured_from_first_stt_guard": measured,
            "fixed24_comparator_from_first_stt_guard": comparators,
            "completed_stt_actual_peak_from_run_ledger": actual,
        },
        "numbers_hardcoded_without_source": False,
    }
    monkeypatch.setattr(runner, "DISK_BASELINE_SHA256", runner.sha256_json(body))
    return body


def test_loads_hash_bound_baseline_and_selfhashed_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "baseline.zip"
    _write_result(source)
    body = _bind_fixture(monkeypatch, source)
    receipt = runner.load_dynamic_disk_baseline(source)
    assert receipt["baseline_measured_case_peaks"] == body["baseline_measured_case_peaks"]
    assert receipt["baseline_comparator_peaks"] == body["baseline_comparator_peaks"]
    receipt_body = dict(receipt)
    claim = receipt_body.pop("receipt_sha256")
    assert claim == runner.sha256_json(receipt_body)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"include_disk": False}, "SOURCE_MEMBER_MISSING"),
        ({"include_run": False}, "SOURCE_MEMBER_MISSING"),
        ({"measured": []}, "MEASURED_EMPTY"),
        ({"measured": [0]}, "MEASURED_PEAK_INVALID"),
        ({"measured": ["11"]}, "MEASURED_PEAK_INVALID"),
        ({"comparators": [0]}, "COMPARATOR_INVALID"),
        ({"comparators": ["19"]}, "COMPARATOR_INVALID"),
        ({"events": []}, "STT_COMPLETE_MISSING"),
        (
            {"events": [{"sequence": 1, "ticker": "STT", "status": "COMPLETE"}]},
            "STT_ACTUAL_PEAK_INVALID",
        ),
        ({"measured": [11, 11]}, "DUPLICATE_PEAK"),
        ({"measured": [11], "comparators": [11]}, "DUPLICATE_PEAK"),
        ({"guard_sequence": 2}, "STT_GUARD_INVALID"),
        ({"guard_ticker": "VLO"}, "STT_GUARD_INVALID"),
        ({"guard_decision": "STOP"}, "STT_GUARD_INVALID"),
    ],
)
def test_malformed_baseline_blocks_before_provider_use(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kwargs: dict[str, Any],
    message: str,
) -> None:
    source = tmp_path / "baseline.zip"
    _write_result(source, **kwargs)
    if kwargs.get("include_disk", True) and kwargs.get("include_run", True):
        _bind_fixture(monkeypatch, source)
    else:
        monkeypatch.setattr(runner, "PRIOR_RESULT_SHA256", hashlib.sha256(source.read_bytes()).hexdigest())
        with zipfile.ZipFile(source) as archive:
            manifest = json.loads(archive.read("MANIFEST.json"))
        monkeypatch.setattr(runner, "PRIOR_RESULT_MANIFEST", manifest["manifest_sha256"])
    provider_calls = 0
    with pytest.raises(RuntimeError, match=message):
        runner.load_dynamic_disk_baseline(source)
        provider_calls += 1
    assert provider_calls == 0


def test_wrong_outer_sha_blocks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "baseline.zip"
    _write_result(source)
    monkeypatch.setattr(runner, "PRIOR_RESULT_SHA256", "0" * 64)
    with pytest.raises(RuntimeError, match="RESULT_HASH_MISMATCH"):
        runner.load_dynamic_disk_baseline(source)


def test_wrong_manifest_blocks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "baseline.zip"
    _write_result(source)
    outer_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    monkeypatch.setattr(runner, "PRIOR_RESULT_SHA256", outer_sha)
    monkeypatch.setattr(runner, "PRIOR_RESULT_MANIFEST", "0" * 64)
    with pytest.raises(RuntimeError, match="MANIFEST_MISMATCH"):
        runner.load_dynamic_disk_baseline(source)


def test_guard_stop_does_not_call_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    body = {
        "contract_id": "room16.dynamic_disk_baseline_receipt@1",
        "baseline_sha256": "a" * 64,
        "source_result_sha256": "b" * 64,
        "source_result_manifest_sha256": "c" * 64,
        "source_payload_sha256": {},
        "stt_guard_sequence": 1,
        "stt_guard_ticker": "STT",
        "stt_guard_decision": "PASS",
        "baseline_measured_case_peaks": [1024**3],
        "baseline_comparator_peaks": [1024**3],
        "evidence_refs": ["fixture"],
    }
    receipt = {**body, "receipt_sha256": runner.sha256_json(body)}
    monkeypatch.setattr(runner.shutil, "disk_usage", lambda _: type("D", (), {"free": 1})())
    guard = runner._guard_from_baseline(receipt, measured=[1024**3], evidence_refs=("fixture",))
    provider_calls = 0
    if guard["decision"] == "PASS":
        provider_calls += 1
    assert guard["decision"] == "STOP"
    assert provider_calls == 0


def test_finalization_reverifies_bound_runtime_freeze_without_case_or_provider_work(
    tmp_path: Path,
) -> None:
    output = tmp_path / "r5-runtime"
    runtime = output / "_runtime"
    runtime.mkdir(parents=True)
    expected = "d" * 64
    (runtime / "15_ENERGY_RECOVERY_FREEZE.json").write_text(
        json.dumps({"freeze_sha256": expected})
    )

    provider_calls = 0
    case_executions = 0
    with pytest.raises(FileNotFoundError):
        runner._read(output / "15_ENERGY_RECOVERY_FREEZE.json")

    freeze = runner.verify_runtime_energy_freeze(output, expected)
    assert freeze["freeze_sha256"] == expected
    assert provider_calls == 0
    assert case_executions == 0


def test_finalization_rejects_runtime_freeze_drift(tmp_path: Path) -> None:
    output = tmp_path / "r5-runtime"
    runtime = output / "_runtime"
    runtime.mkdir(parents=True)
    (runtime / "15_ENERGY_RECOVERY_FREEZE.json").write_text(
        json.dumps({"freeze_sha256": "e" * 64})
    )

    with pytest.raises(RuntimeError, match="ENERGY_RECOVERY_FREEZE_DRIFT"):
        runner.verify_runtime_energy_freeze(output, "f" * 64)
