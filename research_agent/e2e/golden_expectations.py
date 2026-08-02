from __future__ import annotations

from pathlib import Path

from research_agent.e2e.e2e_case import E2ECase, ExpectedIssue, ExpectedRatingCorridor


GOLDEN_E2E_CASES = {
    "amzn_2026_05_01": {
        "ticker": "AMZN",
        "preferred_rating": "Hold",
        "blocked_ratings": ["Sell", "Strong Buy"],
        "expected_issues": ["NO_NEWS_WITH_AVAILABLE_SOURCES", "NUMERIC_MISMATCH"],
        "minimum_quality_score_after_repair": 85,
        "expected_final_status": "repaired_publishable",
    },
    "nvda_2026_05_01": {
        "ticker": "NVDA",
        "preferred_rating": "Hold",
        "blocked_ratings": ["Sell", "Underweight"],
        "expected_issues": ["NUMERIC_MISMATCH", "PERIOD_MISMATCH"],
        "minimum_quality_score_after_repair": 85,
        "expected_final_status": "repaired_publishable",
    },
    "ddog_2026_05_01": {
        "ticker": "DDOG",
        "preferred_rating": "Hold",
        "blocked_ratings": ["Sell", "Strong Buy"],
        "expected_issues": ["INVALID_TRADE_LEVEL", "RATING_TOO_HARSH_FOR_ACTION"],
        "minimum_quality_score_after_repair": 85,
        "expected_final_status": "repaired_publishable",
    },
    "mdb_2026_05_01": {
        "ticker": "MDB",
        "preferred_rating": "Hold",
        "blocked_ratings": ["Sell", "Strong Buy"],
        "expected_issues": ["OVERSTATED_CAUSALITY", "FORWARD_EPS_GUIDANCE_MISMATCH", "RATING_TOO_HARSH_FOR_ACTION"],
        "minimum_quality_score_after_repair": 85,
        "expected_final_status": "repaired_publishable",
    },
}


def build_golden_case(case_id: str, fixture_root: str | Path = "research_agent/tests/fixtures") -> E2ECase:
    if case_id not in GOLDEN_E2E_CASES:
        raise KeyError(f"No golden E2E expectations for {case_id}")
    root = Path(fixture_root) / case_id
    spec = GOLDEN_E2E_CASES[case_id]
    return E2ECase(
        case_id=case_id,
        ticker=spec["ticker"],
        as_of_date="2026-05-01",
        original_report_path=str(root / "bad_report.md"),
        data_packet_path=str(root / "data_packet.json"),
        metrics_packet_path=str(root / "metrics_packet.json"),
        validation_report_path=str(root / "validation_report.json"),
        source_registry_path=str(root / "source_registry.json"),
        expected_issues=[ExpectedIssue(code=code) for code in spec["expected_issues"]],
        expected_rating=ExpectedRatingCorridor(
            preferred_rating=spec["preferred_rating"],
            blocked_ratings=spec["blocked_ratings"],
        ),
        minimum_quality_score=spec["minimum_quality_score_after_repair"],
        expected_final_status=spec["expected_final_status"],
    )


def build_all_golden_cases(fixture_root: str | Path = "research_agent/tests/fixtures") -> list[E2ECase]:
    return [build_golden_case(case_id, fixture_root) for case_id in sorted(GOLDEN_E2E_CASES)]
