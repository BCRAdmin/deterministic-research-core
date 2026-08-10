from __future__ import annotations

import pytest

from research_agent.scale.change_detector import ChangeDetectorError, detect_authority_changes


def _manifest(**updates):
    value = {
        "contract_id": "room16.research_authority_bundle",
        "contract_version": 2,
        "ticker": "KO",
        "as_of_date": "2026-08-10",
        "pipeline_version": "research_agent_v0.1.0",
        "analysis_allowed": True,
        "blocking_failures": [],
        "rating_permission": {"preferred_rating": "Hold"},
        "artifacts": {"data_packet": {"sha256": "a" * 64}},
        "generated_at": "2026-08-10T10:00:00Z",
    }
    value.update(updates)
    return value


def test_change_detector_ignores_generation_timestamp_only() -> None:
    result = detect_authority_changes(
        _manifest(generated_at="2026-08-10T10:00:00Z"),
        _manifest(generated_at="2026-08-10T11:00:00Z"),
    )
    assert result["reviewRequired"] is False
    assert result["reviewTask"] is None
    assert all(action is False for action in result["automaticActions"].values())


def test_change_detector_creates_review_task_without_triggering_work() -> None:
    result = detect_authority_changes(
        _manifest(),
        _manifest(
            as_of_date="2026-08-11",
            artifacts={"data_packet": {"sha256": "b" * 64}},
            rating_permission={"preferred_rating": "Accumulate"},
        ),
    )
    assert result["reviewRequired"] is True
    assert result["reviewTask"]["type"] == "human_authority_change_review"
    assert set(result["reviewTask"]["changedFields"]) == {
        "as_of_date",
        "rating_permission",
        "artifacts",
    }
    assert all(action is False for action in result["automaticActions"].values())


def test_change_detector_rejects_cross_issuer_comparison() -> None:
    with pytest.raises(ChangeDetectorError, match="ticker_mismatch"):
        detect_authority_changes(_manifest(), _manifest(ticker="MCD"))
