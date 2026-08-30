from __future__ import annotations

import pytest

from research_agent.alpha_shared.dynamic_disk_guard import (
    GIB,
    DiskGuardPolicy,
    evaluate_disk_guard,
)


def test_guard_is_measured_and_reports_explicit_reserves() -> None:
    report = evaluate_disk_guard(
        free_before=8 * GIB,
        measured_case_peaks=(50_000_000, 70_000_000),
        comparator_peaks=(100_000_000,),
        evidence_refs=("recovery8:TFC", "fixed24:largest-bank-energy"),
    )
    assert report["decision"] == "PASS"
    assert report["absolute_floor"] >= 2 * GIB
    assert report["safety_factor"] >= 3
    assert report["package_reserve"] > 0
    assert report["predicted_peak"] == 100_000_000


def test_guard_blocks_before_callback_when_headroom_is_insufficient() -> None:
    provider_calls = 0
    report = evaluate_disk_guard(
        free_before=2 * GIB - 1,
        measured_case_peaks=(1,),
    )
    if report["decision"] == "PASS":
        provider_calls += 1
    assert report["decision"] == "STOP"
    assert provider_calls == 0


def test_policy_rejects_weak_floor_or_factor() -> None:
    with pytest.raises(ValueError, match="FLOOR"):
        DiskGuardPolicy(absolute_floor=GIB)
    with pytest.raises(ValueError, match="FACTOR"):
        DiskGuardPolicy(safety_factor=2)

