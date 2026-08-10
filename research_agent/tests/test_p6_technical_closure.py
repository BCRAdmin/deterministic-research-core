from __future__ import annotations

from research_agent.ops.p6_technical_closure import evaluate


def test_p6_surface_is_technically_ready_but_not_performance_ready() -> None:
    report = evaluate()
    assert report["status"] == "technically_ready_for_human_verification"
    assert report["technicalScopeComplete"] is True
    assert report["performanceClaimsAllowed"] is False
    assert report["liveCalibrationActivationAllowed"] is False
    assert report["singleReportSharpeAllowed"] is False
    assert report["automaticRatingOrWeightChangeAllowed"] is False
    assert report["counts"] == {"requirements": 7, "passed": 7, "blocked": 0}
