from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from research_agent.alpha_shared.observation_registry import label_profiles


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ops/run_fixed24_no_tuning_batch.py"
SPEC = importlib.util.spec_from_file_location("holdout12_p1_recovery_test", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def test_reit_operational_profile_uses_current_generic_registry_ids() -> None:
    assert RUNNER.PROFILE_METRICS["reit"] == (
        "reported_ffo",
        "reported_core_ffo",
        "reported_affo",
        "occupancy",
        "same_store_noi",
    )
    assert "adjusted_ffo" not in RUNNER.PROFILE_METRICS["reit"]
    assert set(RUNNER.PROFILE_METRICS["reit"]) <= set(label_profiles())


def test_saas_operational_profile_is_unchanged() -> None:
    assert RUNNER.PROFILE_METRICS["saas"] == ("crpo", "guidance")


def test_all_operational_profile_requests_validate_deterministically() -> None:
    first = RUNNER.validate_profile_metric_requests()
    second = RUNNER.validate_profile_metric_requests()
    assert tuple(first) == ("saas", "reit", "bank", "energy")
    assert tuple(first) == tuple(second)
    assert {
        profile: tuple(requests) for profile, requests in first.items()
    } == {
        profile: RUNNER.PROFILE_METRICS[profile] for profile in RUNNER.PROFILE_METRICS
    }


def test_missing_profile_label_blocks_before_provider_callback() -> None:
    provider_calls = 0

    def provider_callback() -> None:
        nonlocal provider_calls
        provider_calls += 1

    with pytest.raises(
        RuntimeError,
        match="SUPPLEMENTAL_PROFILE_LABEL_MISSING:reit:synthetic_missing",
    ):
        RUNNER.validate_profile_metric_requests({"reit": ("synthetic_missing",)})
        provider_callback()
    assert provider_calls == 0


def test_duplicate_profile_label_blocks() -> None:
    with pytest.raises(
        RuntimeError, match="SUPPLEMENTAL_PROFILE_LABEL_DUPLICATE:reit"
    ):
        RUNNER.validate_profile_metric_requests(
            {"reit": ("reported_affo", "reported_affo")}
        )
