from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from research_agent.scale.scale_contract import (
    ScaleContractError,
    ScalePlanRequest,
    build_scale_plan,
    execute_scale_plan,
    load_scale_plan,
    save_scale_plan,
    validate_scale_plan,
)


def _request(*items, interval=0.0):
    return ScalePlanRequest(
        as_of_date="2026-08-10",
        minimum_interval_seconds=interval,
        items=list(items),
    )


def test_scale_plan_binds_supported_markets_and_blocks_recognized_gaps() -> None:
    plan = build_scale_plan(
        _request(
            {"ticker": "KO", "jurisdiction": "US"},
            {"ticker": "MOL", "jurisdiction": "HU"},
            {"ticker": "7203", "jurisdiction": "JP"},
        )
    )

    assert plan["executionPolicy"]["mode"] == "plan_only"
    assert plan["executionPolicy"]["modelRunsAllowed"] is False
    assert [item["priceProviderId"] for item in plan["items"]] == ["nasdaq", "bse", None]
    assert plan["items"][2]["status"] == "blocked"
    assert "EDINET" in plan["items"][2]["reason"]
    validate_scale_plan(plan)


def test_scale_plan_rejects_duplicates_parallelism_and_more_than_1000_items() -> None:
    with pytest.raises(ValidationError, match="duplicate"):
        _request(
            {"ticker": "KO", "jurisdiction": "US"},
            {"ticker": "KO", "jurisdiction": "US"},
        )
    with pytest.raises(ValidationError, match="max_parallel_jobs"):
        ScalePlanRequest(
            as_of_date="2026-08-10",
            max_parallel_jobs=2,
            items=[{"ticker": "KO", "jurisdiction": "US"}],
        )
    with pytest.raises(ValidationError):
        _request(
            *(
                {"ticker": f"X{index}", "jurisdiction": "US"}
                for index in range(1_001)
            )
        )


def test_scale_plan_hash_blocks_tampering_and_wrong_confirmation(tmp_path) -> None:
    plan = build_scale_plan(_request({"ticker": "KO", "jurisdiction": "US"}))
    tampered = deepcopy(plan)
    tampered["items"][0]["priceProviderId"] = "massive"
    with pytest.raises(ScaleContractError, match="provider_binding|hash_invalid"):
        validate_scale_plan(tampered)
    with pytest.raises(ScaleContractError, match="confirmation_mismatch"):
        execute_scale_plan(
            plan,
            confirmation_sha256="0" * 64,
            runtime_root=tmp_path,
            research_runner=lambda request: pytest.fail("runner must not be called"),
        )


def test_scale_plan_round_trip_is_runtime_only(tmp_path) -> None:
    plan = build_scale_plan(_request({"ticker": "KO", "jurisdiction": "US"}))
    path = save_scale_plan(plan, runtime_root=tmp_path)
    assert path == tmp_path / "plans" / f"{plan['planSha256']}.json"
    assert load_scale_plan(path) == plan


def test_scale_execution_is_sequential_isolates_failures_and_resumes(tmp_path) -> None:
    calls = []

    def first_runner(request):
        calls.append((request.ticker, request.price_provider, request.output_root))
        if request.ticker == "FAIL":
            raise RuntimeError("provider unavailable")
        return {"authority_bundle": f"/authority/{request.ticker}", "analysis_allowed": True}

    plan = build_scale_plan(
        _request(
            {"ticker": "KO", "jurisdiction": "US"},
            {"ticker": "FAIL", "jurisdiction": "US"},
            {"ticker": "7203", "jurisdiction": "JP"},
        )
    )
    state = execute_scale_plan(
        plan,
        confirmation_sha256=plan["planSha256"],
        runtime_root=tmp_path,
        research_runner=first_runner,
        sleeper=lambda seconds: pytest.fail("zero interval must not sleep"),
    )

    assert [item["status"] for item in state["items"]] == ["completed", "failed", "blocked"]
    assert [call[:2] for call in calls] == [("KO", "nasdaq"), ("FAIL", "nasdaq")]
    assert all(str(tmp_path) in call[2] for call in calls)
    assert state["automaticActions"] == {
        "modelRun": False,
        "reportPublish": False,
        "codexTask": False,
        "gitWrite": False,
    }

    retry_calls = []

    def retry_runner(request):
        retry_calls.append(request.ticker)
        return {"authority_bundle": f"/authority/{request.ticker}", "analysis_allowed": True}

    resumed = execute_scale_plan(
        plan,
        confirmation_sha256=plan["planSha256"],
        runtime_root=tmp_path,
        research_runner=retry_runner,
        sleeper=lambda seconds: None,
        retry_failures=True,
    )
    assert retry_calls == ["FAIL"]
    assert [item["status"] for item in resumed["items"]] == [
        "completed",
        "completed",
        "blocked",
    ]
