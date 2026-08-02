from research_agent.e2e.e2e_runner import E2ERunner
from research_agent.e2e.golden_expectations import build_golden_case


def test_e2e_ddog_invalid_stop_repaired(tmp_path):
    result = E2ERunner(tmp_path).run_case(build_golden_case("ddog_2026_05_01"))

    assert result.passed
    assert result.initial_audit.has_issue("INVALID_TRADE_LEVEL")
    assert result.initial_audit.has_issue("RATING_TOO_HARSH_FOR_ACTION")
    assert not result.final_audit.has_issue("INVALID_TRADE_LEVEL")
    assert result.decision_packet.rating_permission.preferred_rating.value == "Hold"
    assert "Sell" in {rating.value for rating in result.decision_packet.rating_permission.blocked_ratings}
