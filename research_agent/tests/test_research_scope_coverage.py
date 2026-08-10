from research_agent.quality.research_scope_coverage import (
    REQUIRED_SCOPE_IDS,
    build_research_scope_coverage,
    verify_research_scope_coverage,
)


def _scopes(status: str = "complete_no_candidates") -> list[dict[str, str]]:
    return [
        {"scope_id": scope_id, "status": status, "reason": "fixture"}
        for scope_id in sorted(REQUIRED_SCOPE_IDS)
    ]


def test_scope_coverage_is_distinct_and_complete() -> None:
    payload = build_research_scope_coverage(
        ticker="TEST",
        as_of_date="2026-08-10",
        jurisdiction="US",
        scopes=_scopes(),
    )

    assert payload["all_required_scopes_complete"] is True
    assert "Generated-claim evidence coverage is a separate metric" in payload[
        "semantic_note"
    ]
    assert verify_research_scope_coverage(payload)["status"] == "pass"


def test_scope_coverage_fails_for_missing_or_partial_domain() -> None:
    scopes = _scopes()
    scopes = [item for item in scopes if item["scope_id"] != "material_events"]
    next(
        item for item in scopes if item["scope_id"] == "legal_and_contingencies"
    )["status"] = "incomplete"
    payload = build_research_scope_coverage(
        ticker="TEST",
        as_of_date="2026-08-10",
        jurisdiction="US",
        scopes=scopes,
    )

    assert payload["all_required_scopes_complete"] is False
    assert payload["blocking_scope_gaps"] == [
        "missing:material_events",
        "incomplete:legal_and_contingencies",
    ]
    assert verify_research_scope_coverage(payload)["status"] == "fail"
